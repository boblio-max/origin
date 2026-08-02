package origin.bc.JavaImplement;

import java.util.List;
import java.util.Map;

public final class OriginClass {
    public final String name;
    public final List<String> fields;
    public final Map<String, Integer> methods;

    public OriginClass(String name, List<String> fields, Map<String, Integer> methods) {
        this.name = name;
        this.fields = fields;
        this.methods = methods;
    }
}