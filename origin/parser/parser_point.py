"""Aggregate parser: combines mixins into final Parser."""
from .base import BaseParser
from .expr import ExprMixin
from .stmt import StmtMixin
from .block import BlockMixin


class Parser(BaseParser, ExprMixin, StmtMixin, BlockMixin):
    """Final parser (same behaviour as parser.py Parser)."""
    pass
