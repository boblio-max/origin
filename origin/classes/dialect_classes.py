from .base_classes import *

class DialectNode(ASTNode):
    """Placeholder for a foreign/dialect source line.

    The parser emits this when the peeked line matches a mapping in
    ``origin.toml``. ``source`` is the actual dialect line the user wrote;
    the compiler expands ``origin_source`` (the real Origin code it maps to)
    into inline bytecode, so dialects stay compatible with the shared
    constant table and surrounding control flow.

    ``bytecode``/``constants`` support the legacy ``origin_bytecode.toml``
    precompiled form, which the SVM runs via the DIALECT opcode.
    """
    def __init__(self, source, origin_source=None, bytecode=None, constants=None):
        super().__init__()
        self.source = source
        self.origin_source = origin_source
        self.bytecode = list(bytecode) if bytecode is not None else None
        self.constants = list(constants) if constants is not None else None
    def __repr__(self):
        return f"DialectNode({self.source!r}, origin={self.origin_source!r}, bc={self.bytecode!r}, c={self.constants!r})"