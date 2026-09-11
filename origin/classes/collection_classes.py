from .base_classes import *

class ListNode(ASTNode):
    """List literal."""
    def __init__(self, elements):
        super().__init__()
        self.elements = elements
    def __repr__(self):
        return f"ListNode({self.elements})"

class TupleNode(ASTNode):
    """Tuple literal."""
    def __init__(self, elements):
        super().__init__()
        self.elements = elements
    def __repr__(self):
        return f"TupleNode({self.elements})"

class DictNode(ASTNode):
    """Dictionary literal."""
    def __init__(self, elements):
        super().__init__()
        self.elements = elements
    def __repr__(self):
        return f"DictNode({self.elements})"

class IndexNode(ASTNode):
    """Index access (list[index])."""
    def __init__(self, collection, index):
        super().__init__()
        self.collection = collection
        self.index = index
    def __repr__(self):
        return f"IndexNode({self.collection}, {self.index})"

class ListCallNode(ASTNode):
    """Special API calls for lists."""
    def __init__(self, list_node, pos):
        super().__init__()
        self.list_node = list_node
        self.pos = pos
    def __repr__(self):
        return f"ListCallNode({self.list_node}, {self.pos})"

class RangeNode(ASTNode):
    """Numeric range generator."""
    def __init__(self, start, end, step=None):
        super().__init__()
        self.start = start
        self.end = end
        self.step = step
    def __repr__(self):
        return f"RangeNode({self.start}, {self.end},{self.step})"
