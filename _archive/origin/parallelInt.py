"""
parallelInt.py

Parallel execution engine for Origin ASTs.

Takes the real ProgramNode AST object from parser.Parser, performs dependency
analysis directly on node objects, groups statements into wave-front stages,
then executes each stage using a dynamically-scaled thread pool â€”
one thread per independent statement in that stage.

Usage (in runnerAlt.py):
    from parallelInt import parallelInt
    origin = parallelInt.gen(ast)
"""

import threading
from collections import defaultdict
from interpreter import interpreter
import sys

# â”€â”€ 1. NODE SCHEMA â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

NODE_SCHEMA = {
    "AssignNode":      {"write_attr": "name",     "recurse_attr": ["value"]},
    "ConstAssignNode": {"write_attr": "name",     "recurse_attr": ["value"]},
    "openNode":        {"write_attr": "name",     "recurse_attr": ["path"]},
    "AugAssignNode":   {"write_attr": "name",     "read_attr": "name", "recurse_attr": ["value"]},
    "FuncNode":        {"write_attr": "name",     "recurse_attr": ["body"]},
    "ClassNode":       {"write_attr": "name"},
    "VarNode":         {"read_attr":  "name"},
    "IncrNode":        {"read_attr":  "name",     "write_attr": "name"},
    "DecrNode":        {"read_attr":  "name",     "write_attr": "name"},
    "BinOpNode":       {"recurse_attr": ["left",  "right"]},
    "UnaryOpNode":     {"recurse_attr": ["node"]},
    "CastNode":        {"recurse_attr": ["value"]},
    "SqrtNode":        {"recurse_attr": ["value"]},
    "RandNumNode":     {"recurse_attr": ["start", "end"]},
    "RangeNode":       {"recurse_attr": ["start", "end"]},
    "ListNode":        {"recurse_attr": ["elements"]},
    "DictNode":        {"recurse_attr": ["elements"]},
    "ListCallNode":    {"recurse_attr": ["list_node", "pos"]},
    "AttributeNode":   {"recurse_attr": ["obj"]},
    "CallNode":        {"recurse_attr": "all"},
    "IfNode":          {"recurse_attr": ["condition", "then_body", "else_body"]},
    "ElifNode":        {"recurse_attr": ["condition", "then_body", "else_body"]},
    "WhileNode":       {"recurse_attr": ["condition", "body"]},
    "ForNode":         {"write_attr":  "var", "recurse_attr": ["iterable", "body"]},
    "TryNode":         {"recurse_attr": ["try_body", "except_body"]},
    "BlockNode":       {"recurse_attr": ["statements"]},
    "ReturnNode":      {"recurse_attr": ["value"]},
    "PrintNode":       {"recurse_attr": ["expr"],   "side_effect": True},
    "InputNode":       {"recurse_attr": ["prompt"], "side_effect": True},
    "SetNode":         {"recurse_attr": ["num", "params"], "side_effect": True},
    "ExecNode":        {"side_effect": True},
    "ImportNode":      {"side_effect": True},
    "ImportFromNode":  {"side_effect": True},
    "ImportAsNode":    {"side_effect": True},
    "ParallelNode":    {"side_effect": True},
}

_LEAF_NODES    = {"NumberNode", "StringNode", "NoneNode", "PassNode"}
_TYPE_KEYWORDS = {"None", "int", "float", "str", "bool", "list", "dict", "tuple"}


# â”€â”€ 2. DEPENDENCY EXTRACTOR â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _collect(node, reads: set, writes: set, side_effects: list):
    if node is None or not hasattr(node, "__class__"):
        return

    kind = type(node).__name__

    if kind in ("str", "int", "float", "bool", "NoneType") or kind in _LEAF_NODES:
        return

    schema = NODE_SCHEMA.get(kind, {"recurse_attr": "all"})

    wa = schema.get("write_attr")
    if wa:
        val = getattr(node, wa, None)
        # Support different target shapes: plain string, VarNode, or Tuple/List of VarNode
        if isinstance(val, str) and val not in _TYPE_KEYWORDS:
            writes.add(val)
        elif hasattr(val, 'name') and isinstance(val.name, str):
            writes.add(val.name)
        elif isinstance(val, list) or getattr(val, '__class__', None) and type(val).__name__ in ("TupleNode", "ListNode"):
            # Iterate elements
            elements = getattr(val, 'elements', val)
            for el in elements:
                if hasattr(el, 'name') and isinstance(el.name, str):
                    writes.add(el.name)

    ra = schema.get("read_attr")
    if ra:
        val = getattr(node, ra, None)
        if isinstance(val, str) and val not in _TYPE_KEYWORDS:
            reads.add(val)

    if schema.get("side_effect"):
        side_effects.append(kind)

    recurse = schema.get("recurse_attr", [])
    attrs = (
        [k for k in vars(node) if not k.startswith("_")]
        if recurse == "all"
        else recurse
    )

    for attr in attrs:
        child = getattr(node, attr, None)
        if child is None:
            continue
        if isinstance(child, list):
            for item in child:
                _collect(item, reads, writes, side_effects)
        elif isinstance(child, dict):
            for item in list(child.keys()) + list(child.values()):
                _collect(item, reads, writes, side_effects)
        elif type(child).__name__ not in ("str", "int", "float", "bool", "NoneType"):
            _collect(child, reads, writes, side_effects)


def _analyze(statements: list) -> list:
    result = []
    for stmt in statements:
        reads, writes, sfx = set(), set(), []
        _collect(stmt, reads, writes, sfx)
        result.append({
            "stmt": stmt,
            "reads":  reads,
            "writes": writes,
            "has_side_effect": bool(sfx),
        })
    return result


# â”€â”€ 3. WAVE-FRONT SCHEDULER â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _schedule(info: list) -> dict:
    n     = len(info)
    stage = [0] * n

    for j in range(n):
        for i in range(j):
            if (
                info[i]["writes"] & info[j]["reads"]               # RAW
                or info[i]["writes"] & info[j]["writes"]           # WAW
                or info[i]["reads"]  & info[j]["writes"]           # WAR
                or (info[i]["has_side_effect"] and info[j]["has_side_effect"])  # SFIO
            ):
                stage[j] = max(stage[j], stage[i] + 1)

    groups: dict = defaultdict(list)
    for idx, s in enumerate(stage):
        groups[s].append(idx)

    return dict(sorted(groups.items()))


# â”€â”€ 4. PARALLEL EXECUTOR â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class parallelInt:

    @staticmethod
    def gen(ast, shared_globals: dict = None, verbose: bool = True) -> str:
        if shared_globals is None:
            shared_globals = {}

        interp     = interpreter()
        info       = _analyze(ast.statements)
        groups     = _schedule(info)
        all_code   = []

        for stage_num, indices in groups.items():
            stage_stmts = [info[i]["stmt"] for i in indices]
            n_threads   = len(stage_stmts)

            if verbose:
                label = f"PARALLEL x{n_threads}" if n_threads > 1 else "sequential"
                print(f"[parallelInt] Stage {stage_num} [{label}]")

            code_chunks = []
            for stmt in stage_stmts:
                try:
                    chunk = interp.generate(stmt)
                except Exception as e:
                    chunk = f"# codegen error in {type(stmt).__name__}: {e}"
                code_chunks.append(chunk)
                all_code.append(chunk)

            if n_threads == 1:
                parallelInt._exec(code_chunks[0], shared_globals, verbose)
            else:
                threads = [
                    threading.Thread(
                        target=parallelInt._exec,
                        args=(chunk, shared_globals, verbose),
                        name=f"s{stage_num}t{i}",
                        daemon=True,
                    )
                    for i, chunk in enumerate(code_chunks)
                ]
                for t in threads: t.start()
                for t in threads: t.join()  # barrier â€” next stage waits for all

        return "\n".join(all_code)

    @staticmethod
    def _exec(code: str, shared_globals: dict, verbose: bool):
        if not code or code.startswith("#"):
            return
        try:
            if verbose:
                t = threading.current_thread().name
                print(f"[parallelInt]   [{t}] {code[:72].strip()}")
            exec(compile(code, "<origin>", "exec"), shared_globals)
            sys.stdout.flush()  # â† add this
        except Exception as e:
            t = threading.current_thread().name
            print(f"[parallelInt]   [{t}] RUNTIME ERROR: {e}\n  code: {code}")

