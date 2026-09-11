import re
from .token import *
from .lexer_regex import *
TOKEN_REGEX_COMPILED = [(re.compile(pattern), token_type) for pattern, token_type in get_token_regex()]
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