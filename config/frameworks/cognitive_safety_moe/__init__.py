"""
Cognitive Safety MoE Payload - Safety Tier (Always Loaded)
==========================================================

Implements V5 Intervention Experts with Safety Floors.

Source Frameworks:
- Cognitive Safety Framework (specification)
- V5 Intervention Experts (implementation)

This payload is ALWAYS loaded because it contains safety-floor experts
that must respond immediately to safety signals.

Safety Floors (HARD minimums):
- Protector: 10% (never below)
- Decomposer: 5% (never below)
- Restorer: 5% (never below)
"""

from typing import Dict, List, Any

# V5 Expert Archetypes
EXPERTS = {
    "protector": {
        "priority": 1,
        "triggers": ["frustrated", "overwhelmed", "safety", "caps", "help"],
        "display_name": "Safety Guardian",
        "safety_floor": 0.10
    },
    "decomposer": {
        "priority": 2,
        "triggers": ["stuck", "complex", "too_many", "break_down", "simplify"],
        "display_name": "Complexity Simplifier",
        "safety_floor": 0.05
    },
    "restorer": {
        "priority": 3,
        "triggers": ["depleted", "burnout", "tired", "rest", "exhausted"],
        "display_name": "Energy Recharger",
        "safety_floor": 0.05
    },
    "redirector": {
        "priority": 4,
        "triggers": ["tangent", "distracted", "off_topic", "sidetrack"],
        "display_name": "Focus Redirector",
        "safety_floor": 0.00
    },
    "acknowledger": {
        "priority": 5,
        "triggers": ["done", "complete", "milestone", "win", "finished"],
        "display_name": "Progress Celebrator",
        "safety_floor": 0.00
    },
    "guide": {
        "priority": 6,
        "triggers": ["exploring", "what_if", "curious", "learn", "understand"],
        "display_name": "Discovery Guide",
        "safety_floor": 0.00
    },
    "executor": {
        "priority": 7,
        "triggers": ["implement", "code", "do", "execute", "build", "create"],
        "display_name": "Task Builder",
        "safety_floor": 0.00
    }
}

# Aggregate safety floors
SAFETY_FLOORS = {name: config["safety_floor"] for name, config in EXPERTS.items()}

def get_triggers() -> List[str]:
    """Return all trigger words for this payload."""
    triggers = []
    for config in EXPERTS.values():
        triggers.extend(config["triggers"])
    return list(set(triggers))

def detect_expert(task: str) -> Dict[str, Any]:
    """Detect which expert should handle this task.

    Returns activation vector and recommended expert.
    """
    task_lower = task.lower()
    activation = {}

    for expert, config in EXPERTS.items():
        matches = sum(1 for t in config["triggers"] if t in task_lower)
        activation[expert] = min(matches / max(len(config["triggers"]), 1), 1.0)

    # Apply safety floors
    for expert, floor in SAFETY_FLOORS.items():
        activation[expert] = max(activation.get(expert, 0), floor)

    # Normalize
    total = sum(activation.values())
    if total > 0:
        activation = {k: v/total for k, v in activation.items()}

    # Select (argmax with priority tiebreaker)
    sorted_experts = sorted(
        activation.items(),
        key=lambda x: (-x[1], EXPERTS[x[0]]["priority"])
    )
    selected = sorted_experts[0][0]

    return {
        "activation": activation,
        "selected": selected,
        "display_name": EXPERTS[selected]["display_name"],
        "safety_floors_applied": True
    }

__all__ = ["EXPERTS", "SAFETY_FLOORS", "get_triggers", "detect_expert"]
