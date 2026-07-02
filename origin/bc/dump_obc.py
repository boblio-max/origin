"""dump_obc.py — Serialize Compiler output to .obc for the Java VM.

Usage:
    python -m origin.bc.dump_obc path/to/source.or program.obc

or, programmatically:
    from origin.bc.dump_obc import dump
    dump(bytecode_list, constants_list, "out.obc")

The .obc format is the wire contract with Loader.java:

    magic        : "OBC1"            (4 bytes)
    version      : 0x01              (1 byte)
    const_count  : int32 BE
    constants    : repeated [typeTag + payload]
    code_len     : int32 BE
    bytecode     : code_len bytes

Type tags (must match Loader.java readConst):
    0 = LONG       payload = 8 bytes signed
    1 = DOUBLE     payload = 8 bytes IEEE-754
    2 = BOOLEAN    payload = 1 byte
    3 = STRING     payload = int32 len + utf8
    4 = NULL       payload = (empty)
    5 = INT32      payload = 4 bytes signed
    6 = TUPLE      payload = int32 n + n * (tag + payload)   // nested

Python callables stored in compiler.constants (to_byte.py:358, 361, 479,
496) cannot cross the language boundary. We substitute the function's
``__name__`` string at dump time. The Java VM resolves those names
through Builtins.java.
"""

from __future__ import annotations

import io
import struct
import sys
from pathlib import Path
from typing import Any, List

MAGIC = b"OBC1"
VERSION = 1

TAG_LONG = 0
TAG_DOUBLE = 1
TAG_BOOLEAN = 2
TAG_STRING = 3
TAG_NULL = 4
TAG_INT32 = 5
TAG_TUPLE = 6


def _tag_value(v: Any) -> bytes:
    if v is None:
        return struct.pack(">B", TAG_NULL)
    if isinstance(v, bool):
        return struct.pack(">BB", TAG_BOOLEAN, 1 if v else 0)
    if isinstance(v, int):
        # Try int32 first; fall back to long if it overflows.
        if -(2**31) <= v < 2**31:
            return struct.pack(">Bi", TAG_INT32, v)
        return struct.pack(">Bq", TAG_LONG, v)
    if isinstance(v, float):
        return struct.pack(">Bd", TAG_DOUBLE, v)
    if isinstance(v, str):
        b = v.encode("utf-8")
        return struct.pack(">Bi", TAG_STRING, len(b)) + b
    if isinstance(v, (tuple, list)):
        body = struct.pack(">I", len(v))
        for item in v:
            body += _tag_value(item)
        return struct.pack(">B", TAG_TUPLE) + body
    if isinstance(v, dict):
        # On-wire shape for a dict mirrors to_byte.py:389-406 MAKE_CLASS methods
        # table: a flat [key1, value1, key2, value2, ...] list. The Python VM
        # reads it back via pop() and indexes with methods[name]. The element
        # count is 2*len(dict) because each key/value pair contributes two
        # TUPLE elements (matches what Loader.java reads via readConst).
        body = struct.pack(">I", 2 * len(v))
        for k, val in v.items():
            body += _tag_value(k)
            body += _tag_value(val)
        return struct.pack(">B", TAG_TUPLE) + body
    if callable(v):
        # Python builtins / lambdas cross as their __name__.
        return _tag_value(getattr(v, "__name__", repr(v)))
    raise TypeError(f"dump_obc: cannot serialize {type(v).__name__}")


def dump(bytecode: List[int], constants: List[Any], path: str) -> None:
    with open(path, "wb") as f:
        f.write(MAGIC)
        f.write(struct.pack(">B", VERSION))
        f.write(struct.pack(">I", len(constants)))
        for c in constants:
            f.write(_tag_value(c))
        # bytecode is a list[int] in to_byte.py:9 (range 0..255)
        if any(not isinstance(b, int) or b < 0 or b > 255 for b in bytecode):
            raise ValueError("bytecode must be list of bytes 0..255")
        f.write(struct.pack(">I", len(bytecode)))
        f.write(bytes(bytecode))


def dump_compiler_output(bytecode: List[int], constants: List[Any], path: str) -> None:
    dump(bytecode, constants, path)


def _cli(argv: List[str]) -> int:
    if len(argv) < 3:
        sys.stderr.write("usage: dump_obc <source.or> <out.obc>\n")
        return 2
    src, out = argv[1], argv[2]

    # Match runnerByte.py: import origin.bc.to_byte and run its Compiler.
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from ..lexer import lex
    from ..parser import Parser
    from .to_byte import Compiler

    code_lines = [line.rstrip("\n") for line in open(src, "r", encoding="utf-8")]
    tokens = lex(code_lines)
    ast = Parser(tokens).program()
    compiler = Compiler()
    compiler.compile(ast)
    dump(compiler.bytecode, compiler.constants, out)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv))