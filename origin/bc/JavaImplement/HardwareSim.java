package origin.bc.JavaImplement;

import java.util.List;
import java.util.Map;

/**
 * Hardware-backed operations for SET_PIN, HARDWARE_CALL, SET_SERVO.
 * Mirrors the try-import-then-fallback pattern in svm.py:14-46.
 *
 * The Real backend is intentionally absent — Pi GPIO / smbus2 / adafruit_servokit
 * are not available on the JVM, and adding the JNI/pi4j dependencies is out of
 * scope for this port. Any call to setBackend(Backend.REAL) without the
 * corresponding JNI bridge installed will fall through to simulation.
 */
public final class HardwareSim {

    public enum Backend { SIM, REAL }

    private static Backend backend = Backend.SIM;

    public static void setBackend(Backend b) { backend = b; }
    public static Backend getBackend() { return backend; }

    public static void setPin(long pin, long state) {
        // svm.py:14-21 — only the simulation branch is reachable from the JVM.
        System.out.println("[SIM] Pin " + pin + " set to " + state);
    }

    public static Object i2cRead(long addr, long reg, long size) {
        // svm.py:23-29
        return 0L;
    }

    public static void i2cWrite(long addr, long reg, Object data) {
        // svm.py:31-38
        // no-op in simulation
    }

    public static void spiWrite(Object data) {
        // svm.py:40-41
        System.out.println("[SIM] SPI write: " + data);
    }

    public static Object spiRead(long count) {
        // svm.py:43-45
        System.out.println("[SIM] SPI read: " + count);
        return 0L;
    }

    /** SET_SERVO dispatcher (svm.py:427-438). Caches the kit globally. */
    public static void setServo(long channel, double angle) {
        // svm.py:432-438 — without adafruit_servokit available on the JVM,
        // we always take the simulation branch.
        System.out.println("[SIM] Servo " + channel + " angle set to " + angle);
    }

    /** HARDWARE_CALL dispatcher (svm.py:407-425). */
    public static Object hardwareCall(String namespace, String method, List<Object> args) {
        if ("i2c".equals(namespace) && "read".equals(method)) {
            long addr = Builtins.asLong(args.get(0));
            long reg  = Builtins.asLong(args.get(1));
            long size = args.size() > 2 ? Builtins.asLong(args.get(2)) : 1L;
            return i2cRead(addr, reg, size);
        }
        if ("i2c".equals(namespace) && "write".equals(method)) {
            long addr = Builtins.asLong(args.get(0));
            long reg  = Builtins.asLong(args.get(1));
            i2cWrite(addr, reg, args.get(2));
            return null;
        }
        if ("spi".equals(namespace) && "write".equals(method)) {
            spiWrite(args.get(0));
            return null;
        }
        if ("spi".equals(namespace) && "read".equals(method)) {
            return spiRead(Builtins.asLong(args.get(0)));
        }
        // svm.py:425 — unknown hardware call gets a generic SIM line
        StringBuilder sb = new StringBuilder("[SIM] ").append(namespace).append(".").append(method).append("(");
        for (int i = 0; i < args.size(); i++) {
            if (i > 0) sb.append(", ");
            sb.append(Builtins.toStr(args.get(i)));
        }
        sb.append(")");
        System.out.println(sb);
        return null;
    }

    /** EXEC_PY dispatcher (svm.py:461-463). Simulation: print only. */
    public static void execPy(Object code) {
        System.out.println("[SIM] exec(" + Builtins.toStr(code) + ")");
    }
}