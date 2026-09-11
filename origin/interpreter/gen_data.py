"""Literal/collection/data codegen branches."""
from ..classes import *


class DataMixin:
    def _generate_core(self, node):
        """The actual generation logic, separated from the line tracking wrapper."""
        if isinstance(node, PrintNode):
            # Support multiple print arguments (TupleNode or ListNode) without printing a tuple
            expr = node.expr
            if isinstance(expr, TupleNode) or isinstance(expr, ListNode):
                args = ", ".join(self.generate(e) for e in expr.elements)
                return f"print({args})"
            return f"print({self.generate(expr)})"

        elif isinstance(node, NumberNode):
            return str(node.value)

        elif isinstance(node, StringNode):
            return repr(node.value)

        elif isinstance(node, FormattedStringNode):
            # Emit concatenation of parts, converting expressions to str()
            parts = []
            for p in node.parts:
                if isinstance(p, StringNode):
                    parts.append(repr(p.value))
                else:
                    parts.append(f"str({self.generate(p)})")
            if not parts:
                return "''"
            return "(" + " + ".join(parts) + ")"

        elif isinstance(node, BoolNode):
            return str(node.value)

        elif isinstance(node, NoneNode):
            return "None"

        elif isinstance(node, VarNode):
            return node.name

        elif isinstance(node, ListNode):
            return f"[{', '.join(self.generate(e) for e in node.elements)}]"

        elif isinstance(node, TupleNode):
            return f"({', '.join(self.generate(e) for e in node.elements)})"

        elif isinstance(node, DictNode):
            items = ", ".join(f"{self.generate(k)}: {self.generate(v)}" for k, v in node.elements.items())
            return f"{{{items}}}"

        elif isinstance(node, IndexNode):
            return f"{self.generate(node.collection)}[{self.generate(node.index)}]"

        elif isinstance(node, IndexAssignNode):
            return f"{self.generate(node.collection)}[{self.generate(node.index)}] = {self.generate(node.value)}"

        elif isinstance(node, ImuNode):
            return f"{node.name}({node.address})"
        
        elif isinstance(node, ImuFromNode):
            return f"{node.name}.get_{node.value}()"
        
        return super()._generate_core(node)
