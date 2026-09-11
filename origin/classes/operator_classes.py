from .base_classes import *

class BinOpNode(ASTNode):
    """Binary operation (+, -, *, etc.)."""
    def __init__(self, left, op, right):
        super().__init__()
        self.left, self.op, self.right = left, op, right
        self.type = None 
    def __repr__(self):
        return f"BinOpNode({self.left}, {self.op!r}, {self.right})"

class UnaryOpNode(ASTNode):
    """Unary operation (negation, not)."""
    def __init__(self, op, node):
        super().__init__()
        self.op, self.node = op, node
        self.type = None
    def __repr__(self):
        return f"UnaryOpNode({self.op!r}, {self.node})"

class LogicOpNode(ASTNode):
    """Logical operation (AND, OR)."""
    def __init__(self, left, op, right):
        super().__init__()
        self.left = left
        self.op = op
        self.right = right
    def __repr__(self):
        return f"LogicOpNode({self.left}, {self.op!r}, {self.right})"

class SpecialOpNode(ASTNode):
    """Special internal operators."""
    def __init__(self, type, left, op, right):
        super().__init__()
        self.left = left
        self.op = op
        self.right = right
    def __repr__(self):
        return f"SpecialOpNode({self.left}, {self.op!r}, {self.right})"

class PipeNode(ASTNode):
    """Pipeline operation (value -> function)."""
    def __init__(self, value, func):
        super().__init__()
        self.value = value   # left side (the data)
        self.func = func     # right side (the function to call)
    def __repr__(self):
        return f"PipeNode({self.value}, {self.func})"

class LambdaNode(ASTNode):
    def __init__(self, var, func):
        super().__init__()
        self.var = var
        self.func = func
    def __repr__(self):
        return f"LambdaNode({self.var}, {self.func})"
