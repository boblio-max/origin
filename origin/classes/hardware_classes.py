from .base_classes import *

class ParallelNode(ASTNode):
    """Parallel processing context."""
    def __init__(self, body, threads=0):
        super().__init__()
        self.body, self.threads = body, threads
    def __repr__(self):
        return f"ParallelNode({self.body}, {self.threads})"

class HardwarePrimitiveNode(ASTNode):
    """Hardware protocol primitive call (i2c, spi, uart)."""
    def __init__(self, namespace, method, args):
        super().__init__()
        self.namespace = namespace
        self.method = method
        self.args = args
    def __repr__(self):
        return f"HardwarePrimitiveNode({self.namespace}, {self.method}, {self.args})"

class SetNode(ASTNode):
    """Specialized state modification (servo, pin)."""
    def __init__(self, name, num, type_, params):
        super().__init__()
        self.name = name
        self.num = num
        self.type_ = type_
        self.params = params
    def __repr__(self):
        return f"SetNode({self.name}, {self.num}, {self.type_}, {self.params})"

class ImuNode(ASTNode):
    """IMU data"""
    def __init__(self, name, address):
        super().__init__()
        self.name = name
        self.address = address
    def __repr__(self):
        return f"ImuNode({self.name}, {self.address})"

class ImuFromNode(ASTNode):
    """IMU data"""
    def __init__(self, value, name):
        super().__init__()
        self.value = value
        self.name = name
    def __repr__(self):
        return f"ImuFromNode({self.value}, {self.name})"
