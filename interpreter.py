"""interpreter

AST-to-Python translator and execution helpers.

This module implements a small interpreter that traverses the AST produced by
``parser.Parser`` and emits executable Python source strings. Emitted code may
be executed directly or written to temporary files for separate runners. The
interpreter also records imports and constants to simple CSV trackers used by
the wider toolchain.
"""

# Standard library imports used by code generation and runtime support.

from attr import field
from parser import *
from classes import *
import random
import csv
import math, sys
from multiprocessing import Process

# Global dictionary to store constant variables and their values
CONST_VARS = {}
csv_file_path = "C:\\Users\\smile\\OneDrive\\Documents\\origin\\ORIGIN_CODE\\CONST_VARS.csv"

# Clear or create the CSV file for constant variables
with open(csv_file_path, "w") as f:
    pass

# List to store imported modules (for tracking purposes)
imports = []
csv_file_path_imports = "C:\\Users\\smile\\OneDrive\\Documents\\origin\\ORIGIN_CODE\\imports.csv"
with open(csv_file_path_imports, "w") as f:
    pass

# --- Interpreter ---
# The interpreter takes the AST and generates Python code as a string.
# It handles all the different node types and translates them into valid Python code.
# For example, an AssignNode will generate a line of code that assigns a value to a variable,
# while an IfNode will generate an if statement with the appropriate indentation.
# The generated code is then executed using exec() in the runner(Alt/Byte).py file.

class interpreter:
    """Generate Python source from the AST.

    Instances expose :meth:`generate` which performs a recursive traversal of
    AST nodes and returns a string containing the equivalent Python code for
    that subtree.
    """

    def generate(self, node):
        """Recursively translate an AST node into Python source text.

        The method returns a Python code fragment for the provided node. For
        structured nodes (blocks, functions, control flow) the returned text
        will contain one or more properly indented statements. Callers should
        not assume the returned string is a complete program unless the root
        node is a :class:`ProgramNode`.

        Args:
            node (ASTNode): Node to translate.

        Returns:
            str: Python source representing ``node``.

        Raises:
            RuntimeError: For illegal operations (constant reassignment) or when
                encountering an unrecognized node type.
        """
        if isinstance(node, ProgramNode):
            # Evaluate all top-level statements
            return "\n".join(self.generate(stmt) for stmt in node.statements)

        elif isinstance(node, BlockNode):
            # Evaluate an inner block of statements
            return "\n".join(self.generate(stmt) for stmt in node.statements)

        elif isinstance(node, ExecNode):
            # Writes code to a temporary file and dispatches it via a parallel runner
            file_to_run = "temp_exec.py"
            with open("temp_exec.py", mode='w', newline='') as file:
                file.write(node.code)
            command = [sys.executable, "runner.py", file_to_run]
        
        elif isinstance(node, AssignNode):
            # Protect against constant overriding
            if node.name in CONST_VARS:
                raise RuntimeError(f"Cannot reassign constant variable '{node.name}'")
            return f"{node.name} = {self.generate(node.value)}"
        
        elif isinstance(node, SetNode):
            # Custom setter, e.g., setting servo angles
            if node.name in CONST_VARS:
                raise RuntimeError(f"Cannot reassign constant variable '{node.name}'")
            if node.name == "servo" and node.type_ == "angle" and node.name == "servo":
                return "from adafruit_servokit import ServoKit\nkit = ServoKit(channels=16)\nkit.servo[{node.num}].angle = {node.params}"
        
        elif isinstance(node, ConstAssignNode):
            # Handling constant assignments and writing them natively to a CSV
            if node.name in CONST_VARS:
                raise RuntimeError(f"Cannot reassign constant variable '{node.name}'")
            CONST_VARS[node.name] = self.generate(node.value)

            with open(csv_file_path, mode='a', newline='') as csvfile:
                data = [node.name, self.generate(node.value)]
                writer = csv.DictWriter(csvfile, fieldnames=['name', 'value'])
                writer.writeheader()
                writer.writerow(dict(zip(['name', 'value'], data)))
            return f"{node.name} = {self.generate(node.value)}"

        elif isinstance(node, ParallelNode):
            # Handles simulated parallelism operations
            arr = [str(e) for e in node.prc] 
            print(arr)
            
        elif isinstance(node, listCallNode):
            # List item retrieval
            list_code = self.generate(node.list_node)
            pos_code = self.generate(node.pos)
            return f"{list_code}[{pos_code}]"
        
        elif isinstance(node, RandNumNode):
            # Native random integration
            start = self.generate(node.start)
            end = self.generate(node.end)
            return random.randint(int(start), int(end))
        
        elif isinstance(node, NoneNode):
            return "None"
        
        elif isinstance(node, PassNode):
            return "pass"
        
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
        
        elif isinstance(node, DictNode):
            return f"{{{', '.join(f'{self.generate(k)}: {self.generate(v)}' for k, v in node.elements.items())}}}"
            
        elif isinstance(node, BinOpNode):
            # Binary operations, enclosed in parentheses for safety
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
            # Handles conventional IF statements
            code = f"if {self.generate(node.condition)}:\n"
            then_body = self.indent_block(self.generate(node.then_body))
            code += then_body
            if node.else_body:
                code += "\nelse:\n"
                else_body = self.indent_block(self.generate(node.else_body))
                code += else_body
            return code
        
        elif isinstance(node, ElifNode):
            # Handles ELIF cascade
            code = f"elif {self.generate(node.condition)}:\n"
            then_body = self.indent_block(self.generate(node.then_body))
            code += then_body
            if node.else_body:
                code += "\nelse:\n"
                else_body = self.indent_block(self.generate(node.else_body))
                code += else_body
            return code
        
        elif isinstance(node, WhileNode):
            # Translates WHILE loops
            code = f"while {self.generate(node.condition)}:\n"
            body = self.indent_block(self.generate(node.body))
            code += body
            return code
        
        elif isinstance(node, TryNode):
            # Error handling with try-except blocks
            code = "try:\n"
            try_body = self.indent_block(self.generate(node.try_body))
            code += try_body
            if node.except_body:
                code += "\nexcept:\n"
                except_body = self.indent_block(self.generate(node.except_body))
                code += except_body
            return code
        
        elif isinstance(node, ForNode):
            # Standard Python for-each loops
            code = f"for {node.var_name} in {self.generate(node.iterable)}:\n"
            body = self.indent_block(self.generate(node.body))
            code += body
            return code
        
        elif isinstance(node, RangeNode):
            return f"range({self.generate(node.start)}, {self.generate(node.end)})"
        
        elif isinstance(node, CastNode):
            return f"{node.cast_type}({self.generate(node.value)})"
        
        elif isinstance(node, ImportNode):
            # Registering import to standard tracking CSV
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
        """
        Helper method to correctly indent blocks of generated Python code.
        
        Args:
            code (str): The code block string to indent.
            indent (int): Target number of space indentations. Defaults to 4.
            
        Returns:
            str: Indented Python code.
        """
        spaces = " " * indent
        return "\n".join(spaces + line if line.strip() else line for line in code.split("\n"))
