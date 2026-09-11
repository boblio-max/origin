"""Base interpreter: state, analysis passes, generate() wrapper."""
from ..classes import *


class BaseInterpreter:
    """Generate Python source from the AST (base)."""

    def __init__(self):
        self.variable_types = {}
        # Internal tracking (optional, could be moved to a flag)
        self.CONST_VARS = {}
        self.imports = []
        self.classes = {}
        self.original_imports = {}
        # Track whether we're generating code inside a class body
        self._class_depth = 0
        self._module_vars = set()

    def _collect_module_vars(self, node):
        """First pass: collect all variable names declared at module level."""
        for stmt in node.statements:
            if isinstance(stmt, MultAssignNode):
                names = stmt.names if isinstance(stmt.names, list) else [stmt.names]
                for n in names:
                    self._module_vars.add(n)
            elif isinstance(stmt, (AssignNode, ConstAssignNode)) and not isinstance(stmt.value, FuncNode):
                self._module_vars.add(stmt.name)

    def _get_global_vars_in_func(self, node):
        """Find variables inside a function body that shadow module-level vars."""
        if node is None:
            return set()
        result = set()
        if isinstance(node, BlockNode):
            for stmt in node.statements:
                result |= self._get_global_vars_in_func(stmt)
        elif isinstance(node, AssignNode):
            if node.name in self._module_vars:
                result.add(node.name)
        elif isinstance(node, MultAssignNode):
            names = node.names if isinstance(node.names, list) else [node.names]
            for n in names:
                if n in self._module_vars:
                    result.add(n)
        elif isinstance(node, FuncNode):
            result |= self._get_global_vars_in_func(node.body)
        elif isinstance(node, IfNode):
            result |= self._get_global_vars_in_func(node.then_body)
            for elif_n in node.elif_nodes:
                result |= self._get_global_vars_in_func(elif_n.then_body)
            if node.else_body:
                result |= self._get_global_vars_in_func(node.else_body)
        elif isinstance(node, WhileNode):
            result |= self._get_global_vars_in_func(node.body)
        elif isinstance(node, ForNode):
            result |= self._get_global_vars_in_func(node.body)
        elif isinstance(node, TryNode):
            result |= self._get_global_vars_in_func(node.try_body)
            for exc in node.except_body:
                result |= self._get_global_vars_in_func(exc)
            if node.else_body:
                result |= self._get_global_vars_in_func(node.else_body)
        elif isinstance(node, ParallelNode):
            result |= self._get_global_vars_in_func(node.body)
        return result
    def get_type(self, node):
        """Infer the type of an AST node."""
        if hasattr(node, 'type') and node.type is not None:
            return node.type
        if isinstance(node, VarNode):
            return self.variable_types.get(node.name)
        if isinstance(node, BinOpNode):
            left_type = self.get_type(node.left)
            right_type = self.get_type(node.right)
            if left_type == "float" or right_type == "float":
                return "float"
            return left_type
        return None

    def generate(self, node):
        """Recursively translate an AST node into Python source text."""
        if node is None:
            return ""

        # Inject line tracking for statements (nodes that have a line attribute)
        line_marker = ""
        if hasattr(node, 'line') and node.line is not None:
            # We use a global to track the current line so it survives inside functions
            line_marker = f"globals()['_origin_runtime_line'] = {node.line}\n"

        if isinstance(node, ProgramNode):
            self._collect_module_vars(node)
            return "\n".join(self.generate(stmt) for stmt in node.statements)

        elif isinstance(node, BlockNode):
            return "\n".join(self.generate(stmt) for stmt in node.statements)
            
        # Add the line marker to the generated code for other nodes
        res = self._generate_core(node)
        return line_marker + res

    def indent_block(self, code, indent=4):
        if not code: return " " * indent + "pass"
        spaces = " " * indent
        return "\n".join(spaces + line if line.strip() else line for line in code.split("\n"))
