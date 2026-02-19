# IMPORTS
# Math, Random, CSV, Sys used for Initial Generation
# Adafruit ServoKit used for robotics control (if needed)

from attr import field
from parser import *
from classes import *
import random
import csv
import math,sys

# Global dictionary to store constant variables and their values
CONST_VARS = {}
csv_file_path = "CONST_VARS.csv"

with open(csv_file_path, "w") as f:
    pass
# List to store imported modules (for tracking purposes)
imports = []
csv_file_path_imports = "imports.csv"
with open(csv_file_path_imports, "w") as f:
    pass
# --- Interpreter ---
# The interpreter takes the AST and generates Python code as a string.
# It handles all the different node types and translates them into valid Python code.
# For example, an AssignNode will generate a line of code that assigns a value to a variable,
# while an IfNode will generate an if statement with the appropriate indentation.
# The generated code is then executed using exec() in the runner(Alt/Byte).py file.

class interpreter:
    def generate(self, node):
        if isinstance(node, ProgramNode):
            return "\n".join(self.generate(stmt) for stmt in node.statements)

        elif isinstance(node, BlockNode):
            return "\n".join(self.generate(stmt) for stmt in node.statements)

        elif isinstance(node, ExecNode):
            file_to_run = "temp_exec.py"
            with open("temp_exec.py", mode='w', newline='') as file:
                file.write(node.code)
            command = [sys.executable, "runner.py", file_to_run]
        
        elif isinstance(node, AssignNode):
            if node.name in CONST_VARS:
                raise RuntimeError(f"Cannot reassign constant variable '{node.name}'")
            return f"{node.name} = {self.generate(node.value)}"
        
        elif isinstance(node, SetNode):
            if node.name in CONST_VARS:
                raise RuntimeError(f"Cannot reassign constant variable '{node.name}'")
            if node.name == "servo" and node.type_ == "angle" and node.name == "servo":
                return "from adafruit_servokit import ServoKit\nkit = ServoKit(channels=16)\nkit.servo[{node.num}].angle = {node.params}"
        elif isinstance(node, ConstAssignNode):
            if node.name in CONST_VARS:
                raise RuntimeError(f"Cannot reassign constant variable '{node.name}'")
            CONST_VARS[node.name] = self.generate(node.value)

            with open(csv_file_path, mode='a', newline='') as csvfile:
                data = [node.name, self.generate(node.value)]
                writer = csv.DictWriter(csvfile, fieldnames=['name', 'value'])
                writer.writeheader()
                writer.writerow(dict(zip(['name', 'value'], data)))
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
        elif isinstance(node, SqrtNode):
            return f"{math.sqrt(float(self.generate(node.value)))}"
        
        elif isinstance(node, StringNode):
            return repr(node.value)

        elif isinstance(node, VarNode):
            return node.name

        elif isinstance(node, ListNode):
            return f"[{', '.join(self.generate(el) for el in node.elements)}]"
        elif isinstance(node, BinOpNode):
            val = self.generate(node.left) + " " + node.op + " " + self.generate(node.right)
            return f"({val})"

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
        
        elif isinstance(node, TryNode):
            code = "try:\n"
            try_body = self.indent_block(self.generate(node.try_body))
            code += try_body
            if node.except_body:
                code += "\nexcept:\n"
                except_body = self.indent_block(self.generate(node.except_body))
                code += except_body
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
            with open(csv_file_path_imports, mode='a', newline='') as file:
                data = [node.name.value]
                writer = csv.writer(file)
                writer.writerow(data)
                
            return f"import {node.name.value}"

        elif isinstance(node, ImportFromNode):
            with open(csv_file_path_imports, mode='a', newline='') as file:
                data = [node.name.value, node.lib.value]
                writer = csv.writer(file)
                writer.writerow(data)
            return f"from {node.name.value} import {node.lib.value}"

        elif isinstance(node, ImportAsNode):
            with open(csv_file_path_imports, mode='a', newline='') as file:
                data = [node.name.value, node.nName.value]
                writer = csv.writer(file)
                writer.writerow(data)
            return f"import {node.name.value} as {node.nName.value}"
        else:
            raise RuntimeError(f"Unknown node type: {node}")

    @staticmethod
    def indent_block(code, indent=4):
        spaces = " " * indent
        return "\n".join(spaces + line if line.strip() else line for line in code.split("\n"))
