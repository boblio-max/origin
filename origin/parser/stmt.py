"""Statement parsing (statement + _statement)."""
import sys
import textwrap
from ..lexer.lexer_point import lex, Token
from ..classes import *
from ..errors import ParseError


class StmtMixin:
    def statement(self):
        self.skip_newlines()
        line = self.current_token().line
        node = self._statement()
        return self._set_line(node, line)

    def _statement(self):
        tok = self.current_token()
        
        if tok.type == "IDENT":
            start_pos = self.pos
            try:
                target = self.special_expr()
                if self.current_token().type == "ASSIGN":
                    self.eat("ASSIGN")
                    value = self.special_expr()
                    if isinstance(target, IndexNode):
                        return IndexAssignNode(target.collection, target.index, value)
                    if isinstance(target, VarNode):
                        return AssignNode(target.name, value)
                    if isinstance(target, AttributeNode):
                        return AttributeAssignNode(target.obj, target.attr, value)
                
                if isinstance(target, VarNode) and self.current_token().type == "ASSIGN_OP":
                    op = self.eat("ASSIGN_OP").value
                    value = self.special_expr()
                    return CompoundAssignNode(target.name, op, value)
            except SyntaxError:
                pass
            self.pos = start_pos

        if tok.type == "KEYWORD":
            if tok.value == "let":
                self.eat("KEYWORD")
                names = [self.eat(self.current_token().type).value]
                while self.current_token().value == ",":
                    self.eat("SYMBOL")
                    names.append(self.eat(self.current_token().type).value)
                _types = []
                if self.current_token().value == ":":
                    self.eat("SYMBOL")
                    while True:
                        _types.append(self.eat(self.current_token().type).value)
                        if self.current_token().value == ",":
                            self.eat("SYMBOL")
                        else:
                            break
                else:
                    # No type annotation: nudge toward strict typing, but auto-infer
                    print(
                        f"[WARNING] Variable '{names[0]}' declared without a type annotation; "
                        f"the type will be inferred. Tip: use `let {names[0]}: <type> = ...` "
                        f"for strict typing.",
                        file=sys.stderr,
                    )
                self.eat("ASSIGN")
                values = [self.special_expr()]
                while self.current_token().value == ",":
                    self.eat("SYMBOL")
                    values.append(self.special_expr())
                if len(names) == 1:
                    return MultAssignNode(names[0], values[0], _types[0] if _types else None)
                return MultAssignNode(names, values, _types or [None])

            if tok.value == "self":
                start_pos = self.pos
                try:
                    target = self.factor()
                    if self.current_token().type == "ASSIGN":
                        self.eat("ASSIGN")
                        value = self.special_expr()
                        if isinstance(target, AttributeNode):
                            return AttributeAssignNode(target.obj, target.attr, value)
                except SyntaxError:
                    pass
                self.pos = start_pos
                
            if tok.value == "const":
                self.eat("KEYWORD")
                name = self.eat(self.current_token().type).value
                _type = None
                if self.current_token().value == ":":
                    self.eat("SYMBOL")
                    _type = self.eat(self.current_token().type).value
                else:
                    # No type annotation: nudge toward strict typing, but auto-infer
                    print(
                        f"[WARNING] Constant '{name}' declared without a type annotation; "
                        f"the type will be inferred. Tip: use `const {name}: <type> = ...` "
                        f"for strict typing.",
                        file=sys.stderr,
                    )
                self.eat("ASSIGN")
                value = self.special_expr()
                return ConstAssignNode(name, value, _type)

            if tok.value == "set":
                self.eat("KEYWORD")
                name = self.eat("IDENT").value
                if self.current_token().value == "[":
                    self.eat("BRACKET")
                    num = self.special_expr()
                    self.eat("BRACKET")
                    self.eat("ASSIGN")
                    subtype = self.eat("IDENT").value
                    if self.current_token().value == ",": self.eat("SYMBOL")
                    param = self.special_expr()
                else:
                    subtype = None
                    if self.current_token().value == ".":
                        self.eat("SYMBOL")
                        subtype = self.eat("IDENT").value
                    num = self.special_expr()
                    if self.current_token().value == ",": self.eat("SYMBOL")
                    param = self.special_expr()
                return SetNode(name, num, subtype, param)
            if tok.value == "print":
                # Support both normal print statements and single-line `print ... for ...` forms
                self.eat("KEYWORD")
                # Parse one or more comma-separated expressions as print arguments
                args = []
                self.skip_newlines()
                # If next token is not a for/EOF/BRACE, parse expressions
                if not (self.current_token().type == "KEYWORD" and self.current_token().value == "for"):
                    args.append(self.special_expr())
                    while self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                        self.eat("SYMBOL")
                        self.skip_newlines()
                        # Stop if 'for' follows (allow trailing commas before for)
                        if self.current_token().type == "KEYWORD" and self.current_token().value == "for":
                            break
                        args.append(self.special_expr())

                expr_node = args[0] if len(args) == 1 else TupleNode(args)

                # Handle single-line `print ... for ...` syntax
                if self.current_token().type == "KEYWORD" and self.current_token().value == "for":
                    # Reuse the existing for-loop parsing logic: parse target and iterable
                    self.eat("KEYWORD")
                    # Parse target: allow single identifier or unpacking (reuse logic similar to for branch)
                    if self.current_token().type == "SYMBOL" and self.current_token().value == "(":
                        self.eat("SYMBOL")
                        targets = []
                        self.skip_newlines()
                        if not (self.current_token().type == "SYMBOL" and self.current_token().value == ")"):
                            if self.current_token().type in ("IDENT", "KEYWORD"):
                                targets.append(VarNode(self.eat(self.current_token().type).value))
                            while self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                                self.eat("SYMBOL")
                                self.skip_newlines()
                                targets.append(VarNode(self.eat(self.current_token().type).value))
                        self.skip_newlines()
                        self.eat("SYMBOL")
                        var = TupleNode(targets)
                    elif self.current_token().type == "BRACKET" and self.current_token().value == "[":
                        self.eat("BRACKET")
                        targets = []
                        self.skip_newlines()
                        if not (self.current_token().type == "BRACKET" and self.current_token().value == "]"):
                            if self.current_token().type in ("IDENT", "KEYWORD"):
                                targets.append(VarNode(self.eat(self.current_token().type).value))
                            while self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                                self.eat("SYMBOL")
                                self.skip_newlines()
                                targets.append(VarNode(self.eat(self.current_token().type).value))
                        self.skip_newlines()
                        self.eat("BRACKET")
                        var = ListNode(targets)
                    else:
                        # bare unpacking or single identifier
                        if self.current_token().type in ("IDENT", "KEYWORD"):
                            first_name = self.eat(self.current_token().type).value
                            if self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                                targets = [VarNode(first_name)]
                                while self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                                    self.eat("SYMBOL")
                                    self.skip_newlines()
                                    targets.append(VarNode(self.eat(self.current_token().type).value))
                                var = TupleNode(targets)
                            else:
                                var = VarNode(first_name)
                        else:
                            raise self._error("Expected identifier for for-loop target")

                    self.eat("KEYWORD") # in
                    iterable = self.special_expr()
                    # Build a ForNode whose body is a single PrintNode of the parsed expr_node
                    return ForNode(var, iterable, BlockNode([PrintNode(expr_node)]))

                return PrintNode(expr_node)

            if tok.value == "if":
                return self.if_stmt()

            if tok.value == "while":
                self.eat("KEYWORD")
                condition = self._cast_or_none(self.special_expr())
                body = self.block()
                return WhileNode(condition, body)
        
            if tok.value == "match":
                self.eat("KEYWORD")
                name = self.eat("IDENT").value
                self.match_block(name)
                 
            if tok.value == "run":
                self.eat("KEYWORD")  # run
                cmd_tok = self.current_token()
                if cmd_tok.type != "KEYWORD" or cmd_tok.value != "command":
                    raise self._error(f"Expected 'command' after 'run' but got {cmd_tok.type} ({cmd_tok.value})")
                self.eat("KEYWORD")  # command
                str_tok = self.eat("STRING")
                command = str_tok.value[1:-1]  # strip surrounding quotes
                flags = None
                if self.current_token().type == "BRACKET" and self.current_token().value == "{":
                    flags = self.block()
                return CommandNode(command, flags)
                
            if tok.value == "for":
                self.eat("KEYWORD")
                # Parse target: allow a single identifier or an unpacking tuple/list
                if self.current_token().type == "SYMBOL" and self.current_token().value == "(":
                    # Parenthesized unpacking target
                    self.eat("SYMBOL")  # (
                    targets = []
                    self.skip_newlines()
                    if not (self.current_token().type == "SYMBOL" and self.current_token().value == ")"):
                        if self.current_token().type in ("IDENT", "KEYWORD"):
                            targets.append(VarNode(self.eat(self.current_token().type).value))
                        while self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                            self.eat("SYMBOL")
                            self.skip_newlines()
                            targets.append(VarNode(self.eat(self.current_token().type).value))
                    self.skip_newlines()
                    self.eat("SYMBOL")  # )
                    var = TupleNode(targets)
                elif self.current_token().type == "BRACKET" and self.current_token().value == "[":
                    # Bracketed unpacking target
                    self.eat("BRACKET")  # [
                    targets = []
                    self.skip_newlines()
                    if not (self.current_token().type == "BRACKET" and self.current_token().value == "]"):
                        if self.current_token().type in ("IDENT", "KEYWORD"):
                            targets.append(VarNode(self.eat(self.current_token().type).value))
                        while self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                            self.eat("SYMBOL")
                            self.skip_newlines()
                            targets.append(VarNode(self.eat(self.current_token().type).value))
                    self.skip_newlines()
                    self.eat("BRACKET")  # ]
                    var = ListNode(targets)
                else:
                    # Support bare unpacking: `for a, b in iterable` (no parentheses)
                    if self.current_token().type in ("IDENT", "KEYWORD"):
                        first_name = self.eat(self.current_token().type).value
                        if self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                            targets = [VarNode(first_name)]
                            while self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                                self.eat("SYMBOL")
                                self.skip_newlines()
                                if self.current_token().type in ("IDENT", "KEYWORD"):
                                    targets.append(VarNode(self.eat(self.current_token().type).value))
                                else:
                                    raise self._error("Expected identifier in unpacking target")
                            var = TupleNode(targets)
                        else:
                            var = VarNode(first_name)
                            var_type = None
                            if self.current_token().type == "SYMBOL" and self.current_token().value == ":":
                                var_type = self._parse_type_annotation(allow_ident=True)
                            var.var_type = var_type
                    else:
                        raise self._error("Expected identifier for for-loop target")
                self.eat("KEYWORD") # in
                iterable = self.special_expr()
                body = self.block()
                return ForNode(var, iterable, body)

            if tok.value in ("def", "func"):
                self.eat("KEYWORD")
                if self.current_token().type in ("IDENT", "KEYWORD"):
                    name = self.eat(self.current_token().type).value
                else:
                    tok_name = self.current_token()
                    raise self._error(
                        f"Expected function name, got {tok_name.type} ({tok_name.value})"
                    )
                self.eat("SYMBOL") # (
                params = []
                param_types = {}
                if self.current_token().value != ")":
                    p_tok = self.current_token()
                    if p_tok.type in ("IDENT", "KEYWORD"):
                        pname = self.eat(p_tok.type).value
                        params.append(pname)
                        ptype = self._parse_type_annotation(allow_ident=True)
                        if ptype:
                            param_types[pname] = ptype
                        # Optional default value `= <expr>` (e.g. `indent=4`, `mode="vm"`)
                        if self.current_token().type == "ASSIGN" and self.current_token().value == "=":
                            self.eat("ASSIGN")
                            self.special_expr()
                    else:
                            raise self._error("Expected parameter name in function definition")
                    while self.current_token().value == ",":
                        self.eat("SYMBOL")
                        p_tok = self.current_token()
                        if p_tok.type in ("IDENT", "KEYWORD"):
                            pname = self.eat(p_tok.type).value
                            params.append(pname)
                            ptype = self._parse_type_annotation(allow_ident=True)
                            if ptype:
                                param_types[pname] = ptype
                            if self.current_token().type == "ASSIGN" and self.current_token().value == "=":
                                self.eat("ASSIGN")
                                self.special_expr()
                        else:
                            raise self._error("Expected parameter name in function definition")
                self.eat("SYMBOL") # )
                body = self.block()
                return FuncNode(name, params, body, param_types)

            if tok.value == "class":
                self.eat("KEYWORD")
                if self.current_token().type in ("IDENT", "KEYWORD"):
                    name = self.eat(self.current_token().type).value
                else:
                    tok_name = self.current_token()
                    raise self._error(
                        f"Expected class name, got {tok_name.type} ({tok_name.value})"
                    )
                self.eat("SYMBOL") # (
                fields = []
                field_types = {}
                if self.current_token().value != ")":
                    fname = self.eat("IDENT").value
                    fields.append(fname)
                    ftype = self._parse_type_annotation(allow_ident=True)
                    if ftype:
                        field_types[fname] = ftype
                    while self.current_token().value == ",":
                        self.eat("SYMBOL")
                        fname = self.eat("IDENT").value
                        fields.append(fname)
                        ftype = self._parse_type_annotation(allow_ident=True)
                        if ftype:
                            field_types[fname] = ftype
                self.eat("SYMBOL") # )
                body = self.block()
                return ClassNode(name, fields, body, field_types)

            if tok.value == "try":
                self.eat("KEYWORD")
                try_body = self.block()
                except_nodes = []
                while True:
                    self.skip_newlines()
                    if self.current_token().value == "except":
                        self.eat("KEYWORD")
                        except_nodes.append(self.block())
                    else:
                        break
                else_body = None
                if self.current_token().value == "else":
                    self.eat("KEYWORD")
                    else_body = self.block()
                return TryNode(try_body, except_nodes, else_body)

            if tok.value == "parallel":
                self.eat("KEYWORD")
                threads = 0
                if self.current_token().value == "(":
                    self.eat("SYMBOL")
                    threads = int(self.eat("INT").value)
                    self.eat("SYMBOL")
                body = self.block()
                return ParallelNode(body, threads)

            if tok.value == "import":
                self.eat("KEYWORD")
                # Allow keywords as module names and dotted paths (e.g. bc.byte_key)
                name = self.eat(self.current_token().type).value
                while self.current_token().type == "SYMBOL" and self.current_token().value == ".":
                    self.eat("SYMBOL")
                    name += "." + self.eat(self.current_token().type).value
                if self.current_token().value == "as":
                    self.eat("KEYWORD")
                    alias = self.eat("IDENT").value
                    return ImportAsNode(name, alias)
                return ImportNode(name)

            if tok.value == "from":
                self.eat("KEYWORD")
                # Module name may be dotted (e.g. bc.byte_key)
                lib = self.eat(self.current_token().type).value
                while self.current_token().type == "SYMBOL" and self.current_token().value == ".":
                    self.eat("SYMBOL")
                    lib += "." + self.eat(self.current_token().type).value
                self.eat("KEYWORD") # import
                # Allow keywords as imported names; support comma-separated list
                # Grammar allows single Ident, but tolerate `a, b, c` for convenience
                names = []
                names.append(self.eat(self.current_token().type).value)
                while self.current_token().type == "SYMBOL" and self.current_token().value == ",":
                    self.eat("SYMBOL")
                    self.skip_newlines()
                    names.append(self.eat(self.current_token().type).value)
                # If multiple names, we store them as comma-joined string in ImportFromNode
                # and let the interpreter handle splitting; for now return first and
                # rely on inorigin files being split into single imports.
                if len(names) == 1:
                    return ImportFromNode(names[0], lib)
                else:
                    # Store as ImportFromNode with first name, but also handle via multiple nodes
                    # For compatibility, return a BlockNode containing multiple ImportFromNodes
                    # However parser expects single node; we handle by returning the first and
                    # the caller will need to handle the rest via separate statements.
                    # Instead, we join and let classes handle split.
                    return ImportFromNode(", ".join(names), lib)

            if tok.value == "return":
                self.eat("KEYWORD")
                # Return may be bare (no value) – e.g. `return` inside void function
                if self.current_token().type in ("NEWLINE", "EOF") or self.current_token().value in ("}", ";"):
                    return ReturnNode(NoneNode())
                try:
                    return ReturnNode(self.special_expr())
                except SyntaxError:
                    return ReturnNode(NoneNode())

            if tok.value == "break":
                self.eat("KEYWORD")
                return BreakNode()

            if tok.value in ["continue", "skip"]:
                self.eat("KEYWORD")
                return ContinueNode()

            if tok.value == "pass":
                self.eat("KEYWORD")
                return PassNode()
            
            if tok.value == "exec":
                self.eat("KEYWORD")
                return ExecNode(self.eat("STRING").value[1:-1])

            if tok.value == "py":
                self.eat("KEYWORD")
                self.eat("BRACKET") # {
                raw = ""
                depth = 1
                while depth > 0:
                    t = self.tokens[self.pos]
                    self.pos += 1
                    if t.type == "BRACKET" and t.value == "{":
                        depth += 1
                    elif t.type == "BRACKET" and t.value == "}":
                        depth -= 1
                        if depth == 0:
                            break
                    if t.type == "NEWLINE":
                        raw += "\n"
                    elif t.type == "WHITESPACE":
                        raw += t.value
                    else:
                        token_str = t.value
                        if raw and not raw.endswith((" ", "\n")):
                            prev_char = raw[-1]
                            if prev_char in ("(", "[", "{", "."):
                                raw += token_str
                            elif token_str in (")", "]", "}", ",", ":", ";", "."):
                                raw += token_str
                            elif token_str in ("(", "[", "{"):
                                raw += token_str
                            else:
                                raw += " " + token_str
                        else:
                            raw += token_str
                lines = raw.split("\n")
                non_empty = [l for l in lines if l.strip()]
                if non_empty:
                    min_indent = min(len(l) - len(l.lstrip()) for l in non_empty)
                    lines = [l[min_indent:] if len(l) >= min_indent and l.strip() else l for l in lines]
                return PyNode("\n".join(lines).strip("\n"))

        return self.special_expr()

