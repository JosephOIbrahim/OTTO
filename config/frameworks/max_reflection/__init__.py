"""
MAX Reflection Payload - Weighted Tier
======================================

Implements RC^+xi bounded reflection from MAX 3 Framework.

Source Frameworks:
- MAX 3 Framework (canonical - MAX 4 merged into this)
- RC^+xi Research (epistemic tension formula)

Key Features:
- Epistemic tension calculation: xi_n = ||A_{n+1} - A_n||_2
- Bounded reflection (MAX 3 iterations)
- Convergence tracking
"""

from typing import Dict, Any

# Convergence parameters
EPSILON = 0.1  # Convergence threshold
MAX_ITERATIONS = 3  # Bounded reflection
STABLE_EXCHANGES = 3  # Consecutive exchanges at xi < epsilon = CONVERGED

# Attractor basins
ATTRACTORS = {
    "focused": {"experts": ["executor"], "paradigm": "cortex", "energy": "high"},
    "exploring": {"experts": ["guide"], "paradigm": "mycelium", "energy": "high"},
    "recovery": {"experts": ["restorer"], "paradigm": "cortex", "energy": "low"},
    "teaching": {"experts": ["guide"], "paradigm": "cortex", "energy": "medium"}
}

def get_triggers():
    """Triggers for loading this payload."""
    return ["think", "analyze", "consider", "reflect", "converge", "tension"]

def calculate_epistemic_tension(state_prev: Dict, state_curr: Dict) -> float:
    """Calculate epistemic tension between two states.

    xi_n = ||A_{n+1} - A_n||_2

    Uses L2 norm of state difference.
    """
    # Extract comparable features
    features_prev = _extract_features(state_prev)
    features_curr = _extract_features(state_curr)

    # L2 distance
    sum_sq = 0.0
    for key in features_curr:
        diff = features_curr.get(key, 0) - features_prev.get(key, 0)
        sum_sq += diff * diff

    return sum_sq ** 0.5

def _extract_features(state: Dict) -> Dict[str, float]:
    """Extract numeric features from state for comparison."""
    return {
        "energy": {"high": 1.0, "medium": 0.5, "low": 0.25, "depleted": 0.0}.get(
            state.get("energy_level", "medium"), 0.5
        ),
        "confidence": state.get("confidence", 0.5),
        "iteration": state.get("iteration", 0) / 10.0
    }

def check_convergence(history: list) -> Dict[str, Any]:
    """Check if we've converged (xi < epsilon for 3 consecutive exchanges)."""
    if len(history) < STABLE_EXCHANGES + 1:
        return {"converged": False, "reason": "Insufficient history"}

    # Calculate tension for recent exchanges
    recent_tensions = []
    for i in range(-STABLE_EXCHANGES, 0):
        xi = calculate_epistemic_tension(history[i-1], history[i])
        recent_tensions.append(xi)

    all_below = all(xi < EPSILON for xi in recent_tensions)

    return {
        "converged": all_below,
        "recent_tensions": recent_tensions,
        "epsilon": EPSILON,
        "attractor": _detect_attractor(history[-1]) if all_below else None
    }

def _detect_attractor(state: Dict) -> str:
    """Detect which attractor basin we're in."""
    # Simplified detection
    if state.get("energy_level") in ["low", "depleted"]:
        return "recovery"
    if "explore" in str(state.get("mode", "")).lower():
        return "exploring"
    return "focused"

__all__ = ["EPSILON", "MAX_ITERATIONS", "ATTRACTORS", "get_triggers",
           "calculate_epistemic_tension", "check_convergence"]
