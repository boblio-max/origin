"""System/IO/hardware/import codegen branches + dispatch terminus."""
from pathlib import Path
from multiprocessing import Process
from ..lexer import lex
from ..parser import Parser
from ..classes import *


class SysMixin:
    def _generate_core(self, node):
        """The actual generation logic, separated from the line tracking wrapper."""
        if isinstance(node, ParallelNode):
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
                lib_path = str(lib_dir).replace("\\", "\\\\")
                preamble = f"import sys as _sys\nif r'{lib_path}' not in _sys.path:\n    _sys.path.insert(0, r'{lib_path}')\n"
                with open(or_path, encoding="utf-8") as f:
                    code = [line.rstrip("\n") for line in f]
                _lex = lex(code)
                _parse = Parser(_lex).program()
                return preamble + self.generate(_parse)
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
                left = self.generate(node.left)
                right = self.generate(node.right)
                return f"(lambda _v: _v if _v is not None else ({right}))({left})"
                
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

        elif isinstance(node, MathNode):
            py_func = {"abs": "abs", "floor": "math.floor", "ceil": "math.ceil"}.get(node.func, node.func)
            return f"{py_func}({self.generate(node.value)})"

        elif isinstance(node, RandNumNode):
            return f"random.randint({self.generate(node.start)}, {self.generate(node.end)})"

        elif isinstance(node, CastNode):
            return f"{node.cast_type}({self.generate(node.value)})"

        elif isinstance(node, InputNode):
            prompt = self.generate(node.prompt) if node.prompt else ""
            return f"input({prompt})"
        
        elif isinstance(node, CommandNode):
            # Generate Python code that runs at runtime, not at compile time.
            # Handle both str and Token storage for command (with or without quotes)
            cmd = node.command
            if hasattr(cmd, 'value'):
                cmd = cmd.value
            if isinstance(cmd, str) and len(cmd) >= 2 and cmd[0] in ('"', "'") and cmd[-1] == cmd[0]:
                cmd = cmd[1:-1]
            # flags may be stored as .flags or legacy .params
            flags = getattr(node, 'flags', getattr(node, 'params', None))
            # If flags is a dict, expand as kwargs; BlockNode/list flags are ignored for now
            if isinstance(flags, dict) and flags:
                kwargs = ", ".join(f"{k}={repr(v)}" for k, v in flags.items())
                return f"__import__('subprocess').run({repr(cmd)}.split(), {kwargs})"
            return f"__import__('subprocess').run({repr(cmd)}.split())"
        else:
            raise RuntimeError(f"Unknown node type: {type(node)}")
