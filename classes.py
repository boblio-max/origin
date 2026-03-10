"""AST node definitions

This module defines the Abstract Syntax Tree (AST) node classes used by the
parser and interpreter. Each node class represents a single syntactic
construct (literal, expression, statement, etc.) and is intentionally small
and data-focused so the interpreter can pattern-match on types and fields.
"""

import os 

class ASTNode:
    """Abstract base type for AST nodes.

    Subclass instances are plain data containers consumed by the interpreter
    and code-generation routines. This base class is intentionally empty and
    serves as a type marker.
    """
    pass

class ExecNode(ASTNode):
    """Represents an execution of an embedded string evaluation/command."""
    def __init__(self, code):
        self.code = code
    def __repr__(self):
        return f"ExecNode({self.code!r})"

class NumberNode(ASTNode):
    """Represents a numeric literal (integer or float)."""
    def __init__(self, value, _type):
        self.value = value
        self.type = _type
    def __repr__(self):
        return f"NumberNode({self.value}, {self.type})"

class StringNode(ASTNode):
    """Represents a string literal."""
    def __init__(self, value, _type="str"):
        self.value = value
        self.type = _type
    def __repr__(self): 
        return f"StringNode({self.value!r}, {self.type})"

class SqrtNode(ASTNode):
    """Represents a square root operation."""
    def __init__(self, value):
        self.value = value
    def __repr__(self):
        return f"SqrtNode({self.value})"

class VarNode(ASTNode):
    """Represents a variable reference."""
    def __init__(self, name, _type=None):
        self.name = name
        self.type = _type
    def __repr__(self):
        return f"VarNode({self.name}, {self.type})"
    
class TryNode(ASTNode): 
    """Represents a try-except error handling block."""
    def __init__(self, try_block, except_blocks=None, else_block=None):
        self.try_block = try_block
        self.except_blocks = except_blocks or []
        self.else_block = else_block

    def __repr__(self):
        return f"TryNode({self.try_block}, {self.except_blocks}, {self.else_block})"
    
class openNode(ASTNode): 
    def __init__(self, name, path, _type):
        self.name = name
        self.path = path
        self.type = _type
    def __repr__(self):
        return f"openNode({self.name}, {self.path}, {self.type})"
class ErrorNode(ASTNode):
    """Represents a generic evaluation error or syntax error."""
    def __init__(self, message):
        self.message = message
    def __repr__(self):
        return f"ErrorNode({self.message})"
    
class CastNode(ASTNode):
    """Represents a type casting operation (e.g., to int, float, str)."""
    def __init__(self, cast_type, value):
        self.cast_type = cast_type
        self.value = value
        self.type = cast_type
        
class RangeNode(ASTNode):
    """Represents a numeric generator range."""
    def __init__(self, start, end):
        self.start = start
        self.end = end
    def __repr__(self):
        return f"RangeNode({self.start}, {self.end})"
    
class ListNode(ASTNode):
    """Represents an inline declaration of a list."""
    def __init__(self, elements):
        self.elements = elements
    def __repr__(self):
        return f"ListNode({self.elements})"
    
class DictNode(ASTNode):
    """Represents an inline declaration of a dictionary."""
    def __init__(self, elements):
        self.elements = elements
    def __repr__(self):
        return f"DictNode({self.elements})"

class NoneNode(ASTNode):
    """Represents the None literal."""
    def __init__(self):
        self.type = "none"
    def __repr__(self):
        return "NoneNode()"

class PassNode(ASTNode):
    """Represents the pass statement."""
    def __init__(self):
        pass
    def __repr__(self):
        return "PassNode()"

class IndexNode(ASTNode):
    """Represents an index access operation on a collection (e.g., list[index])."""
    def __init__(self, collection, index):
        self.collection = collection
        self.index = index

class IndexAssignNode(ASTNode):
    """Represents an assignment to a specific index of a collection."""
    def __init__(self, collection, index, value):
        self.collection = collection
        self.index = index
        self.value = value

class BinOpNode(ASTNode):
    """Represents a binary operation between two nodes (e.g., +, -, *, /)."""
    def __init__(self, left, op, right):
        self.left, self.op, self.right = left, op, right
        self.type = None # Inferred at runtime or by a type checker
    def __repr__(self):
        return f"BinOpNode({self.left}, {self.op!r}, {self.right})"
    
class AttributeNode(ASTNode):
    """Represents attribute or method access on an object."""
    def __init__(self, obj, attr):
        self.obj = obj
        self.attr = attr
    def __repr__(self):
        return f"AttributeNode({self.obj}, {self.attr})"
    
class CallerNode(ASTNode):
    """Represents a function call execution."""
    def __init__(self, callee, args):
        self.callee = callee
        self.args = args
    def __repr__(self):
        return f"CallerNode({self.callee}, {self.args})"

class listCallNode(ASTNode):
    """Represents standard API calls mapped directly to list implementations."""
    def __init__(self, list_node, pos):
        self.list_node = list_node
        self.pos = pos
    def __repr__(self):
        return f"ListCallNode({self.list_node}, {self.pos})"

class AssignNode(ASTNode):
    """Represents an assignment operation binding a value to a variable name."""
    def __init__(self, name, value, _type):
        self.name, self.value, self.type = name, value, _type
    def __repr__(self):
        return f"AssignNode({self.name}, {self.value}, {self.type})"

class RandNumNode(ASTNode):
    """Represents a random number generation query."""
    def __init__(self, start, end):
        self.start = start
        self.end = end
    def __repr__(self):
        return f"RandNumNode({self.start}, {self.end})"

class ConstAssignNode(ASTNode):
    """Represents a constant variable declaration and assignment."""
    def __init__(self, name, value):
        self.name, self.value = name, value
    def __repr__(self):
        return f"ConstAssignNode({self.name}, {self.value})"

class PrintNode(ASTNode):
    """Represents a console print statement."""
    def __init__(self, expr, _type):
        self.expr = expr
        self.type = _type
    def __repr__(self):
        return f"PrintNode({self.expr}, {self.type})"

class ParallelNode(ASTNode):
    """Represents parallel processing thread spawn context."""
    def __init__(self, process_arr, threads=0):
        self.prc, self.threads = process_arr, threads
    def __repr__(self):
        return f"ParallelNode({self.prc}, {self.threads})"

class InputNode(ASTNode):
    """Represents a user input request, optionally with a prompt."""
    def __init__(self, prompt=None):
        self.prompt = prompt
    def __repr__(self):
        return f"InputNode({self.prompt})"
    
class ClassNode(ASTNode):
    """Represents an object-oriented class definition."""
    def __init__(self, name, fields, methods):
        self.name = name
        self.fields = fields
        self.methods = methods
    def __repr__(self):
        return f"ClassNode({self.name}, {self.fields},{self.methods})"
    
class InstanceNode(ASTNode):
    """Represents an instantiated object of a given class."""
    def __init__(self, class_node):
        self.class_node = class_node
        self.fields = {field: None for field in class_node.fields} 
    def __repr__(self):
        return f"InstanceNode({self.class_node}, {self.fields})"

class LenNode(ASTNode):
    """Represents an operation fetching the length of a collection."""
    def __init__(self, value):
        self.value = value 
    def __repr__(self):
        return f"LenNode({self.value})"

class BlockNode(ASTNode):
    """Represents a structured block containing multiple statements (e.g., loop body)."""
    def __init__(self, statements):
        self.statements = statements
    def __repr__(self):
        return f"BlockNode({self.statements})"

class ImportNode:
    """Represents an external library import statement."""
    def __init__(self, name_token):
        self.name = name_token  

    def __repr__(self):
        return f"ImportNode({self.name})"

class ImportFromNode:
    """Represents an import 'from' statement to import a specific module element."""
    def __init__(self, name, library):
        self.name = name
        self.lib = library
    
    def __repr__(self):
        return f"ImportFromNode({self.name}, {self.lib})"

class SetNode:
    """Represents a specialized assignment node for settings and state modifications."""
    def __init__(self, name, num, type_, params):
        self.name = name
        self.params = params
        self.type_ = type_
        self.num = num
    def __repr__(self):
        return f"SetNode({self.name}, {self.num},{self.type_},{self.params})"

class ImportAsNode:
    """Represents an import statement bound to a specific local alias."""
    def __init__(self, name, newName):
        self.name = name
        self.nName = newName
    
    def __repr__(self):
        return f"ImportAsNode({self.name}, {self.nName})"
    
class FuncNode:
    """Represents a defined function including parameters and execution block."""
    def __init__(self, name, params, body):
        self.name = name
        self.params = params
        self.body = body
    def __repr__(self):
        return f"FuncNode({self.name},{self.params}, {self.body})"
    
class IfNode(ASTNode):
    """Represents standard control flow 'if' conditioning."""
    def __init__(self, condition, then_body, elif_nodes=None, else_body=None):
        self.condition = condition
        self.then_body = then_body
        self.elif_nodes = elif_nodes or []
        self.else_body = else_body
    def __repr__(self):
        return f"IfNode({self.condition}, {self.then_body}, {self.elif_nodes}, {self.else_body})"

class ElifNode(ASTNode):
    """Represents a subsequent chained conditional within an if-else block."""
    def __init__(self, condition, then_body, else_body=None):
        self.condition = condition
        self.then_body = then_body
        self.else_body = else_body
    def __repr__(self):
        return f"ElifNode({self.condition}, {self.then_body}, {self.else_body})"

class WhileNode(ASTNode):
    """Represents a continuously looping conditional state block."""
    def __init__(self, condition, body):
        self.condition = condition
        self.body = body
    def __repr__(self):
        return f"WhileNode({self.condition}, {self.body})"

class ForNode(ASTNode):
    """Represents a scoped iteration over an iterable expression structure."""
    def __init__(self, var_name, iterable, body):
        self.var_name = var_name
        self.iterable = iterable
        self.body = body
    def __repr__(self):
        return f"ForNode({self.var_name}, {self.iterable}, {self.body})"

class UnaryOpNode(ASTNode):
    """Represents an operation affecting a single targeted syntactic node (e.g., value negation)."""
    def __init__(self, op, node):
        self.op, self.node = op, node
        self.type = None
    def __repr__(self):
        return f"UnaryOpNode({self.op!r}, {self.node})"
    
class ProgramNode(ASTNode):
    """Represents the root program tree consisting of global execution statements."""
    def __init__(self, statements):
        self.statements = statements
    def __repr__(self):
        return f"ProgramNode({self.statements})"

class BoolNode(ASTNode):
    """Represents a literal True or False constant boolean structure."""
    def __init__(self, value: bool):
        self.value = value
        self.type = "bool"
    def __repr__(self):
        return f"BoolNode({self.value})"

class CompoundAssignNode(ASTNode):
    """Represents variables resolving an operation during its assignment phase (e.g., +=)."""
    def __init__(self, name, op, value):
        self.name = name
        self.op = op
        self.value = value
    def __repr__(self):
        return f"CompoundAssignNode({self.name}, {self.op!r}, {self.value})"

class LogicOpNode(ASTNode):
    """Represents structural evaluation mappings spanning AND/OR logic."""
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right
    def __repr__(self):
        return f"LogicOpNode({self.left}, {self.op!r}, {self.right})"

class NotNode(ASTNode):
    """Represents a logical negation of evaluating boolean logic."""
    def __init__(self, expr):
        self.expr = expr
    def __repr__(self):
        return f"NotNode({self.expr})"

class CallNode(ASTNode):
    """Represents invocation logic addressing customized defined functionality."""
    def __init__(self, func_name, arg):
        self.func_name = func_name
        self.arg = arg
    def __repr__(self):
        return f"CallNode({self.func_name}, {self.arg})"

class SpecialOpNode(ASTNode):
    """Represents internal operator functionalities isolated securely."""
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right
    def __repr__(self):
        return f"SpecialOpNode({self.left}, {self.op!r}, {self.right})"

class BreakNode(ASTNode):
    """Represents the operational flow instruction terminating a loop."""
    def __repr__(self):
        return "BreakNode()"

class ContinueNode(ASTNode):
    """Represents the operational flow instruction advancing to the next loop scope."""
    def __repr__(self):
        return "ContinueNode()"

class ReturnNode(ASTNode):
    """Represents the operational mapping yielding context flow entirely dynamically."""
    def __init__(self, value):
        self.value = value
    def __repr__(self):
        return f"ReturnNode({self.value})"

class YieldNode(ASTNode):
    """Represents generative returning functionalities mapped temporally."""
    def __init__(self, value):
        self.value = value
    def __repr__(self):
        return f"YieldNode({self.value})"
