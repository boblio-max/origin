# Origin Language Grammar (PEG)

This document is the **canonical, machine-friendly specification** of Origin v1.7 syntax. It is written so that a language model can generate syntactically correct Origin by construction: every rule is closed, every keyword/operator literal is listed, and every ambiguous corner is pinned down by a precedence table.

The grammar is expressed in [PEG](https://en.wikipedia.org/wiki/Parsing_expression_grammar) notation — chosen over EBNF because Origin's parser is a hand-written recursive-descent parser that matches longest prefix with ordered choice, which is exactly PEG semantics. The grammar here is derived from `ORIGIN_CODE/lexer.py` and `ORIGIN_CODE/parser.py` (the reference implementation) and is the source of truth for the surface form. Where the reference parser is loose, this grammar tightens the rule and flags it as **`(tightened)`**.

## Notation

- `A B C` — sequence
- `A | B | C` — ordered choice (PEG)
- `A?` — zero or one
- `A*` — zero or more (greedy)
- `A+` — one or more (greedy)
- `&A` — lookahead (positive)
- `!A` — negative lookahead
- `( A )` — grouping
- `"x"` — terminal literal (case-sensitive, lowercase keyword text is normalized in the lexer)
- Uppercase identifiers (`Program`, `Statement`, `Expr`) — non-terminals

Whitespace is significant only inside `py { ... }` blocks; otherwise spaces, tabs, and newlines separate tokens. Comments run from `#` to end of line.

## Lexical Tokens (terminals)

```
# Comments
Comment        <- "#" (!Newline .)*

# Literals
Int            <- "0x" [0-9a-fA-F]+ | [0-9]+
Float          <- [0-9]+ "." [0-9]+
String         <- '"' (!'"' .)* '"' | "'" (!"'" .)* "'"
FString        <- [fF] ('"' (!'"' .)* '"' | "'" (!"'" .)* "'")
Ident          <- [A-Za-z_] [A-Za-z0-9_]*

# Operators (single source of truth — order matters for longest match)
AssignOp       <- "+=" | "-=" | "*=" | "/=" | "%=" | "**=" | "//=" | "&=" | "|="
SpecialOp      <- "??" | "->" | "=>" | "<=>" | "::"
CompOp         <- "===" | "!==" | "==" | "!=" | "<=" | ">=" | "<>" | "<" | ">"
LogicOp        <- "&&" | "||" | "and" | "or" | "not" | "!"
UnaryOp        <- "++" | "--"
ArithOp        <- "+" | "-" | "**" | "*" | "//" | "/" | "%" | "&" | "|" | "^" | "<<" | ">>"
Bracket        <- "[" | "]" | "{" | "}"
Symbol         <- "(" | ")" | ":" | "," | "." | ";" | "?"
Newline        <- "\n"
Whitespace     <- [ \t]+
```

`//` is **floor division** and `//=` is its compound-assign form, mirroring Python's `//` / `//=`: for ints, `a // b` truncates toward zero; for floats, it floors `a / b` to the nearest whole number. Both are supported in the interpreter, the bytecode VM, and the Java VM mirror.

Keyword reserved words (cannot be used as identifiers except where the parser explicitly allows it via `KEYWORD`-typed ident capture — see "Keyword-as-Ident" below):

```
none  if  elif  else  for  to  while  write  with  return
py    int  read  len   str   sqrt   float  let  rand_num  const  in
print  true  exec  false  break  input  continue  def  func
import  from  class  try  call  except  set  pass  as
bool  parallel  range  self  address  accel  gyro  temp
```

## Top-Level Program

```
Program        <- _ TopItem* _ EOF
TopItem        <- Statement (Newline | EOF)

# Statements are newline-terminated inside blocks; at the top level they may
# also be separated by EOF. The parser inserts NEWLINE tokens after every line.
```

## Statements

```
Statement      <- ( Decorator )? Stmt
Decorator      <- "@" Ident            # reserved for future use

Stmt           <- ImportStmt
                | DefStmt
                | ClassStmt
                | IfStmt
                | WhileStmt
                | ForStmt
                | TryStmt
                | ParallelStmt
                | ReturnStmt
                | BreakStmt
                | ContinueStmt
                | PassStmt
                | ExecStmt
                | PyBlock
                | LetStmt
                | ConstStmt
                | SetStmt
                | PrintStmt
                | ExprStmt

LetStmt        <- "let" Ident TypeAnn? "=" Expr
ConstStmt      <- "const" Ident TypeAnn? "=" Expr
TypeAnn        <- ":" TypeName
TypeName       <- "int" | "float" | "str" | "bool" | "list" | "any" | Ident

PrintStmt      <- "print" PrintArgs (Newline | EOF)
PrintArgs      <- Expr ("," Expr)* ("for" ForTarget "in" Expr)?   # (tightened) trailing 'for' must be last

# Bare expression statement (function call, attribute mutation, etc.)
ExprStmt       <- Expr (Newline | EOF)
```

### Control flow

```
IfStmt         <- "if" CondExpr Block ("elif" CondExpr Block)* ("else" Block)?
WhileStmt      <- "while" CondExpr Block
CondExpr       <- Expr (":" CastableType)?            # optional cast annotation on the condition
ForStmt        <- "for" ForTarget "in" Expr Block
ForTarget      <- Ident (":" TypeName)?               # optional type annotation on the loop variable
                | Ident ("," Ident)*                          # bare unpacking
                | "(" Ident ("," Ident)* ")"
                | "[" Ident ("," Ident)* "]"
TryStmt        <- "try" Block ("except" Block)* ("else" Block)?
ParallelStmt   <- "parallel" ("(" Int ")")? Block
ReturnStmt     <- "return" Expr?
BreakStmt      <- "break"
ContinueStmt   <- "continue"
PassStmt       <- "pass"
```

### Definitions

```
DefStmt        <- ("def" | "func") Ident "(" Params? ")" Block
Params         <- Param ("," Param)*
Param          <- Ident (":" TypeName)?

ClassStmt      <- "class" Ident "(" Params? ")" Block
```

### Imports

```
ImportStmt     <- "import" ModuleName ("as" Ident)?
                | "from" ModuleName "import" Ident ("," Ident)*
ModuleName     <- Ident ("." Ident)*
```

### Special forms

```
PyBlock        <- "py" "{"  # raw python source until matching '}' at depth 0
                   # Implementation note: the reference parser treats the
                   # contents as an opaque token stream; here we express it
                   # informally. See lexer.py BRACKET depth tracking.
                   RawPython "}"

ExecStmt       <- "exec" String
SetStmt        <- "set" Ident ( "." Ident )? Expr ("," Expr)?
```

## Expressions

Precedence, lowest to highest. PEG ordered choice gives left-associativity naturally at each level where recursion is on the left:

| Level | Name            | Operators                                              | Associativity |
|-------|-----------------|--------------------------------------------------------|---------------|
| 1     | Pipeline        | `->`                                                   | left          |
| 2     | Special         | `??`, `=>`, `<=>`, `::`                                | left          |
| 3     | Logical         | `or`, `\|\|`, `and`, `&&`, `!`, `not`                  | left          |
| 4     | Comparison      | `===`, `!==`, `==`, `!=`, `<=`, `>=`, `<>`, `<`, `>`   | non-chainable |
| 5     | Additive        | `+`, `-`                                               | left          |
| 6     | Multiplicative  | `*`, `/`, `//`, `%`, `**`                              | left          |
| 7     | Unary           | `-`, `!`, `not`, `++`, `--`                            | right         |
| 8     | Postfix         | call, index, attribute, cast annotation                | left          |
| 9     | Primary         | literals, idents, lambdas, parens, list/dict literals  | —             |

```
Expr           <- PipeExpr

PipeExpr       <- SpecialExpr ("->" SpecialExpr)*
SpecialExpr    <- LogicExpr ( SpecialOp LogicExpr )*
LogicExpr      <- CompExpr  ( LogicOp  CompExpr  )*
CompExpr       <- AddExpr   ( CompOp   AddExpr   )?            # (tightened) NO chained comparisons
AddExpr        <- MulExpr   ( ArithOp  MulExpr   )*
MulExpr        <- UnaryExpr ( ArithOp  UnaryExpr )*
UnaryExpr      <- (UnaryOp | "-") UnaryExpr
                | PostfixExpr
PostfixExpr    <- PrimaryExpr Postfix*
Postfix        <- "(" Args? ")"                                # call
                | "[" Expr "]"                                # index
                | "." Ident                                   # attribute
                | ":" TypeName                                # cast annotation (only valid immediately after a method-call argument)

PrimaryExpr    <- Literal
                | IdentOrKeyword
                | "(" Expr ("," Expr)* ")"                    # tuple if comma present, else parens
                | "[" (Expr ("," Expr)*)? "]"                # list literal
                | "{" (Expr ":" Expr ("," Expr ":" Expr)*)? "}"  # dict literal
                | LambdaExpr
                | SpecialCall

Literal        <- FString | String | Float | Int
```

### Special-call primary (keyword-as-function forms)

These are factors in the parser — they are only valid in expression position. A model that emits them outside an expression will fail to parse.

```
Args           <- CastArg ("," CastArg)*
CastArg        <- Expr (":" CastableType)?           # optional cast annotation on an argument
CastableType   <- "int" | "float" | "str" | "bool"

SpecialCall    <- ("input" Prompt?)                           # input [STRING]
                | ("sqrt" | "len") "(" CastArg ")"
                | ("int" | "float" | "str" | "bool") "(" Expr ")"   # cast
                | "range" "(" CastArg "," CastArg ("," CastArg)? ")"
                | "rand_num" "(" CastArg "," CastArg ")"
                | "write" String Expr
                | "append" String Expr
                | "read" String ("to" Int)?
                | "call" "[" Expr "," Expr "]"
                | "self" Postfix*                              # only inside class methods
                | HardwarePrimitive

Prompt         <- String
```

### Hardware primitives

The reference parser only accepts these as bare identifier-prefixed calls with a non-parenthesized argument list. They are modeled as a special primary:

```
HardwarePrimitive <- ("i2c" | "spi" | "uart") "." Ident ArgList
ArgList           <- "(" Args? ")" | Expr ("," Expr)*        # (tightened) prefer parenthesized form
```

### Lambdas

A single-parameter lambda only. Multi-arg lambdas must be spelled `def` / `func`.

```
LambdaExpr     <- Ident "=>" Expr                            # restricted to single ident param
```

### Keyword-as-Ident

The reference parser allows certain keywords (`self`, `int`, `float`, `str`, `bool`, `range`, `write`, `append`, `read`, `input`, `sqrt`, `rand_num`, `true`, `false`, `len`, `call`) to be treated as identifiers in *expression position*. **Do not rely on this for new code.** A model generating Origin should use `Ident` for variable names; the parser's lenient behavior is documented here only because test corpus files use it.

```
IdentOrKeyword <- Ident
```

## Reserved / Future Keywords

These appear in the lexer's keyword list but are not yet implemented in the reference parser (parser falls through, no AST node). Models **must not** generate them as standalone statements; they are documented for forward compatibility:

```
match  case  enum  type  interface  pub  priv
async  await  yield  macro  inline  parallel (statement form works; "parallel" as expression does not)
when  unless  loop  until  do  capture  check  get  open  raise  global  nonlocal  assert  del  as (used by import)
```

## Common Pitfalls (read before generating)

These are the bugs that consistently break model output. Pin them in your prompt:

1. **`print` is a statement, not a function.** `print(x)` is a parse error. Use `print x`.
2. **No chained comparisons.** `1 < x < 10` must be rewritten as `(1 < x) and (x < 10)`.
3. **`let` and `const` require `=`** when a type annotation is present; without an annotation the parser infers the type. `let x: int` without `= value` is a parse error.
4. **`for` unpacking targets** use one of: `for a, b in iter`, `for (a, b) in iter`, `for [a, b] in iter`. Mixing forms fails.
5. **Bare `except` only** — no `except ExceptionType:`. The reference parser accepts only `except { ... }`.
6. **String concatenation is `+`, not interpolation.** To embed a value, use `str(x)` or an f-string.
7. **f-string inner expressions are re-parsed by the lexer/parser.** They may not contain raw newlines; use `\n` inside.
8. **`py { ... }` is opaque to Origin's parser.** Anything inside is Python and is not validated by this grammar.
9. **`return` at top level is a parse error.** `return` is only valid inside a `def`/`func` body.
10. **Method calls on hardware primitives** (`i2c.read addr, reg`) use *no parentheses* around the argument list. This is unique to the `i2c`/`spi`/`uart` namespaces; regular method calls require `(...)`.
11. **Typed parameters are optional but encouraged.** `def add(a:int, b:int)`, `class Point(x:int, y:int)`, `for i:int in ...`, and argument casts `range(0:int, 10:int)` are all supported. Annotations without a castable builtin type (`int`, `float`, `str`, `bool`) are declarations only and are advisory in the VM.

## Worked Examples (canonical, model-tested)

### Hello, calculator

```
print "WELCOME TO THE CALCULATOR"
let x: float = float(input "Enter a number: ")
let y: float = float(input "Enter another number: ")
let op: str   = input "Enter the operation (+, -, *, /): "

print "Your result is..."
if op == "+" {
    print x + y
} elif op == "-" {
    print x - y
} elif op == "*" {
    print x * y
} elif op == "/" {
    print x / y
}
```

> Note: the README example contains a bug (`print x + b` references an undefined `b`). This grammar documents the correct form above.

### Class + self

```
class Drone(x, y) {
    def setPos(self, nx, ny) {
        self.x = nx
        self.y = ny
    }
    def show(self, label) {
        print label
        print self.x
        print self.y
    }
}

let d: any = Drone()
d.x = 100
d.y = 200
d.show("Initial position:")
```

### For / range / cast

```
let x: int = 10
x += 5
print "X is now: " + str(x)

for val in [10, 20, 30] {
    print "Loop Value: " + str(val)
}

for i in range(1, 4) {
    print "Count: " + str(i)
}
```

### Hardware

```
let addr: int = 0x48
let reg:  int = 0x01
try {
    let val: int = i2c.read addr, reg
    print val
} except {
    print "I2C Read Failed"
}
```

### py-block escape hatch

```
import adafruit_servokit as servokit
py {
    kit = ServoKit(channels=16)
}
let angle: float = 90
while true {
    set servo.angle 15, angle
}
```

## Validation Checklist for Model Output

Before emitting a snippet, a model should self-check:

- [ ] Every statement ends with a newline (or is the last line of the file).
- [ ] Every `let`/`const` either has a type annotation + `=` value, or omits the annotation (inferred).
- [ ] No `print(...)` — use `print ...`.
- [ ] No chained comparisons.
- [ ] Every `def`/`func`/`class`/`if`/`while`/`for`/`try`/`parallel`/`py` opens with `{` and the matching `}` closes on its own line.
- [ ] Every `(` has a matching `)`; every `[` has a matching `]`; every `"` has a matching `"`.
- [ ] No use of reserved-but-unimplemented keywords (`match`, `enum`, `async`, ...).
- [ ] `return` appears only inside a `def`/`func` body.
- [ ] `self` appears only inside a `def`/`func` body of a class.

## Companion AST Schema

Each `Stmt` and `Expr` production above maps 1-to-1 to an AST node class in `ORIGIN_CODE/classes.py`. The mapping is:

| Production               | AST node                  |
|--------------------------|---------------------------|
| `Program`                | `ProgramNode`             |
| `LetStmt`                | `AssignNode(name, value, type)` |
| `ConstStmt`              | `ConstAssignNode(...)`    |
| `PrintStmt`              | `PrintNode(expr)`         |
| `IfStmt`                 | `IfNode(cond, then, elifs, else)` |
| `WhileStmt`              | `WhileNode(cond, body)`   |
| `ForStmt`                | `ForNode(var, iter, body)`|
| `TryStmt`                | `TryNode(try, excepts, else)` |
| `ParallelStmt`           | `ParallelNode(body, n)`   |
| `DefStmt`                | `FuncNode(name, params, body, param_types)` |
| `ClassStmt`              | `ClassNode(name, fields, body, field_types)` |
| `ImportStmt` (plain)     | `ImportNode(name)`        |
| `ImportStmt` (`as`)      | `ImportAsNode(name, alias)` |
| `ImportStmt` (`from`)    | `ImportFromNode(name, lib)` |
| `ReturnStmt`             | `ReturnNode(value)`       |
| `BreakStmt`              | `BreakNode()`             |
| `ContinueStmt`           | `ContinueNode()`          |
| `PassStmt`               | `PassNode()`              |
| `ExecStmt`               | `ExecNode(code)`          |
| `PyBlock`                | `PyNode(code)`            |
| `SetStmt`                | `SetNode(name, num, type, params)` |
| Ident `=` Expr           | `AssignNode(name, value)` |
| Ident `.` Ident `=` Expr | `AttributeAssignNode(obj, attr, value)` |
| Expr `[` Expr `]` `=` Expr | `IndexAssignNode(coll, idx, value)` |
| Ident (right-hand)       | `VarNode(name)`           |
| Int / Hex / Float        | `NumberNode(value, type)` |
| String                   | `StringNode(value, "str")`|
| FString                  | `FormattedStringNode(parts)` |
| `true` / `false`         | `BoolNode(value)`         |
| Lambda                   | `LambdaNode(var, body)`   |
| Pipe `->`                | `PipeNode(value, func)`   |
| Special `??`, `=>`, `<=>`, `::` | `SpecialOpNode(left, op, right)` |
| Logical                  | `LogicOpNode(left, op, right)` |
| Comparison / arithmetic  | `BinOpNode(left, op, right)` |
| Unary `-`/`!`/`not`/`++`/`--` | `UnaryOpNode(op, node)` |
| Call                     | `CallNode(callee, args)`  |
| Index                    | `IndexNode(coll, idx)`    |
| Attribute                | `AttributeNode(obj, attr)`|
| Cast (postfix `:` or fn-call `int(...)`) | `CastNode(type, value)` |
| List literal             | `ListNode(elements)`     |
| Dict literal             | `DictNode(elements)`      |
| Tuple / paren group      | `TupleNode(elements)`     |
| `input`                  | `InputNode(prompt)`       |
| `sqrt`                   | `SqrtNode(value)`         |
| `len`                    | `LenNode(value)`          |
| `range`                  | `RangeNode(start, end, step)` |
| `rand_num`               | `RandNumNode(start, end)` |
| `write`                  | `WriteNode(file, content)`|
| `append`                 | `AppendNode(file, content)` |
| `read`                   | `ReadNode(file, count)`   |
| `call` `[` Expr `,` Expr `]` | `ListCallNode(list, pos)` |
| `i2c`/`spi`/`uart` `.` Ident | `HardwarePrimitiveNode(ns, method, args)` |

## Few-shot Prompt Template (paste after the system prompt)

```
You generate Origin v1.7 code. Origin's grammar is fully specified here:
[paste this file's "Grammar" section]

Rules you must follow:
- `print` is a statement: `print x`, never `print(x)`.
- No chained comparisons: rewrite `a < b < c` as `(a < b) and (b < c)`.
- `let x: int = 10` — type annotation requires `= value`.
- Method calls use parentheses: `obj.method(arg)`. Hardware primitives don't:
  `i2c.read addr, reg`.
- No `match`, `enum`, `async`, `await`, `yield` — these are reserved and unimplemented.
- Every block `{ ... }` closes with `}` on its own line.
- Type your parameters and variables: `def add(a:int, b:int)`, `class P(x:int, y:int)`,
  `for i:int in ...`, `range(0, 10, 2)`.

Example — input: "sum a list of numbers"
Example — output:
let xs: list = [1, 2, 3, 4, 5]
let total: int = 0
def sum(a:list) {
    for v:int in a {
        total += v
    }
    return total
}
print sum(xs)
```

## Changelog / Tightening Notes

Items marked **`(tightened)`** above are places where the reference parser is more permissive than the documented grammar. The model-facing grammar is the strict one; the parser is being migrated to match.

- `PrintStmt`: trailing `for` only valid as the last argument group.
- `CompExpr`: single comparison only; no chaining.
- `HardwarePrimitive`: prefer parenthesized `ArgList`; the parser's bare form is deprecated.