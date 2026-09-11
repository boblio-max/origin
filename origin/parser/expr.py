"""Expression parsing (factor through lambda)."""
import sys
from ..lexer.lexer_point import lex, Token
from ..classes import *
from ..errors import ParseError


class ExprMixin:
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

        if tok.type == "BOOL":
            self.eat("BOOL")
            return BoolNode(tok.value == "true")
        
        if tok.type == "STRING":
            self.eat("STRING")
            return StringNode(tok.value[1:-1], "str")
        if tok.type == "FSTRING":
            # Parse formatted string content into parts (text and expressions)
            self.eat("FSTRING")
            val = tok.value
            # val starts with f" or f'
            quote = val[1]
            inner = val[2:-1]
            parts = []
            i = 0
            while i < len(inner):
                if inner[i] == '{':
                    # find matching '}' (no nesting of expressions assumed, but handle nested braces)
                    j = i + 1
                    depth = 1
                    while j < len(inner) and depth > 0:
                        if inner[j] == '{': depth += 1
                        elif inner[j] == '}': depth -= 1
                        j += 1
                    if depth != 0:
                        raise self._error("Unmatched '{' in f-string")
                    expr_text = inner[i+1:j-1]
                    # Lex and parse the inner expression
                    expr_tokens = lex(expr_text.splitlines())
                    expr_node = type(self)(expr_tokens).special_expr()
                    parts.append(expr_node)
                    i = j
                else:
                    j = i
                    while j < len(inner) and inner[j] != '{':
                        j += 1
                    text = inner[i:j]
                    parts.append(StringNode(text))
                    i = j
            return FormattedStringNode(parts)
        
        if tok.type == "IMU":
            self.eat("IMU")
            try:
                self.eat("KEYWORD") # address
                address = self.eat("HEX").value
                return ImuNode(tok.value, address)
            except SyntaxError:
                return ImuNode(tok.value, "0x68")

        if tok.type == "KEYWORD":
            if tok.value == "range":
                self.eat("KEYWORD")
                self._expect_symbol("(")
                first = self._cast_or_none(self.special_expr())
                # Support both `range(n)` (single arg) and `range(start, end)` forms
                if self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                    self.eat("SYMBOL")
                    second = self._cast_or_none(self.special_expr())
                    step = None
                    if self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                        self.eat("SYMBOL")
                        step = self._cast_or_none(self.special_expr())
                    self._expect_symbol(")")
                    return RangeNode(first, second, step)
                else:
                    self._expect_symbol(")")
                    return RangeNode(NumberNode(0, "int"), first, None)
            
            if tok.value == "abs":
                self.eat("KEYWORD")
                value = self._cast_or_none(self.special_expr())
                return MathNode("abs", value)
            
            if tok.value == "floor":
                self.eat("KEYWORD")
                value = self._cast_or_none(self.special_expr())
                return MathNode("floor", value)
            
            if tok.value == "ceil":
                self.eat("KEYWORD")
                value = self._cast_or_none(self.special_expr())
                return MathNode("ceil", value)
            
            if tok.value in ("accel", "gyro", "temp"):
                value = self.eat("KEYWORD").value
                self.eat("KEYWORD") #from
                name = self.eat("IDENT").value
                return ImuFromNode(value, name)
            if tok.value == "write":
                self.eat("KEYWORD")
                file_name = self.eat("STRING").value 
                content = self.special_expr()  # <-- parses any expression
                return WriteNode(file_name, content)
                
            if tok.value == "append":
                self.eat("KEYWORD")
                file_name = self.eat("STRING").value 
                content = self.special_expr()  # <-- parses any expression
                return AppendNode(file_name, content)
            if tok.value == "read":
                self.eat("KEYWORD")                
                file_name = self.eat("STRING").value 
                count = -1
                if self.current_token().value == "to":
                    self.eat("KEYWORD")
                    count = int(self.eat("INT").value)
                return ReadNode(file_name, count)

            if tok.value == "input":
                self.eat("KEYWORD")
                prompt = None
                if self.current_token().type == "STRING":
                    prompt = StringNode(self.eat("STRING").value[1:-1])
                return InputNode(prompt)
            
            if tok.value == "sqrt":
                self.eat("KEYWORD")
                self._expect_symbol("(")
                value = self._cast_or_none(self.special_expr())
                self._expect_symbol(")")
                return SqrtNode(value)
                
            if tok.value == "rand_num":
                self.eat("KEYWORD")
                self._expect_symbol("(")
                start = self._cast_or_none(self.special_expr())
                self._expect_symbol(",")
                end = self._cast_or_none(self.special_expr())
                self._expect_symbol(")")
                return RandNumNode(start, end)
            
            if tok.value == "true":
                self.eat("KEYWORD")
                return BoolNode(True)

            if tok.value == "false":
                self.eat("KEYWORD")
                return BoolNode(False)

            if tok.value == "pi":
                self.eat("KEYWORD")
                _x = 157079632679489661923 / 50000000000000000000
                return NumberNode(_x, "float")
            
            if tok.value == "none":
                self.eat("KEYWORD")
                return NoneNode()
                
            if tok.value == "len":
                self.eat("KEYWORD") 
                self._expect_symbol("(")
                expr_node = self._cast_or_none(self.special_expr()) 
                self._expect_symbol(")")
                return LenNode(expr_node)
            
            if tok.value == "call":
                self.eat("KEYWORD")
                self.eat("BRACKET")  # [
                list_node = self.special_expr()
                self.eat("SYMBOL")  # ,
                pos = self.special_expr()
                self.eat("BRACKET")  # ]
                return ListCallNode(list_node, pos)
            
            if tok.value == "self":
                self.eat("KEYWORD")
                node = VarNode("self")
                while True:
                    if self.current_token().type == "SYMBOL" and self.current_token().value == ".":
                        self.eat("SYMBOL")
                        # Allow keywords as attribute names (e.g. self.func where func is keyword)
                        if self.current_token().type not in ("IDENT", "KEYWORD"):
                            raise self._error(f"Expected attribute name after '.', got {self.current_token().type} ({self.current_token().value})")
                        attr_name = self.eat(self.current_token().type).value
                        node = AttributeNode(node, attr_name)
                    elif self.current_token().type == "SYMBOL" and self.current_token().value == "(":
                        self.eat("SYMBOL")
                        args = []
                        self.skip_newlines()
                        if not (self.current_token().type == "SYMBOL" and self.current_token().value == ")"):
                            args.append(self._cast_or_none(self.special_expr()))
                            while self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                                self.eat("SYMBOL")
                                args.append(self._cast_or_none(self.special_expr()))
                        self.eat("SYMBOL")
                        node = CallNode(node, args)
                    else:
                        break
                return node
            
            if tok.value in ("int", "str", "float", "bool"):
                # Only treat as CastNode if followed by `(` (e.g. `int(x)`); otherwise it's a type reference (e.g. `isinstance(x, int)`)
                if self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1].type == "SYMBOL" and self.tokens[self.pos + 1].value == "(":
                    func_name = self.eat("KEYWORD").value
                    self.eat("SYMBOL")  # (
                    arg = self.special_expr()
                    self.eat("SYMBOL")  # )
                    return CastNode(func_name, arg)
                else:
                    # Treat as plain identifier (type reference)
                    return VarNode(self.eat("KEYWORD").value, None)

        if tok.type == "IDENT" or tok.type == "KEYWORD":
            # Look ahead for lambda syntax: identifier => expression
            if self.pos + 1 < len(self.tokens):
                next_tok = self.tokens[self.pos + 1]
                if next_tok.type == "SPECIAL" and next_tok.value == "=>":
                    return self.lambda_expr()

            # Allow keywords as identifiers for variable references (e.g. `func` param name)
            if tok.type == "KEYWORD":
                name = self.eat("KEYWORD").value
            else:
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
                        args.append(self._cast_or_none(self.special_expr()))
                        while self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                            self.eat("SYMBOL")
                            args.append(self._cast_or_none(self.special_expr()))
                    self.eat("SYMBOL")  # )
                    node = CallNode(node, args)

                # Attribute access
                elif self.current_token().type == "SYMBOL" and self.current_token().value == ".":
                    self.eat("SYMBOL")  # .
                    if self.current_token().type in ("IDENT", "KEYWORD"):
                        attr_name = self.eat(self.current_token().type).value
                    else:
                        tok_name = self.current_token()
                        raise self._error(
                            f"Expected attribute name after '.', got {tok_name.type} ({tok_name.value})"
                        )
                    node = AttributeNode(node, attr_name)

                    # Support non-parenthesized method call syntax: `obj.method arg`
                    # Optionally allow a type annotation after the argument: `obj.method 3:int`
                    # Only treat as a call when the next token can start an expression.
                    # NOTE: `[` and `{` are excluded to avoid consuming index/dict literals as call args.
                    nxt = self.current_token()
                    if nxt.type in ("INT", "HEX", "FLOAT", "STRING", "IDENT"):
                        # Parse a single expression as the argument
                        arg = self.special_expr()
                        # Optional type annotation after the arg: ':' TYPE
                        if self.current_token().type == "SYMBOL" and self.current_token().value == ":":
                            self.eat("SYMBOL")
                            type_tok = self.eat(self.current_token().type).value
                            arg = CastNode(type_tok, arg)
                        node = CallNode(node, [arg])

                else:
                    break
            return node
        
        # Parenthesized expressions or tuples
        if tok.type == "SYMBOL" and tok.value == "(":
            self.eat("SYMBOL")
            first = self.special_expr()
            if self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                elements = [first]
                while self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                    self.eat("SYMBOL")
                    if self.current_token().type == "SYMBOL" and self.current_token().value == ")":
                        break
                    elements.append(self.special_expr())
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
            
        if tok.type == "EOF":
            raise self._error("Unexpected end of input (an expression was expected)")
        raise self._error(f"Unexpected token {tok.type} ({tok.value})")

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

    def unary(self):
        tok = self.current_token()
        if tok.type == "UNARY" or (tok.type == "LOGIC" and tok.value in ("not", "!")) or (tok.type == "ARITH" and tok.value in ("-", "~", "+")):
            op = self.eat(tok.type).value
            return UnaryOpNode(op, self.unary())
        return self.factor()

    def term(self):
        node = self.unary()
        while self.current_token().type == "ARITH" and self.current_token().value in ("*", "/", "//", "%", "**"):
            op = self.eat("ARITH").value
            node = BinOpNode(node, op, self.unary())
        return node

    def expr(self):
        node = self.term()
        while self.current_token().type == "ARITH" and self.current_token().value in ("+", "-", "<<", ">>", "&", "|", "^"):
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
            right = self.logic()
            if op == "->":
                node = PipeNode(node, right)   
            else:
                node = SpecialOpNode(None, node, op, right)
        return node

    def lambda_expr(self):
        """Parses a lambda expression: parameter => body_expression"""
        var_tok = self.eat("IDENT")
        self.eat("SPECIAL")  # Consumes the '=>' operator
        body = self.special_expr()  # Recursively parse the body as a full expression
        return LambdaNode(var_tok.value, body)

