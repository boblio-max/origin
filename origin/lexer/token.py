class Token:
    """Immutable token value produced by :func:`lex`.

    Attributes:
        type (str): Token type name (for example, ``INT``, ``IDENT``, ``KEYWORD``).
        value (str): The original source text matched by the token.
        line (int): 1-based source line number where the token appears.
        col (int): 0-based column index where the token starts on the line.
    """
    def __init__(self, type_, value, line, col):
        self.type = type_
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, {self.line}:{self.col})"

