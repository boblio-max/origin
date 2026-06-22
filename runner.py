"""runner

Main entry point for the Origin programming language.
Usage: origin <file.or>
"""

import sys
import os
import random
import math

# Add current directory to path so we can find lexer, parser, interpreter, errors
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lexer import lex
from parser import Parser
from interpreter import Interpreter, _execute_set_pin, _execute_i2c_read, _execute_i2c_write
from errors import report_error, translate_python_error

def run_origin(file_path):
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)

    abs_file_path = os.path.abspath(file_path)

    with open(abs_file_path, "r", encoding="utf-8") as f:
        code_lines = [line.rstrip("\n") for line in f]

    try:
        # 1. Lexical Analysis
        tokens = lex(code_lines)
        
        # 2. Parsing
        parser = Parser(tokens)
        ast = parser.program()
        
        # 3. Code Generation
        interp = Interpreter()
        generated_python = interp.generate(ast)
        
        # 4. Execution
        # We store the runtime line in a dictionary that will be shared with the exec globals
        # so it's accessible everywhere.
        runtime_globals = {
            "random": random,
            "math": math,
            "__name__": "__main__",
            "_execute_set_pin": _execute_set_pin,
            "_execute_i2c_read": _execute_i2c_read,
            "_execute_i2c_write": _execute_i2c_write,
            "_origin_runtime_line": 0,  # Default
        }
        
        # Ensure we are in the directory of the file being run
        original_cwd = os.getcwd()
        file_dir = os.path.dirname(os.path.abspath(file_path))
        if file_dir:
            os.chdir(file_dir)
            
        try:
            exec(generated_python, runtime_globals)
        except Exception as e:
            # Smart Error Handling
            exc_type, exc_value, exc_traceback = sys.exc_info()
            
            # Get the line number from the runtime globals
            line_num = runtime_globals.get("_origin_runtime_line", 0)
            
            # Translate the error message
            friendly_msg = translate_python_error(exc_type, exc_value)
            
            # Report the error beautifully
            report_error(abs_file_path, friendly_msg, line_num)
            sys.exit(1)
        finally:
            os.chdir(original_cwd)

    except SyntaxError as se:
        # Lexer or Parser error
        print(f"\n[Syntax Error] {se}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[System Error] {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Origin Programming Language v1.7.6")
        print("Usage: origin <file.or>")
        sys.exit(1)

    target_file = sys.argv[1]
    run_origin(target_file)