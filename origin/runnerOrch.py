from lexer import lex
from parser import Parser
from origin.bytecodeCOMPS.bCompS import VM, Compiler
import os
import time

# os.system('cls')
# times = []
# for i in range(10):
code_lines = []


code_name = "code.or"


# Get the path to the TESTS(Or) directory relative to this script
base_dir = os.path.dirname(os.path.abspath(__file__))
tests_dir = os.path.join(base_dir, "..", "TESTS(Or)")

with open(os.path.join(tests_dir, code_name), 'r') as file:
        for line in file:
            code_lines.append(line.strip())

# 1. Tokenize the code
start_time = time.perf_counter()
tokens = lex(code_lines)
# for i in tokens:
#     print(i)
# 2. Parse tokens into an AST
parser = Parser(tokens)
ast = parser.program()
# print(ast)

# 3. Compile AST to bytecode
compiler = Compiler()  
compiler.compile(ast)

# compiler.print()
# 4. Run bytecode on VM


# vm = VM(compiler.bytecode, compiler.constants)
print(compiler.bytecode)
# vm.run()
end_time = time.perf_counter()

# Calculate the elapsed time
elapsed_time = end_time - start_time

print(f"Execution completed in {elapsed_time:.4f} seconds.")

# times.append(elapsed_time) 
# for i in range(len(times)):
#     print(f"Run {i+1}: {times[i]:.4f} seconds") 

