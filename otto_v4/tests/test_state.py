"""Tests for cognitive state tracking (Phase 0.2)."""

from __future__ import annotations

import pytest

from otto.state import CognitiveState, StateStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def state_store(tmp_path) -> StateStore:
    """StateStore backed by a temp database."""
    db_path = str(tmp_path / "test_state.db")
    return StateStore(db_path=db_path)


# ---------------------------------------------------------------------------
# CognitiveState dataclass
# ---------------------------------------------------------------------------


class TestCognitiveStateDefaults:
    """Default state is healthy baseline."""

    def test_default_energy(self):
        s = CognitiveState()
        assert s.energy == "medium"

    def test_default_burnout(self):
        s = CognitiveState()
        assert s.burnout == "GREEN"

    def test_default_momentum(self):
        s = CognitiveState()
        assert s.momentum == "cold_start"

    def test_default_counters(self):
        s = CognitiveState()
        assert s.nudges_sent_today == 0
        assert s.nudges_completed_today == 0
        assert s.suppressed_count == 0


class TestNudgeEffectiveness:
    """nudge_effectiveness property."""

    def test_no_nudges_returns_one(self):
        s = CognitiveState(nudges_sent_today=0)
        assert s.nudge_effectiveness == 1.0

    def test_all_completed(self):
        s = CognitiveState(nudges_sent_today=3, nudges_completed_today=3)
        assert s.nudge_effectiveness == 1.0

    def test_none_completed(self):
        s = CognitiveState(nudges_sent_today=5, nudges_completed_today=0)
        assert s.nudge_effectiveness == 0.0

    def test_partial(self):
        s = CognitiveState(nudges_sent_today=4, nudges_completed_today=2)
        assert s.nudge_effectiveness == 0.5


class TestShouldSuppressNudge:
    """Constitutional suppression logic on CognitiveState."""

    def test_red_always_suppresses(self):
        s = CognitiveState(burnout="RED")
        assert s.should_suppress_nudge is True

    def test_green_does_not_suppress(self):
        s = CognitiveState(burnout="GREEN", energy="high")
        assert s.should_suppress_nudge is False

    def test_orange_depleted_suppresses(self):
        s = CognitiveState(burnout="ORANGE", energy="depleted")
        assert s.should_suppress_nudge is True

    def test_orange_low_suppresses(self):
        s = CognitiveState(burnout="ORANGE", energy="low")
        assert s.should_suppress_nudge is True

    def test_orange_medium_does_not_suppress(self):
        s = CognitiveState(burnout="ORANGE", energy="medium")
        assert s.should_suppress_nudge is False

    def test_low_effectiveness_high_volume_suppresses(self):
        s = CognitiveState(
            nudges_sent_today=5,
            nudges_completed_today=0,  # effectiveness = 0.0 < 0.1
        )
        assert s.should_suppress_nudge is True

    def test_low_effectiveness_low_volume_does_not_suppress(self):
        """Threshold requires > 3 nudges sent before effectiveness check kicks in."""
        s = CognitiveState(
            nudges_sent_today=2,
            nudges_completed_today=0,  # effectiveness = 0.0 but only 2 sent
        )
        assert s.should_suppress_nudge is False


# ---------------------------------------------------------------------------
# StateStore persistence
# ---------------------------------------------------------------------------


class TestStateStorePersistence:
    """State survives save/load cycle."""

    def test_default_load(self, state_store):
        state = state_store.load()
        assert state.energy == "medium"
        assert state.burnout == "GREEN"

    def test_save_and_load(self, state_store):
        original = CognitiveState(
            energy="low",
            burnout="YELLOW",
            momentum="building",
            nudges_sent_today=3,
            nudges_completed_today=1,
            suppressed_count=2,
        )
        state_store.save(original)

        loaded = state_store.load()
        assert loaded.energy == "low"
        assert loaded.burnout == "YELLOW"
        assert loaded.momentum == "building"
        assert loaded.nudges_sent_today == 3
        assert loaded.nudges_completed_today == 1
        assert loaded.suppressed_count == 2

    def test_overwrite(self, state_store):
        state_store.save(CognitiveState(energy="high"))
        state_store.save(CognitiveState(energy="depleted"))

        loaded = state_store.load()
        assert loaded.energy == "depleted"


class TestStateStoreSetters:
    """Individual field setters with validation."""

    def test_set_energy_valid(self, state_store):
        state = state_store.set_energy("low")
        assert state.energy == "low"
        # Persisted
        assert state_store.load().energy == "low"

    def test_set_energy_invalid(self, state_store):
        with pytest.raises(ValueError, match="Invalid energy level"):
            state_store.set_energy("exhausted")

    def test_set_burnout_valid(self, state_store):
        state = state_store.set_burnout("ORANGE")
        assert state.burnout == "ORANGE"
        assert state_store.load().burnout == "ORANGE"

    def test_set_burnout_invalid(self, state_store):
        with pytest.raises(ValueError, match="Invalid burnout level"):
            state_store.set_burnout("PURPLE")

    def test_set_momentum_valid(self, state_store):
        state = state_store.set_momentum("rolling")
        assert state.momentum == "rolling"
        assert state_store.load().momentum == "rolling"

    def test_set_momentum_invalid(self, state_store):
        with pytest.raises(ValueError, match="Invalid momentum phase"):
            state_store.set_momentum("flying")


class TestStateStoreCounters:
    """Counter increment methods."""

    def test_increment_nudges_sent(self, state_store):
        state_store.increment_nudges_sent()
        state_store.increment_nudges_sent()
        assert state_store.load().nudges_sent_today == 2

    def test_increment_nudges_completed(self, state_store):
        state_store.increment_nudges_completed()
        assert state_store.load().nudges_completed_today == 1

    def test_increment_suppressed(self, state_store):
        state_store.increment_suppressed()
        state_store.increment_suppressed()
        state_store.increment_suppressed()
        assert state_store.load().suppressed_count == 3

    def test_reset_daily_counters(self, state_store):
        state_store.save(CognitiveState(
            nudges_sent_today=5,
            nudges_completed_today=3,
            suppressed_count=2,
        ))
        state_store.reset_daily_counters()

        loaded = state_store.load()
        assert loaded.nudges_sent_today == 0
        assert loaded.nudges_completed_today == 0
        assert loaded.suppressed_count == 2  # NOT reset
