# [He2025] Determinism Addendum for OTTO OS Blueprint v1.0

## Reference

> [He2025] He, Horace and Thinking Machines Lab, "Defeating Nondeterminism in LLM Inference",
> Thinking Machines Lab: Connectionism, Sep 2025.
> https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/

## Executive Summary

This addendum specifies determinism requirements for OTTO OS to ensure:
- Same inputs → Same outputs (bit-identical where possible)
- "Doesn't judge" → Consistent state classification
- "Doesn't annoy" → Predictable intervention timing
- "Doesn't forget" → Reproducible profile behavior

---

## 1. Float Precision Specification

### 1.1 Comparison Precision

All float comparisons use 6-decimal rounding:

```python
# WRONG: Direct comparison
if dial_value > 0.7:

# CORRECT: Precision-controlled comparison
if round(dial_value, 6) > 0.7:
```

**Rationale:** IEEE 754 floating-point arithmetic is non-associative. The same mathematical value can have different binary representations depending on computation order.

### 1.2 Kahan Summation for Aggregation

All float aggregations use Kahan summation with sorted input:

```python
def kahan_sum(values: list[float]) -> float:
    """[He2025] Batch-invariant summation."""
    total = 0.0
    compensation = 0.0
    for v in sorted(values):  # CRITICAL: sort first
        y = v - compensation
        t = total + y
        compensation = (t - total) - y
        total = t
    return total
```

**Rationale:** Sorting ensures identical computation order regardless of how values were collected. Kahan summation minimizes accumulated rounding error.

### 1.3 Dial Computation

```python
def compute_dial(intake_answers: list[float]) -> float:
    """[He2025] compliant dial computation."""
    if not intake_answers:
        return 0.5  # Default

    # 1. Sort for deterministic order
    sorted_answers = sorted(intake_answers)

    # 2. Kahan summation
    total = kahan_sum(sorted_answers)

    # 3. Fixed precision output
    return round(total / len(sorted_answers), 6)
```

---

## 2. State Detection Specification

### 2.1 Fixed Signal Vocabularies

State detection uses **frozen** vocabularies, not heuristics:

```python
# Alphabetically sorted for determinism
FRUSTRATED_VOCABULARY = frozenset(sorted([
    "annoyed", "broken", "can't", "confused", "frustrated",
    "gave up", "hate", "impossible", "stuck", "ugh", "why",
]))

POSITIVE_VOCABULARY = frozenset(sorted([
    "done", "fixed", "good", "got it", "great", "nice",
    "perfect", "thanks", "works", "yes",
]))

OVERWHELMED_VOCABULARY = frozenset(sorted([
    "everything", "much", "many", "overwhelmed", "so much",
    "too many", "too much",
]))
```

### 2.2 Fixed Thresholds

```python
# Character counts
SHORT_MESSAGE_THRESHOLD = 20
LONG_MESSAGE_THRESHOLD = 500

# Ratios (2 decimal precision)
CAPS_RATIO_THRESHOLD = 0.50
REPETITION_SIMILARITY_THRESHOLD = 0.80

# Counts
MIN_FRUSTRATED_WORDS = 1
MIN_OVERWHELMED_WORDS = 2
```

### 2.3 Signal Extraction (Fixed Order)

Signals are extracted in **fixed evaluation order**:

```python
def extract_signals(message: str, history: list[str]) -> dict:
    """
    [He2025] Fixed evaluation order:
    1. Length → 2. Caps → 3. Vocabulary → 4. Repetition
    """
    signals = {}

    # Phase 1: Length (cheapest)
    signals["char_count"] = len(message)
    signals["is_short"] = signals["char_count"] < SHORT_MESSAGE_THRESHOLD
    signals["is_long"] = signals["char_count"] > LONG_MESSAGE_THRESHOLD

    # Phase 2: Caps ratio
    alpha_chars = [c for c in message if c.isalpha()]
    if alpha_chars:
        caps_count = sum(1 for c in alpha_chars if c.isupper())
        signals["caps_ratio"] = round(caps_count / len(alpha_chars), 2)
    else:
        signals["caps_ratio"] = 0.0
    signals["is_caps"] = signals["caps_ratio"] > CAPS_RATIO_THRESHOLD

    # Phase 3: Vocabulary matching (sorted iteration)
    words = set(message.lower().split())
    signals["frustrated_count"] = len(words & FRUSTRATED_VOCABULARY)
    signals["positive_count"] = len(words & POSITIVE_VOCABULARY)
    signals["overwhelmed_count"] = len(words & OVERWHELMED_VOCABULARY)

    # Phase 4: Repetition (expensive, last)
    if history:
        last_words = set(history[-1].lower().split())
        current_words = set(message.lower().split())
        union = last_words | current_words
        if union:
            similarity = len(last_words & current_words) / len(union)
            signals["repetition_similarity"] = round(similarity, 2)
        else:
            signals["repetition_similarity"] = 0.0
    else:
        signals["repetition_similarity"] = 0.0
    signals["is_repetitive"] = signals["repetition_similarity"] > REPETITION_SIMILARITY_THRESHOLD

    return signals
```

### 2.4 State Classification (Priority Order)

First match wins - explicit priority:

```python
STATE_PRIORITY = [
    # (priority, state, condition_function)
    (1, "frustrated", lambda s: s["is_caps"] and s["frustrated_count"] >= MIN_FRUSTRATED_WORDS),
    (2, "overwhelmed", lambda s: s["overwhelmed_count"] >= MIN_OVERWHELMED_WORDS),
    (3, "stuck", lambda s: s["is_repetitive"]),
    (4, "depleted", lambda s: s["is_short"] and s["positive_count"] == 0),
    (5, "scattered", lambda s: not s["is_long"] and s["char_count"] > 0),
    (6, "focused", lambda s: True),  # Default fallback
]

def classify_state(signals: dict) -> str:
    """[He2025] First match wins, explicit priority order."""
    for priority, state, condition in STATE_PRIORITY:
        if condition(signals):
            return state
    return "focused"  # Should never reach here
```

---

## 3. Expert Selection Specification

### 3.1 Explicit Priority Numbers

```python
EXPERT_PRIORITY = {
    # Safety-critical (lowest numbers = highest priority)
    "Validator": 1,     # Emotional safety - ALWAYS checked first
    "Scaffolder": 2,    # Task breakdown for overwhelm
    "Restorer": 3,      # Recovery for depletion

    # Support
    "Refocuser": 4,     # Redirect tangents
    "Celebrator": 5,    # Acknowledge wins

    # Modes
    "Socratic": 6,      # Guide discovery
    "Direct": 7,        # Stay out of way (DEFAULT)
}
```

### 3.2 Expert → State Mapping

```python
EXPERT_TRIGGERS = {
    "Validator": ["frustrated"],
    "Scaffolder": ["overwhelmed", "stuck"],
    "Restorer": ["depleted"],
    "Refocuser": ["scattered"],
    "Celebrator": [],  # Triggered by task completion, not state
    "Socratic": [],    # Triggered by "what if" signals
    "Direct": ["focused"],  # Default
}

def select_expert(state: str, signals: dict) -> str:
    """[He2025] Deterministic expert selection."""
    # Sort by priority, check triggers
    for expert, priority in sorted(EXPERT_PRIORITY.items(), key=lambda x: x[1]):
        triggers = EXPERT_TRIGGERS.get(expert, [])
        if state in triggers:
            return expert
    return "Direct"
```

### 3.3 Safety Floors (Never Bypassed)

From `constitutional.usda`:

```python
SAFETY_FLOORS = {
    "Validator": 0.10,   # Minimum 10% weight
    "Restorer": 0.05,    # Minimum 5% weight
    "Scaffolder": 0.05,  # Minimum 5% weight
}

def apply_safety_floors(expert_weights: dict) -> dict:
    """[He2025] Safety floors are ADDITIVE, never removed."""
    result = dict(expert_weights)
    for expert, floor in SAFETY_FLOORS.items():
        if expert in result:
            result[expert] = max(result[expert], floor)
        else:
            result[expert] = floor
    return result
```

---

## 4. Permission Engine Specification

### 4.1 Permission Decision Order

```python
PERMISSION_DECISION_ORDER = [
    # (priority, check_name, condition, permission_type)
    (1, "crisis_language", lambda s: s["frustrated_count"] >= 2, "stop"),
    (2, "energy_depleted", lambda s: s["is_short"] and s["positive_count"] == 0, "stop"),
    (3, "stuck_pattern", lambda s: s["is_repetitive"], "pivot"),
    (4, "perfectionism", lambda m: any(p in m for p in ["one more", "almost"]), "imperfect"),
]

def check_permission_needed(signals: dict, message: str) -> Optional[str]:
    """[He2025] Fixed evaluation order for permission decisions."""
    for priority, name, condition, perm_type in PERMISSION_DECISION_ORDER:
        try:
            if condition(signals):
                return perm_type
        except (KeyError, TypeError):
            if condition(message):
                return perm_type
    return None
```

### 4.2 Permission Phrasing (Deterministic Selection)

```python
PERMISSION_PHRASES = {
    "stop": [
        "Permission granted: Stop for today.",
        "Permission granted: This is enough.",
        "Permission granted: Rest is productive.",
    ],
    "pivot": [
        "Permission granted: Abandon this approach.",
        "Permission granted: Try something different.",
    ],
    "imperfect": [
        "Permission granted: Ship it ugly.",
        "Permission granted: Done beats perfect.",
    ],
}

def select_permission_phrase(perm_type: str, exchange_count: int) -> str:
    """[He2025] Deterministic phrase selection via modulo."""
    phrases = PERMISSION_PHRASES.get(perm_type, PERMISSION_PHRASES["stop"])
    # Use exchange_count as deterministic seed
    index = exchange_count % len(phrases)
    return phrases[index]
```

---

## 5. Convergence Calculation Specification

### 5.1 Epistemic Tension (RC^+xi)

```python
def calculate_tension(
    current_attractor: str,
    previous_attractor: str,
    stable_exchanges: int,
) -> float:
    """
    [He2025] Deterministic tension calculation.

    Formula: xi_n = ||A_{n+1} - A_n||_2
    """
    # From constitutional.usda
    TENSION_INCREASE_ON_SWITCH = 0.3
    TENSION_DECREASE_WHEN_STABLE = 0.1
    CONVERGENCE_EPSILON = 0.1

    if current_attractor != previous_attractor:
        # Attractor switch - increase tension
        return round(TENSION_INCREASE_ON_SWITCH, 6)
    else:
        # Same attractor - decay tension
        decay = stable_exchanges * TENSION_DECREASE_WHEN_STABLE
        tension = max(0.0, TENSION_INCREASE_ON_SWITCH - decay)
        return round(tension, 6)
```

### 5.2 Convergence Detection

```python
def is_converged(tension: float, stable_exchanges: int) -> bool:
    """[He2025] Deterministic convergence check."""
    CONVERGENCE_EPSILON = 0.1
    CONVERGENCE_STABLE_EXCHANGES = 3

    return (
        round(tension, 6) < CONVERGENCE_EPSILON and
        stable_exchanges >= CONVERGENCE_STABLE_EXCHANGES
    )
```

---

## 6. Query Ordering Specification

All database/storage queries return results in deterministic order:

### 6.1 Trail Queries

```sql
-- All trail queries include explicit ORDER BY
SELECT * FROM trails
WHERE path = ?
ORDER BY trail_type ASC, signal ASC;

-- Strongest trail uses deterministic tie-breaking
-- (highest strength, then alphabetically by signal)
```

### 6.2 Session Queries

```sql
-- Sessions ordered by start time
SELECT * FROM sessions
WHERE user_id = ?
ORDER BY started_at DESC;

-- Messages ordered by timestamp
SELECT * FROM messages
WHERE session_id = ?
ORDER BY timestamp ASC;
```

### 6.3 In-Memory Sorting

```python
def sort_for_determinism(items: list, key_func) -> list:
    """[He2025] Explicit sorting for deterministic iteration."""
    return sorted(items, key=key_func)

# Example: Sort experts by priority
for expert in sort_for_determinism(experts, key=lambda e: EXPERT_PRIORITY[e]):
    ...
```

---

## 7. Constants Reference

```python
# =============================================================================
# [He2025] DETERMINISM CONSTANTS
# =============================================================================

# Precision
FLOAT_PRECISION = 6          # Decimal places for float comparison
RATIO_PRECISION = 2          # Decimal places for ratios

# Thresholds (message analysis)
SHORT_MESSAGE_THRESHOLD = 20
LONG_MESSAGE_THRESHOLD = 500
CAPS_RATIO_THRESHOLD = 0.50
REPETITION_SIMILARITY_THRESHOLD = 0.80

# Vocabulary minimums
MIN_FRUSTRATED_WORDS = 1
MIN_OVERWHELMED_WORDS = 2

# Convergence (from constitutional.usda)
CONVERGENCE_EPSILON = 0.1
CONVERGENCE_STABLE_EXCHANGES = 3
TENSION_INCREASE_ON_SWITCH = 0.3
TENSION_DECREASE_WHEN_STABLE = 0.1

# Safety floors (from constitutional.usda)
SAFETY_FLOOR_VALIDATOR = 0.10
SAFETY_FLOOR_RESTORER = 0.05
SAFETY_FLOOR_SCAFFOLDER = 0.05

# Tile size (from batch invariance)
COGNITIVE_TILE_SIZE = 32
```

---

## 8. Verification Protocol

### 8.1 Determinism Test

```python
def test_determinism(func, inputs, n_trials=100):
    """Verify same inputs → same outputs."""
    results = set()
    for _ in range(n_trials):
        result = func(*inputs)
        results.add(hash(str(result)))
    assert len(results) == 1, f"Non-deterministic: {len(results)} unique results"
```

### 8.2 Required Tests

Each component must pass:

| Component | Test |
|-----------|------|
| `compute_dial()` | 100 trials, identical output |
| `extract_signals()` | 100 trials, identical dict |
| `classify_state()` | All vocabulary combinations |
| `select_expert()` | All state × signal combinations |
| `calculate_tension()` | 100 trials, identical float |
| Trail queries | Identical ordering across runs |

---

## 9. Integration with Existing Code

### 9.1 TrailStore Pattern (Reference Implementation)

The existing `TrailStore` (`otto/trails/store.py`) is the reference for [He2025] compliance:

```python
# Line 450: Precision rounding
rounded_strength = round(current, 6)

# Line 458: Deterministic tie-breaking
candidates.sort(key=lambda x: (-x[0], x[1]))

# Line 510: Query ordering
ORDER BY path ASC, trail_type ASC, signal ASC
```

All new code should follow this pattern.

### 9.2 Mobile Compatibility

All determinism code must be mobile-compatible:
- No `pxr-usd` dependency
- Pure Python implementations
- No platform-specific randomness

---

## Appendix A: Vocabulary Definitions

### A.1 Frustrated Vocabulary

```python
FRUSTRATED_VOCABULARY = frozenset(sorted([
    "annoyed",
    "broken",
    "can't",
    "confused",
    "frustrated",
    "gave up",
    "hate",
    "impossible",
    "stuck",
    "ugh",
    "why",
]))
```

### A.2 Positive Vocabulary

```python
POSITIVE_VOCABULARY = frozenset(sorted([
    "done",
    "fixed",
    "good",
    "got it",
    "great",
    "nice",
    "perfect",
    "thanks",
    "works",
    "yes",
]))
```

### A.3 Overwhelmed Vocabulary

```python
OVERWHELMED_VOCABULARY = frozenset(sorted([
    "everything",
    "many",
    "much",
    "overwhelmed",
    "so much",
    "too many",
    "too much",
]))
```

---

*Addendum v1.0 | February 2026*
*Ensures OTTO OS Blueprint compliance with [He2025] determinism principles*
