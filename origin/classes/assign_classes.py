from .base_classes import * 

class AssignNode(ASTNode):
    """Assignment operation (let)."""
    def __init__(self, name, value, _type=None):
        super().__init__()
        self.name, self.value, self.type = name, value, _type
    def __repr__(self):
        return f"AssignNode({self.name}, {self.value}, {self.type})"
    
class ConstAssignNode(ASTNode):
    """Constant declaration (const)."""
    def __init__(self, name, value, _type=None):
        super().__init__()
        self.name, self.value, self.type = name, value, _type
    def __repr__(self):
        return f"ConstAssignNode({self.name}, {self.value}, {self.type})"
    
class MultAssignNode(ASTNode):
    def __init__(self, names, value, _type=None):
        super().__init__()
        self.names, self.value, self.type = names, value, _type
    def __repr__(self):
        return f"MultAssignNode({self.names}, {self.value}, {self.type})"
    
class CompoundAssignNode(ASTNode):
    """Compound assignment (+=, -=, etc.)."""
    def __init__(self, name, op, value):
        super().__init__()
        self.name = name
        self.op = op
        self.value = value
    def __repr__(self):
        return f"CompoundAssignNode({self.name}, {self.op!r}, {self.value})"

class AttributeAssignNode(ASTNode):
    """Assignment to an attribute (obj.attr = value)."""
    def __init__(self, obj, attr, value):
        super().__init__()
        self.obj = obj
        self.attr = attr
        self.value = value
    def __repr__(self):
        return f"AttributeAssignNode({self.obj}, {self.attr}, {self.value})"

class IndexAssignNode(ASTNode):
    """Assignment to an index (list[index] = value)."""
    def __init__(self, collection, index, value):
        super().__init__()
        self.collection = collection
        self.index = index
        self.value = value
    def __repr__(self):
        return f"IndexAssignNode({self.collection}, {self.index}, {self.value})"
