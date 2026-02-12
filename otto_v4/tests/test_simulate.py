"""Tests for the deterministic simulation engine."""

from __future__ import annotations

from otto.simulate import SimulationEngine, SimulationResult


def test_simulation_produces_outcomes(tmp_path: object) -> None:
    """A short simulation run produces at least one outcome."""
    db_path = str(tmp_path / "sim.db")  # type: ignore[operator]
    engine = SimulationEngine(db_path=db_path)
    result = engine.run(n_cycles=10, seed=42)
    assert result.total_outcomes > 0
    assert result.cycles_completed == 10


def test_simulation_deterministic(tmp_path: object) -> None:
    """Two runs with the same seed produce identical results."""
    db_a = str(tmp_path / "sim_a.db")  # type: ignore[operator]
    db_b = str(tmp_path / "sim_b.db")  # type: ignore[operator]

    result_a = SimulationEngine(db_path=db_a).run(n_cycles=50, seed=42)
    result_b = SimulationEngine(db_path=db_b).run(n_cycles=50, seed=42)

    assert result_a.cycles_completed == result_b.cycles_completed
    assert result_a.total_outcomes == result_b.total_outcomes
    assert result_a.mode_activations == result_b.mode_activations
    assert result_a.ucb_adjustments_final == result_b.ucb_adjustments_final
    assert result_a.success_rates == result_b.success_rates


def test_ucb_adjustments_change_after_outcomes(tmp_path: object) -> None:
    """After enough cycles, UCB adjustments are non-empty."""
    db_path = str(tmp_path / "sim.db")  # type: ignore[operator]
    engine = SimulationEngine(db_path=db_path)
    result = engine.run(n_cycles=50, seed=42)
    assert len(result.ucb_adjustments_final) > 0


def test_simulation_records_multiple_modes(tmp_path: object) -> None:
    """A 100-cycle run activates at least 4 distinct modes."""
    db_path = str(tmp_path / "sim.db")  # type: ignore[operator]
    engine = SimulationEngine(db_path=db_path)
    result = engine.run(n_cycles=100, seed=42)
    assert len(result.mode_activations) >= 4, (
        f"Expected >= 4 modes, got {len(result.mode_activations)}: "
        f"{sorted(result.mode_activations.keys())}"
    )


def test_simulation_result_summary(tmp_path: object) -> None:
    """summary() returns a readable string with key info."""
    db_path = str(tmp_path / "sim.db")  # type: ignore[operator]
    engine = SimulationEngine(db_path=db_path)
    result = engine.run(n_cycles=20, seed=42)
    text = result.summary()
    assert "cycles" in text.lower()
    assert "outcomes" in text.lower()
