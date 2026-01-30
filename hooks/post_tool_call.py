"""
Post-Tool Call Hook
===================

Updates cognitive state after each tool call based on outcomes.

Responsibilities:
1. Track task completion (update momentum)
2. Detect errors/frustration signals
3. Update burnout based on outcomes
4. Check for body check timing
5. Handle agent results (work/delegate/protect)

This hook runs AFTER each tool call, allowing state to adapt
based on what actually happened.

Philosophy: "Orchestra helps you finish projects by knowing when to
do the work yourself, when to delegate to agents, and when to protect your flow."
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
from otto.prism_detector import create_detector
from otto.cognitive_state import MomentumPhase, BurnoutLevel
from otto.decision_engine import DecisionEngine
from otto.agent_coordinator import AgentCoordinator, DecisionMode, QueuedResult

logger = logging.getLogger(__name__)


@dataclass
class ToolOutcome:
    """Outcome of a tool call."""
    tool_name: str
    success: bool
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    output_length: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
            "output_length": self.output_length,
        }


@dataclass
class PostToolResult:
    """Result from post-tool-call hook."""
    state_updated: bool
    momentum_phase: str
    burnout_level: str
    tasks_completed: int
    body_check_due: bool
    message: Optional[str] = None
    # Agent coordination fields
    agent_results_queued: int = 0
    agent_results_ready: Optional[str] = None
    flow_protection_active: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state_updated": self.state_updated,
            "momentum_phase": self.momentum_phase,
            "burnout_level": self.burnout_level,
            "tasks_completed": self.tasks_completed,
            "body_check_due": self.body_check_due,
            "message": self.message,
            "agent_results_queued": self.agent_results_queued,
            "agent_results_ready": self.agent_results_ready,
            "flow_protection_active": self.flow_protection_active,
        }


# =============================================================================
# Tool Categories
# =============================================================================

# Tools that indicate task completion
COMPLETION_TOOLS = {
    "Write", "Edit", "NotebookEdit",  # File modifications
    "Bash",  # Command execution (if successful)
}

# Tools that might indicate struggle
STRUGGLE_INDICATORS = {
    "multiple_reads": 3,  # Reading same file multiple times
    "repeated_greps": 3,  # Searching for same pattern
    "rapid_edits": 5,     # Many quick edits (might be stuck)
}


# =============================================================================
# Post-Tool Call Hook Implementation
# =============================================================================

def on_post_tool_call(tool_name: str,
                      success: bool,
                      error_message: str = None,
                      duration_ms: int = None,
                      context: Dict[str, Any] = None) -> PostToolResult:
    """
    Update state after a tool call.

    This hook:
    1. Records tool outcome
    2. Updates momentum on successful completions
    3. Escalates burnout on repeated errors
    4. Checks body check timing

    Args:
        tool_name: Name of the tool that was called
        success: Whether the tool call succeeded
        error_message: Error message if failed
        duration_ms: Duration of the call in milliseconds
        context: Additional context

    Returns:
        PostToolResult with updated state info
    """
    context = context or {}

    # Load cognitive stage
    stage = create_cognitive_stage()
    state = stage.get_cognitive_state()

    outcome = ToolOutcome(
        tool_name=tool_name,
        success=success,
        error_message=error_message,
        duration_ms=duration_ms,
    )

    state_updated = False
    message = None

    # Track successful completion
    if success and tool_name in COMPLETION_TOOLS:
        state.complete_task()
        state_updated = True
        logger.debug(f"Task completed via {tool_name}, total={state.tasks_completed}")

    # Handle errors
    if not success:
        state_updated = True
        error_count = context.get("consecutive_errors", 0) + 1
        context["consecutive_errors"] = error_count

        # Escalate burnout on repeated errors
        if error_count >= 3:
            state.escalate_burnout()
            message = f"Multiple errors encountered. Current burnout: {state.burnout_level.value}"
            logger.warning(f"Burnout escalated to {state.burnout_level.value} after {error_count} errors")
    else:
        # Reset error count on success
        context["consecutive_errors"] = 0

    # Check for struggle patterns
    struggle_message = _check_struggle_patterns(tool_name, context)
    if struggle_message:
        message = struggle_message

    # Check body check timing
    body_check_due = state.check_body_check_needed()
    if body_check_due:
        message = "Quick check: You've been at this a while. Water? Stretch?"

    # Save state
    stage.save()

    return PostToolResult(
        state_updated=state_updated,
        momentum_phase=state.momentum_phase.value,
        burnout_level=state.burnout_level.value,
        tasks_completed=state.tasks_completed,
        body_check_due=body_check_due,
        message=message,
    )


def update_state_from_tool(outcome: ToolOutcome,
                           context: Dict[str, Any] = None) -> PostToolResult:
    """
    Alternative entry point using ToolOutcome dataclass.
    """
    return on_post_tool_call(
        tool_name=outcome.tool_name,
        success=outcome.success,
        error_message=outcome.error_message,
        duration_ms=outcome.duration_ms,
        context=context,
    )


def _check_struggle_patterns(tool_name: str,
                             context: Dict[str, Any]) -> Optional[str]:
    """
    Check for patterns indicating user/system is struggling.

    Returns intervention message if struggle detected.
    """
    # Track tool calls in context
    tool_history = context.setdefault("tool_history", [])
    tool_history.append({
        "tool": tool_name,
        "timestamp": datetime.now().isoformat(),
    })

    # Keep only recent history
    tool_history = tool_history[-20:]
    context["tool_history"] = tool_history

    # Count recent tool types
    recent_tools = [t["tool"] for t in tool_history[-10:]]

    # Check for repeated reads
    read_count = sum(1 for t in recent_tools if t == "Read")
    if read_count >= STRUGGLE_INDICATORS["multiple_reads"]:
        return "Noticing multiple file reads - are we looking for something specific? Maybe try Grep or Glob?"

    # Check for repeated greps
    grep_count = sum(1 for t in recent_tools if t == "Grep")
    if grep_count >= STRUGGLE_INDICATORS["repeated_greps"]:
        return "Multiple search attempts - would it help to step back and clarify what we're looking for?"

    # Check for rapid edits
    edit_count = sum(1 for t in recent_tools if t in ("Edit", "Write"))
    if edit_count >= STRUGGLE_INDICATORS["rapid_edits"]:
        return "Many quick edits - everything OK? Want to step back and plan before continuing?"

    return None


def mark_task_complete() -> PostToolResult:
    """
    Explicitly mark a task as complete.

    Use when task completion isn't tied to a specific tool call.
    """
    stage = create_cognitive_stage()
    state = stage.get_cognitive_state()

    state.complete_task()
    stage.save()

    return PostToolResult(
        state_updated=True,
        momentum_phase=state.momentum_phase.value,
        burnout_level=state.burnout_level.value,
        tasks_completed=state.tasks_completed,
        body_check_due=state.check_body_check_needed(),
        message=None,
    )


def acknowledge_body_check() -> None:
    """
    Acknowledge body check, reset rapid exchange counter.
    """
    stage = create_cognitive_stage()
    state = stage.get_cognitive_state()

    state.reset_rapid_exchanges()
    stage.save()

    logger.info("Body check acknowledged, rapid exchange counter reset")


# =============================================================================
# Agent Result Handling
# =============================================================================

# Global coordinator instance for agent tracking across calls
_coordinator: Optional[AgentCoordinator] = None

def get_coordinator() -> AgentCoordinator:
    """Get or create the global agent coordinator."""
    global _coordinator
    if _coordinator is None:
        stage = create_cognitive_stage()
        _coordinator = AgentCoordinator(stage)
    return _coordinator


def on_agent_completed(agent_id: str, result: Any) -> PostToolResult:
    """
    Handle completion of an agent task.

    This is the entry point for agent results. It:
    1. Checks if flow protection is active
    2. Either queues result or formats for presentation
    3. Updates cognitive state

    Args:
        agent_id: ID of the completed agent
        result: Result from the agent

    Returns:
        PostToolResult with agent result info
    """
    stage = create_cognitive_stage()
    state = stage.get_cognitive_state()
    coordinator = get_coordinator()

    # Handle the agent result
    queued = coordinator.agent_completed(agent_id, result)

    # Track task completion
    state.complete_task()

    # Prepare result
    agent_results_ready = None
    if queued is not None:
        # Result is ready for immediate presentation
        context = coordinator.get_cognitive_context()
        agent_results_ready = coordinator.format_results_for_state([queued], context)

    # Check for more queued results
    status = coordinator.get_status()

    stage.save()

    return PostToolResult(
        state_updated=True,
        momentum_phase=state.momentum_phase.value,
        burnout_level=state.burnout_level.value,
        tasks_completed=state.tasks_completed,
        body_check_due=state.check_body_check_needed(),
        message=None,
        agent_results_queued=status["queued_results"],
        agent_results_ready=agent_results_ready,
        flow_protection_active=status["flow_protection"],
    )


def check_agent_results() -> Optional[str]:
    """
    Check if queued agent results are ready for presentation.

    Called at natural break points to deliver results that were
    queued during flow protection.

    Returns:
        Formatted results string if ready, None otherwise
    """
    coordinator = get_coordinator()

    # Check if we should deliver queued results
    if coordinator.check_flow_exit():
        results = coordinator.get_queued_results()
        if results:
            context = coordinator.get_cognitive_context()
            return coordinator.format_results_for_state(results, context)

    return None


def get_agent_status() -> Dict[str, Any]:
    """
    Get current agent coordination status.

    Returns status dict with:
    - active_agents: Count of running agents
    - queued_results: Count of pending results
    - flow_protection: Whether flow protection is active
    - can_spawn: Whether new agents can be spawned
    """
    coordinator = get_coordinator()
    return coordinator.get_status()


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    """Run post-tool-call from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="Orchestra Post-Tool Call Hook")
    parser.add_argument("tool_name", help="Name of the tool")
    parser.add_argument("--success", action="store_true", default=True,
                        help="Whether tool succeeded")
    parser.add_argument("--error", type=str, help="Error message if failed")
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON")
    args = parser.parse_args()

    result = on_post_tool_call(
        tool_name=args.tool_name,
        success=args.success and not args.error,
        error_message=args.error,
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"Momentum: {result.momentum_phase}")
        print(f"Burnout: {result.burnout_level}")
        print(f"Tasks completed: {result.tasks_completed}")
        if result.message:
            print(f"\n{result.message}")
