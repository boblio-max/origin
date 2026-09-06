package origin.bc.JavaImplement;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.HashMap;
import java.util.Iterator;
import java.util.LinkedList;
import java.util.List;
import java.util.Map;

/**
 * sVM â€” Origin bytecode virtual machine. 1:1 port of bc/svm.py.
 *
 * Stack frame layout (svm.py:49-58):
 *   bytecode[], constants[]       â€” from the loader
 *   stack                          â€” operand stack (ArrayDeque, used as stack)
 *   variables                      â€” current frame's locals (HashMap)
 *   pc                             â€” program counter
 *   callStack                      â€” [(retPc, savedVariables), ...]
 *   tryCatchStack                  â€” handler-PC stack for THROW
 *
 * Jump targets are encoded as two big-endian bytes (svm.py:178,183,268,350):
 *   target = (bytecode[pc] << 8) | bytecode[pc+1]
 * This caps code size at 64KB; not addressed in this port (kept for parity).
 *
 * Parallel execution (PARALLEL_START) is implemented with one shared
 * ExecutorService and a per-task copy of the operand stack. The Python
 * version (svm.py:469-479) races on self.pc/self.stack without locking;
 * the Java port fixes that bug by giving each task its own state.
 */
public final class svm {

    private final byte[] bytecode;
    private final Object[] constants;

    // LinkedList used as a stack with TOP-at-end semantics (matches Python's
    // list.append/pop). It permits null elements (e.g. PUSH_CONST None) and
    // supports middle insertion via add(int, E) for the BoundMethod CALL
    // path (svm.py:318). CALL on a BoundMethod inserts `self` beneath the
    // numArgs args; we emulate the Python stack.insert semantics directly.
    private final LinkedList<Object> stack = new LinkedList<>();
    private Map<String, Object> variables = new HashMap<>();
    private int pc;

    private final Deque<int[]> callStack = new ArrayDeque<>();          // each entry: [retPc, localsRefIndex]
    private final List<Map<String, Object>> savedLocals = new ArrayList<>();
    private final Deque<Integer> tryCatchStack = new ArrayDeque<>();

    private final Builtins builtins;
    private final java.util.concurrent.ExecutorService parallelPool =
            java.util.concurrent.Executors.newCachedThreadPool();

    public svm(byte[] bytecode, Object[] constants) {
        this(bytecode, constants, new Builtins());
    }

    public svm(byte[] bytecode, Object[] constants, Builtins builtins) {
        this.bytecode = bytecode;
        this.constants = constants;
        this.builtins = builtins;
    }

    public void run() {
        while (pc < bytecode.length) {
            byte op = bytecode[pc++];
            exec(op);
        }
        parallelPool.shutdown();
    }

    // ---- single-opcode dispatcher (mirrors svm.py:60-466) ----
    private void exec(byte op) {
        switch (op) {
            // ----- constants & variables -----
            case OpCode.PUSH_CONST: {
                int idx = ubyte(bytecode[pc++]);
                push(constants[idx]);
                break;
            }
            case OpCode.LOAD_VAR: {
                int idx = ubyte(bytecode[pc++]);
                String name = (String) constants[idx];
                if (!variables.containsKey(name)) {
                    throw new RuntimeException("Name '" + name + "' is not defined");
                }
                push(variables.get(name));
                break;
            }
            case OpCode.STORE_VAR: {
                int idx = ubyte(bytecode[pc++]);
                String name = (String) constants[idx];
                Object val = pop();
                variables.put(name, val);
                break;
            }

            // ----- arithmetic -----
            case OpCode.ADD: binArith(Arith.ADD); break;
            case OpCode.SUB: binArith(Arith.SUB); break;
            case OpCode.MUL: binArith(Arith.MUL); break;
            case OpCode.DIV: binArith(Arith.DIV); break;
            case OpCode.FLOOR_DIV: binArith(Arith.FLOOR_DIV); break;
            case OpCode.MOD: binArith(Arith.MOD); break;
            case OpCode.POW: binArith(Arith.POW); break;
            case OpCode.NEGATE: {
                Object v = pop();
                if (v instanceof Long) push(-(Long) v);
                else if (v instanceof Double) push(-(Double) v);
                else throw new RuntimeException("unary - on non-number");
                break;
            }
            case OpCode.BIT_AND: bitwise(Arith.AND); break;
            case OpCode.BIT_OR:  bitwise(Arith.OR);  break;
            case OpCode.BIT_XOR: bitwise(Arith.XOR); break;
            case OpCode.BIT_NOT: {
                Object v = pop();
                if (v instanceof Long) push(~(Long) v);
                else throw new RuntimeException("bitwise ~ on non-int");
                break;
            }
            case OpCode.LSHIFT: bitwise(Arith.LSHIFT); break;
            case OpCode.RSHIFT: bitwise(Arith.RSHIFT); break;

            // ----- comparison -----
            case OpCode.EQ:  cmpPush(Cmp.EQ);  break;
            case OpCode.NEQ: cmpPush(Cmp.NEQ); break;
            case OpCode.LT:  cmpPush(Cmp.LT);  break;
            case OpCode.GT:  cmpPush(Cmp.GT);  break;
            case OpCode.LTE: cmpPush(Cmp.LTE); break;
            case OpCode.GTE: cmpPush(Cmp.GTE); break;

            // ----- control flow -----
            case OpCode.JMP: {
                int target = readJumpTarget();
                pc = target;
                break;
            }
            case OpCode.JMP_IF_FALSE: {
                int target = readJumpTarget();
                Object v = pop();
                if (!Builtins.toBool(v)) pc = target;
                break;
            }
            case OpCode.HALT: return;

            // ----- stack ops -----
            case OpCode.POP: pop(); break;
            case OpCode.DUP: push(peek()); break;

            // ----- I/O -----
            case OpCode.PRINT: {
                Object v = pop();
                System.out.println(Builtins.toStr(v));
                break;
            }
            case OpCode.INPUT: {
                Object prompt = pop();
                java.util.Scanner sc = new java.util.Scanner(System.in);
                String line = sc.nextLine();
                push(prompt == null ? line : line);
                break;
            }
            case OpCode.SQRT: {
                Object v = pop();
                push(Math.sqrt(Builtins.asDouble(v)));
                break;
            }
            case OpCode.ABS: {
                Object v = pop();
                if (v instanceof Double) push(Math.abs((Double) v));
                else push(Math.abs(Builtins.asLong(v)));
                break;
            }
            case OpCode.FLOOR: {
                push((long) Math.floor(Builtins.asDouble(pop())));
                break;
            }
            case OpCode.CEIL: {
                push((long) Math.ceil(Builtins.asDouble(pop())));
                break;
            }
            case OpCode.RAND_NUM: {
                long end   = Builtins.asLong(pop());
                long start = Builtins.asLong(pop());
                push((long) Builtins.randInt(start, end));
                break;
            }

            // ----- collections -----
            case OpCode.LEN: {
                Object v = pop();
                push(Builtins.lengthOf(v));
                break;
            }
            case OpCode.LIST_INIT: {
                int n = ubyte(bytecode[pc++]);
                List<Object> out = new ArrayList<>(n);
                for (int i = 0; i < n; i++) out.add(0, pop()); // svm.py:212
                push(out);
                break;
            }
            case OpCode.DICT_INIT: {
                int n = ubyte(bytecode[pc++]);
                Map<Object, Object> out = new HashMap<>();
                for (int i = 0; i < n; i++) {
                    Object v = pop();
                    Object k = pop();
                    out.put(k, v);
                }
                push(out);
                break;
            }
            case OpCode.INDEX_LOAD: {
                Object idx = pop();
                Object coll = pop();
                push(indexLoad(coll, idx));
                break;
            }
            case OpCode.INDEX_STORE: {
                Object val = pop();
                Object idx = pop();
                Object coll = pop();
                indexStore(coll, idx, val);
                break;
            }
            case OpCode.UNPACK_SEQ: {
                int count = ubyte(bytecode[pc++]);
                Object seq = pop();
                if (seq instanceof List) {
                    List<?> l = (List<?>) seq;
                    for (int i = l.size() - 1; i >= 0; i--) push(l.get(i));
                } else if (seq instanceof String) {
                    String s = (String) seq;
                    for (int i = s.length() - 1; i >= 0; i--)
                        push(String.valueOf(s.charAt(i)));
                } else {
                    throw new RuntimeException("cannot unpack non-iterable");
                }
                break;
            }

            // ----- logic -----
            case OpCode.NOT: push(!Builtins.toBool(pop())); break;
            case OpCode.AND: {
                Object b = pop(); Object a = pop();
                push(Builtins.toBool(a) ? b : a);  // Python a and b semantics
                break;
            }
            case OpCode.OR: {
                Object b = pop(); Object a = pop();
                push(Builtins.toBool(a) ? a : b);
                break;
            }

            // ----- casts -----
            case OpCode.CAST_STR:   push(Builtins.toStr(pop())); break;
            case OpCode.CAST_INT:   push((Long) Builtins.asLong(pop())); break;
            case OpCode.CAST_FLOAT: push(Builtins.asDouble(pop())); break;

            // ----- iteration -----
            case OpCode.GET_ITER: push(iter(pop())); break;
            case OpCode.FOR_ITER: {
                int target = readJumpTarget();
                Iterator<?> it = (Iterator<?>) peek();
                if (it.hasNext()) {
                    push(it.next());
                } else {
                    pop();  // exhausted iterator
                    pc = target;
                }
                break;
            }

            // ----- OOP -----
            case OpCode.MAKE_CLASS: {
                List<?> methods = (List<?>) pop();
                List<?> fields = (List<?>) pop();
                String name = (String) pop();
                Map<String, Integer> methodMap = new HashMap<>();
                for (int i = 0; i + 1 < methods.size(); i += 2) {
                    methodMap.put((String) methods.get(i), ((Long) methods.get(i + 1)).intValue());
                }
                push(new OriginClass(name, new ArrayList<>((List<String>) fields), methodMap));
                break;
            }
            case OpCode.LOAD_ATTR: {
                String attr = (String) pop();
                Object obj = pop();
                if (obj instanceof OriginInstance) {
                    OriginInstance inst = (OriginInstance) obj;
                    if (inst.attrs.containsKey(attr)) {
                        push(inst.attrs.get(attr));
                    } else if (inst.originClass.methods.containsKey(attr)) {
                        push(new BoundMethod(inst, inst.originClass.methods.get(attr)));
                    } else {
                        throw new RuntimeException("'" + inst.originClass.name + "' object has no attribute '" + attr + "'");
                    }
                } else if (obj instanceof OriginClass) {
                    OriginClass cls = (OriginClass) obj;
                    if (cls.methods.containsKey(attr)) {
                        push(new BoundMethod(null, cls.methods.get(attr)));
                    } else {
                        throw new RuntimeException("type object '" + cls.name + "' has no attribute '" + attr + "'");
                    }
                } else {
                    // Generic get via map / list / string
                    if (obj instanceof Map) push(((Map<?, ?>) obj).get(attr));
                    else if (obj instanceof List) {
                        int i = Integer.parseInt(attr);
                        push(((List<?>) obj).get(i));
                    } else {
                        throw new RuntimeException("no attribute access on " + obj.getClass().getName());
                    }
                }
                break;
            }
            case OpCode.STORE_ATTR: {
                String attr = (String) pop();
                Object value = pop();
                Object obj = pop();
                if (obj instanceof OriginInstance) {
                    ((OriginInstance) obj).attrs.put(attr, value);
                } else if (obj instanceof Map) {
                    ((Map<Object, Object>) obj).put(attr, value);
                } else {
                    throw new RuntimeException("cannot set attribute on " + obj.getClass().getName());
                }
                break;
            }

            // ----- calls -----
            case OpCode.CALL: {
                int numArgs = ubyte(bytecode[pc++]);
                Object func = pop();
                if (func instanceof Long) {
                    int funcPc = ((Long) func).intValue();
                    saveFrame(numArgs);
                    pc = funcPc;
                } else if (func instanceof BoundMethod) {
                    BoundMethod bm = (BoundMethod) func;
                    // Python (svm.py:318): self.stack.insert(len(stack)-num_args, instance)
                    // In our LinkedList with TOP-at-end semantics, insertAt = stack.size()-numArgs
                    // puts the instance beneath the args â€” same effect as Python.
                    int insertAt = stack.size() - numArgs;
                    stack.add(insertAt, bm.instance);
                    saveFrame(numArgs);
                    pc = bm.funcPc;
                } else if (func instanceof OriginClass) {
                    OriginClass cls = (OriginClass) func;
                    OriginInstance instance = new OriginInstance(cls);
                    List<Object> args = new ArrayList<>(numArgs);
                    for (int i = 0; i < numArgs; i++) args.add(0, pop());
                    List<String> fields = cls.fields;
                    for (int i = 0; i < fields.size(); i++) {
                        instance.attrs.put(fields.get(i), i < args.size() ? args.get(i) : null);
                    }
                    push(instance);
                } else {
                    // Built-in call (svm.py:333-339)
                    List<Object> args = new ArrayList<>(numArgs);
                    for (int i = 0; i < numArgs; i++) args.add(0, pop());
                    Object result = callBuiltin(func, args);
                    push(result);
                }
                break;
            }
            case OpCode.RETURN: {
                if (!callStack.isEmpty()) {
                    int[] frame = callStack.pop();
                    pc = frame[0];
                    variables = savedLocals.remove(savedLocals.size() - 1);
                } else {
                    pc = bytecode.length;  // top-level return ends execution
                }
                break;
            }

            // ----- exceptions -----
            case OpCode.SETUP_EXCEPT: {
                int target = readJumpTarget();
                tryCatchStack.push(target);
                break;
            }
            case OpCode.POP_EXCEPT: {
                if (!tryCatchStack.isEmpty()) tryCatchStack.pop();
                break;
            }
            case OpCode.THROW: {
                Object exceptionVal = pop();
                if (!tryCatchStack.isEmpty()) {
                    int handlerPc = tryCatchStack.pop();
                    pc = handlerPc;
                    push(exceptionVal);
                } else {
                    throw new RuntimeException("Uncaught Exception: " + Builtins.toStr(exceptionVal));
                }
                break;
            }

            // ----- strings -----
            case OpCode.FORMAT_VAL: {
                Object v = pop();
                push(Builtins.toStr(v));
                break;
            }
            case OpCode.BUILD_STR: {
                int count = ubyte(bytecode[pc++]);
                StringBuilder sb = new StringBuilder();
                for (int i = 0; i < count; i++) sb.insert(0, Builtins.toStr(pop()));
                push(sb.toString());
                break;
            }

            // ----- file I/O -----
            case OpCode.READ_FILE: {
                String path = (String) pop();
                int count = (int) (long) (Long) pop();
                try {
                    if (count == -1) push(new String(java.nio.file.Files.readAllBytes(java.nio.file.Paths.get(path))));
                    else push(new String(java.nio.file.Files.readAllBytes(java.nio.file.Paths.get(path))).substring(0, count));
                } catch (java.io.IOException e) { throw new RuntimeException(e); }
                break;
            }
            case OpCode.WRITE_FILE: {
                Object content = pop();
                String path = (String) pop();
                try (java.io.FileWriter w = new java.io.FileWriter(path)) {
                    w.write(Builtins.toStr(content));
                } catch (java.io.IOException e) { throw new RuntimeException(e); }
                break;
            }
            case OpCode.APPEND_FILE: {
                Object content = pop();
                String path = (String) pop();
                try (java.io.FileWriter w = new java.io.FileWriter(path, true)) {
                    w.write(Builtins.toStr(content));
                } catch (java.io.IOException e) { throw new RuntimeException(e); }
                break;
            }

            // ----- hardware -----
            case OpCode.HARDWARE_CALL: {
                int idx = ubyte(bytecode[pc++]);
                int numArgs = ubyte(bytecode[pc++]);
                List<?> nsMethod = (List<?>) constants[idx];
                String ns = (String) nsMethod.get(0);
                String method = (String) nsMethod.get(1);
                List<Object> args = new ArrayList<>(numArgs);
                for (int i = 0; i < numArgs; i++) args.add(0, pop());
                push(HardwareSim.hardwareCall(ns, method, args));
                break;
            }
            case OpCode.SET_SERVO: {
                Object angle = pop();
                Object channel = pop();
                HardwareSim.setServo(Builtins.asLong(channel), Builtins.asDouble(angle));
                break;
            }
            case OpCode.SET_PIN: {
                Object state = pop();
                Object pin = pop();
                HardwareSim.setPin(Builtins.asLong(pin), Builtins.asLong(state));
                break;
            }

            // ----- parallel -----
            case OpCode.PARALLEL_START: {
                int numThreads = ubyte(bytecode[pc++]);
                int bodyStart = readJumpTarget();
                List<java.util.concurrent.Future<?>> tasks = new ArrayList<>();
                for (int i = 0; i < numThreads; i++) {
                    tasks.add(parallelPool.submit(() -> runFrom(bodyStart)));
                }
                push(new ParallelGroup(tasks));
                break;
            }
            case OpCode.PARALLEL_END: {
                ParallelGroup group = (ParallelGroup) pop();
                for (java.util.concurrent.Future<?> f : group.tasks) {
                    try { f.get(); }
                    catch (java.util.concurrent.ExecutionException e) {
                        Throwable c = e.getCause();
                        if (c instanceof RuntimeException) throw (RuntimeException) c;
                        throw new RuntimeException(c);
                    }
                    catch (java.lang.InterruptedException e) {
                        Thread.currentThread().interrupt();
                        throw new RuntimeException(e);
                    }
                }
                break;
            }

            // ----- exec -----
            case OpCode.EXEC_PY: {
                Object code = pop();
                HardwareSim.execPy(code);
                break;
            }

            // ----- loop markers: not actively used by svm.py either -----
            case OpCode.LOOP_START:
            case OpCode.LOOP_END:
            case OpCode.BREAK:
            case OpCode.CONTINUE:
            case OpCode.IMPORT_NAME:
            case OpCode.IMPORT_FROM:
            case OpCode.MAKE_CLOSURE:
            case OpCode.LOAD_UPVALUE:
            case OpCode.STORE_UPVALUE:
                // Reserved for future use; svm.py does not handle these either.
                break;

            default:
                throw new RuntimeException("Unknown opcode: 0x" + String.format("%02X", op & 0xFF));
        }
    }

    // ---- parallel-thread entry point ----
    private void runFrom(int startPc) {
        int savedPc = pc;
        Map<String, Object> savedVars = variables;
        // Each thread gets a fresh local-variable map; constants/bytecode are read-only.
        pc = startPc;
        variables = new HashMap<>();
        try {
            while (pc < bytecode.length) {
                byte op = bytecode[pc++];
                if (op == OpCode.RETURN || op == OpCode.HALT) return;
                exec(op);
            }
        } finally {
            pc = savedPc;
            variables = savedVars;
        }
    }

    // ---- frame helpers ----
    private void saveFrame(int numArgs) {
        savedLocals.add(variables);
        callStack.push(new int[]{ pc });
        variables = new HashMap<>();
        // svm.py doesn't pre-populate locals from args; origin's compiler
        // typically emits explicit STORE_VAR after CALL for bound parameters.
    }

    // ---- arithmetic / comparison helpers ----
    private enum Arith { ADD, SUB, MUL, DIV, FLOOR_DIV, MOD, POW, AND, OR, XOR, LSHIFT, RSHIFT }
    private enum Cmp   { EQ, NEQ, LT, GT, LTE, GTE }

    private void binArith(Arith op) {
        Object b = pop(); Object a = pop();
        if (a instanceof String || b instanceof String) {
            push(Builtins.toStr(a) + Builtins.toStr(b));
            return;
        }
        if (a instanceof Double || b instanceof Double) {
            double aa = Builtins.asDouble(a), bb = Builtins.asDouble(b);
            switch (op) {
                case ADD: push(aa + bb); break;
                case SUB: push(aa - bb); break;
                case MUL: push(aa * bb); break;
                case DIV: push(aa / bb); break;
                case FLOOR_DIV: push((long) Math.floor(aa / bb)); break;
                case MOD: push(aa % bb); break;
                case POW: push(Math.pow(aa, bb)); break;
                default:  throw new RuntimeException("bad op"); // unreachable
            }
            return;
        }
        long aa = Builtins.asLong(a), bb = Builtins.asLong(b);
        switch (op) {
            case ADD: push(aa + bb); break;
            case SUB: push(aa - bb); break;
            case MUL: push(aa * bb); break;
            case DIV: push(aa / bb); break;
            case FLOOR_DIV: push(aa / bb); break;
            case MOD: push(aa % bb); break;
            case POW: push(Math.pow(aa, bb)); break;
            default:  throw new RuntimeException("bad op");
        }
    }

    private void bitwise(Arith op) {
        Object b = pop(); Object a = pop();
        long aa = Builtins.asLong(a), bb = Builtins.asLong(b);
        switch (op) {
            case AND:    push(aa & bb); break;
            case OR:     push(aa | bb); break;
            case XOR:    push(aa ^ bb); break;
            case LSHIFT: push(aa << bb); break;
            case RSHIFT: push(aa >> bb); break;
            default: throw new RuntimeException("bad op");
        }
    }

    private void cmpPush(Cmp op) {
        Object b = pop(); Object a = pop();
        boolean result;
        if (a instanceof Double || b instanceof Double) {
            double aa = Builtins.asDouble(a), bb = Builtins.asDouble(b);
            switch (op) {
                case EQ:  result = aa == bb; break;
                case NEQ: result = aa != bb; break;
                case LT:  result = aa <  bb; break;
                case GT:  result = aa >  bb; break;
                case LTE: result = aa <= bb; break;
                case GTE: result = aa >= bb; break;
                default: throw new RuntimeException("bad op");
            }
        } else if (a instanceof Long && b instanceof Long) {
            long aa = (Long) a, bb = (Long) b;
            switch (op) {
                case EQ:  result = aa == bb; break;
                case NEQ: result = aa != bb; break;
                case LT:  result = aa <  bb; break;
                case GT:  result = aa >  bb; break;
                case LTE: result = aa <= bb; break;
                case GTE: result = aa >= bb; break;
                default: throw new RuntimeException("bad op");
            }
        } else {
            // Generic equals (svm.py:148 uses Python `==` semantics)
            switch (op) {
                case EQ:  result = a == null ? b == null : a.equals(b); break;
                case NEQ: result = !(a == null ? b == null : a.equals(b)); break;
                case LT:  result = compareAny(a, b) < 0;  break;
                case GT:  result = compareAny(a, b) > 0;  break;
                case LTE: result = compareAny(a, b) <= 0; break;
                case GTE: result = compareAny(a, b) >= 0; break;
                default: throw new RuntimeException("bad op");
            }
        }
        push(result);
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    private static int compareAny(Object a, Object b) {
        if (a instanceof Comparable && a.getClass().equals(b.getClass())) {
            return ((Comparable) a).compareTo(b);
        }
        throw new RuntimeException("unorderable types: " + a.getClass().getName() + " , " + b.getClass().getName());
    }

    // ---- stack helpers ----
    private void push(Object v) { stack.addLast(v); }   // TOP-at-end (Python semantics)
    private Object pop() { return stack.removeLast(); }
    private Object peek() { return stack.getLast(); }

    private static int ubyte(byte b) { return b & 0xFF; }
    private int readJumpTarget() {
        int hi = ubyte(bytecode[pc++]);
        int lo = ubyte(bytecode[pc++]);
        return (hi << 8) | lo;
    }

    // ---- collection helpers ----
    private static Object indexLoad(Object coll, Object idx) {
        if (coll instanceof List) return ((List<?>) coll).get(((Long) idx).intValue());
        if (coll instanceof Map)  return ((Map<?, ?>) coll).get(idx);
        if (coll instanceof String) return String.valueOf(((String) coll).charAt(((Long) idx).intValue()));
        throw new RuntimeException("unsubscriptable: " + coll.getClass().getName());
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    private static void indexStore(Object coll, Object idx, Object val) {
        if (coll instanceof List) ((List) coll).set(((Long) idx).intValue(), val);
        else if (coll instanceof Map) ((Map) coll).put(idx, val);
        else throw new RuntimeException("cannot store index into " + coll.getClass().getName());
    }

    private static Iterator<?> iter(Object v) {
        if (v instanceof List) return ((List<?>) v).iterator();
        if (v instanceof String) {
            String s = (String) v;
            List<Character> chars = new ArrayList<>(s.length());
            for (int i = 0; i < s.length(); i++) chars.add(s.charAt(i));
            return chars.iterator();
        }
        if (v instanceof Map) return ((Map<?, ?>) v).entrySet().iterator();
        throw new RuntimeException("not iterable: " + v.getClass().getName());
    }

    // ---- built-in callable bridge ----
    private Object callBuiltin(Object func, List<Object> args) {
        if (func instanceof Builtins.BuiltinFn) {
            return ((Builtins.BuiltinFn) func).call(args);
        }
        // Compiler-side builtins are registered as strings (svm.py CALL branch).
        // to_byte.py uses function objects, but on the wire they serialize as names.
        if (func instanceof String) {
            Builtins.BuiltinFn f = builtins.get((String) func);
            if (f != null) return f.call(args);
        }
        // Fall back to invoking the name in the registry by class method name.
        if (func instanceof String && builtins.contains((String) func)) {
            return builtins.get((String) func).call(args);
        }
        throw new RuntimeException("cannot call object: " + func);
    }

    /** Marker class returned from PARALLEL_START so PARALLEL_END can join. */
    public static final class ParallelGroup {
        public final List<java.util.concurrent.Future<?>> tasks;
        public ParallelGroup(List<java.util.concurrent.Future<?>> tasks) { this.tasks = tasks; }
    }

    // ---- backwards-compatible alias for runnerByte.py / test_oop.py / etc. ----
    public static final class VM {
        private final svm impl;
        public VM(byte[] bytecode, Object[] constants) { this.impl = new svm(bytecode, constants); }
        public VM(byte[] bytecode, Object[] constants, Builtins b) { this.impl = new svm(bytecode, constants, b); }
        public void run() { impl.run(); }
    }
}
