"""interpreter

AST-to-Python translator and execution helpers.

This module implements a small interpreter that traverses the AST produced by
``parser.Parser`` and emits executable Python source strings. Emitted code may
be executed directly or written to temporary files for separate runners. The
interpreter also records imports and constants to simple CSV trackers used by
the wider toolchain.
"""

from platform import node

from parser import *
from lexer import *
from classes import *
import random
import csv
import math
import sys
import subprocess
# from adafruit_servokit import ServoKit

# ---------------------------------------------------------------------------
# Global constant-variable registry
# ---------------------------------------------------------------------------

CONST_VARS = {}
csv_file_path = "CONST_VARS.csv"

with open(csv_file_path, "w") as f:
    pass  # truncate on startup

imports = []
csv_file_path_imports = "imports.csv"
with open(csv_file_path_imports, "w") as f:
    pass

classes = {}
csv_file_path_classes = "classes.csv"
with open(csv_file_path_classes, "w") as f:
    pass

# kit = ServoKit(channels=16)
# ---------------------------------------------------------------------------
# Hardware helpers
# ---------------------------------------------------------------------------

# FIX 1: ServoKit must be a module-level singleton, not recreated per command.
# Creating a new ServoKit() opens a fresh I2C connection every call — this
# corrupts the bus on most Pi setups and adds ~50 ms latency per command.
#
# We lazily initialise the kit the first time a servo command is executed and
# reuse it for every subsequent command in the same process.

_servo_kit = None  # PCA9685-based kit (adafruit_servokit)
_gpio_initialized = False  # raw Raspberry Pi GPIO state

SERVO_MIN_ANGLE = 0
SERVO_MAX_ANGLE = 180


def _get_servo_kit():
    """Return (and lazily create) the shared ServoKit instance."""
    global _servo_kit
    if _servo_kit is None:
        try:
            from adafruit_servokit import ServoKit
            _servo_kit = ServoKit(channels=16)
        except ImportError as e:
            raise ImportError(
                "adafruit_servokit is not installed. "
                "Run: pip install adafruit-circuitpython-servokit"
            ) from e
        except Exception as e:
            raise RuntimeError(
                f"Failed to initialise ServoKit (check I2C wiring): {e}"
            ) from e
    return _servo_kit


def _ensure_gpio():
    """Set up RPi.GPIO in BCM mode once. Safe to call multiple times."""
    global _gpio_initialized
    if not _gpio_initialized:
        try:
            import RPi.GPIO as GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            _gpio_initialized = True
        except ImportError as e:
            raise ImportError(
                "RPi.GPIO is not installed or this is not a Raspberry Pi."
            ) from e
    return _gpio_initialized


def _execute_servo(index: int, angle: float) -> None:
    """Move a servo to *angle* degrees with bounds checking.

    FIX 2: angle is clamped hard to [0, 180] before ANY signal reaches the
    hardware. Sending out-of-range angles (the old code had no guard at all)
    can strip servo gears or burn the motor winding.

    Args:
        index: Servo channel on the PCA9685 (0-15).
        angle: Target angle in degrees. Clamped to [0, 180].
    """
    # FIX 3: validate index so we don't silently address a non-existent channel
    if not isinstance(index, (int, float)):
        raise TypeError(f"Servo index must be a number, got {type(index).__name__}")
    index = int(index)
    if not (0 <= index <= 15):
        raise ValueError(f"Servo index {index} out of range (0–15 for PCA9685)")

    # FIX 2: hard clamp — never send an out-of-range angle to hardware
    if not isinstance(angle, (int, float)):
        raise TypeError(f"Servo angle must be a number, got {type(angle).__name__}")
    angle = float(angle)
    if angle < SERVO_MIN_ANGLE or angle > SERVO_MAX_ANGLE:
        clamped = max(SERVO_MIN_ANGLE, min(SERVO_MAX_ANGLE, angle))
        print(
            f"[WARN] Servo angle {angle}° is out of range [0–180]. "
            f"Clamped to {clamped}°."
        )
        angle = clamped

    kit = _get_servo_kit()
    kit.servo[index].angle = angle


def _execute_set_pin(pin: int, state: int) -> None:
    """Drive a GPIO pin HIGH (1) or LOW (0).

    FIX 4: GPIO pin control was completely absent from the original
    interpreter — the SetNode handler only handled servo, not pin.
    This function handles it correctly:
      - Calls _ensure_gpio() once to configure BCM mode
      - Sets the pin as OUTPUT before driving it (missing in the AI-written version)
      - Validates state is 0 or 1

    Args:
        pin:   BCM pin number.
        state: 1 for HIGH, 0 for LOW.
    """
    import RPi.GPIO as GPIO

    if not isinstance(pin, (int, float)):
        raise TypeError(f"Pin number must be an integer, got {type(pin).__name__}")
    pin = int(pin)

    if state not in (0, 1):
        raise ValueError(f"Pin state must be 0 or 1, got {state!r}")

    _ensure_gpio()
    GPIO.setup(pin, GPIO.OUT)           # safe to call even if already set up
    GPIO.output(pin, GPIO.HIGH if state == 1 else GPIO.LOW)


def gpio_cleanup() -> None:
    """Release all GPIO resources cleanly.

    Call this at interpreter shutdown or on KeyboardInterrupt. Leaving GPIO
    pins in an active state between runs causes undefined behaviour on the
    next startup.
    """
    global _gpio_initialized
    if _gpio_initialized:
        try:
            import RPi.GPIO as GPIO
            GPIO.cleanup()
        except Exception:
            pass  # best-effort cleanup
        _gpio_initialized = False


# ---------------------------------------------------------------------------
# Interpreter
# ---------------------------------------------------------------------------

class interpreter:
    """Generate Python source from the AST."""

    def __init__(self):
        self.variable_types = {}

    def get_type(self, node):
        """Infer the type of an AST node."""
        if hasattr(node, 'type') and node.type is not None:
            return node.type
        if isinstance(node, VarNode):
            return self.variable_types.get(node.name)
        if isinstance(node, BinOpNode):
            left_type = self.get_type(node.left)
            right_type = self.get_type(node.right)
            if left_type == "float" or right_type == "float":
                return "float"
            return left_type
        if isinstance(node, UnaryOpNode):
            return self.get_type(node.node)
        if isinstance(node, CallNode):
            return None
        return getattr(node, 'type', None)

    def generate(self, node):
        """Recursively translate an AST node into Python source text."""

        if isinstance(node, ProgramNode):
            return "\n".join(self.generate(stmt) for stmt in node.statements)

        elif isinstance(node, BlockNode):
            return "\n".join(self.generate(stmt) for stmt in node.statements)

        elif isinstance(node, PyNode):
            return node.code
        
        elif isinstance(node, ExecNode):
            # FIX 5: original code built the command list but never ran it.
            # subprocess.run() actually executes the parallel script.
            file_to_run = "temp_exec.py"
            with open(file_to_run, mode='w') as f:
                f.write(node.code)
            result = subprocess.run(
                [sys.executable, "runner.py", file_to_run],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"ExecNode subprocess failed:\n{result.stderr}"
                )
            return ""

        elif isinstance(node, ClassNode):
            # FIX 6: original code used undefined name 'csvfile' — should be 'f'
            with open(csv_file_path_classes, mode='a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['name', 'fields', 'methods'])
                writer.writerow({
                    'name': node.name,
                    'fields': node.fields,
                    'methods': node.methods,
                })
            return ""

        elif isinstance(node, openNode):
            return f"{node.name} = open({node.path}, {node.type})"

        elif isinstance(node, AssignNode):
            if node.name in CONST_VARS:
                raise RuntimeError(f"Cannot reassign constant variable '{node.name}'")

            value_type = self.get_type(node.value)

            if node.type is not None:
                if value_type is not None and value_type != node.type:
                    raise TypeError(
                        f"Type Mismatch: variable '{node.name}' declared as "
                        f"{node.type} but assigned {value_type}"
                    )
                self.variable_types[node.name] = node.type
            elif node.name in self.variable_types:
                expected_type = self.variable_types[node.name]
                if value_type is not None and value_type != expected_type:
                    raise TypeError(
                        f"Type Mismatch: variable '{node.name}' is "
                        f"{expected_type} but assigned {value_type}"
                    )

            return f"{node.name} = {self.generate(node.value)}"

       
        
        elif isinstance(node, SetNode):
            if node.name in CONST_VARS:
                raise RuntimeError(f"Cannot reassign constant variable '{node.name}'")

            if node.name == "servo" and node.type_ == "angle":
                # Generate a call to our validated runtime helper.
                # The helper clamps angles, validates the index, and reuses
                # the singleton ServoKit — no I2C churn.
                return f"_execute_servo({self.generate(node.num)}, float({self.generate(node.params)}))"
                # print("executed")
                # return ""
                    # return (
                    #     f"from adafruit_servokit import ServoKit\n"
                    #     f"_kit = ServoKit(channels=16) if '_kit' not in dir() else _kit\n"
                    #     f"_kit.servo[{self.generate(node.num)}].angle = {self.generate(node.params)}"
                    # )

            elif node.name == "pin":
                # FIX 4: GPIO pin control — was completely missing.
                return (
                    f"_execute_set_pin({self.generate(node.num)}, "
                    f"{self.generate(node.params)})"
                )

            else:
                return f"{node.name}.{node.type_} = {self.generate(node.params)}  "

        elif isinstance(node, ConstAssignNode):
            if node.name in CONST_VARS:
                raise RuntimeError(f"Cannot reassign constant variable '{node.name}'")

            val_str = self.generate(node.value)
            CONST_VARS[node.name] = val_str

            # FIX 7: original code wrote the header on every append, producing
            # a corrupt CSV with a header row between every data row.
            # Check whether the file is empty first; only write header once.
            with open(csv_file_path, mode='a', newline='') as csvfile:
                write_header = csvfile.tell() == 0
                writer = csv.DictWriter(csvfile, fieldnames=['name', 'value'])
                if write_header:
                    writer.writeheader()
                writer.writerow({'name': node.name, 'value': val_str})

            return f"{node.name} = {val_str}"

        elif isinstance(node, ParallelNode):
            arr = [str(e) for e in node.prc]
            print(arr)
            return ""

        elif isinstance(node, listCallNode):
            return f"{self.generate(node.list_node)}[{self.generate(node.pos)}]"

        elif isinstance(node, RandNumNode):
            # FIX 8: original code evaluated random.randint at *generation* time,
            # meaning every execution of the same script returned the same number.
            # Generate a runtime call instead so it re-evaluates on every run.
            start = self.generate(node.start)
            end = self.generate(node.end)
            return f"random.randint({start}, {end})"

        elif isinstance(node, NoneNode):
            return "None"

        elif isinstance(node, PassNode):
            return "pass"

        elif isinstance(node, PrintNode):
            return f"print({self.generate(node.expr)})"

        elif isinstance(node, NumberNode):
            if node.type == "float":
                return str(float(node.value))
            return str(node.value)

        elif isinstance(node, SqrtNode):
            # FIX 9: original code computed sqrt at generation time, baking the
            # result in as a literal. Generate a runtime math.sqrt() call instead.
            return f"math.sqrt(float({self.generate(node.value)}))"

        elif isinstance(node, StringNode):
            return repr(node.value)

        elif isinstance(node, VarNode):
            return node.name

        elif isinstance(node, ListNode):
            return f"[{', '.join(self.generate(el) for el in node.elements)}]"

        elif isinstance(node, TupleNode):
            # Single-element tuples need a trailing comma in Python: (a,)
            if len(node.elements) == 1:
                return f"({self.generate(node.elements[0])},)"
            return f"({', '.join(self.generate(el) for el in node.elements)})"

        elif isinstance(node, DictNode):
            pairs = ', '.join(
                f"{self.generate(k)}: {self.generate(v)}"
                for k, v in node.elements.items()
            )
            return f"{{{pairs}}}"

        elif isinstance(node, BinOpNode):
            return f"({self.generate(node.left)} {node.op} {self.generate(node.right)})"

        elif isinstance(node, LogicOpNode):
            op_str = "and" if node.op in ("&&", "and") else "or"
            return f"({self.generate(node.left)} {op_str} {self.generate(node.right)})"

        elif isinstance(node, UnaryOpNode):
            op_str = "not " if node.op in ("!", "not") else node.op
            return f"({op_str}{self.generate(node.node)})"

        elif isinstance(node, InputNode):
            if node.prompt:
                return f"input({self.generate(node.prompt)})"
            return "input()"

        elif isinstance(node, IfNode):
            code = f"if {self.generate(node.condition)}:\n"
            code += self.indent_block(self.generate(node.then_body))
            if node.else_body:
                code += "\nelse:\n"
                code += self.indent_block(self.generate(node.else_body))
            return code

        elif isinstance(node, ElifNode):
            code = f"elif {self.generate(node.condition)}:\n"
            code += self.indent_block(self.generate(node.then_body))
            if node.else_body:
                code += "\nelse:\n"
                code += self.indent_block(self.generate(node.else_body))
            return code

        elif isinstance(node, WhileNode):
            code = f"while {self.generate(node.condition)}:\n"
            code += self.indent_block(self.generate(node.body))
            return code

        elif isinstance(node, TryNode):
            code = "try:\n"
            code += self.indent_block(self.generate(node.try_body))
            if node.except_body:
                code += "\nexcept Exception as _err:\n"
                code += self.indent_block(self.generate(node.except_body))
            return code

        elif isinstance(node, ForNode):
            code = f"for {node.var_name} in {self.generate(node.iterable)}:\n"
            code += self.indent_block(self.generate(node.body))
            return code

        elif isinstance(node, RangeNode):
            return f"range({self.generate(node.start)}, {self.generate(node.end)})"

        elif isinstance(node, FuncNode):
            params_str = ", ".join(node.params)
            code = f"def {node.name}({params_str}):\n"
            code += self.indent_block(self.generate(node.body))
            return code

        elif isinstance(node, BoolNode):
            return "True" if node.value else "False"

        elif isinstance(node, AttributeNode):
            return f"{self.generate(node.obj)}.{node.attr}"

        elif isinstance(node, CallNode):
            args_str = ", ".join(self.generate(arg) for arg in node.arg)
            return f"{self.generate(node.func_name)}({args_str})"

        elif isinstance(node, CastNode):
            return f"{node.cast_type}({self.generate(node.value)})"

        elif isinstance(node, ImportNode):
            import_name = node.name.value
            target_filename = f"{import_name}.or"
            found_code = None

            with open("classes.txt", "r", encoding="utf-8") as f:
                content = f.read()

            sections = content.split("=" * 40)
            for i, section in enumerate(sections):
                if target_filename in section:
                    found_code = sections[i + 1].strip()
                    break
            
            
            if found_code is not None:
                tokens = lex(found_code.splitlines())
                parser = Parser(tokens)
                mod_ast = parser.program()
                generated = self.generate(mod_ast)
                with open(csv_file_path_imports, mode='a', newline='') as f:
                    csv.writer(f).writerow([import_name, ""])
                return f"{generated}\n"
            else:
                with open(csv_file_path_imports, mode='a', newline='') as f:
                    csv.writer(f).writerow([import_name, ""])
                return f"import {import_name}"

        elif isinstance(node, ImportFromNode):
            import_name = node.name.value
            target_filename = f"{import_name}.or"
            found_code = None
            
            try:
                
                with open("classes.txt", "r", encoding="utf-8") as f:
                    content = f.read()

                sections = content.split("=" * 40)
                for i, section in enumerate(sections):
                    if target_filename in section:
                        found_code = sections[i + 1].strip()
                        break
            except FileNotFoundError: 
                print(f"{target_filename} not found in output.txt")

            if found_code is not None:
                tokens = lex(found_code.splitlines())
                parser = Parser(tokens)
                mod_ast = parser.program()
                generated = self.generate(mod_ast)
                return f"{generated}\n"
            else:
                return f"from {import_name} import {node.lib.value}"
            
        elif isinstance(node, ImportAsNode):
            with open(csv_file_path_imports, mode='a', newline='') as f:
                csv.writer(f).writerow([node.name.value, node.nName.value])
            return f"import {node.name.value} as {node.nName.value}"

        else:
            raise RuntimeError(f"Unknown node type: {type(node).__name__} — {node}")

    @staticmethod
    def indent_block(code, indent=4):
        spaces = " " * indent
        return "\n".join(
            spaces + line if line.strip() else line
            for line in code.split("\n")
        )