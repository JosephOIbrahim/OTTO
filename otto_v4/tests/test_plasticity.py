"""Tests for the plasticity layer."""

from __future__ import annotations

from otto.plasticity import PlasticityWindow, _AMPLIFICATION, _STABILITY_THRESHOLD
from otto.state import CognitiveState


# ------------------------------------------------------------------
# PlasticityWindow — opening conditions
# ------------------------------------------------------------------


class TestPlasticityOpens:

    def test_opens_on_red_burnout(self):
        window = PlasticityWindow()
        state = CognitiveState(burnout="RED")
        window.update(state)
        assert window.is_open

    def test_opens_on_crashed_orange(self):
        window = PlasticityWindow()
        state = CognitiveState(burnout="ORANGE", momentum="crashed")
        window.update(state)
        assert window.is_open

    def test_does_not_open_on_green(self):
        window = PlasticityWindow()
        state = CognitiveState(burnout="GREEN")
        window.update(state)
        assert not window.is_open

    def test_does_not_open_on_orange_without_crashed(self):
        window = PlasticityWindow()
        state = CognitiveState(burnout="ORANGE", momentum="building")
        window.update(state)
        assert not window.is_open

    def test_does_not_open_on_crashed_without_orange(self):
        window = PlasticityWindow()
        state = CognitiveState(burnout="YELLOW", momentum="crashed")
        window.update(state)
        assert not window.is_open

    def test_does_not_open_on_yellow(self):
        window = PlasticityWindow()
        state = CognitiveState(burnout="YELLOW")
        window.update(state)
        assert not window.is_open


# ------------------------------------------------------------------
# PlasticityWindow — closing conditions
# ------------------------------------------------------------------


class TestPlasticityCloses:

    def test_closes_after_stability_threshold(self):
        """Window closes after N stable (non-crisis) exchanges."""
        window = PlasticityWindow(is_open=True)
        stable_state = CognitiveState(burnout="GREEN")

        for i in range(_STABILITY_THRESHOLD - 1):
            window.update(stable_state)
            assert window.is_open, f"Closed prematurely at exchange {i + 1}"

        window.update(stable_state)
        assert not window.is_open

    def test_stability_resets_on_relapse(self):
        """If crisis returns during stability counting, reset the counter."""
        window = PlasticityWindow(is_open=True)
        stable = CognitiveState(burnout="GREEN")
        crisis = CognitiveState(burnout="RED")

        # 2 stable exchanges (not enough to close)
        window.update(stable)
        window.update(stable)
        assert window.is_open
        assert window.stable_count == 2

        # Relapse: crisis returns
        window.update(crisis)
        assert window.is_open
        assert window.stable_count == 0

        # Need full threshold again
        for _ in range(_STABILITY_THRESHOLD):
            window.update(stable)
        assert not window.is_open

    def test_already_closed_stays_closed(self):
        window = PlasticityWindow()
        stable = CognitiveState(burnout="GREEN")
        window.update(stable)
        assert not window.is_open
        assert window.stable_count == 0


# ------------------------------------------------------------------
# PlasticityWindow — amplification
# ------------------------------------------------------------------


class TestAmplification:

    def test_amplification_when_open(self):
        window = PlasticityWindow(is_open=True)
        assert window.amplification == _AMPLIFICATION
        assert window.adjust_strength(1.0) == _AMPLIFICATION

    def test_no_amplification_when_closed(self):
        window = PlasticityWindow(is_open=False)
        assert window.amplification == 1.0
        assert window.adjust_strength(1.0) == 1.0

    def test_amplification_scales_base_strength(self):
        window = PlasticityWindow(is_open=True)
        assert window.adjust_strength(0.3) == 0.3 * _AMPLIFICATION
        assert window.adjust_strength(0.5) == 0.5 * _AMPLIFICATION

    def test_zero_strength_stays_zero(self):
        window = PlasticityWindow(is_open=True)
        assert window.adjust_strength(0.0) == 0.0


# ------------------------------------------------------------------
# Full lifecycle
# ------------------------------------------------------------------


class TestLifecycle:

    def test_full_cycle_open_recover_close(self):
        """Open during crisis, recover, close after 3 stable exchanges."""
        window = PlasticityWindow()

        # Enter crisis
        window.update(CognitiveState(burnout="RED"))
        assert window.is_open
        assert window.adjust_strength(1.0) == _AMPLIFICATION

        # Still in crisis
        window.update(CognitiveState(burnout="RED"))
        assert window.is_open

        # Recovery begins
        window.update(CognitiveState(burnout="YELLOW"))
        assert window.is_open
        assert window.stable_count == 1

        window.update(CognitiveState(burnout="GREEN"))
        assert window.is_open
        assert window.stable_count == 2

        window.update(CognitiveState(burnout="GREEN"))
        assert not window.is_open
        assert window.adjust_strength(1.0) == 1.0

    def test_multiple_cycles(self):
        """Window can open, close, and reopen."""
        window = PlasticityWindow()

        # First cycle
        window.update(CognitiveState(burnout="RED"))
        assert window.is_open
        for _ in range(_STABILITY_THRESHOLD):
            window.update(CognitiveState(burnout="GREEN"))
        assert not window.is_open

        # Second cycle
        window.update(CognitiveState(burnout="ORANGE", momentum="crashed"))
        assert window.is_open
        for _ in range(_STABILITY_THRESHOLD):
            window.update(CognitiveState(burnout="GREEN"))
        assert not window.is_open

    def test_deterministic_behavior(self):
        """Same state sequence -> same window behavior (100 iterations)."""
        results = []
        for _ in range(100):
            window = PlasticityWindow()
            window.update(CognitiveState(burnout="RED"))
            window.update(CognitiveState(burnout="GREEN"))
            window.update(CognitiveState(burnout="GREEN"))
            results.append((window.is_open, window.stable_count))

        assert len(set(results)) == 1
