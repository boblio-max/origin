package origin.bc.JavaImplement;

public final class BoundMethod {
    public final OriginInstance instance;
    public final int funcPc;

    public BoundMethod(OriginInstance instance, int funcPc) {
        this.instance = instance;
        this.funcPc = funcPc;
    }
}