"""
runnerAlt.py

This module provides an alternative execution script for the language.
It reads a source file, tokenizes it using the lexer, parses the tokens
into an Abstract Syntax Tree (AST), and uses the interpreter to generate
Python code which is then executed. It measures the execution time of the entire process.
"""

from lexer import lex
from parser import Parser
from interpreter import interpreter
from parallelInt import parallelInt
import os, sys
import time

# Clear the terminal screen for clean output
# os.system('cls')

code_lines = []

print("Enter the name of the code file")

name = input()

def find_or_files(folder: str) -> list[str]:
    matches = []
    for root, _, files in os.walk(folder):
        for file in files:
            if file.endswith(".or"):
                matches.append(os.path.join(root, file))
    return matches


folder = sys.argv[1] if len(sys.argv) > 1 else "."
files = find_or_files(folder)
if not files:
    print("No .or files found.")
else:
    with open("classes.txt", "w", encoding="utf-8") as out:
        for path in files:
            header = f"\n{'='*40}\n{path}\n{'='*40}\n"
            # print(header, end="")
            out.write(header)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            # print(content)
            out.write(content + "\n")
    
# Read the target source code file to be interpreted
code_name = name
try:
    with open(f"TESTS(Or)\\{code_name}", 'r') as file:
        for line in file:
            code_lines.append(line.strip())
except FileNotFoundError:
    print("file not found, defaulting")
    with open("TESTS(Or)\\code.or", 'r', encoding="utf-8") as file:
        for line in file:
            code_lines.append(line.strip())

# 1. Tokenize the code using the lexer
start_time = time.perf_counter()
tokens = lex(code_lines)
# print(tokens)
# 2. Parse tokens into an Abstract Syntax Tree (AST)
parser = Parser(tokens)
ast = parser.program()
par_ast = str(ast)
# Display the generated AST for debugging
# print("Generated AST:", ast)
# astStr = str(ast)
# print(astStr)

# map = runMap()
# map.gen(astStr)
# 3. Interpret the AST to generate equivalent Python code
origin = interpreter()
origin_code = origin.generate(ast)
# If interpreter inlined modules we mark their end with '# END_MODULE: <name>'.
# Insert a marker for the main source file after the last inlined module so
# generated Python shows module code first, then the main file (as you wanted).
if "# END_MODULE:" in origin_code:
    last_idx = origin_code.rfind("# END_MODULE:")
    # find end of line after the marker
    nl_idx = origin_code.find("\n", last_idx)
    if nl_idx == -1:
        nl_idx = len(origin_code)
    origin_code = origin_code[: nl_idx + 1] + f"# {code_name}\n" + origin_code[nl_idx + 1 :]
else:
    origin_code = f"# {code_name}\n" + origin_code

# print(origin_code)
exec(origin_code)

end_time = time.perf_counter()
elapsed_time = end_time - start_time
print(f"Execution completed in {elapsed_time:.4f} seconds.")





