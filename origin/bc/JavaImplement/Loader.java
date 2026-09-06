package origin.bc.JavaImplement;

import java.io.DataInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Loads an .obc bytecode file into (bytecode, constants[]) for the VM.
 *
 * Format (all big-endian):
 *   magic        : 4 bytes  "OBC1"
 *   version      : 1 byte   (0x01)
 *   const_count  : 4 bytes int32
 *   constants    : repeated [typeTag(1) + payload]
 *   code_len     : 4 bytes int32
 *   bytecode     : code_len bytes
 *
 * Type tags:
 *   0 = LONG       payload  = 8 bytes signed
 *   1 = DOUBLE     payload  = 8 bytes IEEE-754
 *   2 = BOOLEAN    payload  = 1 byte
 *   3 = STRING     payload  = int32 len + utf8 bytes
 *   4 = NULL       payload  = 0 bytes
 *   5 = INT32      payload  = 4 bytes signed
 *
 * Origin's bytecode emitter emits integer addresses as ints and small
 * constants as ints; everything else gets LONG. STRING carries names
 * for LOAD_VAR / STORE_VAR and the (ns, method) pair for HARDWARE_CALL
 * (encoded as STRING, STRING).
 */
public final class Loader {

    public static final class Loaded {
        public final byte[] bytecode;
        public final Object[] constants;
        public Loaded(byte[] bytecode, Object[] constants) {
            this.bytecode = bytecode;
            this.constants = constants;
        }
    }

    public static Loaded load(InputStream in) throws IOException {
        DataInputStream din = new DataInputStream(in);
        byte[] magic = new byte[4];
        din.readFully(magic);
        if (!new String(magic, StandardCharsets.US_ASCII).equals("OBC1")) {
            throw new IOException("bad magic: " + new String(magic, StandardCharsets.US_ASCII));
        }
        int version = din.readByte() & 0xFF;
        if (version != 1) throw new IOException("unsupported version: " + version);

        int constCount = din.readInt();
        Object[] consts = new Object[constCount];
        for (int i = 0; i < constCount; i++) {
            consts[i] = readConst(din);
        }

        int codeLen = din.readInt();
        byte[] code = new byte[codeLen];
        din.readFully(code);
        return new Loaded(code, consts);
    }

    private static Object readConst(DataInputStream din) throws IOException {
        int tag = din.readByte() & 0xFF;
        switch (tag) {
            case 0: return din.readLong();
            case 1: return din.readDouble();
            case 2: return din.readByte() != 0;
            case 3: {
                int len = din.readInt();
                byte[] b = new byte[len];
                din.readFully(b);
                return new String(b, StandardCharsets.UTF_8);
            }
            case 4: return null;
            case 5: return (long) din.readInt();
            case 6: {
                // TUPLE â€” emitted by dump_obc.py for both tuple/list literals
                // and for the flat [key, value, ...] representation of dicts
                // used by MAKE_CLASS's methods table.
                int n = din.readInt();
                List<Object> tuple = new ArrayList<>(n);
                for (int i = 0; i < n; i++) tuple.add(readConst(din));
                return tuple;
            }
            default: throw new IOException("bad const tag: " + tag);
        }
    }

    /** Convenience: load from a file path. */
    public static Loaded loadFromFile(String path) throws IOException {
        try (InputStream in = new java.io.FileInputStream(path)) {
            return load(in);
        }
    }
}
