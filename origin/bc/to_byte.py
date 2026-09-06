import random
import csv
import math
import sys
from pathlib import Path
from .classes import *
from lexer import lex
from parser import Parser
from bc.byteKey import OpCode

class Compiler:
    def __init__(self):
        self.bytecode = []
        self.constants = []
        self.loop_starts = [] # Stack of JMP targets for continue
        self.loop_ends = []   # Stack of placeholder indices for break
        self._for_tmp_counter = 0
        self.variable_types = {}
        self.const_names = set()
        self.functions = {}
        self.unresolved_calls = []
        self.builtins = {
            "open": open,
            "read": lambda path: open(path).read(),
            "write": lambda path, content: open(path, 'w').write(content),
            "append": lambda path, content: open(path, 'a').write(content),
            "range": range,
        }

    def emit_jmp(self, opcode, target=0):
        self.emit(opcode)
        idx = len(self.bytecode)
        self.bytecode.extend([(target >> 8) & 0xFF, target & 0xFF])
        return idx

    def patch_jmp(self, idx, target):
        self.bytecode[idx] = (target >> 8) & 0xFF
        self.bytecode[idx+1] = target & 0xFF

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
        
        if isinstance(node, UnaryOpNode):
            return self.get_type(node.node)
            
        return getattr(node, 'type', None)

    def emit(self, opcode, *operands):
        self.bytecode.append(opcode & 0xFF)
        for op in operands:
            if op is None:
                continue
            # mask to byte range; -1 (sentinel for read) becomes 0xFF
            self.bytecode.append(op & 0xFF)

    def add_constant(self, value):
        for i, c in enumerate(self.constants):
            if type(c) is type(value) and c == value:
                return i
        self.constants.append(value)
        return len(self.constants) - 1

    def compile(self, node):
        if isinstance(node, ProgramNode) or isinstance(node, BlockNode):
            for stmt in node.statements:
                self.compile(stmt)
                # If the statement is a standalone call (e.g. `list.append(x)`),
                # its return value (often None) is left on the stack. Pop it so
                # the stack stays clean for subsequent FOR_ITER handling.
                if isinstance(stmt, CallNode):
                    self.emit(OpCode.POP)

        elif isinstance(node, NumberNode):
            idx = self.add_constant(node.value)
            self.emit(OpCode.PUSH_CONST, idx)

        elif isinstance(node, StringNode):
            idx = self.add_constant(node.value)
            self.emit(OpCode.PUSH_CONST, idx)

        elif isinstance(node, BoolNode):
            idx = self.add_constant(node.value)
            self.emit(OpCode.PUSH_CONST, idx)

        elif isinstance(node, NoneNode):
            idx = self.add_constant(None)
            self.emit(OpCode.PUSH_CONST, idx)

        elif isinstance(node, VarNode):
            idx = self.add_constant(node.name)
            self.emit(OpCode.LOAD_VAR, idx)

        elif isinstance(node, AssignNode) or isinstance(node, ConstAssignNode):
            value_type = self.get_type(node.value)
            is_const = isinstance(node, ConstAssignNode)

            if is_const:
                if node.name in self.const_names:
                    raise TypeError(f"Type Mismatch: constant '{node.name}' cannot be reassigned")
                self.const_names.add(node.name)
            elif node.name in self.const_names:
                raise TypeError(f"Type Mismatch: constant '{node.name}' cannot be reassigned")

            if node.type is not None:
                # Declaration with explicit type (let x: int = ...)
                if value_type is not None and value_type != node.type and node.type != "any" and value_type != "any":
                     raise TypeError(f"Type Mismatch: variable '{node.name}' declared as {node.type} but assigned {value_type}")
                self.variable_types[node.name] = node.type
            elif node.name not in self.variable_types:
                # Declaration without type annotation: auto-infer from the assigned value
                inferred = value_type if value_type is not None else "any"
                self.variable_types[node.name] = inferred
            else:
                # Re-assignment without type (x = ...)
                expected_type = self.variable_types[node.name]
                if value_type is not None and expected_type not in (None, "any") and value_type != expected_type:
                    raise TypeError(f"Type Mismatch: variable '{node.name}' is {expected_type} but assigned {value_type}")

            self.compile(node.value)
            idx = self.add_constant(node.name)
            self.emit(OpCode.STORE_VAR, idx)

        elif isinstance(node, MultAssignNode):
            names = node.names if isinstance(node.names, list) else [node.names]
            values = node.value if isinstance(node.value, list) else [node.value]
            annotations = node.type if isinstance(node.type, list) else [node.type]
            if len(names) != len(values):
                raise RuntimeError("Type Mismatch: number of names and values in multi-assignment must match")
            value_types = [self.get_type(value) for value in values]
            for value in values:
                self.compile(value)
            for i in reversed(range(len(names))):
                name = names[i]
                if name in self.const_names:
                    raise TypeError(f"Type Mismatch: constant '{name}' cannot be reassigned")
                value_type = value_types[i]
                annotation = annotations[i] if i < len(annotations) else None
                if annotation is not None:
                    if value_type is not None and value_type != annotation and annotation != "any" and value_type != "any":
                        raise TypeError(f"Type Mismatch: variable '{name}' declared as {annotation} but assigned {value_type}")
                    self.variable_types[name] = annotation
                elif name not in self.variable_types:
                    self.variable_types[name] = value_type if value_type is not None else "any"
                else:
                    expected_type = self.variable_types[name]
                    if value_type is not None and expected_type not in (None, "any") and value_type != expected_type:
                        raise TypeError(f"Type Mismatch: variable '{name}' is {expected_type} but assigned {value_type}")
                idx = self.add_constant(name)
                self.emit(OpCode.STORE_VAR, idx)

        elif isinstance(node, BinOpNode):
            self.compile(node.left)
            self.compile(node.right)
            ops = {
                '+': OpCode.ADD, '-': OpCode.SUB, '*': OpCode.MUL, '/': OpCode.DIV,
                '//': OpCode.FLOOR_DIV,
                '==': OpCode.EQ, '!=': OpCode.NEQ, '<': OpCode.LT, '>': OpCode.GT,
                '<=': OpCode.LTE, '>=': OpCode.GTE, '%': OpCode.MOD, '**': OpCode.POW,
                '&': OpCode.BIT_AND, '|': OpCode.BIT_OR, '^': OpCode.BIT_XOR,
                '<<': OpCode.LSHIFT, '>>': OpCode.RSHIFT,
            }
            if node.op in ops:
                self.emit(ops[node.op])
            else:
                raise RuntimeError(f"Unsupported binop: {node.op}")

        elif isinstance(node, UnaryOpNode):
            self.compile(node.node)
            if node.op == '-':
                self.emit(OpCode.NEGATE)
            elif node.op == '~':
                self.emit(OpCode.BIT_NOT)
            elif node.op == '+':
                pass  # unary plus no-op
            elif node.op in ('not', '!'):
                self.emit(OpCode.NOT)

        elif isinstance(node, LogicOpNode):
            self.compile(node.left)
            self.compile(node.right)
            if node.op in ('and', '&&'): self.emit(OpCode.AND)
            elif node.op in ('or', '||'): self.emit(OpCode.OR)

        elif isinstance(node, PrintNode):
            self.compile(node.expr)
            self.emit(OpCode.PRINT)

        elif isinstance(node, InputNode):
            if node.prompt:
                self.compile(node.prompt)
            else:
                idx = self.add_constant("")
                self.emit(OpCode.PUSH_CONST, idx)
            self.emit(OpCode.INPUT)

        elif isinstance(node, IfNode):
            end_jmp_indices = []

            self.compile(node.condition)
            false_jmp_idx = self.emit_jmp(OpCode.JMP_IF_FALSE)

            self.compile(node.then_body)
            end_jmp_indices.append(self.emit_jmp(OpCode.JMP))

            # Patch false jump (to elif or else or end)
            self.patch_jmp(false_jmp_idx, len(self.bytecode))

            for elif_node in node.elif_nodes:
                 self.compile(elif_node.condition)
                 next_elif_idx = self.emit_jmp(OpCode.JMP_IF_FALSE)
                 
                 self.compile(elif_node.then_body)
                 end_jmp_indices.append(self.emit_jmp(OpCode.JMP))
                 
                 self.patch_jmp(next_elif_idx, len(self.bytecode))

            if node.else_body:
                self.compile(node.else_body)
            
            for idx in end_jmp_indices:
                self.patch_jmp(idx, len(self.bytecode))

        elif isinstance(node, ListCallNode):
            self.compile(node.list_node)
            self.compile(node.pos)
            self.emit(OpCode.INDEX_LOAD)

        elif isinstance(node, PassNode):
            pass

        elif isinstance(node, WhileNode):
            start_pc = len(self.bytecode)
            self.loop_starts.append(start_pc)
            breaks = []
            self.loop_ends.append(breaks)

            self.compile(node.condition)
            exit_jmp_idx = self.emit_jmp(OpCode.JMP_IF_FALSE)

            self.compile(node.body)
            self.emit_jmp(OpCode.JMP, start_pc)

            # Patch exit jump
            self.patch_jmp(exit_jmp_idx, len(self.bytecode))
            # Patch breaks
            for b_idx in breaks:
                self.patch_jmp(b_idx, len(self.bytecode))
            
            self.loop_starts.pop()
            self.loop_ends.pop()

        elif isinstance(node, CompoundAssignNode):
            var_idx = self.add_constant(node.name)
            # 1. Get the current value
            self.emit(OpCode.LOAD_VAR, var_idx)
            # 2. Get the new value
            self.compile(node.value)
            
            # 3. Choose the operation
            op_map = {
                '+=': OpCode.ADD,
                '-=': OpCode.SUB,
                '*=': OpCode.MUL,
                '/=': OpCode.DIV,
                '//=': OpCode.FLOOR_DIV,
                '%=': OpCode.MOD,
                '**=': OpCode.POW,
                '&=': OpCode.BIT_AND,
                '|=': OpCode.BIT_OR,
                '^=': OpCode.BIT_XOR,
                '<<=': OpCode.LSHIFT,
                '>>=': OpCode.RSHIFT
            }
            
            if node.op in op_map:
                self.emit(op_map[node.op])
                # 4. Save the result back to the variable
                self.emit(OpCode.STORE_VAR, var_idx)
            else:
                raise RuntimeError(f"Unsupported compound assign: {node.op}")
            
        elif isinstance(node, ForNode):
            # 1. Compile the thing we are looping over
            self.compile(node.iterable)
            # 2. Create the iterator (bookmark)
            self.emit(OpCode.GET_ITER)
            
            # 3. Start of the loop
            start_pc = len(self.bytecode)
            self.loop_starts.append(start_pc)
            
            # 4. Get next item or jump to end if done
            exit_jmp_idx = self.emit_jmp(OpCode.FOR_ITER)
            
            # 5. Save the item to the loop variable(s)
            if isinstance(node.var, VarNode):
                var_idx = self.add_constant(node.var.name)
                self.emit(OpCode.STORE_VAR, var_idx)
                if getattr(node.var, "var_type", None):
                    self.variable_types[node.var.name] = node.var.var_type
            elif isinstance(node.var, TupleNode) or isinstance(node.var, ListNode):
                # Store into a temporary, then extract elements into variables
                tmp_name = f"_for_tmp_{self._for_tmp_counter}"
                self._for_tmp_counter += 1
                tmp_idx = self.add_constant(tmp_name)
                self.emit(OpCode.STORE_VAR, tmp_idx)
                for i, el in enumerate(node.var.elements):
                    self.emit(OpCode.LOAD_VAR, tmp_idx)
                    const_idx = self.add_constant(i)
                    self.emit(OpCode.PUSH_CONST, const_idx)
                    self.emit(OpCode.INDEX_LOAD)
                    dest_idx = self.add_constant(el.name)
                    self.emit(OpCode.STORE_VAR, dest_idx)
            else:
                raise RuntimeError("Unsupported for-loop target type")
            
            # 6. Compile the code inside the loop
            breaks = []
            self.loop_ends.append(breaks)
            self.compile(node.body)
            
            # 7. Jump back to step 4 to get the next item
            self.emit_jmp(OpCode.JMP, start_pc)
            
            # 8. Patch the exit jump for when we are finished
            self.patch_jmp(exit_jmp_idx, len(self.bytecode))
            
            # 9. Clean up any breaks
            for b_idx in breaks:
                self.patch_jmp(b_idx, len(self.bytecode))
            
            self.loop_starts.pop()
            self.loop_ends.pop()
        elif isinstance(node, BreakNode):
            if not self.loop_ends: raise RuntimeError("Break outside loop")
            self.loop_ends[-1].append(self.emit_jmp(OpCode.JMP))

        elif isinstance(node, ContinueNode):
            if not self.loop_starts: raise RuntimeError("Continue outside loop")
            self.emit_jmp(OpCode.JMP, self.loop_starts[-1])

        elif isinstance(node, ListNode):
            for el in node.elements:
                self.compile(el)
            self.emit(OpCode.LIST_INIT, len(node.elements))

        elif isinstance(node, DictNode):
            for k, v in node.elements.items():
                self.compile(k)
                self.compile(v)
            self.emit(OpCode.DICT_INIT, len(node.elements))

        elif isinstance(node, IndexNode):
            self.compile(node.collection)
            self.compile(node.index)
            self.emit(OpCode.INDEX_LOAD)

        elif isinstance(node, IndexAssignNode):
            self.compile(node.collection)
            self.compile(node.index)
            self.compile(node.value)
            self.emit(OpCode.INDEX_STORE)

        elif isinstance(node, RangeNode):
            self.compile(node.start)
            self.compile(node.end)
            if node.step is not None:
                self.compile(node.step)
            # We don't have a RANGE opcode, so we'll just use a CALL to Python's range
            idx = self.add_constant(range)
            self.emit(OpCode.PUSH_CONST, idx)
            self.emit(OpCode.CALL, 3 if node.step is not None else 2)

        elif isinstance(node, LenNode):
            self.compile(node.value)
            self.emit(OpCode.LEN)

        elif isinstance(node, SqrtNode):
            self.compile(node.value)
            self.emit(OpCode.SQRT)

        elif isinstance(node, MathNode):
            self.compile(node.value)
            math_ops = {"abs": OpCode.ABS, "floor": OpCode.FLOOR, "ceil": OpCode.CEIL}
            if node.func not in math_ops:
                raise RuntimeError(f"Unsupported math op: {node.func}")
            self.emit(math_ops[node.func])

        elif isinstance(node, RandNumNode):
            self.compile(node.start)
            self.compile(node.end)
            self.emit(OpCode.RAND_NUM)

        elif isinstance(node, PassNode):
            pass

        elif isinstance(node, FuncNode):
            skip_jmp_idx = self.emit_jmp(OpCode.JMP)

            self.functions[node.name] = len(self.bytecode)
            for param in reversed(node.params):
                idx = self.add_constant(param)
                self.emit(OpCode.STORE_VAR, idx)
            for pname, ptype in (node.param_types or {}).items():
                self.variable_types[pname] = ptype
            self.compile(node.body)
            idx = self.add_constant(None)
            self.emit(OpCode.PUSH_CONST, idx)
            self.emit(OpCode.RETURN)

            self.patch_jmp(skip_jmp_idx, len(self.bytecode))
        elif isinstance(node, CallNode):
            for arg in node.args:
                self.compile(arg)
            
            if isinstance(node.callee, VarNode):
                func_name = node.callee.name
                if func_name in self.functions:
                    idx = self.add_constant(self.functions[func_name])
                    self.emit(OpCode.PUSH_CONST, idx)
                elif func_name in self.builtins:
                    idx = self.add_constant(self.builtins[func_name])
                    self.emit(OpCode.PUSH_CONST, idx)
                else:
                    opcode_idx = len(self.bytecode)
                    idx = self.add_constant(func_name)
                    self.emit(OpCode.PUSH_CONST, idx)
                    self.unresolved_calls.append((func_name, idx, opcode_idx))
            else:
                self.compile(node.callee)
            
            self.emit(OpCode.CALL, len(node.args))

        elif isinstance(node, CastNode):
            self.compile(node.value)
            if node.cast_type == "str":
                self.emit(OpCode.CAST_STR)
            elif node.cast_type == "int":
                self.emit(OpCode.CAST_INT)
            elif node.cast_type == "float":
                self.emit(OpCode.CAST_FLOAT)
            elif node.cast_type == "bool":
                # No CAST_BOOL opcode; `not not value` yields a Python bool.
                self.emit(OpCode.NOT)
                self.emit(OpCode.NOT)
            else:
                # Non-builtin/class type names in annotations are advisory in the VM.
                pass

        elif isinstance(node, ReturnNode):
            self.compile(node.value)
            self.emit(OpCode.RETURN)

        elif isinstance(node, ClassNode):
            methods = {}
            for stmt in node.body.statements:
                if isinstance(stmt, FuncNode):
                    skip_jmp_idx = self.emit_jmp(OpCode.JMP)
                    method_pc = len(self.bytecode)
                    method_params = stmt.params
                    if not method_params or method_params[0] != "self":
                        method_params = ["self"] + method_params
                    for param in reversed(method_params):
                        idx = self.add_constant(param)
                        self.emit(OpCode.STORE_VAR, idx)
                    self.compile(stmt.body)
                    idx = self.add_constant(None)
                    self.emit(OpCode.PUSH_CONST, idx)
                    self.emit(OpCode.RETURN)
                    self.patch_jmp(skip_jmp_idx, len(self.bytecode))
                    methods[stmt.name] = method_pc
            
            idx_name = self.add_constant(node.name)
            idx_fields = self.add_constant(node.fields)
            idx_methods = self.add_constant(methods)
            self.emit(OpCode.PUSH_CONST, idx_name)
            self.emit(OpCode.PUSH_CONST, idx_fields)
            self.emit(OpCode.PUSH_CONST, idx_methods)
            self.emit(OpCode.MAKE_CLASS)
            
            idx_var = self.add_constant(node.name)
            self.emit(OpCode.STORE_VAR, idx_var)

        elif isinstance(node, AttributeNode):
            self.compile(node.obj)
            idx = self.add_constant(node.attr)
            self.emit(OpCode.PUSH_CONST, idx)
            self.emit(OpCode.LOAD_ATTR)

        elif isinstance(node, AttributeAssignNode):
            self.compile(node.obj)
            self.compile(node.value)
            idx = self.add_constant(node.attr)
            self.emit(OpCode.PUSH_CONST, idx)
            self.emit(OpCode.STORE_ATTR)

        elif isinstance(node, FormattedStringNode):
            for part in node.parts:
                if isinstance(part, StringNode):
                    idx = self.add_constant(part.value)
                    self.emit(OpCode.PUSH_CONST, idx)
                else:
                    self.compile(part)
                    self.emit(OpCode.FORMAT_VAL)
            self.emit(OpCode.BUILD_STR, len(node.parts))

        elif isinstance(node, TupleNode):
            for el in node.elements:
                self.compile(el)
            self.emit(OpCode.LIST_INIT, len(node.elements))
            idx = self.add_constant(tuple)
            self.emit(OpCode.PUSH_CONST, idx)
            self.emit(OpCode.CALL, 1)

        elif isinstance(node, PipeNode):
            self.compile(node.value)
            self.compile(node.func)
            self.emit(OpCode.CALL, 1)

        elif isinstance(node, SpecialOpNode):
            if node.op == "??":
                self.compile(node.left)
                self.emit(OpCode.DUP)
                none_idx = self.add_constant(None)
                self.emit(OpCode.PUSH_CONST, none_idx)
                self.emit(OpCode.EQ)
                skip_idx = self.emit_jmp(OpCode.JMP_IF_FALSE)
                self.emit(OpCode.POP)
                self.compile(node.right)
                self.patch_jmp(skip_idx, len(self.bytecode))
            else:
                raise RuntimeError(f"Unsupported special op: {node.op}")

        elif isinstance(node, TryNode):
            handler_idx = self.emit_jmp(OpCode.SETUP_EXCEPT)
            self.compile(node.try_body)
            self.emit(OpCode.POP_EXCEPT)
            if node.else_body:
                self.compile(node.else_body)
            end_idx = self.emit_jmp(OpCode.JMP)
            self.patch_jmp(handler_idx, len(self.bytecode))
            for exc_body in node.except_body:
                self.compile(exc_body)
            self.emit(OpCode.POP_EXCEPT)
            self.patch_jmp(end_idx, len(self.bytecode))

        elif isinstance(node, ImportNode):
            lib_dir = Path(__file__).resolve().parent.parent / "lib"
            or_path = lib_dir / f"{node.name}.or"
            if or_path.exists():
                lib_path = str(lib_dir).replace("\\", "\\\\")
                preamble = PyNode(f"import sys as _sys\nif r'{lib_path}' not in _sys.path:\n    _sys.path.insert(0, r'{lib_path}')")
                self.compile(preamble)
                with open(or_path, encoding="utf-8") as f:
                    code = [line.rstrip("\n") for line in f]
                tokens = lex(code)
                ast = Parser(tokens).program()
                for stmt in ast.statements:
                    self.compile(stmt)
            else:
                idx = self.add_constant(node.name)
                self.emit(OpCode.PUSH_CONST, idx)
                builtins_idx = self.add_constant(__import__)
                self.emit(OpCode.PUSH_CONST, builtins_idx)
                self.emit(OpCode.CALL, 1)
                var_idx = self.add_constant(node.name)
                self.emit(OpCode.STORE_VAR, var_idx)

        elif isinstance(node, ImportFromNode):
            mod = __import__(node.lib, fromlist=node.name.split(", "))
            for i in node.name.split(", "):
                i = i.strip()
                if not i:
                    continue
                attr = getattr(mod, i)
                idx = self.add_constant(attr)
                self.emit(OpCode.PUSH_CONST, idx)
                var_idx = self.add_constant(i)
                self.emit(OpCode.STORE_VAR, var_idx)

        elif isinstance(node, ImportAsNode):
            idx = self.add_constant(node.name)
            self.emit(OpCode.PUSH_CONST, idx)
            builtins_idx = self.add_constant(__import__)
            self.emit(OpCode.PUSH_CONST, builtins_idx)
            self.emit(OpCode.CALL, 1)
            var_idx = self.add_constant(node.alias)
            self.emit(OpCode.STORE_VAR, var_idx)

        elif isinstance(node, LambdaNode):
            skip_jmp_idx = self.emit_jmp(OpCode.JMP)
            lambda_pc = len(self.bytecode)
            if node.var:
                param_idx = self.add_constant(node.var)
                self.emit(OpCode.STORE_VAR, param_idx)
            self.compile(node.func)
            self.emit(OpCode.RETURN)
            self.patch_jmp(skip_jmp_idx, len(self.bytecode))
            func_const_idx = self.add_constant(lambda_pc)
            self.emit(OpCode.PUSH_CONST, func_const_idx)

        elif isinstance(node, SetNode):
            if node.name == "servo" and node.type_ == "angle":
                self.compile(node.num)
                self.compile(node.params)
                self.emit(OpCode.SET_SERVO)
            elif node.name == "pin":
                self.compile(node.num)
                self.compile(node.params)
                self.emit(OpCode.SET_PIN)
            else:
                self.compile(node.num)
                self.compile(node.params)
                idx = self.add_constant(node.name)
                self.emit(OpCode.PUSH_CONST, idx)
                t_idx = self.add_constant(node.type_)
                self.emit(OpCode.PUSH_CONST, t_idx)
                self.emit(OpCode.CALL, 3)

        elif isinstance(node, HardwarePrimitiveNode):
            self.compile(node.args[0]) if node.args else None
            for arg in node.args[1:]:
                self.compile(arg)
            idx = self.add_constant((node.namespace, node.method))
            self.emit(OpCode.PUSH_CONST, idx)
            self.emit(OpCode.HARDWARE_CALL, len(node.args))

        elif isinstance(node, ReadNode):
            fname = node.file[1:-1] if node.file[:1] in ('"', "'") else node.file
            file_idx = self.add_constant(fname)
            self.emit(OpCode.PUSH_CONST, file_idx)
            self.emit(OpCode.READ_FILE, node.count)

        elif isinstance(node, WriteNode):
            fname = node.file[1:-1] if node.file[:1] in ('"', "'") else node.file
            file_idx = self.add_constant(fname)
            self.emit(OpCode.PUSH_CONST, file_idx)
            self.compile(node.contents)
            self.emit(OpCode.WRITE_FILE)

        elif isinstance(node, AppendNode):
            fname = node.file[1:-1] if node.file[:1] in ('"', "'") else node.file
            file_idx = self.add_constant(fname)
            self.emit(OpCode.PUSH_CONST, file_idx)
            self.compile(node.contents)
            self.emit(OpCode.APPEND_FILE)

        elif isinstance(node, ParallelNode):
            # For bytecode VM, delegate to a builtin that handles threading
            code_str = "import threading\n_threads = []\n"
            if node.threads > 0:
                code_str += "def _parallel_block():\n"
                lines = []
                if hasattr(node.body, 'statements'):
                    for stmt in node.body.statements:
                        lines.append(str(stmt))
                code_str += "    pass\n"
                code_str += f"for _ in range({node.threads}):\n"
                code_str += "    t = threading.Thread(target=_parallel_block)\n"
                code_str += "    t.start(); _threads.append(t)\n"
            else:
                for i, stmt in enumerate(node.body.statements):
                    code_str += f"def _ps_{i}():\n"
                    code_str += f"    print(f'[SIM] parallel statement {i}')\n"
                    code_str += f"_t{i} = threading.Thread(target=_ps_{i})\n"
                    code_str += f"_t{i}.start(); _threads.append(_t{i})\n"
            code_str += "for t in _threads: t.join()\n"
            idx = self.add_constant(code_str)
            self.emit(OpCode.PUSH_CONST, idx)
            self.emit(OpCode.EXEC_PY)

        elif isinstance(node, PyNode):
            idx = self.add_constant(node.code)
            self.emit(OpCode.PUSH_CONST, idx)
            self.emit(OpCode.EXEC_PY)
        
        elif isinstance(node, ImuNode):
            # Mirror interpreter.py:360 - handled via EXEC_PY to import and instantiate
            code = f"from {node.name} import {node.name}\n__imu_tmp = {node.name}({node.address})"
            idx = self.add_constant(code)
            self.emit(OpCode.PUSH_CONST, idx)
            self.emit(OpCode.EXEC_PY)
            # Push the created instance onto stack for expression use
            tmp_idx = self.add_constant("__imu_tmp")
            self.emit(OpCode.LOAD_VAR, tmp_idx)

        elif isinstance(node, ImuFromNode):
            # Mirror interpreter.py:363 - node.value is sensor (accel/gyro/temp), node.name is device var
            tmp_code = f"__imu_from_tmp = {node.name}.get_{node.value}()"
            idx2 = self.add_constant(tmp_code)
            self.emit(OpCode.PUSH_CONST, idx2)
            self.emit(OpCode.EXEC_PY)
            tmp_idx = self.add_constant("__imu_from_tmp")
            self.emit(OpCode.LOAD_VAR, tmp_idx)

        elif isinstance(node, ExecNode):
            # Mirror interpreter.py:119 - run Origin code via runner.py subprocess
            # Generate Python code that host EXEC_PY will exec
            runner_code = (
                "import os, sys, subprocess\n"
                f"runner_path = os.path.join(os.path.dirname({repr(__file__)}), 'runner.py')\n"
                f"open('temp_exec.py','w',encoding='utf-8').write({repr(node.code)})\n"
                "subprocess.run([sys.executable, runner_path, 'temp_exec.py'])"
            )
            idx = self.add_constant(runner_code)
            self.emit(OpCode.PUSH_CONST, idx)
            self.emit(OpCode.EXEC_PY)

        elif isinstance(node, CommandNode):
            # Mirror interpreter.py:504 - subprocess.run(cmd.split(), **flags)
            cmd = node.command
            if hasattr(cmd, 'value'):
                cmd = cmd.value
            if isinstance(cmd, str) and len(cmd) >= 2 and cmd[0] in ('"', "'") and cmd[-1] == cmd[0]:
                cmd = cmd[1:-1]
            flags = getattr(node, 'flags', getattr(node, 'params', None))
            # Generate Python code string and exec via EXEC_PY (reuses svm.py:514)
            if isinstance(flags, dict) and flags:
                kwargs = ", ".join(f"{k}={repr(v)}" for k, v in flags.items())
                code = f"__import__('subprocess').run({repr(cmd)}.split(), {kwargs})"
            else:
                code = f"__import__('subprocess').run({repr(cmd)}.split())"
            idx = self.add_constant(code)
            self.emit(OpCode.PUSH_CONST, idx)
            self.emit(OpCode.EXEC_PY)
            
        elif isinstance(node, MoveNode):
            src_name_idx = self.add_constant(node.src)
            dst_name_idx = self.add_constant(node.dst)
            self.emit(OpCode.MOVE, dst_name_idx, src_name_idx)
            
        elif isinstance(node, CopyNode):
            src_name_idx = self.add_constant(node.src)
            dst_name_idx = self.add_constant(node.dst)
            self.emit(OpCode.COPY, dst_name_idx, src_name_idx)

        if isinstance(node, ProgramNode):
            self.emit(OpCode.HALT)
            
            for item in self.unresolved_calls:
                if len(item) == 2:
                    func_name, const_idx = item
                    opcode_idx = None
                else:
                    func_name, const_idx, opcode_idx = item
                    
                if func_name in self.functions:
                    self.constants[const_idx] = self.functions[func_name]
                else:
                    if opcode_idx is not None:
                        self.bytecode[opcode_idx] = OpCode.LOAD_VAR
                    else:
                        raise NameError(f"Function '{func_name}' is not defined")


