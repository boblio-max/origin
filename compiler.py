from attr import field
from parser import *
from classes import *
import random
import csv

CONST_VARS = {}
fieldnames = ['name', 'value']
csv_file_path = 'CONST_VARS.csv'

# --- Bytecode instructions ---
OP_LOAD_CONST    = 1
OP_LOAD_VAR      = 2
OP_STORE_VAR     = 3
OP_ADD           = 4
OP_SUB           = 5
OP_MUL           = 6
OP_DIV           = 7
OP_PRINT         = 8
OP_JUMP_IF_FALSE = 9
OP_JUMP         = 10
OP_LOAD_LIST    = 11
OP_STORE_LIST   = 12
OP_RAND         = 13
OP_INPUT        = 14
OP_CAST         = 15
OP_LT           = 16

# --- Bytecode Compiler ---
class Compiler:
    def __init__(self):
        self.bytecode = []
        self.constants = []

    def print(self):
        print(self.bytecode)
    def compile(self, node):
        if isinstance(node, NumberNode):
            idx = self.add_const(node.value)
            self.emit(OP_LOAD_CONST, idx)

        elif isinstance(node, StringNode):
            idx = self.add_const(node.value)
            self.emit(OP_LOAD_CONST, idx)

        elif isinstance(node, VarNode):
            self.emit(OP_LOAD_VAR, node.name)

        elif isinstance(node, AssignNode):
            self.compile(node.value)
            self.emit(OP_STORE_VAR, node.name)

        elif isinstance(node, BinOpNode):
            self.compile(node.left)
            self.compile(node.right)
            if node.op == '+': self.emit(OP_ADD)
            elif node.op == '-': self.emit(OP_SUB)
            elif node.op == '*': self.emit(OP_MUL)
            elif node.op == '/': self.emit(OP_DIV)

        elif isinstance(node, PrintNode):
            self.compile(node.expr)
            self.emit(OP_PRINT)

        elif isinstance(node, RandNumNode):
            self.compile(node.start)
            self.compile(node.end)
            self.emit(OP_RAND)

        elif isinstance(node, ListNode):
            for el in node.elements:
                self.compile(el)
            self.emit(OP_LOAD_LIST, len(node.elements))

        elif isinstance(node, listCallNode):
            self.compile(node.list_node)
            self.compile(node.pos)
            self.emit(OP_LOAD_LIST)

        elif isinstance(node, BlockNode) or isinstance(node, ProgramNode):
            for stmt in node.statements:
                self.compile(stmt)

        elif isinstance(node, UnaryOpNode):
            self.compile(node.node)
            # Support unary minus
            if node.op == '-':
                idx = self.add_const(-1)
                self.emit(OP_LOAD_CONST, idx)
                self.emit(OP_MUL)

        elif isinstance(node, IfNode):
            self.compile(node.condition)
            jump_idx = len(self.bytecode)
            self.emit(OP_JUMP_IF_FALSE, 0)  # placeholder
            self.compile(node.then_body)
            op, _ = self.bytecode[jump_idx]
            self.bytecode[jump_idx] = (op, len(self.bytecode))    # patch jump
            if node.else_body:
                self.compile(node.else_body)

        elif isinstance(node, ForNode):
            # Initialize loop variable
            self.compile(node.iterable.start)
            self.emit(OP_STORE_VAR, node.var_name)

            start_idx = len(self.bytecode)  # start of loop

            # Compare i < end
            self.emit(OP_LOAD_VAR, node.var_name)
            self.compile(node.iterable.end)
            self.emit(OP_LT)

            # Conditional jump
            jump_idx = len(self.bytecode)
            self.emit(OP_JUMP_IF_FALSE, None)  # placeholder

            # Loop body
            self.compile(node.body)

            # Increment loop variable
            self.emit(OP_LOAD_VAR, node.var_name)
            idx = self.add_const(1)
            self.emit(OP_LOAD_CONST, idx)
            self.emit(OP_ADD)
            self.emit(OP_STORE_VAR, node.var_name)

            # Jump back to start
            self.emit(OP_JUMP, start_idx)

            # Patch jump target
            op, _ = self.bytecode[jump_idx]
            self.bytecode[jump_idx] = (op, len(self.bytecode))
        # patch jump
            
        elif isinstance(node, WhileNode):
            start_idx = len(self.bytecode)
            self.compile(node.condition)
            jump_idx = len(self.bytecode)
            self.emit(OP_JUMP_IF_FALSE, 0)  # placeholder
            self.compile(node.body)
            self.emit(OP_JUMP, start_idx)
            op, _ = self.bytecode[jump_idx]
            self.bytecode[jump_idx] = (op, len(self.bytecode))  # patch jump

        elif isinstance(node, CastNode):
            self.compile(node.value)
            self.emit(OP_CAST, node.cast_type)

        else:
            raise RuntimeError(f"Unknown node type: {node}")

    def emit(self, op, arg=None):
        self.bytecode.append((op,arg))


    def add_const(self, value):
        self.constants.append(value)
        return len(self.constants)-1

# --- Virtual Machine ---
class VM:
    def __init__(self, bytecode, constants):
        self.bytecode = bytecode
        self.constants = constants
        self.stack = []
        self.vars = {}
        self.pc = 0

    def run(self):
        # bytecode = self.bytecode
        # constants = self.constants
        # stack = self.stack
        # vars = self.vars
        # pc = self.pc
        while self.pc < len(self.bytecode):
            op, args = self.bytecode[self.pc]
            self.pc += 1

            if op == OP_LOAD_CONST:
                self.stack.append(self.constants[args])

            elif op == OP_LOAD_VAR:
                self.stack.append(self.vars[args])

            elif op == OP_STORE_VAR:
               self.vars[args] = self.stack.pop()

            elif op == OP_ADD:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a + b)

            elif op == OP_SUB:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a - b)

            elif op == OP_MUL:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a * b)

            elif op == OP_DIV:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a / b)

            elif op == OP_PRINT:
                print(self.stack.pop())

            elif op == OP_RAND:
                end = self.stack.pop()
                start = self.stack.pop()
                self.stack.append(random.randint(int(start), int(end)))

            elif op == OP_CAST:
                val = self.stack.pop()
                if args == 'int': self.stack.append(int(val))
                elif args == 'float': self.stack.append(float(val))
                elif args == 'str': self.stack.append(str(val))

            elif op == OP_JUMP:
                self.pc = args

            elif op == OP_JUMP_IF_FALSE:
                cond = self.stack.pop()
                if not cond:
                    self.pc = args

            elif op == OP_LT:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a < b)
