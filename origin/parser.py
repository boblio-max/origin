"""parser

Recursive-descent parser for the origin language.

This module consumes a linear sequence of :class:`lexer.Token` objects and
constructs an Abstract Syntax Tree (AST) comprised of node classes from
``classes.py``.
"""

import sys
import textwrap
from .lexer import lex, Token
from .classes import *
from .errors import ParseError


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
        """Return the next non-whitespace token, skipping WHITESPACE."""
        while self.pos < len(self.tokens) and self.tokens[self.pos].type == "WHITESPACE":
            self.pos += 1
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return Token("EOF", "", -1, -1)

    def _error(self, message, suggestion=None, tok=None):
        """Build a ParseError positioned at the given (or current) token.

        At end of input the position falls back to the last real token so the
        diagnostic still points somewhere useful.
        """
        if tok is None:
            tok = self.current_token()
        if tok.line < 1 or tok.type == "EOF":
            for t in reversed(self.tokens):
                if t.type not in ("EOF", "WHITESPACE", "NEWLINE") and t.line >= 1:
                    tok = t
                    break
        return ParseError(message, line=tok.line, col=max(tok.col, 0), suggestion=suggestion)

    def eat(self, type_):
        """Consume and return the current token when it matches ``type_``."""
        tok = self.current_token()
        if tok.type == type_:
            self.pos += 1
            return tok
        raise self._error(f"Expected {type_}, got {tok.type} ({tok.value})")

    def _expect_symbol(self, value):
        """Consume a symbol token with the given value, else raise a syntax error."""
        tok = self.current_token()
        if tok.type == "SYMBOL" and tok.value == value:
            self.pos += 1
            return tok
        raise self._error(f"Expected '{value}' but got {tok.type} ({tok.value})")

    def _parse_type_annotation(self, allow_ident=False):
        """Consume an optional ``:type`` annotation and return the type name, or None.

        With ``allow_ident`` any identifier/keyword is accepted as a type name
        (for declarations). Without it, only the castable builtin types
        (int, float, str, bool) are accepted (for argument casts).
        """
        if not (self.current_token().type == "SYMBOL" and self.current_token().value == ":"):
            return None
        self.eat("SYMBOL")
        t = self.current_token()
        if t.type in ("IDENT", "KEYWORD"):
            if allow_ident or t.value in ("int", "float", "str", "bool"):
                return self.eat(t.type).value
        raise self._error(
            f"Expected a type name after ':' but got {t.type} ({t.value})"
        )

    def _cast_or_none(self, node):
        """Wrap ``node`` in a CastNode if a ``:type`` annotation follows it.

        Only the castable builtin types produce a cast; otherwise the node is
        returned unchanged.
        """
        type_name = self._parse_type_annotation(allow_ident=False)
        if type_name is not None:
            return CastNode(type_name, node)
        return node

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
                    expr_node = Parser(expr_tokens).special_expr()
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
                start = self._cast_or_none(self.special_expr())
                self._expect_symbol(",")
                end = self._cast_or_none(self.special_expr())
                step = None
                if self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                    self.eat("SYMBOL")
                    step = self._cast_or_none(self.special_expr())
                self._expect_symbol(")")
                return RangeNode(start, end, step)
            
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
                        attr_name = self.eat("IDENT").value
                        node = AttributeNode(node, attr_name)
                    elif self.current_token().type == "SYMBOL" and self.current_token().value == "(":
                        self.eat("SYMBOL")
                        args = []
                        self.skip_newlines()
                        if not (self.current_token().type == "SYMBOL" and self.current_token().value == ")"):
                            args.append(self._cast_or_none(self.special_expr()))
                            while self.current_token().type == ",":
                                self.eat("SYMBOL")
                                args.append(self._cast_or_none(self.special_expr()))
                        self.eat("SYMBOL")
                        node = CallNode(node, args)
                    else:
                        break
                return node
            
            if tok.value in ("int", "str", "float", "bool"):
                func_name = self.eat("KEYWORD").value
                self.eat("SYMBOL")  # (
                arg = self.special_expr()
                self.eat("SYMBOL")  # )
                return CastNode(func_name, arg)

        if tok.type == "IDENT":
            # Look ahead for lambda syntax: identifier => expression
            if self.pos + 1 < len(self.tokens):
                next_tok = self.tokens[self.pos + 1]
                if next_tok.type == "SPECIAL" and next_tok.value == "=>":
                    return self.lambda_expr()

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
                    nxt = self.current_token()
                    if nxt.type in ("INT", "HEX", "FLOAT", "STRING", "IDENT") or (nxt.type == "BRACKET" and nxt.value in ("[", "{")):
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
                names = [self.eat(self.current_token().type).value]
                while self.current_token().value == ",":
                    self.eat("SYMBOL")
                    names.append(self.eat(self.current_token().type).value)
                _types = []
                if self.current_token().value == ":":
                    self.eat("SYMBOL")
                    while True:
                        _types.append(self.eat(self.current_token().type).value)
                        if self.current_token().value == ",":
                            self.eat("SYMBOL")
                        else:
                            break
                else:
                    # No type annotation: nudge toward strict typing, but auto-infer
                    print(
                        f"[WARNING] Variable '{names[0]}' declared without a type annotation; "
                        f"the type will be inferred. Tip: use `let {names[0]}: <type> = ...` "
                        f"for strict typing.",
                        file=sys.stderr,
                    )
                self.eat("ASSIGN")
                values = [self.special_expr()]
                while self.current_token().value == ",":
                    self.eat("SYMBOL")
                    values.append(self.special_expr())
                if len(names) == 1:
                    return MultAssignNode(names[0], values[0], _types[0] if _types else None)
                return MultAssignNode(names, values, _types or [None])

            if tok.value == "self":
                start_pos = self.pos
                try:
                    target = self.factor()
                    if self.current_token().type == "ASSIGN":
                        self.eat("ASSIGN")
                        value = self.special_expr()
                        if isinstance(target, AttributeNode):
                            return AttributeAssignNode(target.obj, target.attr, value)
                except SyntaxError:
                    pass
                self.pos = start_pos
                
            if tok.value == "const":
                self.eat("KEYWORD")
                name = self.eat(self.current_token().type).value
                _type = None
                if self.current_token().value == ":":
                    self.eat("SYMBOL")
                    _type = self.eat(self.current_token().type).value
                else:
                    # No type annotation: nudge toward strict typing, but auto-infer
                    print(
                        f"[WARNING] Constant '{name}' declared without a type annotation; "
                        f"the type will be inferred. Tip: use `const {name}: <type> = ...` "
                        f"for strict typing.",
                        file=sys.stderr,
                    )
                self.eat("ASSIGN")
                value = self.special_expr()
                return ConstAssignNode(name, value, _type)

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
                # Support both normal print statements and single-line `print ... for ...` forms
                self.eat("KEYWORD")
                # Parse one or more comma-separated expressions as print arguments
                args = []
                self.skip_newlines()
                # If next token is not a for/EOF/BRACE, parse expressions
                if not (self.current_token().type == "KEYWORD" and self.current_token().value == "for"):
                    args.append(self.special_expr())
                    while self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                        self.eat("SYMBOL")
                        self.skip_newlines()
                        # Stop if 'for' follows (allow trailing commas before for)
                        if self.current_token().type == "KEYWORD" and self.current_token().value == "for":
                            break
                        args.append(self.special_expr())

                expr_node = args[0] if len(args) == 1 else TupleNode(args)

                # Handle single-line `print ... for ...` syntax
                if self.current_token().type == "KEYWORD" and self.current_token().value == "for":
                    # Reuse the existing for-loop parsing logic: parse target and iterable
                    self.eat("KEYWORD")
                    # Parse target: allow single identifier or unpacking (reuse logic similar to for branch)
                    if self.current_token().type == "SYMBOL" and self.current_token().value == "(":
                        self.eat("SYMBOL")
                        targets = []
                        self.skip_newlines()
                        if not (self.current_token().type == "SYMBOL" and self.current_token().value == ")"):
                            if self.current_token().type in ("IDENT", "KEYWORD"):
                                targets.append(VarNode(self.eat(self.current_token().type).value))
                            while self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                                self.eat("SYMBOL")
                                self.skip_newlines()
                                targets.append(VarNode(self.eat(self.current_token().type).value))
                        self.skip_newlines()
                        self.eat("SYMBOL")
                        var = TupleNode(targets)
                    elif self.current_token().type == "BRACKET" and self.current_token().value == "[":
                        self.eat("BRACKET")
                        targets = []
                        self.skip_newlines()
                        if not (self.current_token().type == "BRACKET" and self.current_token().value == "]"):
                            if self.current_token().type in ("IDENT", "KEYWORD"):
                                targets.append(VarNode(self.eat(self.current_token().type).value))
                            while self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                                self.eat("SYMBOL")
                                self.skip_newlines()
                                targets.append(VarNode(self.eat(self.current_token().type).value))
                        self.skip_newlines()
                        self.eat("BRACKET")
                        var = ListNode(targets)
                    else:
                        # bare unpacking or single identifier
                        if self.current_token().type in ("IDENT", "KEYWORD"):
                            first_name = self.eat(self.current_token().type).value
                            if self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                                targets = [VarNode(first_name)]
                                while self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                                    self.eat("SYMBOL")
                                    self.skip_newlines()
                                    targets.append(VarNode(self.eat(self.current_token().type).value))
                                var = TupleNode(targets)
                            else:
                                var = VarNode(first_name)
                        else:
                            raise self._error("Expected identifier for for-loop target")

                    self.eat("KEYWORD") # in
                    iterable = self.special_expr()
                    # Build a ForNode whose body is a single PrintNode of the parsed expr_node
                    return ForNode(var, iterable, BlockNode([PrintNode(expr_node)]))

                return PrintNode(expr_node)

            if tok.value == "if":
                return self.if_stmt()

            if tok.value == "while":
                self.eat("KEYWORD")
                condition = self._cast_or_none(self.special_expr())
                body = self.block()
                return WhileNode(condition, body)
                 
            if tok.value == "run":
                self.eat("KEYWORD")  # run
                cmd_tok = self.current_token()
                if cmd_tok.type != "KEYWORD" or cmd_tok.value != "command":
                    raise self._error(f"Expected 'command' after 'run' but got {cmd_tok.type} ({cmd_tok.value})")
                self.eat("KEYWORD")  # command
                str_tok = self.eat("STRING")
                command = str_tok.value[1:-1]  # strip surrounding quotes
                flags = None
                if self.current_token().type == "BRACKET" and self.current_token().value == "{":
                    flags = self.block()
                return CommandNode(command, flags)
                
            if tok.value == "for":
                self.eat("KEYWORD")
                # Parse target: allow a single identifier or an unpacking tuple/list
                if self.current_token().type == "SYMBOL" and self.current_token().value == "(":
                    # Parenthesized unpacking target
                    self.eat("SYMBOL")  # (
                    targets = []
                    self.skip_newlines()
                    if not (self.current_token().type == "SYMBOL" and self.current_token().value == ")"):
                        if self.current_token().type in ("IDENT", "KEYWORD"):
                            targets.append(VarNode(self.eat(self.current_token().type).value))
                        while self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                            self.eat("SYMBOL")
                            self.skip_newlines()
                            targets.append(VarNode(self.eat(self.current_token().type).value))
                    self.skip_newlines()
                    self.eat("SYMBOL")  # )
                    var = TupleNode(targets)
                elif self.current_token().type == "BRACKET" and self.current_token().value == "[":
                    # Bracketed unpacking target
                    self.eat("BRACKET")  # [
                    targets = []
                    self.skip_newlines()
                    if not (self.current_token().type == "BRACKET" and self.current_token().value == "]"):
                        if self.current_token().type in ("IDENT", "KEYWORD"):
                            targets.append(VarNode(self.eat(self.current_token().type).value))
                        while self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                            self.eat("SYMBOL")
                            self.skip_newlines()
                            targets.append(VarNode(self.eat(self.current_token().type).value))
                    self.skip_newlines()
                    self.eat("BRACKET")  # ]
                    var = ListNode(targets)
                else:
                    # Support bare unpacking: `for a, b in iterable` (no parentheses)
                    if self.current_token().type in ("IDENT", "KEYWORD"):
                        first_name = self.eat(self.current_token().type).value
                        if self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                            targets = [VarNode(first_name)]
                            while self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                                self.eat("SYMBOL")
                                self.skip_newlines()
                                if self.current_token().type in ("IDENT", "KEYWORD"):
                                    targets.append(VarNode(self.eat(self.current_token().type).value))
                                else:
                                    raise self._error("Expected identifier in unpacking target")
                            var = TupleNode(targets)
                        else:
                            var = VarNode(first_name)
                            var_type = None
                            if self.current_token().type == "SYMBOL" and self.current_token().value == ":":
                                var_type = self._parse_type_annotation(allow_ident=True)
                            var.var_type = var_type
                    else:
                        raise self._error("Expected identifier for for-loop target")
                self.eat("KEYWORD") # in
                iterable = self.special_expr()
                body = self.block()
                return ForNode(var, iterable, body)

            if tok.value in ("def", "func"):
                self.eat("KEYWORD")
                if self.current_token().type in ("IDENT", "KEYWORD"):
                    name = self.eat(self.current_token().type).value
                else:
                    tok_name = self.current_token()
                    raise self._error(
                        f"Expected function name, got {tok_name.type} ({tok_name.value})"
                    )
                self.eat("SYMBOL") # (
                params = []
                param_types = {}
                if self.current_token().value != ")":
                    p_tok = self.current_token()
                    if p_tok.type in ("IDENT", "KEYWORD"):
                        pname = self.eat(p_tok.type).value
                        params.append(pname)
                        ptype = self._parse_type_annotation(allow_ident=True)
                        if ptype:
                            param_types[pname] = ptype
                    else:
                            raise self._error("Expected parameter name in function definition")
                    while self.current_token().value == ",":
                        self.eat("SYMBOL")
                        p_tok = self.current_token()
                        if p_tok.type in ("IDENT", "KEYWORD"):
                            pname = self.eat(p_tok.type).value
                            params.append(pname)
                            ptype = self._parse_type_annotation(allow_ident=True)
                            if ptype:
                                param_types[pname] = ptype
                        else:
                            raise self._error("Expected parameter name in function definition")
                self.eat("SYMBOL") # )
                body = self.block()
                return FuncNode(name, params, body, param_types)

            if tok.value == "class":
                self.eat("KEYWORD")
                if self.current_token().type in ("IDENT", "KEYWORD"):
                    name = self.eat(self.current_token().type).value
                else:
                    tok_name = self.current_token()
                    raise self._error(
                        f"Expected class name, got {tok_name.type} ({tok_name.value})"
                    )
                self.eat("SYMBOL") # (
                fields = []
                field_types = {}
                if self.current_token().value != ")":
                    fname = self.eat("IDENT").value
                    fields.append(fname)
                    ftype = self._parse_type_annotation(allow_ident=True)
                    if ftype:
                        field_types[fname] = ftype
                    while self.current_token().value == ",":
                        self.eat("SYMBOL")
                        fname = self.eat("IDENT").value
                        fields.append(fname)
                        ftype = self._parse_type_annotation(allow_ident=True)
                        if ftype:
                            field_types[fname] = ftype
                self.eat("SYMBOL") # )
                body = self.block()
                return ClassNode(name, fields, body, field_types)

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
                # Allow keywords as module names
                name = self.eat(self.current_token().type).value
                if self.current_token().value == "as":
                    self.eat("KEYWORD")
                    alias = self.eat("IDENT").value
                    return ImportAsNode(name, alias)
                return ImportNode(name)

            if tok.value == "from":
                self.eat("KEYWORD")
                lib = self.eat(self.current_token().type).value
                self.eat("KEYWORD") # import
                # Allow keywords as imported names
                lib_names = []
                if tok.type == "ARITH":
                    while tok.type == "NEWLINE":
                        lib_names.append(self.eat(self.current_token().type).value)
                else:
                    lib_names.append(self.eat(self.current_token().type).value)
                return ImportFromNode(lib, lib_names)

            if tok.value == "return":
                self.eat("KEYWORD")
                return ReturnNode(self.special_expr())

            if tok.value == "break":
                self.eat("KEYWORD")
                return BreakNode()

            if tok.value in ["continue", "skip"]:
                self.eat("KEYWORD")
                return ContinueNode()

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
                    t = self.tokens[self.pos]
                    self.pos += 1
                    if t.type == "BRACKET" and t.value == "{":
                        depth += 1
                    elif t.type == "BRACKET" and t.value == "}":
                        depth -= 1
                        if depth == 0:
                            break
                    if t.type == "NEWLINE":
                        raw += "\n"
                    elif t.type == "WHITESPACE":
                        raw += t.value
                    else:
                        token_str = t.value
                        if raw and not raw.endswith((" ", "\n")):
                            prev_char = raw[-1]
                            if prev_char in ("(", "[", "{", "."):
                                raw += token_str
                            elif token_str in (")", "]", "}", ",", ":", ";", "."):
                                raw += token_str
                            elif token_str in ("(", "[", "{"):
                                raw += token_str
                            else:
                                raw += " " + token_str
                        else:
                            raw += token_str
                lines = raw.split("\n")
                non_empty = [l for l in lines if l.strip()]
                if non_empty:
                    min_indent = min(len(l) - len(l.lstrip()) for l in non_empty)
                    lines = [l[min_indent:] if len(l) >= min_indent and l.strip() else l for l in lines]
                return PyNode("\n".join(lines).strip("\n"))

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