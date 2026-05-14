"""builder

This module provides the compilation logic to turn Origin (.or) scripts
into standalone executables using PyInstaller.
"""

import os
import sys
import subprocess
import shutil

def build_binary(target_file):
    """Compile an Origin file into a standalone executable."""
    if not os.path.exists(target_file):
        print(f"Error: File '{target_file}' not found.")
        return False

    abs_target = os.path.abspath(target_file)
    base_name = os.path.splitext(os.path.basename(abs_target))[0]
    target_dir = os.path.dirname(abs_target)

    # 1. Setup build environment
    build_dir = os.path.join(target_dir, "__origin_build__")
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    os.makedirs(build_dir)

    # 2. Transpile the main script
    from lexer import lex
    from parser import Parser
    from interpreter import Interpreter
    
    print(f"[*] Transpiling {target_file}...")
    with open(abs_target, "r", encoding="utf-8") as f:
        code_lines = [line.rstrip("\n") for line in f]
    
    tokens = lex(code_lines)
    p = Parser(tokens)
    ast = p.program()
    
    interp = Interpreter()
    # Ensure current directory is where the script is so imports work during transpilation
    original_cwd = os.getcwd()
    os.chdir(target_dir)
    try:
        generated_python = interp.generate(ast)
    finally:
        os.chdir(original_cwd)

    # 3. Create the entry point Python file
    # We include the necessary runtime imports and globals
    main_py = os.path.join(build_dir, f"{base_name}_main.py")
    with open(main_py, "w", encoding="utf-8") as f:
        f.write("import math\nimport random\nimport sys\nimport os\n")
        f.write("try:\n    import adafruit_servokit\nexcept ImportError: pass\n")
        f.write("\n# Origin Runtime Globals\n")
        f.write("_origin_runtime_line = 0\n")
        f.write("\n" + generated_python)

    # 4. Invoke PyInstaller
    print(f"[*] Bundling into {base_name}.exe...")
    
    # We need to find where pyinstaller is
    pyinstaller_cmd = os.path.join(os.path.dirname(sys.executable), "pyinstaller")
    if os.name == 'nt':
        pyinstaller_cmd += ".exe"

    cmd = [
        pyinstaller_cmd,
        "--onefile",
        "--clean",
        "--distpath", target_dir,
        "--workpath", os.path.join(build_dir, "build"),
        "--specpath", build_dir,
        f"--name={base_name}",
        main_py
    ]

    # Add the origin cache directory if it exists
    cache_dir = os.path.join(target_dir, "__origin_cache__")
    if os.path.exists(cache_dir):
        cmd.extend(["--paths", cache_dir])

    try:
        subprocess.run(cmd, check=True)
        print(f"[+] Successfully built: {os.path.join(target_dir, base_name + ('.exe' if os.name == 'nt' else ''))}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[-] Build failed: {e}")
        return False
    finally:
        # Cleanup
        # shutil.rmtree(build_dir) # Keep for debugging if needed, or remove
        pass

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python builder.py <file.or>")
        sys.exit(1)
    build_binary(sys.argv[1])
