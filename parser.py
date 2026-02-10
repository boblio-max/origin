from lexer import Token, lex
from classes import *

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def current_token(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return Token("EOF", "", -1, -1)

    def eat(self, type_):
        tok = self.current_token()
        if tok.type == type_:
            self.pos += 1
            return tok
        raise SyntaxError(f"Expected {type_}, got {tok.type} ({tok.value})")

    def factor(self):
        self.skip_newlines()
        tok = self.current_token()

        if tok.type == "INT":
            self.eat("INT")
            return NumberNode(int(tok.value))

        if tok.type == "negate":
            self.eat("negate")
            return UnaryOpNode('-', self.factor())
        
        if tok.type == "FLOAT":
            self.eat("FLOAT")
            return NumberNode(float(tok.value))

        
        if tok.type == "STRING":
            self.eat("STRING")
            return StringNode(tok.value[1:-1] )
        
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
                if self.current_token().type == "BRACKET" and self.current_token().value == "[":
                    self.eat("BRACKET")
                    index = self.comparison()
                    self.eat("BRACKET")
                    node = IndexNode(node, index)

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
            
        if tok.type == "KEYWORD" and tok.value == "rand_num":
            self.eat("KEYWORD")
            self.eat("SYMBOL")
            start = self.comparison()
            self.eat("SYMBOL")
            end = self.comparison()
            self.eat("SYMBOL")
            return RandNumNode(start, end)
        
        if tok.type == "BRACKET" and tok.value == "(":
            self.eat("BRACKET")
            node = self.comparison()
            self.eat("BRACKET")
            return node

        if tok.type == "BRACKET" and tok.value == "[":
            return self.list_literal()
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
        elements = []
        self.eat("BRACKET")  # [

        if self.current_token().value != "]":
            elements.append(self.comparison())
            while self.current_token().value == ",":
                self.eat("SYMBOL")
                elements.append(self.comparison())

        self.eat("BRACKET")  # ]
        return ListNode(elements)

    def term(self):
        node = self.factor()
        while self.current_token().type == "ARITH" and self.current_token().value in ("*", "/"):
            op = self.eat("ARITH").value
            node = BinOpNode(node, op, self.factor())
        return node

    def expr(self):
        node = self.term()
        while self.current_token().type == "ARITH" and self.current_token().value in ("+", "-"):
            op = self.eat("ARITH").value
            node = BinOpNode(node, op, self.term())
        return node

    def comparison(self):
        node = self.expr()
        if self.current_token().type == "COMP":
            op = self.eat("COMP").value
            right = self.expr()
            return BinOpNode(node, op, right)
        return node

    def assignment(self, type_):
        if type_ == "const":
            self.eat("KEYWORD")
            name = self.eat("IDENT").value
            self.eat("ASSIGN")
            value = self.comparison()
            return ConstAssignNode(name, value)
        elif type_ == "let":
            self.eat("KEYWORD")
            name = self.eat("IDENT").value
            self.eat("ASSIGN")
            value = self.comparison()
            return AssignNode(name, value)
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
        self.eat("KEYWORD")
        return PrintNode(self.comparison())
    
    def block(self):
        statements = []
        self.eat("BRACKET")  

        while not (self.current_token().type == "BRACKET" and self.current_token().value == "}"):
            statements.append(self.statement())
            while self.current_token().type == "NEWLINE":
                self.eat("NEWLINE")

        self.eat("BRACKET")  # }
        return BlockNode(statements)
    
    def len_stmt(self):
        self.eat("KEYWORD")
        self.eat("SYMBOL")
        value = self.comparison()
        self.eat("SYMBOL")
        return LenNode(value)
    def listCall(self):
        self.eat("KEYWORD")
        self.eat("BRACKET")  # [
        list_node = self.comparison()
        self.eat("SYMBOL")  # ,
        pos = self.comparison()
        self.eat("BRACKET")  # ]
        return listCallNode(list_node, pos)
    
    def if_stmt(self):
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
        self.eat("KEYWORD")
        condition = self.comparison()
        body = self.block()
        return WhileNode(condition, body)

    def class_stmt(self):
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
        self.eat("KEYWORD")
        itr = self.eat("IDENT").value
        self.eat("KEYWORD")
        iterable = self.factor()
        body = self.block()
        return ForNode(itr, iterable, body)

    def unary(self):
        tok = self.current_token()
        if tok.type == "UNARY" or (tok.type == "LOGIC" and tok.value in ("not", "!")):
            op = self.eat(tok.type).value
            node = self.unary()
            return UnaryOpNode(op, node)
        return self.factor()
    def logic(self):
        node = self.comparison()
        while self.current_token().type == "LOGIC":
            op = self.eat("LOGIC").value
            right = self.comparison()
            node = LogicOpNode(node, op, right)
        return node
    def import_stmt(self):
        self.eat("KEYWORD")
        name_token = self.eat("IDENT")
        if self.current_token().value == "\\n":
            return ImportNode(name_token)
        else:
            self.eat("KEYWORD")
            nName = self.eat("IDENT")
            return ImportAsNode(name_token, nName)
    def import_from_stmt(self):
        self.eat("KEYWORD")
        name = self.eat("IDENT")
        if self.current_token() == ".":
            print("coolio")
        self.eat("KEYWORD")
        lib = self.eat("IDENT")
        return ImportFromNode(name,lib)
    
    def import_as_stmt(self):
        self.eat("KEYWORD")
        name = self.eat("IDENT")
        self.eat("KEYWORD") 
        nName = self.eat("IDENT")
        return ImportAsNode(name, nName)
        

        
    def special_expr(self):
        node = self.logic()
        while self.current_token().type == "SPECIAL":
            op = self.eat("SPECIAL").value
            right = self.logic()
            node = SpecialOpNode(node, op, right)
        return node

    def statement(self):
        self.skip_newlines() 
        if self.current_token().type == "IDENT":
            start_pos = self.pos
            target = self.comparison()

            if self.current_token().type == "ASSIGN":
                self.eat("ASSIGN")
                value = self.comparison()
                if isinstance(target, IndexNode):
                    return IndexAssignNode(target.collection, target.index, value)
                if isinstance(target, VarNode):
                    return AssignNode(target.name, value)

            if isinstance(target, VarNode) and self.current_token().type == "ASSIGN_OP":
                op = self.eat("ASSIGN_OP").value
                value = self.comparison()
                return CompoundAssignNode(target.name, op, value)

            self.pos = start_pos
                
        
        self.skip_newlines()
        tok = self.current_token()
        if tok.type == "KEYWORD":
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
            if tok.value == "if":
                return self.if_stmt()
            if tok.value == "try":
                return self.try_stmt()
            if tok.value == "while":
                return self.while_stmt()
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
        statements = []
        while self.current_token().type != "EOF":
            statements.append(self.statement())
            while self.current_token().type == "NEWLINE":
                self.eat("NEWLINE")
        return ProgramNode(statements)
    
    def skip_newlines(self):
        while self.current_token().type == "NEWLINE":
            self.eat("NEWLINE")
