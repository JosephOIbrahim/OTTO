"""Deterministic simulation engine for OTTO v5.1.

Generates synthetic interactions to exercise the full UCB1 -> trail -> routing
pipeline. Proves learning works with real outcome data.

Deterministic: same seed -> same results. Uses hashlib for PRNG
(not random module) to avoid PYTHONHASHSEED dependency.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .learner import compute_ucb_adjustments
from .models import Commitment
from .modes import (
    AcknowledgerMode,
    DecomposerMode,
    ExecutorMode,
    GuideMode,
    ProtectorMode,
    RedirectorMode,
    RestorerMode,
)
from .router import _SIGNAL_TO_MODE, route_and_execute
from .signals import Signal, SignalType
from .state import CognitiveState
from .store import CommitmentStore
from .trails import TrailStore


# ---------------------------------------------------------------------------
# Scenarios: (signal_type, state_overrides, success_probability)
# ---------------------------------------------------------------------------

_SCENARIOS: list[tuple[SignalType, dict[str, str], float]] = [
    (SignalType.COMMITMENT_DETECTED, {"energy": "medium"}, 0.7),
    (SignalType.COMMITMENT_DETECTED, {"energy": "low"}, 0.4),
    (SignalType.FRUSTRATED, {"burnout": "YELLOW"}, 0.6),
    (SignalType.FRUSTRATED, {"burnout": "ORANGE"}, 0.3),
    (SignalType.DEPLETED, {"energy": "depleted"}, 0.5),
    (SignalType.STUCK, {"energy": "medium"}, 0.6),
    (SignalType.OVERWHELMED, {"energy": "low"}, 0.4),
    (SignalType.EXPLORING, {"energy": "high", "momentum": "rolling"}, 0.8),
    (SignalType.BURST_DETECTED, {"momentum": "peak"}, 0.5),
    (SignalType.FOCUSED, {"momentum": "building"}, 0.9),
]


@dataclass
class SimulationResult:
    """Outcome of a simulation run."""

    cycles_completed: int = 0
    total_outcomes: int = 0
    mode_activations: dict[str, int] = field(default_factory=dict)
    ucb_adjustments_final: dict[str, float] = field(default_factory=dict)
    success_rates: dict[str, float] = field(default_factory=dict)

    def summary(self) -> str:
        """Human-readable summary of the simulation."""
        lines = [
            f"Simulation: {self.cycles_completed} cycles, {self.total_outcomes} outcomes",
            f"Modes activated: {len(self.mode_activations)}",
        ]
        for mode_name, count in sorted(self.mode_activations.items()):
            rate = self.success_rates.get(mode_name, 0.0)
            adj = self.ucb_adjustments_final.get(mode_name, 0.0)
            lines.append(
                f"  {mode_name}: {count} activations, "
                f"success_rate={rate:.2f}, ucb_adj={adj:+.4f}"
            )
        return "\n".join(lines)


class SimulationEngine:
    """Deterministic simulation engine for the UCB1 learning pipeline.

    Generates synthetic interactions, routes them through NEXUS, records
    outcomes, and computes UCB adjustments. Proves the full learning loop
    works end-to-end.

    Parameters
    ----------
    db_path:
        SQLite database path. Must be a real filesystem path
        (CommitmentStore uses Path expansion). Use tmp_path in tests.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    @staticmethod
    def _deterministic_choice(seed: int, cycle: int, n: int) -> int:
        """Pick an index in [0, n) deterministically.

        Uses SHA-256 of (seed, cycle) to produce a stable integer.
        """
        key = f"choice:{seed}:{cycle}".encode()
        digest = hashlib.sha256(key).hexdigest()  # noqa: S324
        return int(digest[:8], 16) % n

    @staticmethod
    def _deterministic_bool(seed: int, cycle: int, probability: float) -> bool:
        """Return True with the given probability, deterministically.

        Uses SHA-256 of (seed, cycle, "bool") to produce a stable float
        in [0, 1), then compares against probability.
        """
        key = f"bool:{seed}:{cycle}".encode()
        digest = hashlib.sha256(key).hexdigest()  # noqa: S324
        value = int(digest[:8], 16) / 0xFFFFFFFF
        return value < probability

    def run(self, n_cycles: int = 100, seed: int = 42) -> SimulationResult:
        """Run the simulation for n_cycles.

        Each cycle:
        1. Pick a scenario deterministically
        2. Build cognitive state and signal
        3. Compute UCB adjustments from trail data (the learning)
        4. Route through NEXUS with all 7 modes
        5. Record outcome and deposit trail

        Parameters
        ----------
        n_cycles:
            Number of simulation cycles to run.
        seed:
            Deterministic seed for reproducibility.

        Returns
        -------
        SimulationResult
            Full results including mode activations, UCB adjustments,
            and success rates.
        """
        # Initialize stores
        commitment_store = CommitmentStore(db_path=self._db_path)
        trail_store = TrailStore(db_path=self._db_path)

        # Seed one test commitment so ExecutorMode has something to work with
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        test_commitment = Commitment(
            id="sim-commitment-001",
            raw_message="I'll send the report to Sarah by Friday",
            commitment_text="send the report to Sarah",
            who_to="Sarah",
            source_chat="simulation",
            created_at=base_time,
            updated_at=base_time,
        )
        commitment_store.add(test_commitment, dedup=False)

        result = SimulationResult()
        mode_activations: dict[str, int] = {}

        for cycle in range(n_cycles):
            # (a) Pick scenario deterministically
            scenario_idx = self._deterministic_choice(seed, cycle, len(_SCENARIOS))
            signal_type, state_overrides, success_prob = _SCENARIOS[scenario_idx]

            # (b) Build CognitiveState with scenario overrides
            state = CognitiveState(
                energy=state_overrides.get("energy", "medium"),
                burnout=state_overrides.get("burnout", "GREEN"),
                momentum=state_overrides.get("momentum", "cold_start"),
            )

            # (c) Build Signal
            signal = Signal(
                type=signal_type,
                confidence=0.8,
                source="pattern",
                evidence=f"sim_cycle_{cycle}",
            )
            signals = [signal]

            # (d) Compute UCB adjustments from trail_store (this is the learning!)
            adjustments = compute_ucb_adjustments(signals, trail_store)

            # (e) Create all 7 modes
            modes = [
                AcknowledgerMode(),
                DecomposerMode(),
                ExecutorMode(store=commitment_store),
                GuideMode(),
                ProtectorMode(),
                RedirectorMode(),
                RestorerMode(),
            ]

            # (f) Call route_and_execute
            response = route_and_execute(
                signals, state, modes, trail_adjustments=adjustments
            )

            # (g) Process response
            if response is not None and response.text:
                # Track mode activation
                primary = response.metadata.get("primary", "unknown")
                if isinstance(primary, str):
                    mode_activations[primary] = mode_activations.get(primary, 0) + 1

                # Determine outcome deterministically
                success = self._deterministic_bool(seed, cycle, success_prob)
                outcome = "success" if success else "ignored"

                # Get the context string for trail deposit
                context = signal_type.value

                # Record outcome in trail store
                trail_store.record_outcome(
                    mode=primary,
                    context=context,
                    outcome=outcome,
                    now=base_time + timedelta(minutes=cycle),
                )

                # Deposit trail with strength based on outcome
                strength = 1.0 if success else 0.3
                trail_store.deposit(
                    action=primary,
                    context=context,
                    strength=strength,
                    now=base_time + timedelta(minutes=cycle),
                )

                result.total_outcomes += 1

        # After all cycles: compute final UCB adjustments across all signal types
        all_signal_types = sorted(
            set(st for st, _, _ in _SCENARIOS),
            key=lambda st: st.value,
        )
        all_signals = [
            Signal(type=st, confidence=0.8, source="pattern", evidence="final_check")
            for st in all_signal_types
        ]
        final_adjustments = compute_ucb_adjustments(all_signals, trail_store)

        # Collect success rates for all modes with outcomes
        success_rates: dict[str, float] = {}
        for mode_name in sorted(trail_store.get_all_modes()):
            rate = trail_store.get_success_rate(mode_name)
            if rate is not None:
                success_rates[mode_name] = rate

        result.cycles_completed = n_cycles
        result.mode_activations = dict(sorted(mode_activations.items()))
        result.ucb_adjustments_final = dict(sorted(final_adjustments.items()))
        result.success_rates = dict(sorted(success_rates.items()))

        return result
