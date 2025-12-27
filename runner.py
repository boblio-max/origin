from lexer import lex
from parser import Parser
from interpreter import Interpreter
# Example code as if it were in code.txt
code_lines = []
with open("code.txt", 'r') as file:
        for line in file:
            code_lines.append(line.strip())

# 1. Tokenize the code
tokens = lex(code_lines)

# 2. Parse tokens into an AST
parser = Parser(tokens)
ast = parser.program()

interpreter = Interpreter()
interpreter.run(ast)
