import random
import csv
import math
import sys
from .classes import *

class ir_gen:
    def __init__(self):
        self.code = []
        self.temp_count = 0
        self.label_count = 0
        self.loop_stack = []
        self.current_function = None

    def new_temp(self):
        self.temp_count += 1
        return f"t{self.temp_count}"

    def new_label(self):
        self.label_count += 1
        return f"L{self.label_count}"

    def emit(self, opcode, *args):
        self.code.append((opcode, *args))

    def generate(self, node):
        if isinstance(node, ProgramNode):
            return self.visitProgram(node)
        elif isinstance(node, BlockNode):
            return self.visitBlock(node)
        elif isinstance(node, NumberNode):
            return self.visitNumber(node)
        elif isinstance(node, StringNode):
            return self.visitString(node)
        elif isinstance(node, BoolNode):
            return self.visitBool(node)
        elif isinstance(node, NoneNode):
            return self.visitNull(node)
        elif isinstance(node, VarNode):
            return self.visitVariable(node)
        elif isinstance(node, AssignNode):
            self.visitAssign(node)
            return None
        elif isinstance(node, CompoundAssignNode):
            self.visitCompoundAssign(node)
            return None
        elif isinstance(node, BinOpNode):
            return self.visitBinary(node)
        elif isinstance(node, UnaryOpNode):
            return self.visitUnary(node)
        elif isinstance(node, CastNode):
            return self.visitCast(node)
        elif isinstance(node, PrintNode):
            self.visitPrint(node)
            return None
        elif isinstance(node, IfNode):
            self.visitIf(node)
            return None
        elif isinstance(node, WhileNode):
            self.visitWhile(node)
            return None
        elif isinstance(node, ForNode):
            self.visitFor(node)
            return None
        elif isinstance(node, BreakNode):
            self.visitBreak(node)
            return None
        elif isinstance(node, ContinueNode):
            self.visitContinue(node)
            return None
        elif isinstance(node, ReturnNode):
            self.visitReturn(node)
            return None
        elif isinstance(node, FuncNode):
            self.visitFunction(node)
            return None
        elif isinstance(node, CallNode):
            return self.visitCall(node)
        else:
            raise ValueError(f"Unsupported node type: {type(node)}")

    def visitProgram(self, node):
        for stmt in node.statements:
            self.generate(stmt)

    def visitBlock(self, node):
        for stmt in node.statements:
            self.generate(stmt)

    def visitNumber(self, node):
        temp = self.new_temp()
        if isinstance(node.value, int):
            self.emit("CONST_INT", temp, node.value)
        else:
            self.emit("CONST_FLOAT", temp, node.value)
        return temp

    def visitString(self, node):
        temp = self.new_temp()
        self.emit("CONST_STRING", temp, node.value)
        return temp

    def visitBool(self, node):
        temp = self.new_temp()
        self.emit("CONST_BOOL", temp, node.value)
        return temp

    def visitNull(self, node):
        temp = self.new_temp()
        self.emit("CONST_NULL", temp)
        return temp

    def visitVariable(self, node):
        temp = self.new_temp()
        self.emit("LOAD", temp, node.name)
        return temp

    def visitAssign(self, node):
        value_temp = self.generate(node.value)
        self.emit("STORE", node.name, value_temp)

    def visitCompoundAssign(self, node):
        temp1 = self.new_temp()
        self.emit("LOAD", temp1, node.name)

        right_temp = self.generate(node.value)

        if node.op == '+':
            temp2 = self.new_temp()
            self.emit("ADD", temp2, temp1, right_temp)
        elif node.op == '-':
            temp2 = self.new_temp()
            self.emit("SUB", temp2, temp1, right_temp)
        elif node.op == '*':
            temp2 = self.new_temp()
            self.emit("MUL", temp2, temp1, right_temp)
        elif node.op == '/':
            temp2 = self.new_temp()
            self.emit("DIV", temp2, temp1, right_temp)
        elif node.op == '%':
            temp2 = self.new_temp()
            self.emit("MOD", temp2, temp1, right_temp)
        elif node.op == '**':
            temp2 = self.new_temp()
            self.emit("POW", temp2, temp1, right_temp)
        elif node.op == '//':
            temp2 = self.new_temp()
            self.emit("IDIV", temp2, temp1, right_temp)

        self.emit("STORE", node.name, temp2)

    def visitBinary(self, node):
        left_temp = self.generate(node.left)
        right_temp = self.generate(node.right)

        op_map = {
            '+': 'ADD',
            '-': 'SUB',
            '*': 'MUL',
            '/': 'DIV',
            '%': 'MOD',
            '**': 'POW',
            '//': 'IDIV',

            '==': 'EQ',
            '!=': 'NE',
            '<': 'LT',
            '<=': 'LE',
            '>': 'GT',
            '>=': 'GE',

            '&&': 'AND',
            '||': 'OR',

            '&': 'BIT_AND',
            '|': 'BIT_OR',
            '^': 'BIT_XOR',

            '<<': 'SHL',
            '>>': 'SHR'
        }

        op = op_map.get(node.op)
        if op is not None:
            temp = self.new_temp()
            self.emit(op, temp, left_temp, right_temp)
            return temp

        raise ValueError(f"Unsupported binary operator: {node.op}")

    def visitUnary(self, node):
        operand_temp = self.generate(node.node)
        op_map = {
            '-': 'NEG',
            '!': 'NOT',
            '~': 'BIT_NOT',
        }
        op = op_map[node.op]
        temp = self.new_temp()
        self.emit(op, temp, operand_temp)
        return temp

    def visitCast(self, node):
        value_temp = self.generate(node.value)
        op_map = {
            'int': 'CAST_INT',
            'float': 'CAST_FLOAT',
            'str': 'CAST_STRING',
            'bool': 'CAST_BOOL',
            'char': 'CAST_CHAR',
        }
        op = op_map[node.cast_type]
        temp = self.new_temp()
        self.emit(op, temp, value_temp)
        return temp

    def visitPrint(self, node):
        expr_temp = self.generate(node.expr)
        self.emit("PRINT", expr_temp)

    def visitIf(self, node):
        cond_temp = self.generate(node.condition)
        else_label = self.new_label()
        end_label = self.new_label()
        self.emit("JUMP_IF_FALSE", cond_temp, else_label)
        self.generate(node.then_body)
        self.emit("JUMP", end_label)
        self.emit("LABEL", else_label)
        if node.else_body:
            self.generate(node.else_body)
        self.emit("LABEL", end_label)

    def visitWhile(self, node):
        loop_start = self.new_label()
        loop_end = self.new_label()
        self.loop_stack.append((loop_start, loop_end))
        self.emit("LABEL", loop_start)
        cond_temp = self.generate(node.condition)
        self.emit("JUMP_IF_FALSE", cond_temp, loop_end)
        self.generate(node.body)
        self.emit("JUMP", loop_start)
        self.emit("LABEL", loop_end)
        self.loop_stack.pop()

    def visitFor(self, node):
        iterable_temp = self.generate(node.iterable)
        len_temp = self.new_temp()
        self.emit("LEN", len_temp, iterable_temp)
        start_idx = self.new_temp()
        self.emit("CONST_INT", start_idx, 0)
        start_label = self.new_label()
        loop_label = self.new_label()
        end_label = self.new_label()
        self.emit("LABEL", loop_label)
        if isinstance(node.var, TupleNode):
            current_temp = self.new_temp()
            self.emit("LOAD_INDEX", current_temp, iterable_temp, start_idx)
        elif isinstance(node.var, ListNode):
            current_temp = self.new_temp()
            self.emit("LOAD_INDEX", current_temp, iterable_temp, start_idx)
        else:
            current_temp = self.new_temp()
            self.emit("LOAD_INDEX", current_temp, iterable_temp, start_idx)
        if isinstance(node.var, TupleNode):
            for i, var in enumerate(node.var.elements):
                self.emit("STORE", var.name, f"{current_temp}_{i}")
        else:
            self.emit("STORE", node.var.name, current_temp)
        self.emit("LABEL", start_label)
        cond_temp = self.new_temp()
        self.emit("LT", cond_temp, start_idx, len_temp)
        self.emit("JUMP_IF_FALSE", cond_temp, end_label)
        self.generate(node.body)
        next_idx = self.new_temp()
        one = self.new_temp()
        self.emit("CONST_INT", one, 1)
        self.emit("ADD", next_idx, start_idx, one)
        self.emit("STORE", start_idx, next_idx)
        self.emit("JUMP", loop_label)
        self.emit("LABEL", end_label)

    def visitBreak(self, node):
        start, end = self.loop_stack[-1]
        self.emit("JUMP", end)

    def visitContinue(self, node):
        start, end = self.loop_stack[-1]
        self.emit("JUMP", start)

    def visitReturn(self, node):
        value_temp = self.generate(node.value)
        self.emit("RETURN", value_temp)

    def visitFunction(self, node):
        old_function = self.current_function
        self.current_function = node.name
        self.emit("FUNCTION_BEGIN", node.name)
        for param in node.params:
            self.emit("PARAM", param)
        self.generate(node.body)
        self.emit("RETURN", "none")
        self.emit("FUNCTION_END")
        self.current_function = old_function

    def visitCall(self, node):
        args_temp = []
        for arg in node.args:
            args_temp.append(self.generate(arg))
        result_temp = self.new_temp()
        self.emit("CALL", result_temp, node.callee, *args_temp)
        return result_temp

    def visitList(self, node):
        temp = self.new_temp()
        self.emit("LIST_START", temp)
        for elem in node.elements:
            elem_temp = self.generate(elem)
            self.emit("LIST_ADD", temp, elem_temp)
        return temp

    def visitTuple(self, node):
        temp = self.new_temp()
        self.emit("TUPLE_START", temp)
        for elem in node.elements:
            elem_temp = self.generate(elem)
            self.emit("TUPLE_ADD", temp, elem_temp)
        return temp

    def visitRange(self, node):
        start_temp = self.generate(node.start)
        end_temp = self.generate(node.end)
        temp = self.new_temp()
        self.emit("RANGE", temp, start_temp, end_temp)
        return temp

    def visitMove(self, node):
        src_temp = self.generate(node.src)
        self.emit("STORE", node.dst, src_temp)
        
    def visitCopy(self, node):
        src_temp = self.generate(node.src)
        self.emit("COPY", node.dst, src_temp)

