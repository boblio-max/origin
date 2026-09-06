package origin.bc;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Scanner;
import java.util.concurrent.ThreadLocalRandom;

/**
 * Registry of built-in callables that the VM exposes to bytecode via CALL.
 * Mirrors the {open, read, write, append, range, ...} dictionary in
 * to_byte.py:18 plus the implicit built-ins handled by the Python branch
 * of CALL at svm.py:333-339.
 */
public final class Builtins {

    @FunctionalInterface
    public interface BuiltinFn {
        Object call(List<Object> args);
    }

    private final Map<String, BuiltinFn> registry;

    public Builtins() {
        this.registry = new HashMap<>();
        registerDefaults();
    }

    public BuiltinFn get(String name) {
        return registry.get(name);
    }

    public boolean contains(String name) {
        return registry.containsKey(name);
    }

    private void registerDefaults() {
        // Compiler builtins (to_byte.py:18-24)
        registry.put("open", args -> new OpenFile(asStr(args, 0), "r"));
        registry.put("read", args -> {
            OpenFile f = asOpenFile(args, 0);
            return f.readAll();
        });
        registry.put("write", args -> {
            Object pathOrFile = args.get(0);
            Object content = args.get(1);
            String contentStr = String.valueOf(content);
            if (pathOrFile instanceof OpenFile openFile) {
                openFile.writeAll(contentStr);
                return null;
            }
            try (java.io.FileWriter w = new java.io.FileWriter(asStr(args, 0))) {
                w.write(contentStr);
            } catch (java.io.IOException e) {
                throw new RuntimeException(e);
            }
            return null;
        });
        registry.put("append", args -> {
            Object pathOrFile = args.get(0);
            Object content = args.get(1);
            String contentStr = String.valueOf(content);
            if (pathOrFile instanceof OpenFile openFile) {
                openFile.appendAll(contentStr);
                return null;
            }
            try (java.io.FileWriter w = new java.io.FileWriter(asStr(args, 0), true)) {
                w.write(contentStr);
            } catch (java.io.IOException e) {
                throw new RuntimeException(e);
            }
            return null;
        });
        registry.put("range", args -> {
            int n = args.size();
            int start, end;
            if (n == 1) { start = 0; end = asInt(args, 0); }
            else { start = asInt(args, 0); end = asInt(args, 1); }
            List<Object> out = new ArrayList<>();
            for (int i = start; i < end; i++) out.add((long) i);
            return out;
        });

        // Implied built-ins called from bytecode (svm.py CALL branch)
        registry.put("str",  args -> toStr(args.isEmpty() ? null : args.get(0)));
        registry.put("int",  args -> {
            if (args.isEmpty()) return 0L;
            Object v = args.get(0);
            if (v instanceof Long) return v;
            if (v instanceof Double) return ((Double) v).longValue();
            if (v instanceof Boolean) return ((Boolean) v) ? 1L : 0L;
            return Long.parseLong(String.valueOf(v));
        });
        registry.put("float", args -> {
            if (args.isEmpty()) return 0.0;
            Object v = args.get(0);
            if (v instanceof Double) return v;
            if (v instanceof Long) return ((Long) v).doubleValue();
            return Double.parseDouble(String.valueOf(v));
        });
        registry.put("bool", args -> toBool(args.isEmpty() ? null : args.get(0)));
        registry.put("len", args -> (long) lengthOf(args.get(0)));
        registry.put("input", args -> {
            if (args.isEmpty()) return new Scanner(System.in).nextLine();
            System.out.print(args.get(0));
            return new Scanner(System.in).nextLine();
        });
        registry.put("random", args -> {
            // Placeholder; VM handles RAND_NUM directly via ThreadLocalRandom.
            return null;
        });
        registry.put("math", args -> null);  // VM handles SQRT directly
        registry.put("print", args -> {
            StringBuilder sb = new StringBuilder();
            for (Object a : args) sb.append(toStr(a));
            System.out.println(sb.toString());
            return null;
        });
        registry.put("list", args -> {
            if (args.isEmpty()) return new ArrayList<>();
            Object v = args.get(0);
            if (v instanceof List) return new ArrayList<>((List<?>) v);
            if (v instanceof String) {
                List<Object> out = new ArrayList<>();
                String s = (String) v;
                for (int i = 0; i < s.length(); i++) out.add(String.valueOf(s.charAt(i)));
                return out;
            }
            throw new RuntimeException("object is not iterable");
        });
        registry.put("dict", args -> new HashMap<>());
        registry.put("tuple", args -> new ArrayList<>(args));
    }

    // --- helpers used by Builtins and by VM opcode handlers ---

    public static String toStr(Object v) {
        if (v == null) return "null";
        if (v instanceof OriginInstance) return v.toString();
        return String.valueOf(v);
    }

    public static boolean toBool(Object v) {
        if (v == null) return false;
        if (v instanceof Boolean) return (Boolean) v;
        if (v instanceof Long) return ((Long) v) != 0;
        if (v instanceof Double) return ((Double) v) != 0.0;
        if (v instanceof String) return !((String) v).isEmpty();
        if (v instanceof List) return !((List<?>) v).isEmpty();
        if (v instanceof Map) return !((Map<?, ?>) v).isEmpty();
        return true;
    }

    public static int asInt(List<Object> args, int i) {
        Object v = args.get(i);
        if (v instanceof Long) return ((Long) v).intValue();
        if (v instanceof Double) return ((Double) v).intValue();
        if (v instanceof Boolean) return ((Boolean) v) ? 1 : 0;
        return Integer.parseInt(String.valueOf(v));
    }

    public static String asStr(List<Object> args, int i) {
        Object v = args.get(i);
        if (v == null) return "null";
        return String.valueOf(v);
    }

    public static long asLong(Object v) {
        if (v instanceof Long) return (Long) v;
        if (v instanceof Double) return ((Double) v).longValue();
        if (v instanceof Boolean) return ((Boolean) v) ? 1L : 0L;
        return Long.parseLong(String.valueOf(v));
    }

    public static double asDouble(Object v) {
        if (v instanceof Double) return (Double) v;
        if (v instanceof Long) return ((Long) v).doubleValue();
        if (v instanceof Boolean) return ((Boolean) v) ? 1.0 : 0.0;
        return Double.parseDouble(String.valueOf(v));
    }

    public static long lengthOf(Object v) {
        if (v instanceof String) return ((String) v).length();
        if (v instanceof List) return ((List<?>) v).size();
        if (v instanceof Map) return ((Map<?, ?>) v).size();
        throw new RuntimeException("object has no len(): " + (v == null ? "null" : v.getClass().getName()));
    }

    public static int randInt(long start, long end) {
        return ThreadLocalRandom.current().nextInt((int) start, (int) end + 1);
    }

    /** Wrapper for a file handle returned by built-in open(). */
    public static final class OpenFile {
        public final String path;
        public final String mode;
        public OpenFile(String path, String mode) { this.path = path; this.mode = mode; }
        public String readAll() {
            try {
                return new String(java.nio.file.Files.readAllBytes(java.nio.file.Paths.get(path)));
            } catch (java.io.IOException e) {
                throw new RuntimeException(e);
            }
        }
        public void writeAll(String content) {
            try (java.io.FileWriter w = new java.io.FileWriter(path)) {
                w.write(content);
            } catch (java.io.IOException e) { throw new RuntimeException(e); }
        }
        public void appendAll(String content) {
            try (java.io.FileWriter w = new java.io.FileWriter(path, true)) {
                w.write(content);
            } catch (java.io.IOException e) { throw new RuntimeException(e); }
        }
        @Override public String toString() { return "<open file '" + path + "' mode='" + mode + "'>"; }
    }

    private static OpenFile asOpenFile(List<Object> args, int i) {
        Object v = args.get(i);
        if (v instanceof OpenFile) return (OpenFile) v;
        return new OpenFile(asStr(args, i), "r");
    }
}
