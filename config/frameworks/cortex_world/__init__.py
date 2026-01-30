"""
Cortex World Payload - Deferred Tier
====================================

Implements world modeling and causal inference from CORTEX Framework.

Source Frameworks:
- Cortex_Mycelium Framework (CORTEX paradigm)

Key Features:
- Entity extraction
- Causal chain construction
- Dependency graph building
- Paradigm selection (Cortex vs Mycelium)
"""

from typing import Dict, List, Any, Tuple

# Paradigms
PARADIGMS = {
    "cortex": {
        "name": "Cortex (Hierarchical)",
        "description": "Structured, explicit, controlled reasoning",
        "triggers": ["plan", "debug", "analyze", "step by step"],
        "characteristics": ["top-down", "explicit", "sequential"]
    },
    "mycelium": {
        "name": "Mycelium (Distributed)",
        "description": "Associative, emergent, exploratory reasoning",
        "triggers": ["explore", "what if", "brainstorm", "creative"],
        "characteristics": ["bottom-up", "emergent", "parallel"]
    }
}

# Energy dimensions for world state
ENERGY_DIMENSIONS = ["correctness", "efficiency", "maintainability", "style"]

def get_triggers() -> List[str]:
    """Triggers for loading this payload."""
    return ["entity", "causal", "graph", "dependency", "world model",
            "relationship", "structure"]

def extract_entities(task: str) -> List[str]:
    """Extract entities from task text.

    Simple heuristic: capitalized words that aren't at sentence start.
    """
    words = task.split()
    entities = []

    for i, word in enumerate(words):
        # Skip first word of sentences
        if i > 0 and words[i-1].endswith('.'):
            continue
        # Check if capitalized
        if word and word[0].isupper() and len(word) > 1:
            # Clean punctuation
            clean = word.strip('.,!?()[]{}')
            if clean and clean not in entities:
                entities.append(clean)

    return entities

def build_causal_chains(entities: List[str]) -> List[Dict[str, Any]]:
    """Build potential causal chains between entities.

    Simple heuristic: sequential entities may have causal relationship.
    """
    chains = []

    for i in range(len(entities) - 1):
        chains.append({
            "cause": entities[i],
            "effect": entities[i + 1],
            "confidence": 0.7,  # Default confidence
            "type": "sequential"
        })

    return chains

def detect_paradigm(task: str) -> str:
    """Detect appropriate paradigm from task signals."""
    task_lower = task.lower()

    for paradigm_name, config in PARADIGMS.items():
        if any(t in task_lower for t in config["triggers"]):
            return paradigm_name

    return "cortex"  # Default to structured

def calculate_energy_state(metrics: Dict[str, float] = None) -> Dict[str, Any]:
    """Calculate composite energy state.

    Energy represents the "health" of the world model.
    """
    if metrics is None:
        metrics = {dim: 0.75 for dim in ENERGY_DIMENSIONS}

    composite = sum(metrics.values()) / len(metrics)

    return {
        "dimensions": metrics,
        "composite": composite,
        "status": "healthy" if composite > 0.7 else "degraded" if composite > 0.4 else "critical"
    }

__all__ = ["PARADIGMS", "ENERGY_DIMENSIONS", "get_triggers", "extract_entities",
           "build_causal_chains", "detect_paradigm", "calculate_energy_state"]
