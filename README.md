# Origin Programming Language · v1.7.28

**Origin** is my programming language — English-like syntax, strict typing, hardware-first (GPIO/servo primitives for Raspberry Pi), and the full Python ecosystem underneath. this repo is the stable release: `pip install origin-or` and you're writing `.or` files. dev chaos happens in `origin-dev`; this is the polished snapshot.

docs live at [docs-origin.onrender.com](https://docs-origin.onrender.com).

## what's new in v1.7.28

- **dialect support (TOML)** — mix foreign-language lines straight into `.or` programs. each line is looked up in the bundled `origin.toml` (`"<origin source>" _ "<dialect line>"`) and compiled to real Origin before execution, including `$name` template captures (e.g. `"let $n:int = $v" _ "$n:$v"` turns `x:5` into `let x:int = 5`). expansion is inline, sharing constants and control flow.
- **dialect-aware runner** — `origin/runner.py` preloads `origin.toml`, precompiles exact mappings to `origin_bytecode.toml`, resolves templates at parse time. interpreter mode (`origin i`) skips dialect lines; use default VM mode.
- fresh `origin.exe` + `OriginInstallerV1.7.28.zip`, carried-over modular layout (lexer/parser/interpreter/classes subpackages) with the bytecode VM as default backend.

## quickstart

```powershell
git clone https://github.com/boblio-max/origin.git
pip install -r requirements.txt
```

```origin
let x: int = 10
let name: str = "Origin"
let flag: bool = true
const e: float = 2.71828

let a, b = 1, 2
print x + a
```

```bash
python -m origin main.or    # bytecode VM (default)
python -m origin i main.or  # AST interpreter
```

## how it actually works

`origin/` package pipeline: `lexer.py` tokenizes → `parser.py` builds the AST → either `bc/to_byte.py` compiles to bytecode for `bc/svm.py` (the stack VM, default) or the interpreter generates Python and `exec`s it. `dialect.py` + `origin.toml` handle the foreign-line expansion before parsing. `errors.py` gives friendly diagnostics with suggestions instead of raw tracebacks.

## features

English-like syntax · strict (recommended) type annotations with inference · classes/OOP · `try/except/else` · `parallel` thread blocks · module system (`import math as m`, `from lib import x`) · `.or` library imports (`calc.or`, `graph.or`) · hardware I/O (GPIO, ServoKit/PCA9685 with 0–180° servo clamping) · binary builder (PyInstaller `.exe`) · binary + `install.sh`/`secure_install.ps1` installers.

## stack

Python 3.10+, zero runtime deps (extras: Pi/servo libs, pyinstaller for builds). see `requirements.txt`, `setup.py`, `helloworld.or`.
