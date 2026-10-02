"""runner — run Origin programs with TOML-defined dialects.

Dialect mappings ship preinstalled in this package's ``origin.toml`` as::

    "<origin source>" _ "<dialect source line>"

When a program line matches a dialect line, it is compiled to its origin
source and injected into the program's bytecode, which is then executed::

    code.or:            origin.toml:
      x:5                 "let $n:int = $v" _ "$n:$v"
      print x

Usage: origin <file.or>         # bytecode VM (default), dialects resolved
       origin i <file.or>       # AST-to-Python interpreter
"""

import sys
import os
import json

# Auto-detect .venv and re-exec with it if not already using it
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_venv_python = os.path.join(_project_root, ".venv", "Scripts", "python.exe")
if os.path.isfile(_venv_python) and sys.executable.lower() != os.path.abspath(_venv_python).lower():
    os.execv(_venv_python, [_venv_python] + sys.argv)

# Directory that holds origin.toml / origin_bytecode.toml (this package).
_CODE_ROOT = os.path.dirname(os.path.abspath(__file__))

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

from .dialect import normalize_line
from . import dialect as _dialect


def compile_origin(code_line, file_path="<dialect>"):
    """Compile a single origin source line to bytecode.

    Returns ``(bytecode, constants)``. Raises ``ParseError`` / other
    exceptions with a properly sourced diagnostic — callers decide what to do.
    """
    if not _HAVE_BC:
        raise RuntimeError("dialect compilation requires the bytecode VM (bc.to_byte / bc.svm)")

    code_lines = [code_line.strip('"')]
    original_cwd = os.getcwd()
    _prev_enabled = _dialect.enabled()
    _dialect.set_enabled(False)
    try:
        tokens = lex(code_lines)
        parser = Parser(tokens)
        ast = parser.program()
        compiler = Compiler()
        compiler.compile(ast)
        return compiler.bytecode, compiler.constants
    except ParseError as pe:
        report_error(
            file_path=file_path,
            error_message=pe.message,
            line_num=pe.line,
            col_num=pe.col,
            error_type="Syntax Error",
            suggestion=pe.suggestion,
        )
        raise
    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        error_type, friendly_message, suggestion = translate_python_error(exc_type, exc_value)
        report_error(
            file_path=file_path,
            error_message=friendly_message,
            error_type=error_type,
            suggestion=suggestion,
        )
        raise
    finally:
        _dialect.set_enabled(_prev_enabled)
        os.chdir(original_cwd)


def parse_mapping_line(line):
    """Split one origin.toml line into (origin_source, dialect_line), or None."""
    line = line.strip()
    if not line or " _ " not in line:
        return None
    left, _, right = line.partition(" _ ")
    left = left.strip().strip('"').strip("'").strip()
    right = right.strip().strip('"').strip("'").strip()
    if not left or not right:
        return None
    return left, right


def _toml_value(value):
    """Convert a compiler constant to a TOML literal, or raise ValueError."""
    if value is None:
        raise ValueError("None is not representable in TOML")
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, (list, tuple)):
        return "[ " + ", ".join(_toml_value(v) for v in value) + " ]"
    raise ValueError(f"unsupported constant {type(value).__name__}")


def dump_table(entries):
    """Serialize entries to real TOML (inline tables); fallback to str(dict)."""
    try:
        lines = []
        for key, payload in entries.items():
            bc = ", ".join(_toml_value(v) for v in payload["bytecode"])
            cs = ", ".join(_toml_value(v) for v in payload["constants"])
            lines.append(
                f'{json.dumps(key)} = {{ bytecode = [ {bc} ], constants = [ {cs} ] }}'
            )
        return "\n".join(lines) + "\n"
    except (ValueError, TypeError):
        return str(entries) + "\n"


def build_table():
    """Compile every origin.toml mapping and write origin_bytecode.toml."""
    origin_path = os.path.join(_CODE_ROOT, "origin.toml")
    out_path = os.path.join(_CODE_ROOT, "origin_bytecode.toml")

    entries = {}
    if os.path.isfile(origin_path):
        with open(origin_path, "r", encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f]
        for line in lines:
            mapping = parse_mapping_line(line)
            if mapping is None:
                continue
            origin_source, dialect_line = mapping
            if "$" in origin_source or "$" in dialect_line:
                # Templated mappings have unbounded variants and are compiled
                # inline at parse time; they cannot be precompiled here.
                continue
            try:
                bytecode, constants = compile_origin(origin_source, file_path=origin_path)
            except Exception:
                continue
            entries[normalize_line(dialect_line)] = {
                "bytecode": bytecode,
                "constants": constants,
            }

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(dump_table(entries))
    return entries


def ensure_table():
    """Best-effort refresh of the precompiled dialect table.

    Exact (non-templated) mappings are also expanded inline at parse time, so
    the precompiled table is a legacy fallback. Rebuild only when origin.toml
    is newer or the table is missing, and stay quiet if the package directory
    is not writable (e.g. system installs).
    """
    origin_path = os.path.join(_CODE_ROOT, "origin.toml")
    out_path = os.path.join(_CODE_ROOT, "origin_bytecode.toml")
    if not os.path.isfile(origin_path):
        return
    if os.path.isfile(out_path) and os.path.getmtime(out_path) >= os.path.getmtime(origin_path):
        return
    try:
        build_table()
    except OSError:
        pass


def run_origin(file_path, mode="vm"):
    """Compile and run a .or file, resolving dialect lines through origin.toml."""
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)

    abs_file_path = os.path.abspath(file_path)

    with open(abs_file_path, "r", encoding="utf-8") as f:
        code_lines = [line.rstrip("\n") for line in f]

    if mode == "vm" and _HAVE_BC:
        ensure_table()

    original_cwd = os.getcwd()
    try:
        file_dir = os.path.dirname(abs_file_path)
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
        print("Origin Programming Language v1.7.30")
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
