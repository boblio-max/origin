from xml.dom import SyntaxErr
from lexer import lex, Token
class ASTNode:
    pass

# Represents a numeric literal
class NumberNode(ASTNode):
    def __init__(self, value):
        self.value = value
    def __repr__(self):
        return f"NumberNode({self.value})"

# Represents a variable (like x, y)
class VarNode(ASTNode):
    def __init__(self, name):
        self.name = name
    def __repr__(self):
        return f"VarNode({self.name})"

# Represents a binary operation (like 2 + 3)
class BinOpNode(ASTNode):
    def __init__(self, left, op, right):
        self.left = left      # left side of operation (ASTNode)
        self.op = op          # operator as string, e.g. '+'
        self.right = right    # right side of operation (ASTNode)
    def __repr__(self):
        return f"BinOpNode({self.left}, {self.op!r}, {self.right})"

# Represents variable assignment (let x = expr)
class AssignNode(ASTNode):
    def __init__(self, name, value=None):
        if value == None:
            return f"PrintNode({self.name})"
        else:
            self.name = name  
            self.value = value   
        
    def __repr__(self):
        return f"AssignNode({self.name}, {self.value})"
    
class StringNode(ASTNode):
    def __init__(self, value):
        self.value = value  # string
    def __repr__(self):
        return f"StringNode({self.value!r})"
# Represents print statements (print x)
class PrintNode(ASTNode):
    def __init__(self, expr):
        self.expr = expr      # ASTNode to print
    def __repr__(self):
        return f"PrintNode({self.expr})"

# Optional: unary operations (like ++x, --y)
class UnaryOpNode(ASTNode):
    def __init__(self, op, node):
        self.op = op
        self.node = node
    def __repr__(self):
        return f"UnaryOpNode({self.op!r}, {self.node})"

# Optional: full program (list of statements)
class ProgramNode(ASTNode):
    def __init__(self, statements):
        self.statements = statements  # list of ASTNode
    def __repr__(self):
        return f"ProgramNode({self.statements})"
class InputNode(ASTNode):
    def __init__(self, prompt=None):
        self.prompt = prompt  # optional string prompt
    def __repr__(self):
        return f"InputNode({self.prompt!r})"


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        
    def current_token(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        else:
            return Token("EOF", "" , -1, -1)
    def eat(self, type_):
        tok = self.current_token()
        if tok.type == type_:
            self.pos += 1
            return tok
        else:
            raise SyntaxError(f"Expected {type_}, got {tok.type} at {tok.line}:{tok.col}")
    def factor(self):
        tok = self.current_token()
        if tok.type == "INT":
            self.eat("INT")
            return NumberNode(int(tok.value))
        elif tok.type == "FLOAT":
            self.eat("FLOAT")
            return NumberNode(float(tok.value))
        elif tok.type == "IDENT":
            self.eat("IDENT")
            return VarNode(tok.value)
        elif tok.type == "SYMBOL" and tok.value == "(":
            self.eat("SYMBOL")  # '('
            node = self.expr()
            if self.current_token().type == "SYMBOL" and self.current_token().value == ")":
                self.eat("SYMBOL")  # eat ')'
            return node
        elif tok.type == "STRING":
            self.eat("STRING")
            # strip quotes if needed
            value = tok.value
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            return StringNode(value)
        else:
            raise SyntaxError(f"Unexpected token {tok} at {tok.line}:{tok.col}")
        
    def term(self):
        node = self.factor()
        while self.pos < len(self.tokens) and self.current_token().type == "ARITH" and self.current_token().value in ("*", "/"):
            op_tok = self.eat("ARITH")
            node = BinOpNode(node, op_tok.value, self.factor())
        return node
    
    def expr(self):
        node = self.term()
        while self.pos < len(self.tokens) and self.current_token().type == "ARITH" and self.current_token().value in ("+", "-"):
            op_tok = self.eat("ARITH")
            node = BinOpNode(node, op_tok.value, self.term())
        return node
    
    def assignment(self):
        self.eat("KEYWORD")
        name_tok = self.eat("IDENT")
        self.eat("ASSIGN")
        value = self.expr()
        return AssignNode(name_tok.value, value)
            
    def print_stmt(self):
        self.eat("KEYWORD")  # 'print'
        value = self.expr()
        return PrintNode(value)
    def statement(self):
        tok = self.current_token()
        if tok.type == "KEYWORD" and tok.value == "let":
            return self.assignment()
        elif tok.type == "KEYWORD" and tok.value == "print":
            return self.print_stmt()
        elif tok.type == "KEYWORD" and tok.value == "input":
            self.eat("KEYWORD")  # eat 'input'
            prompt = None
            if self.current_token().type == "STRING":
                prompt_tok = self.eat("STRING")
                prompt = prompt_tok.value[1:-1]  # strip quotes
            return InputNode(prompt)
        else:
            return self.expr()
        
    def program(self):
        statements = []

        while self.pos < len(self.tokens) and self.current_token().type != "EOF":
            stmt = self.statement()        # parse the next statement
            statements.append(stmt)

            # Skip any NEWLINE tokens between statements
            while self.pos < len(self.tokens) and self.current_token().type == "NEWLINE":
                self.eat("NEWLINE")

        return ProgramNode(statements)
