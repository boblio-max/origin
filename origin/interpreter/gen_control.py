"""Control-flow codegen branches."""
from ..classes import *


class ControlMixin:
    def _generate_core(self, node):
        """The actual generation logic, separated from the line tracking wrapper."""
        if isinstance(node, IfNode):
            code = f"if {self.generate(node.condition)}:\n"
            code += self.indent_block(self.generate(node.then_body))
            for elif_node in node.elif_nodes:
                code += f"\nelif {self.generate(elif_node.condition)}:\n"
                code += self.indent_block(self.generate(elif_node.then_body))
            if node.else_body:
                code += "\nelse:\n"
                code += self.indent_block(self.generate(node.else_body))
            return code

        elif isinstance(node, WhileNode):
            code = f"while {self.generate(node.condition)}:\n"
            code += self.indent_block(self.generate(node.body))
            return code

        elif isinstance(node, ForNode):
            code = f"for {self.generate(node.var)} in {self.generate(node.iterable)}:\n"
            code += self.indent_block(self.generate(node.body))
            return code

        elif isinstance(node, TryNode):
            code = "try:\n"
            code += self.indent_block(self.generate(node.try_body))
            for exc in node.except_body:
                code += "\nexcept Exception:\n"
                code += self.indent_block(self.generate(exc))
            if node.else_body:
                code += "\nelse:\n"
                code += self.indent_block(self.generate(node.else_body))
            return code

        return super()._generate_core(node)
