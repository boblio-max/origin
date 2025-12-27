import re
from sqlite3 import OperationalError

from more_itertools import value_chain
from parser import ASTNode, StringNode, NumberNode, VarNode, PrintNode, ProgramNode, BinOpNode, AssignNode, UnaryOpNode, Parser

class Interpreter:
    def __init__(self):
        self.env = {}
        
    def run(self, node):
        if isinstance(node, ProgramNode):
            for stmt in node.statements:
                self.run(stmt)
        elif isinstance(node, AssignNode):
            value = self.eval(node.value)
            self.env[node.name] = value
        elif isinstance(node, PrintNode):
            print(self.eval(node.expr))
            
        else:
            raise RuntimeError(f"Unknown statement node: {node}")
    
    def eval(self, node):
        if isinstance(node, NumberNode):
            return node.value
        
        elif isinstance(node, VarNode):
            if node.name not in self.env:
                print(node.name)
            
            return self.env[node.name]
        
        elif isinstance(node, BinOpNode):
            left = self.eval(node.left)
            right = self.eval(node.right)
            
            if node.op == "+":
                return left + right
            if node.op == "-":
                return left - right
            if node.op == "*":
                return left * right
            if node.op == "/":
                return left / right
            if node.op == "%":
                if right == 0:
                    raise ZeroDivisionError("Division by zero")
                return left % right
            else:
                raise RuntimeError("Operation not found")
        elif isinstance(node, StringNode):
            return node.value
        elif isinstance(node, UnaryOpNode):
            value = self.eval(node.node)
            if node.op == "+":
                return +value
            elif node.op == "-":
                return -value
            
            elif node.op == "++":
                return value + 1
            elif node.op == "--":
                return value - 1
            else:
                raise RuntimeError("Unknown unary operator")
            
        else:
            raise RuntimeError("Unknown expression node: {node}")

