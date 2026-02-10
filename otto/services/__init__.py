"""Ambient intelligence services — OS-level signal detection.

Services observe the user's computing environment and produce
categorical signals that feed into PRISM and NEXUS.  The privacy
boundary (Patent Claim #3) is enforced at the service level:
raw data NEVER leaves a service.

Tier 1 (core):
    ClockService       — Time of day, day type, time pressure
    ProcessMonitor     — Active app, context switches, load
    GitWatcher         — Commit velocity, stuck detection
    FileSystemWatcher  — Activity level, file churn

Tier 2 (enrichment): Calendar, Discord (future)
Tier 3 (advanced): Proactive Engine (future)
"""

from otto.services.base import CategoricalSignal, OTTOService, ServiceRegistry
from otto.services.clock import ClockService
from otto.services.filesystem import FileSystemSnapshot, FileSystemWatcher
from otto.services.git import GitSnapshot, GitWatcher
from otto.services.platform import PlatformInfo, detect_platform
from otto.services.process import ProcessMonitor, ProcessSnapshot

__all__ = [
    "CategoricalSignal",
    "ClockService",
    "FileSystemSnapshot",
    "FileSystemWatcher",
    "GitSnapshot",
    "GitWatcher",
    "OTTOService",
    "PlatformInfo",
    "ProcessMonitor",
    "ProcessSnapshot",
    "ServiceRegistry",
    "detect_platform",
]
