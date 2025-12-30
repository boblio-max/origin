import re

# Regex of tokens(like dictionary)
TOKEN_REGEX = [
    (r"[ \t]+",              None),
    (r"#.*",                 None),
    (r"\n",                  "NEWLINE"),
    (r"\d+\.\d+",            "FLOAT"),
    (r"\d+",                 "INT"),
    (r"\".*?\"|'.*?'",       "STRING"),
    (r"===|!==|==|!=|<=|>=|<>|<|>", "COMP"),
    (r"\&\&|\|\||and|or|not|!", "LOGIC"),
    (r"\+\+|\-\-",           "UNARY"),
    (r"\+=|\-=|\*=|\/=|\%=|\*\*=|\/\/=|&=|\|=", "ASSIGN_OP"),
    (r"\?\?|->|=>|<=>|::",   "SPECIAL"),
    (r"=",                   "ASSIGN"),
    (r"\+|\-|\*\*|\*|\/\/|\/|\%|\&|\||\^|<<|>>", "ARITH"),
    (r"\[|\]|\{|\}",         "BRACKET"),
    (r"\(|\)|:|,|\.|;|\?",   "SYMBOL"),
    (r"\b(fn|if|elif|else|for|while|return|int|str|float|let|const|in|print|break|input|continue|import|from|class|try|except|raise|pass|yield|lambda|with|as|del|assert|global|nonlocal|async|await|match|case|macro|inline|parallel|when|range|unless|loop|until|do|struct|enum|type|interface|pub|priv|అడ్మిన్)\b", "KEYWORD"),
    (r"[A-Za-z_][A-Za-z0-9_]*", "IDENT"),
]
# Reduces redundancy and time efficiency of the regex
TOKEN_REGEX_COMPILED = [(re.compile(r), t) for r, t in TOKEN_REGEX]

# Token class
class Token:
    def __init__(self, type_, value, line, col):
        self.type = type_
        self.value = value
        self.line = line
        self.col = col
    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, {self.line}:{self.col})"

def lex(code_lines):
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

