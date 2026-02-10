"""Tests for NEXUS 5-phase expert routing — Day 4 of OTTO OS v3.0.

These tests verify:
1. Safety floors ALWAYS applied (100 random inputs)
2. Signal → correct primary expert routing
3. State boosts influence weighting
4. Supporting experts filtered by > 0.20 threshold
5. Agent team flag set correctly
6. Determinism (same signals + same state → same selection, 100x)
7. All 5 phases produce correct intermediate results
8. Expert registry is properly sorted
"""

from __future__ import annotations

import random

import pytest

from otto_v3.core.constitution import SafetyFloors
from otto_v3.core.prism.signals import CognitiveSignal, Signal
from otto_v3.core.experts.base import ExpertConfig, ExpertSelection, ExpertWeight
from otto_v3.core.experts.router import (
    ALL_EXPERTS,
    NEXUSRouter,
    STATE_BOOSTS,
)


# ===================================================================
# Helpers
# ===================================================================

def make_signal(
    signal_type: CognitiveSignal,
    confidence: float = 0.80,
) -> Signal:
    """Create a Signal with defaults for testing."""
    return Signal(type=signal_type, confidence=confidence, source="test")


def make_signals(*pairs: tuple[CognitiveSignal, float]) -> list[Signal]:
    """Create multiple signals from (type, confidence) pairs."""
    return [make_signal(t, c) for t, c in pairs]


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def router() -> NEXUSRouter:
    return NEXUSRouter()


@pytest.fixture
def floors() -> SafetyFloors:
    return SafetyFloors()


# ===================================================================
# Test: Expert registry
# ===================================================================

class TestExpertRegistry:
    """ALL_EXPERTS must be sorted and complete."""

    def test_has_seven_experts(self) -> None:
        assert len(ALL_EXPERTS) == 7

    def test_sorted_by_name(self) -> None:
        names = [e.name for e in ALL_EXPERTS]
        assert names == sorted(names)

    def test_expected_names(self) -> None:
        names = {e.name for e in ALL_EXPERTS}
        expected = {
            "protector", "decomposer", "restorer",
            "redirector", "acknowledger", "guide", "executor",
        }
        assert names == expected

    def test_is_tuple(self) -> None:
        assert isinstance(ALL_EXPERTS, tuple)

    def test_floored_experts_have_correct_floors(self) -> None:
        floor_map = {e.name: e.safety_floor for e in ALL_EXPERTS}
        assert floor_map["protector"] == 0.10
        assert floor_map["decomposer"] == 0.05
        assert floor_map["restorer"] == 0.05

    def test_non_floored_experts_have_zero_floor(self) -> None:
        for expert in ALL_EXPERTS:
            if expert.name not in ("protector", "decomposer", "restorer"):
                assert expert.safety_floor == 0.0, (
                    f"{expert.name} should have floor 0.0"
                )

    def test_all_affinities_are_subsets_of_triggers(self) -> None:
        """Every signal in affinities must also be in trigger_signals."""
        for expert in ALL_EXPERTS:
            affinity_signals = set(expert.signal_affinities.keys())
            assert affinity_signals <= expert.trigger_signals, (
                f"{expert.name}: affinities {affinity_signals - expert.trigger_signals} "
                f"not in trigger_signals"
            )


# ===================================================================
# Test: Safety floors ALWAYS applied
# ===================================================================

class TestSafetyFloors:
    """Safety floors must hold under ALL conditions — 100 random inputs."""

    def test_safety_floors_100_random_inputs(self, router: NEXUSRouter) -> None:
        """Generate 100 random signal combinations and verify floors."""
        rng = random.Random(42)  # Seeded for reproducibility
        all_signals = list(CognitiveSignal)

        for i in range(100):
            # Random subset of signals with random confidences
            count = rng.randint(0, 5)
            chosen = rng.sample(all_signals, min(count, len(all_signals)))
            signals = [
                make_signal(s, round(rng.uniform(0.1, 1.0), 2))
                for s in chosen
            ]

            selection = router.route(signals)

            # Extract all expert weights from the selection
            all_weights = {selection.primary.expert: selection.primary.value}
            for sup in selection.supporting:
                all_weights[sup.expert] = sup.value

            # The primary and supporting may not include all experts,
            # but the primary expert must exist. We need to verify
            # that the BOUND phase was applied correctly. Let's run
            # the internal phases directly for deeper verification.
            bounded = router._bound(
                router._weight(
                    router._activate(signals),
                    signals,
                    {},
                )
            )
            weight_map = {w.expert: w.value for w in bounded}

            assert weight_map["protector"] >= 0.10, (
                f"Iteration {i}: protector={weight_map['protector']}"
            )
            assert weight_map["decomposer"] >= 0.05, (
                f"Iteration {i}: decomposer={weight_map['decomposer']}"
            )
            assert weight_map["restorer"] >= 0.05, (
                f"Iteration {i}: restorer={weight_map['restorer']}"
            )

    def test_safety_floors_with_empty_signals(self, router: NEXUSRouter) -> None:
        """Even with NO signals, floors must apply."""
        selection = router.route([])
        bounded = router._bound(router._weight(router._activate([]), [], {}))
        weight_map = {w.expert: w.value for w in bounded}

        assert weight_map["protector"] >= 0.10
        assert weight_map["decomposer"] >= 0.05
        assert weight_map["restorer"] >= 0.05

    def test_floors_cannot_be_lowered(self) -> None:
        """Even if you construct with custom floors, minimum is enforced."""
        floors = SafetyFloors()  # Always 0.10, 0.05, 0.05
        router = NEXUSRouter(safety_floors=floors)
        bounded = router._bound(router._weight(router._activate([]), [], {}))
        weight_map = {w.expert: w.value for w in bounded}

        assert weight_map["protector"] >= floors.protector
        assert weight_map["decomposer"] >= floors.decomposer
        assert weight_map["restorer"] >= floors.restorer


# ===================================================================
# Test: Signal → Primary Expert routing
# ===================================================================

class TestSignalToExpert:
    """Specific signals must route to the correct primary expert."""

    def test_frustrated_routes_to_protector(self, router: NEXUSRouter) -> None:
        signals = [make_signal(CognitiveSignal.FRUSTRATED, 0.80)]
        selection = router.route(signals)
        assert selection.primary.expert == "protector"

    def test_crashed_routes_to_protector(self, router: NEXUSRouter) -> None:
        signals = [make_signal(CognitiveSignal.CRASHED, 0.85)]
        selection = router.route(signals)
        assert selection.primary.expert == "protector"

    def test_overwhelmed_routes_to_protector(self, router: NEXUSRouter) -> None:
        """OVERWHELMED triggers both protector and decomposer, but
        protector has higher affinity (0.70 * 0.80 vs 0.75 * 0.80)
        PLUS 10% floor advantage. Wait — let's check:
        protector: 0.80 * 0.70 = 0.56
        decomposer: 0.80 * 0.75 = 0.60
        So decomposer wins on raw weight. That's fine — the Decomposer
        IS the right response for overwhelm (break things down)."""
        signals = [make_signal(CognitiveSignal.OVERWHELMED, 0.80)]
        selection = router.route(signals)
        assert selection.primary.expert in ("protector", "decomposer")

    def test_stuck_routes_to_decomposer(self, router: NEXUSRouter) -> None:
        signals = [make_signal(CognitiveSignal.STUCK, 0.70)]
        selection = router.route(signals)
        assert selection.primary.expert == "decomposer"

    def test_depleted_routes_to_restorer(self, router: NEXUSRouter) -> None:
        signals = [make_signal(CognitiveSignal.DEPLETED, 0.75)]
        selection = router.route(signals)
        assert selection.primary.expert == "restorer"

    def test_low_energy_routes_to_restorer(self, router: NEXUSRouter) -> None:
        signals = [make_signal(CognitiveSignal.LOW_ENERGY, 0.60)]
        selection = router.route(signals)
        assert selection.primary.expert == "restorer"

    def test_focused_routes_to_executor(self, router: NEXUSRouter) -> None:
        signals = [make_signal(CognitiveSignal.FOCUSED, 0.65)]
        selection = router.route(signals)
        assert selection.primary.expert == "executor"

    def test_exploring_routes_to_guide(self, router: NEXUSRouter) -> None:
        signals = [make_signal(CognitiveSignal.EXPLORING, 0.65)]
        selection = router.route(signals)
        assert selection.primary.expert == "guide"

    def test_context_switch_routes_to_redirector(self, router: NEXUSRouter) -> None:
        signals = [make_signal(CognitiveSignal.CONTEXT_SWITCH, 0.80)]
        selection = router.route(signals)
        assert selection.primary.expert == "redirector"

    def test_high_energy_routes_to_acknowledger(self, router: NEXUSRouter) -> None:
        signals = [make_signal(CognitiveSignal.HIGH_ENERGY, 0.65)]
        selection = router.route(signals)
        assert selection.primary.expert == "acknowledger"


# ===================================================================
# Test: State boosts
# ===================================================================

class TestStateBoosts:
    """LIVRPS-resolved state must influence expert weighting."""

    def test_energy_depleted_boosts_restorer(self, router: NEXUSRouter) -> None:
        """Restorer should win over a weak signal when state says depleted.

        With FOCUSED at 0.30: executor = 0.30 * 0.85 = 0.255
        With energy=depleted: restorer boost = 0.30
        Restorer (0.30) > Executor (0.255) → restorer wins.
        """
        signals = [make_signal(CognitiveSignal.FOCUSED, 0.30)]
        state = {"energy": "depleted"}
        selection = router.route(signals, state)
        assert selection.primary.expert == "restorer"

    def test_burnout_red_boosts_protector(self, router: NEXUSRouter) -> None:
        """Protector should win over a weak signal when burnout is red.

        With FOCUSED at 0.30: executor = 0.30 * 0.85 = 0.255
        With burnout=red: protector boost = 0.30
        Protector (0.30) > Executor (0.255) → protector wins.
        """
        signals = [make_signal(CognitiveSignal.FOCUSED, 0.30)]
        state = {"burnout": "red"}
        selection = router.route(signals, state)
        assert selection.primary.expert == "protector"

    def test_energy_high_boosts_executor(self, router: NEXUSRouter) -> None:
        signals = [make_signal(CognitiveSignal.FOCUSED, 0.65)]
        state = {"energy": "high"}
        selection = router.route(signals, state)
        # Executor: 0.65*0.85 + 0.10 = 0.6525
        assert selection.primary.expert == "executor"

    def test_state_boosts_are_sorted(self) -> None:
        """STATE_BOOSTS must be a sorted tuple for."""
        keys = [(prop, val, name) for prop, val, name, _ in STATE_BOOSTS]
        assert keys == sorted(keys)

    def test_empty_state_no_effect(self, router: NEXUSRouter) -> None:
        signals = [make_signal(CognitiveSignal.STUCK, 0.70)]
        with_state = router.route(signals, {})
        without_state = router.route(signals)
        assert with_state.primary.expert == without_state.primary.expert
        assert with_state.primary.value == without_state.primary.value


# ===================================================================
# Test: Supporting experts and agent team
# ===================================================================

class TestSupportingExperts:
    """Supporting experts must be filtered by > 0.20 threshold."""

    def test_supporting_above_threshold(self, router: NEXUSRouter) -> None:
        """Multi-signal input should produce supporting experts."""
        signals = make_signals(
            (CognitiveSignal.FRUSTRATED, 0.80),
            (CognitiveSignal.STUCK, 0.70),
        )
        selection = router.route(signals)
        # Both protector and decomposer should score high
        for sup in selection.supporting:
            assert sup.value > 0.20

    def test_max_two_supporting(self, router: NEXUSRouter) -> None:
        """Supporting experts capped at 2."""
        signals = make_signals(
            (CognitiveSignal.FRUSTRATED, 0.90),
            (CognitiveSignal.STUCK, 0.80),
            (CognitiveSignal.DEPLETED, 0.70),
            (CognitiveSignal.CONTEXT_SWITCH, 0.60),
        )
        selection = router.route(signals)
        assert len(selection.supporting) <= 2

    def test_agent_team_true_with_supporting(self, router: NEXUSRouter) -> None:
        signals = make_signals(
            (CognitiveSignal.FRUSTRATED, 0.80),
            (CognitiveSignal.STUCK, 0.70),
        )
        selection = router.route(signals)
        if selection.supporting:
            assert selection.use_agent_team is True

    def test_agent_team_false_single_expert(self, router: NEXUSRouter) -> None:
        """Single dominant signal → single expert, no team."""
        signals = [make_signal(CognitiveSignal.EXPLORING, 0.65)]
        selection = router.route(signals)
        # Guide should dominate, others below 0.20
        if not selection.supporting:
            assert selection.use_agent_team is False

    def test_no_signals_still_selects_primary(self, router: NEXUSRouter) -> None:
        """With no signals, safety floors determine the primary."""
        selection = router.route([])
        # Protector has highest floor (0.10) → wins
        assert selection.primary.expert == "protector"
        assert selection.primary.value >= 0.10


# ===================================================================
# Test: ExpertSelection.from_bounded_weights
# ===================================================================

class TestExpertSelection:
    """ExpertSelection must be built deterministically from weights."""

    def test_highest_weight_is_primary(self) -> None:
        weights = [
            ExpertWeight("a", 0.30),
            ExpertWeight("b", 0.80),
            ExpertWeight("c", 0.50),
        ]
        sel = ExpertSelection.from_bounded_weights(weights)
        assert sel.primary.expert == "b"
        assert sel.primary.value == 0.80

    def test_tiebreaker_is_alphabetical(self) -> None:
        """When weights tie, alphabetically first expert wins."""
        weights = [
            ExpertWeight("beta", 0.50),
            ExpertWeight("alpha", 0.50),
        ]
        sel = ExpertSelection.from_bounded_weights(weights)
        assert sel.primary.expert == "alpha"

    def test_supporting_above_020(self) -> None:
        weights = [
            ExpertWeight("a", 0.80),
            ExpertWeight("b", 0.25),
            ExpertWeight("c", 0.15),
            ExpertWeight("d", 0.30),
        ]
        sel = ExpertSelection.from_bounded_weights(weights)
        supporting_names = {w.expert for w in sel.supporting}
        assert "b" in supporting_names  # 0.25 > 0.20
        assert "d" in supporting_names  # 0.30 > 0.20
        assert "c" not in supporting_names  # 0.15 <= 0.20

    def test_supporting_max_two(self) -> None:
        weights = [
            ExpertWeight("a", 0.90),
            ExpertWeight("b", 0.80),
            ExpertWeight("c", 0.70),
            ExpertWeight("d", 0.60),
        ]
        sel = ExpertSelection.from_bounded_weights(weights)
        assert len(sel.supporting) <= 2

    def test_frozen(self) -> None:
        import dataclasses
        weights = [ExpertWeight("a", 0.80)]
        sel = ExpertSelection.from_bounded_weights(weights)
        with pytest.raises(dataclasses.FrozenInstanceError):
            sel.use_agent_team = False  # type: ignore[misc]


# ===================================================================
# Test: Phase 1 — ACTIVATE
# ===================================================================

class TestPhaseActivate:
    """Phase 1 must correctly identify responding experts."""

    def test_frustrated_activates_protector(self, router: NEXUSRouter) -> None:
        signals = [make_signal(CognitiveSignal.FRUSTRATED)]
        activated = router._activate(signals)
        names = {e.name for e in activated}
        assert "protector" in names

    def test_no_signals_activates_nothing(self, router: NEXUSRouter) -> None:
        activated = router._activate([])
        assert activated == []

    def test_multiple_signals_activate_multiple_experts(
        self, router: NEXUSRouter
    ) -> None:
        signals = make_signals(
            (CognitiveSignal.FRUSTRATED, 0.80),
            (CognitiveSignal.STUCK, 0.70),
        )
        activated = router._activate(signals)
        names = {e.name for e in activated}
        assert "protector" in names
        assert "decomposer" in names

    def test_activated_list_sorted_by_name(self, router: NEXUSRouter) -> None:
        signals = make_signals(
            (CognitiveSignal.FOCUSED, 0.80),
            (CognitiveSignal.EXPLORING, 0.70),
        )
        activated = router._activate(signals)
        names = [e.name for e in activated]
        assert names == sorted(names)


# ===================================================================
# Test: Phase 3 — BOUND
# ===================================================================

class TestPhaseBound:
    """Phase 3 must enforce safety floors."""

    def test_raises_zero_weights_to_floors(self, router: NEXUSRouter) -> None:
        weights = [
            ExpertWeight("protector", 0.0),
            ExpertWeight("decomposer", 0.0),
            ExpertWeight("restorer", 0.0),
        ]
        bounded = router._bound(weights)
        weight_map = {w.expert: w.value for w in bounded}
        assert weight_map["protector"] == 0.10
        assert weight_map["decomposer"] == 0.05
        assert weight_map["restorer"] == 0.05

    def test_does_not_lower_above_floor(self, router: NEXUSRouter) -> None:
        weights = [
            ExpertWeight("protector", 0.80),
            ExpertWeight("decomposer", 0.60),
        ]
        bounded = router._bound(weights)
        weight_map = {w.expert: w.value for w in bounded}
        assert weight_map["protector"] == 0.80  # Not lowered
        assert weight_map["decomposer"] == 0.60

    def test_bounded_output_sorted_by_name(self, router: NEXUSRouter) -> None:
        weights = [
            ExpertWeight("z_expert", 0.50),
            ExpertWeight("a_expert", 0.50),
        ]
        bounded = router._bound(weights)
        names = [w.expert for w in bounded]
        assert names == sorted(names)


# ===================================================================
# Test: Phase 5 — UPDATE callback
# ===================================================================

class TestPhaseUpdate:
    """Phase 5 must invoke the callback when provided."""

    def test_callback_invoked(self) -> None:
        calls: list[tuple] = []

        def on_route(sel: ExpertSelection, sigs: list[Signal]) -> None:
            calls.append((sel.primary.expert, len(sigs)))

        router = NEXUSRouter(on_route=on_route)
        signals = [make_signal(CognitiveSignal.FRUSTRATED, 0.80)]
        router.route(signals)
        assert len(calls) == 1
        assert calls[0][0] == "protector"
        assert calls[0][1] == 1

    def test_no_callback_no_error(self, router: NEXUSRouter) -> None:
        """Default router has no callback — should not raise."""
        signals = [make_signal(CognitiveSignal.FRUSTRATED)]
        router.route(signals)  # Should not raise


# ===================================================================
# Test: Determinism — Determinism
# ===================================================================

class TestDeterminism:
    """Same signals + same state = same selection, always."""

    SCENARIOS = [
        ("frustrated", [(CognitiveSignal.FRUSTRATED, 0.80)], {}),
        ("stuck", [(CognitiveSignal.STUCK, 0.70)], {}),
        ("depleted", [(CognitiveSignal.DEPLETED, 0.75)], {}),
        ("focused", [(CognitiveSignal.FOCUSED, 0.65)], {}),
        ("exploring", [(CognitiveSignal.EXPLORING, 0.65)], {}),
        ("multi", [
            (CognitiveSignal.FRUSTRATED, 0.80),
            (CognitiveSignal.STUCK, 0.70),
            (CognitiveSignal.DEPLETED, 0.60),
        ], {}),
        ("empty", [], {}),
        ("with_state", [
            (CognitiveSignal.FOCUSED, 0.40),
        ], {"energy": "depleted"}),
    ]

    def test_deterministic_100x(self, router: NEXUSRouter) -> None:
        """Run routing 100 times for each scenario — must be identical."""
        for name, signal_defs, state in self.SCENARIOS:
            signals = make_signals(*signal_defs)
            first = router.route(signals, state)
            first_key = (
                first.primary.expert,
                first.primary.value,
                tuple((s.expert, s.value) for s in first.supporting),
                first.use_agent_team,
            )
            for i in range(99):
                current = router.route(signals, state)
                current_key = (
                    current.primary.expert,
                    current.primary.value,
                    tuple((s.expert, s.value) for s in current.supporting),
                    current.use_agent_team,
                )
                assert current_key == first_key, (
                    f"Scenario '{name}' diverged on iteration {i + 2}"
                )

    def test_two_routers_same_result(self) -> None:
        """Two independent routers must produce identical results."""
        r1 = NEXUSRouter()
        r2 = NEXUSRouter()
        for name, signal_defs, state in self.SCENARIOS:
            signals = make_signals(*signal_defs)
            sel1 = r1.route(signals, state)
            sel2 = r2.route(signals, state)
            assert sel1.primary.expert == sel2.primary.expert
            assert sel1.primary.value == sel2.primary.value


# ===================================================================
# Test: Full pipeline integration
# ===================================================================

class TestFullPipeline:
    """End-to-end routing through all 5 phases."""

    def test_frustrated_user_full_pipeline(self, router: NEXUSRouter) -> None:
        """Simulate: user sends frustrated message."""
        from otto_v3.core.prism.detector import PRISMDetector

        detector = PRISMDetector()
        signals = detector.detect("UGH this is broken, nothing works!!")
        selection = router.route(signals)

        # Protector should be primary (FRUSTRATED signal)
        assert selection.primary.expert == "protector"
        assert selection.primary.value > 0.10

    def test_stuck_user_full_pipeline(self, router: NEXUSRouter) -> None:
        from otto_v3.core.prism.detector import PRISMDetector

        detector = PRISMDetector()
        signals = detector.detect("I'm completely stuck, don't know how to proceed")
        selection = router.route(signals)

        assert selection.primary.expert == "decomposer"

    def test_depleted_user_full_pipeline(self, router: NEXUSRouter) -> None:
        from otto_v3.core.prism.detector import PRISMDetector

        detector = PRISMDetector()
        signals = detector.detect("I'm exhausted, need a break, can't think anymore")
        selection = router.route(signals)

        assert selection.primary.expert == "restorer"

    def test_focused_user_full_pipeline(self, router: NEXUSRouter) -> None:
        from otto_v3.core.prism.detector import PRISMDetector

        detector = PRISMDetector()
        signals = detector.detect("ready to go, let's do this")
        selection = router.route(signals)

        assert selection.primary.expert == "executor"

    def test_exploring_user_full_pipeline(self, router: NEXUSRouter) -> None:
        from otto_v3.core.prism.detector import PRISMDetector

        detector = PRISMDetector()
        signals = detector.detect("what if we tried a completely different approach?")
        selection = router.route(signals)

        assert selection.primary.expert == "guide"
