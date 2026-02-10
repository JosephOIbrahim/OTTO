"""Platform detection and capability probing.

Detects the current platform and reports which optional service
dependencies are available.  Used by the service registry to
decide which services to instantiate.

Handles:
    - Windows (native)
    - macOS
    - Linux (including WSL2 detection)
"""

from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformInfo:
    """Detected platform capabilities.

    Frozen — platform doesn't change mid-session.

    Attributes:
        os: Operating system (``"windows"``, ``"macos"``, ``"linux"``).
        is_wsl: Whether running under WSL2.
        has_psutil: Whether ``psutil`` is importable.
        has_watchdog: Whether ``watchdog`` is importable.
        has_git: Whether ``git`` CLI is available.
    """

    os: str
    is_wsl: bool
    has_psutil: bool
    has_watchdog: bool
    has_git: bool


def detect_platform() -> PlatformInfo:
    """Detect the current platform and available dependencies.

    Returns:
        PlatformInfo with detected capabilities.
    """
    # Detect OS
    if sys.platform == "win32":
        os_name = "windows"
    elif sys.platform == "darwin":
        os_name = "macos"
    else:
        os_name = "linux"

    # Detect WSL (only relevant on Linux)
    is_wsl = False
    if os_name == "linux":
        try:
            with open("/proc/version", "r") as f:
                if "microsoft" in f.read().lower():
                    is_wsl = True
        except (FileNotFoundError, PermissionError):
            pass

    return PlatformInfo(
        os=os_name,
        is_wsl=is_wsl,
        has_psutil=_check_import("psutil"),
        has_watchdog=_check_import("watchdog"),
        has_git=_check_git(),
    )


def _check_import(module_name: str) -> bool:
    """Check if a module is importable without side effects."""
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


def _check_git() -> bool:
    """Check if the git CLI is available."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return False
