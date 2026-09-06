class OriginClass:
    def __init__(self, name, fields, methods):
        self.name = name
        self.fields = fields
        self.methods = methods

class OriginInstance:
    def __init__(self, origin_class):
        self.origin_class = origin_class
        self.attrs = {}
        
    def __repr__(self):
        return f"<{self.origin_class.name} instance>"

class BoundMethod:
    def __init__(self, instance, func_pc):
        self.instance = instance
        self.func_pc = func_pc


