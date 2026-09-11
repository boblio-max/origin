from .base_classes import *

class PassNode(ASTNode):
    """Pass statement."""
    def __init__(self):
        super().__init__()
    def __repr__(self):
        return "PassNode()"

class IfNode(ASTNode):
    """Control flow (if/elif/else)."""
    def __init__(self, condition, then_body, elif_nodes=None, else_body=None):
        super().__init__()
        self.condition = condition
        self.then_body = then_body
        self.elif_nodes = elif_nodes or []
        self.else_body = else_body
    def __repr__(self):
        return f"IfNode({self.condition}, {self.then_body}, {self.elif_nodes}, {self.else_body})"

class ElifNode(ASTNode):
    """Subsequent conditional in an if-else block."""
    def __init__(self, condition, then_body):
        super().__init__()
        self.condition = condition
        self.then_body = then_body
    def __repr__(self):
        return f"ElifNode({self.condition}, {self.then_body})"

class WhileNode(ASTNode):
    """While loop."""
    def __init__(self, condition, body):
        super().__init__()
        self.condition = condition
        self.body = body
    def __repr__(self):
        return f"WhileNode({self.condition}, {self.body})"

class ForNode(ASTNode):
    """For-each loop. `var` may be a single `VarNode` or a `TupleNode`/`ListNode` of `VarNode`s for unpacking."""
    def __init__(self, var, iterable, body):
        super().__init__()
        self.var = var
        self.iterable = iterable
        self.body = body
    def __repr__(self):
        return f"ForNode({self.var}, {self.iterable}, {self.body})"

class TryNode(ASTNode): 
    """Try-except block."""
    def __init__(self, try_body, except_body=None, else_body=None):
        super().__init__()
        self.try_body = try_body
        self.except_body = except_body or []
        self.else_body = else_body
    def __repr__(self):
        return f"TryNode({self.try_body}, {self.except_body}, {self.else_body})"

class BreakNode(ASTNode):
    """Loop break."""
    def __repr__(self):
        return "BreakNode()"

class ContinueNode(ASTNode):
    """Loop continue."""
    def __repr__(self):
        return "ContinueNode()"

class ReturnNode(ASTNode):
    """Function return."""
    def __init__(self, value):
        super().__init__()
        self.value = value
    def __repr__(self):
        return f"ReturnNode({self.value})"

class YieldNode(ASTNode):
    """Generator yield."""
    def __init__(self, value):
        super().__init__()
        self.value = value
    def __repr__(self):
        return f"YieldNode({self.value})"

class MatchNode(ASTNode):
    """Pattern matching (match/case)."""
    def __init__(self, value, cases):
        super().__init__()
        self.value = value
        self.cases = cases  # list of (pattern, body) tuples
    def __repr__(self):
        return f"MatchNode({self.value}, {self.cases})"
