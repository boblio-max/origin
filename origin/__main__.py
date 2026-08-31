"""Entry point for `python -m origin` and the `origin` CLI command."""

import sys
from .runner import run_origin


def main():
    if len(sys.argv) < 2:
        print("Origin Programming Language v1.7.22")
        print("Usage: origin <file.or>")
        print("       origin i <file.or>   (interpreter mode)")
        sys.exit(1)

    if sys.argv[1] in ("cli","--cli","repl"):
        
    if sys.argv[1] == "i":
        if len(sys.argv) < 3:
            print("Usage: origin i <file.or>")
            sys.exit(1)
        run_origin(sys.argv[2], mode="interp")
    else:
        run_origin(sys.argv[1], mode="vm")


if __name__ == "__main__":
    main()
