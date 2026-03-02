"""parser

Recursive-descent parser for the origin language.

This module consumes a linear sequence of :class:`lexer.Token` objects and
constructs an Abstract Syntax Tree (AST) comprised of node classes from
``classes.py``. The parser is intentionally straightforward and designed to
produce clear, well-formed ASTs for the interpreter to evaluate or compile.
"""

from lexer import Token, lex
from classes import *

class Parser:
    """Deterministic recursive-descent parser.

    The :class:`Parser` traverses a token stream and produces AST nodes. It
    maintains a single integer position pointer into the token list and
    exposes small, focused parsing routines for each grammar production.

    Attributes:
        tokens (list[lexer.Token]): Input token sequence.
        pos (int): Current token index within ``tokens``.
    """
    types = {"int":"float", "float":"int", "str": "str"}
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def current_token(self):
        """Return the token at the current parser position.

        If the position is past the end of the sequence an ``EOF`` token is
        returned to simplify downstream parsing code.
        """
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return Token("EOF", "", -1, -1)

    def eat(self, type_):
        """Consume and return the current token when it matches ``type_``.

        Advances the internal position by one. Raises :class:`SyntaxError` if
        the current token does not match the expected type.
        """
        tok = self.current_token()
        if tok.type == type_:
            self.pos += 1
            return tok
        raise SyntaxError(f"Expected {type_}, got {tok.type} ({tok.value})")

    def factor(self):
        """Parse the smallest expression units: literals, identifiers, calls.

        This routine handles numeric and string literals, parenthesized
        expressions, built-in functions (e.g. ``len``, ``sqrt``), variable
        references, indexing and function calls. It returns an AST node
        representing the parsed value.
        """
        self.skip_newlines()
        tok = self.current_token()

        if tok.type == "INT":
            self.eat("INT")
            return NumberNode(int(tok.value), "int")

        if tok.type == "negate":
            self.eat("negate")
            return UnaryOpNode('-', self.factor())
        
        if tok.type == "FLOAT":
            self.eat("FLOAT")
            return NumberNode(float(tok.value), "float")

        if tok.type == "STRING":
            self.eat("STRING")
            return StringNode(tok.value[1:-1], "str")
        
        if tok.type == "KEYWORD" and tok.value == "range":
            self.eat("KEYWORD")          
            self.eat("SYMBOL")      
            start = self.comparison()
            self.eat("SYMBOL")          
            end = self.comparison()
            self.eat("SYMBOL")          
            return RangeNode(start, end)
        
        if tok.type == "IDENT":
            node = VarNode(self.eat("IDENT").value)
            while True:
                # Handle list indexing: node[index]
                if self.current_token().type == "BRACKET" and self.current_token().value == "[":
                    self.eat("BRACKET")
                    index = self.comparison()
                    self.eat("BRACKET")
                    node = IndexNode(node, index)
                
                # Handle dictionary indexing: node{key}
                if self.current_token().type == "BRACKET" and self.current_token().value == "{":
                    self.eat("BRACKET")
                    key = self.comparison()
                    self.eat("BRACKET")
                    node = IndexNode(node, key)                    

                # Handle function calls: node(arg1, arg2...)
                elif self.current_token().type == "SYMBOL" and self.current_token().value == "(":
                    self.eat("SYMBOL")  # (
                    args = []
                    if not (self.current_token().type == "SYMBOL" and self.current_token().value == ")"):
                        args.append(self.comparison())
                        while self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                            self.eat("SYMBOL")
                            args.append(self.comparison())
                    self.eat("SYMBOL")  # )
                    node = CallNode(node, args)

                else:
                    break

            return node
        
        if tok.type == "KEYWORD" and tok.value == "input":
            self.eat("KEYWORD")
            prompt = None
            if self.current_token().type == "STRING":
                prompt = StringNode(self.eat("STRING").value[1:-1])
            return InputNode(prompt)
        
        if tok.type == "KEYWORD" and tok.value == "sqrt":
            self.eat("KEYWORD")
            self.eat("SYMBOL")  # (
            value = self.comparison()
            self.eat("SYMBOL")  # )
            return SqrtNode(value)
            
        if tok.type == "KEYWORD" and tok.value == "rand_num":
            self.eat("KEYWORD")
            self.eat("SYMBOL")
            start = self.comparison()
            self.eat("SYMBOL")
            end = self.comparison()
            self.eat("SYMBOL")
            return RandNumNode(start, end)
        
        # Parenthesized expressions
        if tok.type == "SYMBOL" and tok.value == "(":
            self.eat("SYMBOL")
            node = self.comparison()
            self.eat("SYMBOL")
            return node

        if tok.type == "BRACKET" and tok.value == "[":
            return self.list_literal()
            
        if tok.type == "BRACKET" and tok.value == "{":
            return self.dict_literal()
            
        # Type casting variables
        if tok.type == "KEYWORD" and tok.value in ("int", "str", "float"):
            func_name = self.eat("KEYWORD").value
            self.eat("SYMBOL")  # (
            arg = self.comparison()
            self.eat("SYMBOL")  # )
            return CastNode(func_name, arg)
        
        if tok.type == "KEYWORD" and tok.value == "true":
            self.eat("KEYWORD")
            return BoolNode(True)

        if tok.type == "KEYWORD" and tok.value == "false":
            self.eat("KEYWORD")
            return BoolNode(False)
            
        if tok.type == "KEYWORD" and tok.value == "len":
            self.eat("KEYWORD") 
            self.eat("SYMBOL") 
            expr_node = self.comparison() 
            self.eat("SYMBOL")  
            return LenNode(expr_node)
        
        # Built-in list traversal logic mapped physically to 'call' implementation
        if tok.type == "KEYWORD" and tok.value == "call":
            self.eat("KEYWORD")
            self.eat("BRACKET")  # [
            list_node = self.comparison()
            self.eat("SYMBOL")  # ,
            pos = self.comparison()
            self.eat("BRACKET")  # ]
            return listCallNode(list_node, pos)
            
        raise SyntaxError(f"Unexpected token {tok}")


        
    def list_literal(self):
        """Parses list literals."""
        elements = []
        if self.current_token().type == "BRACKET" and self.current_token().value == "[":
            self.eat("BRACKET")  # [

            if self.current_token().value != "]":
                elements.append(self.comparison())
                while self.current_token().value == ",":
                    self.eat("SYMBOL")
                    elements.append(self.comparison())

            self.eat("BRACKET")  # ]
            return ListNode(elements)

    def dict_literal(self):
        """Parses dictionary mappings."""
        elements = {}
        if self.current_token().type == "BRACKET" and self.current_token().value == "{":
            self.eat("BRACKET")  # {

            if self.current_token().value != "}":
                key = self.comparison()
                self.eat("SYMBOL")  # :
                value = self.comparison()
                elements[key] = value

                while self.current_token().value == ",":
                    self.eat("SYMBOL")
                    key = self.comparison()
                    self.eat("SYMBOL")  # :
                    value = self.comparison()
                    elements[key] = value

            self.eat("BRACKET")  # }
            return DictNode(elements)
        
        
    def term(self):
        """Evaluates multiplication and division with precedence."""
        node = self.factor()
        while self.current_token().type == "ARITH" and self.current_token().value in ("*", "/"):
            op = self.eat("ARITH").value
            node = BinOpNode(node, op, self.factor())
        return node

    def expr(self):
        """Evaluates addition and subtraction with precedence mapped back recursively."""
        node = self.term()
        while self.current_token().type == "ARITH" and self.current_token().value in ("+", "-"):
            op = self.eat("ARITH").value
            node = BinOpNode(node, op, self.term())
        return node

    def comparison(self):
        """Evaluates general-purpose comparison operations."""
        node = self.expr()
        if self.current_token().type == "COMP":
            op = self.eat("COMP").value
            right = self.expr()
            return BinOpNode(node, op, right)
        return node

    def assignment(self, type_):
        """Identifies assignment declarations (let, const, or state setters)."""
        if type_ == "const":
            self.eat("KEYWORD")
            name = self.eat("IDENT").value
            self.eat("SYMBOL")
            _type = self.eat("KEYWORD").value
            self.eat("ASSIGN")
            value = self.comparison()
            return ConstAssignNode(name, value)
        elif type_ == "let":
            self.eat("KEYWORD")
            name = self.eat("IDENT").value
            self.eat("SYMBOL")
            _type = self.eat("KEYWORD").value
            self.eat("ASSIGN")
            value = self.comparison()
            return AssignNode(name, value, _type)
        elif type_ == "set":
            self.eat("KEYWORD")
            name = self.eat("IDENT").value
            self.eat("BRACKET")
            num = self.eat("INT")
            self.eat("BRACKET")
            self.eat("ASSIGN")
            type_ = self.eat("IDENT").value
            self.eat("SYMBOL")
            param = self.eat("INT").value
            return SetNode(name,num,  type_, param)
    def print_stmt(self):
        """Handles built-in stream writing out via print."""
        self.eat("KEYWORD")
        var = self.comparison()
        try:
            self.eat("KEYWORD") # as
            _type = self.eat("KEYWORD").value
            # print(var)
            # print(_type)
            print(var)
            if var.type == _type:
                return PrintNode(var, _type)
            elif var.type == self.types[_type]:
                if _type == "float":
                    var = NumberNode(var.value, "float")
                    return PrintNode(var, None)
                elif _type == "int":
                    var = NumberNode(var.value, "int")
                    return PrintNode(var, None)
                
            elif var.type != _type:
                raise SyntaxError(f"Type mismatch at {var.value}")
        except SyntaxError:
            return PrintNode(var, None)
                    
    
    def exec_stmt(self):
        """Handles code inline-execution statements."""
        self.eat("KEYWORD")
        code = self.eat("STRING").value[1:-1]
        return ExecNode(code)
    
    def block(self):
        """Parses a scoped block of statements encapsulating logical steps within { }. """
        statements = []
        self.eat("BRACKET")  

        while not (self.current_token().type == "BRACKET" and self.current_token().value == "}"):
            statements.append(self.statement())
            while self.current_token().type == "NEWLINE":
                self.eat("NEWLINE")

        self.eat("BRACKET")  # }
        return BlockNode(statements)
    
    def len_stmt(self):
        """Handles mapping collection string/array lengths respectively."""
        self.eat("KEYWORD")
        self.eat("SYMBOL")
        value = self.comparison()
        self.eat("SYMBOL")
        return LenNode(value)
        
    def listCall(self):
        """Specific array retrieval parser mapped contextually manually."""
        self.eat("KEYWORD")
        self.eat("BRACKET")  # [
        list_node = self.comparison()
        self.eat("SYMBOL")  # ,
        pos = self.comparison()
        self.eat("BRACKET")  # ]
        return listCallNode(list_node, pos)
    
    def if_stmt(self):
        """Parses if / elif / else control flow structures recursively."""
        self.eat("KEYWORD")  # 'if'
        condition = self.comparison()
        then_body = self.block()

        elif_nodes = []
        while True:
            self.skip_newlines()  # skip all newlines before next keyword
            tok = self.current_token()
            if tok.type == "KEYWORD" and tok.value == "elif":
                self.eat("KEYWORD")
                elif_condition = self.comparison()
                elif_body = self.block()
                elif_nodes.append(ElifNode(elif_condition, elif_body))
            else:
                break

        else_body = None
        self.skip_newlines()
        if self.current_token().type == "KEYWORD" and self.current_token().value == "else":
            self.eat("KEYWORD")
            else_body = self.block()

        return IfNode(condition, then_body, elif_nodes, else_body)

    def try_stmt(self):
        """Parses structured error-catching boundaries (try-except)."""
        self.eat("KEYWORD")  # 'try'
        self.skip_newlines() 
        self.eat("BRACKET")   # '{'
        try_body = self.block()

        except_nodes = []
        while True:
            self.skip_newlines()
            tok = self.current_token()
            if tok.type == "KEYWORD" and tok.value == "except":
                self.eat("KEYWORD")
                self.skip_newlines()  # allow newline before '{'
                except_body = self.block()
                except_nodes.append(except_body)
            else:
                break

        else_body = None
        self.skip_newlines()
        if self.current_token().type == "KEYWORD" and self.current_token().value == "else":
            self.eat("KEYWORD")
            self.skip_newlines()  # allow newline before '{'
            else_body = self.block()

        return TryNode(try_body, except_nodes, else_body)


    
    def while_stmt(self):
        """Parses infinite or condition-loop mapped behaviors conditionally."""
        self.eat("KEYWORD")
        condition = self.comparison()
        body = self.block()
        return WhileNode(condition, body)

    def par_stmt(self):
        """Parses thread spanning contexts parallel to main process mapping."""
        self.eat("KEYWORD")
        try:
            self.eat("SYMBOL")
            threads = self.eat("INT")
            self.eat("SYMBOL")
        except:
            threads = 0
        body = self.block()
        return ParallelNode(body, threads)
    
    def class_stmt(self):
        """Translates OOP definition mapping objects conceptually class-level blocks."""
        self.eat("KEYWORD")  
        class_name = self.eat("IDENT").value
        self.eat("BRACKET") 

        fields = []
        methods = {}

        while not (self.current_token().type == "BRACKET" and self.current_token().value == "}"):
            tok = self.current_token()
            if tok.type == "KEYWORD" and tok.value == "let":
                self.eat("KEYWORD")
                field_name = self.eat("IDENT").value
                fields.append(field_name)
            if tok.type == "KEYWORD" and tok.value == "def":
                method = self.func_stmt()
                methods[method.name] = method
            else:
                raise SyntaxError(f"Unexpected Token: {tok.type} in class {class_name}")
        
    def func_stmt(self):
        """Defines functions capturing context, scope mappings explicitly."""
        self.eat("KEYWORD")     
        name = self.eat("IDENT").value  
        self.eat("SYMBOL")               

        params = []
        while self.current_token().type != "SYMBOL" or self.current_token().value != ")":
            tok = self.current_token()
            if tok.type == "IDENT":
                params.append(tok.value)
                self.eat("IDENT")
            elif tok.type == "SYMBOL":
                self.eat("SYMBOL")        
            else:
                raise SyntaxError(f"Unexpected token in parameter list: {tok.type} ({tok.value})")

        self.eat("SYMBOL")              
        body = self.block()            
        return FuncNode(name, params, body)

    def for_stmt(self):
        """Defines context iterations for generators and object states."""
        self.eat("KEYWORD")
        itr = self.eat("IDENT").value
        self.eat("KEYWORD")
        iterable = self.factor()
        body = self.block()
        return ForNode(itr, iterable, body)

    def unary(self):
        """Recursively parses unary state operations ensuring context logic cascades properly."""
        tok = self.current_token()
        if tok.type == "UNARY" or (tok.type == "LOGIC" and tok.value in ("not", "!")):
            op = self.eat(tok.type).value
            node = self.unary()
            return UnaryOpNode(op, node)
        return self.factor()
    def logic(self):
        """Translates basic general logic (and/or logic flows)."""
        node = self.comparison()
        while self.current_token().type == "LOGIC":
            op = self.eat("LOGIC").value
            right = self.comparison()
            node = LogicOpNode(node, op, right)
        return node
    def import_stmt(self):
        """Translates external module requirement directives strictly defining context logic mappings."""
        self.eat("KEYWORD")
        name_token = self.eat("IDENT")
        if self.current_token().value == "\\n":
            return ImportNode(name_token)
        else:
            self.eat("KEYWORD")
            nName = self.eat("IDENT")
            return ImportAsNode(name_token, nName)
    def import_from_stmt(self):
        """Specific from-module extraction logically bound exclusively contextually."""
        self.eat("KEYWORD")
        name = self.eat("IDENT")
        self.eat("KEYWORD")
        lib = self.eat("IDENT")
        return ImportFromNode(name, lib)
    
    def import_as_stmt(self):
        """Alias resolving namespace collisions dynamically mappings externally locally bound explicitly."""
        self.eat("KEYWORD")
        name = self.eat("IDENT")
        self.eat("KEYWORD") 
        nName = self.eat("IDENT")
        return ImportAsNode(name, nName)
        

        
    def special_expr(self):
        """Resolves edge behaviors mappings explicitly ensuring distinct processing uniquely bounded."""
        node = self.logic()
        while self.current_token().type == "SPECIAL":
            op = self.eat("SPECIAL").value
            right = self.logic()
            node = SpecialOpNode(node, op, right)
        return node

    def statement(self):
        """
        Parses overarching flow statements routing contexts logically into
        AST evaluations bound implicitly across scopes cleanly uniformly spanning all logic.
        """
        self.skip_newlines() 
        if self.current_token().type == "IDENT":
            start_pos = self.pos
            target = self.comparison()

            # Direct mapping context
            if self.current_token().type == "ASSIGN":
                self.eat("ASSIGN")
                value = self.comparison()
                if isinstance(target, IndexNode):
                    return IndexAssignNode(target.collection, target.index, value)
                if isinstance(target, VarNode):
                    return AssignNode(target.name, value, target.type)

            # Complex compounding evaluations internally managed explicitly bounds inherently mapped naturally
            if isinstance(target, VarNode) and self.current_token().type == "ASSIGN_OP":
                op = self.eat("ASSIGN_OP").value
                value = self.comparison()
                return CompoundAssignNode(target.name, op, value)

            self.pos = start_pos
                
        
        self.skip_newlines()
        tok = self.current_token()
        if tok.type == "KEYWORD":
            if tok.value == "exec":
                return self.exec_stmt()
            if tok.value in ("elif", "else"):
                raise SyntaxError(f"Unexpected '{tok.value}' outside of if statement")
            if tok.value in ("let"):
                return self.assignment("let")
            if tok.value in ("set"):
                return self.assignment("set")
            if tok.value in ("const"):
                return self.assignment("const")
            if tok.value == "print":
                return self.print_stmt()
            if tok.value == "none":
                return NoneNode()
            if tok.value == "pass":
                return PassNode()
            if tok.value == "if":
                return self.if_stmt()
            if tok.value == "try":
                return self.try_stmt()
            if tok.value == "while":
                return self.while_stmt()
            if tok.value == "parallel":
                return self.par_stmt()
            if tok.value == "def":
                return self.func_stmt()
            if tok.value == "class":
                return self.class_stmt()
            if tok.value == "for":
                return self.for_stmt()
            if tok.value == "len": 
                return self.len_stmt()
            if tok.value == "call":
                return self.listCall()
            if tok.value == "import":
                    return self.import_stmt()
            if tok.value == "from":
                return self.import_from_stmt()
            if tok.value == "break":
                self.eat("KEYWORD")
                return BreakNode()
            if tok.value == "continue":
                self.eat("KEYWORD")
                return ContinueNode()
            if tok.type == "KEYWORD" and tok.value == "return":
                self.eat("KEYWORD")
                return ReturnNode(self.comparison())
            if tok.type == "KEYWORD" and tok.value == "yield":
                self.eat("KEYWORD")
                return YieldNode(self.comparison())
        return self.comparison()

    def program(self):
        """Top-level mapping recursively encapsulating entirety logically distinct statements."""
        statements = []
        while self.current_token().type != "EOF":
            statements.append(self.statement())
            while self.current_token().type == "NEWLINE":
                self.eat("NEWLINE")
        return ProgramNode(statements)
    
    def skip_newlines(self):
        """Helper to navigate empty lines inherently generated explicitly inherently ensuring parsing safety."""
        while self.current_token().type == "NEWLINE":
            self.eat("NEWLINE")
