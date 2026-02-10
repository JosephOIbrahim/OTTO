"""Tests for ambient intelligence services (Days 10-12).

Tests cover:
    - CategoricalSignal: frozen, fields, privacy semantics
    - ServiceRegistry: register, lifecycle, signal collection
    - ClockService: time period, day type, time pressure
    - ProcessMonitor: app classification, load, context switches
    - GitWatcher: velocity, uncommitted, stuck detection
    - FileSystemWatcher: activity level, file churn
    - PlatformInfo: detection basics
    - Protocol compliance: all services satisfy OTTOService
    - Privacy boundary: no raw data leaks in any signal
    - Determinism: same input → same signals (100×)
    - Import completeness

All tests use injected providers — no real psutil/watchdog/git calls.
"""

from __future__ import annotations

import pytest
from datetime import datetime, time, timezone, timedelta

from otto.services.base import CategoricalSignal, OTTOService, ServiceRegistry
from otto.services.clock import (
    ClockService,
    _classify_time_period,
    _classify_day_type,
    _classify_time_pressure,
)
from otto.services.process import (
    ProcessMonitor,
    ProcessSnapshot,
    _classify_process,
    _classify_load,
    _classify_context_switches,
)
from otto.services.git import (
    GitWatcher,
    GitSnapshot,
    _classify_velocity,
    _classify_uncommitted,
    _classify_stuck,
)
from otto.services.filesystem import (
    FileSystemWatcher,
    FileSystemSnapshot,
    _classify_activity,
    _classify_churn,
)
from otto.services.platform import PlatformInfo, detect_platform


# ═══════════════════════════════════════════════════════════════════
# CategoricalSignal
# ═══════════════════════════════════════════════════════════════════


class TestCategoricalSignal:
    """Verify the privacy-safe signal type."""

    def test_frozen(self) -> None:
        sig = CategoricalSignal(
            category="test", value="val",
            confidence=0.9, source="test_svc",
        )
        with pytest.raises(AttributeError):
            sig.category = "changed"  # type: ignore[misc]

    def test_fields(self) -> None:
        now = datetime.now(timezone.utc)
        sig = CategoricalSignal(
            category="energy", value="declining",
            confidence=0.8, source="typing_cadence",
            timestamp=now,
        )
        assert sig.category == "energy"
        assert sig.value == "declining"
        assert sig.confidence == 0.8
        assert sig.source == "typing_cadence"
        assert sig.timestamp == now

    def test_default_timestamp(self) -> None:
        sig = CategoricalSignal(
            category="c", value="v",
            confidence=1.0, source="s",
        )
        assert sig.timestamp is not None
        assert sig.timestamp.tzinfo == timezone.utc

    def test_no_raw_data_fields(self) -> None:
        """CategoricalSignal has only category/value — no raw data."""
        fields = {f.name for f in sig.__dataclass_fields__.values()}
        # These are the ONLY permitted fields
        assert fields == {
            "category", "value", "confidence", "source", "timestamp",
        }


# Hack for accessing dataclass fields in the test above
sig = CategoricalSignal(
    category="c", value="v", confidence=1.0, source="s",
)


# ═══════════════════════════════════════════════════════════════════
# ServiceRegistry
# ═══════════════════════════════════════════════════════════════════


class TestServiceRegistry:
    """Verify registry lifecycle and signal collection."""

    def _make_clock(self, hour: int = 10) -> ClockService:
        dt = datetime(2026, 2, 10, hour, 30, tzinfo=timezone.utc)
        return ClockService(clock=lambda: dt)

    def test_register_and_count(self) -> None:
        reg = ServiceRegistry()
        reg.register(self._make_clock())
        assert reg.count() == 1

    def test_start_all(self) -> None:
        reg = ServiceRegistry()
        svc = self._make_clock()
        reg.register(svc)
        assert not svc.running
        reg.start_all()
        assert svc.running

    def test_stop_all(self) -> None:
        reg = ServiceRegistry()
        svc = self._make_clock()
        reg.register(svc)
        reg.start_all()
        reg.stop_all()
        assert not svc.running

    def test_get_all_signals_only_running(self) -> None:
        reg = ServiceRegistry()
        svc = self._make_clock()
        reg.register(svc)
        # Not started → no signals
        assert reg.get_all_signals() == []
        reg.start_all()
        signals = reg.get_all_signals()
        assert len(signals) > 0

    def test_signals_sorted_by_source_category_value(self) -> None:
        reg = ServiceRegistry()
        reg.register(self._make_clock())
        provider = lambda: ProcessSnapshot("code.exe", 100, 0)
        reg.register(ProcessMonitor(snapshot_provider=provider))
        reg.start_all()
        signals = reg.get_all_signals()
        keys = [(s.source, s.category, s.value) for s in signals]
        assert keys == sorted(keys)

    def test_services_sorted_by_name(self) -> None:
        reg = ServiceRegistry()
        reg.register(ProcessMonitor(snapshot_provider=lambda: None))
        reg.register(self._make_clock())
        names = [s.name for s in reg.services]
        assert names == sorted(names)

    def test_multiple_services(self) -> None:
        reg = ServiceRegistry()
        reg.register(self._make_clock())
        provider = lambda: ProcessSnapshot("code.exe", 100, 0)
        reg.register(ProcessMonitor(snapshot_provider=provider))
        assert reg.count() == 2


# ═══════════════════════════════════════════════════════════════════
# ClockService — classification functions
# ═══════════════════════════════════════════════════════════════════


class TestClockClassification:
    """Verify time classification functions."""

    def test_night_early(self) -> None:
        assert _classify_time_period(time(2, 0)) == "night"

    def test_dawn(self) -> None:
        assert _classify_time_period(time(5, 30)) == "dawn"

    def test_morning(self) -> None:
        assert _classify_time_period(time(9, 0)) == "morning"

    def test_afternoon(self) -> None:
        assert _classify_time_period(time(14, 0)) == "afternoon"

    def test_evening(self) -> None:
        assert _classify_time_period(time(18, 0)) == "evening"

    def test_night_late(self) -> None:
        assert _classify_time_period(time(22, 0)) == "night"

    def test_weekday(self) -> None:
        assert _classify_day_type(0) == "weekday"  # Monday
        assert _classify_day_type(4) == "weekday"  # Friday

    def test_weekend(self) -> None:
        assert _classify_day_type(5) == "weekend"  # Saturday
        assert _classify_day_type(6) == "weekend"  # Sunday

    def test_no_pressure(self) -> None:
        assert _classify_time_pressure(time(10, 0)) == "none"

    def test_approaching_eod(self) -> None:
        assert _classify_time_pressure(time(17, 0)) == "approaching_eod"

    def test_late_night(self) -> None:
        assert _classify_time_pressure(time(23, 30)) == "late_night"


# ═══════════════════════════════════════════════════════════════════
# ClockService — full service
# ═══════════════════════════════════════════════════════════════════


class TestClockService:
    """Verify ClockService protocol compliance and signal production."""

    def test_name(self) -> None:
        svc = ClockService()
        assert svc.name == "clock"

    def test_tier(self) -> None:
        assert ClockService().tier == 1

    def test_start_stop(self) -> None:
        svc = ClockService()
        assert not svc.running
        svc.start()
        assert svc.running
        svc.stop()
        assert not svc.running

    def test_morning_weekday_signals(self) -> None:
        # Monday 10:30 UTC
        dt = datetime(2026, 2, 9, 10, 30, tzinfo=timezone.utc)
        svc = ClockService(clock=lambda: dt)
        signals = svc.get_signals()
        categories = {s.category: s.value for s in signals}
        assert categories["time_period"] == "morning"
        assert categories["day_type"] == "weekday"
        assert categories["time_pressure"] == "none"

    def test_evening_weekend_signals(self) -> None:
        # Saturday 18:00 UTC
        dt = datetime(2026, 2, 14, 18, 0, tzinfo=timezone.utc)
        svc = ClockService(clock=lambda: dt)
        signals = svc.get_signals()
        categories = {s.category: s.value for s in signals}
        assert categories["time_period"] == "evening"
        assert categories["day_type"] == "weekend"
        assert categories["time_pressure"] == "approaching_eod"

    def test_signals_sorted(self) -> None:
        dt = datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)
        svc = ClockService(clock=lambda: dt)
        signals = svc.get_signals()
        keys = [(s.category, s.value) for s in signals]
        assert keys == sorted(keys)

    def test_all_signals_have_clock_source(self) -> None:
        dt = datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)
        svc = ClockService(clock=lambda: dt)
        for signal in svc.get_signals():
            assert signal.source == "clock"

    def test_confidence_is_1(self) -> None:
        """Time is deterministic — always 100% confidence."""
        dt = datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)
        svc = ClockService(clock=lambda: dt)
        for signal in svc.get_signals():
            assert signal.confidence == 1.0


# ═══════════════════════════════════════════════════════════════════
# ProcessMonitor — classification functions
# ═══════════════════════════════════════════════════════════════════


class TestProcessClassification:
    """Verify process classification functions."""

    def test_coding_app(self) -> None:
        assert _classify_process("Code.exe") == "coding"

    def test_browser_app(self) -> None:
        assert _classify_process("chrome.exe") == "browsing"

    def test_communication_app(self) -> None:
        assert _classify_process("Discord.exe") == "communication"

    def test_terminal_app(self) -> None:
        assert _classify_process("WindowsTerminal.exe") == "terminal"

    def test_media_app(self) -> None:
        assert _classify_process("Spotify.exe") == "media"

    def test_unknown_app(self) -> None:
        assert _classify_process("myapp.exe") == "other"

    def test_case_insensitive(self) -> None:
        assert _classify_process("CHROME.EXE") == "browsing"

    def test_load_light(self) -> None:
        assert _classify_load(30) == "light"

    def test_load_moderate(self) -> None:
        assert _classify_load(100) == "moderate"

    def test_load_heavy(self) -> None:
        assert _classify_load(250) == "heavy"

    def test_switches_low(self) -> None:
        assert _classify_context_switches(2) == "low"

    def test_switches_medium(self) -> None:
        assert _classify_context_switches(5) == "medium"

    def test_switches_high(self) -> None:
        assert _classify_context_switches(15) == "high"


# ═══════════════════════════════════════════════════════════════════
# ProcessMonitor — full service
# ═══════════════════════════════════════════════════════════════════


class TestProcessMonitor:
    """Verify ProcessMonitor service behavior."""

    def _make_provider(
        self,
        process: str = "code.exe",
        count: int = 100,
        switches: int = 0,
    ) -> ProcessSnapshot:
        return ProcessSnapshot(
            active_process=process,
            process_count=count,
            recent_switches=switches,
        )

    def test_name(self) -> None:
        svc = ProcessMonitor(snapshot_provider=lambda: None)
        assert svc.name == "process_monitor"

    def test_tier(self) -> None:
        svc = ProcessMonitor(snapshot_provider=lambda: None)
        assert svc.tier == 1

    def test_coding_context(self) -> None:
        snap = self._make_provider("Code.exe", 100, 0)
        svc = ProcessMonitor(snapshot_provider=lambda: snap)
        signals = svc.get_signals()
        categories = {s.category: s.value for s in signals}
        assert categories["app_context"] == "coding"
        assert categories["process_load"] == "moderate"

    def test_no_snapshot_returns_empty(self) -> None:
        svc = ProcessMonitor(snapshot_provider=lambda: None)
        assert svc.get_signals() == []

    def test_context_switch_tracking(self) -> None:
        """Switching between different apps increments switch count."""
        call_count = [0]
        apps = ["code.exe", "chrome.exe", "discord.exe", "code.exe"]

        def provider() -> ProcessSnapshot:
            idx = min(call_count[0], len(apps) - 1)
            call_count[0] += 1
            return ProcessSnapshot(
                active_process=apps[idx],
                process_count=100,
                recent_switches=0,
            )

        svc = ProcessMonitor(snapshot_provider=provider)
        svc.start()
        svc.get_signals()  # code
        svc.get_signals()  # chrome (+1 switch)
        svc.get_signals()  # discord (+1 switch)
        signals = svc.get_signals()  # code (+1 switch = 3 total)
        categories = {s.category: s.value for s in signals}
        # 3 switches → "low" (threshold is >3 for medium)
        assert categories["context_switches"] == "low"

    def test_signals_sorted(self) -> None:
        snap = self._make_provider()
        svc = ProcessMonitor(snapshot_provider=lambda: snap)
        signals = svc.get_signals()
        keys = [(s.category, s.value) for s in signals]
        assert keys == sorted(keys)

    def test_privacy_no_process_names_in_signals(self) -> None:
        """Constitutional: no raw process names in signal values."""
        snap = self._make_provider("SuperSecretApp.exe", 150, 5)
        svc = ProcessMonitor(snapshot_provider=lambda: snap)
        for signal in svc.get_signals():
            assert "SuperSecretApp" not in signal.value
            assert "SuperSecretApp" not in signal.category


# ═══════════════════════════════════════════════════════════════════
# GitWatcher — classification functions
# ═══════════════════════════════════════════════════════════════════


class TestGitClassification:
    """Verify git classification functions."""

    def test_velocity_active(self) -> None:
        assert _classify_velocity(5, 0.5) == "active"

    def test_velocity_moderate(self) -> None:
        assert _classify_velocity(2, 3.0) == "moderate"

    def test_velocity_stalled(self) -> None:
        assert _classify_velocity(0, 10.0) == "stalled"

    def test_uncommitted_none(self) -> None:
        assert _classify_uncommitted(0) == "none"

    def test_uncommitted_few(self) -> None:
        assert _classify_uncommitted(3) == "few"

    def test_uncommitted_many(self) -> None:
        assert _classify_uncommitted(10) == "many"

    def test_stuck_none(self) -> None:
        assert _classify_stuck(1.0, 2, 3) == "none"

    def test_stuck_possible(self) -> None:
        assert _classify_stuck(3.0, 4, 1) == "possible"

    def test_stuck_likely(self) -> None:
        assert _classify_stuck(5.0, 8, 0) == "likely"


# ═══════════════════════════════════════════════════════════════════
# GitWatcher — full service
# ═══════════════════════════════════════════════════════════════════


class TestGitWatcher:
    """Verify GitWatcher service behavior."""

    def _make_snapshot(
        self,
        uncommitted: int = 2,
        hours_since: float = 1.0,
        commits_24h: int = 3,
        is_repo: bool = True,
    ) -> GitSnapshot:
        return GitSnapshot(
            uncommitted_count=uncommitted,
            hours_since_commit=hours_since,
            commits_last_24h=commits_24h,
            is_repo=is_repo,
        )

    def test_name(self) -> None:
        svc = GitWatcher(snapshot_provider=lambda: None)
        assert svc.name == "git_watcher"

    def test_tier(self) -> None:
        svc = GitWatcher(snapshot_provider=lambda: None)
        assert svc.tier == 1

    def test_active_repo(self) -> None:
        snap = self._make_snapshot(2, 0.5, 5)
        svc = GitWatcher(snapshot_provider=lambda: snap)
        signals = svc.get_signals()
        categories = {s.category: s.value for s in signals}
        assert categories["commit_velocity"] == "active"
        assert categories["uncommitted_changes"] == "few"
        assert categories["stuck_signal"] == "none"

    def test_stalled_repo(self) -> None:
        snap = self._make_snapshot(8, 6.0, 0)
        svc = GitWatcher(snapshot_provider=lambda: snap)
        signals = svc.get_signals()
        categories = {s.category: s.value for s in signals}
        assert categories["commit_velocity"] == "stalled"
        assert categories["uncommitted_changes"] == "many"
        assert categories["stuck_signal"] == "likely"

    def test_not_a_repo(self) -> None:
        snap = self._make_snapshot(is_repo=False)
        svc = GitWatcher(snapshot_provider=lambda: snap)
        assert svc.get_signals() == []

    def test_no_snapshot_returns_empty(self) -> None:
        svc = GitWatcher(snapshot_provider=lambda: None)
        assert svc.get_signals() == []

    def test_signals_sorted(self) -> None:
        snap = self._make_snapshot()
        svc = GitWatcher(snapshot_provider=lambda: snap)
        signals = svc.get_signals()
        keys = [(s.category, s.value) for s in signals]
        assert keys == sorted(keys)

    def test_privacy_no_file_paths_in_signals(self) -> None:
        """Constitutional: no file paths or commit messages in signals."""
        snap = self._make_snapshot(10, 2.0, 1)
        svc = GitWatcher(snapshot_provider=lambda: snap)
        allowed_values = {
            "active", "moderate", "stalled",
            "none", "few", "many",
            "possible", "likely",
        }
        for signal in svc.get_signals():
            assert signal.value in allowed_values, (
                f"Unexpected value '{signal.value}' in git signal"
            )


# ═══════════════════════════════════════════════════════════════════
# FileSystemWatcher — classification functions
# ═══════════════════════════════════════════════════════════════════


class TestFileSystemClassification:
    """Verify filesystem classification functions."""

    def test_activity_idle(self) -> None:
        assert _classify_activity(0, 300.0) == "idle"

    def test_activity_active(self) -> None:
        # 30 events / 5 min = 6/min → active (>3)
        assert _classify_activity(30, 300.0) == "active"

    def test_activity_intense(self) -> None:
        # 200 events / 5 min = 40/min → intense (>20)
        assert _classify_activity(200, 300.0) == "intense"

    def test_activity_zero_window(self) -> None:
        assert _classify_activity(10, 0) == "idle"

    def test_churn_low(self) -> None:
        assert _classify_churn(5, 300.0) == "low"

    def test_churn_medium(self) -> None:
        # 50 events / 5 min = 10/min → medium (>5)
        assert _classify_churn(50, 300.0) == "medium"

    def test_churn_high(self) -> None:
        # 300 events / 5 min = 60/min → high (>30)
        assert _classify_churn(300, 300.0) == "high"

    def test_churn_zero_window(self) -> None:
        assert _classify_churn(10, 0) == "low"


# ═══════════════════════════════════════════════════════════════════
# FileSystemWatcher — full service
# ═══════════════════════════════════════════════════════════════════


class TestFileSystemWatcher:
    """Verify FileSystemWatcher service behavior."""

    def test_name(self) -> None:
        svc = FileSystemWatcher()
        assert svc.name == "filesystem_watcher"

    def test_tier(self) -> None:
        svc = FileSystemWatcher()
        assert svc.tier == 1

    def test_idle_with_no_events(self) -> None:
        snap = FileSystemSnapshot(events_in_window=0, window_seconds=300.0)
        svc = FileSystemWatcher(snapshot_provider=lambda: snap)
        signals = svc.get_signals()
        categories = {s.category: s.value for s in signals}
        assert categories["activity_level"] == "idle"
        assert categories["file_churn"] == "low"

    def test_active_filesystem(self) -> None:
        snap = FileSystemSnapshot(events_in_window=30, window_seconds=300.0)
        svc = FileSystemWatcher(snapshot_provider=lambda: snap)
        signals = svc.get_signals()
        categories = {s.category: s.value for s in signals}
        assert categories["activity_level"] == "active"

    def test_intense_filesystem(self) -> None:
        snap = FileSystemSnapshot(events_in_window=200, window_seconds=300.0)
        svc = FileSystemWatcher(snapshot_provider=lambda: snap)
        signals = svc.get_signals()
        categories = {s.category: s.value for s in signals}
        assert categories["activity_level"] == "intense"

    def test_no_snapshot_returns_empty(self) -> None:
        svc = FileSystemWatcher(snapshot_provider=lambda: None)
        assert svc.get_signals() == []

    def test_signals_sorted(self) -> None:
        snap = FileSystemSnapshot(events_in_window=50, window_seconds=300.0)
        svc = FileSystemWatcher(snapshot_provider=lambda: snap)
        signals = svc.get_signals()
        keys = [(s.category, s.value) for s in signals]
        assert keys == sorted(keys)

    def test_internal_event_tracking(self) -> None:
        """Without a provider, uses internal event deque."""
        svc = FileSystemWatcher(window_seconds=300.0)
        svc.start()
        # Should return idle with no events
        signals = svc.get_signals()
        categories = {s.category: s.value for s in signals}
        assert categories["activity_level"] == "idle"

    def test_privacy_no_file_paths(self) -> None:
        """Constitutional: no file paths in signals."""
        snap = FileSystemSnapshot(events_in_window=100, window_seconds=300.0)
        svc = FileSystemWatcher(snapshot_provider=lambda: snap)
        allowed_values = {"idle", "active", "intense", "low", "medium", "high"}
        for signal in svc.get_signals():
            assert signal.value in allowed_values


# ═══════════════════════════════════════════════════════════════════
# PlatformInfo
# ═══════════════════════════════════════════════════════════════════


class TestPlatformInfo:
    """Verify platform detection."""

    def test_frozen(self) -> None:
        info = PlatformInfo(
            os="windows", is_wsl=False,
            has_psutil=True, has_watchdog=True, has_git=True,
        )
        with pytest.raises(AttributeError):
            info.os = "linux"  # type: ignore[misc]

    def test_detect_returns_platform_info(self) -> None:
        info = detect_platform()
        assert isinstance(info, PlatformInfo)
        assert info.os in ("windows", "macos", "linux")

    def test_detect_psutil_available(self) -> None:
        """psutil is installed in test env."""
        info = detect_platform()
        assert info.has_psutil is True

    def test_detect_git_available(self) -> None:
        """git is available in test env (we're in a git repo)."""
        info = detect_platform()
        assert info.has_git is True


# ═══════════════════════════════════════════════════════════════════
# Protocol compliance
# ═══════════════════════════════════════════════════════════════════


class TestServiceProtocol:
    """Verify all services satisfy OTTOService protocol."""

    def test_clock_is_service(self) -> None:
        svc = ClockService()
        assert isinstance(svc, OTTOService)

    def test_process_monitor_is_service(self) -> None:
        svc = ProcessMonitor(snapshot_provider=lambda: None)
        assert isinstance(svc, OTTOService)

    def test_git_watcher_is_service(self) -> None:
        svc = GitWatcher(snapshot_provider=lambda: None)
        assert isinstance(svc, OTTOService)

    def test_filesystem_watcher_is_service(self) -> None:
        svc = FileSystemWatcher()
        assert isinstance(svc, OTTOService)

    def test_all_services_have_required_attributes(self) -> None:
        """Every service has name, tier, running, start, stop, get_signals."""
        services = [
            ClockService(),
            ProcessMonitor(snapshot_provider=lambda: None),
            GitWatcher(snapshot_provider=lambda: None),
            FileSystemWatcher(),
        ]
        for svc in services:
            assert hasattr(svc, "name")
            assert hasattr(svc, "tier")
            assert hasattr(svc, "running")
            assert hasattr(svc, "start")
            assert hasattr(svc, "stop")
            assert hasattr(svc, "get_signals")


# ═══════════════════════════════════════════════════════════════════
# Privacy boundary (constitutional)
# ═══════════════════════════════════════════════════════════════════


class TestPrivacyBoundary:
    """Constitutional: verify no raw data leaks through signals."""

    def test_clock_no_raw_timestamps(self) -> None:
        dt = datetime(2026, 2, 10, 14, 30, tzinfo=timezone.utc)
        svc = ClockService(clock=lambda: dt)
        for signal in svc.get_signals():
            # Values should be categories, not raw times
            assert "14:30" not in signal.value
            assert "2026" not in signal.value

    def test_process_no_raw_names(self) -> None:
        snap = ProcessSnapshot(
            active_process="SuperSecretProject.exe",
            process_count=147,
            recent_switches=3,
        )
        svc = ProcessMonitor(snapshot_provider=lambda: snap)
        for signal in svc.get_signals():
            assert "SuperSecret" not in signal.value
            assert "147" not in signal.value

    def test_git_no_raw_paths(self) -> None:
        snap = GitSnapshot(
            uncommitted_count=7,
            hours_since_commit=2.5,
            commits_last_24h=3,
            is_repo=True,
        )
        svc = GitWatcher(snapshot_provider=lambda: snap)
        for signal in svc.get_signals():
            # No numbers (raw counts) in values
            assert signal.value in {
                "active", "moderate", "stalled",
                "none", "few", "many", "possible", "likely",
            }

    def test_filesystem_no_raw_paths(self) -> None:
        snap = FileSystemSnapshot(events_in_window=42, window_seconds=300.0)
        svc = FileSystemWatcher(snapshot_provider=lambda: snap)
        for signal in svc.get_signals():
            assert "42" not in signal.value
            assert signal.value in {"idle", "active", "intense", "low", "medium", "high"}


# ═══════════════════════════════════════════════════════════════════
# Determinism
# ═══════════════════════════════════════════════════════════════════


class TestServiceDeterminism:
    """Same inputs must produce identical outputs [He2025]."""

    def test_clock_deterministic_100x(self) -> None:
        dt = datetime(2026, 2, 10, 14, 30, tzinfo=timezone.utc)
        svc = ClockService(clock=lambda: dt)
        first = svc.get_signals()
        for _ in range(100):
            current = svc.get_signals()
            assert len(current) == len(first)
            for s1, s2 in zip(first, current):
                assert s1.category == s2.category
                assert s1.value == s2.value

    def test_process_deterministic_100x(self) -> None:
        snap = ProcessSnapshot("code.exe", 100, 0)
        svc = ProcessMonitor(snapshot_provider=lambda: snap)
        first = svc.get_signals()
        for _ in range(100):
            current = svc.get_signals()
            for s1, s2 in zip(first, current):
                assert s1.category == s2.category
                assert s1.value == s2.value

    def test_git_deterministic_100x(self) -> None:
        snap = GitSnapshot(3, 2.0, 4, True)
        svc = GitWatcher(snapshot_provider=lambda: snap)
        first = svc.get_signals()
        for _ in range(100):
            current = svc.get_signals()
            for s1, s2 in zip(first, current):
                assert s1.category == s2.category
                assert s1.value == s2.value


# ═══════════════════════════════════════════════════════════════════
# Import completeness
# ═══════════════════════════════════════════════════════════════════


class TestServiceImports:
    """Verify all public exports are accessible."""

    def test_all_exports_importable(self) -> None:
        from otto.services import __all__
        import otto.services as svc_module

        for name in __all__:
            assert hasattr(svc_module, name), f"Missing export: {name}"

    def test_key_types_importable(self) -> None:
        from otto.services import (
            CategoricalSignal,
            ClockService,
            FileSystemSnapshot,
            FileSystemWatcher,
            GitSnapshot,
            GitWatcher,
            OTTOService,
            PlatformInfo,
            ProcessMonitor,
            ProcessSnapshot,
            ServiceRegistry,
            detect_platform,
        )
        assert CategoricalSignal is not None
        assert detect_platform is not None
