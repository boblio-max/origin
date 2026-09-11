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
