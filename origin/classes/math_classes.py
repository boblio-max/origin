from .base_classes import *

class SqrtNode(ASTNode):
    """Square root operation."""
    def __init__(self, value):
        super().__init__()
        self.value = value
    def __repr__(self):
        return f"SqrtNode({self.value})"

class MathNode(ASTNode):
    """Unary math operation (abs, floor, ceil) evaluated at runtime."""
    def __init__(self, func, value):
        super().__init__()
        self.func = func
        self.value = value
    def __repr__(self):
        return f"MathNode({self.func!r}, {self.value})"

class RandNumNode(ASTNode):
    """Random number generation."""
    def __init__(self, start, end):
        super().__init__()
        self.start = start
        self.end = end
    def __repr__(self):
        return f"RandNumNode({self.start}, {self.end})"

class LenNode(ASTNode):
    """Collection length."""
    def __init__(self, value):
        super().__init__()
        self.value = value 
    def __repr__(self):
        return f"LenNode({self.value})"

class CastNode(ASTNode):
    """Type casting."""
    def __init__(self, cast_type, value):
        super().__init__()
        self.cast_type = cast_type
        self.value = value
        self.type = cast_type
    def __repr__(self):
        return f"CastNode({self.cast_type}, {self.value})"
