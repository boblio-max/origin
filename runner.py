import sys
import os
def find_or_files(folder: str) -> list[str]:
    matches = []
    for root, _, files in os.walk(folder):
        for file in files:
            if file.endswith(".or"):
                matches.append(os.path.join(root, file))
    return matches

def run_origin(file_path):
    folder = sys.argv[1] if len(sys.argv) > 1 else "."
    files = find_or_files(folder)
    if not files:
        print("No .or files found.")
    else:
        with open("classes.txt", "w", encoding="utf-8") as out:
            for path in files:
                header = f"\n{'='*40}\n{path}\n{'='*40}\n"
                # print(header, end="")
                out.write(header)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                # print(content)
                out.write(content + "\n")
        
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    from lexer import lex
    from parser import Parser
    from interpreter import interpreter, _execute_servo, _get_servo_kit

    with open(file_path, "r") as f:
        code_lines = [line.rstrip("\n") for line in f]

    tokens = lex(code_lines)
    parser = Parser(tokens)
    ast = parser.program()
    origin = interpreter()
    generated = origin.generate(ast)

    exec(generated, {
        "_execute_servo": _execute_servo,
        "_get_servo_kit": _get_servo_kit,
    })

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: origin <file.or>")
        sys.exit(1)

    run_origin(sys.argv[1])