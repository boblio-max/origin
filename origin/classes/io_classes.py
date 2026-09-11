from .base_classes import *

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

class CommandNode(ASTNode):
    def __init__(self, command, flags=None):
        super().__init__()
        self.command = command
        self.flags = flags if flags is not None else []
        # backward-compat alias (interpreter historically used .params)
        self.params = self.flags
    def __repr__(self):
        return f"CommandNode({self.command!r}, {self.flags!r})"

class OpenNode(ASTNode): 
    """File open operation."""
    def __init__(self, name, path, _type):
        super().__init__()
        self.name = name
        self.path = path
        self.type = _type
    def __repr__(self):
        return f"OpenNode({self.name}, {self.path}, {self.type})"

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

class ImportNode(ASTNode):
    """Library import."""
    def __init__(self, name):
        super().__init__()
        self.name = name  
    def __repr__(self):
        return f"ImportNode({self.name})"

class ImportFromNode(ASTNode):
    """'from ... import' statement."""
    def __init__(self, name, lib):
        super().__init__()
        self.name = name
        self.lib = lib
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
