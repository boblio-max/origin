# origin

origin is the v1.7.5 reference implementation of the Origin programming language — a Python-implemented, English-like language with strict type annotations, native hardware primitives (Raspberry Pi GPIO, ServoKit/PCA9685), a module system, OOP, and a binary builder that produces standalone `.exe` files via PyInstaller. Source files are `lexer.py`, `parser.py`, `interpreter.py`, `classes.py`, `errors.py`, with `runner.py` as the entry point.

## Build / Test / Lint Commands

- Install: `pip install -r requirements.txt` (adafruit-circuitpython-servokit, RPi.GPIO, pyinstaller)
- Build: `python runner.py path/to/script.or` runs an Origin script; `origin build main.or` (when installed standalone) builds a binary
- Test: no automated tests are wired in; verify by running the language reference snippets from the README
- Lint: not configured
- Dev / run:
  - From repo root: `python runner.py <file>.or`
  - Standalone (after installer): `origin main.or`

## Code Style Rules

- Language/version: Python 3.10+
- Paradigm: classic interpreter pipeline (lexer → parser → AST → AST-to-Python codegen → `exec`); `classes.py` defines the language's type system
- Types: type hints on interpreter methods; runtime type checks per Origin's strict-typing rules
- Formatting: PEP 8 (no formatter configured)
- Imports / module style: flat module layout — `from classes import *`, `from lexer import lex`, `from parser import Parser`
- Dependencies: `adafruit-circuitpython-servokit`, `RPi.GPIO`, `pyinstaller` (RPi.GPIO is Linux-only)

## Verification Criteria

Before claiming any task done, you MUST:
1. Run `python -c "from runner import run_origin; from interpreter import Interpreter; from lexer import lex; from parser import Parser"` to confirm core modules import.
2. Confirm `pip install -r requirements.txt` succeeds (on Windows, expect `RPi.GPIO` to fail — that is acceptable on non-Pi dev boxes; document the skip in the final report).
3. Boot `python runner.py` against a small example Origin file (e.g. a `print` statement) and confirm it executes.
4. Report the exact commands run and their outcomes in the final message.