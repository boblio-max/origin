from .base_classes import *

class NumberNode(ASTNode):
    """Numeric literal (integer or float)."""
    def __init__(self, value, _type):
        super().__init__()
        self.value = value
        self.type = _type
    def __repr__(self):
        return f"NumberNode({self.value}, {self.type})"
    
class StringNode(ASTNode):
    """String literal."""
    def __init__(self, value, _type="str"):
        super().__init__()
        self.value = value
        self.type = _type
    def __repr__(self): 
        return f"StringNode({self.value!r}, {self.type})"

class BoolNode(ASTNode):
    """Boolean literal (True/False)."""
    def __init__(self, value: bool):
        super().__init__()
        self.value = value
        self.type = "bool"
    def __repr__(self):
        return f"BoolNode({self.value})"
    
class NoneNode(ASTNode):
    """None literal."""
    def __init__(self):
        super().__init__()
        self.type = "none"
    def __repr__(self):
        return "NoneNode()"

class FormattedStringNode(ASTNode):
    """Formatted string with interleaved text and expression parts."""
    def __init__(self, parts):
        super().__init__()
        self.parts = parts  # list of StringNode or expression nodes
    def __repr__(self):
        return f"FormattedStringNode({self.parts})"
    
class VarNode(ASTNode):
    """Variable reference."""
    def __init__(self, name, _type=None):
        super().__init__()
        self.name = name
        self.type = _type
    def __repr__(self):
        return f"VarNode({self.name}, {self.type})"
