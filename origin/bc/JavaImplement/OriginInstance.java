package origin.bc.JavaImplement;

import java.util.HashMap;
import java.util.Map;

public final class OriginInstance {
    public final OriginClass originClass;
    public final Map<String, Object> attrs;

    public OriginInstance(OriginClass originClass) {
        this.originClass = originClass;
        this.attrs = new HashMap<>();
    }

    @Override
    public String toString() {
        return "<" + originClass.name + " instance>";
    }
}
