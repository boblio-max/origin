package origin.bc.JavaImplement;

import java.io.IOException;

/**
 * CLI entry point. Usage:
 *   java -cp . origin.bc.JavaImplement.Main program.obc
 */
public final class Main {

    public static void main(String[] args) {
        if (args.length < 1) {
            System.err.println("usage: java -cp . origin.bc.JavaImplement.Main <program.obc>");
            System.exit(2);
        }
        String path = args[0];

        if (args.length >= 2 && "--hw=real".equals(args[1])) {
            HardwareSim.setBackend(HardwareSim.Backend.REAL);
        }

        try {
            Loader.Loaded prog = Loader.loadFromFile(path);
            svm vm = new svm(prog.bytecode, prog.constants);
            vm.run();
        } catch (IOException e) {
            System.err.println("load error: " + e.getMessage());
            System.exit(1);
        } catch (RuntimeException e) {
            System.err.println("runtime error: " + e.getMessage());
            System.exit(1);
        }
    }
}