from .base_classes import *

class FuncNode(ASTNode):
    """Function definition."""
    def __init__(self, name, params, body, param_types=None):
        super().__init__()
        self.name = name
        self.params = params
        self.body = body
        self.param_types = param_types or {}
    def __repr__(self):
        return f"FuncNode({self.name}, {self.params}, {self.param_types}, {self.body})"

class ClassNode(ASTNode):
    """Class definition."""
    def __init__(self, name, fields, body, field_types=None):
        super().__init__()
        self.name = name
        self.fields = fields
        self.body = body
        self.field_types = field_types or {}
    def __repr__(self):
        return f"ClassNode({self.name}, {self.fields}, {self.field_types}, {self.body})"

class CallNode(ASTNode):
    """Function or method call."""
    def __init__(self, callee, args):
        super().__init__()
        self.callee = callee
        self.args = args
    def __repr__(self):
        return f"CallNode({self.callee}, {self.args})"

class AttributeNode(ASTNode):
    """Attribute or method access (obj.attr)."""
    def __init__(self, obj, attr):
        super().__init__()
        self.obj = obj
        self.attr = attr
    def __repr__(self):
        return f"AttributeNode({self.obj}, {self.attr})"
