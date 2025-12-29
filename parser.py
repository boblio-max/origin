from lexer import Token


# =====================
# AST NODES
# =====================

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

class CastNode(ASTNode):
    def __init__(self, cast_type, value):
        self.cast_type = cast_type
        self.value = value

class ListNode(ASTNode):
    def __init__(self, elements):
        self.elements = elements
    def __repr__(self):
        return f"ListNode({self.elements})"


class BinOpNode(ASTNode):
    def __init__(self, left, op, right):
        self.left, self.op, self.right = left, op, right
    def __repr__(self):
        return f"BinOpNode({self.left}, {self.op!r}, {self.right})"


class AssignNode(ASTNode):
    def __init__(self, name, value):
        self.name, self.value = name, value
    def __repr__(self):
        return f"AssignNode({self.name}, {self.value})"


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


class BlockNode(ASTNode):
    def __init__(self, statements):
        self.statements = statements
    def __repr__(self):
        return f"BlockNode({self.statements})"


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


# =====================
# PARSER
# =====================

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def current_token(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return Token("EOF", "", -1, -1)

    def eat(self, type_):
        tok = self.current_token()
        if tok.type == type_:
            self.pos += 1
            return tok
        raise SyntaxError(f"Expected {type_}, got {tok.type} ({tok.value})")

    # -------- EXPRESSIONS --------

    def factor(self):
        self.skip_newlines()
        tok = self.current_token()

        if tok.type == "INT":
            self.eat("INT")
            return NumberNode(int(tok.value))

        if tok.type == "FLOAT":
            self.eat("FLOAT")
            return NumberNode(float(tok.value))

        if tok.type == "STRING":
            self.eat("STRING")
            return StringNode(tok.value[1:-1])

        if tok.type == "IDENT":
            self.eat("IDENT")
            return VarNode(tok.value)

        if tok.type == "KEYWORD" and tok.value == "input":
            self.eat("KEYWORD")
            prompt = None
            if self.current_token().type == "STRING":
                prompt = StringNode(self.eat("STRING").value[1:-1])
            return InputNode(prompt)

        if tok.type == "BRACKET" and tok.value == "(":
            self.eat("BRACKET")
            node = self.comparison()
            self.eat("BRACKET")
            return node

        if tok.type == "BRACKET" and tok.value == "[":
            return self.list_literal()
        if tok.type == "KEYWORD" and tok.value in ("int", "str", "float"):
            func_name = self.eat("KEYWORD").value
            self.eat("SYMBOL")  # (
            arg = self.comparison()
            self.eat("SYMBOL")  # )
            return CastNode(func_name, arg)
        raise SyntaxError(f"Unexpected token {tok}")

    def list_literal(self):
        elements = []
        self.eat("BRACKET")  # [

        if self.current_token().value != "]":
            elements.append(self.comparison())
            while self.current_token().value == ",":
                self.eat("SYMBOL")
                elements.append(self.comparison())

        self.eat("BRACKET")  # ]
        return ListNode(elements)

    def term(self):
        node = self.factor()
        while self.current_token().type == "ARITH" and self.current_token().value in ("*", "/"):
            op = self.eat("ARITH").value
            node = BinOpNode(node, op, self.factor())
        return node

    def expr(self):
        node = self.term()
        while self.current_token().type == "ARITH" and self.current_token().value in ("+", "-"):
            op = self.eat("ARITH").value
            node = BinOpNode(node, op, self.term())
        return node

    def comparison(self):
        node = self.expr()
        if self.current_token().type == "COMP":
            op = self.eat("COMP").value
            right = self.expr()
            return BinOpNode(node, op, right)
        return node

    # -------- STATEMENTS --------

    def assignment(self):
        self.eat("KEYWORD")  # let
        name = self.eat("IDENT").value
        self.eat("ASSIGN")
        value = self.comparison()
        return AssignNode(name, value)

    def print_stmt(self):
        self.eat("KEYWORD")
        return PrintNode(self.comparison())

    def block(self):
        statements = []
        self.eat("BRACKET")  # {

        while not (self.current_token().type == "BRACKET" and self.current_token().value == "}"):
            statements.append(self.statement())
            while self.current_token().type == "NEWLINE":
                self.eat("NEWLINE")

        self.eat("BRACKET")  # }
        return BlockNode(statements)

    def if_stmt(self):
        self.eat("KEYWORD")  # 'if'
        condition = self.comparison()
        then_body = self.block()
        elif_nodes = []

        # while self.current_token().type == "KEYWORD" and self.current_token().value == "elif":
        #     self.eat("KEYWORD")
        #     elif_condition = self.comparison()
        #     elif_body = self.block()
        #     elif_nodes.append(ElifNode(elif_condition, elif_body))

        else_body = None
        if self.current_token().type == "KEYWORD" and self.current_token().value == "else":
            self.eat("KEYWORD")
            else_body = self.block()

        return IfNode(condition, then_body, elif_nodes, else_body)
    def elif_stmt(self):
        self.eat("KEYWORD")  # 'if'
        condition = self.comparison()
        then_body = self.block()
        elif_nodes = []

        # while self.current_token().type == "KEYWORD" and self.current_token().value == "elif":
        #     self.eat("KEYWORD")
        #     elif_condition = self.comparison()
        #     elif_body = self.block()
        #     elif_nodes.append(ElifNode(elif_condition, elif_body))

        else_body = None
        if self.current_token().type == "KEYWORD" and self.current_token().value == "else":
            self.eat("KEYWORD")
            else_body = self.block()

        return ElifNode(condition, then_body, else_body)
    def while_stmt(self):
        self.eat("KEYWORD")
        condition = self.comparison()
        body = self.block()
        return WhileNode(condition, body)

    def for_stmt(self):
        self.eat("KEYWORD")
        var_name = self.eat("IDENT").value
        self.eat("KEYWORD")  # in
        iterable = self.comparison()
        body = self.block()
        return ForNode(var_name, iterable, body)

    def statement(self):
        self.skip_newlines()
        tok = self.current_token()

        if tok.type == "KEYWORD" and tok.value == "let":
            return self.assignment()
        if tok.type == "KEYWORD" and tok.value == "print":
            return self.print_stmt()
        if tok.type == "KEYWORD" and tok.value == "if":
            return self.if_stmt()
        if tok.type == "KEYWORD" and tok.value == "elif":
            return self.elif_stmt()
        if tok.type == "KEYWORD" and tok.value == "while":
            return self.while_stmt()
        if tok.type == "KEYWORD" and tok.value == "for":
            return self.for_stmt()

        return self.comparison()

    def program(self):
        statements = []
        while self.current_token().type != "EOF":
            statements.append(self.statement())
            while self.current_token().type == "NEWLINE":
                self.eat("NEWLINE")
        return ProgramNode(statements)
    
    def skip_newlines(self):
        while self.current_token().type == "NEWLINE":
            self.eat("NEWLINE")
