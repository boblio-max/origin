"""
runnerAlt.py

This module provides an alternative execution script for the language.
It reads a source file, tokenizes it using the lexer, parses the tokens
into an Abstract Syntax Tree (AST), and uses the interpreter to generate
Python code which is then executed. It measures the execution time of the entire process.
"""

import sys
import os

# Auto-detect .venv and re-exec with it if not already using it
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_venv_python = os.path.join(_project_root, ".venv", "Scripts", "python.exe")
if os.path.isfile(_venv_python) and sys.executable.lower() != os.path.abspath(_venv_python).lower():
    os.execv(_venv_python, [_venv_python] + sys.argv)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 

from .lexer import lex
from .parser import Parser
from .interpreter import Interpreter
from . import errors
errors.install()
import os, sys
import time

# Clear the terminal screen for clean output
# os.system('cls')

code_lines = []

print("Enter the name of the code file")

name = sys.argv[2] if len(sys.argv) > 2 else input()

def find_or_files(folder: str) -> list[str]:
    matches = []
    for root, _, files in os.walk(folder):
        for file in files:
            if file.endswith(".or"):
                matches.append(os.path.join(root, file))
    return matches


def _normalize_line(s: str) -> str:
    # Replace common “smart” punctuation with ASCII equivalents
    if not s:
        return s
    repl = {
        '\u201c': '"', '\u201d': '"',  # left/right double quotation mark
        '\u2018': "'", '\u2019': "'",  # left/right single quotation mark
        '\u2013': '-', '\u2014': '-',      # en dash, em dash
        '\u2026': '...',                    # ellipsis
        '\u00A0': ' ',                      # non-breaking space
        '\u2010': '-',                      # hyphen
    }
    for k, v in repl.items():
        s = s.replace(k, v)
    return s


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
    # Open with explicit UTF-8 and replace invalid bytes to avoid decoding errors on Windows
    with open(f"TESTS(Or)\\{code_name}", 'r', encoding="utf-8", errors="replace") as file:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache.py"), "w", encoding="utf-8") as f:
            f.write("\"\"\"" + f"TESTS(Or)\\{code_name}" + "\"\"\"\n")
        for line in file:
            code_lines.append(_normalize_line(line).rstrip("\n"))
except FileNotFoundError:
    print("file not found, exiting...")

# 1. Tokenize the code using the lexer
start_time = time.perf_counter()
tokens = lex(code_lines)
print(tokens)
# 2. Parse tokens into an Abstract Syntax Tree (AST)
parser = Parser(tokens)
ast = parser.program()
par_ast = str(ast)
# Display the generated AST for debugging
print("Generated AST:", ast)
print(par_ast)

# 3. Interpret the AST to generate equivalent Python code
origin = Interpreter()
origin_code = origin.generate(ast)
print(origin_code)
# If interpreter inlined modules we mark their end with '# END_MODULE: <name>'.
# Insert a marker for the main source file after the last inlined module so
# generated Python shows module code first, then the main file (as you wanted).
# if "# END_MODULE:" in origin_code:
#     last_idx = origin_code.rfind("# END_MODULE:")
#     # find end of line after the marker
#     nl_idx = origin_code.find("\n", last_idx)
#     if nl_idx == -1:
#         nl_idx = len(origin_code)
#     origin_code = origin_code[: nl_idx + 1] + f"# {code_name}\n" + origin_code[nl_idx + 1 :]
# else:
#     origin_code = f"# {code_name}\n" + origin_code

# # print(origin_code)
# # Make the origin filename available to generated code so errors.report_error can show location
# globals()['_origin_source_file'] = code_name
# # Execute generated code with `errors` available to allow generated snippets to call error helpers
# # print(origin_code)
# with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache.py"), "a", encoding="utf-8") as f:
#     f.write(origin_code)
# exec(origin_code, globals())

end_time = time.perf_counter()
elapsed_time = end_time - start_time
print(f"Execution completed in {elapsed_time:.4f} seconds.")





