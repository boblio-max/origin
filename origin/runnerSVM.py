# Bytecode runner with optional Rust VM acceleration.
#
# Usage:
#   python runnerSVM.py [r|p] <file.or>
#   python -m origin.runnerSVM [r|p] <file.or>
#
# r = Rust VM via my_rust_module (falls back to Python sVM if unavailable)
# p = Python sVM (default, always works)
import json
import os
import sys
import time
from pathlib import Path

# Support both `python origin/runnerSVM.py` and `python -m origin.runnerSVM`
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

try:
    from lexer import lex
    from parser import Parser
    from bc.byteKey import OpCode  # noqa: F401 (re-export check)
    from bc.to_byte import Compiler
    from bc.svm import sVM
except ImportError:  # pragma: no cover - fallback for -m invocation
    from origin.lexer import lex
    from origin.parser import Parser
    from origin.bc.byteKey import OpCode  # noqa: F401
    from origin.bc.to_byte import Compiler
    from origin.bc.svm import sVM


def _resolve_or_file(code_name):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        code_name,
        os.path.join(os.getcwd(), code_name),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    raise FileNotFoundError(f"file not found: {code_name} (tried {candidates})")


def _run_python(bytecode, constants):
    vm = sVM(bytecode, constants)
    vm.run()


def _run_rust(bytecode, constants):
    """Try the Rust VM. Returns True if Rust handled it, False to fall back."""
    try:
        import my_rust_module
    except ImportError:
        print("[runnerSVM] my_rust_module not built; falling back to Python sVM.")
        print("[runnerSVM] Build it with: maturin develop -m origin/bc/rust_implementation/Cargo.toml")
        return False

    # Prefer direct call (no sockets); fall back to TCP handoff for legacy servers.
    run_fn = getattr(my_rust_module, "run_bytecode", None)
    if run_fn is not None:
        # Build JSON-safe constants via a throwaway compiler helper
        tmp = Compiler("vm")
        tmp.bytecode, tmp.constants = bytecode, constants
        _, safe_constants = tmp.to_payload()
        try:
            run_fn(bytecode, json.dumps(safe_constants))
            return True
        except Exception as e:
            print(f"[runnerSVM] Rust VM failed ({e}); falling back to Python sVM.")
            return False

    # Legacy path: my_rust_module.svm() starts a blocking server; don't call it
    # here. Instead use the compiler's TCP handoff if a server is listening.
    print("[runnerSVM] my_rust_module has no run_bytecode(); using TCP handoff.")
    try:
        tmp = Compiler("vm")
        tmp.bytecode, tmp.constants = bytecode, constants
        tmp.send_to_rust()
        return True
    except Exception as e:
        print(f"[runnerSVM] Rust TCP handoff failed ({e}); falling back to Python sVM.")
        return False


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    mode = "p"
    code_name = None
    if argv and argv[0] in ("r", "p", "rust", "python"):
        mode = "r" if argv.pop(0).startswith("r") else "p"
    if argv:
        code_name = argv[0]
    if mode == "p" and code_name is None and len(sys.argv) <= 1:
        # Backwards-compat interactive prompts
        mode = (input("Using Rust or python (r,p): ").strip().lower() or "p")
        mode = "r" if mode.startswith("r") else "p"
        code_name = input("Enter the name of the code file: ").strip()
    if not code_name:
        print("Usage: python runnerSVM.py [r|p] <file.or>")
        sys.exit(2)

    path = _resolve_or_file(code_name)
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        code_lines = [line.rstrip("\n") for line in f]

    start_time = time.perf_counter()
    tokens = lex(code_lines)
    ast = Parser(tokens).program()

    compiler = Compiler("r" if mode == "r" else "vm")
    compiler.compile(ast)

    if hasattr(compiler, "print"):
        try:
            compiler.print()
        except Exception:
            pass

    if mode == "r":
        handled = _run_rust(compiler.bytecode, compiler.constants)
        if not handled:
            _run_python(compiler.bytecode, compiler.constants)
    else:
        _run_python(compiler.bytecode, compiler.constants)

    elapsed = time.perf_counter() - start_time
    print(f"seconds elapsed: {elapsed}s")


if __name__ == "__main__":
    main()
