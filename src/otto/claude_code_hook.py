#!/usr/bin/env python3
"""
Claude Code Hook Integration
=============================

Integrates the CognitiveOrchestrator with Claude Code's hookify system.

This module provides:
1. Hook handler for UserPromptSubmit events
2. Maps orchestrator output to hookify systemMessage format
3. Persists state to ~/.orchestra/state/ for dashboard sync

ThinkingMachines [He2025] Compliance:
- Same message → same signals → same routing → same params
- Deterministic execution anchor in every response
- FIXED evaluation order (5 phases)
- FIXED priority order (experts, signals)

Usage from hookify:
    from otto.claude_code_hook import process_user_message
    result = process_user_message(user_prompt, context)
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Import cognitive orchestrator components
try:
    from .cognitive_orchestrator import CognitiveOrchestrator, NexusResult, create_orchestrator
    from .dashboard_bridge import DashboardBridge, create_bridge
    from .cognitive_state import BurnoutLevel, EnergyLevel
except ImportError:
    # When running as standalone script
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from otto.cognitive_orchestrator import CognitiveOrchestrator, NexusResult, create_orchestrator
    from otto.dashboard_bridge import DashboardBridge, create_bridge
    from otto.cognitive_state import BurnoutLevel, EnergyLevel


# Singleton instances for session persistence
_orchestrator: Optional[CognitiveOrchestrator] = None
_bridge: Optional[DashboardBridge] = None


def get_orchestrator() -> CognitiveOrchestrator:
    """Get or create the singleton orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = create_orchestrator()
    return _orchestrator


def get_bridge() -> DashboardBridge:
    """Get or create the singleton bridge instance."""
    global _bridge
    if _bridge is None:
        _bridge = create_bridge(get_orchestrator())
    return _bridge


def process_user_message(
    user_prompt: str,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Process a user message through the 5-Phase NEXUS Pipeline.

    This is the main entry point for hookify integration.

    Args:
        user_prompt: The user's message text
        context: Optional context dict (active project, etc.)

    Returns:
        Dict with:
        - systemMessage: Execution anchor for Claude to follow
        - hookSpecificOutput: Full pipeline result for debugging
    """
    try:
        bridge = get_bridge()

        # Run through NEXUS pipeline and broadcast to dashboard
        result = bridge.process_and_broadcast(user_prompt, context or {})

        # Format response for hookify
        return format_hook_response(result)

    except Exception as e:
        # On error, return minimal response that doesn't block Claude
        return {
            "systemMessage": f"[EXEC:error|Direct|Cortex|30000ft|standard] (Cognitive engine error: {str(e)[:100]})"
        }


def format_hook_response(result: NexusResult) -> Dict[str, Any]:
    """
    Format NexusResult for hookify systemMessage.

    The systemMessage tells Claude what parameters to use for this response.
    """
    # Get anchor string (the deterministic execution parameters)
    anchor = result.to_anchor()

    # Build context-aware guidance based on routing
    guidance = build_guidance(result)

    # Combine into systemMessage
    system_message = f"""
{anchor}

{guidance}
""".strip()

    return {
        "systemMessage": system_message,
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "pipeline_result": {
                "anchor": anchor,
                "expert": result.routing.expert.value,
                "paradigm": result.lock.params.paradigm,
                "safety_gate_pass": result.routing.safety_gate_pass,
                "convergence": {
                    "tension": result.convergence.epistemic_tension,
                    "attractor": result.convergence.attractor_basin.value,
                    "converged": result.convergence.converged
                }
            }
        }
    }


def build_guidance(result: NexusResult) -> str:
    """
    Build context-aware guidance based on routing result.

    This provides Claude with expert-specific instructions.
    """
    expert = result.routing.expert.value
    trigger = result.routing.trigger
    paradigm = result.lock.params.paradigm

    # Expert-specific guidance
    expert_guidance = {
        "validator": "EMPATHY FIRST. Acknowledge the struggle. Normalize difficulty. Do not immediately try to solve.",
        "scaffolder": "BREAK DOWN the task. Provide structure. Reduce scope if needed. One small step at a time.",
        "restorer": "EASY WINS mode. Suggest simple tasks. Rest is OK. Recovery without guilt.",
        "refocuser": "GENTLE REDIRECT. Acknowledge the tangent, then guide back to the goal.",
        "celebrator": "ACKNOWLEDGE THE WIN. Provide dopamine boost. Celebrate before moving on.",
        "socratic": "GUIDE DISCOVERY. Follow threads. Ask questions. Let them explore.",
        "direct": "MINIMAL FRICTION. Stay out of the way. Direct execution."
    }

    guidance = expert_guidance.get(expert, "Proceed with standard response.")

    # Add safety redirect info if applicable
    if not result.routing.safety_gate_pass:
        guidance = f"SAFETY GATE TRIGGERED ({result.routing.safety_redirect}). " + guidance

    # Add paradigm guidance
    if paradigm == "Mycelium":
        guidance += " Follow associative threads. Emergent thinking allowed."
    else:
        guidance += " Stay structured and explicit."

    # Add convergence info for context
    if result.convergence.converged:
        guidance += f" (Converged to {result.convergence.attractor_basin.value} attractor)"
    elif result.convergence.epistemic_tension > 0.3:
        guidance += f" (High epistemic tension: {result.convergence.epistemic_tension:.2f})"

    return guidance


def update_state_from_feedback(
    burnout: Optional[str] = None,
    energy: Optional[str] = None
) -> None:
    """
    Update cognitive state from external feedback.

    This allows the dashboard or user to adjust state.

    Args:
        burnout: Burnout level (GREEN, YELLOW, ORANGE, RED)
        energy: Energy level (high, medium, low, depleted)
    """
    bridge = get_bridge()

    if burnout:
        bridge.set_burnout(burnout)

    if energy:
        bridge.set_energy(energy)


def reset_session() -> Dict[str, Any]:
    """Reset the cognitive session (new task/session)."""
    global _orchestrator, _bridge
    _orchestrator = None
    _bridge = None
    return {"systemMessage": "Cognitive session reset. Fresh start."}


# =============================================================================
# CLI Entry Point (for testing)
# =============================================================================

def main():
    """CLI entry point for testing the hook."""
    import argparse

    parser = argparse.ArgumentParser(description="Test cognitive orchestrator hook")
    parser.add_argument("message", nargs="?", default="Help me implement this feature",
                        help="Test message to process")
    parser.add_argument("--reset", action="store_true", help="Reset session")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.reset:
        result = reset_session()
    else:
        result = process_user_message(args.message)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(result.get("systemMessage", "No message"))


if __name__ == "__main__":
    main()
