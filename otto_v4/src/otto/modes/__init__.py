"""Specialist modes for OTTO's cognitive architecture.

Each mode implements the Mode protocol defined in base.py.
All 7 modes: Protector, Decomposer, Restorer, Redirector,
Acknowledger, Guide, Executor.
"""

from .acknowledger import AcknowledgerMode
from .base import Mode, ModeResponse
from .decomposer import DecomposerMode
from .executor import ExecutorMode
from .guide import GuideMode
from .protector import ProtectorMode
from .redirector import RedirectorMode
from .restorer import RestorerMode

__all__ = [
    "AcknowledgerMode",
    "DecomposerMode",
    "GuideMode",
    "Mode",
    "ModeResponse",
    "ExecutorMode",
    "ProtectorMode",
    "RedirectorMode",
    "RestorerMode",
]
