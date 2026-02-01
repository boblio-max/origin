from attr import field
from parser import *
from classes import *
import random
import csv

CONST_VARS = {}
fieldnames = ['name', 'value']
csv_file_path = 'CONST_VARS.csv'

imports = []
csv_file_path_imports = 'imports.csv'
class interpreter:
    def generate(self, node):
        if isinstance(node, ProgramNode):
            return "\n".join(self.generate(stmt) for stmt in node.statements)

        elif isinstance(node, BlockNode):
            return "\n".join(self.generate(stmt) for stmt in node.statements)

        elif isinstance(node, AssignNode):
            if node.name in CONST_VARS:
                raise RuntimeError(f"Cannot reassign constant variable '{node.name}'")
            return f"{node.name} = {self.generate(node.value)}"
        elif isinstance(node, ConstAssignNode):
            if node.name in CONST_VARS:
                raise RuntimeError(f"Cannot reassign constant variable '{node.name}'")
            CONST_VARS['name'] = node.name
            CONST_VARS['value'] = self.generate(node.value)
            with open(csv_file_path, mode='w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            return f"{node.name} = {self.generate(node.value)}"
        elif isinstance(node, listCallNode):
            list_code = self.generate(node.list_node)
            pos_code = self.generate(node.pos)
            return f"{list_code}[{pos_code}]"
        
        elif isinstance(node, RandNumNode):
            start = self.generate(node.start)
            end = self.generate(node.end)
            return random.randint(int(start), int(end))
        elif isinstance(node, PrintNode):
            return f"print({self.generate(node.expr)})"

        elif isinstance(node, NumberNode):
            return str(node.value)

        elif isinstance(node, StringNode):
            return repr(node.value)

        elif isinstance(node, VarNode):
            return node.name

        elif isinstance(node, ListNode):
            return f"[{', '.join(self.generate(el) for el in node.elements)}]"
        elif isinstance(node, BinOpNode):
            return f"({self.generate(node.left)} {node.op} {self.generate(node.right)})"

        elif isinstance(node, UnaryOpNode):
            return f"({node.op}{self.generate(node.node)})"

        elif isinstance(node, InputNode):
            if node.prompt:
                return f"input({self.generate(node.prompt)})"
            else:
                return "input()"

        elif isinstance(node, IfNode):
            code = f"if {self.generate(node.condition)}:\n"
            then_body = self.indent_block(self.generate(node.then_body))
            code += then_body
            if node.else_body:
                code += "\nelse:\n"
                else_body = self.indent_block(self.generate(node.else_body))
                code += else_body
            return code
        elif isinstance(node, ElifNode):
            code = f"elif {self.generate(node.condition)}:\n"
            then_body = self.indent_block(self.generate(node.then_body))
            code += then_body
            if node.else_body:
                code += "\nelse:\n"
                else_body = self.indent_block(self.generate(node.else_body))
                code += else_body
            return code
        elif isinstance(node, WhileNode):
            code = f"while {self.generate(node.condition)}:\n"
            body = self.indent_block(self.generate(node.body))
            code += body
            return code
        
        elif isinstance(node, ForNode):
            code = f"for {node.var_name} in {self.generate(node.iterable)}:\n"
            body = self.indent_block(self.generate(node.body))
            code += body
            return code
        
        elif isinstance(node, RangeNode):
            return f"range({self.generate(node.start)}, {self.generate(node.end)})"
        
        elif isinstance(node, CastNode):
            return f"{node.cast_type}({self.generate(node.value)})"
        
        elif isinstance(node, ImportNode):
            with open(csv_file_path_imports, mode='w', newline='') as file:
                writer = csv.writer(file)
            return f"import {node.name.value}"

        else:
            raise RuntimeError(f"Unknown node type: {node}")

    @staticmethod
    def indent_block(code, indent=4):
        spaces = " " * indent
        return "\n".join(spaces + line if line.strip() else line for line in code.split("\n"))
