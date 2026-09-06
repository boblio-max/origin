"""interpreter_no_debug

AST-to-Python translator (no runtime line tracking).
"""

import random
import csv
import math
import sys
import os
import subprocess
from multiprocessing import Process
from pathlib import Path
from classes import *
from lexer import lex
from parser import Parser
class Interpreter:
    """Generate Python source from the AST."""

    def __init__(self):
        self.variable_types = {}
        self.CONST_VARS = {}
        self.imports = []
        self.classes = {}
        self.original_imports = {}
        self._class_depth = 0
        self._module_vars = set()
        self._func_depth = 0

    def _collect_module_vars(self, node):
        """First pass: collect all variable names declared at module level."""
        for stmt in node.statements:
            if isinstance(stmt, MultAssignNode):
                names = stmt.names if isinstance(stmt.names, list) else [stmt.names]
                for n in names:
                    self._module_vars.add(n)
            elif isinstance(stmt, (AssignNode, ConstAssignNode)) and not isinstance(stmt.value, FuncNode):
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
        elif isinstance(node, MultAssignNode):
            names = node.names if isinstance(node.names, list) else [node.names]
            for n in names:
                if n in self._module_vars:
                    result.add(n)
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
        if node is None:
            return ""

        if isinstance(node, ProgramNode):
            self._collect_module_vars(node)
            return "\n".join(self.generate(stmt) for stmt in node.statements)

        elif isinstance(node, BlockNode):
            return "\n".join(self.generate(stmt) for stmt in node.statements)

        return self._generate_core(node)

    def _generate_core(self, node):
        if isinstance(node, ExecNode):
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

            val_type = self.get_type(node.value)

            if node.type and val_type and node.type != val_type:
                try:
                    casted_expr = f"{node.type}({self.generate(node.value)})"
                    assign_code = f"{node.name} = {casted_expr}"
                except Exception:
                    assign_code = f"{node.name} = {self.generate(node.value)}"
                    node.type = val_type
            else:
                assign_code = f"{node.name} = {self.generate(node.value)}"

            if node.type:
                self.variable_types[node.name] = node.type
            elif val_type:
                self.variable_types[node.name] = val_type

            return assign_code

        elif isinstance(node, MultAssignNode):
            names = node.names if isinstance(node.names, list) else [node.names]
            values = node.value if isinstance(node.value, list) else [node.value]
            annotations = node.type if isinstance(node.type, list) else [node.type]
            if len(names) != len(values):
                raise RuntimeError("Type Mismatch: number of names and values in multi-assignment must match")
            for name in names:
                if name in self.CONST_VARS:
                    raise RuntimeError(f"Cannot reassign constant '{name}'")
            value_codes = []
            for i, name in enumerate(names):
                value = values[i]
                val_type = self.get_type(value)
                annotation = annotations[i] if i < len(annotations) else None
                code = self.generate(value)
                if annotation and val_type and annotation != val_type:
                    code = f"{annotation}({code})"
                if annotation:
                    self.variable_types[name] = annotation
                elif val_type:
                    self.variable_types[name] = val_type
                value_codes.append(code)
            return ", ".join(names) + " = " + ", ".join(value_codes)

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
                left = self.generate(node.left)
                right = self.generate(node.right)
                return f"(str({left}) + str({right})) if isinstance({left}, str) or isinstance({right}, str) else ({left} + {right})"
            return f"({self.generate(node.left)} {node.op} {self.generate(node.right)})"

        elif isinstance(node, UnaryOpNode):
            if node.op in ("not", "!"):
                return f"(not {self.generate(node.node)})"
            return f"({node.op}{self.generate(node.node)})"

        elif isinstance(node, LogicOpNode):
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
            if getattr(self, "_class_depth", 0) > 0 and (not node.params or node.params[0] != "self"):
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
            params = []
            for f in node.fields:
                ftype = (node.field_types or {}).get(f)
                if ftype in ("int", "float", "str", "bool"):
                    params.append(f"{f}: {ftype} = None")
                else:
                    params.append(f"{f}=None")
            params = ", ".join(params)
            code = f"class {node.name}:\n"
            init_body = "\n".join(f"        self.{f} = {f}" for f in node.fields) or "        pass"
            init_sig = ("self, " + params) if params else "self"
            code += f"    def __init__({init_sig}):\n{init_body}\n"
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
                lib_path_str = str(lib_dir).replace("\\", "\\\\")
                with open(or_path, encoding="utf-8") as f:
                    code = [line.rstrip("\n") for line in f]
                _lex = lex(code)
                _parse = Parser(_lex).program()
                return f"import sys; sys.path.insert(0, r'{lib_dir}')\n" + self.generate(_parse)
            elif py_path.exists():
                return f"exec(open({str(py_path)!r}).read())"
            else:
                return f"import {node.name}"

        elif isinstance(node, ImportAsNode):
            lib_dir = Path(__file__).resolve().parent / "lib"
            or_path = lib_dir / f"{node.name}.or"
            if or_path.exists():
                with open(or_path, encoding="utf-8") as f:
                    code = [line.rstrip("\n") for line in f]
                _lex = lex(code)
                _parse = Parser(_lex).program()
                inlined = self.generate(_parse)
                return f"{inlined}\n{node.alias} = {node.name}" if node.name in self._module_vars else inlined
            return f"import {node.name} as {node.alias}"

        elif isinstance(node, ImportFromNode):
            return f"from {node.lib} import {node.name}"

        elif isinstance(node, ReturnNode):
            return f"return {self.generate(node.value)}"

        elif isinstance(node, BreakNode):
            return "break"

        elif isinstance(node, ContinueNode):
            return "continue"

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
            content = self.generate(node.content)
            return f"open({repr(node.file_name)}, 'a').write({content})"

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


