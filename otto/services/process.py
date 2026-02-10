"""Process monitor service — active app awareness.

Produces categorical signals about the user's current computing
context by observing active processes.

Signals produced::

    app_context:       coding / browsing / communication / terminal / media / other
    context_switches:  low / medium / high
    process_load:      light / moderate / heavy

Privacy boundary (Patent Claim #3)::

    RAW:         "chrome.exe", "Code.exe", 147 processes
    CATEGORICAL: app_context=coding, process_load=moderate

Process names and counts NEVER leave this service.

[He2025]: App classification rules sorted by category.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from otto.services.base import CategoricalSignal


# ── App classification rules ──────────────────────────────────
# [He2025]: Sorted by category at module load.

_APP_CATEGORIES: tuple[tuple[str, tuple[str, ...]], ...] = tuple(sorted([
    ("browsing", (
        "chrome", "firefox", "safari", "edge", "brave", "opera",
    )),
    ("coding", (
        "code", "vim", "nvim", "neovim", "pycharm", "intellij",
        "cursor", "zed", "sublime", "emacs",
    )),
    ("communication", (
        "discord", "slack", "teams", "zoom", "telegram", "signal",
        "whatsapp",
    )),
    ("media", ("spotify", "vlc", "mpv", "obs")),
    ("terminal", (
        "terminal", "iterm", "wezterm", "alacritty", "powershell",
        "cmd", "windowsterminal",
    )),
], key=lambda x: x[0]))


def _classify_process(process_name: str) -> str:
    """Classify a process name into an app category.

    [He2025]: Categories iterated in sorted order.
    First match wins (categories are non-overlapping).
    """
    name_lower = process_name.lower()
    # Strip common suffixes
    for suffix in (".exe", ".app", ".bin"):
        if name_lower.endswith(suffix):
            name_lower = name_lower[: -len(suffix)]

    for category, keywords in _APP_CATEGORIES:
        for keyword in keywords:
            if keyword in name_lower:
                return category
    return "other"


def _classify_load(process_count: int) -> str:
    """Classify process count into load category."""
    if process_count > 200:
        return "heavy"
    if process_count > 50:
        return "moderate"
    return "light"


def _classify_context_switches(switch_count: int) -> str:
    """Classify context switch frequency."""
    if switch_count > 10:
        return "high"
    if switch_count > 3:
        return "medium"
    return "low"


@dataclass
class ProcessSnapshot:
    """Internal process state snapshot.

    This is the RAW representation — it never leaves the service.
    ``get_signals()`` transforms this into CategoricalSignals.
    """

    active_process: str  # Name of foreground process
    process_count: int  # Total running processes
    recent_switches: int  # App switches in tracking window


class ProcessMonitor:
    """Process monitor — active app awareness.

    Observes running processes and produces categorical signals
    about the computing context without exposing process details.

    Uses an injected snapshot provider for testability.  When no
    provider is given, attempts to use psutil (graceful fallback
    to empty signals if unavailable).

    Args:
        snapshot_provider: Callable returning a ProcessSnapshot.
            If ``None``, attempts psutil; falls back to no-op.
    """

    def __init__(
        self,
        snapshot_provider: Callable[[], ProcessSnapshot | None] | None = None,
    ) -> None:
        self._provider = snapshot_provider or _default_provider
        self._running = False
        self._switch_count = 0
        self._last_process: str | None = None

    @property
    def name(self) -> str:
        return "process_monitor"

    @property
    def tier(self) -> int:
        return 1

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        self._running = True
        self._switch_count = 0
        self._last_process = None

    def stop(self) -> None:
        self._running = False

    def get_signals(self) -> list[CategoricalSignal]:
        """Get process-based categorical signals.

        Privacy boundary enforced here: process names become
        categories, counts become load levels.

        [He2025]: Signals returned in sorted (category, value) order.
        """
        snapshot = self._provider()
        if snapshot is None:
            return []

        now = datetime.now(timezone.utc)

        # Track context switches internally
        if (
            self._last_process is not None
            and snapshot.active_process != self._last_process
        ):
            self._switch_count += 1
        self._last_process = snapshot.active_process

        signals = [
            CategoricalSignal(
                category="app_context",
                value=_classify_process(snapshot.active_process),
                confidence=0.9,
                source=self.name,
                timestamp=now,
            ),
            CategoricalSignal(
                category="context_switches",
                value=_classify_context_switches(
                    snapshot.recent_switches + self._switch_count,
                ),
                confidence=0.8,
                source=self.name,
                timestamp=now,
            ),
            CategoricalSignal(
                category="process_load",
                value=_classify_load(snapshot.process_count),
                confidence=0.95,
                source=self.name,
                timestamp=now,
            ),
        ]

        return sorted(signals, key=lambda s: (s.category, s.value))


def _default_provider() -> ProcessSnapshot | None:
    """Default snapshot provider using psutil.

    Returns ``None`` if psutil is not installed.
    """
    try:
        import psutil
    except ImportError:
        return None

    try:
        processes = list(psutil.process_iter(["name"]))
        process_count = len(processes)

        # Attempt foreground window detection (Windows)
        active = "unknown"
        try:
            import sys

            if sys.platform == "win32":
                import ctypes

                hwnd = ctypes.windll.user32.GetForegroundWindow()
                pid = ctypes.c_ulong()
                ctypes.windll.user32.GetWindowThreadProcessId(
                    hwnd, ctypes.byref(pid),
                )
                try:
                    proc = psutil.Process(pid.value)
                    active = proc.name()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except (ImportError, AttributeError, OSError):
            pass

        return ProcessSnapshot(
            active_process=active,
            process_count=process_count,
            recent_switches=0,
        )
    except Exception:
        return None
