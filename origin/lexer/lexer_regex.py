# Ordered list of regular-expression patterns mapping to token type names.
# Order is critical for overlapping prefixes: multi-char ops must precede their single-char prefixes.
# `!=` must be before `!` (COMP before LOGIC single), `<<` before `<` (ARITH shift before COMP single).
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
    (r"===|!==|==|!=|<=|>=|<>", "COMP"), # Multi-char comparisons (must be before single-char)
    (r"\&\&|\|\|",           "LOGIC"),    # Multi-char logic
    (r"<<|>>",               "ARITH"),    # Shift operators (must be before single < >)
    (r"\b(and|or|not)\b|!",  "LOGIC"),    # Single logic (after multi-char comps)
    (r"<|>",                 "COMP"),     # Single comparisons (after shift)
    (r"\+\+|\-\-",           "UNARY"),    # Unary operators
    (r"\+=|\-=|\*=|\/=|\%=|\*\*=|\/\/=|&=|\|=|\^=|<<=|>>=", "ASSIGN_OP"), # Compound assignment operators
    (r"\?\?|->|=>|<=>|::",   "SPECIAL"),  # Special operators
    (r"=",                   "ASSIGN"),   # Assignment operator
    (r"\+|\-|\*\*|\*|\/\/|\/|\%|\&|\||\^|~", "ARITH"), # Remaining arithmetic/bitwise (without << >>)
    (r"\[|\]|\{|\}",         "BRACKET"),  # Brackets and braces
    (r"\(|\)|:|,|\.|;|\?",   "SYMBOL"),   # Symbols and punctuation
    (r"\b(none|if|elif|else|for|to|while|write|pi|with|return|py|int|run|read|len|str|sqrt|float|let|rand_num|const|in|print|true|exec|false|abs|floor|ceil|append|address|accel|gyro|temp|break|input|skip|continue|def|func|import|from|class|try|call|except|set|ifinstance|pass|as|bool|parallel|range|self|command|match)\b", "KEYWORD"), # Reserved keywords
    (r"\b(mpu6050|mpu9250|mpu6500|mpu9255|mpu6000|mpu9150|mpu9256|mpu9257|mpu9258|mpu9259)\b", "IMU"), # IMU keywords
    (r"[A-Za-z_][A-Za-z0-9_]*", "IDENT"), # Identifiers
]

def get_token_regex():
    """Return the ordered list of token regex patterns."""
    return TOKEN_REGEX