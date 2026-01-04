from math import e
from classes import *

class Interpreter:
    def __init__(self):
        self.global_classes = set()

    def generate(self, node):
        if isinstance(node, ProgramNode):
            return "\n".join(self.generate(stmt) for stmt in node.statements)

        elif isinstance(node, BlockNode):
            return "\n".join(self.generate(stmt) for stmt in node.statements)
        
        elif isinstance(node, FuncNode):
            if hasattr(node, "params") and node.params:
                params_code = ", ".join(node.params)
                code = f"def {node.name}({params_code}):\n"
            else:
                code = f"def {node.name}():\n"

            body = self.indent_block(self.generate(node.body))
            code += body
            return code
        
        elif isinstance(node, CallNode):
            args_code = ", ".join(self.generate(a) for a in node.arg) if node.arg else ""
            if isinstance(node.func_name, VarNode):
                if node.func_name.name in self.global_classes:  # you can define self.global_classes = set of class names
                    return f"{node.func_name.name}({args_code})"

            return f"{self.generate(node.func_name)}({args_code})"

            
        elif isinstance(node, AssignNode):
            return f"{node.name} = {self.generate(node.value)}"
        elif isinstance(node, IndexAssignNode):
            collection = self.generate(node.collection)
            index = self.generate(node.index)
            value = self.generate(node.value)
            return f"{collection}[{index}] = {value}"

        elif isinstance(node, PrintNode):
            return f"print({self.generate(node.expr)})"

        elif isinstance(node, NumberNode):
            return str(node.value)

        elif isinstance(node, StringNode):
            return repr(node.value)
        
                
        elif isinstance(node, VarNode):
            return node.name

        elif isinstance(node, ClassNode):
            code = f"class {node.name}:\n"
            self.global_classes.add(node.name)
            # fields: create in __init__ if not already defined
            init_node = node.methods.get("init", None)
            if init_node is None and node.fields:
                # create default __init__ if none
                params_code = ", ".join(node.fields)
                init_code = f"def __init__(self, {params_code}):\n"
                for field in node.fields:
                    init_code += f"    self.{field} = {field}\n"
                code += self.indent_block(init_code)
            else:
                # include existing methods including init
                for method in node.methods.values():
                    method_code = self.generate(method)
                    code += self.indent_block(method_code)

            return code

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
            code += self.indent_block(self.generate(node.then_body))

            for elif_node in node.elif_nodes:
                code += "\nelif " + self.generate(elif_node.condition) + ":\n"
                code += self.indent_block(self.generate(elif_node.then_body))

            
            if node.else_body:
                code += "\nelse:\n"
                code += self.indent_block(self.generate(node.else_body))

            return code
        
        elif isinstance(node, LenNode):
            value = self.generate(node.value)
            return f"len({value})"
        elif isinstance(node, WhileNode):
            code = f"while {self.generate(node.condition)}:\n"
            body = self.indent_block(self.generate(node.body))
            code += body
            return code
        elif isinstance(node, IndexNode):
            return f"{self.generate(node.collection)}[{self.generate(node.index)}]"
        elif isinstance(node, RangeNode):
            return f"range({self.generate(node.start)}, {self.generate(node.end)})"
        elif isinstance(node, ForNode):
            code = f"for {node.var_name} in {self.generate(node.iterable)}:\n"
            body = self.indent_block(self.generate(node.body))
            code += body
            return code
        elif isinstance(node, CastNode):
            return f"{node.cast_type}({self.generate(node.value)})"
        
        elif isinstance(node, ImportNode):
            return f"import {node.name.value}"
    
        elif isinstance(node, BoolNode):
            return "True" if node.value else "False"
        else:
            raise RuntimeError(f"Unknown node type: {node}")

    @staticmethod
    def indent_block(code, indent=4):
        spaces = " " * indent
        return "\n".join(spaces + line if line.strip() else line for line in code.split("\n"))
