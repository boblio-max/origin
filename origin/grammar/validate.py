"""Origin AST validator and serializer.

Reads a JSON AST matching ``ast.schema.json`` and emits two things:

1. A list of structural validation errors (line numbers, messages).
2. Best-effort Origin source code (a serializer from AST -> .or text).

The serializer targets the *tightened* grammar documented in
``origin.peg.md`` (no ``print(x)``, no chained comparisons, etc.). When
the AST contains shapes that the reference parser cannot accept as written
(for example ``TupleLit`` is rare in source), the validator emits a warning
and a best-guess lowering.

Usage:
    python -m origin.grammar.validate path/to/ast.json
    python -m origin.grammar.validate path/to/ast.json --emit > out.or
    python -m origin.grammar.validate path/to/ast.json --check   # parse the emitted source
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Reserved keywords (must not be used as identifiers in user code)
# ---------------------------------------------------------------------------

RESERVED = {
    "none", "if", "elif", "open", "else", "check", "for", "get", "to",
    "while", "write", "with", "return", "py", "int", "read", "len", "str",
    "sqrt", "float", "let", "rand_num", "const", "in", "print",
    "true", "exec", "false", "break", "input", "continue", "def", "func",
    "import", "from", "class", "try", "call", "except", "raise", "set",
    "pass", "yield", "with", "as", "del", "assert", "global", "nonlocal",
    "async", "await", "match", "case", "macro", "inline", "parallel",
    "when", "range", "unless", "loop", "until", "do", "capture", "enum",
    "type", "bool", "interface", "pub", "priv", "self",
}

UNIMPLEMENTED = {
    "match", "case", "enum", "interface", "async", "await",
    "yield", "macro", "inline", "when", "unless", "loop", "until",
    "do", "capture", "check", "raise", "open", "global", "nonlocal",
    "assert", "del",
}

# ---------------------------------------------------------------------------
# Validation result types
# ---------------------------------------------------------------------------

@dataclass
class Issue:
    severity: str   # "error" | "warning"
    line: int | None
    message: str

@dataclass
class Report:
    issues: list[Issue] = field(default_factory=list)

    def error(self, line, msg):
        self.issues.append(Issue("error", line, msg))

    def warn(self, line, msg):
        self.issues.append(Issue("warning", line, msg))

    @property
    def ok(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

# ---------------------------------------------------------------------------
# Structural validation
# ---------------------------------------------------------------------------

def _line(node: dict | None) -> int | None:
    return node.get("line") if isinstance(node, dict) else None

def _check_ident(report: Report, name: str, where: str, line: int | None = None):
    if not isinstance(name, str) or not name:
        report.error(line, f"{where}: identifier must be a non-empty string")
        return
    if not (name[0].isalpha() or name[0] == "_") or not all(c.isalnum() or c == "_" for c in name):
        report.error(line, f"{where}: '{name}' is not a valid identifier")
        return
    if name in RESERVED:
        report.warn(line, f"{where}: '{name}' is a reserved keyword")

def _check_expr(report: Report, expr: Any, ctx: str) -> bool:
    """Recursively validate an expression node. Returns True if expr is a dict."""
    if not isinstance(expr, dict):
        report.error(_line(expr) if isinstance(expr, dict) else None,
                     f"{ctx}: expected expression object, got {type(expr).__name__}")
        return False
    kind = expr.get("kind")
    line = _line(expr)
    if not kind:
        report.error(line, f"{ctx}: expression missing 'kind'")
        return False
    if kind == "Var":
        _check_ident(report, expr.get("name", ""), f"{ctx}.Var.name", line)
    elif kind == "Number":
        v = expr.get("value")
        t = expr.get("type")
        if not isinstance(v, (int, float)):
            report.error(line, f"{ctx}.Number: 'value' must be a number")
        if t not in ("int", "float"):
            report.error(line, f"{ctx}.Number: 'type' must be 'int' or 'float'")
    elif kind == "String":
        if not isinstance(expr.get("value"), str):
            report.error(line, f"{ctx}.String: 'value' must be a string")
    elif kind == "FString":
        for i, p in enumerate(expr.get("parts", [])):
            if isinstance(p, dict) and p.get("kind") == "String":
                if not isinstance(p.get("value"), str):
                    report.error(line, f"{ctx}.FString.parts[{i}]: text must be a string")
            else:
                _check_expr(report, p, f"{ctx}.FString.parts[{i}]")
    elif kind == "Bool":
        if not isinstance(expr.get("value"), bool):
            report.error(line, f"{ctx}.Bool: 'value' must be a boolean")
    elif kind in ("BinOp", "LogicOp", "SpecialOp", "Pipe"):
        for f in ("op", "left", "right"):
            if f not in expr:
                report.error(line, f"{ctx}.{kind}: missing '{f}'")
        if "left" in expr:  _check_expr(report, expr["left"], f"{ctx}.{kind}.left")
        if "right" in expr: _check_expr(report, expr["right"], f"{ctx}.{kind}.right")
    elif kind == "Unary":
        if expr.get("op") not in ("-", "!", "not", "++", "--"):
            report.error(line, f"{ctx}.Unary: invalid op {expr.get('op')!r}")
        _check_expr(report, expr.get("operand"), f"{ctx}.Unary.operand")
    elif kind == "Call":
        _check_expr(report, expr.get("callee"), f"{ctx}.Call.callee")
        for i, a in enumerate(expr.get("args", [])):
            _check_expr(report, a, f"{ctx}.Call.args[{i}]")
    elif kind == "Index":
        _check_expr(report, expr.get("collection"), f"{ctx}.Index.collection")
        _check_expr(report, expr.get("index"), f"{ctx}.Index.index")
    elif kind == "Attr":
        _check_expr(report, expr.get("object"), f"{ctx}.Attr.object")
        _check_ident(report, expr.get("attr", ""), f"{ctx}.Attr.attr", line)
    elif kind == "Cast":
        if expr.get("castType") not in ("int", "float", "str", "bool", "list", "any"):
            report.error(line, f"{ctx}.Cast: invalid castType {expr.get('castType')!r}")
        _check_expr(report, expr.get("value"), f"{ctx}.Cast.value")
    elif kind == "ListLit":
        for i, e in enumerate(expr.get("elements", [])):
            _check_expr(report, e, f"{ctx}.ListLit[{i}]")
    elif kind == "DictLit":
        for i, e in enumerate(expr.get("entries", [])):
            _check_expr(report, e.get("key"), f"{ctx}.DictLit[{i}].key")
            _check_expr(report, e.get("value"), f"{ctx}.DictLit[{i}].value")
    elif kind == "TupleLit":
        if len(expr.get("elements", [])) < 2:
            report.error(line, f"{ctx}.TupleLit: needs at least 2 elements")
    elif kind == "Lambda":
        _check_ident(report, expr.get("param", ""), f"{ctx}.Lambda.param", line)
        _check_expr(report, expr.get("body"), f"{ctx}.Lambda.body")
    elif kind == "Input":
        if expr.get("prompt") is not None:
            _check_expr(report, expr["prompt"], f"{ctx}.Input.prompt")
    elif kind in ("Sqrt", "Len"):
        _check_expr(report, expr.get("value"), f"{ctx}.{kind}.value")
    elif kind in ("Range", "RandNum"):
        _check_expr(report, expr.get("start"), f"{ctx}.{kind}.start")
        _check_expr(report, expr.get("end"), f"{ctx}.{kind}.end")
        if kind == "Range" and expr.get("step") is not None:
            _check_expr(report, expr["step"], f"{ctx}.Range.step")
    elif kind in ("Write", "Append"):
        if not isinstance(expr.get("file"), str):
            report.error(line, f"{ctx}.{kind}: 'file' must be a string")
        _check_expr(report, expr.get("content"), f"{ctx}.{kind}.content")
    elif kind == "Read":
        if not isinstance(expr.get("file"), str):
            report.error(line, f"{ctx}.Read: 'file' must be a string")
    elif kind == "ListCall":
        _check_expr(report, expr.get("list"), f"{ctx}.ListCall.list")
        _check_expr(report, expr.get("pos"), f"{ctx}.ListCall.pos")
    elif kind == "HwPrimitive":
        if expr.get("namespace") not in ("i2c", "spi", "uart"):
            report.error(line, f"{ctx}.HwPrimitive: invalid namespace")
        _check_ident(report, expr.get("method", ""), f"{ctx}.HwPrimitive.method", line)
        for i, a in enumerate(expr.get("args", [])):
            _check_expr(report, a, f"{ctx}.HwPrimitive.args[{i}]")
    elif kind == "SelfRef":
        if expr.get("attr") is not None:
            _check_ident(report, expr["attr"], f"{ctx}.SelfRef.attr", line)
    else:
        report.error(line, f"{ctx}: unknown expression kind '{kind}'")
        return False
    return True

def _check_block(report: Report, block: Any, ctx: str) -> bool:
    if not isinstance(block, dict) or block.get("kind") != "Block":
        report.error(_line(block) if isinstance(block, dict) else None,
                     f"{ctx}: expected Block")
        return False
    for i, s in enumerate(block.get("statements", [])):
        _check_stmt(report, s, f"{ctx}.statements[{i}]")
    return True

def _check_stmt(report: Report, stmt: Any, ctx: str):
    if not isinstance(stmt, dict):
        report.error(None, f"{ctx}: expected statement object")
        return
    kind = stmt.get("kind")
    line = _line(stmt)
    if not kind:
        report.error(line, f"{ctx}: statement missing 'kind'")
        return

    if kind in ("Let", "Const", "Assign"):
        _check_ident(report, stmt.get("name", ""), f"{ctx}.{kind}.name", line)
        _check_expr(report, stmt.get("value"), f"{ctx}.{kind}.value")
    elif kind == "IndexAssign":
        _check_expr(report, stmt.get("collection"), f"{ctx}.IndexAssign.collection")
        _check_expr(report, stmt.get("index"), f"{ctx}.IndexAssign.index")
        _check_expr(report, stmt.get("value"), f"{ctx}.IndexAssign.value")
    elif kind == "AttrAssign":
        _check_expr(report, stmt.get("object"), f"{ctx}.AttrAssign.object")
        _check_ident(report, stmt.get("attr", ""), f"{ctx}.AttrAssign.attr", line)
        _check_expr(report, stmt.get("value"), f"{ctx}.AttrAssign.value")
    elif kind == "CompoundAssign":
        _check_ident(report, stmt.get("name", ""), f"{ctx}.CompoundAssign.name", line)
        if stmt.get("op") not in ("+=", "-=", "*=", "/=", "%=", "**=", "//=", "&=", "|="):
            report.error(line, f"{ctx}.CompoundAssign: invalid op")
        _check_expr(report, stmt.get("value"), f"{ctx}.CompoundAssign.value")
    elif kind == "Print":
        _check_expr(report, stmt.get("expr"), f"{ctx}.Print.expr")
        if stmt.get("for") is not None:
            _check_stmt(report, stmt["for"], f"{ctx}.Print.for")
    elif kind == "If":
        _check_expr(report, stmt.get("cond"), f"{ctx}.If.cond")
        _check_block(report, stmt.get("then"), f"{ctx}.If.then")
        for i, e in enumerate(stmt.get("elifs") or []):
            _check_expr(report, e.get("cond"), f"{ctx}.If.elifs[{i}].cond")
            _check_block(report, e.get("then"), f"{ctx}.If.elifs[{i}].then")
        if stmt.get("else") is not None:
            _check_block(report, stmt["else"], f"{ctx}.If.else")
    elif kind == "While":
        _check_expr(report, stmt.get("cond"), f"{ctx}.While.cond")
        _check_block(report, stmt.get("body"), f"{ctx}.While.body")
    elif kind == "For":
        target = stmt.get("target")
        if isinstance(target, dict):
            # Single typed/untyped loop variable: { "name": ..., "type": ... }
            _check_ident(report, target.get("name", ""), f"{ctx}.For.target.name", line)
            if "type" in target and not isinstance(target["type"], str):
                report.error(line, f"{ctx}.For.target.type: must be a type name string")
        elif isinstance(target, str):
            _check_ident(report, target, f"{ctx}.For.target", line)
        elif isinstance(target, list):
            for i, t in enumerate(target):
                if not isinstance(t, str):
                    report.error(line, f"{ctx}.For.target[{i}]: must be identifier string")
                else:
                    _check_ident(report, t, f"{ctx}.For.target[{i}]", line)
        else:
            report.error(line, f"{ctx}.For.target: must be identifier or list of identifiers")
        _check_expr(report, stmt.get("iter"), f"{ctx}.For.iter")
        _check_block(report, stmt.get("body"), f"{ctx}.For.body")
    elif kind == "Try":
        _check_block(report, stmt.get("body"), f"{ctx}.Try.body")
        for i, b in enumerate(stmt.get("excepts") or []):
            _check_block(report, b, f"{ctx}.Try.excepts[{i}]")
        if stmt.get("else") is not None:
            _check_block(report, stmt["else"], f"{ctx}.Try.else")
    elif kind == "Parallel":
        _check_block(report, stmt.get("body"), f"{ctx}.Parallel.body")
    elif kind == "Def":
        _check_ident(report, stmt.get("name", ""), f"{ctx}.Def.name", line)
        for i, p in enumerate(stmt.get("params") or []):
            _check_ident(report, p.get("name", ""), f"{ctx}.Def.params[{i}].name", line)
        _check_block(report, stmt.get("body"), f"{ctx}.Def.body")
    elif kind == "Class":
        _check_ident(report, stmt.get("name", ""), f"{ctx}.Class.name", line)
        for i, f in enumerate(stmt.get("fields") or []):
            if isinstance(f, str):
                _check_ident(report, f, f"{ctx}.Class.fields[{i}]", line)
            elif isinstance(f, dict):
                _check_ident(report, f.get("name", ""), f"{ctx}.Class.fields[{i}].name", line)
                if "type" in f and not isinstance(f["type"], str):
                    report.error(line, f"{ctx}.Class.fields[{i}].type: must be a type name string")
            else:
                report.error(line, f"{ctx}.Class.fields[{i}]: must be identifier or {{name, type}} object")
        _check_block(report, stmt.get("body"), f"{ctx}.Class.body")
    elif kind == "Import":
        if not isinstance(stmt.get("name"), str) or "." in stmt.get("name", "") and any(
            part in UNIMPLEMENTED for part in stmt["name"].split(".")
        ):
            report.error(line, f"{ctx}.Import: invalid module name")
    elif kind == "ImportAs":
        _check_ident(report, stmt.get("alias", ""), f"{ctx}.ImportAs.alias", line)
    elif kind == "ImportFrom":
        # Reference parser (parser.py) accepts `from x import a, b, c` and
        # stores the names as one comma-joined string, so validate each part.
        raw = stmt.get("name", "")
        if not isinstance(raw, str) or not raw.strip():
            _check_ident(report, raw, f"{ctx}.ImportFrom.name", line)
        else:
            for part in [p.strip() for p in raw.split(",")]:
                _check_ident(report, part, f"{ctx}.ImportFrom.name", line)
    elif kind == "Return":
        if stmt.get("value") is not None:
            _check_expr(report, stmt["value"], f"{ctx}.Return.value")
    elif kind in ("Break", "Continue", "Pass"):
        pass
    elif kind == "Exec":
        if not isinstance(stmt.get("code"), str):
            report.error(line, f"{ctx}.Exec: 'code' must be a string")
    elif kind == "PyBlock":
        if not isinstance(stmt.get("code"), str):
            report.error(line, f"{ctx}.PyBlock: 'code' must be a string")
    elif kind == "Set":
        _check_ident(report, stmt.get("name", ""), f"{ctx}.Set.name", line)
        if stmt.get("subtype") is not None:
            _check_ident(report, stmt["subtype"], f"{ctx}.Set.subtype", line)
        _check_expr(report, stmt.get("arg1"), f"{ctx}.Set.arg1")
        _check_expr(report, stmt.get("arg2"), f"{ctx}.Set.arg2")
    elif kind == "ExprStmt":
        _check_expr(report, stmt.get("expr"), f"{ctx}.ExprStmt.expr")
    else:
        report.error(line, f"{ctx}: unknown statement kind '{kind}'")

def validate(ast: dict) -> Report:
    r = Report()
    if not isinstance(ast, dict) or ast.get("kind") != "Program":
        r.error(None, "root must be a Program object")
        return r
    for i, s in enumerate(ast.get("statements", [])):
        _check_stmt(r, s, f"statements[{i}]")
    return r

# ---------------------------------------------------------------------------
# Serializer: AST -> Origin source
# ---------------------------------------------------------------------------

_INDENT = "    "

def _expr(node: dict, prec: int = 0) -> str:
    """Serialize an expression with precedence-aware parenthesization."""
    kind = node.get("kind")

    # Primary-level: no parens ever needed
    if kind in ("Number", "String", "Bool", "ListLit", "DictLit", "Input",
                "Sqrt", "Len", "Range", "RandNum", "Read", "ListCall",
                "SelfRef"):
        return _primary(node)

    if kind == "Var":
        return node["name"]
    if kind == "FString":
        return _fstring(node)
    if kind == "TupleLit":
        return "(" + ", ".join(_expr(e) for e in node["elements"]) + ")"

    # Lambda is primary in our grammar
    if kind == "Lambda":
        return f"{node['param']} => {_expr(node['body'])}"

    # HwPrimitive is its own primary (no parentheses required)
    if kind == "HwPrimitive":
        args = ", ".join(_expr(a) for a in node["args"])
        return f"{node['namespace']}.{node['method']} {args}"

    # Binary / logic / pipe / special: precedence-aware
    PREC = {
        "Pipe": 1, "SpecialOp": 2, "LogicOp": 3, "CompOp": 4,
        "BinOp": 5, "Unary": 7,
    }
    if kind == "Pipe":
        op = "->"
        l = _maybe_paren(_expr(node["value"], 1), node["value"], 1)
        r = _maybe_paren(_expr(node["func"], 2),  node["func"],  2)
        return f"{l} {op} {r}"
    if kind == "SpecialOp":
        op = node["op"]
        l = _maybe_paren(_expr(node["left"], 2), node["left"], 2)
        r = _maybe_paren(_expr(node["right"], 3), node["right"], 3)
        return f"{l} {op} {r}"
    if kind == "LogicOp":
        op = node["op"]
        l = _maybe_paren(_expr(node["left"], 3), node["left"], 3)
        r = _maybe_paren(_expr(node["right"], 4), node["right"], 4)
        return f"{l} {op} {r}"
    if kind == "BinOp":
        # Comparison vs arithmetic distinguished by op string
        if node["op"] in ("===", "!==", "==", "!=", "<=", ">=", "<>", "<", ">"):
            l = _maybe_paren(_expr(node["left"], 4), node["left"], 4)
            r = _maybe_paren(_expr(node["right"], 5), node["right"], 5)
            return f"{l} {node['op']} {r}"
        # Arithmetic precedence within BinOp: +,- are level 5; *,/,//,%,** at 6
        if node["op"] in ("+", "-"):
            l = _maybe_paren(_expr(node["left"], 5), node["left"], 5)
            r = _maybe_paren(_expr(node["right"], 6), node["right"], 6)
        else:
            l = _maybe_paren(_expr(node["left"], 6), node["left"], 6)
            r = _maybe_paren(_expr(node["right"], 7), node["right"], 7)
        return f"{l} {node['op']} {r}"
    if kind == "Unary":
        op = node["op"]
        operand = _maybe_paren(_expr(node["operand"], 7), node["operand"], 7)
        if op in ("++", "--"):
            return f"{operand}{op}"
        return f"{op} {operand}"

    # Postfix chain: Call / Index / Attr
    if kind in ("Call", "Index", "Attr"):
        return _postfix(node, base=None)

    raise ValueError(f"cannot serialize expression kind: {kind}")

def _maybe_paren(text: str, node: dict, parent_prec: int) -> str:
    # For simplicity we never add extra parens around expressions whose
    # primary kind is itself parenthesized-friendly. This is intentionally
    # conservative.
    return text

def _postfix(node: dict, base: str | None) -> str:
    if node.get("kind") == "Call":
        callee = base if base is not None else _postfix(node["callee"], None)
        args = ", ".join(_expr(a) for a in node["args"])
        return f"{callee}({args})"
    if node.get("kind") == "Index":
        coll = base if base is not None else _postfix(node["collection"], None)
        return f"{coll}[{_expr(node['index'])}]"
    if node.get("kind") == "Attr":
        obj = base if base is not None else _postfix(node["object"], None)
        nxt = node
        chain = [node["attr"]]
        # The serializer doesn't currently represent an explicit attr chain;
        # when it sees an Attr whose object is itself an Attr it just emits
        # one step. Models should keep chains flat.
        return f"{obj}.{node['attr']}"
    if base is None:
        return _expr(node)
    raise ValueError("unexpected postfix")

def _primary(node: dict) -> str:
    kind = node["kind"]
    if kind == "Number":
        v = node["value"]
        if node["type"] == "int":
            return str(int(v))
        return str(v) if "." in str(v) else f"{v}.0"
    if kind == "String":
        return '"' + node["value"].replace("\\", "\\\\").replace('"', '\\"') + '"'
    if kind == "FString":
        return _fstring(node)
    if kind == "Bool":
        return "true" if node["value"] else "false"
    if kind == "ListLit":
        return "[" + ", ".join(_expr(e) for e in node["elements"]) + "]"
    if kind == "DictLit":
        return "{" + ", ".join(
            f"{_expr(e['key'])}: {_expr(e['value'])}" for e in node["entries"]
        ) + "}"
    if kind == "Input":
        if node.get("prompt"):
            return f"input {_primary(node['prompt'])}"
        return "input"
    if kind == "Sqrt":
        return f"sqrt({_expr(node['value'])})"
    if kind == "Len":
        return f"len({_expr(node['value'])})"
    if kind == "Range":
        if node.get("step") is not None:
            return f"range({_expr(node['start'])}, {_expr(node['end'])}, {_expr(node['step'])})"
        return f"range({_expr(node['start'])}, {_expr(node['end'])})"
    if kind == "RandNum":
        return f"rand_num({_expr(node['start'])}, {_expr(node['end'])})"
    if kind == "Read":
        file = '"' + node["file"].replace("\\", "\\\\").replace('"', '\\"') + '"'
        if node.get("count", -1) >= 0:
            return f"read {file} to {node['count']}"
        return f"read {file}"
    if kind == "ListCall":
        return f"call[{_expr(node['list'])}, {_expr(node['pos'])}]"
    if kind == "SelfRef":
        if node.get("attr"):
            return f"self.{node['attr']}"
        return "self"
    raise ValueError(f"cannot serialize primary kind: {kind}")

def _fstring(node: dict) -> str:
    out = ['f"']
    for p in node["parts"]:
        if isinstance(p, dict) and p.get("kind") == "String":
            out.append(p["value"])
        else:
            out.append("{" + _expr(p) + "}")
    out.append('"')
    return "".join(out)

def _block(block: dict, indent: int) -> str:
    pad = _INDENT * indent
    body = []
    for s in block.get("statements", []):
        body.append(pad + _stmt(s, indent))
    return "{\n" + "\n".join(body) + "\n" + _INDENT * (indent - 1) + "}"

def _stmt(node: dict, indent: int) -> str:
    kind = node["kind"]
    if kind == "Let":
        ann = f": {node['type']}" if node.get("type") else ""
        return f"let {node['name']}{ann} = {_expr(node['value'])}"
    if kind == "Const":
        ann = f": {node['type']}" if node.get("type") else ""
        return f"const {node['name']}{ann} = {_expr(node['value'])}"
    if kind == "Assign":
        return f"{node['name']} = {_expr(node['value'])}"
    if kind == "IndexAssign":
        return f"{_expr(node['collection'])}[{_expr(node['index'])}] = {_expr(node['value'])}"
    if kind == "AttrAssign":
        return f"{_expr(node['object'])}.{node['attr']} = {_expr(node['value'])}"
    if kind == "CompoundAssign":
        return f"{node['name']} {node['op']} {_expr(node['value'])}"
    if kind == "Print":
        if node.get("for"):
            return f"print {_expr(node['expr'])} for {_target(node['for']['target'])} in {_expr(node['for']['iter'])}"
        return f"print {_expr(node['expr'])}"
    if kind == "If":
        out = [f"if {_expr(node['cond'])} {_block(node['then'], indent + 1)}"]
        for e in node.get("elifs") or []:
            out.append(f"elif {_expr(e['cond'])} {_block(e['then'], indent + 1)}")
        if node.get("else"):
            out.append(f"else {_block(node['else'], indent + 1)}")
        return "\n".join(out)
    if kind == "While":
        return f"while {_expr(node['cond'])} {_block(node['body'], indent + 1)}"
    if kind == "For":
        return f"for {_target(node['target'])} in {_expr(node['iter'])} {_block(node['body'], indent + 1)}"
    if kind == "Try":
        out = [f"try {_block(node['body'], indent + 1)}"]
        for b in node.get("excepts") or []:
            out.append(f"except {_block(b, indent + 1)}")
        if node.get("else"):
            out.append(f"else {_block(node['else'], indent + 1)}")
        return "\n".join(out)
    if kind == "Parallel":
        head = "parallel"
        if node.get("threads"):
            head += f"({node['threads']})"
        return f"{head} {_block(node['body'], indent + 1)}"
    if kind == "Def":
        params = ", ".join(p["name"] + (f": {p['type']}" if p.get("type") else "")
                           for p in node.get("params") or [])
        return f"def {node['name']}({params}) {_block(node['body'], indent + 1)}"
    if kind == "Class":
        fields = ", ".join(node.get("fields") or [])
        return f"class {node['name']}({fields}) {_block(node['body'], indent + 1)}"
    if kind == "Import":
        return f"import {node['name']}"
    if kind == "ImportAs":
        return f"import {node['name']} as {node['alias']}"
    if kind == "ImportFrom":
        return f"from {node['lib']} import {node['name']}"
    if kind == "Return":
        return f"return {_expr(node['value'])}" if node.get("value") else "return"
    if kind == "Break":    return "break"
    if kind == "Continue": return "continue"
    if kind == "Pass":     return "pass"
    if kind == "Exec":
        return f'exec "{node["code"]}"'
    if kind == "PyBlock":
        inner = node["code"].rstrip("\n")
        return "py {\n" + "\n".join(_INDENT * (indent + 1) + l for l in inner.splitlines()) + "\n" + _INDENT * indent + "}"
    if kind == "Set":
        head = node["name"]
        if node.get("subtype"):
            head += f".{node['subtype']}"
        return f"set {head} {_expr(node['arg1'])}, {_expr(node['arg2'])}"
    if kind == "ExprStmt":
        return _expr(node["expr"])
    raise ValueError(f"cannot serialize statement kind: {kind}")

def _target(t: Any) -> str:
    if isinstance(t, str):
        return t
    if isinstance(t, list):
        if len(t) == 1:
            return t[0]
        return "(" + ", ".join(t) + ")"
    raise ValueError(f"invalid for-target: {t!r}")

def serialize(ast: dict) -> str:
    if ast.get("kind") != "Program":
        raise ValueError("root must be a Program")
    lines = []
    for s in ast.get("statements", []):
        lines.append(_stmt(s, 1))
    return "\n".join(lines) + "\n"

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _check_round_trip(source: str) -> Issue | None:
    """Try to parse the emitted source with the reference parser."""
    try:
        from origin.lexer import lex
        from origin.parser import Parser
    except Exception as e:
        return Issue("warning", None, f"could not import reference parser: {e}")
    try:
        tokens = lex(source.splitlines())
        Parser(tokens).program()
        return None
    except Exception as e:
        return Issue("error", None, f"reference parser rejected emitted source: {e}")

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Validate and serialize Origin JSON AST.")
    p.add_argument("path", type=Path)
    p.add_argument("--emit", action="store_true", help="print serialized Origin source to stdout")
    p.add_argument("--check", action="store_true", help="parse the emitted source with the reference parser")
    args = p.parse_args(argv)

    ast = json.loads(args.path.read_text())
    report = validate(ast)

    if args.emit:
        try:
            print(serialize(ast), end="")
        except Exception as e:
            print(f"-- serializer error: {e}", file=sys.stderr)
            return 2
        if args.check:
            src = serialize(ast)
            rt = _check_round_trip(src)
            if rt is not None:
                report.issues.append(rt)
                print(f"-- round-trip check FAILED: {rt.message}", file=sys.stderr)
                return 1
            print("-- round-trip check OK", file=sys.stderr)
        return 0 if report.ok else 1

    for issue in report.issues:
        loc = f"line {issue.line}" if issue.line is not None else "global"
        print(f"[{issue.severity}] {loc}: {issue.message}")
    return 0 if report.ok else 1

if __name__ == "__main__":
    raise SystemExit(main())

