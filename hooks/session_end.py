"""
Session End Hook
================

Handles state persistence and session export when a Claude Code session ends.

Responsibilities:
1. Persist final cognitive state
2. Export session to .usda for debugging/analysis
3. Generate session summary
4. Clean up temporary state

This hook runs when the session ends (explicit exit or timeout).
"""

import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

# Add Orchestra to path if needed
orchestra_path = Path(__file__).parent.parent / "src"
if str(orchestra_path) not in sys.path:
    sys.path.insert(0, str(orchestra_path))

from otto.cognitive_stage import CognitiveStage, create_cognitive_stage

logger = logging.getLogger(__name__)


@dataclass
class SessionSummary:
    """Summary of the completed session."""
    session_id: str
    start_time: str
    end_time: str
    duration_minutes: float
    exchange_count: int
    tasks_completed: int
    final_burnout: str
    final_energy: str
    final_momentum: str
    peak_epistemic_tension: float
    exported_usda: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_minutes": self.duration_minutes,
            "exchange_count": self.exchange_count,
            "tasks_completed": self.tasks_completed,
            "final_burnout": self.final_burnout,
            "final_energy": self.final_energy,
            "final_momentum": self.final_momentum,
            "peak_epistemic_tension": self.peak_epistemic_tension,
            "exported_usda": self.exported_usda,
        }

    def format_for_display(self) -> str:
        """Format summary for display."""
        lines = [
            "═" * 50,
            "SESSION SUMMARY",
            "═" * 50,
            f"Duration: {self.duration_minutes:.1f} minutes",
            f"Exchanges: {self.exchange_count}",
            f"Tasks completed: {self.tasks_completed}",
            "",
            "Final State:",
            f"  Burnout: {self.final_burnout}",
            f"  Energy: {self.final_energy}",
            f"  Momentum: {self.final_momentum}",
            "",
            f"Peak tension: {self.peak_epistemic_tension:.2f}",
        ]

        if self.exported_usda:
            lines.append(f"\nSession exported to: {self.exported_usda}")

        lines.append("═" * 50)
        return "\n".join(lines)


@dataclass
class SessionEndResult:
    """Result from session end hook."""
    summary: SessionSummary
    state_persisted: bool
    export_path: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary.to_dict(),
            "state_persisted": self.state_persisted,
            "export_path": self.export_path,
        }


# =============================================================================
# Session End Hook Implementation
# =============================================================================

def on_session_end(export_usda: bool = True,
                   session_id: str = None) -> SessionEndResult:
    """
    Handle session end: persist state and generate summary.

    This hook:
    1. Captures final cognitive state
    2. Generates session summary
    3. Exports session to .usda (if enabled)
    4. Persists state for cross-session continuity

    Args:
        export_usda: Whether to export session to .usda file
        session_id: Optional session identifier

    Returns:
        SessionEndResult with summary and export info
    """
    # Load cognitive stage
    stage = create_cognitive_stage()
    state = stage.get_cognitive_state()

    # Generate session ID if not provided
    if not session_id:
        session_id = stage.checksum()[:8]

    # Calculate session duration
    end_time = datetime.now()
    start_timestamp = state.session_start
    start_time = datetime.fromtimestamp(start_timestamp)
    duration_minutes = (end_time - start_time).total_seconds() / 60

    # Export to .usda if enabled
    export_path = None
    if export_usda:
        filename = f"session_{end_time.strftime('%Y-%m-%d_%H%M%S')}_{session_id}.usda"
        export_path = str(stage.export(filename))
        logger.info(f"Exported session to {export_path}")

    # Generate summary
    summary = SessionSummary(
        session_id=session_id,
        start_time=start_time.isoformat(),
        end_time=end_time.isoformat(),
        duration_minutes=duration_minutes,
        exchange_count=state.exchange_count,
        tasks_completed=state.tasks_completed,
        final_burnout=state.burnout_level.value,
        final_energy=state.energy_level.value,
        final_momentum=state.momentum_phase.value,
        peak_epistemic_tension=state.epistemic_tension,  # Would need tracking for true peak
        exported_usda=export_path,
    )

    # Persist state
    stage.save()
    state_persisted = True

    # Log summary
    logger.info(f"Session ended: {summary.exchange_count} exchanges, "
                f"{summary.tasks_completed} tasks, "
                f"burnout={summary.final_burnout}")

    return SessionEndResult(
        summary=summary,
        state_persisted=state_persisted,
        export_path=export_path,
    )


def persist_and_export(session_id: str = None) -> SessionEndResult:
    """
    Persist current state and export to .usda.

    Convenience function for explicit save points.
    """
    return on_session_end(export_usda=True, session_id=session_id)


def persist_only() -> bool:
    """
    Just persist state without export.

    Returns:
        True if successful
    """
    stage = create_cognitive_stage()
    stage.save()
    return True


def get_session_stats() -> Dict[str, Any]:
    """
    Get current session statistics without ending the session.

    Returns:
        Dict with session stats
    """
    stage = create_cognitive_stage()
    state = stage.get_cognitive_state()

    start_time = datetime.fromtimestamp(state.session_start)
    duration_minutes = (datetime.now() - start_time).total_seconds() / 60

    return {
        "duration_minutes": duration_minutes,
        "exchange_count": state.exchange_count,
        "tasks_completed": state.tasks_completed,
        "burnout_level": state.burnout_level.value,
        "energy_level": state.energy_level.value,
        "momentum_phase": state.momentum_phase.value,
        "epistemic_tension": state.epistemic_tension,
        "tangent_budget_remaining": state.tangent_budget,
    }


def reset_session() -> bool:
    """
    Reset session state to defaults.

    Use with caution - this clears the current session.

    Returns:
        True if successful
    """
    stage = create_cognitive_stage()
    stage._state_manager.reset()
    stage._backend.create_stage()  # Reset stage
    stage.save()

    logger.info("Session state reset to defaults")
    return True


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    """Run session end from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="Orchestra Session End Hook")
    parser.add_argument("--no-export", action="store_true",
                        help="Skip .usda export")
    parser.add_argument("--session-id", type=str,
                        help="Custom session identifier")
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON")
    parser.add_argument("--stats-only", action="store_true",
                        help="Just show stats, don't end session")
    args = parser.parse_args()

    if args.stats_only:
        stats = get_session_stats()
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            for key, value in stats.items():
                print(f"{key}: {value}")
    else:
        result = on_session_end(
            export_usda=not args.no_export,
            session_id=args.session_id,
        )

        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(result.summary.format_for_display())
