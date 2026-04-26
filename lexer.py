"""lexer

Lightweight lexical analyzer for the origin language.

This module exposes a small, deterministic lexer that converts source code
lines into a flat sequence of :class:`Token` objects. Token patterns are
declared in ``TOKEN_REGEX`` and compiled once for efficiency.

The lexer is intentionally simple and geared toward predictable, readable
token streams for the recursive-descent parser in ``parser.py``.
"""

import re

# Ordered list of regular-expression patterns mapping to token type names.
# Each tuple is (pattern, token_type). A token_type of ``None`` means the
# pattern is skipped (comments, whitespace, etc.). Order matters: the lexer
# tests patterns sequentially and consumes the first match.
TOKEN_REGEX = [
    (r"[ \t]+|None",         None),       # Ignore whitespace and 'None'
    (r"#.*",                 None),       # Ignore comments
    (r"\n",                  "NEWLINE"),  # Newline characters
    (r"0x[0-9a-fA-F]+",      "HEX"),      # Hexadecimal numbers
    (r"\d+\.\d+",            "FLOAT"),    # Floating-point numbers
    (r"\d+",                 "INT"),      # Integer numbers
    (r"\".*?\"|'.*?'",       "STRING"),   # String literals
    (r"===|!==|==|!=|<=|>=|<>|<|>", "COMP"), # Comparison operators
    (r"\&\&|\|\||\b(and|or|not)\b|!", "LOGIC"),    # Logical operators
    (r"\+\+|\-\-",           "UNARY"),    # Unary operators
    (r"\+=|\-=|\*=|\/=|\%=|\*\*=|\/\/=|&=|\|=", "ASSIGN_OP"), # Compound assignment operators
    (r"\?\?|->|=>|<=>|::",   "SPECIAL"),  # Special operators
    (r"=",                   "ASSIGN"),   # Assignment operator
    (r"\+|\*\*|\*|\/\/|\/|\%|\&|\||\^|<<|>>", "ARITH"), # Arithmetic and bitwise operators
    (r"\-",                 "negate"),    # Negation operator
    (r"\[|\]|\{|\}",         "BRACKET"),  # Brackets and braces
    (r"\(|\)|:|,|\.|;|\?",   "SYMBOL"),   # Symbols and punctuation
    (r"\b(if|elif|open|else|check|for|get|while|return|py|int|len|str|sqrt|float|let|rand_num|const|in|print|true|exec|false|break|input|continue|def|import|from|class|try|call|except|raise|set|pass|yield|with|as|del|assert|global|nonlocal|async|await|match|case|macro|inline|parallel|when|range|unless|loop|until|do|struct|enum|type|bool|interface|pub|priv)\b", "KEYWORD"), # Reserved keywords
    (r"[A-Za-z_][A-Za-z0-9_]*", "IDENT"), # Identifiers
]

# Precompile patterns for performance. Each entry is (compiled_pattern, type).
TOKEN_REGEX_COMPILED = [(re.compile(r), t) for r, t in TOKEN_REGEX]

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

def lex(code_lines):
    """Convert an iterable of source lines into a token list.

    The function returns a list of :class:`Token` objects finished by a
    terminal ``EOF`` token. Each input line produces a trailing ``NEWLINE``
    token so the parser can reason about line-oriented constructs.

    Args:
        code_lines (iterable[str]): Source lines (typically read from a file
            or supplied by the REPL).

    Returns:
        list[Token]: Token sequence ending with an ``EOF`` token.

    Raises:
        SyntaxError: When an unexpected character is encountered.
    """
    tokens = []
    line_num = 1
    for line in code_lines:
        col = 0
        length = len(line)
        while col < length:
            match = None
            for r, t in TOKEN_REGEX_COMPILED:
                match = r.match(line, col)
                if match:
                    text = match.group(0)
                    if t is not None:
                        tokens.append(Token(t, text, line_num, col))
                    col += len(text)
                    break
            if not match:
                raise SyntaxError(f"Illegal Character {line[col]!r} at {line_num}:{col}")
        tokens.append(Token("NEWLINE", "\\n", line_num, col))
        line_num += 1
    tokens.append(Token("EOF", "", line_num, 0))
    return tokens

def return_token_type(TOKEN):
    """Return the token type name for an input string, or ``None``.

    This helper tests the input against the compiled token patterns and returns
    the associated token type name (the second element of each ``TOKEN_REGEX``
    entry). If no pattern matches the full input string, ``None`` is returned.

    Args:
        TOKEN (str): Exact token text to classify.

    Returns:
        Optional[str]: Token type name, or ``None`` when the text is unknown.
    """
    for pattern, token_type in TOKEN_REGEX_COMPILED:
        if pattern.fullmatch(TOKEN):
            return token_type
    return None
