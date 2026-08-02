"""lexer

Lightweight lexical analyzer for the origin language.

This module exposes a small, deterministic lexer that converts source code
lines into a flat sequence of :class:`Token` objects. Token patterns are
declared in ``TOKEN_REGEX`` and compiled once for efficiency.
"""

import re


# Ordered list of regular-expression patterns mapping to token type names.
TOKEN_REGEX = [
    (r"[ \t]+",              "WHITESPACE"),# Preserve whitespace for py{} blocks
    (r"#.*",                 None),       # Ignore comments
    (r"\n",                  "NEWLINE"),  # Newline characters
    (r"0x[0-9a-fA-F]+",      "HEX"),      # Hexadecimal numbers
    (r"\d+\.?\d*[eE][+-]?\d+", "FLOAT"),  # Scientific notation (e.g. 5e-5, 1.5E10)
    (r"\d+\.\d+",            "FLOAT"),    # Floating-point numbers
    (r"\d+",                 "INT"),      # Integer numbers
    (r"[fF]\".*?\"|[fF]'.*?'", "FSTRING"), # Formatted f-strings
    (r"\".*?\"|'.*?'",       "STRING"),   # String literals
    (r"===|!==|==|!=|<=|>=|<>|<|>", "COMP"), # Comparison operators
    (r"\&\&|\|\||\b(and|or|not)\b|!", "LOGIC"),    # Logical operators
    (r"\+\+|\-\-",           "UNARY"),    # Unary operators
    (r"\+=|\-=|\*=|\/=|\%=|\*\*=|\/\/=|&=|\|=", "ASSIGN_OP"), # Compound assignment operators
    (r"\?\?|->|=>|<=>|::",   "SPECIAL"),  # Special operators
    (r"=",                   "ASSIGN"),   # Assignment operator
    (r"\+|\-|\*\*|\*|\/\/|\/|\%|\&|\||\^|<<|>>", "ARITH"), # Arithmetic and bitwise operators
    (r"\[|\]|\{|\}",         "BRACKET"),  # Brackets and braces
    (r"\(|\)|:|,|\.|;|\?",   "SYMBOL"),   # Symbols and punctuation
    (r"\b(none|if|elif|else|for|to|while|write|pi|with|return|py|int|read|len|str|sqrt|float|let|rand_num|const|in|print|true|exec|false|abs|floor|ceil|append|address|accel|gyro|temp|break|input|skip|continue|def|func|import|from|class|try|call|except|set|ifinstance|pass|as|bool|parallel|range|self)\b", "KEYWORD"), # Reserved keywords
    (r"\b(mpu6050|mpu9250|mpu6500|mpu9255|mpu6000|mpu9150|mpu9256|mpu9257|mpu9258|mpu9259)\b", "IMU"), # IMU keywords
    (r"[A-Za-z_][A-Za-z0-9_]*", "IDENT"), # Identifiers
]

# Precompile patterns for performance.
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

    Args:
        code_lines (iterable[str]): Source lines.

    Returns:
        list[Token]: Token sequence ending with an ``EOF`` token.
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
                        # Normalize keyword token text to lowercase for parser convenience
                        if t == "KEYWORD":
                            text = text.lower()
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
    """Return the token type name for an input string, or ``None``."""
    for pattern, token_type in TOKEN_REGEX_COMPILED:
        if pattern.fullmatch(TOKEN):
            return token_type
    return None
