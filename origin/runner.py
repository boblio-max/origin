"""runner

Main entry point for the Origin programming language.
Usage: origin <file.or>         # bytecode VM (default)
       origin i <file.or>       # AST-to-Python interpreter
"""

import sys
import os

# Auto-detect .venv and re-exec with it if not already using it
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_venv_python = os.path.join(_project_root, ".venv", "Scripts", "python.exe")
if os.path.isfile(_venv_python) and sys.executable.lower() != os.path.abspath(_venv_python).lower():
    os.execv(_venv_python, [_venv_python] + sys.argv)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from .lexer import lex
from .parser import Parser
from .errors import ParseError, report_error, translate_python_error

try:
    from .bc.to_byte import Compiler
    from .bc.svm import sVM
    _HAVE_BC = True
except ImportError:
    # Standalone builds (origin.exe) ship without the bytecode VM package;
    # fall back to the interpreter backend.
    Compiler = None
    sVM = None
    _HAVE_BC = False


def run_origin(file_path, mode="vm"):
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)

    abs_file_path = os.path.abspath(file_path)

    with open(abs_file_path, "r", encoding="utf-8") as f:
        code_lines = [line.rstrip("\n") for line in f]

    try:
        original_cwd = os.getcwd()
        file_dir = os.path.dirname(os.path.abspath(file_path))
        if file_dir:
            os.chdir(file_dir)

        try:
            tokens = lex(code_lines)
            parser = Parser(tokens)
            ast = parser.program()

            if mode == "vm" and _HAVE_BC:
                compiler = Compiler()
                compiler.compile(ast)
                sVM(compiler.bytecode, compiler.constants).run()
            else:
                import random
                import math
                from .interpreter import Interpreter, _execute_set_pin, _execute_i2c_read, _execute_i2c_write

                interp = Interpreter()
                generated_python = interp.generate(ast)

                runtime_globals = {
                    "random": random,
                    "math": math,
                    "__name__": "__main__",
                    "__file__": abs_file_path,
                    "_execute_set_pin": _execute_set_pin,
                    "_execute_i2c_read": _execute_i2c_read,
                    "_execute_i2c_write": _execute_i2c_write,
                    "_origin_runtime_line": 0,
                }
                exec(generated_python, runtime_globals)
        except ParseError as pe:
            report_error(
                file_path=abs_file_path,
                error_message=pe.message,
                line_num=pe.line,
                col_num=pe.col,
                error_type="Syntax Error",
                suggestion=pe.suggestion,
            )
            sys.exit(1)
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            error_type, friendly_message, suggestion = translate_python_error(exc_type, exc_value)
            report_error(
                file_path=abs_file_path,
                error_message=friendly_message,
                error_type=error_type,
                suggestion=suggestion
            )
            sys.exit(1)
        finally:
            os.chdir(original_cwd)

    except SyntaxError as se:
        print(f"\n[Syntax Error] {se}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[System Error] {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Origin Programming Language v1.7.22")
        print("Usage: origin <file.or>")
        print("       origin i <file.or>   (interpreter mode)")
        sys.exit(1)

    if sys.argv[1] == "i":
        if len(sys.argv) < 3:
            print("Usage: origin i <file.or>")
            sys.exit(1)
        run_origin(sys.argv[2], mode="interp")
    else:
        run_origin(sys.argv[1], mode="vm")
