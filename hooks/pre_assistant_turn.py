"""
Pre-Assistant Turn Hook
=======================

Injects cognitive context into Claude's prompt before each response.

Responsibilities:
1. Detect signals from user message (PRISM)
2. Check for tensions to surface
3. Generate cognitive context for prompt injection
4. Check for safety interventions needed
5. Make work/delegate/protect decisions for tasks

This hook runs BEFORE Claude generates a response, allowing it to
adapt behavior based on cognitive state.

Philosophy: "Orchestra helps you finish projects by knowing when to
do the work yourself, when to delegate to agents, and when to protect your flow."
"""

import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

# Add Orchestra to path if needed
orchestra_path = Path(__file__).parent.parent / "src"
if str(orchestra_path) not in sys.path:
    sys.path.insert(0, str(orchestra_path))

from otto.cognitive_stage import CognitiveStage, create_cognitive_stage
from otto.prism_detector import PRISMDetector, SignalVector, create_detector
from otto.tension_surfacer import TensionSurfacer, TensionReport, create_tension_surfacer
from otto.cognitive_support import CognitiveSupportManager, CognitiveCheckResult
from otto.decision_engine import DecisionEngine, TaskRequest, TaskCategory, ExecutionPlan
from otto.agent_coordinator import DecisionMode

logger = logging.getLogger(__name__)


@dataclass
class PreTurnResult:
    """Result from pre-assistant-turn hook."""
    cognitive_context: str
    signals: Optional[Dict[str, Any]]
    tensions: Optional[Dict[str, Any]]
    cognitive_check: Optional[Dict[str, Any]]
    should_intervene: bool
    intervention_message: Optional[str]
    # Agent coordination fields
    execution_plan: Optional[Dict[str, Any]] = None
    decision_mode: Optional[str] = None  # work, delegate, protect
    agent_suggestion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cognitive_context": self.cognitive_context,
            "signals": self.signals,
            "tensions": self.tensions,
            "cognitive_check": self.cognitive_check,
            "should_intervene": self.should_intervene,
            "intervention_message": self.intervention_message,
            "execution_plan": self.execution_plan,
            "decision_mode": self.decision_mode,
            "agent_suggestion": self.agent_suggestion,
        }


# =============================================================================
# Pre-Assistant Turn Hook Implementation
# =============================================================================

def on_pre_assistant_turn(user_message: str,
                          context: Dict[str, Any] = None) -> PreTurnResult:
    """
    Process user message before Claude responds.

    This hook:
    1. Detects signals in user message (PRISM)
    2. Updates cognitive state based on signals
    3. Checks for tensions to surface
    4. Checks cognitive constraints
    5. Generates context for prompt injection

    Args:
        user_message: The user's message text
        context: Optional additional context (e.g., from previous turns)

    Returns:
        PreTurnResult with context and any interventions needed
    """
    context = context or {}

    # Load cognitive stage
    stage = create_cognitive_stage()

    # Detect signals in user message
    detector = create_detector()
    signals = detector.detect(user_message, context)

    # Quick safety check
    needs_intervention, reason = detector.quick_safety_check(user_message)

    # Update state from signals
    _update_state_from_signals(stage, signals)

    # Check for tensions
    surfacer = create_tension_surfacer(stage)
    tension_report = surfacer.detect(signals, user_message)

    # Check cognitive constraints
    support = CognitiveSupportManager()
    state = stage.get_cognitive_state()
    cognitive_check = support.check(state, text=user_message)

    # Determine if intervention needed
    should_intervene = (
        needs_intervention or
        tension_report.should_surface or
        cognitive_check.recovery_needed or
        cognitive_check.body_check_needed
    )

    # Build intervention message if needed
    intervention_message = None
    if should_intervene:
        intervention_message = _build_intervention_message(
            reason, tension_report, cognitive_check
        )

    # Generate cognitive context
    cognitive_context = _build_cognitive_context(stage, signals, tension_report)

    # === Agent Coordination (work/delegate/protect) ===
    execution_plan = None
    decision_mode = None
    agent_suggestion = None

    # Analyze task for potential delegation
    task_request = analyze_for_delegation(user_message, signals)
    if task_request:
        engine = DecisionEngine(stage)
        plan = engine.process_task(task_request)
        execution_plan = {
            "mode": plan.decision.mode.value,
            "rationale": plan.decision.rationale,
            "steps": plan.steps,
            "checksum": plan.checksum
        }
        decision_mode = plan.decision.mode.value
        agent_suggestion = get_agent_suggestion(plan)

        # Add agent suggestion to cognitive context if relevant
        if agent_suggestion and plan.decision.mode == DecisionMode.DELEGATE:
            cognitive_context += f"\n[AGENT SUGGESTION: {agent_suggestion}]"

    # Save updated state
    stage.save()

    return PreTurnResult(
        cognitive_context=cognitive_context,
        signals=signals.to_dict() if signals else None,
        tensions=tension_report.to_dict() if tension_report.has_tensions() else None,
        cognitive_check=cognitive_check.to_dict(),
        should_intervene=should_intervene,
        intervention_message=intervention_message,
        execution_plan=execution_plan,
        decision_mode=decision_mode,
        agent_suggestion=agent_suggestion,
    )


def get_cognitive_context(user_message: str = "") -> str:
    """
    Get cognitive context for prompt injection.

    Lighter-weight version that just returns the context string.
    """
    result = on_pre_assistant_turn(user_message)
    return result.cognitive_context


def _update_state_from_signals(stage: CognitiveStage, signals: SignalVector) -> None:
    """Update cognitive state based on detected signals."""
    # Update burnout from emotional signals
    if signals.emotional_score >= 0.7:
        stage.set_session_value("burnout_level", "orange")
    elif signals.emotional_score >= 0.9:
        stage.set_session_value("burnout_level", "red")

    # Update mode from mode signals
    if signals.mode_detected:
        stage.set_mode(signals.mode_detected)

    # Update energy from energy signals
    if signals.energy_state:
        stage.set_session_value("energy_level", signals.energy_state)

    # Increment exchange count
    state = stage.get_cognitive_state()
    state.increment_exchange(rapid=True)  # Assume rapid until proven otherwise


def _build_intervention_message(safety_reason: Optional[str],
                                 tension_report: TensionReport,
                                 cognitive_check: CognitiveCheckResult) -> str:
    """Build intervention message from various sources."""
    messages = []

    # Safety intervention
    if safety_reason:
        if "caps" in safety_reason:
            messages.append("I notice some frustration. Let's pause and make sure we're on the same page.")
        elif "overwhelmed" in safety_reason:
            messages.append("That sounds like a lot. Let's break this down into smaller pieces.")
        elif "depleted" in safety_reason:
            messages.append("You sound exhausted. Want to take a break or switch to something easier?")

    # Tension surfacing
    if tension_report.should_surface:
        tension_str = tension_report.tensions[0].format_for_display() if tension_report.tensions else ""
        if tension_str:
            messages.append(tension_str)

    # Cognitive check interventions
    if cognitive_check.body_check_needed:
        messages.append(cognitive_check.body_check_message or
                       "Quick check: How are you doing? Water? Stretch?")

    if cognitive_check.recovery_needed:
        messages.append("You're running on empty. What would help right now?")

    if cognitive_check.perfectionism_detected:
        messages.append(cognitive_check.intervention_message or
                       "Is this blocking ship? Ship it. Polish later.")

    return "\n\n".join(messages) if messages else None


def _build_cognitive_context(stage: CognitiveStage,
                             signals: SignalVector,
                             tension_report: TensionReport) -> str:
    """Build cognitive context for prompt injection."""
    # Get base context from stage
    base_context = stage.get_prompt_context()

    # Add signal summary
    priority_signal = signals.get_priority_signal() if signals else None

    lines = [base_context]

    if priority_signal:
        category, signal, score = priority_signal
        lines.append(f"[SIGNAL: {category.name}:{signal} ({score:.2f})]")

    if tension_report.has_tensions():
        lines.append(f"[TENSIONS: {len(tension_report.tensions)} pending]")

    return "\n".join(lines)


# =============================================================================
# Task Analysis and Agent Coordination
# =============================================================================

def analyze_for_delegation(message: str, signals: SignalVector) -> Optional[TaskRequest]:
    """
    Analyze if message represents a delegatable task.

    Returns TaskRequest if task could benefit from agent delegation,
    None if it should be handled directly.
    """
    # Keywords that suggest specific task categories
    category_keywords = {
        TaskCategory.EXPLORATION: ["find", "search", "where", "look for", "locate", "understand"],
        TaskCategory.IMPLEMENTATION: ["implement", "create", "add", "build", "write", "code"],
        TaskCategory.DEBUGGING: ["debug", "fix", "broken", "error", "bug", "not working"],
        TaskCategory.REVIEW: ["review", "check", "analyze", "audit"],
        TaskCategory.RESEARCH: ["research", "learn about", "documentation", "how does"],
        TaskCategory.PLANNING: ["plan", "design", "architect", "strategy"],
    }

    message_lower = message.lower()

    # Detect category
    detected_category = TaskCategory.SIMPLE
    for category, keywords in category_keywords.items():
        if any(kw in message_lower for kw in keywords):
            detected_category = category
            break

    # Simple messages don't need delegation analysis
    word_count = len(message.split())
    if word_count < 5 and detected_category == TaskCategory.SIMPLE:
        return None

    # Detect scope from message complexity
    if word_count > 50 or "all" in message_lower or "across" in message_lower:
        scope = "large"
    elif word_count > 20 or "multiple" in message_lower:
        scope = "medium"
    else:
        scope = "small"

    # Detect urgency from signals
    urgency = "normal"
    if signals.emotional_score > 0.5:
        urgency = "high"
    elif "urgent" in message_lower or "asap" in message_lower:
        urgency = "high"

    return TaskRequest(
        description=message[:200],  # Truncate for summary
        category=detected_category,
        files_involved=[],  # Will be populated by agent if needed
        requires_user_input=False,
        estimated_scope=scope,
        urgency=urgency
    )


def get_agent_suggestion(plan: ExecutionPlan) -> Optional[str]:
    """Generate human-readable agent suggestion from execution plan."""
    if plan.decision.mode == DecisionMode.WORK:
        return None  # No suggestion for direct work

    if plan.decision.mode == DecisionMode.PROTECT:
        return f"Flow protection active. Task queued for: {plan.decision.protect_until}"

    if plan.decision.mode == DecisionMode.DELEGATE:
        if plan.decision.agent_count == 1:
            return (f"This task could benefit from an agent. "
                   f"Suggestion: spawn {plan.decision.agent_type.value} agent. "
                   f"Rationale: {plan.decision.rationale}")
        else:
            return (f"Complex task detected. "
                   f"Suggestion: spawn {plan.decision.agent_count} parallel {plan.decision.agent_type.value} agents. "
                   f"Rationale: {plan.decision.rationale}")

    return None


# =============================================================================
# Expert Routing (Cognitive Safety MoE)
# =============================================================================

def get_recommended_expert(signals: SignalVector,
                           cognitive_check: CognitiveCheckResult) -> Tuple[str, str]:
    """
    Get recommended expert based on signals (Cognitive Safety MoE routing).

    Returns:
        (expert_name, reason) tuple
    """
    # First-match routing (FIXED priority order)
    priority_signal = signals.get_priority_signal()
    category, signal, score = priority_signal

    # 1. Validator for frustration/caps
    if category.name == "EMOTIONAL" and score >= 0.5:
        return ("validator", f"Emotional signal detected: {signal}")

    # 2. Scaffolder for overwhelmed/stuck
    if signal in ("overwhelmed", "stuck"):
        return ("scaffolder", f"Need breakdown: {signal}")

    # 3. Restorer for energy depletion
    if cognitive_check.recovery_needed or signals.energy_state == "depleted":
        return ("restorer", "Energy depleted, recovery mode")

    # 4. Socratic for exploring
    if signals.mode_detected == "exploring":
        return ("socratic", "Exploring mode detected")

    # 5. Direct for focused
    if signals.mode_detected == "focused":
        return ("direct", "Focused mode, minimal friction")

    # Default to direct
    return ("direct", "Default routing")


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    """Run pre-assistant-turn from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="Orchestra Pre-Assistant Turn Hook")
    parser.add_argument("message", nargs="?", default="",
                        help="User message to process")
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON")
    args = parser.parse_args()

    result = on_pre_assistant_turn(args.message)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(result.cognitive_context)
        if result.should_intervene:
            print("\n---INTERVENTION---")
            print(result.intervention_message)
