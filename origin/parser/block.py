"""Block and program parsing."""
from ..lexer.lexer_point import lex, Token
from ..classes import *
from ..errors import ParseError


class BlockMixin:
    def block(self):
        self.skip_newlines()
        self.eat("BRACKET") # {
        statements = []
        while self.current_token().value != "}":
            statements.append(self.statement())
            self.skip_newlines()
        self.eat("BRACKET") # }
        return BlockNode(statements)

    def match_block(self, name):
        self.skip_newlines()
        self.eat("BRACKET") # {
        cases = []
        while self.current_token().value != "}":
            pattern = self.eat("IDENT")
            self.eat("ARITH")
            command = self.eat_line()
            cases.append((pattern.value, command))
        self.eat("BRACKET") # }
        return MatchNode(name, cases)
    
    def if_stmt(self):
        self.eat("KEYWORD") # if
        condition = self._cast_or_none(self.special_expr())
        then_body = self.block()
        elif_nodes = []
        while True:
            self.skip_newlines()
            if self.current_token().value == "elif":
                self.eat("KEYWORD")
                cond = self._cast_or_none(self.special_expr())
                elif_nodes.append(ElifNode(cond, self.block()))
            else:
                break
        else_body = None
        if self.current_token().value == "else":
            self.eat("KEYWORD")
            else_body = self.block()
        return IfNode(condition, then_body, elif_nodes, else_body)

    def program(self):
        statements = []
        while self.current_token().type != "EOF":
            statements.append(self.statement())
            self.skip_newlines()
        return ProgramNode(statements)