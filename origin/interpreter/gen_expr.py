"""Expression/assignment codegen branches."""
import os
import sys
import subprocess
from ..classes import *


class ExprMixin:
    def _generate_core(self, node):
        """The actual generation logic, separated from the line tracking wrapper."""
        if isinstance(node, ExecNode):
            # Fragile but kept for compatibility - improved to use absolute paths
            runner_path = os.path.join(os.path.dirname(__file__), "runner.py")
            temp_file = "temp_exec.py"
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(node.code)
            subprocess.run([sys.executable, runner_path, temp_file])
            return ""

        if isinstance(node, PyNode):
            return node.code

        elif isinstance(node, AssignNode):
            if isinstance(node.value, ImuNode):
                return f"from {node.value.name} import {node.value.name}\n{node.name} = {self.generate(node.value)}"

            if node.name in self.CONST_VARS:
                raise RuntimeError(f"Cannot reassign constant '{node.name}'")

            # Infer the type of the assigned value
            val_type = self.get_type(node.value)

            # If an explicit type annotation exists and differs from inferred, attempt to cast
            if node.type and val_type and node.type != val_type and node.type != "any" and val_type != "any":
                # Simple casting based on annotation name (int, float, str, bool)
                try:
                    # Use the cast function directly in generated code
                    casted_expr = f"{node.type}({self.generate(node.value)})"
                    assign_code = f"{node.name} = {casted_expr}"
                except Exception:
                    # If casting fails, fall back to using the inferred value without casting
                    assign_code = f"{node.name} = {self.generate(node.value)}"
                    node.type = val_type
            else:
                assign_code = f"{node.name} = {self.generate(node.value)}"

            # Record variable type information for later use
            if node.type:
                self.variable_types[node.name] = node.type
            elif val_type:
                self.variable_types[node.name] = val_type

            return assign_code

        elif isinstance(node, MultAssignNode):
            names = node.names if isinstance(node.names, list) else [node.names]
            values = node.value if isinstance(node.value, list) else [node.value]
            annotations = node.type if isinstance(node.type, list) else [node.type]
            if len(names) != len(values):
                raise RuntimeError("Type Mismatch: number of names and values in multi-assignment must match")
            for name in names:
                if name in self.CONST_VARS:
                    raise RuntimeError(f"Cannot reassign constant '{name}'")
            value_codes = []
            for i, name in enumerate(names):
                value = values[i]
                val_type = self.get_type(value)
                annotation = annotations[i] if i < len(annotations) else None
                code = self.generate(value)
                if annotation and val_type and annotation != val_type and annotation != "any" and val_type != "any":
                    code = f"{annotation}({code})"
                if annotation:
                    self.variable_types[name] = annotation
                elif val_type:
                    self.variable_types[name] = val_type
                value_codes.append(code)
            return ", ".join(names) + " = " + ", ".join(value_codes)

        elif isinstance(node, ConstAssignNode):
            if node.name in self.CONST_VARS:
                raise RuntimeError(f"Cannot reassign constant '{node.name}'")
            val_str = self.generate(node.value)
            val_type = self.get_type(node.value)
            if node.type and val_type and node.type != val_type and node.type != "any" and val_type != "any":
                raise TypeError(f"Type Mismatch: {node.name} is {node.type} but got {val_type}")
            if node.type:
                self.variable_types[node.name] = node.type
            elif val_type:
                self.variable_types[node.name] = val_type
            self.CONST_VARS[node.name] = val_str
            return f"{node.name} = {val_str}"

        elif isinstance(node, CompoundAssignNode):
            return f"{node.name} {node.op} {self.generate(node.value)}"

        elif isinstance(node, BinOpNode):
            if node.op == "+":
                # Smart Concatenation: if either side is a string, treat as string concat
                left = self.generate(node.left)
                right = self.generate(node.right)
                return f"(str({left}) + str({right})) if isinstance({left}, str) or isinstance({right}, str) else ({left} + {right})"
            return f"({self.generate(node.left)} {node.op} {self.generate(node.right)})"

        elif isinstance(node, UnaryOpNode):
            if node.op in ("not", "!"):
                return f"(not {self.generate(node.node)})"
            return f"({node.op}{self.generate(node.node)})"

        elif isinstance(node, LogicOpNode):
            # Map Origin logic operators to Python
            op_map = {"and": "and", "or": "or", "&&": "and", "||": "or"}
            py_op = op_map.get(node.op, node.op)
            return f"({self.generate(node.left)} {py_op} {self.generate(node.right)})"

        return super()._generate_core(node)
