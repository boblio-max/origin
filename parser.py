"""parser

Recursive-descent parser for the origin language.

This module consumes a linear sequence of :class:`lexer.Token` objects and
constructs an Abstract Syntax Tree (AST) comprised of node classes from
``classes.py``.
"""

from lexer import Token, lex
from classes import *

class Parser:
    """Deterministic recursive-descent parser."""
    
    types = {"int": "int", "float": "float", "str": "str", "bool": "bool"}
    
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def _set_line(self, node, line):
        if node and hasattr(node, '__dict__'):
            node.line = line
        return node

    def current_token(self):
        """Return the token at the current parser position."""
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return Token("EOF", "", -1, -1)

    def eat(self, type_):
        """Consume and return the current token when it matches ``type_``."""
        tok = self.current_token()
        if tok.type == type_:
            self.pos += 1
            return tok
        raise SyntaxError(f"Expected {type_}, got {tok.type} ({tok.value}) at {tok.line}:{tok.col}")

    def skip_newlines(self):
        """Skip optional newline tokens."""
        while self.current_token().type == "NEWLINE":
            self.eat("NEWLINE")

    def factor(self):
        """Smallest expression units: literals, identifiers, calls."""
        self.skip_newlines()
        tok = self.current_token()

        if tok.type == "INT":
            self.eat("INT")
            return NumberNode(int(tok.value), "int")

        if tok.type == "HEX":
            self.eat("HEX")
            return NumberNode(int(tok.value, 16), "int")

        if tok.type == "FLOAT":
            self.eat("FLOAT")
            return NumberNode(float(tok.value), "float")

        if tok.type == "STRING":
            self.eat("STRING")
            return StringNode(tok.value, "str")
        
        if tok.type == "KEYWORD":
            if tok.value == "range":
                self.eat("KEYWORD")          
                self.eat("SYMBOL")      
                start = self.special_expr()
                self.eat("SYMBOL")          
                end = self.special_expr()
                self.eat("SYMBOL")          
                return RangeNode(start, end)
            
            if tok.value == "input":
                self.eat("KEYWORD")
                prompt = None
                if self.current_token().type == "STRING":
                    prompt = StringNode(self.eat("STRING").value[1:-1])
                return InputNode(prompt)
            
            if tok.value == "true":
                self.eat("KEYWORD")
                return BoolNode(True)

            if tok.value == "false":
                self.eat("KEYWORD")
                return BoolNode(False)
            
            if tok.value == "call":
                self.eat("KEYWORD")
                self.eat("BRACKET")  # [
                list_node = self.special_expr()
                self.eat("SYMBOL")  # ,
                pos = self.special_expr()
                self.eat("BRACKET")  # ]
                return ListCallNode(list_node, pos)
            
            if tok.value in ("int", "str", "float", "bool"):
                func_name = self.eat("KEYWORD").value
                self.eat("SYMBOL")  # (
                arg = self.special_expr()
                self.eat("SYMBOL")  # )
                return CallNode(VarNode(func_name), [arg])

        if tok.type == "IDENT":
            name = self.eat("IDENT").value
            
            # Hardware primitives
            if name in ("i2c", "spi", "uart") and self.current_token().type == "SYMBOL" and self.current_token().value == ".":
                self.eat("SYMBOL")  # .
                method = self.eat("IDENT").value
                args = []
                self.skip_newlines()
                if self.current_token().type not in ("NEWLINE", "EOF", "SYMBOL", "BRACKET") or \
                   (self.current_token().type == "SYMBOL" and self.current_token().value == "("):
                    if self.current_token().value == "(":
                        self.eat("SYMBOL")
                        if self.current_token().value != ")":
                            args.append(self.special_expr())
                            while self.current_token().value == ",":
                                self.eat("SYMBOL")
                                args.append(self.special_expr())
                        self.eat("SYMBOL")
                    else:
                        args.append(self.special_expr())
                        while self.current_token().value == ",":
                            self.eat("SYMBOL")
                            args.append(self.special_expr())
                return HardwarePrimitiveNode(name, method, args)

            node = VarNode(name)
            while True:
                # Indexing
                if self.current_token().type == "BRACKET" and self.current_token().value == "[":
                    self.eat("BRACKET")
                    index = self.special_expr()
                    self.eat("BRACKET")
                    node = IndexNode(node, index)
                
                # Calls
                elif self.current_token().type == "SYMBOL" and self.current_token().value == "(":
                    self.eat("SYMBOL")  # (
                    args = []
                    self.skip_newlines()
                    if not (self.current_token().type == "SYMBOL" and self.current_token().value == ")"):
                        self.skip_newlines()
                        args.append(self.special_expr())
                        self.skip_newlines()
                        while self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                            self.eat("SYMBOL")
                            self.skip_newlines()
                            args.append(self.special_expr())
                            self.skip_newlines()
                    self.eat("SYMBOL")  # )
                    node = CallNode(node, args)
                    self.skip_newlines()

                # Attribute access
                elif self.current_token().type == "SYMBOL" and self.current_token().value == ".":
                    self.eat("SYMBOL")  # .
                    attr_name = self.eat("IDENT").value
                    node = AttributeNode(node, attr_name)

                else:
                    break
            return node
        
        # Parenthesized expressions or tuples
        if tok.type == "SYMBOL" and tok.value == "(":
            self.eat("SYMBOL")
            first = self.special_expr()
            if self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                self.skip_newlines()
                elements = [first]
                while self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                    self.eat("SYMBOL")
                    self.skip_newlines()
                    if self.current_token().type == "SYMBOL" and self.current_token().value == ")":
                        break
                    elements.append(self.special_expr())
                    self.skip_newlines()
                self.eat("SYMBOL")  # )
                return TupleNode(elements)
            else:
                self.eat("SYMBOL")  # )
                return first

        if tok.type == "BRACKET":
            if tok.value == "[":
                return self.list_literal()
            if tok.value == "{":
                return self.dict_literal()
            
        raise SyntaxError(f"Unexpected token {tok}")

    def list_literal(self):
        elements = []
        self.eat("BRACKET")  # [
        self.skip_newlines()
        if self.current_token().value != "]":
            elements.append(self.special_expr())
            self.skip_newlines()
            while self.current_token().value == ",":
                self.eat("SYMBOL")
                self.skip_newlines()
                if self.current_token().value == "]":
                    break
                elements.append(self.special_expr())
                self.skip_newlines()
        self.eat("BRACKET")  # ]
        return ListNode(elements)

    def dict_literal(self):
        elements = {}
        self.eat("BRACKET")  # {
        self.skip_newlines()
        if self.current_token().value != "}":
            key = self.special_expr()
            self.eat("SYMBOL")  # :
            self.skip_newlines()
            value = self.special_expr()
            elements[key] = value
            self.skip_newlines()
            while self.current_token().value == ",":
                self.eat("SYMBOL")
                self.skip_newlines()
                if self.current_token().value == "}":
                    break
                key = self.special_expr()
                self.eat("SYMBOL")  # :
                self.skip_newlines()
                value = self.special_expr()
                elements[key] = value
                self.skip_newlines()
        self.eat("BRACKET")  # }
        return DictNode(elements)

    def power(self):
        node = self.factor()
        if self.current_token().type == "ARITH" and self.current_token().value == "**":
            op = self.eat("ARITH").value
            node = BinOpNode(node, op, self.power()) # Right associative
        return node

    def unary(self):
        tok = self.current_token()
        if tok.type == "UNARY" or (tok.type == "LOGIC" and tok.value in ("not", "!")) or (tok.type == "ARITH" and tok.value == "-"):
            op = self.eat(tok.type).value
            return UnaryOpNode(op, self.unary())
        return self.power()

    def term(self):
        node = self.unary()
        while self.current_token().type == "ARITH" and self.current_token().value in ("*", "/", "//", "%"):
            op = self.eat("ARITH").value
            node = BinOpNode(node, op, self.unary())
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
            node = BinOpNode(node, op, self.expr())
        return node

    def logic(self):
        node = self.comparison()
        while self.current_token().type == "LOGIC":
            op = self.eat("LOGIC").value
            node = LogicOpNode(node, op, self.comparison())
        return node

    def special_expr(self):
        node = self.logic()
        while self.current_token().type == "SPECIAL":
            op = self.eat("SPECIAL").value
            node = SpecialOpNode(node, op, self.logic())
        return node

    def statement(self):
        self.skip_newlines()
        line = self.current_token().line
        node = self._statement()
        return self._set_line(node, line)

    def _statement(self):
        tok = self.current_token()
        
        if tok.type == "IDENT":
            start_pos = self.pos
            try:
                target = self.special_expr()
                if self.current_token().type == "ASSIGN":
                    self.eat("ASSIGN")
                    value = self.special_expr()
                    if isinstance(target, IndexNode):
                        return IndexAssignNode(target.collection, target.index, value)
                    if isinstance(target, VarNode):
                        return AssignNode(target.name, value)
                    if isinstance(target, AttributeNode):
                        return AttributeAssignNode(target.obj, target.attr, value)
                
                if isinstance(target, VarNode) and self.current_token().type == "ASSIGN_OP":
                    op = self.eat("ASSIGN_OP").value
                    value = self.special_expr()
                    return CompoundAssignNode(target.name, op, value)
            except SyntaxError:
                pass
            self.pos = start_pos

        if tok.type == "KEYWORD":
            if tok.value == "let":
                self.eat("KEYWORD")
                name = self.eat("IDENT").value
                _type = None
                if self.current_token().value == ":":
                    self.eat("SYMBOL")
                    _type = self.eat(self.current_token().type).value # int, float, etc.
                self.eat("ASSIGN")
                value = self.special_expr()
                return AssignNode(name, value, _type)

            if tok.value == "const":
                self.eat("KEYWORD")
                name = self.eat("IDENT").value
                if self.current_token().value == ":":
                    self.eat("SYMBOL")
                    self.eat(self.current_token().type)
                self.eat("ASSIGN")
                value = self.special_expr()
                return ConstAssignNode(name, value)

            if tok.value == "set":
                self.eat("KEYWORD")
                name = self.eat("IDENT").value
                if self.current_token().value == "[":
                    self.eat("BRACKET")
                    num = self.special_expr()
                    self.eat("BRACKET")
                    self.eat("ASSIGN")
                    subtype = self.eat("IDENT").value
                    if self.current_token().value == ",": self.eat("SYMBOL")
                    param = self.special_expr()
                else:
                    subtype = None
                    if self.current_token().value == ".":
                        self.eat("SYMBOL")
                        subtype = self.eat("IDENT").value
                    num = self.special_expr()
                    if self.current_token().value == ",": self.eat("SYMBOL")
                    param = self.special_expr()
                return SetNode(name, num, subtype, param)

            if tok.value == "print":
                self.eat("KEYWORD")
                self.skip_newlines()
                return PrintNode(self.special_expr())

            if tok.value == "if":
                return self.if_stmt()

            if tok.value == "while":
                self.eat("KEYWORD")
                self.skip_newlines()
                condition = self.special_expr()
                body = self.block()
                return WhileNode(condition, body)

            if tok.value == "for":
                self.eat("KEYWORD")
                self.skip_newlines()
                var = self.eat("IDENT").value
                self.eat("KEYWORD") # in
                iterable = self.special_expr()
                body = self.block()
                return ForNode(var, iterable, body)

            if tok.value == "def":
                self.eat("KEYWORD")
                name = self.eat("IDENT").value
                self.eat("SYMBOL") # (
                params = []
                if self.current_token().value != ")":
                    self.skip_newlines()
                    params.append(self.eat("IDENT").value)
                    self.skip_newlines()
                    while self.current_token().value == ",":
                        self.eat("SYMBOL")
                        self.skip_newlines()
                        params.append(self.eat("IDENT").value)
                        self.skip_newlines()
                self.eat("SYMBOL") # )
                body = self.block()
                return FuncNode(name, params, body)

            if tok.value == "class":
                self.eat("KEYWORD")
                name = self.eat("IDENT").value
                self.eat("SYMBOL") # (
                fields = []
                if self.current_token().value != ")":
                    self.skip_newlines()
                    fields.append(self.eat("IDENT").value)
                    self.skip_newlines()
                    while self.current_token().value == ",":
                        self.eat("SYMBOL")
                        self.skip_newlines()
                        fields.append(self.eat("IDENT").value)
                        self.skip_newlines()
                self.eat("SYMBOL") # )
                body = self.block()
                return ClassNode(name, fields, body)

            if tok.value == "try":
                self.eat("KEYWORD")
                try_body = self.block()
                except_nodes = []
                while True:
                    self.skip_newlines()
                    if self.current_token().value == "except":
                        self.eat("KEYWORD")
                        except_nodes.append(self.block())
                    else:
                        break
                else_body = None
                if self.current_token().value == "else":
                    self.eat("KEYWORD")
                    else_body = self.block()
                return TryNode(try_body, except_nodes, else_body)

            if tok.value == "parallel":
                self.eat("KEYWORD")
                threads = 0
                if self.current_token().value == "(":
                    self.eat("SYMBOL")
                    threads = int(self.eat("INT").value)
                    self.eat("SYMBOL")
                body = self.block()
                return ParallelNode(body, threads)

            if tok.value == "import":
                self.eat("KEYWORD")
                name = self.eat("IDENT").value
                if self.current_token().value == "as":
                    self.eat("KEYWORD")
                    alias = self.eat("IDENT").value
                    return ImportAsNode(name, alias)
                return ImportNode(name)

            if tok.value == "from":
                self.eat("KEYWORD")
                lib = self.eat("IDENT").value
                self.eat("KEYWORD") # import
                name = self.eat("IDENT").value
                return ImportFromNode(name, lib)

            if tok.value == "return":
                self.eat("KEYWORD")
                return ReturnNode(self.special_expr())

            if tok.value == "break":
                self.eat("KEYWORD")
                return BreakNode()

            if tok.value == "continue":
                self.eat("KEYWORD")
                return ContinueNode()

            if tok.value == "global":
                self.eat("KEYWORD")
                name = self.eat("IDENT").value
                return GlobalNode(name)

            if tok.value == "pass":
                self.eat("KEYWORD")
                return PassNode()
            
            if tok.value == "exec":
                self.eat("KEYWORD")
                return ExecNode(self.eat("STRING").value[1:-1])

            if tok.value == "py":
                self.eat("KEYWORD")
                self.eat("BRACKET") # {
                raw = ""
                depth = 1
                while depth > 0:
                    t = self.current_token()
                    self.pos += 1
                    if t.type == "BRACKET" and t.value == "{": depth += 1
                    elif t.type == "BRACKET" and t.value == "}":
                        depth -= 1
                        if depth == 0: break
                    raw += t.value if t.type != "NEWLINE" else "\n"
                return PyNode(raw.strip())

        return self.special_expr()

    def block(self):
        self.skip_newlines()
        self.eat("BRACKET") # {
        statements = []
        while self.current_token().value != "}":
            statements.append(self.statement())
            self.skip_newlines()
        self.eat("BRACKET") # }
        return BlockNode(statements)

    def if_stmt(self):
        self.eat("KEYWORD") # if
        self.skip_newlines()
        condition = self.special_expr()
        then_body = self.block()
        elif_nodes = []
        while True:
            self.skip_newlines()
            if self.current_token().value == "elif":
                self.eat("KEYWORD")
                self.skip_newlines()
                cond = self.special_expr()
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