"""Function/class/call codegen branches."""
from ..classes import *


class FuncMixin:
    def _generate_core(self, node):
        """The actual generation logic, separated from the line tracking wrapper."""
        if isinstance(node, FuncNode):
            params = []
            for p in node.params:
                ptype = (node.param_types or {}).get(p)
                if ptype in ("int", "float", "str", "bool"):
                    params.append(f"{p}: {ptype}")
                else:
                    params.append(p)
            params = ", ".join(params) if params else ""
            # If inside a class, ensure 'self' is the first parameter (unless already declared)
            if getattr(self, "_class_depth", 0) > 0 and (not node.params or node.params[0] != "self"):
                params = "self" if not params else "self, " + params
            code = f"def {node.name}({params}):\n"
            body_code = self.generate(node.body) or "pass"
            global_vars = self._get_global_vars_in_func(node.body)
            if global_vars:
                global_line = "global " + ", ".join(sorted(global_vars)) + "\n"
                body_code = global_line + body_code
            code += self.indent_block(body_code)
            return code

        elif isinstance(node, ClassNode):
            # Make fields optional by defaulting to None, with type annotations when given
            params = []
            for f in node.fields:
                ftype = (node.field_types or {}).get(f)
                if ftype in ("int", "float", "str", "bool"):
                    params.append(f"{f}: {ftype} = None")
                else:
                    params.append(f"{f}=None")
            params = ", ".join(params)
            code = f"class {node.name}:\n"
            # Body of __init__ must be indented further (8 spaces total)
            init_body = "\n".join(f"        self.{f} = {f}" for f in node.fields) or "        pass"
            init_sig = ("self, " + params) if params else "self"
            code += f"    def __init__({init_sig}):\n{init_body}\n"
            # Generate class body with class-depth tracking so methods get 'self'
            self._class_depth += 1
            body_code = self.generate(node.body)
            self._class_depth -= 1
            code += self.indent_block(body_code)
            return code

        
        elif isinstance(node, CallNode):
            args = ", ".join(self.generate(arg) for arg in node.args)
            return f"{self.generate(node.callee)}({args})"

        elif isinstance(node, AttributeNode):
            return f"{self.generate(node.obj)}.{node.attr}"

        elif isinstance(node, AttributeAssignNode):
            return f"{self.generate(node.obj)}.{node.attr} = {self.generate(node.value)}"

        return super()._generate_core(node)
