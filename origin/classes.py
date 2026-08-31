"""AST node definitions

This module defines the Abstract Syntax Tree (AST) node classes used by the
parser and interpreter. Each node class represents a single syntactic
construct (literal, expression, statement, etc.) and is intentionally small
and data-focused so the interpreter can pattern-match on types and fields.
"""

class ASTNode:
    """Abstract base type for AST nodes."""
    def __init__(self, line=None):
        self.line = line

class ProgramNode(ASTNode):
    """Root program tree consisting of global execution statements."""
    def __init__(self, statements):
        super().__init__()
        self.statements = statements
    def __repr__(self):
        return f"ProgramNode({self.statements})"

class BlockNode(ASTNode):
    """Structured block containing multiple statements."""
    def __init__(self, statements):
        super().__init__()
        self.statements = statements
    def __repr__(self):
        return f"BlockNode({self.statements})"

class ExecNode(ASTNode):
    """Embedded string evaluation/command."""
    def __init__(self, code):
        super().__init__()
        self.code = code
    def __repr__(self):
        return f"ExecNode({self.code!r})"

class PyNode(ASTNode):
    """Raw Python code block."""
    def __init__(self, code):
        super().__init__()
        self.code = code
    def __repr__(self):
        return f"PyNode({self.code!r})"
    
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

class FormattedStringNode(ASTNode):
    """Formatted string with interleaved text and expression parts."""
    def __init__(self, parts):
        super().__init__()
        self.parts = parts  # list of StringNode or expression nodes
    def __repr__(self):
        return f"FormattedStringNode({self.parts})"

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

class PassNode(ASTNode):
    """Pass statement."""
    def __init__(self):
        super().__init__()
    def __repr__(self):
        return "PassNode()"

class VarNode(ASTNode):
    """Variable reference."""
    def __init__(self, name, _type=None):
        super().__init__()
        self.name = name
        self.type = _type
    def __repr__(self):
        return f"VarNode({self.name}, {self.type})"

class CommandNode(ASTNode):
    def __init__(self, command, flags=None):
        super().__init__()
        self.command = command
        self.flags = flags if flags is not None else []
        # backward-compat alias (interpreter historically used .params)
        self.params = self.flags
    def __repr__(self):
        return f"CommandNode({self.command!r}, {self.flags!r})"
class AssignNode(ASTNode):
    """Assignment operation (let)."""
    def __init__(self, name, value, _type=None):
        super().__init__()
        self.name, self.value, self.type = name, value, _type
    def __repr__(self):
        return f"AssignNode({self.name}, {self.value}, {self.type})"

class MultAssignNode(ASTNode):
    def __init__(self, names, value, _type=None):
        super().__init__()
        self.names, self.value, self.type = names, value, _type
    def __repr__(self):
        return f"MultAssignNode({self.names}, {self.value}, {self.type})"
    
class ConstAssignNode(ASTNode):
    """Constant declaration (const)."""
    def __init__(self, name, value, _type=None):
        super().__init__()
        self.name, self.value, self.type = name, value, _type
    def __repr__(self):
        return f"ConstAssignNode({self.name}, {self.value}, {self.type})"

class CompoundAssignNode(ASTNode):
    """Compound assignment (+=, -=, etc.)."""
    def __init__(self, name, op, value):
        super().__init__()
        self.name = name
        self.op = op
        self.value = value
    def __repr__(self):
        return f"CompoundAssignNode({self.name}, {self.op!r}, {self.value})"

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

class AttributeAssignNode(ASTNode):
    """Assignment to an attribute (obj.attr = value)."""
    def __init__(self, obj, attr, value):
        super().__init__()
        self.obj = obj
        self.attr = attr
        self.value = value
    def __repr__(self):
        return f"AttributeAssignNode({self.obj}, {self.attr}, {self.value})"

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

class IndexAssignNode(ASTNode):
    """Assignment to an index (list[index] = value)."""
    def __init__(self, collection, index, value):
        super().__init__()
        self.collection = collection
        self.index = index
        self.value = value
    def __repr__(self):
        return f"IndexAssignNode({self.collection}, {self.index}, {self.value})"

class ListCallNode(ASTNode):
    """Special API calls for lists."""
    def __init__(self, list_node, pos):
        super().__init__()
        self.list_node = list_node
        self.pos = pos
    def __repr__(self):
        return f"ListCallNode({self.list_node}, {self.pos})"

class OpenNode(ASTNode): 
    """File open operation."""
    def __init__(self, name, path, _type):
        super().__init__()
        self.name = name
        self.path = path
        self.type = _type
    def __repr__(self):
        return f"OpenNode({self.name}, {self.path}, {self.type})"

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

class PrintNode(ASTNode):
    """Print statement."""
    def __init__(self, expr):
        super().__init__()
        self.expr = expr
    def __repr__(self):
        return f"PrintNode({self.expr})"

class InputNode(ASTNode):
    """User input request."""
    def __init__(self, prompt=None):
        super().__init__()
        self.prompt = prompt
    def __repr__(self):
        return f"InputNode({self.prompt})"

class CastNode(ASTNode):
    """Type casting."""
    def __init__(self, cast_type, value):
        super().__init__()
        self.cast_type = cast_type
        self.value = value
        self.type = cast_type
    def __repr__(self):
        return f"CastNode({self.cast_type}, {self.value})"

class RangeNode(ASTNode):
    """Numeric range generator."""
    def __init__(self, start, end, step=None):
        super().__init__()
        self.start = start
        self.end = end
        self.step = step
    def __repr__(self):
        return f"RangeNode({self.start}, {self.end},{self.step})"

class ParallelNode(ASTNode):
    """Parallel processing context."""
    def __init__(self, body, threads=0):
        super().__init__()
        self.body, self.threads = body, threads
    def __repr__(self):
        return f"ParallelNode({self.body}, {self.threads})"

class HardwarePrimitiveNode(ASTNode):
    """Hardware protocol primitive call (i2c, spi, uart)."""
    def __init__(self, namespace, method, args):
        super().__init__()
        self.namespace = namespace
        self.method = method
        self.args = args
    def __repr__(self):
        return f"HardwarePrimitiveNode({self.namespace}, {self.method}, {self.args})"

class SetNode(ASTNode):
    """Specialized state modification (servo, pin)."""
    def __init__(self, name, num, type_, params):
        super().__init__()
        self.name = name
        self.num = num
        self.type_ = type_
        self.params = params
    def __repr__(self):
        return f"SetNode({self.name}, {self.num}, {self.type_}, {self.params})"

class ImportNode(ASTNode):
    """Library import."""
    def __init__(self, name):
        super().__init__()
        self.name = name  
    def __repr__(self):
        return f"ImportNode({self.name})"

class ImportFromNode(ASTNode):
    """'from ... import' statement."""
    def __init__(self, name, libraries):
        super().__init__()
        self.name = name
        self.lib = ", ".join(libraries)
    def __repr__(self):
        return f"ImportFromNode({self.name}, {self.lib})"

class ImportAsNode(ASTNode):
    """'import ... as' statement."""
    def __init__(self, name, alias):
        super().__init__()
        self.name = name
        self.alias = alias
    def __repr__(self):
        return f"ImportAsNode({self.name}, {self.alias})"

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
    
class ReadNode(ASTNode):
    """Converts file to string"""
    def __init__(self, file, count):
        super().__init__()
        self.file = file
        self.count = count
    def __repr__(self):
        return f"ReadNode({self.file}, {self.count})"

class WriteNode(ASTNode):
    """Writes to a file"""
    def __init__(self, file, contents):
        super().__init__()
        self.file = file
        self.contents = contents
    def __repr__(self):
        return f"WriteNode({self.file}, {self.contents})"

class AppendNode(ASTNode):
    """Writes to a file"""
    def __init__(self, file, contents):
        super().__init__()
        self.file = file
        self.contents = contents
    def __repr__(self):
        return f"WriteNode({self.file}, {self.contents})"

class ImuNode(ASTNode):
    """IMU data"""
    def __init__(self, name, address):
        super().__init__()
        self.name = name
        self.address = address
    def __repr__(self):
        return f"ImuNode({self.name}, {self.address})"
    
class ImuFromNode(ASTNode):
    """IMU data"""
    def __init__(self, value, name):
        super().__init__()
        self.value = value
        self.name = name
    def __repr__(self):
        return f"ImuFromNode({self.value}, {self.name})"
class CopyNode(ASTNode):
    """Copy operation (copy variable value)."""
    def __init__(self, src, dst):
        super().__init__()
        self.src = src
        self.dst = dst
    def __repr__(self):
        return f"CopyNode({self.src}, {self.dst})"

class MoveNode(ASTNode):
    """Move operation (move variable value, clear source)."""
    def __init__(self, src, dst):
        super().__init__()
        self.src = src
        self.dst = dst
    def __repr__(self):
        return f"MoveNode({self.src}, {self.dst})"