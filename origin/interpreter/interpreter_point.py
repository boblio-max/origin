"""Aggregate interpreter: combines mixins into final Interpreter."""
from .base import BaseInterpreter
from .gen_expr import ExprMixin
from .gen_control import ControlMixin
from .gen_func import FuncMixin
from .gen_data import DataMixin
from .gen_sys import SysMixin


class Interpreter(BaseInterpreter, ExprMixin, ControlMixin, FuncMixin, DataMixin, SysMixin):
    """Final interpreter (same behaviour as origin-legacy/interpreter.py)."""
    pass
