from optimizer import Optimizer

ir = [
    ('CONST_INT', 't1', 5),
    ('CONST_INT', 't2', 6),
    ('ADD', 't3', 't1', 't2'),
    ('PRINT', 't3')
]

op = Optimizer(ir)
print(op.optimize())

