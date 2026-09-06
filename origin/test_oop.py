import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from lexer import lex
from parser import Parser
from origin.bytecodeCOMPS.bCompS import Compiler, VM

source_code = """
class Person(name, age) {
    def greet(self) {
        print("Hello, my name is ")
        print(self.name)
        print(" and I am ")
        print(self.age)
    }
    
    def have_birthday(self) {
        self.age = self.age + 1
        print("Happy birthday!")
    }
}

p = Person("Alice", 30)
p.greet()
p.have_birthday()
p.greet()
print(p.name)
"""

print("Lexing...")
tokens = lex(source_code.splitlines())

print("Parsing...")
parser = Parser(tokens)
ast = parser.program()

print("Compiling...")
compiler = Compiler()
compiler.compile(ast)

print("Running VM...")
vm = VM(compiler.bytecode, compiler.constants)
vm.run()


