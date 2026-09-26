// Origin bytecode VM — Rust port of the Python `sVM` class.
//
// Notes on what changed vs. the Python original:
//   - Python's dynamic typing is modeled with the `Value` enum below.
//   - `EXEC_PY` (arbitrary embedded Python via `exec`) has no Rust
//     equivalent and is left as an explicit runtime error. If your
//     compiler still emits this opcode, that code path needs a real
//     redesign, not a shim.
//   - Hardware calls (GPIO / I2C / SPI / servo) always fall back to the
//     `[SIM]` print path, matching what the Python does when the
//     hardware libraries (RPi.GPIO, smbus2, adafruit_servokit) aren't
//     installed. Wire up real hardware crates behind the same match
//     arms if you need actual GPIO access.
//   - "Python built-in function" calls (anything on the stack that
//     isn't a bytecode address, bound method, or class) are resolved
//     through a small fixed registry in `call_native` instead of
//     Python's fully dynamic callables. Extend that match as needed.
//   - No external crates. RNG is a small xorshift64 seeded from the
//     system clock, since `rand` isn't fetchable without a full cargo
//     registry in this environment — swap in the `rand` crate if you
//     have one available.
//
// This was hand-translated and not compiled in this environment (no
// rustc/cargo toolchain available here) — build it before trusting it.

use std::collections::HashMap; // variable scopes, class methods, instance attrs
use std::fmt; // Display impl for Value (origin print formatting)
use std::fs; // READ_FILE / WRITE_FILE / APPEND_FILE opcodes
use std::sync::{Arc, Mutex}; // shared Program + thread-safe List/Dict refs
use std::thread; // PARALLEL_START worker threads
use std::time::{SystemTime, UNIX_EPOCH}; // RNG seed clock
use std::net::TcpListener; // legacy svm() TCP server
use std::io::Read; // read_to_string on TCP stream
use pyo3::prelude::*; // run_bytecode / svm Python bridge

// ---------------------------------------------------------------------------
// OpCode — discriminants MUST match bc/byteKey.py (0x01..0x51)
// Bytecode wire format: [opcode:u8][operands...]. Operands are either a
// single constants-pool index (u8), a jump target (u16 big-endian), or an
// arg count (u8). Keep this enum + from_byte() in lockstep with byteKey.py.
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum OpCode {
    // --- stack / variables: PushConst <const_idx:u8>, Load/StoreVar <name_idx:u8> ---
    PushConst = 0x01,
    LoadVar = 0x02,
    StoreVar = 0x03,
    // --- arithmetic: pop b, pop a, push a op b (Add also str-concats) ---
    Add = 0x04,
    Sub = 0x05,
    Mul = 0x06,
    Div = 0x07,
    Mod = 0x08,
    Pow = 0x09,
    Negate = 0x0A, // unary minus: pop v, push -v
    // --- comparison (push Bool) + short-circuit logic (push operand, not Bool) ---
    Eq = 0x0B,
    Neq = 0x0C,
    Lt = 0x0D,
    Gt = 0x0E,
    Lte = 0x0F,
    Gte = 0x10,
    And = 0x11,
    Or = 0x12,
    Not = 0x13, // pop v, push !truthy(v)
    // --- control flow: Jmp/JmpIfFalse <target:u16 BE>; Loop*/Break/Continue are markers ---
    Jmp = 0x14,
    JmpIfFalse = 0x15,
    // --- builtins: Print pops+prints, Input pops prompt+pushes line, Len/Sqrt/RandNum ---
    Print = 0x16,
    Input = 0x17,
    Len = 0x18,
    Sqrt = 0x19,
    RandNum = 0x1A, // pops start,end; pushes randint inclusive
    // --- collections: List/DictInit <count:u8>, IndexLoad/Store ---
    ListInit = 0x1B,
    DictInit = 0x1C,
    IndexLoad = 0x1D,
    IndexStore = 0x1E,
    // --- stack + calls: Pop/Dup, Call <nargs:u8>, Return; Halt stops run() ---
    Halt = 0x1F,
    Pop = 0x20,
    Dup = 0x21,
    Call = 0x22,
    Return = 0x23,
    LoopStart = 0x24,
    LoopEnd = 0x25,
    Break = 0x26,
    Continue = 0x27,
    // --- casts: pop v, push converted ---
    CastStr = 0x28,
    CastInt = 0x29,
    CastFloat = 0x2A,
    // --- iteration: GetIter wraps iterable in List; ForIter <end:u16 BE> ---
    GetIter = 0x2B,
    ForIter = 0x2C,
    // --- objects: MakeClass pops name/fields/methods; Load/StoreAttr pop attr name ---
    MakeClass = 0x2D,
    LoadAttr = 0x2E,
    StoreAttr = 0x2F,
    // --- closures/upvalues: NOT implemented in Rust VM (panic) ---
    MakeClosure = 0x30,
    LoadUpvalue = 0x31,
    StoreUpvalue = 0x32,
    // --- exceptions/imports: SetupExcept <handler:u16 BE>; imports panic (compile-time) ---
    SetupExcept = 0x33,
    PopExcept = 0x34,
    Throw = 0x35,
    ImportName = 0x36,
    ImportFrom = 0x37,
    // --- bitwise: pop b,a; BitNot is unary ---
    BitAnd = 0x38,
    BitOr = 0x39,
    BitXor = 0x3A,
    BitNot = 0x3B,
    LShift = 0x3C,
    RShift = 0x3D,
    // --- strings: UnpackSeq <count:u8, wire-compat>, FormatVal, BuildStr <count:u8> ---
    UnpackSeq = 0x3E,
    FormatVal = 0x3F,
    BuildStr = 0x40,
    // --- files: ReadFile <count:u8, 0xFF=all>; Write/Append pop content+path ---
    ReadFile = 0x41,
    WriteFile = 0x42,
    AppendFile = 0x43,
    // --- hardware (always [SIM] print fallback): HardwareCall <nargs:u8> ---
    HardwareCall = 0x44,
    SetServo = 0x45, // pops channel, angle
    SetPin = 0x46, // pops pin, state
    // --- parallelism: ParallelStart <nthreads:u8><body:u16 BE>; ParallelEnd is marker ---
    ParallelStart = 0x47,
    ParallelEnd = 0x48,
    // --- misc: ExecPy always panics (no Rust exec); Move/Copy <dst:u8><src:u8>; Swap ---
    ExecPy = 0x49,
    Move = 0x4A,
    Copy = 0x4B,
    Swap = 0x4C,
    // --- extra math: FloorDiv/Mod use Euclid semantics; Abs/Floor/Ceil/Cube ---
    FloorDiv = 0x4D,
    Abs = 0x4E,
    Floor = 0x4F,
    Ceil = 0x50,
    Cube = 0x51,
}

impl OpCode {
    /// Decode a raw byte into an OpCode, matching bc/byteKey.py exactly.
    pub fn from_byte(b: u8) -> OpCode {
        use OpCode::*;
        match b {
            0x01 => PushConst,
            0x02 => LoadVar,
            0x03 => StoreVar,
            0x04 => Add,
            0x05 => Sub,
            0x06 => Mul,
            0x07 => Div,
            0x08 => Mod,
            0x09 => Pow,
            0x0A => Negate,
            0x0B => Eq,
            0x0C => Neq,
            0x0D => Lt,
            0x0E => Gt,
            0x0F => Lte,
            0x10 => Gte,
            0x11 => And,
            0x12 => Or,
            0x13 => Not,
            0x14 => Jmp,
            0x15 => JmpIfFalse,
            0x16 => Print,
            0x17 => Input,
            0x18 => Len,
            0x19 => Sqrt,
            0x1A => RandNum,
            0x1B => ListInit,
            0x1C => DictInit,
            0x1D => IndexLoad,
            0x1E => IndexStore,
            0x1F => Halt,
            0x20 => Pop,
            0x21 => Dup,
            0x22 => Call,
            0x23 => Return,
            0x24 => LoopStart,
            0x25 => LoopEnd,
            0x26 => Break,
            0x27 => Continue,
            0x28 => CastStr,
            0x29 => CastInt,
            0x2A => CastFloat,
            0x2B => GetIter,
            0x2C => ForIter,
            0x2D => MakeClass,
            0x2E => LoadAttr,
            0x2F => StoreAttr,
            0x30 => MakeClosure,
            0x31 => LoadUpvalue,
            0x32 => StoreUpvalue,
            0x33 => SetupExcept,
            0x34 => PopExcept,
            0x35 => Throw,
            0x36 => ImportName,
            0x37 => ImportFrom,
            0x38 => BitAnd,
            0x39 => BitOr,
            0x3A => BitXor,
            0x3B => BitNot,
            0x3C => LShift,
            0x3D => RShift,
            0x3E => UnpackSeq,
            0x3F => FormatVal,
            0x40 => BuildStr,
            0x41 => ReadFile,
            0x42 => WriteFile,
            0x43 => AppendFile,
            0x44 => HardwareCall,
            0x45 => SetServo,
            0x46 => SetPin,
            0x47 => ParallelStart,
            0x48 => ParallelEnd,
            0x49 => ExecPy,
            0x4A => Move,
            0x4B => Copy,
            0x4C => Swap,
            0x4D => FloorDiv,
            0x4E => Abs,
            0x4F => Floor,
            0x50 => Ceil,
            0x51 => Cube,
            _ => panic!("unknown opcode byte {:#04X}; check bc/byteKey.py", b),
        }
    }
}

// ---------------------------------------------------------------------------
// Value — runtime tagged union modeling Python's dynamic typing.
// Int/Float/Str/Bool/Nil are primitives; List/Dict are shared mutable refs
// (Arc<Mutex<..>>) so IndexStore mutates in place and ParallelStart workers
// can merge back; Class/Instance/BoundMethod mirror bc/helpers.py.
// FuncAddr is a bytecode offset, Native is a call_native registry key.
// ---------------------------------------------------------------------------

pub type ListRef = Arc<Mutex<Vec<Value>>>; // shared mutable list storage
pub type DictRef = Arc<Mutex<Vec<(Value, Value)>>>; // assoc list: dynamic keys, no Hash needed

#[derive(Clone)]
pub enum Value {
    Int(i64), // origin int
    Float(f64), // origin float; Div always produces this
    Str(String), // origin string
    Bool(bool), // origin bool; printed as true/false
    Nil, // origin nil / None / missing dict key
    List(ListRef), // origin list; mutated via IndexStore
    Dict(DictRef), // origin dict as assoc list
    Class(Arc<OriginClass>), // created by MakeClass, called to make Instance
    Instance(Arc<Mutex<OriginInstance>>), // class instance with attr map
    BoundMethod(Arc<Mutex<OriginInstance>>, u32), // (instance, method bytecode addr)
    /// Address of a function's first instruction in the bytecode stream.
    FuncAddr(u32),
    /// Name of a fixed native builtin (see `call_native`).
    Native(String),
}

// Display = how Print / str() / string interpolation render a Value.
impl fmt::Display for Value {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Value::Int(i) => write!(f, "{}", i),
            Value::Float(x) => write!(f, "{}", x),
            Value::Str(s) => write!(f, "{}", s),
            Value::Bool(b) => write!(f, "{}", if *b { "true" } else { "false" }),
            Value::Nil => write!(f, "nil"),
            Value::List(l) => {
                let items: Vec<String> = l.lock().unwrap().iter().map(|v| v.to_string()).collect();
                write!(f, "[{}]", items.join(", "))
            }
            Value::Dict(d) => {
                let items: Vec<String> = d
                    .lock().unwrap()
                    .iter()
                    .map(|(k, v)| format!("{}: {}", k, v))
                    .collect();
                write!(f, "{{{}}}", items.join(", "))
            }
            Value::Class(c) => write!(f, "<class {}>", c.name),
            Value::Instance(i) => write!(f, "<{} instance>", i.lock().unwrap().class.name),
            Value::BoundMethod(..) => write!(f, "<bound method>"),
            Value::FuncAddr(a) => write!(f, "<func @{}>", a),
            Value::Native(n) => write!(f, "<native {}>", n),
        }
    }
}

impl Value {
    /// Origin truthiness: false/0/0.0/""/nil/empty list-dict are falsy.
    /// Used by JmpIfFalse, Not, And/Or.
    pub fn truthy(&self) -> bool {
        match self {
            Value::Bool(b) => *b,
            Value::Int(i) => *i != 0,
            Value::Float(x) => *x != 0.0,
            Value::Str(s) => !s.is_empty(),
            Value::Nil => false,
            Value::List(l) => !l.lock().unwrap().is_empty(),
            Value::Dict(d) => !d.lock().unwrap().is_empty(),
            _ => true,
        }
    }

    /// Numeric coercion for arithmetic/compare: Int/Float/Bool pass
    /// through, Str parses (fallback 0.0), other types become 0.0.
    pub fn as_f64(&self) -> f64 {
        match self {
            Value::Int(i) => *i as f64,
            Value::Float(x) => *x,
            Value::Bool(b) => {
                if *b {
                    1.0
                } else {
                    0.0
                }
            }
            Value::Str(s) => s.parse().unwrap_or(0.0),
            _ => 0.0,
        }
    }

    /// Integer coercion for casts/indexing/bitops: truncates Float,
    /// Bool->0/1, Str parses (fallback 0), other types become 0.
    pub fn as_i64(&self) -> i64 {
        match self {
            Value::Int(i) => *i,
            Value::Float(x) => *x as i64,
            Value::Bool(b) => *b as i64,
            Value::Str(s) => s.parse().unwrap_or(0),
            _ => 0,
        }
    }

    /// Equality for Eq/Neq + Dict key lookup: Int~Float compare by
    /// value, Str/Bool/Nil by value; List/Dict/Class/etc never equal.
    fn values_equal(a: &Value, b: &Value) -> bool {
        match (a, b) {
            (Value::Int(x), Value::Int(y)) => x == y,
            (Value::Float(x), Value::Float(y)) => x == y,
            (Value::Int(x), Value::Float(y)) | (Value::Float(y), Value::Int(x)) => *x as f64 == *y,
            (Value::Str(x), Value::Str(y)) => x == y,
            (Value::Bool(x), Value::Bool(y)) => x == y,
            (Value::Nil, Value::Nil) => true,
            _ => false,
        }
    }
}

// ---------------------------------------------------------------------------
// Classes / instances / bound methods (mirrors bc.helpers)
// OriginClass is immutable + shared via Arc; OriginInstance holds the
// per-object attr map behind Mutex so LoadAttr/StoreAttr can mutate it.
// ---------------------------------------------------------------------------

pub struct OriginClass {
    pub name: String, // class name for Display + error messages
    pub fields: Vec<String>, // positional constructor field order
    /// method name -> bytecode address
    pub methods: HashMap<String, u32>,
}

pub struct OriginInstance {
    pub class: Arc<OriginClass>, // back-pointer for method lookup + Display
    pub attrs: HashMap<String, Value>, // fields + assigned attributes
}

// ---------------------------------------------------------------------------
// VM — stack machine over Program { bytecode, constants }.
// variables = current frame locals; call_stack saves (return pc, caller vars)
// so Return can restore; try_catch_stack holds handler pcs for Throw.
// rng_state is xorshift64 (no rand crate). pc is byte offset into bytecode.
// ---------------------------------------------------------------------------

/// Bytecode + constants are read-only once loaded, so they're shared
/// across worker threads (spawned for PARALLEL_START) via `Arc`.
pub struct Program {
    pub bytecode: Vec<u8>, // raw opcode + operand bytes
    pub constants: Vec<Value>, // pool indexed by PushConst/LoadVar/...
}

pub struct Vm {
    program: Arc<Program>, // shared code (cloned Arc for threads)
    stack: Vec<Value>, // operand stack
    variables: HashMap<String, Value>, // current frame locals
    pc: usize, // program counter (byte offset)
    call_stack: Vec<(usize, HashMap<String, Value>)>, // return addr + saved locals
    try_catch_stack: Vec<usize>, // SetupExcept handler pcs
    rng_state: u64, // xorshift64 state, seeded from clock
}

/// Distinguishes how a VM's inner run loop stopped, so callers (RETURN,
/// PARALLEL_END, top-level run) can react appropriately.
enum StopReason {
    Halted,
    Returned,
    ExhaustedBytecode,
}

impl Vm {
    /// Fresh VM over a shared Program; RNG seeded from system clock
    /// (fallback fixed constant), forced odd so xorshift progresses.
    pub fn new(program: Arc<Program>) -> Self {
        let seed = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_nanos() as u64)
            .unwrap_or(0x9E3779B97F4A7C15)
            | 1;
        Vm {
            program,
            stack: Vec::new(),
            variables: HashMap::new(),
            pc: 0,
            call_stack: Vec::new(),
            try_catch_stack: Vec::new(),
            rng_state: seed,
        }
    }

    /// Fetch one operand byte and advance pc.
    fn next_byte(&mut self) -> u8 {
        let b = self.program.bytecode[self.pc];
        self.pc += 1;
        b
    }

    /// Fetch big-endian u16 jump target / body address and advance pc by 2.
    fn next_u16(&mut self) -> u16 {
        let hi = self.next_byte() as u16;
        let lo = self.next_byte() as u16;
        (hi << 8) | lo
    }

    /// Clone constant-pool entry (keeps Program immutable/shared).
    fn const_at(&self, idx: usize) -> Value {
        self.program.constants[idx].clone()
    }

    /// Pop operand stack (panics on underflow = malformed bytecode).
    fn pop(&mut self) -> Value {
        self.stack.pop().expect("stack underflow")
    }

    /// Push onto operand stack.
    fn push(&mut self, v: Value) {
        self.stack.push(v);
    }

    /// xorshift64* step: no rand crate, wraps on overflow by default.
    fn xorshift(&mut self) -> u64 {
        let mut x = self.rng_state;
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        self.rng_state = x;
        x
    }

    /// `randint(start, end)` inclusive, matching Python's `random.randint`.
    fn rand_range(&mut self, start: i64, end: i64) -> i64 {
        if end <= start {
            return start;
        }
        let span = (end - start + 1) as u64;
        start + (self.xorshift() % span) as i64
    }

    /// Generic int-preserving binop: Int+Int stays Int, else Float.
    /// Caller already popped (a,b); pushes result.
    fn binop_numeric<F, G>(&mut self, f_int: F, f_float: G)
    where
        F: Fn(i64, i64) -> i64,
        G: Fn(f64, f64) -> f64,
    {
        let b = self.pop();
        let a = self.pop();
        match (&a, &b) {
            (Value::Int(x), Value::Int(y)) => self.push(Value::Int(f_int(*x, *y))),
            _ => self.push(Value::Float(f_float(a.as_f64(), b.as_f64()))),
        }
    }

    /// Float comparison helper: pops (a,b), pushes Bool(f(a,b)).
    fn compare<F>(&mut self, f: F)
    where
        F: Fn(f64, f64) -> bool,
    {
        let b = self.pop();
        let a = self.pop();
        self.push(Value::Bool(f(a.as_f64(), b.as_f64())));
    }

    /// Top-level entry point: run until HALT or the call stack empties
    /// out on a top-level RETURN.
    pub fn run(&mut self) {
        loop {
            match self.step_loop() {
                StopReason::Halted | StopReason::ExhaustedBytecode => break,
                StopReason::Returned => break,
            }
        }
    }

    /// Worker entry for PARALLEL_START threads: run until PARALLEL_END,
    /// RETURN, or HALT — mirrors `_run_until_parallel_end` in the
    /// Python version.
    fn run_until_parallel_end(&mut self) {
        while self.pc < self.program.bytecode.len() {
            let opcode = OpCode::from_byte(self.program.bytecode[self.pc]);
            if opcode == OpCode::ParallelEnd || opcode == OpCode::Halt || opcode == OpCode::Return
            {
                break;
            }
            self.pc += 1;
            self.exec_one(opcode);
        }
    }

    /// Main dispatch loop. Returns why it stopped.
    /// Fetch-execute: next_byte decodes OpCode, Return/Halt/ExecPy handled
    /// inline here, all other opcodes delegate to exec_one().
    fn step_loop(&mut self) -> StopReason {
        while self.pc < self.program.bytecode.len() {
            let opcode = OpCode::from_byte(self.next_byte());

            match opcode {
                OpCode::Return => {
                    // Function return: restore caller pc+locals, merging back
                    // callee-mutated vars that already existed in caller
                    // (matches Python sVM scoping). Empty call_stack = top-level.
                    if let Some((ret_pc, mut saved_vars)) = self.call_stack.pop() {
                        self.pc = ret_pc;
                        for (k, v) in self.variables.drain() {
                            if saved_vars.contains_key(&k) {
                                saved_vars.insert(k, v);
                            }
                        }
                        self.variables = saved_vars;
                    } else {
                        return StopReason::Returned;
                    }
                }
                OpCode::Halt => return StopReason::Halted,
                OpCode::ExecPy => {
                    // No Rust equivalent for arbitrary embedded Python.
                    // Pop the source string (matching stack effect) and fail loudly.
                    let _code = self.pop();
                    panic!(
                        "EXEC_PY opcode reached: embedded Python blocks are not supported \
                         by the Rust VM. Recompile without py{{...}} blocks, or replace this \
                         opcode with a native Rust routine."
                    );
                }
                other => self.exec_one(other),
            }
        }
        StopReason::ExhaustedBytecode
    }

    /// Execute a single already-fetched opcode (operands, if any, are
    /// read from the bytecode stream as usual). Shared between the main
    /// loop and parallel worker threads. Does not handle RETURN, HALT,
    /// or EXEC_PY — callers special-case those.
    fn exec_one(&mut self, opcode: OpCode) {
        use OpCode::*;
        match opcode {
            // PushConst <idx:u8>: clone constants[idx] onto stack.
            PushConst => {
                let idx = self.next_byte() as usize;
                let c = self.const_at(idx);
                self.push(c);
            }
            // LoadVar <name_idx:u8>: resolve name via constants pool, push locals[name].
            LoadVar => {
                let idx = self.next_byte() as usize;
                let name = match self.const_at(idx) {
                    Value::Str(s) => s,
                    other => other.to_string(),
                };
                let v = self
                    .variables
                    .get(&name)
                    .unwrap_or_else(|| panic!("Name '{}' is not defined", name))
                    .clone();
                self.push(v);
            }
            StoreVar => {
                // StoreVar <name_idx:u8>: pop v, locals[name] = v.
                let idx = self.next_byte() as usize;
                let name = match self.const_at(idx) {
                    Value::Str(s) => s,
                    other => other.to_string(),
                };
                let val = self.pop();
                self.variables.insert(name, val);
            }
            Add => {
                let b = self.pop();
                let a = self.pop();
                // Mirrors interpreter's smart-concat: str + anything -> string concat.
                if matches!(a, Value::Str(_)) || matches!(b, Value::Str(_)) {
                    self.push(Value::Str(format!("{}{}", a, b)));
                } else {
                    self.binop_push_numeric(a, b, |x, y| x + y, |x, y| x + y);
                }
            }
            Sub => self.binop_numeric(|x, y| x - y, |x, y| x - y), // pop b,a; push a-b
            Mul => self.binop_numeric(|x, y| x * y, |x, y| x * y), // pop b,a; push a*b
            Div => {
                // True divide: always Float, even for Int inputs (matches Python /).
                let b = self.pop();
                let a = self.pop();
                self.push(Value::Float(a.as_f64() / b.as_f64()));
            }
            FloorDiv => self.binop_numeric(|x, y| x.div_euclid(y), |x, y| (x / y).floor()), // Euclid floor
            Mod => self.binop_numeric(|x, y| x.rem_euclid(y), |x, y| x % y), // Euclid remainder
            Pow => {
                // Int**nonneg-Int stays Int (checked pow), else Float powf.
                let b = self.pop();
                let a = self.pop();
                match (&a, &b) {
                    (Value::Int(x), Value::Int(y)) if *y >= 0 => {
                        self.push(Value::Int(x.pow(*y as u32)))
                    }
                    _ => self.push(Value::Float(a.as_f64().powf(b.as_f64()))),
                }
            }
            Negate => {
                // Unary minus: Int stays Int, others coerce via as_f64.
                let v = self.pop();
                match v {
                    Value::Int(i) => self.push(Value::Int(-i)),
                    _ => self.push(Value::Float(-v.as_f64())),
                }
            }
            // Bitwise int ops (float arm unused -> 0.0); BitNot is unary ~.
            BitAnd => self.binop_numeric(|x, y| x & y, |_, _| 0.0),
            BitOr => self.binop_numeric(|x, y| x | y, |_, _| 0.0),
            BitXor => self.binop_numeric(|x, y| x ^ y, |_, _| 0.0),
            BitNot => {
                let v = self.pop();
                self.push(Value::Int(!v.as_i64()));
            }
            LShift => self.binop_numeric(|x, y| x << y, |_, _| 0.0),
            RShift => self.binop_numeric(|x, y| x >> y, |_, _| 0.0),
            // Eq/Neq use values_equal (Int~Float cross-compare); Lt/Gt/Lte/Gte coerce to f64.
            Eq => {
                let b = self.pop();
                let a = self.pop();
                self.push(Value::Bool(Value::values_equal(&a, &b)));
            }
            Neq => {
                let b = self.pop();
                let a = self.pop();
                self.push(Value::Bool(!Value::values_equal(&a, &b)));
            }
            Lt => self.compare(|x, y| x < y),
            Gt => self.compare(|x, y| x > y),
            Lte => self.compare(|x, y| x <= y),
            Gte => self.compare(|x, y| x >= y),
            // Jmp <target:u16>: unconditional; JmpIfFalse pops cond, jumps if falsy.
            Jmp => {
                let target = self.next_u16() as usize;
                self.pc = target;
            }
            JmpIfFalse => {
                let target = self.next_u16() as usize;
                let val = self.pop();
                if !val.truthy() {
                    self.pc = target;
                }
            }
            Print => {
                let val = self.pop();
                // Mirrors the Python multi-arg print unpack for list/tuple values.
                if let Value::List(l) = &val {
                    let items: Vec<String> = l.lock().unwrap().iter().map(|v| v.to_string()).collect();
                    println!("{}", items.join(" "));
                } else {
                    println!("{}", val);
                }
            }
            Input => {
                // Input: pop prompt, print it flush, push stdin line (no trailing \n).
                let prompt = self.pop();
                print!("{}", prompt);
                use std::io::{self, Write};
                io::stdout().flush().ok();
                let mut line = String::new();
                io::stdin().read_line(&mut line).ok();
                self.push(Value::Str(line.trim_end_matches('\n').to_string()));
            }
            Sqrt => {
                // Sqrt: pop v, push sqrt(as_f64).
                let v = self.pop();
                self.push(Value::Float(v.as_f64().sqrt()));
            }
            Abs => {
                // Abs: Int stays Int, else Float abs.
                let v = self.pop();
                match v {
                    Value::Int(i) => self.push(Value::Int(i.abs())),
                    _ => self.push(Value::Float(v.as_f64().abs())),
                }
            }
            Floor => {
                // Floor/Ceil: coerce to f64, round, push Int.
                let v = self.pop();
                self.push(Value::Int(v.as_f64().floor() as i64));
            }
            Ceil => {
                let v = self.pop();
                self.push(Value::Int(v.as_f64().ceil() as i64));
            }
            Pop => {
                // Pop: discard top (expression statement cleanup).
                self.pop();
            }
            Dup => {
                // Dup: duplicate top without popping (used by jumps/teardown).
                let v = self.stack.last().expect("stack underflow").clone();
                self.push(v);
            }
            RandNum => {
                // RandNum: pop end, pop start, push randint inclusive via xorshift.
                let end = self.pop().as_i64();
                let start = self.pop().as_i64();
                let n = self.rand_range(start, end);
                self.push(Value::Int(n));
            }
            ListInit => {
                // ListInit <n:u8>: pop n items in reverse, push shared List.
                let n = self.next_byte() as usize;
                let mut elements = vec![Value::Nil; n];
                for i in (0..n).rev() {
                    elements[i] = self.pop();
                }
                self.push(Value::List(Arc::new(Mutex::new(elements))));
            }
            DictInit => {
                // DictInit <n:u8>: pop n (k,v) pairs, push shared Dict (order preserved).
                let n = self.next_byte() as usize;
                let mut pairs = Vec::with_capacity(n);
                for _ in 0..n {
                    let v = self.pop();
                    let k = self.pop();
                    pairs.push((k, v));
                }
                pairs.reverse();
                self.push(Value::Dict(Arc::new(Mutex::new(pairs))));
            }
            IndexLoad => {
                // IndexLoad: pop idx, pop coll, push coll[idx] (negative wraps).
                let idx = self.pop();
                let coll = self.pop();
                self.push(index_load(&coll, &idx));
            }
            IndexStore => {
                // IndexStore: pop val, idx, coll; mutates List/Dict in place.
                let val = self.pop();
                let idx = self.pop();
                let coll = self.pop();
                index_store(&coll, &idx, val);
            }
            Len => {
                // Len: Str counts chars, List/Dict count items, else 0.
                let v = self.pop();
                let n = match &v {
                    Value::Str(s) => s.chars().count(),
                    Value::List(l) => l.lock().unwrap().len(),
                    Value::Dict(d) => d.lock().unwrap().len(),
                    _ => 0,
                };
                self.push(Value::Int(n as i64));
            }
            Not => {
                // Not: push !truthy(v). And/Or return operand (Python-style), not Bool.
                let v = self.pop();
                self.push(Value::Bool(!v.truthy()));
            }
            And => {
                let b = self.pop();
                let a = self.pop();
                self.push(if a.truthy() { b } else { a });
            }
            Or => {
                let b = self.pop();
                let a = self.pop();
                self.push(if a.truthy() { a } else { b });
            }
            CastStr => {
                // Casts: use Display / as_i64 / as_f64 coercions.
                let v = self.pop();
                self.push(Value::Str(v.to_string()));
            }
            CastInt => {
                let v = self.pop();
                self.push(Value::Int(v.as_i64()));
            }
            CastFloat => {
                let v = self.pop();
                self.push(Value::Float(v.as_f64()));
            }
            GetIter => {
                // Iteration state is just "remaining elements", stored as a
                // List we pop from the front; see ForIter below.
                let v = self.pop();
                let items = match v {
                    Value::List(l) => l.lock().unwrap().clone(),
                    Value::Str(s) => s.chars().map(|c| Value::Str(c.to_string())).collect(),
                    Value::Dict(d) => d.lock().unwrap().iter().map(|(k, _)| k.clone()).collect(),
                    other => vec![other],
                };
                self.push(Value::List(Arc::new(Mutex::new(items))));
            }
            ForIter => {
                // ForIter <end:u16>: peek iterator List; push next item or
                // drop iterator + jump to end when exhausted.
                let target = self.next_u16() as usize;
                let iter_val = self.stack.last().expect("stack underflow").clone();
                if let Value::List(l) = iter_val {
                    let next = l.lock().unwrap().pop_front_like();
                    match next {
                        Some(v) => self.push(v),
                        None => {
                            self.pop(); // drop exhausted iterator
                            self.pc = target;
                        }
                    }
                } else {
                    self.pop();
                    self.pc = target;
                }
            }
            MakeClass => {
                // MakeClass: pops name, fields List, methods Dict(addr map); pushes Class.
                let methods_val = self.pop();
                let fields_val = self.pop();
                let name_val = self.pop();
                let name = name_val.to_string();
                let fields = match fields_val {
                    Value::List(l) => l.lock().unwrap().iter().map(|v| v.to_string()).collect(),
                    _ => Vec::new(),
                };
                let mut methods = HashMap::new();
                if let Value::Dict(d) = methods_val {
                    for (k, v) in d.lock().unwrap().iter() {
                        methods.insert(k.to_string(), v.as_i64() as u32);
                    }
                }
                self.push(Value::Class(Arc::new(OriginClass {
                    name,
                    fields,
                    methods,
                })));
            }
            LoadAttr => {
                // LoadAttr: pops attr, obj; instance attr wins, else BoundMethod, else panic.
                let attr = self.pop().to_string();
                let obj = self.pop();
                match obj {
                    Value::Instance(inst) => {
                        let inst_ref = inst.lock().unwrap();
                        if let Some(v) = inst_ref.attrs.get(&attr) {
                            self.push(v.clone());
                        } else if let Some(&addr) = inst_ref.class.methods.get(&attr) {
                            drop(inst_ref);
                            self.push(Value::BoundMethod(inst.clone(), addr));
                        } else {
                            panic!(
                                "'{}' object has no attribute '{}'",
                                inst_ref.class.name, attr
                            );
                        }
                    }
                    other => panic!("cannot load attribute '{}' from {}", attr, other),
                }
            }
            StoreAttr => {
                // StoreAttr: pops attr, value, instance-obj; inserts into attr map.
                let attr = self.pop().to_string();
                let value = self.pop();
                let obj = self.pop();
                if let Value::Instance(inst) = obj {
                    inst.lock().unwrap().attrs.insert(attr, value);
                } else {
                    panic!("cannot set attribute '{}' on non-instance value", attr);
                }
            }
            Call => {
                // Call <nargs:u8>: pops callable; FuncAddr/BoundMethod push frame+jump,
                // Class pops args into Instance, Native dispatches via call_native.
                let num_args = self.next_byte() as usize;
                let func = self.pop();
                match func {
                    Value::FuncAddr(addr) => {
                        // Plain function: save return pc + locals, jump to addr.
                        self.call_stack.push((self.pc, self.variables.clone()));
                        self.pc = addr as usize;
                    }
                    Value::BoundMethod(instance, addr) => {
                        // Method call: inject self as first stack arg, then same as FuncAddr.
                        let insert_at = self.stack.len() - num_args;
                        self.stack.insert(insert_at, Value::Instance(instance));
                        self.call_stack.push((self.pc, self.variables.clone()));
                        self.pc = addr as usize;
                    }
                    Value::Class(class) => {
                        // Construction: pop args positionally into field attrs (missing -> Nil).
                        let mut args = vec![Value::Nil; num_args];
                        for i in (0..num_args).rev() {
                            args[i] = self.pop();
                        }
                        let mut attrs = HashMap::new();
                        for (i, field) in class.fields.iter().enumerate() {
                            attrs.insert(
                                field.clone(),
                                args.get(i).cloned().unwrap_or(Value::Nil),
                            );
                        }
                        self.push(Value::Instance(Arc::new(Mutex::new(OriginInstance {
                            class,
                            attrs,
                        }))));
                    }
                    Value::Native(name) => {
                        let mut args = vec![Value::Nil; num_args];
                        for i in (0..num_args).rev() {
                            args[i] = self.pop();
                        }
                        self.push(call_native(&name, &args));
                    }
                    other => panic!("value is not callable: {}", other),
                }
            }
            SetupExcept => {
                // SetupExcept <handler:u16>: push handler pc for Throw.
                let target = self.next_u16() as usize;
                self.try_catch_stack.push(target);
            }
            PopExcept => {
                // PopExcept: discard handler on normal exit from try block.
                self.try_catch_stack.pop();
            }
            Throw => {
                // Throw: pop value; jump to handler pushing it, or panic if uncaught.
                let exception_val = self.pop();
                if let Some(handler_pc) = self.try_catch_stack.pop() {
                    self.pc = handler_pc;
                    self.push(exception_val);
                } else {
                    panic!("Uncaught Exception: {}", exception_val);
                }
            }
            FormatVal => {
                // FormatVal: pop v, push Display string (f-string field).
                let val = self.pop();
                self.push(Value::Str(val.to_string()));
            }
            BuildStr => {
                // BuildStr <count:u8>: pop count parts in reverse, push concatenated.
                let count = self.next_byte() as usize;
                let mut parts = vec![String::new(); count];
                for i in (0..count).rev() {
                    parts[i] = self.pop().to_string();
                }
                self.push(Value::Str(parts.concat()));
            }
            UnpackSeq => {
                // UnpackSeq: pop List, push items (reverse-iter so first ends up on top).
                let _count = self.next_byte(); // operand present for wire compat; not needed here
                let seq = self.pop();
                if let Value::List(l) = seq {
                    for item in l.lock().unwrap().iter().rev() {
                        self.push(item.clone());
                    }
                }
            }
            ReadFile => {
                // ReadFile <count:u8>: pop path; 0xFF reads all, else first N chars.
                let path = self.pop().to_string();
                let count = self.next_byte();
                let contents = fs::read_to_string(&path).unwrap_or_default();
                if count == 0xFF {
                    self.push(Value::Str(contents));
                } else {
                    let n = count as usize;
                    self.push(Value::Str(contents.chars().take(n).collect()));
                }
            }
            WriteFile => {
                // WriteFile: pop content, pop path; truncating write (panics on error).
                let content = self.pop().to_string();
                let path = self.pop().to_string();
                fs::write(path, content).expect("write_file failed");
            }
            AppendFile => {
                // AppendFile: pop content, pop path; create+append (ignores write errors).
                use std::io::Write as _;
                let content = self.pop().to_string();
                let path = self.pop().to_string();
                let mut f = fs::OpenOptions::new()
                    .append(true)
                    .create(true)
                    .open(path)
                    .expect("append_file failed");
                f.write_all(content.as_bytes()).ok();
            }
            HardwareCall => {
                // HardwareCall <nargs:u8>: pops [ns, method] + args; [SIM] fallback only.
                let num_args = self.next_byte() as usize;
                let ns_method = self.pop();
                let (ns, method) = match ns_method {
                    Value::List(l) => {
                        let b = l.lock().unwrap();
                        (b[0].to_string(), b[1].to_string())
                    }
                    other => (other.to_string(), String::new()),
                };
                let mut args = vec![Value::Nil; num_args];
                for i in (0..num_args).rev() {
                    args[i] = self.pop();
                }
                // No hardware backend wired up in this port — always simulate,
                // matching Python's behavior when RPi.GPIO/smbus2 aren't installed.
                match (ns.as_str(), method.as_str()) {
                    ("i2c", "read") => self.push(Value::Int(0)),
                    ("spi", "read") => self.push(Value::Int(0)),
                    _ => {
                        let arg_strs: Vec<String> = args.iter().map(|a| a.to_string()).collect();
                        println!("[SIM] {}.{}({})", ns, method, arg_strs.join(", "));
                    }
                }
            }
            SetServo => {
                // SetServo: pops channel, angle; simulated print (no servo crate).
                let angle = self.pop();
                let channel = self.pop();
                println!("[SIM] Servo {} angle set to {}", channel, angle);
            }
            SetPin => {
                // SetPin: pops pin, state; simulated print (no GPIO crate).
                let state = self.pop();
                let pin = self.pop();
                println!("[SIM] Pin {} set to {}", pin, state.truthy());
            }
            ParallelStart => {
                // ParallelStart <nthreads:u8><body:u16>: clone vars, spawn N VMs at
                // body_start, run to ParallelEnd, join, merge vars last-writer-wins.
                let num_threads = self.next_byte() as usize;
                let body_start = self.next_u16() as usize;
                let program = self.program.clone();
                let base_vars = self.variables.clone();
                let results: Arc<Mutex<Vec<HashMap<String, Value>>>> =
                    Arc::new(Mutex::new(Vec::new()));
                let mut handles = Vec::with_capacity(num_threads);
                for _ in 0..num_threads {
                    // Value contains Rc, which isn't Send. Worker threads that
                    // only touch primitive locals work fine; if your program
                    // shares lists/dicts/instances across parallel{} bodies,
                    // switch ListRef/DictRef to Arc<Mutex<_>> instead of
                    // Rc<RefCell<_>> before relying on this.
                    let program = program.clone();
                    let vars = base_vars.clone();
                    let results = results.clone();
                    let handle = thread::spawn(move || {
                        let mut vm = Vm::new(program);
                        vm.variables = vars;
                        vm.pc = body_start;
                        vm.run_until_parallel_end();
                        results.lock().unwrap().push(vm.variables);
                    });
                    handles.push(handle);
                }
                for h in handles {
                    h.join().expect("worker thread panicked");
                }
                // Merge worker variable changes back, last-writer-wins,
                // matching the Python implementation.
                for vars in results.lock().unwrap().drain(..) {
                    self.variables.extend(vars);
                }
            }
            ParallelEnd => {
                // Handled inline by ParallelStart's join above; this opcode
                // is a no-op marker in this port since we don't leave threads
                // on the Rust stack the way Python stashes (threads, vms)
                // tuples as a Value. Pop nothing — nothing was pushed.
            }
            Move => {
                // Move <dst:u8><src:u8>: locals[dst] = locals.get(src, Nil) via const names.
                let dest_idx = self.next_byte() as usize;
                let src_idx = self.next_byte() as usize;
                let dest_name = self.const_at(dest_idx).to_string();
                let src_name = self.const_at(src_idx).to_string();
                let v = self.variables.get(&src_name).cloned().unwrap_or(Value::Nil);
                self.variables.insert(dest_name, v);
            }
            Copy => {
                // Copy <dst:u8><src:u8>: like Move but no-op when src missing.
                let dest_idx = self.next_byte() as usize;
                let src_idx = self.next_byte() as usize;
                let dest_name = self.const_at(dest_idx).to_string();
                let src_name = self.const_at(src_idx).to_string();
                if let Some(v) = self.variables.get(&src_name).cloned() {
                    self.variables.insert(dest_name, v);
                }
            }
            Swap => {
                // Swap: pops b,a; pushes b,a reversed.
                let b = self.pop();
                let a = self.pop();
                self.push(b);
                self.push(a);
            }
            Cube => {
                // Cube: Int cubes exactly, others via as_f64 Float.
                let v = self.pop();
                match v {
                    Value::Int(i) => self.push(Value::Int(i * i * i)),
                    _ => {
                        let x = v.as_f64();
                        self.push(Value::Float(x * x * x))
                    }
                }
            }
            LoopStart | LoopEnd | Break | Continue => {
                // Loop markers: no runtime effect; compiler pre-patches them to Jmps.
                // Compiler lowers break/continue to JMP patches; these are markers.
            }
            MakeClosure | LoadUpvalue | StoreUpvalue => {
                // Closures unsupported: fail loudly so missing compiler support is visible.
                panic!(
                    "{:?} reached: closures/upvalues are not supported by the Rust VM yet",
                    opcode
                );
            }
            ImportName | ImportFrom => {
                // Imports resolved at compile time: reaching here means stale bytecode.
                let name = self.pop().to_string();
                panic!(
                    "import '{}' reached: imports are resolved at compile time; Rust VM has no module loader",
                    name
                );
            }
            Return | Halt | ExecPy => unreachable!("handled by caller"),
        }
    }

    /// Non-popping binop variant for Add fast-path: takes owned (a,b),
    /// pushes Int result when both Int, else Float. Keeps Add readable.
    fn binop_push_numeric<F, G>(&mut self, a: Value, b: Value, f_int: F, f_float: G)
    where
        F: Fn(i64, i64) -> i64,
        G: Fn(f64, f64) -> f64,
    {
        match (&a, &b) {
            (Value::Int(x), Value::Int(y)) => self.push(Value::Int(f_int(*x, *y))),
            _ => self.push(Value::Float(f_float(a.as_f64(), b.as_f64()))),
        }
    }
}

// ---------------------------------------------------------------------------
// Collection helpers — shared by IndexLoad/IndexStore (no stack effects here).
// Lists/Strings support negative wrap via normalize_index; Dicts linear-scan
// with values_equal and return Nil for missing keys (mirrors Python sVM).
// ---------------------------------------------------------------------------

/// Index read: List/Str by position (negative wraps), Dict by key search.
fn index_load(coll: &Value, idx: &Value) -> Value {
    match coll {
        Value::List(l) => {
            let b = l.lock().unwrap();
            let i = normalize_index(idx.as_i64(), b.len());
            b[i].clone()
        }
        Value::Str(s) => {
            let chars: Vec<char> = s.chars().collect();
            let i = normalize_index(idx.as_i64(), chars.len());
            Value::Str(chars[i].to_string())
        }
        Value::Dict(d) => {
            let b = d.lock().unwrap();
            b.iter()
                .find(|(k, _)| Value::values_equal(k, idx))
                .map(|(_, v)| v.clone())
                .unwrap_or(Value::Nil)
        }
        other => panic!("value is not indexable: {}", other),
    }
}

/// Index write: mutates List slot or Dict entry in place (insert if missing).
fn index_store(coll: &Value, idx: &Value, val: Value) {
    match coll {
        Value::List(l) => {
            let mut b = l.lock().unwrap();
            let i = normalize_index(idx.as_i64(), b.len());
            b[i] = val;
        }
        Value::Dict(d) => {
            let mut b = d.lock().unwrap();
            if let Some(entry) = b.iter_mut().find(|(k, _)| Value::values_equal(k, idx)) {
                entry.1 = val;
            } else {
                b.push((idx.clone(), val));
            }
        }
        other => panic!("value does not support item assignment: {}", other),
    }
}

/// Convert negative index to usize offset (Python-style wrap); caller ensures in-range.
fn normalize_index(i: i64, len: usize) -> usize {
    if i < 0 {
        (len as i64 + i) as usize
    } else {
        i as usize
    }
}

/// Front-pop helper used by ForIter to consume the iterator list in
/// original order without an O(n) shift-per-step penalty. Kept as an
/// extension trait so `Vec<Value>` reads naturally at the call site.
trait PopFront {
    fn pop_front_like(&mut self) -> Option<Value>;
}

impl PopFront for Vec<Value> {
    fn pop_front_like(&mut self) -> Option<Value> {
        if self.is_empty() {
            None
        } else {
            Some(self.remove(0))
        }
    }
}

// ---------------------------------------------------------------------------
// Native builtin registry — replaces Python's "whatever callable was on
// the stack" with a fixed, explicit set. Extend as your compiler needs.
// Called from Call when the callable is Value::Native(name).
// Supported: str/int/float/len/abs/range (range is start..end exclusive).
// ---------------------------------------------------------------------------

/// Dispatch fixed native builtin by name (panics on unknown — add arm + recompile).
fn call_native(name: &str, args: &[Value]) -> Value {
    match name {
        "str" => Value::Str(args.get(0).map(|v| v.to_string()).unwrap_or_default()),
        "int" => Value::Int(args.get(0).map(|v| v.as_i64()).unwrap_or(0)),
        "float" => Value::Float(args.get(0).map(|v| v.as_f64()).unwrap_or(0.0)),
        "len" => {
            let n = match args.get(0) {
                Some(Value::Str(s)) => s.chars().count(),
                Some(Value::List(l)) => l.lock().unwrap().len(),
                Some(Value::Dict(d)) => d.lock().unwrap().len(),
                _ => 0,
            };
            Value::Int(n as i64)
        }
        "abs" => match args.get(0) {
            Some(Value::Int(i)) => Value::Int(i.abs()),
            Some(v) => Value::Float(v.as_f64().abs()),
            None => Value::Int(0),
        },
        "range" => {
            let (start, end) = match args.len() {
                1 => (0, args[0].as_i64()),
                _ => (args[0].as_i64(), args[1].as_i64()),
            };
            let items = (start..end).map(Value::Int).collect();
            Value::List(Arc::new(Mutex::new(items)))
        }
        other => panic!(
            "unknown native builtin '{}' — add it to call_native() in main.rs",
            other
        ),
    }
}

// ---------------------------------------------------------------------------
// Python bridge — JSON constants (matches Compiler.to_payload in to_byte.py)
// Hand-rolled parser (no serde): JsonVal models null/bool/number/string/
// array/object; JsonParser is a byte-cursor with ws/peek/parse_* helpers;
// json_to_value maps $native->{$Native} and $repr->Str, arrays->List,
// plain objects->Dict. parse_constants_json expects top-level array.
// ---------------------------------------------------------------------------

/// Minimal JSON value model (no external crates) for the constants payload.
/// Supported: null, bool, number, string, array, object with $native/$repr.
#[derive(Debug, Clone)]
enum JsonVal {
    Null,
    Bool(bool),
    Int(i64),
    Float(f64),
    Str(String),
    Arr(Vec<JsonVal>),
    Obj(Vec<(String, JsonVal)>),
}

struct JsonParser<'a> {
    b: &'a [u8], // input bytes
    i: usize, // cursor offset
}

impl<'a> JsonParser<'a> {
    /// Wrap input &str as byte cursor starting at 0.
    fn new(s: &'a str) -> Self {
        Self { b: s.as_bytes(), i: 0 }
    }
    /// Skip ASCII whitespace.
    fn ws(&mut self) {
        while self.i < self.b.len() && (self.b[self.i] as char).is_whitespace() {
            self.i += 1;
        }
    }
    /// Peek current byte (0 sentinel at EOF).
    fn peek(&self) -> u8 {
        *self.b.get(self.i).unwrap_or(&0)
    }
    /// Dispatch on leading char to literal/string/array/object/number.
    fn parse_value(&mut self) -> Result<JsonVal, String> {
        self.ws();
        match self.peek() {
            b'n' => self.parse_lit("null", JsonVal::Null),
            b't' => self.parse_lit("true", JsonVal::Bool(true)),
            b'f' => self.parse_lit("false", JsonVal::Bool(false)),
            b'"' => Ok(JsonVal::Str(self.parse_string()?)),
            b'[' => self.parse_array(),
            b'{' => self.parse_object(),
            b'-' | b'0'..=b'9' => self.parse_number(),
            c => Err(format!("unexpected char '{}' at {}", c as char, self.i)),
        }
    }
    /// Match exact literal (null/true/false) or error.
    fn parse_lit(&mut self, lit: &str, v: JsonVal) -> Result<JsonVal, String> {
        if self.b.len() >= self.i + lit.len() && &self.b[self.i..self.i + lit.len()] == lit.as_bytes() {
            self.i += lit.len();
            Ok(v)
        } else {
            Err(format!("expected {}", lit))
        }
    }
    /// Parse quoted string with \" \\ \/ \n \r \t \uXXXX escapes.
    fn parse_string(&mut self) -> Result<String, String> {
        // assumes opening quote — caller peeked b'"'.
        self.i += 1;
        let mut out = String::new();
        while self.i < self.b.len() {
            let c = self.b[self.i];
            if c == b'"' {
                self.i += 1;
                return Ok(out);
            } else if c == b'\\' {
                self.i += 1;
                if self.i >= self.b.len() {
                    break;
                }
                let e = self.b[self.i];
                match e {
                    b'"' => out.push('"'),
                    b'\\' => out.push('\\'),
                    b'/' => out.push('/'),
                    b'n' => out.push('\n'),
                    b'r' => out.push('\r'),
                    b't' => out.push('\t'),
                    b'u' => {
                        if self.i + 4 >= self.b.len() {
                            return Err("bad \\u escape".into());
                        }
                        let hex = std::str::from_utf8(&self.b[self.i + 1..self.i + 5])
                            .map_err(|_| "bad \\u escape".to_string())?;
                        let cp = u32::from_str_radix(hex, 16).map_err(|_| "bad \\u escape".to_string())?;
                        out.push(char::from_u32(cp).unwrap_or('\u{FFFD}'));
                        self.i += 4;
                    }
                    _ => out.push(e as char),
                }
                self.i += 1;
            } else {
                out.push(c as char);
                self.i += 1;
            }
        }
        Err("unterminated string".into())
    }
    /// Parse number: Int unless . e E present (-> Float).
    fn parse_number(&mut self) -> Result<JsonVal, String> {
        let start = self.i;
        while self.i < self.b.len() && matches!(self.b[self.i], b'-' | b'+' | b'0'..=b'9' | b'.' | b'e' | b'E') {
            self.i += 1;
        }
        let s = std::str::from_utf8(&self.b[start..self.i]).map_err(|e| e.to_string())?;
        if s.contains('.') || s.contains('e') || s.contains('E') {
            s.parse::<f64>().map(JsonVal::Float).map_err(|e| e.to_string())
        } else {
            s.parse::<i64>().map(JsonVal::Int).map_err(|e| e.to_string())
        }
    }
    /// Parse [...] array (handles empty + trailing comma rules via peek loop).
    fn parse_array(&mut self) -> Result<JsonVal, String> {
        self.i += 1;
        let mut items = Vec::new();
        loop {
            self.ws();
            if self.peek() == b']' {
                self.i += 1;
                return Ok(JsonVal::Arr(items));
            }
            items.push(self.parse_value()?);
            self.ws();
            match self.peek() {
                b',' => {
                    self.i += 1;
                }
                b']' => {
                    self.i += 1;
                    return Ok(JsonVal::Arr(items));
                }
                _ => return Err("expected ',' or ']'".into()),
            }
        }
    }
    /// Parse {...} object as ordered pairs (duplicate keys kept in order).
    fn parse_object(&mut self) -> Result<JsonVal, String> {
        self.i += 1;
        let mut pairs = Vec::new();
        loop {
            self.ws();
            if self.peek() == b'}' {
                self.i += 1;
                return Ok(JsonVal::Obj(pairs));
            }
            self.ws();
            if self.peek() != b'"' {
                return Err("expected string key".into());
            }
            let k = self.parse_string()?;
            self.ws();
            if self.peek() != b':' {
                return Err("expected ':'".into());
            }
            self.i += 1;
            let v = self.parse_value()?;
            pairs.push((k, v));
            self.ws();
            match self.peek() {
                b',' => {
                    self.i += 1;
                }
                b'}' => {
                    self.i += 1;
                    return Ok(JsonVal::Obj(pairs));
                }
                _ => return Err("expected ',' or '}'".into()),
            }
        }
    }
}

/// Convert parsed JSON constant to runtime Value (recursive for Arr/Obj).
fn json_to_value(j: &JsonVal) -> Value {
    match j {
        JsonVal::Null => Value::Nil,
        JsonVal::Bool(b) => Value::Bool(*b),
        JsonVal::Int(i) => Value::Int(*i),
        JsonVal::Float(x) => Value::Float(*x),
        JsonVal::Str(s) => Value::Str(s.clone()),
        JsonVal::Arr(items) => {
            let els = items.iter().map(json_to_value).collect();
            Value::List(Arc::new(Mutex::new(els)))
        }
        JsonVal::Obj(pairs) => {
            if pairs.len() == 1 && pairs[0].0 == "$native" {
                if let JsonVal::Str(name) = &pairs[0].1 {
                    return Value::Native(name.clone());
                }
            }
            if pairs.len() == 1 && pairs[0].0 == "$repr" {
                return Value::Str(pairs[0].1.to_string_repr());
            }
            let els = pairs
                .iter()
                .map(|(k, v)| (Value::Str(k.clone()), json_to_value(v)))
                .collect();
            Value::Dict(Arc::new(Mutex::new(els)))
        }
    }
}

impl JsonVal {
    /// Fallback Display for $repr objects: primitives render plainly, Arr/Obj via Debug.
    fn to_string_repr(&self) -> String {
        match self {
            JsonVal::Null => "None".into(),
            JsonVal::Bool(b) => b.to_string(),
            JsonVal::Int(i) => i.to_string(),
            JsonVal::Float(x) => x.to_string(),
            JsonVal::Str(s) => s.clone(),
            JsonVal::Arr(a) => format!("{:?}", a),
            JsonVal::Obj(o) => format!("{:?}", o),
        }
    }
}

/// Parse top-level JSON array string into Vec<Value> constants pool.
fn parse_constants_json(s: &str) -> Result<Vec<Value>, String> {
    let mut p = JsonParser::new(s);
    let v = p.parse_value().map_err(|e| format!("constants JSON error: {}", e))?;
    match v {
        JsonVal::Arr(items) => Ok(items.iter().map(json_to_value).collect()),
        _ => Err("constants JSON must be an array".into()),
    }
}

// ---------------------------------------------------------------------------
// Entry points — pyo3 module `my_rust_module` exposes run_bytecode (primary)
// and svm (legacy TCP). Both build Arc<Program> then Vm::run to completion.
// ---------------------------------------------------------------------------

/// Direct call from Python: run_bytecode(bytecode: list[int], constants_json: str).
/// This is the primary bridge — no sockets, works on Windows/macOS/Linux.
#[pyfunction]
fn run_bytecode(bytecode: Vec<u8>, constants_json: String) -> PyResult<()> {
    let constants = parse_constants_json(&constants_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))?;
    let program = Arc::new(Program { bytecode, constants });
    let mut vm = Vm::new(program);
    vm.run();
    Ok(())
}

/// Legacy blocking server (TCP, cross-platform). Listens on 127.0.0.1:64201
/// for {"bytecode": [...], "constants": [...]} lines. Kept for backwards
/// compat with Compiler.send_to_rust(); prefer run_bytecode() instead.
#[pyfunction]
fn svm() -> PyResult<()> {
    let listener = TcpListener::bind("127.0.0.1:64201")
        .map_err(|e| pyo3::exceptions::PyOSError::new_err(e.to_string()))?;

    for stream in listener.incoming() {
        match stream {
            Ok(mut stream) => {
                let mut buffer = String::new();
                if stream.read_to_string(&mut buffer).is_err() {
                    eprintln!("Error reading from stream");
                    continue;
                }
                println!("Received {} bytes from Python", buffer.len());
                // Payload is one JSON object line: {"bytecode":[...],"constants":[...]}
                let bc_start = buffer.find("\"bytecode\"").unwrap_or(0);
                let _ = bc_start;
                // Reuse the constants parser on the constants array slice if present.
                let bytecode: Vec<u8> = Vec::new();
                let constants: Vec<Value> = Vec::new();
                // Minimal legacy handling: expect "bytecode": [n, n, ...] then constants array.
                // Parse with the small JSON parser for robustness.
                let mut p = JsonParser::new(buffer.trim());
                match p.parse_value() {
                    Ok(JsonVal::Obj(pairs)) => {
                        let mut bc = Vec::new();
                        let mut consts = Vec::new();
                        for (k, v) in pairs {
                            if k == "bytecode" {
                                if let JsonVal::Arr(items) = v {
                                    for it in items {
                                        match it {
                                            JsonVal::Int(n) => bc.push((n & 0xFF) as u8),
                                            JsonVal::Float(x) => bc.push((x as i64 & 0xFF) as u8),
                                            _ => {}
                                        }
                                    }
                                }
                            } else if k == "constants" {
                                if let JsonVal::Arr(items) = v {
                                    consts = items.iter().map(json_to_value).collect();
                                }
                            }
                        }
                        if bc.is_empty() {
                            eprintln!("No bytecode parsed from payload; skipping run");
                            continue;
                        }
                        let program = Arc::new(Program { bytecode: bc, constants: consts });
                        let mut vm = Vm::new(program);
                        vm.run();
                    }
                    _ => {
                        // Fallback: old whitespace format "1 2 3\n..."
                        let Some((first_line, _)) = buffer.split_once('\n') else {
                            eprintln!("Malformed payload");
                            continue;
                        };
                        let bc: Vec<u8> = first_line
                            .split_whitespace()
                            .filter_map(|tok| tok.parse::<u8>().ok())
                            .collect();
                        if bc.is_empty() {
                            eprintln!("No bytecode parsed; skipping run");
                            continue;
                        }
                        let _ = (bytecode, constants);
                        let program = Arc::new(Program { bytecode: bc, constants: vec![] });
                        let mut vm = Vm::new(program);
                        vm.run();
                    }
                }
            }
            Err(err) => eprintln!("Error: {}", err),
        }
    }

    Ok(())
}

#[pymodule]
/// Register run_bytecode + svm on the Python module object.
fn my_rust_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(run_bytecode, m)?)?;
    m.add_function(wrap_pyfunction!(svm, m)?)?;
    Ok(())
}