"""Tests for mode protocol compliance (Phase 3.1)."""

from __future__ import annotations

from otto.modes.base import Mode
from otto.modes.executor import ExecutorMode
from otto.modes.protector import ProtectorMode
from otto.modes.restorer import RestorerMode


class TestProtocolCompliance:
    """Verify all modes satisfy the Mode protocol."""

    def test_executor_is_mode(self):
        assert isinstance(ExecutorMode(), Mode)

    def test_protector_is_mode(self):
        assert isinstance(ProtectorMode(), Mode)

    def test_restorer_is_mode(self):
        assert isinstance(RestorerMode(), Mode)


class TestSafetyFloors:
    def test_protector_floor_is_10_percent(self):
        assert ProtectorMode().safety_floor == 0.10

    def test_restorer_floor_is_5_percent(self):
        assert RestorerMode().safety_floor == 0.05

    def test_executor_floor_is_zero(self):
        assert ExecutorMode().safety_floor == 0.0


class TestModeNames:
    def test_executor_name(self):
        assert ExecutorMode().name == "executor"

    def test_protector_name(self):
        assert ProtectorMode().name == "protector"

    def test_restorer_name(self):
        assert RestorerMode().name == "restorer"
