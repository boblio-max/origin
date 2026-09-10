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

use std::collections::HashMap;
use std::fmt;
use std::fs;
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{SystemTime, UNIX_EPOCH};
use std::net::TcpListener;
use std::io::Read;
use pyo3::prelude::*;

// ---------------------------------------------------------------------------
// OpCode — discriminants MUST match ORIGIN_CODE/bc/byteKey.py (0x01..0x51)
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum OpCode {
    PushConst = 0x01,
    LoadVar = 0x02,
    StoreVar = 0x03,
    Add = 0x04,
    Sub = 0x05,
    Mul = 0x06,
    Div = 0x07,
    Mod = 0x08,
    Pow = 0x09,
    Negate = 0x0A,
    Eq = 0x0B,
    Neq = 0x0C,
    Lt = 0x0D,
    Gt = 0x0E,
    Lte = 0x0F,
    Gte = 0x10,
    And = 0x11,
    Or = 0x12,
    Not = 0x13,
    Jmp = 0x14,
    JmpIfFalse = 0x15,
    Print = 0x16,
    Input = 0x17,
    Len = 0x18,
    Sqrt = 0x19,
    RandNum = 0x1A,
    ListInit = 0x1B,
    DictInit = 0x1C,
    IndexLoad = 0x1D,
    IndexStore = 0x1E,
    Halt = 0x1F,
    Pop = 0x20,
    Dup = 0x21,
    Call = 0x22,
    Return = 0x23,
    LoopStart = 0x24,
    LoopEnd = 0x25,
    Break = 0x26,
    Continue = 0x27,
    CastStr = 0x28,
    CastInt = 0x29,
    CastFloat = 0x2A,
    GetIter = 0x2B,
    ForIter = 0x2C,
    MakeClass = 0x2D,
    LoadAttr = 0x2E,
    StoreAttr = 0x2F,
    MakeClosure = 0x30,
    LoadUpvalue = 0x31,
    StoreUpvalue = 0x32,
    SetupExcept = 0x33,
    PopExcept = 0x34,
    Throw = 0x35,
    ImportName = 0x36,
    ImportFrom = 0x37,
    BitAnd = 0x38,
    BitOr = 0x39,
    BitXor = 0x3A,
    BitNot = 0x3B,
    LShift = 0x3C,
    RShift = 0x3D,
    UnpackSeq = 0x3E,
    FormatVal = 0x3F,
    BuildStr = 0x40,
    ReadFile = 0x41,
    WriteFile = 0x42,
    AppendFile = 0x43,
    HardwareCall = 0x44,
    SetServo = 0x45,
    SetPin = 0x46,
    ParallelStart = 0x47,
    ParallelEnd = 0x48,
    ExecPy = 0x49,
    Move = 0x4A,
    Copy = 0x4B,
    Swap = 0x4C,
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
// Value
// ---------------------------------------------------------------------------

pub type ListRef = Arc<Mutex<Vec<Value>>>;
pub type DictRef = Arc<Mutex<Vec<(Value, Value)>>>; // assoc list: dynamic keys, no Hash needed

#[derive(Clone)]
pub enum Value {
    Int(i64),
    Float(f64),
    Str(String),
    Bool(bool),
    Nil,
    List(ListRef),
    Dict(DictRef),
    Class(Arc<OriginClass>),
    Instance(Arc<Mutex<OriginInstance>>),
    BoundMethod(Arc<Mutex<OriginInstance>>, u32), // (instance, method bytecode addr)
    /// Address of a function's first instruction in the bytecode stream.
    FuncAddr(u32),
    /// Name of a fixed native builtin (see `call_native`).
    Native(String),
}

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

    pub fn as_i64(&self) -> i64 {
        match self {
            Value::Int(i) => *i,
            Value::Float(x) => *x as i64,
            Value::Bool(b) => *b as i64,
            Value::Str(s) => s.parse().unwrap_or(0),
            _ => 0,
        }
    }

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
// ---------------------------------------------------------------------------

pub struct OriginClass {
    pub name: String,
    pub fields: Vec<String>,
    /// method name -> bytecode address
    pub methods: HashMap<String, u32>,
}

pub struct OriginInstance {
    pub class: Arc<OriginClass>,
    pub attrs: HashMap<String, Value>,
}

// ---------------------------------------------------------------------------
// VM
// ---------------------------------------------------------------------------

/// Bytecode + constants are read-only once loaded, so they're shared
/// across worker threads (spawned for PARALLEL_START) via `Arc`.
pub struct Program {
    pub bytecode: Vec<u8>,
    pub constants: Vec<Value>,
}

pub struct Vm {
    program: Arc<Program>,
    stack: Vec<Value>,
    variables: HashMap<String, Value>,
    pc: usize,
    call_stack: Vec<(usize, HashMap<String, Value>)>,
    try_catch_stack: Vec<usize>,
    rng_state: u64,
}

/// Distinguishes how a VM's inner run loop stopped, so callers (RETURN,
/// PARALLEL_END, top-level run) can react appropriately.
enum StopReason {
    Halted,
    Returned,
    ExhaustedBytecode,
}

impl Vm {
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

    fn next_byte(&mut self) -> u8 {
        let b = self.program.bytecode[self.pc];
        self.pc += 1;
        b
    }

    fn next_u16(&mut self) -> u16 {
        let hi = self.next_byte() as u16;
        let lo = self.next_byte() as u16;
        (hi << 8) | lo
    }

    fn const_at(&self, idx: usize) -> Value {
        self.program.constants[idx].clone()
    }

    fn pop(&mut self) -> Value {
        self.stack.pop().expect("stack underflow")
    }

    fn push(&mut self, v: Value) {
        self.stack.push(v);
    }

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
    fn step_loop(&mut self) -> StopReason {
        while self.pc < self.program.bytecode.len() {
            let opcode = OpCode::from_byte(self.next_byte());

            match opcode {
                OpCode::Return => {
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
            PushConst => {
                let idx = self.next_byte() as usize;
                let c = self.const_at(idx);
                self.push(c);
            }
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
            Sub => self.binop_numeric(|x, y| x - y, |x, y| x - y),
            Mul => self.binop_numeric(|x, y| x * y, |x, y| x * y),
            Div => {
                let b = self.pop();
                let a = self.pop();
                self.push(Value::Float(a.as_f64() / b.as_f64()));
            }
            FloorDiv => self.binop_numeric(|x, y| x.div_euclid(y), |x, y| (x / y).floor()),
            Mod => self.binop_numeric(|x, y| x.rem_euclid(y), |x, y| x % y),
            Pow => {
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
                let v = self.pop();
                match v {
                    Value::Int(i) => self.push(Value::Int(-i)),
                    _ => self.push(Value::Float(-v.as_f64())),
                }
            }
            BitAnd => self.binop_numeric(|x, y| x & y, |_, _| 0.0),
            BitOr => self.binop_numeric(|x, y| x | y, |_, _| 0.0),
            BitXor => self.binop_numeric(|x, y| x ^ y, |_, _| 0.0),
            BitNot => {
                let v = self.pop();
                self.push(Value::Int(!v.as_i64()));
            }
            LShift => self.binop_numeric(|x, y| x << y, |_, _| 0.0),
            RShift => self.binop_numeric(|x, y| x >> y, |_, _| 0.0),
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
                let prompt = self.pop();
                print!("{}", prompt);
                use std::io::{self, Write};
                io::stdout().flush().ok();
                let mut line = String::new();
                io::stdin().read_line(&mut line).ok();
                self.push(Value::Str(line.trim_end_matches('\n').to_string()));
            }
            Sqrt => {
                let v = self.pop();
                self.push(Value::Float(v.as_f64().sqrt()));
            }
            Abs => {
                let v = self.pop();
                match v {
                    Value::Int(i) => self.push(Value::Int(i.abs())),
                    _ => self.push(Value::Float(v.as_f64().abs())),
                }
            }
            Floor => {
                let v = self.pop();
                self.push(Value::Int(v.as_f64().floor() as i64));
            }
            Ceil => {
                let v = self.pop();
                self.push(Value::Int(v.as_f64().ceil() as i64));
            }
            Pop => {
                self.pop();
            }
            Dup => {
                let v = self.stack.last().expect("stack underflow").clone();
                self.push(v);
            }
            RandNum => {
                let end = self.pop().as_i64();
                let start = self.pop().as_i64();
                let n = self.rand_range(start, end);
                self.push(Value::Int(n));
            }
            ListInit => {
                let n = self.next_byte() as usize;
                let mut elements = vec![Value::Nil; n];
                for i in (0..n).rev() {
                    elements[i] = self.pop();
                }
                self.push(Value::List(Arc::new(Mutex::new(elements))));
            }
            DictInit => {
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
                let idx = self.pop();
                let coll = self.pop();
                self.push(index_load(&coll, &idx));
            }
            IndexStore => {
                let val = self.pop();
                let idx = self.pop();
                let coll = self.pop();
                index_store(&coll, &idx, val);
            }
            Len => {
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
                let num_args = self.next_byte() as usize;
                let func = self.pop();
                match func {
                    Value::FuncAddr(addr) => {
                        self.call_stack.push((self.pc, self.variables.clone()));
                        self.pc = addr as usize;
                    }
                    Value::BoundMethod(instance, addr) => {
                        let insert_at = self.stack.len() - num_args;
                        self.stack.insert(insert_at, Value::Instance(instance));
                        self.call_stack.push((self.pc, self.variables.clone()));
                        self.pc = addr as usize;
                    }
                    Value::Class(class) => {
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
                let target = self.next_u16() as usize;
                self.try_catch_stack.push(target);
            }
            PopExcept => {
                self.try_catch_stack.pop();
            }
            Throw => {
                let exception_val = self.pop();
                if let Some(handler_pc) = self.try_catch_stack.pop() {
                    self.pc = handler_pc;
                    self.push(exception_val);
                } else {
                    panic!("Uncaught Exception: {}", exception_val);
                }
            }
            FormatVal => {
                let val = self.pop();
                self.push(Value::Str(val.to_string()));
            }
            BuildStr => {
                let count = self.next_byte() as usize;
                let mut parts = vec![String::new(); count];
                for i in (0..count).rev() {
                    parts[i] = self.pop().to_string();
                }
                self.push(Value::Str(parts.concat()));
            }
            UnpackSeq => {
                let _count = self.next_byte(); // operand present for wire compat; not needed here
                let seq = self.pop();
                if let Value::List(l) = seq {
                    for item in l.lock().unwrap().iter().rev() {
                        self.push(item.clone());
                    }
                }
            }
            ReadFile => {
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
                let content = self.pop().to_string();
                let path = self.pop().to_string();
                fs::write(path, content).expect("write_file failed");
            }
            AppendFile => {
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
                let angle = self.pop();
                let channel = self.pop();
                println!("[SIM] Servo {} angle set to {}", channel, angle);
            }
            SetPin => {
                let state = self.pop();
                let pin = self.pop();
                println!("[SIM] Pin {} set to {}", pin, state.truthy());
            }
            ParallelStart => {
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
                let dest_idx = self.next_byte() as usize;
                let src_idx = self.next_byte() as usize;
                let dest_name = self.const_at(dest_idx).to_string();
                let src_name = self.const_at(src_idx).to_string();
                let v = self.variables.get(&src_name).cloned().unwrap_or(Value::Nil);
                self.variables.insert(dest_name, v);
            }
            Copy => {
                let dest_idx = self.next_byte() as usize;
                let src_idx = self.next_byte() as usize;
                let dest_name = self.const_at(dest_idx).to_string();
                let src_name = self.const_at(src_idx).to_string();
                if let Some(v) = self.variables.get(&src_name).cloned() {
                    self.variables.insert(dest_name, v);
                }
            }
            Swap => {
                let b = self.pop();
                let a = self.pop();
                self.push(b);
                self.push(a);
            }
            Cube => {
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
                // Compiler lowers break/continue to JMP patches; these are markers.
            }
            MakeClosure | LoadUpvalue | StoreUpvalue => {
                panic!(
                    "{:?} reached: closures/upvalues are not supported by the Rust VM yet",
                    opcode
                );
            }
            ImportName | ImportFrom => {
                let name = self.pop().to_string();
                panic!(
                    "import '{}' reached: imports are resolved at compile time; Rust VM has no module loader",
                    name
                );
            }
            Return | Halt | ExecPy => unreachable!("handled by caller"),
        }
    }

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
// Collection helpers
// ---------------------------------------------------------------------------

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
// ---------------------------------------------------------------------------

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
    b: &'a [u8],
    i: usize,
}

impl<'a> JsonParser<'a> {
    fn new(s: &'a str) -> Self {
        Self { b: s.as_bytes(), i: 0 }
    }
    fn ws(&mut self) {
        while self.i < self.b.len() && (self.b[self.i] as char).is_whitespace() {
            self.i += 1;
        }
    }
    fn peek(&self) -> u8 {
        *self.b.get(self.i).unwrap_or(&0)
    }
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
    fn parse_lit(&mut self, lit: &str, v: JsonVal) -> Result<JsonVal, String> {
        if self.b.len() >= self.i + lit.len() && &self.b[self.i..self.i + lit.len()] == lit.as_bytes() {
            self.i += lit.len();
            Ok(v)
        } else {
            Err(format!("expected {}", lit))
        }
    }
    fn parse_string(&mut self) -> Result<String, String> {
        // assumes opening quote
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

fn parse_constants_json(s: &str) -> Result<Vec<Value>, String> {
    let mut p = JsonParser::new(s);
    let v = p.parse_value().map_err(|e| format!("constants JSON error: {}", e))?;
    match v {
        JsonVal::Arr(items) => Ok(items.iter().map(json_to_value).collect()),
        _ => Err("constants JSON must be an array".into()),
    }
}

// ---------------------------------------------------------------------------
// Entry points
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
fn my_rust_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(run_bytecode, m)?)?;
    m.add_function(wrap_pyfunction!(svm, m)?)?;
    Ok(())
}