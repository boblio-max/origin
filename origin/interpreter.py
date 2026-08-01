"""interpreter

AST-to-Python translator and execution helpers.

This module implements a small interpreter that traverses the AST produced by
``parser.Parser`` and emits executable Python source strings.
"""

import random
import csv
import math
import sys
import os
import subprocess
from multiprocessing import Process
from pathlib import Path
from .classes import *
from .lexer import lex
from .parser import Parser
class Interpreter:
    """Generate Python source from the AST."""

    def __init__(self):
        self.variable_types = {}
        # Internal tracking (optional, could be moved to a flag)
        self.CONST_VARS = {}
        self.imports = []
        self.classes = {}
        self.original_imports = {}
        # Track whether we're generating code inside a class body
        self._class_depth = 0
        self._module_vars = set()

    def _collect_module_vars(self, node):
        """First pass: collect all variable names declared at module level."""
        for stmt in node.statements:
            if isinstance(stmt, AssignNode) and not isinstance(stmt.value, FuncNode):
                self._module_vars.add(stmt.name)

    def _get_global_vars_in_func(self, node):
        """Find variables inside a function body that shadow module-level vars."""
        if node is None:
            return set()
        result = set()
        if isinstance(node, BlockNode):
            for stmt in node.statements:
                result |= self._get_global_vars_in_func(stmt)
        elif isinstance(node, AssignNode):
            if node.name in self._module_vars:
                result.add(node.name)
        elif isinstance(node, FuncNode):
            result |= self._get_global_vars_in_func(node.body)
        elif isinstance(node, IfNode):
            result |= self._get_global_vars_in_func(node.then_body)
            for elif_n in node.elif_nodes:
                result |= self._get_global_vars_in_func(elif_n.then_body)
            if node.else_body:
                result |= self._get_global_vars_in_func(node.else_body)
        elif isinstance(node, WhileNode):
            result |= self._get_global_vars_in_func(node.body)
        elif isinstance(node, ForNode):
            result |= self._get_global_vars_in_func(node.body)
        elif isinstance(node, TryNode):
            result |= self._get_global_vars_in_func(node.try_body)
            for exc in node.except_body:
                result |= self._get_global_vars_in_func(exc)
            if node.else_body:
                result |= self._get_global_vars_in_func(node.else_body)
        elif isinstance(node, ParallelNode):
            result |= self._get_global_vars_in_func(node.body)
        return result
    def get_type(self, node):
        """Infer the type of an AST node."""
        if hasattr(node, 'type') and node.type is not None:
            return node.type
        if isinstance(node, VarNode):
            return self.variable_types.get(node.name)
        if isinstance(node, BinOpNode):
            left_type = self.get_type(node.left)
            right_type = self.get_type(node.right)
            if left_type == "float" or right_type == "float":
                return "float"
            return left_type
        return None

    def generate(self, node):
        """Recursively translate an AST node into Python source text."""
        if node is None:
            return ""

        # Inject line tracking for statements (nodes that have a line attribute)
        line_marker = ""
        if hasattr(node, 'line') and node.line is not None:
            # We use a global to track the current line so it survives inside functions
            line_marker = f"globals()['_origin_runtime_line'] = {node.line}\n"

        if isinstance(node, ProgramNode):
            self._collect_module_vars(node)
            return "\n".join(self.generate(stmt) for stmt in node.statements)

        elif isinstance(node, BlockNode):
            return "\n".join(self.generate(stmt) for stmt in node.statements)
            
        # Add the line marker to the generated code for other nodes
        res = self._generate_core(node)
        return line_marker + res

    def _generate_core(self, node):
        """The actual generation logic, separated from the line tracking wrapper."""
        if isinstance(node, ExecNode):
            # Fragile but kept for compatibility - improved to use absolute paths
            runner_path = os.path.join(os.path.dirname(__file__), "runner.py")
            temp_file = "temp_exec.py"
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(node.code)
            subprocess.run([sys.executable, runner_path, temp_file])
            return ""

        elif isinstance(node, PyNode):
            return node.code

        elif isinstance(node, AssignNode):
            if isinstance(node.value, ImuNode):
                return f"from {node.value.name} import {node.value.name}\n{node.name} = {self.generate(node.value)}"

            if node.name in self.CONST_VARS:
                raise RuntimeError(f"Cannot reassign constant '{node.name}'")

            # Infer the type of the assigned value
            val_type = self.get_type(node.value)

            # If an explicit type annotation exists and differs from inferred, attempt to cast
            if node.type and val_type and node.type != val_type:
                # Simple casting based on annotation name (int, float, str, bool)
                try:
                    # Use the cast function directly in generated code
                    casted_expr = f"{node.type}({self.generate(node.value)})"
                    assign_code = f"{node.name} = {casted_expr}"
                except Exception:
                    # If casting fails, fall back to using the inferred value without casting
                    assign_code = f"{node.name} = {self.generate(node.value)}"
                    node.type = val_type
            else:
                assign_code = f"{node.name} = {self.generate(node.value)}"

            # Record variable type information for later use
            if node.type:
                self.variable_types[node.name] = node.type
            elif val_type:
                self.variable_types[node.name] = val_type

            return assign_code

        elif isinstance(node, ConstAssignNode):
            if node.name in self.CONST_VARS:
                raise RuntimeError(f"Cannot reassign constant '{node.name}'")
            val_str = self.generate(node.value)
            val_type = self.get_type(node.value)
            if node.type and val_type and node.type != val_type:
                raise TypeError(f"Type Mismatch: {node.name} is {node.type} but got {val_type}")
            if node.type:
                self.variable_types[node.name] = node.type
            elif val_type:
                self.variable_types[node.name] = val_type
            self.CONST_VARS[node.name] = val_str
            return f"{node.name} = {val_str}"

        elif isinstance(node, CompoundAssignNode):
            return f"{node.name} {node.op} {self.generate(node.value)}"

        elif isinstance(node, BinOpNode):
            if node.op == "+":
                # Smart Concatenation: if either side is a string, treat as string concat
                left = self.generate(node.left)
                right = self.generate(node.right)
                return f"(str({left}) + str({right})) if isinstance({left}, str) or isinstance({right}, str) else ({left} + {right})"
            return f"({self.generate(node.left)} {node.op} {self.generate(node.right)})"

        elif isinstance(node, UnaryOpNode):
            if node.op in ("not", "!"):
                return f"(not {self.generate(node.node)})"
            return f"({node.op}{self.generate(node.node)})"

        elif isinstance(node, LogicOpNode):
            # Map Origin logic operators to Python
            op_map = {"and": "and", "or": "or", "&&": "and", "||": "or"}
            py_op = op_map.get(node.op, node.op)
            return f"({self.generate(node.left)} {py_op} {self.generate(node.right)})"

        elif isinstance(node, IfNode):
            code = f"if {self.generate(node.condition)}:\n"
            code += self.indent_block(self.generate(node.then_body))
            for elif_node in node.elif_nodes:
                code += f"\nelif {self.generate(elif_node.condition)}:\n"
                code += self.indent_block(self.generate(elif_node.then_body))
            if node.else_body:
                code += "\nelse:\n"
                code += self.indent_block(self.generate(node.else_body))
            return code

        elif isinstance(node, WhileNode):
            code = f"while {self.generate(node.condition)}:\n"
            code += self.indent_block(self.generate(node.body))
            return code

        elif isinstance(node, ForNode):
            code = f"for {self.generate(node.var)} in {self.generate(node.iterable)}:\n"
            code += self.indent_block(self.generate(node.body))
            return code

        elif isinstance(node, TryNode):
            code = "try:\n"
            code += self.indent_block(self.generate(node.try_body))
            for exc in node.except_body:
                code += "\nexcept Exception:\n"
                code += self.indent_block(self.generate(exc))
            if node.else_body:
                code += "\nelse:\n"
                code += self.indent_block(self.generate(node.else_body))
            return code

        elif isinstance(node, FuncNode):
            params = []
            for p in node.params:
                ptype = (node.param_types or {}).get(p)
                if ptype in ("int", "float", "str", "bool"):
                    params.append(f"{p}: {ptype}")
                else:
                    params.append(p)
            params = ", ".join(params) if params else ""
            # If inside a class, ensure 'self' is the first parameter (unless already declared)
            if getattr(self, "_class_depth", 0) > 0 and node.params and node.params[0] != "self":
                params = "self" if not params else "self, " + params
            code = f"def {node.name}({params}):\n"
            body_code = self.generate(node.body) or "pass"
            global_vars = self._get_global_vars_in_func(node.body)
            if global_vars:
                global_line = "global " + ", ".join(sorted(global_vars)) + "\n"
                body_code = global_line + body_code
            code += self.indent_block(body_code)
            return code

        elif isinstance(node, ClassNode):
            # Make fields optional by defaulting to None, with type annotations when given
            params = []
            for f in node.fields:
                ftype = (node.field_types or {}).get(f)
                if ftype in ("int", "float", "str", "bool"):
                    params.append(f"{f}: {ftype} = None")
                else:
                    params.append(f"{f}=None")
            params = ", ".join(params)
            code = f"class {node.name}:\n"
            # Body of __init__ must be indented further (8 spaces total)
            init_body = "\n".join(f"        self.{f} = {f}" for f in node.fields) or "        pass"
            init_sig = ("self, " + params) if params else "self"
            code += f"    def __init__({init_sig}):\n{init_body}\n"
            # Generate class body with class-depth tracking so methods get 'self'
            self._class_depth += 1
            body_code = self.generate(node.body)
            self._class_depth -= 1
            code += self.indent_block(body_code)
            return code

        
        elif isinstance(node, CallNode):
            args = ", ".join(self.generate(arg) for arg in node.args)
            return f"{self.generate(node.callee)}({args})"

        elif isinstance(node, AttributeNode):
            return f"{self.generate(node.obj)}.{node.attr}"

        elif isinstance(node, AttributeAssignNode):
            return f"{self.generate(node.obj)}.{node.attr} = {self.generate(node.value)}"

        elif isinstance(node, PrintNode):
            # Support multiple print arguments (TupleNode or ListNode) without printing a tuple
            expr = node.expr
            if isinstance(expr, TupleNode) or isinstance(expr, ListNode):
                args = ", ".join(self.generate(e) for e in expr.elements)
                return f"print({args})"
            return f"print({self.generate(expr)})"

        elif isinstance(node, NumberNode):
            return str(node.value)

        elif isinstance(node, StringNode):
            return repr(node.value)

        elif isinstance(node, FormattedStringNode):
            # Emit concatenation of parts, converting expressions to str()
            parts = []
            for p in node.parts:
                if isinstance(p, StringNode):
                    parts.append(repr(p.value))
                else:
                    parts.append(f"str({self.generate(p)})")
            if not parts:
                return "''"
            return "(" + " + ".join(parts) + ")"

        elif isinstance(node, BoolNode):
            return str(node.value)

        elif isinstance(node, NoneNode):
            return "None"

        elif isinstance(node, VarNode):
            return node.name

        elif isinstance(node, ListNode):
            return f"[{', '.join(self.generate(e) for e in node.elements)}]"

        elif isinstance(node, TupleNode):
            return f"({', '.join(self.generate(e) for e in node.elements)})"

        elif isinstance(node, DictNode):
            items = ", ".join(f"{self.generate(k)}: {self.generate(v)}" for k, v in node.elements.items())
            return f"{{{items}}}"

        elif isinstance(node, IndexNode):
            return f"{self.generate(node.collection)}[{self.generate(node.index)}]"

        elif isinstance(node, IndexAssignNode):
            return f"{self.generate(node.collection)}[{self.generate(node.index)}] = {self.generate(node.value)}"

        elif isinstance(node, ImuNode):
            return f"{node.name}({node.address})"
        
        elif isinstance(node, ImuFromNode):
            return f"{node.name}.get_{node.value}()"
        
        elif isinstance(node, ParallelNode):
            code = ""
            code += "import threading\n"
            code += "_threads = []\n"
            if node.threads > 0:
                code += "def _parallel_block():\n"
                code += self.indent_block(self.generate(node.body))
                code += f"\nfor _ in range({node.threads}):\n"
                code += "    t = threading.Thread(target=_parallel_block)\n"
                code += "    t.start(); _threads.append(t)\n"
            else:
                # Parallelize each statement in the block
                for i, stmt in enumerate(node.body.statements):
                    code += f"def _parallel_stmt_{i}():\n"
                    code += self.indent_block(self.generate(stmt))
                    code += f"\n_t{i} = threading.Thread(target=_parallel_stmt_{i})\n"
                    code += f"_t{i}.start(); _threads.append(_t{i})\n"
            code += "for t in _threads: t.join()\n"
            return code

        elif isinstance(node, SetNode):
            if node.name == "servo" and node.type_ == "angle":
                return (
                    f"try:\n"
                    f"    from adafruit_servokit import ServoKit\n"
                    f"    if '_kit' not in globals():\n"
                    f"        import board\n"
                    f"        _kit = ServoKit(channels=16)\n"
                    f"    _kit.servo[{self.generate(node.num)}].angle = {self.generate(node.params)}\n"
                    f"except (ImportError, AttributeError, Exception):\n"
                    f"    print(f'[SIM] Servo {self.generate(node.num)} angle set to {self.generate(node.params)}')\n"
                )
            elif node.name == "pin":
                 return f"_execute_set_pin({self.generate(node.num)}, {self.generate(node.params)})"
            return f"{node.name}.{node.type_} = {self.generate(node.params)}"

        elif isinstance(node, ImportNode):
            if node.name in self.original_imports:
                path = self.original_imports[node.name]
                with open(path, "r", encoding="utf-8") as f:
                    code = f.read()
                _lex = lex(code.splitlines())
                _parse = Parser(_lex).program()
                return self.generate(_parse)

            lib_dir = Path(__file__).resolve().parent / "lib"
            or_path = lib_dir / f"{node.name}.or"
            py_path = lib_dir / f"{node.name}.py"
            if or_path.exists():
                with open(or_path, encoding="utf-8") as f:
                    code = [line.rstrip("\n") for line in f]
                _lex = lex(code)
                _parse = Parser(_lex).program()
                return self.generate(_parse)
            elif py_path.exists():
                return f"exec(open({str(py_path)!r}).read())"
            else:
                return f"import {node.name}"

        elif isinstance(node, ImportAsNode):
            return f"import {node.name} as {node.alias}"

        elif isinstance(node, ImportFromNode):
            return f"from {node.lib} import {node.name}"

        elif isinstance(node, ReturnNode):
            return f"return {self.generate(node.value)}"

        elif isinstance(node, BreakNode):
            return "break"

        elif isinstance(node, ContinueNode):
            return "continue"

        elif isinstance(node, GraphNode):
            if not getattr(self, '_graph_loaded', False):
                self._graph_loaded = True
                lib_path = Path(__file__).resolve().parent / "lib" / "graph.or"
                with open(lib_path, encoding="utf-8") as f:
                    lib_code = [line.rstrip("\n") for line in f]
                lib_tokens = lex(lib_code)
                lib_ast = Parser(lib_tokens).program()
                prefix = self.generate(lib_ast) + "\n"
            else:
                prefix = ""

            name = node.name or ""
            params2 = node.params2 or {}
            labelx = node.labelx or ""
            labely = node.labely or ""
            colorx = node.colorx
            colory = node.colory
            markermap = node.marker

            call = (
                f"graph_show({repr(name)}, {repr(params2)}, {repr(labelx)}, "
                f"{repr(labely)}, {repr(colorx)}, {repr(colory)}, {repr(markermap)})"
            )
            return prefix + call

        elif isinstance(node, PassNode):
            return "pass"

        elif isinstance(node, PipeNode):
            value = self.generate(node.value)
            func  = self.generate(node.func)
            return f"{func}({value})"

        elif isinstance(node, LambdaNode):
            return f"(lambda {node.var}: {self.generate(node.func)})"

        elif isinstance(node, SpecialOpNode):
            if node.op == "??":
                if node.left is not None:
                    return node.left
                else:
                    return node.right
                
        elif isinstance(node, HardwarePrimitiveNode):
            args = ", ".join(self.generate(arg) for arg in node.args)
            return f"_execute_{node.namespace}_{node.method}({args})"

        elif isinstance(node, RangeNode):
            if node.step is not None:
                return f"range({self.generate(node.start)}, {self.generate(node.end)}, {self.generate(node.step)})"
            return f"range({self.generate(node.start)}, {self.generate(node.end)})"

        elif isinstance(node, ReadNode):
            if node.count == -1:
                return f"open({repr(node.file_name)}).read()"
            else:
                return f"open({repr(node.file_name)}).read({node.count})"
        
        elif isinstance(node, WriteNode):
            fname = node.file[1:-1] if node.file[:1] in ('"', "'") else node.file
            content = self.generate(node.contents)
            return f"open({repr(fname)}, 'w').write({content})"
        
        elif isinstance(node, AppendNode):
            fname = node.file[1:-1] if node.file[:1] in ('"', "'") else node.file
            content = self.generate(node.contents)
            return f"open({repr(fname)}, 'a').write({content})"
        
        elif isinstance(node, LenNode):
            return f"len({self.generate(node.value)})"

        elif isinstance(node, SqrtNode):
            return f"math.sqrt({self.generate(node.value)})"

        elif isinstance(node, RandNumNode):
            return f"random.randint({self.generate(node.start)}, {self.generate(node.end)})"

        elif isinstance(node, CastNode):
            return f"{node.cast_type}({self.generate(node.value)})"

        elif isinstance(node, InputNode):
            prompt = self.generate(node.prompt) if node.prompt else ""
            return f"input({prompt})"

        else:
            raise RuntimeError(f"Unknown node type: {type(node)}")

    def indent_block(self, code, indent=4):
        if not code: return " " * indent + "pass"
        spaces = " " * indent
        return "\n".join(spaces + line if line.strip() else line for line in code.split("\n"))

# --- Hardware Runtime Helpers ---
def _execute_set_pin(pin, state):
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.HIGH if state else GPIO.LOW)
    except ImportError:
        print(f"[SIM] Pin {pin} set to {state}")

def _execute_i2c_read(addr, reg, size=1):
    try:
        import smbus2
        bus = smbus2.SMBus(1)
        return bus.read_byte_data(addr, reg) if size == 1 else bus.read_i2c_block_data(addr, reg, size)
    except ImportError:
        return 0

def _execute_i2c_write(addr, reg, data):
    try:
        import smbus2
        bus = smbus2.SMBus(1)
        if isinstance(data, int): bus.write_byte_data(addr, reg, data)
        else: bus.write_i2c_block_data(addr, reg, data)
    except ImportError:
        pass
