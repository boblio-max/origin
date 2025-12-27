from lexer import lex, Token
from parser import Parser, ProgramNode, NumberNode, BinOpNode, VarNode, AssignNode, PrintNode

# Example code as if it were in code.txt
code_lines = []
with open("code.txt", 'r') as file:
        for line in file:
            code_lines.append(line.strip())

# 1. Tokenize the code
tokens = lex(code_lines)

# Optional: append EOF token if lexer doesn't
tokens.append(Token("EOF", "", -1, -1))

# 2. Parse tokens into an AST
parser = Parser(tokens)
ast = parser.program()

# 3. Print the resulting AST
print(ast)
