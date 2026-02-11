"""Specialist modes for OTTO's cognitive architecture.

Each mode implements the Mode protocol defined in base.py.
"""

from .base import Mode, ModeResponse
from .executor import ExecutorMode
from .protector import ProtectorMode
from .restorer import RestorerMode

__all__ = [
    "Mode",
    "ModeResponse",
    "ExecutorMode",
    "ProtectorMode",
    "RestorerMode",
]
