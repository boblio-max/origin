import random
import csv
import math
import sys
from classes import *

class OpCode:
    PUSH_CONST = 0x01
    LOAD_VAR   = 0x02
    STORE_VAR  = 0x03
    ADD        = 0x04
    SUB        = 0x05
    MUL        = 0x06
    DIV        = 0x07
    MOD        = 0x08
    POW        = 0x09
    NEGATE     = 0x0A
    EQ         = 0x0B
    NEQ        = 0x0C
    LT         = 0x0D
    GT         = 0x0E
    LTE        = 0x0F
    GTE        = 0x10
    AND        = 0x11
    OR         = 0x12
    NOT        = 0x13
    JMP        = 0x14
    JMP_IF_FALSE = 0x15
    PRINT      = 0x16
    INPUT      = 0x17
    LEN        = 0x18
    SQRT       = 0x19
    RAND_NUM   = 0x1A
    LIST_INIT  = 0x1B
    DICT_INIT  = 0x1C
    INDEX_LOAD = 0x1D
    INDEX_STORE= 0x1E
    HALT       = 0x1F
    POP        = 0x20
    DUP        = 0x21
    CALL       = 0x22
    RETURN     = 0x23
    LOOP_START = 0x24 # For break/continue logic
    LOOP_END   = 0x25
    BREAK      = 0x26
    CONTINUE   = 0x27

class Compiler:
    def __init__(self):
        self.bytecode = []
        self.constants = []
        self.loop_starts = [] # Stack of JMP targets for continue
        self.loop_ends = []   # Stack of placeholder indices for break
        self.variable_types = {}

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
            self.compile(node.condition)
            self.emit(OpCode.JMP_IF_FALSE)
            false_jmp_idx = len(self.bytecode)
            self.emit(0) # Placeholder

            self.compile(node.then_body)
            self.emit(OpCode.JMP)
            end_jmp_idx = len(self.bytecode)
            self.emit(0) # Placeholder

            # Patch false jump (to elif or else or end)
            self.bytecode[false_jmp_idx] = len(self.bytecode)

            for elif_node in node.elif_nodes:
                 self.compile(elif_node.condition)
                 self.emit(OpCode.JMP_IF_FALSE)
                 next_elif_idx = len(self.bytecode)
                 self.emit(0)
                 
                 self.compile(elif_node.then_body)
                 self.emit(OpCode.JMP)
                 self.bytecode[end_jmp_idx] = len(self.bytecode) # Update jump targets
                 end_jmp_idx = len(self.bytecode) - 1
                 
                 self.bytecode[next_elif_idx] = len(self.bytecode)

            if node.else_body:
                self.compile(node.else_body)
            
            # Patch end jump
            # We need to loop back and patch all end jumps to the final end
            # For simplicity in this implementation, we just patch the last one.
            # A more robust compiler would track a list of 'end' jumps.
            self.bytecode[end_jmp_idx] = len(self.bytecode)

        elif isinstance(node, listCallNode):
            self.compile(node.list_node)
            self.compile(node.pos)
            self.emit(OpCode.INDEX_LOAD)

        elif isinstance(node, PassNode):
            pass

            start_pc = len(self.bytecode)
            self.loop_starts.append(start_pc)
            breaks = []
            self.loop_ends.append(breaks)

            self.compile(node.condition)
            self.emit(OpCode.JMP_IF_FALSE)
            exit_jmp_idx = len(self.bytecode)
            self.emit(0)

            self.compile(node.body)
            self.emit(OpCode.JMP, start_pc)

            # Patch exit jump
            self.bytecode[exit_jmp_idx] = len(self.bytecode)
            # Patch breaks
            for b_idx in breaks:
                self.bytecode[b_idx] = len(self.bytecode)
            
            self.loop_starts.pop()
            self.loop_ends.pop()

        elif isinstance(node, BreakNode):
            if not self.loop_ends: raise RuntimeError("Break outside loop")
            self.emit(OpCode.JMP)
            self.loop_ends[-1].append(len(self.bytecode))
            self.emit(0)

        elif isinstance(node, ContinueNode):
            if not self.loop_starts: raise RuntimeError("Continue outside loop")
            self.emit(OpCode.JMP, self.loop_starts[-1])

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

        if isinstance(node, ProgramNode):
            self.emit(OpCode.HALT)

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

            elif opcode == OpCode.EQ:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a == b)

            elif opcode == OpCode.JMP:
                target = self.bytecode[self.pc]
                self.pc = target

            elif opcode == OpCode.JMP_IF_FALSE:
                target = self.bytecode[self.pc]
                self.pc += 1
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

            elif opcode == OpCode.CALL:
                num_args = self.bytecode[self.pc]
                self.pc += 1
                func_pc = self.stack.pop() # Function entry point is on top of stack
                self.call_stack.append(self.pc) # Save current PC for return
                self.pc = func_pc # Jump to function entry point

            elif opcode == OpCode.RETURN:
                if self.call_stack:
                    self.pc = self.call_stack.pop() # Restore PC from call stack
                else:
                    break # No more calls on stack, end execution

            elif opcode == OpCode.HALT:
                break
