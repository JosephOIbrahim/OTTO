"""Tests for otto metrics command."""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from otto.cli import main
from otto.trails import TrailStore


@patch("otto.cli._get_trail_store")
def test_metrics_no_data(mock_ts, tmp_path):
    mock_ts.return_value = TrailStore(str(tmp_path / "m.db"))
    runner = CliRunner()
    result = runner.invoke(main, ["metrics"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "No outcome data yet" in result.output


@patch("otto.cli._get_trail_store")
def test_metrics_with_data(mock_ts, tmp_path):
    store = TrailStore(str(tmp_path / "m.db"))
    store.record_outcome("executor", "commitment_detected", "success")
    store.record_outcome("executor", "commitment_detected", "success")
    store.record_outcome("executor", "commitment_detected", "ignored")
    mock_ts.return_value = store

    runner = CliRunner()
    result = runner.invoke(main, ["metrics"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "Mode outcomes" in result.output
    assert "executor" in result.output
    assert "success=2" in result.output
    assert "total=3" in result.output


@patch("otto.cli._get_trail_store")
def test_metrics_shows_ucb_adjustments(mock_ts, tmp_path):
    store = TrailStore(str(tmp_path / "m.db"))
    for _ in range(5):
        store.record_outcome("executor", "commitment_detected", "success")
    mock_ts.return_value = store

    runner = CliRunner()
    result = runner.invoke(main, ["metrics"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "UCB1 adjustments" in result.output


@patch("otto.cli._get_trail_store")
def test_metrics_shows_trail_counts(mock_ts, tmp_path):
    store = TrailStore(str(tmp_path / "m.db"))
    store.deposit("executor:nudge", "commitment_detected", 1.0)
    store.record_outcome("executor", "commitment_detected", "success")
    mock_ts.return_value = store

    runner = CliRunner()
    result = runner.invoke(main, ["metrics"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "Trail deposits: 1" in result.output
    assert "Total outcomes: 1" in result.output
