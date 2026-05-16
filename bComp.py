import random
import csv
import math
import sys
from classes import *

class OpCode:
    PUSH_CONST   = 0x01
    LOAD_VAR     = 0x02
    STORE_VAR    = 0x03
    ADD          = 0x04
    SUB          = 0x05
    MUL          = 0x06
    DIV          = 0x07
    MOD          = 0x08
    POW          = 0x09
    NEGATE       = 0x0A
    EQ           = 0x0B
    NEQ          = 0x0C
    LT           = 0x0D
    GT           = 0x0E
    LTE          = 0x0F
    GTE          = 0x10
    AND          = 0x11
    OR           = 0x12
    NOT          = 0x13
    JMP          = 0x14
    JMP_IF_FALSE = 0x15
    PRINT        = 0x16
    INPUT        = 0x17
    LEN          = 0x18
    SQRT         = 0x19
    RAND_NUM     = 0x1A
    LIST_INIT    = 0x1B
    DICT_INIT    = 0x1C
    INDEX_LOAD   = 0x1D
    INDEX_STORE  = 0x1E
    HALT         = 0x1F
    POP          = 0x20
    DUP          = 0x21
    CALL         = 0x22
    RETURN       = 0x23
    LOOP_START   = 0x24 # For break/continue logic
    LOOP_END     = 0x25
    BREAK        = 0x26
    CONTINUE     = 0x27
    CAST_STR     = 0x28
    CAST_INT     = 0x29
    CAST_FLOAT   = 0x2A
    GET_ITER     = 0x2B
    FOR_ITER     = 0x2C

class Compiler:
    def __init__(self):
        self.bytecode = []
        self.constants = []
        self.loop_starts = [] # Stack of JMP targets for continue
        self.loop_ends = []   # Stack of placeholder indices for break
        self.variable_types = {}
        self.functions = {}
        self.unresolved_calls = []

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

    def emit(self, opcode, operand=None):
        self.bytecode.append(opcode)
        if operand is not None:
            self.bytecode.append(operand)

    def add_constant(self, value):
        if value in self.constants:
            return self.constants.index(value)
        self.constants.append(value)
        return len(self.constants) - 1

    def compile(self, node):
        if isinstance(node, ProgramNode) or isinstance(node, BlockNode):
            for stmt in node.statements:
                self.compile(stmt)

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
            
            if isinstance(node, AssignNode):
                if node.type is not None:
                    # Declaration with type (let x: int = ...)
                    if value_type is not None and value_type != node.type:
                         raise TypeError(f"Type Mismatch: variable '{node.name}' declared as {node.type} but assigned {value_type}")
                    self.variable_types[node.name] = node.type
                elif node.name in self.variable_types:
                    # Re-assignment without type (x = ...)
                    expected_type = self.variable_types[node.name]
                    if value_type is not None and value_type != expected_type:
                        raise TypeError(f"Type Mismatch: variable '{node.name}' is {expected_type} but assigned {value_type}")

            self.compile(node.value)
            idx = self.add_constant(node.name)
            self.emit(OpCode.STORE_VAR, idx)

        elif isinstance(node, BinOpNode):
            self.compile(node.left)
            self.compile(node.right)
            ops = {
                '+': OpCode.ADD, '-': OpCode.SUB, '*': OpCode.MUL, '/': OpCode.DIV,
                '==': OpCode.EQ, '!=': OpCode.NEQ, '<': OpCode.LT, '>': OpCode.GT,
                '<=': OpCode.LTE, '>=': OpCode.GTE, '%': OpCode.MOD, '**': OpCode.POW
            }
            if node.op in ops:
                self.emit(ops[node.op])
            else:
                raise RuntimeError(f"Unsupported binop: {node.op}")

        elif isinstance(node, UnaryOpNode):
            self.compile(node.node)
            if node.op == '-':
                self.emit(OpCode.NEGATE)
            elif node.op in ('not', '!'):
                self.emit(OpCode.NOT)

        elif isinstance(node, LogicOpNode):
            self.compile(node.left)
            self.compile(node.right)
            if node.op == 'and': self.emit(OpCode.AND)
            elif node.op == 'or': self.emit(OpCode.OR)

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
                '%=': OpCode.MOD,
                '**=': OpCode.POW
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
            
            # 5. Save the item to the loop variable (e.g. 'x')
            var_idx = self.add_constant(node.var_name)
            self.emit(OpCode.STORE_VAR, var_idx)
            
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
            # We don't have a RANGE opcode, so we'll just use a CALL to Python's range
            # Or we can just add a RANGE OpCode. Let's use a Call for now to keep it simple.
            idx = self.add_constant(range)
            self.emit(OpCode.PUSH_CONST, idx)
            self.emit(OpCode.CALL, 2)

        elif isinstance(node, LenNode):
            self.compile(node.value)
            self.emit(OpCode.LEN)

        elif isinstance(node, SqrtNode):
            self.compile(node.value)
            self.emit(OpCode.SQRT)

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
                else:
                    idx = self.add_constant(0)
                    self.emit(OpCode.PUSH_CONST, idx)
                    self.unresolved_calls.append((func_name, idx))
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
            else:
                raise RuntimeError(f"Unsupported cast target: {node.cast_type}")

        elif isinstance(node, ReturnNode):
            self.compile(node.value)
            self.emit(OpCode.RETURN)

        if isinstance(node, ProgramNode):
            self.emit(OpCode.HALT)
            
            for func_name, const_idx in self.unresolved_calls:
                if func_name in self.functions:
                    self.constants[const_idx] = self.functions[func_name]
                else:
                    raise NameError(f"Function '{func_name}' is not defined")

class VM:
    def __init__(self, bytecode, constants):
        self.bytecode = bytecode
        self.constants = constants
        self.stack = []
        self.variables = {}
        self.pc = 0
        self.call_stack = []

    def run(self):
        while self.pc < len(self.bytecode):
            opcode = self.bytecode[self.pc]
            self.pc += 1

            if opcode == OpCode.PUSH_CONST:
                idx = self.bytecode[self.pc]
                self.pc += 1
                self.stack.append(self.constants[idx])

            elif opcode == OpCode.LOAD_VAR:
                idx = self.bytecode[self.pc]
                self.pc += 1
                name = self.constants[idx]
                if name not in self.variables:
                    raise NameError(f"Name '{name}' is not defined")
                self.stack.append(self.variables[name])

            elif opcode == OpCode.STORE_VAR:
                idx = self.bytecode[self.pc]
                self.pc += 1
                name = self.constants[idx]
                val = self.stack.pop()
                self.variables[name] = val

            elif opcode == OpCode.ADD:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a + b)

            elif opcode == OpCode.SUB:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a - b)

            elif opcode == OpCode.MUL:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a * b)

            elif opcode == OpCode.DIV:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a / b)

            elif opcode == OpCode.MOD:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a % b)
            
            elif opcode == OpCode.POW:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a ** b)
                
            elif opcode == OpCode.NEGATE:
                val = self.stack.pop()
                self.stack.append(-(val))
                
            elif opcode == OpCode.EQ:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a == b)

            elif opcode == OpCode.JMP:
                target = (self.bytecode[self.pc] << 8) | self.bytecode[self.pc+1]
                self.pc += 2
                self.pc = target

            elif opcode == OpCode.JMP_IF_FALSE:
                target = (self.bytecode[self.pc] << 8) | self.bytecode[self.pc+1]
                self.pc += 2
                val = self.stack.pop()
                if not val:
                    self.pc = target

            elif opcode == OpCode.PRINT:
                val = self.stack.pop()
                print(val)

            elif opcode == OpCode.INPUT:
                prompt = self.stack.pop()
                res = input(prompt)
                self.stack.append(res)

            elif opcode == OpCode.SQRT:
                val = self.stack.pop()
                self.stack.append(math.sqrt(float(val)))

            elif opcode == OpCode.RAND_NUM:
                end = int(self.stack.pop())
                start = int(self.stack.pop())
                self.stack.append(random.randint(start, end))

            elif opcode == OpCode.LIST_INIT:
                n = self.bytecode[self.pc]
                self.pc += 1
                elements = []
                for _ in range(n):
                    elements.insert(0, self.stack.pop())
                self.stack.append(elements)

            elif opcode == OpCode.DICT_INIT:
                n = self.bytecode[self.pc]
                self.pc += 1
                elements = {}
                for _ in range(n):
                    v = self.stack.pop()
                    k = self.stack.pop()
                    elements[k] = v
                self.stack.append(elements)

            elif opcode == OpCode.INDEX_LOAD:
                idx = self.stack.pop()
                coll = self.stack.pop()
                self.stack.append(coll[idx])

            elif opcode == OpCode.INDEX_STORE:
                val = self.stack.pop()
                idx = self.stack.pop()
                coll = self.stack.pop()
                coll[idx] = val

            elif opcode == OpCode.LEN:
                val = self.stack.pop()
                self.stack.append(len(val))

            elif opcode == OpCode.AND:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a and b)
            
            elif opcode == OpCode.OR:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a or b)
                
            elif opcode == OpCode.CAST_STR:
                self.stack.append(str(self.stack.pop()))
                
            elif opcode == OpCode.CAST_INT:
                self.stack.append(int(self.stack.pop()))
            
            elif opcode == OpCode.CAST_FLOAT:
                self.stack.append(float(self.stack.pop()))

            elif opcode == OpCode.GET_ITER:
                obj = self.stack.pop()
                self.stack.append(iter(obj))

            elif opcode == OpCode.FOR_ITER:
                target = (self.bytecode[self.pc] << 8) | self.bytecode[self.pc+1]
                self.pc += 2
                it = self.stack[-1] # Peek at the iterator on the stack
                try:
                    val = next(it)
                    self.stack.append(val)
                except StopIteration:
                    self.stack.pop() # Remove the exhausted iterator
                    self.pc = target
                
            elif opcode == OpCode.CALL:
                num_args = self.bytecode[self.pc]
                self.pc += 1
                func = self.stack.pop() 
                
                if isinstance(func, int):
                    # It's a bytecode function address (jump to it)
                    self.call_stack.append(self.pc) 
                    self.pc = func 
                else:
                    # It's a Python built-in function (like range or str)
                    args = []
                    for _ in range(num_args):
                        args.insert(0, self.stack.pop())
                    result = func(*args)
                    self.stack.append(result)

            elif opcode == OpCode.RETURN:
                if self.call_stack:
                    self.pc = self.call_stack.pop() # Restore PC from call stack
                else:
                    break # No more calls on stack, end execution

            elif opcode == OpCode.HALT:
                break
