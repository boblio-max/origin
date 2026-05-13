# """
# runnerAlt.py

# This module provides an alternative execution script for the language.
# It reads a source file, tokenizes it using the lexer, parses the tokens
# into an Abstract Syntax Tree (AST), and uses the interpreter to generate
# Python code which is then executed. It measures the execution time of the entire process.
# """

# from lexer import lex
# from parser import Parser
# from interpreter import interpreter
# import os
# import time

# # Clear the terminal screen for clean output
# # os.system('cls')

# code_lines = []

# print("Enter the name of the code file")

# name = input()

# # Get the path to the TESTS(Or) directory relative to this script
# base_dir = os.path.dirname(os.path.abspath(__file__))
# tests_dir = os.path.join(base_dir, "..", "TESTS(Or)")
# 
# # Read the target source code file to be interpreted
# code_name = name
# try:
#     with open(os.path.join(tests_dir, code_name), 'r') as file:
#         for line in file:
#             code_lines.append(line.strip())
# except FileNotFoundError:
#     print("default code.or file not found")
#     with open(os.path.join(tests_dir, "code.or"), 'r') as file:
#         for line in file:
#             code_lines.append(line.strip())

# # 1. Tokenize the code using the lexer
# times = time.perf_counter()
# start_time = time.perf_counter()
# tokens = lex(code_lines)
# end_time = time.perf_counter()
# # 2. Parse tokens into an Abstract Syntax Tree (AST)
# start_time1 = time.perf_counter()
# ast = Parser(tokens).program()
# end_time1 = time.perf_counter()

# # Display the generated AST for debugging
# # print("Generated AST:", ast)

# # 3. Interpret the AST to generate equivalent Python code
# start_time2 = time.perf_counter()
# origin_code = interpreter().generate(ast)
# end_time2 = time.perf_counter()

# start_time3 = time.perf_counter()
# exec(origin_code)
# end_time3 = time.perf_counter()
# timee = time.perf_counter()
# elapsed_time = end_time - start_time
# print(f"Lexing completed in {elapsed_time:.4f} seconds.")

# elapsed_time1 = end_time1 - start_time1
# print(f"Parsing completed in {elapsed_time1:.4f} seconds.")

# elapsed_time2 = end_time2 - start_time2
# print(f"Interpretation completed in {elapsed_time2:.4f} seconds.")

# elapsed_time3 = end_time3 - start_time3
# print(f"Execution completed in {elapsed_time3:.4f} seconds.")   

# ttime = timee-times
# print(f"Total time is {ttime:.4f} seconds")