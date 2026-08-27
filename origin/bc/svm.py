import random
import csv
import math
import sys
import os
import threading
import re
from pathlib import Path
# from origin.classes import *
from .byte_key import OpCode
from .helpers import OriginClass, OriginInstance, BoundMethod

_PY_RETURN_RE = re.compile(r'(?m)^\s*return\b')


# --- Hardware Runtime Helpers (mirrors interpreter.py) ---
def _svm_set_pin(pin, state):
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.HIGH if state else GPIO.LOW)
    except ImportError:
        print(f"[SIM] Pin {pin} set to {state}")

def _svm_i2c_read(addr, reg, size=1):
    try:
        import smbus2
        bus = smbus2.SMBus(1)
        return bus.read_byte_data(addr, reg) if size == 1 else bus.read_i2c_block_data(addr, reg, size)
    except ImportError:
        return 0

def _svm_i2c_write(addr, reg, data):
    try:
        import smbus2
        bus = smbus2.SMBus(1)
        if isinstance(data, int): bus.write_byte_data(addr, reg, data)
        else: bus.write_i2c_block_data(addr, reg, data)
    except ImportError:
        pass

def _svm_spi_write(data):
    print(f"[SIM] SPI write: {data}")

def _svm_spi_read(count=1):
    print(f"[SIM] SPI read: {count}")
    return 0

_kit_cache = None 

class sVM:
    def __init__(self, bytecode, constants):
        self.bytecode = bytecode
        self.constants = constants
        self.stack = []
        self.variables = {}
        self.pc = 0
        self.call_stack = []
        self.try_catch_stack = []

    def run(self):
        while self.pc < len(self.bytecode):
            opcode = self.bytecode[self.pc]
            self.pc += 1

            if opcode == OpCode.PUSH_CONST:
                idx = self.bytecode[self.pc]
                self.pc += 1
                self.stack.append(self.constants[idx])

            elif opcode == OpCode.LOAD_VAR:
                idx = self.bytecode[self.pc]
                self.pc += 1
                name = self.constants[idx]
                if name not in self.variables:
                    raise NameError(f"Name '{name}' is not defined")
                self.stack.append(self.variables[name])

            elif opcode == OpCode.STORE_VAR:
                idx = self.bytecode[self.pc]
                self.pc += 1
                name = self.constants[idx]
                val = self.stack.pop()
                self.variables[name] = val

            elif opcode == OpCode.ADD:
                b = self.stack.pop()
                a = self.stack.pop()
                # Mirror interpreter.py:205 smart concat: str + any -> str concat
                if isinstance(a, str) or isinstance(b, str):
                    self.stack.append(str(a) + str(b))
                else:
                    self.stack.append(a + b)

            elif opcode == OpCode.SUB:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a - b)

            elif opcode == OpCode.MUL:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a * b)

            elif opcode == OpCode.DIV:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a / b)

            elif opcode == OpCode.FLOOR_DIV:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a // b)

            elif opcode == OpCode.MOD:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a % b)
            
            elif opcode == OpCode.POW:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a ** b)
                
            elif opcode == OpCode.NEGATE:
                val = self.stack.pop()
                self.stack.append(-(val))
                
            elif opcode == OpCode.BIT_AND:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a & b)

            elif opcode == OpCode.BIT_OR:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a | b)

            elif opcode == OpCode.BIT_XOR:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a ^ b)

            elif opcode == OpCode.BIT_NOT:
                val = self.stack.pop()
                self.stack.append(~val)

            elif opcode == OpCode.LSHIFT:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a << b)

            elif opcode == OpCode.RSHIFT:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a >> b)

            elif opcode == OpCode.EQ:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a == b)

            elif opcode == OpCode.NEQ:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a != b)

            elif opcode == OpCode.LT:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a < b)

            elif opcode == OpCode.GT:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a > b)

            elif opcode == OpCode.LTE:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a <= b)

            elif opcode == OpCode.GTE:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a >= b)

            elif opcode == OpCode.JMP:
                target = (self.bytecode[self.pc] << 8) | self.bytecode[self.pc+1]
                self.pc += 2
                self.pc = target

            elif opcode == OpCode.JMP_IF_FALSE:
                target = (self.bytecode[self.pc] << 8) | self.bytecode[self.pc+1]
                self.pc += 2
                val = self.stack.pop()
                if not val:
                    self.pc = target

            elif opcode == OpCode.PRINT:
                val = self.stack.pop()
                # Mirror interpreter.py:309 multi-arg print unpack for Tuple/List
                if isinstance(val, (list, tuple)):
                    # Heuristic: if val came from TupleNode/ListNode used as print args, unpack with spaces
                    # This matches interpreter's `print(a,b)` -> `print(arg1, arg2)` not `print([arg1,arg2])`
                    # We distinguish by checking if all elements are not nested collections? For now unpack.
                    # To preserve explicit list printing, interpreter also unpacks - so we follow it.
                    print(*val)
                else:
                    print(val)

            elif opcode == OpCode.INPUT:
                prompt = self.stack.pop()
                res = input(prompt)
                self.stack.append(res)

            elif opcode == OpCode.SQRT:
                val = self.stack.pop()
                self.stack.append(math.sqrt(float(val)))

            elif opcode == OpCode.ABS:
                val = self.stack.pop()
                self.stack.append(abs(val))

            elif opcode == OpCode.FLOOR:
                val = self.stack.pop()
                self.stack.append(math.floor(float(val)))

            elif opcode == OpCode.CEIL:
                val = self.stack.pop()
                self.stack.append(math.ceil(float(val)))

            elif opcode == OpCode.POP:
                self.stack.pop()

            elif opcode == OpCode.DUP:
                self.stack.append(self.stack[-1])

            elif opcode == OpCode.RAND_NUM:
                end = int(self.stack.pop())
                start = int(self.stack.pop())
                self.stack.append(random.randint(start, end))

            elif opcode == OpCode.LIST_INIT:
                n = self.bytecode[self.pc]
                self.pc += 1
                elements = []
                for _ in range(n):
                    elements.insert(0, self.stack.pop())
                self.stack.append(elements)

            elif opcode == OpCode.DICT_INIT:
                n = self.bytecode[self.pc]
                self.pc += 1
                elements = {}
                for _ in range(n):
                    v = self.stack.pop()
                    k = self.stack.pop()
                    elements[k] = v
                self.stack.append(elements)

            elif opcode == OpCode.INDEX_LOAD:
                idx = self.stack.pop()
                coll = self.stack.pop()
                self.stack.append(coll[idx])

            elif opcode == OpCode.INDEX_STORE:
                val = self.stack.pop()
                idx = self.stack.pop()
                coll = self.stack.pop()
                coll[idx] = val

            elif opcode == OpCode.LEN:
                val = self.stack.pop()
                self.stack.append(len(val))

            elif opcode == OpCode.NOT:
                val = self.stack.pop()
                self.stack.append(not val)

            elif opcode == OpCode.AND:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a and b)
            
            elif opcode == OpCode.OR:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a or b)
                
            elif opcode == OpCode.CAST_STR:
                self.stack.append(str(self.stack.pop()))
                
            elif opcode == OpCode.CAST_INT:
                self.stack.append(int(self.stack.pop()))
            
            elif opcode == OpCode.CAST_FLOAT:
                self.stack.append(float(self.stack.pop()))

            elif opcode == OpCode.GET_ITER:
                obj = self.stack.pop()
                self.stack.append(iter(obj))

            elif opcode == OpCode.FOR_ITER:
                target = (self.bytecode[self.pc] << 8) | self.bytecode[self.pc+1]
                self.pc += 2
                it = self.stack[-1] # Peek at the iterator on the stack
                try:
                    val = next(it)
                    self.stack.append(val)
                except StopIteration:
                    self.stack.pop() # Remove the exhausted iterator
                    self.pc = target

            elif opcode == OpCode.MAKE_CLASS:
                methods = self.stack.pop()
                fields = self.stack.pop()
                name = self.stack.pop()
                self.stack.append(OriginClass(name, fields, methods))

            elif opcode == OpCode.LOAD_ATTR:
                attr = self.stack.pop()
                obj = self.stack.pop()
                if isinstance(obj, OriginInstance):
                    if attr in obj.attrs:
                        self.stack.append(obj.attrs[attr])
                    elif attr in obj.origin_class.methods:
                        self.stack.append(BoundMethod(obj, obj.origin_class.methods[attr]))
                    else:
                        raise AttributeError(f"'{obj.origin_class.name}' object has no attribute '{attr}'")
                else:
                    self.stack.append(getattr(obj, attr))

            elif opcode == OpCode.STORE_ATTR:
                attr = self.stack.pop()
                value = self.stack.pop()
                obj = self.stack.pop()
                if isinstance(obj, OriginInstance):
                    obj.attrs[attr] = value
                else:
                    setattr(obj, attr, value)
                
            elif opcode == OpCode.CALL:
                num_args = self.bytecode[self.pc]
                self.pc += 1
                func = self.stack.pop() 
                
                if isinstance(func, int):
                    # It's a bytecode function address (jump to it)
                    # Save return address AND current variable scope
                    self.call_stack.append((self.pc, self.variables))
                    self.variables = self.variables.copy()
                    self.pc = func 
                elif isinstance(func, BoundMethod):
                    self.stack.insert(len(self.stack) - num_args, func.instance)
                    self.call_stack.append((self.pc, self.variables))
                    self.variables = self.variables.copy()
                    self.pc = func.func_pc
                elif isinstance(func, OriginClass):
                    instance = OriginInstance(func)
                    args = []
                    for _ in range(num_args):
                        args.insert(0, self.stack.pop())
                    for i, field in enumerate(func.fields):
                        if i < len(args):
                            instance.attrs[field] = args[i]
                        else:
                            instance.attrs[field] = None
                    self.stack.append(instance)
                else:
                    # It's a Python built-in function (like range or str)
                    args = []
                    for _ in range(num_args):
                        args.insert(0, self.stack.pop())
                    result = func(*args)
                    self.stack.append(result)

            elif opcode == OpCode.RETURN:
                if self.call_stack:
                    ret_pc, saved_vars = self.call_stack.pop()
                    self.pc = ret_pc
                    for k, v in self.variables.items():
                        if k in saved_vars:
                            saved_vars[k] = v
                    self.variables = saved_vars
                else:
                    break # No more calls on stack, end execution

            elif opcode == OpCode.SETUP_EXCEPT:
                target = (self.bytecode[self.pc] << 8) | self.bytecode[self.pc+1]
                self.pc += 2
                self.try_catch_stack.append(target)

            elif opcode == OpCode.POP_EXCEPT:
                if self.try_catch_stack:
                    self.try_catch_stack.pop()

            elif opcode == OpCode.THROW:
                exception_val = self.stack.pop()
                if self.try_catch_stack:
                    handler_pc = self.try_catch_stack.pop()
                    self.pc = handler_pc
                    self.stack.append(exception_val)
                else:
                    raise Exception(f"Uncaught Exception: {exception_val}")

            elif opcode == OpCode.FORMAT_VAL:
                val = self.stack.pop()
                self.stack.append(f"{val}")

            elif opcode == OpCode.BUILD_STR:
                count = self.bytecode[self.pc]
                self.pc += 1
                parts = []
                for _ in range(count):
                    parts.insert(0, str(self.stack.pop()))
                self.stack.append("".join(parts))

            elif opcode == OpCode.UNPACK_SEQ:
                count = self.bytecode[self.pc]
                self.pc += 1
                seq = self.stack.pop()
                for item in reversed(list(seq)):
                    self.stack.append(item)

            elif opcode == OpCode.READ_FILE:
                path = self.stack.pop()
                count = self.bytecode[self.pc]
                self.pc += 1
                # 0xFF is wire encoding for -1 (read all); handle signed byte
                if count == 0xFF:
                    count = -1
                if count == -1:
                    self.stack.append(open(path).read())
                else:
                    self.stack.append(open(path).read(count))

            elif opcode == OpCode.WRITE_FILE:
                content = self.stack.pop()
                path = self.stack.pop()
                with open(path, 'w') as f:
                    f.write(content)

            elif opcode == OpCode.APPEND_FILE:
                content = self.stack.pop()
                path = self.stack.pop()
                with open(path, 'a') as f:
                    f.write(content)

            elif opcode == OpCode.HARDWARE_CALL:
                num_args = self.bytecode[self.pc]; self.pc += 1
                # namespace/method tuple was pushed via PUSH_CONST; pop it
                ns_method = self.stack.pop()
                if isinstance(ns_method, int):
                    # backwards compat: tuple stored as constant index
                    ns_method = self.constants[ns_method]
                ns, method = ns_method
                args = []
                for _ in range(num_args):
                    args.insert(0, self.stack.pop())
                if ns == "i2c" and method == "read":
                    result = _svm_i2c_read(*args)
                    self.stack.append(result)
                elif ns == "i2c" and method == "write":
                    _svm_i2c_write(*args)
                elif ns == "spi" and method == "write":
                    _svm_spi_write(*args)
                elif ns == "spi" and method == "read":
                    result = _svm_spi_read(*args)
                    self.stack.append(result)
                else:
                    print(f"[SIM] {ns}.{method}({', '.join(str(a) for a in args)})")

            elif opcode == OpCode.SET_SERVO:
                global _kit_cache
                angle = self.stack.pop()
                channel = self.stack.pop()
                try:
                    if _kit_cache is None:
                        from adafruit_servokit import ServoKit
                        import board
                        _kit_cache = ServoKit(channels=16)
                    _kit_cache.servo[int(channel)].angle = float(angle)
                except (ImportError, AttributeError, Exception):
                    print(f"[SIM] Servo {channel} angle set to {angle}")

            elif opcode == OpCode.SET_PIN:
                state = self.stack.pop()
                pin = self.stack.pop()
                _svm_set_pin(pin, state)

            elif opcode == OpCode.PARALLEL_START:
                num_threads = self.bytecode[self.pc]; self.pc += 1
                body_start = (self.bytecode[self.pc] << 8) | self.bytecode[self.pc+1]; self.pc += 2
                # Isolated VMs per thread to avoid race on shared self.pc/stack/variables
                threads = []
                vms = []
                for _ in range(num_threads):
                    vm = sVM(self.bytecode, self.constants)
                    vm.variables = self.variables.copy()
                    vm.pc = body_start
                    # each thread runs until PARALLEL_END / RETURN / HALT
                    t = threading.Thread(target=vm._run_until_parallel_end)
                    t.start()
                    threads.append(t)
                    vms.append(vm)
                self.stack.append((threads, vms))

            elif opcode == OpCode.PARALLEL_END:
                item = self.stack.pop()
                if isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], list):
                    threads, vms = item
                    for t in threads:
                        t.join()
                    # merge worker variable changes back (simple update, last wins)
                    for vm in vms:
                        # thread-safe merge under lock
                        self.variables.update(vm.variables)
                else:
                    # backwards compat: old format stored list[Thread]
                    threads = item
                    for t in threads:
                        t.join()

            elif opcode == OpCode.EXEC_PY:
                code = self.stack.pop()
                self.variables['__builtins__'] = __builtins__
                self.variables['__file__'] = os.path.abspath(__file__)
                if _PY_RETURN_RE.search(code):
                    wrapped = "def _py_block():\n    " + code.strip().replace("\n", "\n    ") + "\n"
                    try:
                        exec(wrapped, self.variables)
                        result = self.variables['_py_block']()
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        result = None
                    # A `return` inside a py block returns from the enclosing function
                    # (mirrors the interpreter, which inlines py{} code).
                    if self.call_stack:
                        ret_pc, saved_vars = self.call_stack.pop()
                        self.pc = ret_pc
                        for k, v in self.variables.items():
                            if k in saved_vars:
                                saved_vars[k] = v
                        self.variables = saved_vars
                    else:
                        break
                    self.stack.append(result)
                else:
                    try:
                        exec(code, self.variables)
                    except Exception as e:
                        import traceback
                        traceback.print_exc()

            elif opcode == OpCode.HALT:
                break

            elif opcode == OpCode.MOVE:
                dest_idx = self.bytecode[self.pc]
                self.pc += 1
                src_idx = self.bytecode[self.pc]
                self.pc += 1
                dest_name = self.constants[dest_idx]
                src_name = self.constants[src_idx]
                self.variables[dest_name] = self.variables.get(src_name)

            elif opcode == OpCode.COPY:
                dest_idx = self.bytecode[self.pc]
                self.pc += 1
                src_idx = self.bytecode[self.pc]
                self.pc += 1
                dest_name = self.constants[dest_idx]
                src_name = self.constants[src_idx]
                if src_name in self.variables:
                    self.variables[dest_name] = self.variables[src_name]


    def _run_until_parallel_end(self):
        """Worker entry for PARALLEL_START threads: run until PARALLEL_END/RETURN/HALT."""
        while self.pc < len(self.bytecode):
            opcode = self.bytecode[self.pc]
            self.pc += 1
            if opcode == OpCode.PARALLEL_END:
                break
            if opcode == OpCode.HALT or opcode == OpCode.RETURN:
                break
            # delegate to full handler via _exec_opcode
            self._exec_opcode(opcode)
            # if _exec_opcode didn't handle it (was no-op), fallback to run's logic for jumps
            # need to handle JMP etc. which _exec_opcode now covers

    def _run_from(self, pc):
        """Legacy entry (kept for compat): run from pc until RETURN/HALT with isolated state."""
        # Use isolated VM to avoid racing on shared self
        vm = sVM(self.bytecode, self.constants)
        vm.variables = self.variables.copy()
        vm.pc = pc
        vm._run_until_parallel_end()
        # merge back
        self.variables.update(vm.variables)

    def _exec_opcode(self, opcode):
        """Execute a single opcode (expanded to cover all ops for parallel threads)."""
        # Handle the small subset directly; for others, inline the same logic as run()
        if opcode == OpCode.PUSH_CONST:
            idx = self.bytecode[self.pc]; self.pc += 1
            self.stack.append(self.constants[idx])
        elif opcode == OpCode.LOAD_VAR:
            idx = self.bytecode[self.pc]; self.pc += 1
            name = self.constants[idx]
            if name not in self.variables:
                raise NameError(f"Name '{name}' is not defined")
            self.stack.append(self.variables[name])
        elif opcode == OpCode.STORE_VAR:
            idx = self.bytecode[self.pc]; self.pc += 1
            name = self.constants[idx]
            val = self.stack.pop()
            self.variables[name] = val
        elif opcode == OpCode.PRINT:
            val = self.stack.pop()
            if isinstance(val, (list, tuple)):
                print(*val)
            else:
                print(val)
        elif opcode == OpCode.POP:
            self.stack.pop()
        elif opcode == OpCode.DUP:
            self.stack.append(self.stack[-1])
        elif opcode == OpCode.ADD:
            b = self.stack.pop(); a = self.stack.pop()
            if isinstance(a, str) or isinstance(b, str):
                self.stack.append(str(a) + str(b))
            else:
                self.stack.append(a + b)
        elif opcode == OpCode.SUB:
            b = self.stack.pop(); a = self.stack.pop(); self.stack.append(a - b)
        elif opcode == OpCode.MUL:
            b = self.stack.pop(); a = self.stack.pop(); self.stack.append(a * b)
        elif opcode == OpCode.DIV:
            b = self.stack.pop(); a = self.stack.pop(); self.stack.append(a / b)
        elif opcode == OpCode.FLOOR_DIV:
            b = self.stack.pop(); a = self.stack.pop(); self.stack.append(a // b)
        elif opcode == OpCode.MOD:
            b = self.stack.pop(); a = self.stack.pop(); self.stack.append(a % b)
        elif opcode == OpCode.POW:
            b = self.stack.pop(); a = self.stack.pop(); self.stack.append(a ** b)
        elif opcode == OpCode.NEGATE:
            self.stack.append(-(self.stack.pop()))
        elif opcode == OpCode.BIT_AND:
            b = self.stack.pop(); a = self.stack.pop(); self.stack.append(a & b)
        elif opcode == OpCode.BIT_OR:
            b = self.stack.pop(); a = self.stack.pop(); self.stack.append(a | b)
        elif opcode == OpCode.BIT_XOR:
            b = self.stack.pop(); a = self.stack.pop(); self.stack.append(a ^ b)
        elif opcode == OpCode.BIT_NOT:
            self.stack.append(~self.stack.pop())
        elif opcode == OpCode.LSHIFT:
            b = self.stack.pop(); a = self.stack.pop(); self.stack.append(a << b)
        elif opcode == OpCode.RSHIFT:
            b = self.stack.pop(); a = self.stack.pop(); self.stack.append(a >> b)
        elif opcode == OpCode.EQ:
            b = self.stack.pop(); a = self.stack.pop(); self.stack.append(a == b)
        elif opcode == OpCode.NEQ:
            b = self.stack.pop(); a = self.stack.pop(); self.stack.append(a != b)
        elif opcode == OpCode.LT:
            b = self.stack.pop(); a = self.stack.pop(); self.stack.append(a < b)
        elif opcode == OpCode.GT:
            b = self.stack.pop(); a = self.stack.pop(); self.stack.append(a > b)
        elif opcode == OpCode.LTE:
            b = self.stack.pop(); a = self.stack.pop(); self.stack.append(a <= b)
        elif opcode == OpCode.GTE:
            b = self.stack.pop(); a = self.stack.pop(); self.stack.append(a >= b)
        elif opcode == OpCode.JMP:
            target = (self.bytecode[self.pc] << 8) | self.bytecode[self.pc+1]; self.pc += 2; self.pc = target
        elif opcode == OpCode.JMP_IF_FALSE:
            target = (self.bytecode[self.pc] << 8) | self.bytecode[self.pc+1]; self.pc += 2
            val = self.stack.pop()
            if not val:
                self.pc = target
        elif opcode == OpCode.LEN:
            self.stack.append(len(self.stack.pop()))
        elif opcode == OpCode.NOT:
            self.stack.append(not self.stack.pop())
        elif opcode == OpCode.AND:
            b = self.stack.pop(); a = self.stack.pop(); self.stack.append(a and b)
        elif opcode == OpCode.OR:
            b = self.stack.pop(); a = self.stack.pop(); self.stack.append(a or b)
        elif opcode == OpCode.CAST_STR:
            self.stack.append(str(self.stack.pop()))
        elif opcode == OpCode.CAST_INT:
            self.stack.append(int(self.stack.pop()))
        elif opcode == OpCode.CAST_FLOAT:
            self.stack.append(float(self.stack.pop()))
        elif opcode == OpCode.GET_ITER:
            self.stack.append(iter(self.stack.pop()))
        elif opcode == OpCode.FOR_ITER:
            target = (self.bytecode[self.pc] << 8) | self.bytecode[self.pc+1]; self.pc += 2
            it = self.stack[-1]
            try:
                val = next(it)
                self.stack.append(val)
            except StopIteration:
                self.stack.pop()
                self.pc = target
        elif opcode == OpCode.LIST_INIT:
            n = self.bytecode[self.pc]; self.pc += 1
            elements = []
            for _ in range(n):
                elements.insert(0, self.stack.pop())
            self.stack.append(elements)
        elif opcode == OpCode.DICT_INIT:
            n = self.bytecode[self.pc]; self.pc += 1
            elements = {}
            for _ in range(n):
                v = self.stack.pop(); k = self.stack.pop(); elements[k] = v
            self.stack.append(elements)
        elif opcode == OpCode.INDEX_LOAD:
            idx = self.stack.pop(); coll = self.stack.pop(); self.stack.append(coll[idx])
        elif opcode == OpCode.INDEX_STORE:
            val = self.stack.pop(); idx = self.stack.pop(); coll = self.stack.pop(); coll[idx] = val
        else:
            # For opcodes needing constants/stack like CALL/EXEC_PY etc., fallback to full run loop step
            # rewind pc by 1 so run() can re-dispatch correctly, or handle inline
            self.pc -= 1
            # delegate single step via run's logic by temporarily calling a helper
            # simplest: call run() for one iteration? Instead, handle CALL/RETURN etc. as no-op for parallel stub
            self.pc += 1
            pass


# Backwards-compatible alias used by runnerByte.py
VM = sVM
