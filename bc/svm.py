import random
import csv
import math
import sys
from ORIGIN_CODE.classes import *
from ORIGIN_CODE.bc.byteKey import OpCode
from ORIGIN_CODE.bc.helpers import OriginClass, OriginInstance, BoundMethod 

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
                print(val)

            elif opcode == OpCode.INPUT:
                prompt = self.stack.pop()
                res = input(prompt)
                self.stack.append(res)

            elif opcode == OpCode.SQRT:
                val = self.stack.pop()
                self.stack.append(math.sqrt(float(val)))

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
                    self.call_stack.append((self.pc, self.variables.copy()))
                    self.variables = {}
                    self.pc = func 
                elif isinstance(func, BoundMethod):
                    self.stack.insert(len(self.stack) - num_args, func.instance)
                    self.call_stack.append((self.pc, self.variables.copy()))
                    self.variables = {}
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

            elif opcode == OpCode.HALT:
                break


# Backwards-compatible alias used by ORIGIN_CODE/runnerByte.py
VM = sVM
