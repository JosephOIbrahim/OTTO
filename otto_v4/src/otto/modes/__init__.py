"""Specialist modes for OTTO's cognitive architecture.

Each mode implements the Mode protocol defined in base.py.
4 modes: Executor, Protector, Restorer, Decomposer.
"""

from .base import Mode, ModeResponse
from .decomposer import DecomposerMode
from .executor import ExecutorMode
from .protector import ProtectorMode
from .restorer import RestorerMode

__all__ = [
    "DecomposerMode",
    "Mode",
    "ModeResponse",
    "ExecutorMode",
    "ProtectorMode",
    "RestorerMode",
]
