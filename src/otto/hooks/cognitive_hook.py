#!/usr/bin/env python3
"""
Orchestra Cognitive Engine Hook for Claude Code
===============================================

This hook runs on every UserPromptSubmit event and processes the message
through the 5-Phase NEXUS Pipeline, with integrated Pheromone Trail support.

Usage:
    python -m orchestra.hooks < input.json

ThinkingMachines [He2025] Compliance:
- Same message -> same signals -> same routing -> same params
- Deterministic execution anchor
- FIXED evaluation order (5 phases)
- FIXED priority order (experts, signals)
- Trail deposits use batch-invariant operations

Output:
- systemMessage with execution anchor and expert guidance
- hookSpecificOutput with full pipeline result + trail context
"""

import json
import sys
from typing import Optional

try:
    from ..cognitive_orchestrator import CognitiveOrchestrator, create_orchestrator
    from ..dashboard_bridge import DashboardBridge, create_bridge
    from ..parameter_locker import ThinkDepth
except ImportError:
    # Fallback for direct execution during development
    try:
        from otto.cognitive_orchestrator import CognitiveOrchestrator, create_orchestrator
        from otto.dashboard_bridge import DashboardBridge, create_bridge
        from otto.parameter_locker import ThinkDepth
    except ImportError as e:
        # Output minimal response if imports fail
        error_result = {
            "systemMessage": f"[Orchestra import error: {e}]"
        }
        print(json.dumps(error_result))
        sys.exit(0)

# Import trail and hook system
try:
    from . import (
        HookRegistry,
        HookEvent,
        HookContext,
        setup_default_hooks,
    )
    from ..trails import get_store, TrailType, Trail, TrailQuery
    TRAILS_AVAILABLE = True
except ImportError:
    try:
        from otto.hooks import (
            HookRegistry,
            HookEvent,
            HookContext,
            setup_default_hooks,
        )
        from otto.trails import get_store, TrailType, Trail, TrailQuery
        TRAILS_AVAILABLE = True
    except ImportError:
        TRAILS_AVAILABLE = False


# Singleton instances
_orchestrator = None
_bridge = None
_hook_registry = None


def get_orchestrator():
    """Get or create singleton orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = create_orchestrator()
    return _orchestrator


def get_bridge():
    """Get or create singleton bridge."""
    global _bridge
    if _bridge is None:
        _bridge = create_bridge(get_orchestrator())
    return _bridge


def get_hook_registry() -> Optional["HookRegistry"]:
    """Get or create singleton hook registry with default hooks."""
    global _hook_registry
    if not TRAILS_AVAILABLE:
        return None
    if _hook_registry is None:
        _hook_registry = setup_default_hooks()
    return _hook_registry


def get_trail_context(file_paths: list[str]) -> str:
    """
    Build trail context string for files being accessed.

    Returns a formatted string with trail signals for each path.
    """
    if not TRAILS_AVAILABLE:
        return ""

    store = get_store()
    context_lines = []

    for path in file_paths:
        trails = store.read_trails(path)
        if trails:
            signals = [f"{t.trail_type.value}:{t.signal}" for t in trails[:5]]  # Top 5
            context_lines.append(f"  {path}: {', '.join(signals)}")

    if context_lines:
        return "\n[Trail Context]\n" + "\n".join(context_lines)
    return ""


def deposit_work_trail(file_path: str, action: str, session_id: str = "claude_code"):
    """Deposit a WORK trail for file activity tracking."""
    if not TRAILS_AVAILABLE:
        return

    store = get_store()
    trail = Trail(
        path=file_path,
        signal=f"{action}",
        trail_type=TrailType.WORK,
        deposited_by=session_id,
    )
    store.deposit(trail)


def build_guidance(result):
    """Build expert-specific guidance."""
    expert = result.routing.expert.value
    paradigm = result.lock.params.paradigm

    expert_guidance = {
        "validator": "EMPATHY FIRST. Acknowledge the struggle. Normalize difficulty.",
        "scaffolder": "BREAK DOWN the task. Provide structure. Reduce scope if needed.",
        "restorer": "EASY WINS mode. Suggest simple tasks. Rest is OK.",
        "refocuser": "GENTLE REDIRECT. Acknowledge tangent, guide back to goal.",
        "celebrator": "ACKNOWLEDGE THE WIN. Provide dopamine boost.",
        "socratic": "GUIDE DISCOVERY. Follow threads. Ask questions.",
        "direct": "MINIMAL FRICTION. Stay out of the way. Direct execution."
    }

    guidance = expert_guidance.get(expert, "Proceed with standard response.")

    if not result.routing.safety_gate_pass:
        guidance = f"SAFETY GATE TRIGGERED. " + guidance

    if paradigm == "Mycelium":
        guidance += " Follow associative threads."
    else:
        guidance += " Stay structured and explicit."

    return guidance


def process_message(user_prompt, context=None):
    """
    Process message through NEXUS pipeline with trail integration.

    Pipeline Flow:
    1. Execute PRE_TOOL_USE hooks (trail context injection)
    2. Process through NEXUS cognitive engine
    3. Build execution anchor with trail context
    4. Queue trail deposits (applied in FLUSH phase)

    [He2025] Compliance:
    - Trail context is deterministically ordered (path ASC, signal ASC)
    - Hook execution order is fixed by priority
    - Trail deposits are queued, not applied during processing
    """
    try:
        bridge = get_bridge()
        result = bridge.process_and_broadcast(user_prompt, context or {})

        # Build system message
        anchor = result.to_anchor()
        guidance = build_guidance(result)

        # Add trail context if available
        trail_context = ""
        if TRAILS_AVAILABLE and context:
            file_paths = context.get("file_paths", [])
            if file_paths:
                trail_context = get_trail_context(file_paths)

        system_message = f"{anchor}\n\n{guidance}{trail_context}"

        # Build additional context with trail info
        additional_context = f"Orchestra: expert={result.routing.expert.value}, tension={result.convergence.epistemic_tension:.2f}"
        if TRAILS_AVAILABLE:
            store = get_store()
            trail_count = store.count_trails()
            additional_context += f", trails={trail_count}"

        return {
            "systemMessage": system_message,
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": additional_context,
                "trailsEnabled": TRAILS_AVAILABLE,
            }
        }

    except Exception as e:
        return {
            "systemMessage": f"[EXEC:error|Direct|Cortex|30000ft|standard] (Error: {str(e)[:50]})"
        }


def main():
    """
    Main entry point for hook.

    Handles:
    - UserPromptSubmit: Process through NEXUS with trail context
    - PostToolUse: Trigger validation hooks and deposit trails
    - PreToolUse: Inject trail context for file operations

    Input JSON schema:
    {
        "event": "UserPromptSubmit" | "PreToolUse" | "PostToolUse",
        "user_prompt": "...",
        "tool_name": "Edit" | "Write" | "Read" | ...,
        "tool_input": {"file_path": "...", ...},
        "session_id": "..."
    }
    """
    try:
        # Read input from stdin
        input_data = json.load(sys.stdin)

        # Determine event type
        event = input_data.get("event", "UserPromptSubmit")
        user_prompt = input_data.get("user_prompt", "")
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})
        session_id = input_data.get("session_id", "claude_code")

        # Handle different event types
        if event == "PostToolUse" and tool_name in ("Edit", "Write"):
            # Run validation hooks after file modifications
            file_path = tool_input.get("file_path", "")
            if file_path and TRAILS_AVAILABLE:
                registry = get_hook_registry()
                if registry:
                    hook_context = HookContext(
                        event=HookEvent.POST_TOOL_USE,
                        tool_name=tool_name,
                        tool_input=tool_input,
                        tool_output={},
                        session_id=session_id,
                    )
                    results = registry.execute(hook_context)

                    # Collect any validation messages
                    messages = []
                    for result in results:
                        if result.message:
                            messages.append(result.message)

                    if messages:
                        print(json.dumps({
                            "systemMessage": "\n".join(messages),
                            "hookSpecificOutput": {
                                "hookEventName": "PostToolUse",
                                "validationRan": True,
                            }
                        }))
                        sys.exit(0)

            print(json.dumps({}))
            sys.exit(0)

        elif event == "PreToolUse" and tool_name in ("Edit", "Write", "Read"):
            # Inject trail context before file operations
            file_path = tool_input.get("file_path", "")
            if file_path and TRAILS_AVAILABLE:
                trail_context = get_trail_context([file_path])
                if trail_context:
                    print(json.dumps({
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "trailContext": trail_context,
                        }
                    }))
                    sys.exit(0)

            print(json.dumps({}))
            sys.exit(0)

        # Default: UserPromptSubmit
        if not user_prompt:
            # No prompt, return empty
            print(json.dumps({}))
            sys.exit(0)

        # Build context with any file paths mentioned
        context = {
            "session_id": session_id,
        }

        # Process through cognitive engine
        result = process_message(user_prompt, context)

        # Output result
        print(json.dumps(result))

    except json.JSONDecodeError:
        # Invalid JSON input
        print(json.dumps({"systemMessage": "[Orchestra: invalid input]"}))

    except Exception as e:
        # General error
        print(json.dumps({"systemMessage": f"[Orchestra error: {str(e)[:100]}]"}))

    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
