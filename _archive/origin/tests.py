"""
runnerAlt_benchmark.py

Benchmark:
- Tree-walk interpreter (AST â†’ Python exec)
- Bytecode pipeline (Lexer â†’ Parser â†’ Compiler â†’ VM timing)

Outputs:
- Statistical table
- Bar chart comparison
- Optional run-by-run trend graph
"""

from lexer import lex
from parser import Parser
from interpreter import Interpreter
from origin.bytecodeCOMPS.bCompS import VM, Compiler

import os
import time
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from tqdm import tqdm

# =========================================================
# CONFIG
# =========================================================

TEST_NUM = 1000
FILE_NAME = "code.or"


# =========================================================
# DATA STORAGE
# =========================================================

interp_times = []
byte_times = []


# =========================================================
# LOAD SOURCE CODE
# =========================================================

def load_code():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    tests_dir = os.path.join(base_dir, "..", "TESTS(Or)")
    path = os.path.join(tests_dir, FILE_NAME)

    try:
        with open(path, "r") as f:
            return [line.strip() for line in f]
    except FileNotFoundError:
        print("Fallback: code.or not found")
        fallback = os.path.join(tests_dir, "code.or")
        with open(fallback, "r") as f:
            return [line.strip() for line in f]


# =========================================================
# INTERPRETER BENCHMARK
# =========================================================

for i in tqdm(range(TEST_NUM), desc="Interpreter Benchmark"):

    code_lines = load_code()

    start = time.perf_counter()

    tokens = lex(code_lines)
    ast = Parser(tokens).program()
    origin = Interpreter().generate(ast)

    exec(origin)

    end = time.perf_counter()

    interp_times.append(end - start)


# =========================================================
# BYTECODE PIPELINE BENCHMARK
# =========================================================

for i in tqdm(range(TEST_NUM), desc="Bytecode VM Benchmark"):

    code_lines = load_code()

    start = time.perf_counter()

    tokens = lex(code_lines)
    parser = Parser(tokens)
    ast = parser.program()

    compiler = Compiler()
    compiler.compile(ast)

    # OPTIONAL: actual VM execution
    vm = VM(compiler.bytecode, compiler.constants)
    vm.run()

    end = time.perf_counter()

    byte_times.append(end - start)


# =========================================================
# STATISTICS FUNCTION
# =========================================================

def stats(arr):
    return {
        "mean": np.mean(arr),
        "min": np.min(arr),
        "max": np.max(arr),
        "std": np.std(arr),
    }


interp_stats = stats(interp_times)
byte_stats = stats(byte_times)


# =========================================================
# PRINT TABLE
# =========================================================

table = pd.DataFrame([
    ["Interpreter", interp_stats["mean"], interp_stats["min"], interp_stats["max"], interp_stats["std"]],
    ["Bytecode VM", byte_stats["mean"], byte_stats["min"], byte_stats["max"], byte_stats["std"]],
], columns=["System", "Mean (s)", "Min (s)", "Max (s)", "Std Dev (s)"])

print("\n===== BENCHMARK RESULTS =====\n")
print(table.to_string(index=False))
print(f"Diff (s) = {interp_stats['mean'] - byte_stats['mean']:.4f}")

# =========================================================
# BAR CHART
# =========================================================

labels = ["Interpreter", "Bytecode VM"]
means = [interp_stats["mean"], byte_stats["mean"]]

plt.figure(figsize=(7, 5))
plt.bar(labels, means, color=["skyblue", "orange"])

plt.xlabel("System")
plt.ylabel("Average Execution Time (seconds)")
plt.title(f"Interpreter vs Bytecode VM (n={TEST_NUM})")

plt.show()


# =========================================================
# RUN-BY-RUN TREND (OPTIONAL VISUALIZATION)
# =========================================================

plt.figure(figsize=(10, 5))

plt.plot(interp_times, label="Interpreter", alpha=0.7)
plt.plot(byte_times, label="Bytecode VM", alpha=0.7)

plt.xlabel("Run Index")
plt.ylabel("Execution Time (seconds)")
plt.title("Execution Time Stability Across Runs")
plt.legend()

plt.show()

