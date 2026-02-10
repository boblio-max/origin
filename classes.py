class ASTNode:
    pass



class NumberNode(ASTNode):
    def __init__(self, value):
        self.value = value
    def __repr__(self):
        return f"NumberNode({self.value})"


class StringNode(ASTNode):
    def __init__(self, value):
        self.value = value
    def __repr__(self):
        return f"StringNode({self.value!r})"


class VarNode(ASTNode):
    def __init__(self, name):
        self.name = name
    def __repr__(self):
        return f"VarNode({self.name})"
    
class TryNode(ASTNode): 
    def __init__(self, try_block, except_blocks=None, else_block=None):
        self.try_block = try_block
        self.except_blocks = except_blocks or []
        self.else_block = else_block


    def __repr__(self):
        return f"TryNode({self.try_block}, {self.except_blocks}, {self.else_block})"
    
class ErrorNode(ASTNode):
    def __init__(self, message):
        self.message = message
    def __repr__(self):
        return f"ErrorNode({self.message})"
class CastNode(ASTNode):
    def __init__(self, cast_type, value):
        self.cast_type = cast_type
        self.value = value
class RangeNode(ASTNode):
    def __init__(self, start, end):
        self.start = start
        self.end = end
    def __repr__(self):
        return f"RangeNode({self.start}, {self.end})"
class ListNode(ASTNode):
    def __init__(self, elements):
        self.elements = elements
    def __repr__(self):
        return f"ListNode({self.elements})"
    
class IndexNode(ASTNode):
    def __init__(self, collection, index):
        self.collection = collection
        self.index = index

class IndexAssignNode(ASTNode):
    def __init__(self, collection, index, value):
        self.collection = collection
        self.index = index
        self.value = value

class BinOpNode(ASTNode):
    def __init__(self, left, op, right):
        self.left, self.op, self.right = left, op, right
    def __repr__(self):
        return f"BinOpNode({self.left}, {self.op!r}, {self.right})"
    
class CallerNode(ASTNode):
    def __init__(self, callee, args):
        self.callee = callee
        self.args = args
    def __repr__(self):
        return f"CallerNode({self.callee}, {self.args})"

class listCallNode(ASTNode):
    def __init__(self, list_node, pos):
        self.list_node = list_node
        self.pos = pos
    def __repr__(self):
        return f"ListCallNode({self.list_node}, {self.pos})"
class AssignNode(ASTNode):
    def __init__(self, name, value):
        self.name, self.value = name, value
    def __repr__(self):
        return f"AssignNode({self.name}, {self.value})"

class RandNumNode(ASTNode):
    def __init__(self, start, end):
        self.start = start
        self.end = end
    def __repr__(self):
        return f"RandNumNode({self.start}, {self.end})"
class ConstAssignNode(ASTNode):
    def __init__(self, name, value):
        self.name, self.value = name, value
    def __repr__(self):
        return f"ConstAssignNode({self.name}, {self.value})"

class PrintNode(ASTNode):
    def __init__(self, expr):
        self.expr = expr
    def __repr__(self):
        return f"PrintNode({self.expr})"


class InputNode(ASTNode):
    def __init__(self, prompt=None):
        self.prompt = prompt
    def __repr__(self):
        return f"InputNode({self.prompt})"
    
class ClassNode(ASTNode):
    def __init__(self, name, fields, methods):
        self.name = name
        self.fields = fields
        self.methods=methods
    def __repr__(self):
        return f"ClassNode({self.name}, {self.fields},{self.methods})"
    
class InstanceNode(ASTNode):
    def __init__(self, class_node):
        self.class_node = class_node
        self.fields = {field: None for field in class_node.fields} 
    def __repr__(self):
        return f"InstanceNode({self.class_node}, {self.fields})"
    
    

class LenNode(ASTNode):
    def __init__(self, value):
        self.value = value 
    def __repr__(self):
        return f"LenNode({self.value})"
class BlockNode(ASTNode):
    def __init__(self, statements):
        self.statements = statements
    def __repr__(self):
        return f"BlockNode({self.statements})"

class ImportNode:
    def __init__(self, name_token):
        self.name = name_token  

    def __repr__(self):
        return f"ImportNode({self.name})"

class ImportFromNode:
    def __init__(self, name, library):
        self.name = name
        self.lib = library
    
    def __repr__(self):
        return f"ImportFromNode({self.name}, {self.lib})"
class SetNode:
    def __init__(self,name, num,type_, params):
        self.name = name
        self.params = params
        self.type_ = type_
        self.num = num
    def __repr__(self):
        return f"SetNode({self.name}, {self.num},{self.type_},{self.params})"
class ImportAsNode:
    def __init__(self, name, newName):
        self.name = name
        self.nName = newName
    
    def __repr__(self):
        return f"ImportFromNode({self.name}, {self.nName})"
    
class FuncNode:
    def __init__(self, name, params, body):
        self.name = name
        self.params = params
        self.body = body
    def __repr__(self):
        return f"FuncNode({self.name},{self.params}, {self.body})"
    
class IfNode(ASTNode):
    def __init__(self, condition, then_body, elif_nodes=None, else_body=None):
        self.condition = condition
        self.then_body = then_body
        self.elif_nodes = elif_nodes or []
        self.else_body = else_body
    def __repr__(self):
        return f"IfNode({self.condition}, {self.then_body},{self.elif_nodes} {self.else_body})"

class ElifNode(ASTNode):
    def __init__(self, condition, then_body, else_body=None):
        self.condition = condition
        self.then_body = then_body
        self.else_body = else_body
    def __repr__(self):
        return f"ElifNode({self.condition}, {self.then_body}, {self.else_body})"

class WhileNode(ASTNode):
    def __init__(self, condition, body):
        self.condition = condition
        self.body = body
    def __repr__(self):
        return f"WhileNode({self.condition}, {self.body})"


class ForNode(ASTNode):
    def __init__(self, var_name, iterable, body):
        self.var_name = var_name
        self.iterable = iterable
        self.body = body
    def __repr__(self):
        return f"ForNode({self.var_name}, {self.iterable}, {self.body})"

class UnaryOpNode(ASTNode):
    def __init__(self, op, node):
        self.op, self.node = op, node
    def __repr__(self):
        return f"UnaryOpNode({self.op!r}, {self.node})"
    
class ProgramNode(ASTNode):
    def __init__(self, statements):
        self.statements = statements
    def __repr__(self):
        return f"ProgramNode({self.statements})"

class BoolNode(ASTNode):
    def __init__(self, value: bool):
        self.value = value
    def __repr__(self):
        return f"BoolNode({self.value})"

class CompoundAssignNode(ASTNode):
    def __init__(self, name, op, value):
        self.name = name
        self.op = op
        self.value = value
    def __repr__(self):
        return f"CompoundAssignNode({self.name}, {self.op!r}, {self.value})"

class LogicOpNode(ASTNode):
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right
    def __repr__(self):
        return f"LogicOpNode({self.left}, {self.op!r}, {self.right})"

class NotNode(ASTNode):
    def __init__(self, expr):
        self.expr = expr
    def __repr__(self):
        return f"NotNode({self.expr})"

class CallNode(ASTNode):
    def __init__(self, func_name, arg):
        self.func_name = func_name
        self.arg = arg
    def __repr__(self):
        return f"CallNode({self.func_name}, {self.arg})"

class SpecialOpNode(ASTNode):
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right
    def __repr__(self):
        return f"SpecialOpNode({self.left}, {self.op!r}, {self.right})"

class BreakNode(ASTNode):
    def __repr__(self):
        return "BreakNode()"

class ContinueNode(ASTNode):
    def __repr__(self):
        return "ContinueNode()"

class ReturnNode(ASTNode):
    def __init__(self, value):
        self.value = value
    def __repr__(self):
        return f"ReturnNode({self.value})"

class YieldNode(ASTNode):
    def __init__(self, value):
        self.value = value
    def __repr__(self):
        return f"YieldNode({self.value})"
