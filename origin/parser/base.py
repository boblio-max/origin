"""Base parser: state, helpers, token consumption."""
import sys
import textwrap
from ..lexer.lexer_point import lex, Token
from ..classes import *
from ..errors import ParseError


class BaseParser:
    """Deterministic recursive-descent parser (base: state + helpers)."""
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

    def eat_line(self):
        string = ""
        while self.current_token().type != "NEWLINE":
            part = self.eat(self.current_token().type)
            string += part.value
        return string

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

