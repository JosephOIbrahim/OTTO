"""Git watcher service — commit velocity and stuck detection.

Produces categorical signals about git activity without exposing
file names, commit messages, or diff content.

Signals produced::

    commit_velocity:     active / moderate / stalled
    uncommitted_changes: none / few / many
    stuck_signal:        none / possible / likely

Privacy boundary (Patent Claim #3)::

    RAW:         "Modified: src/auth.py", "Last commit: 3 hours ago"
    CATEGORICAL: commit_velocity=moderate, uncommitted_changes=few

Classification thresholds are fixed constants.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from otto_v3.services.base import CategoricalSignal


@dataclass(frozen=True)
class GitSnapshot:
    """Internal git repository state.

    Raw data — NEVER exposed through ``get_signals()``.

    Attributes:
        uncommitted_count: Number of modified/untracked files.
        hours_since_commit: Hours since last commit.
        commits_last_24h: Commit count in last 24 hours.
        is_repo: Whether we're in a git repo.
    """

    uncommitted_count: int
    hours_since_commit: float
    commits_last_24h: int
    is_repo: bool


def _classify_velocity(commits_24h: int, hours_since: float) -> str:
    """Classify commit velocity from recency and frequency."""
    if commits_24h >= 5 or hours_since < 1.0:
        return "active"
    if commits_24h >= 1 or hours_since < 4.0:
        return "moderate"
    return "stalled"


def _classify_uncommitted(count: int) -> str:
    """Classify uncommitted change count."""
    if count == 0:
        return "none"
    if count <= 5:
        return "few"
    return "many"


def _classify_stuck(
    hours_since: float,
    uncommitted: int,
    commits_24h: int,
) -> str:
    """Classify stuck signal from multiple indicators.

    Stuck = many uncommitted + long since commit + low velocity.
    """
    if hours_since > 4.0 and uncommitted > 5 and commits_24h == 0:
        return "likely"
    if hours_since > 2.0 and uncommitted > 3:
        return "possible"
    return "none"


class GitWatcher:
    """Git repository watcher — commit velocity and stuck detection.

    Monitors git state and produces categorical signals about
    development activity without exposing any source content.

    Args:
        snapshot_provider: Callable returning a GitSnapshot.
            If ``None``, uses subprocess ``git`` commands.
        repo_path: Path to the git repository.  Defaults to cwd.
    """

    def __init__(
        self,
        snapshot_provider: Callable[[], GitSnapshot | None] | None = None,
        repo_path: str | None = None,
    ) -> None:
        self._provider = snapshot_provider or (
            lambda: _default_git_snapshot(repo_path)
        )
        self._running = False

    @property
    def name(self) -> str:
        return "git_watcher"

    @property
    def tier(self) -> int:
        return 1

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def get_signals(self) -> list[CategoricalSignal]:
        """Get git-based categorical signals.

        Privacy: Only velocity/count categories leave.
        No file names, paths, or commit content.

        Signals returned in sorted (category, value) order.
        """
        snapshot = self._provider()
        if snapshot is None or not snapshot.is_repo:
            return []

        now = datetime.now(timezone.utc)

        signals = [
            CategoricalSignal(
                category="commit_velocity",
                value=_classify_velocity(
                    snapshot.commits_last_24h,
                    snapshot.hours_since_commit,
                ),
                confidence=0.85,
                source=self.name,
                timestamp=now,
            ),
            CategoricalSignal(
                category="stuck_signal",
                value=_classify_stuck(
                    snapshot.hours_since_commit,
                    snapshot.uncommitted_count,
                    snapshot.commits_last_24h,
                ),
                confidence=0.7,
                source=self.name,
                timestamp=now,
            ),
            CategoricalSignal(
                category="uncommitted_changes",
                value=_classify_uncommitted(snapshot.uncommitted_count),
                confidence=0.95,
                source=self.name,
                timestamp=now,
            ),
        ]

        return sorted(signals, key=lambda s: (s.category, s.value))


def _default_git_snapshot(repo_path: str | None = None) -> GitSnapshot | None:
    """Build a GitSnapshot using subprocess git commands.

    Returns ``None`` if not in a git repo or git is not available.
    """
    kwargs: dict = {}
    if repo_path:
        kwargs["cwd"] = repo_path

    try:
        # Check if we're in a repo
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, timeout=5,
            **kwargs,
        )
        if result.returncode != 0:
            return GitSnapshot(
                uncommitted_count=0, hours_since_commit=0.0,
                commits_last_24h=0, is_repo=False,
            )

        # Count uncommitted changes (porcelain for machine-readable)
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=5,
            **kwargs,
        )
        uncommitted = (
            len([l for l in result.stdout.strip().split("\n") if l.strip()])
            if result.stdout.strip()
            else 0
        )

        # Hours since last commit
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ct"],
            capture_output=True, text=True, timeout=5,
            **kwargs,
        )
        if result.stdout.strip():
            last_ts = int(result.stdout.strip())
            last_commit = datetime.fromtimestamp(last_ts, tz=timezone.utc)
            hours_since = (
                (datetime.now(timezone.utc) - last_commit).total_seconds()
                / 3600.0
            )
        else:
            hours_since = float("inf")

        # Commits in last 24 hours
        result = subprocess.run(
            ["git", "log", "--oneline", "--since=24.hours"],
            capture_output=True, text=True, timeout=5,
            **kwargs,
        )
        commits_24h = (
            len([l for l in result.stdout.strip().split("\n") if l.strip()])
            if result.stdout.strip()
            else 0
        )

        return GitSnapshot(
            uncommitted_count=uncommitted,
            hours_since_commit=hours_since,
            commits_last_24h=commits_24h,
            is_repo=True,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
