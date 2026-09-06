class Optimizer:

    def __init__(self, ir):
        self.ir = ir
        self.constants = {}
        self.known_constants = {}

    def optimize(self):
        changed = True

        while changed:
            changed = False

            changed |= self.constant_folding()
            changed |= self.constant_propagation()
            # changed |= self.copy_propagation()
            # changed |= self.dead_code_elimination()
            # changed |= self.common_subexpression_elimination()
            # changed |= self.algebraic_simplification()
            # changed |= self.strength_reduction()
            # changed |= self.jump_optimization()
            # changed |= self.unreachable_code_elimination()
            # changed |= self.remove_unused_labels()
            # changed |= self.remove_redundant_loads()
            # changed |= self.remove_redundant_stores()
            # changed |= self.boolean_simplification()
            # changed |= self.control_flow_simplification()
            # changed |= self.peephole_optimization()

        return self.ir

    # -----------------------------
    # Arithmetic Optimizations
    # -----------------------------

    def constant_folding(self):
        self.constants = {}
        changed = False

        operations = {
            "ADD": lambda a, b: a + b,
            "SUB": lambda a, b: a - b,
            "MUL": lambda a, b: a * b,
            "DIV": lambda a, b: a // b,
            "MOD": lambda a, b: a % b,
        }

        new_ir = []

        for instruction in self.ir:
            op = instruction[0]

            if op == "CONST_INT":
                _, temp, value = instruction
                self.constants[temp] = value
                new_ir.append(instruction)

            elif op in operations:
                _, dest, left, right = instruction

                if left in self.constants and right in self.constants:
                    result = operations[op](
                        self.constants[left],
                        self.constants[right]
                    )

                    self.constants[dest] = result
                    new_ir.append(("CONST_INT", dest, result))
                    changed = True
                else:
                    new_ir.append(instruction)

            else:
                new_ir.append(instruction)

        self.ir = new_ir
        return changed

    def constant_propagation(self):
        self.known_constants = {}
        changed = False
        new_ir = []

        for instruction in self.ir:
            op = instruction[0]

            if op == "CONST_INT":
                _, temp, value = instruction
                self.known_constants[temp] = value
                new_ir.append(instruction)

            elif op == "STORE":
                _, variable, source = inst = instruction

                if source in self.known_constants:
                    self.known_constants[variable] = self.known_constants[source]
                    inst = ("STORE", variable, self.known_constants[source])
                else:
                    self.known_constants.pop(variable, None)

                new_ir.append(inst)

            elif op == "LOAD":
                _, temp, variable = instruction

                if variable in self.known_constants:
                    value = self.known_constants[variable]
                    self.known_constants[temp] = value
                    new_ir.append(("CONST_INT", temp, value))
                    changed = True
                else:
                    new_ir.append(instruction)

            else:
                new_ir.append(instruction)

        self.ir = new_ir
        return changed

    def copy_propagation(self):
        pass    
    

    def algebraic_simplification(self):
        self.known_constants = {}
        changed = False
        new_ir = []

        for instruction in self.ir:
            op = instruction[0]

            if op == "ADD":
                _, loc, t1, t2 = instruction
                if 0 in [t1, t2]:
                    new_inst = ("MOVE", loc, t1) if t1 == 0 else ("MOVE", loc, t2)
                    new_ir.append(new_inst)
                elif 0 in [self.known_constants[t1], self.known_constants[t2]]:
                    if 0 in [t1, t2]:
                        new_inst = ("MOVE", loc, t1) if self.known_constants[t1] == 0 else ("MOVE", loc, t2)
                        new_ir.append(new_inst)
                else:
                    new_ir.append(instruction)
        self.ir = new_ir
        return changed
        

    def strength_reduction(self):
        pass

    def common_subexpression_elimination(self):
        pass

    # -----------------------------
    # Dead Code Optimizations
    # -----------------------------

    def dead_code_elimination(self):
        pass

    def unreachable_code_elimination(self):
        pass

    # -----------------------------
    # Memory Optimizations
    # -----------------------------

    def remove_redundant_loads(self):
        pass

    def remove_redundant_stores(self):
        pass

    # -----------------------------
    # Boolean Optimizations
    # -----------------------------

    def boolean_simplification(self):
        pass

    # -----------------------------
    # Control Flow Optimizations
    # -----------------------------

    def jump_optimization(self):
        pass

    def control_flow_simplification(self):
        pass

    def remove_unused_labels(self):
        pass

    # -----------------------------
    # Peephole Optimizations
    # -----------------------------

    def peephole_optimization(self):
        pass

    # -----------------------------
    # Utility Methods
    # -----------------------------

    def build_cfg(self):
        """Construct a control-flow graph."""
        pass

    def compute_liveness(self):
        """Compute live variables."""
        pass

    def find_basic_blocks(self):
        """Split IR into basic blocks."""
        pass

    def replace_temp(self, old, new):
        """Replace every use of one temporary with another."""
        pass

    def instruction_uses(self, instruction):
        """Return variables read by an instruction."""
        pass

    def instruction_defines(self, instruction):
        """Return variable written by an instruction."""
        pass

    def remove_instruction(self, index):
        """Delete one instruction."""
        pass

    def insert_instruction(self, index, instruction):
        """Insert one instruction."""
        pass

    def replace_instruction(self, index, instruction):
        """Replace one instruction."""
        pass

