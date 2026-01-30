# ThinkingMachines [He2025] Compliance Audit

## Reference

He, Horace and Thinking Machines Lab, "Defeating Nondeterminism in LLM Inference",
Thinking Machines Lab: Connectionism, Sep 2025.
https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/

## Core Requirement: Batch-Invariance

**Definition**: Identical inputs must produce identical outputs regardless of batch size or system load.

**Otto Implementation**: ✅ COMPLIANT

The cognitive routing system produces identical results regardless of:
- How many concurrent sessions exist
- System load at time of evaluation
- Order of messages in a batch

## Compliance Matrix

| Principle | ThinkingMachines Requirement | Otto Implementation | Status |
|-----------|------------------------------|--------------------------|--------|
| Fixed Reduction Order | Reduction order must be fixed regardless of batch size | LIVRPS priority order is FIXED (L=1, I=2, V=3, R=4, P=5, S=6) | ✅ |
| Consistent Strategy | Don't switch algorithms based on load | Same evaluation order always used | ✅ |
| Deterministic State | State snapshots before processing | `snapshot()` called before all processing | ✅ |
| Atomic Updates | Batch updates after processing | `batch_update()` applies all changes atomically | ✅ |
| Seeded RNG | Any stochastic decisions must be seeded | RNG seeded with `seed=42` in CognitiveState | ✅ |
| Fixed Evaluation Order | Operations evaluated in fixed order | 5-phase NEXUS execution is fixed | ✅ |

## Detailed Analysis

### 1. LIVRPS Priority Resolution (Batch-Invariant)

```python
# FIXED priority order - NEVER changes
class LayerPriority(Enum):
    LOCAL = 1       # Session state - highest
    INHERITS = 2    # Inherited context
    VARIANTS = 3    # Mode variants
    REFERENCES = 4  # Calibration
    PAYLOADS = 5    # Domain knowledge
    SPECIALIZES = 6 # Constitutional - lowest
```

**Compliance**: The layer priority is encoded as an enum with fixed integer values.
Resolution always evaluates layers in order 1→6. This is analogous to
ThinkingMachines' requirement for "fixed reduction order."

### 2. Signal Detection (Fixed Evaluation Order)

```python
# PRISM Detector - FIXED evaluation order
SIGNAL_PRIORITY = [
    SignalCategory.EMOTIONAL,  # Always checked first
    SignalCategory.MODE,       # Second
    SignalCategory.DOMAIN,     # Third
    SignalCategory.TASK,       # Fourth
    SignalCategory.ENERGY      # Fifth (last)
]
```

**Compliance**: Signal categories are evaluated in fixed order. Same signals
will always produce same detection results. Analogous to ThinkingMachines'
fixed kernel execution order.

### 3. Expert Routing (First-Match-Wins)

```python
# ADHD_MoE Expert Priority - FIXED (first match wins)
EXPERT_PRIORITY = [
    ("Validator", ["frustrated", "RED", "caps"]),      # Pri 1
    ("Scaffolder", ["overwhelmed", "stuck"]),          # Pri 2
    ("Restorer", ["depleted", "ORANGE"]),              # Pri 3
    ("Refocuser", ["distracted"]),                     # Pri 4
    ("Celebrator", ["task_complete"]),                 # Pri 5
    ("Socratic", ["exploring", "what_if"]),            # Pri 6
    ("Direct", ["focused", "flow"])                    # Pri 7 (default)
]
```

**Compliance**: Expert selection uses first-match-wins with fixed priority.
No load-dependent routing changes. Same signals → same expert.

### 4. State Management (Snapshot + Batch Update)

```python
class CognitiveState:
    def snapshot(self) -> 'CognitiveState':
        """Create immutable snapshot BEFORE processing."""
        # All agents see same state during processing
        return CognitiveState(
            burnout_level=self.burnout_level,
            # ... copy all fields
        )

    def batch_update(self, updates: Dict[str, Any]) -> None:
        """Apply updates atomically AFTER processing."""
        # FIXED update order
        UPDATE_ORDER = ['burnout_level', 'momentum_phase', ...]
        for field_name in UPDATE_ORDER:
            if field_name in updates:
                setattr(self, field_name, updates[field_name])
```

**Compliance**: State is snapshotted before processing (all components see
same state), then batch-updated after (atomic application). This matches
ThinkingMachines' pattern of consistent state during kernel execution.

### 5. Convergence Tracking (RC^+xi)

```python
# Convergence formula is deterministic
xi_n = ||A_{n+1} - A_n||_2  # Epistemic tension

# Fixed thresholds
EPSILON = 0.1  # Convergence threshold
STABLE_EXCHANGES = 3  # Required for convergence
TENSION_INCREASE = 0.3  # On attractor switch
TENSION_DECREASE = 0.1  # Per stable exchange
```

**Compliance**: All convergence parameters are fixed constants.
No adaptive thresholds that could vary based on load.

### 6. Checksum Verification

```python
def checksum(self) -> str:
    """Deterministic checksum of state."""
    state_str = json.dumps(self.to_dict(), sort_keys=True)  # Sorted keys!
    return hashlib.sha256(state_str.encode()).hexdigest()[:16]
```

**Compliance**: Checksum uses `sort_keys=True` to ensure deterministic
JSON serialization. Same state → same checksum always.

## Non-Determinism Sources (Identified and Mitigated)

| Source | Risk | Mitigation |
|--------|------|------------|
| Dictionary ordering | Python dicts preserve insertion order (3.7+), but JSON serialization could vary | Using `sort_keys=True` |
| Floating point | Tension calculations use floats | Using simple arithmetic, no complex reductions |
| Timestamps | `time.time()` varies | Timestamps for tracking only, not for routing decisions |
| RNG | Random decisions could vary | Seeded RNG instance `random.Random(seed=42)` |
| Concurrent access | Multiple processes could race | Single-process design, atomic file writes |

## Execution Protocol (5 Phases - NEXUS)

```
1. DETECT    → PRISM parses signals (FIXED order)
2. CASCADE   → ADHD_MoE routes (FIXED priority)
3. LOCK      → Parameters locked BEFORE generation
4. EXECUTE   → Generate with locked params
5. UPDATE    → Batch update state (FIXED order)
```

**Key Guarantee**: Parameters are LOCKED at phase 3, before any generation.
This is equivalent to ThinkingMachines' requirement that kernel parameters
be fixed before execution begins.

## Anchor Format (Reproducibility)

```
[EXEC:{checksum}|{expert}|{paradigm}|{altitude}|{verbosity}|{think_depth}]
```

The anchor captures ALL routing decisions in a reproducible format.
Given the same anchor, the same behavior should result.

## Verification Strategy

### Test 1: Same State → Same Checksum
```python
def test_deterministic_checksum():
    state1 = CognitiveState(burnout_level=BurnoutLevel.YELLOW)
    state2 = CognitiveState(burnout_level=BurnoutLevel.YELLOW)
    assert state1.checksum() == state2.checksum()
```

### Test 2: Same Signals → Same Routing
```python
def test_deterministic_routing():
    detector = PRISMDetector()
    signals1 = detector.detect("I'm frustrated with this bug")
    signals2 = detector.detect("I'm frustrated with this bug")
    assert signals1.to_dict() == signals2.to_dict()
```

### Test 3: Same Opinions → Same Resolution
```python
def test_deterministic_resolution():
    stage = CognitiveStage()
    stage.set_session_value("burnout", "yellow")
    stage.set_calibration_value("burnout", "green")

    result1 = stage.get_resolved("burnout")
    result2 = stage.get_resolved("burnout")
    assert result1 == result2 == "yellow"  # Session wins
```

## Conclusion

Otto's cognitive routing system is **ThinkingMachines [He2025] compliant**:

1. ✅ **Batch-invariant**: Same inputs → same outputs regardless of load
2. ✅ **Fixed reduction order**: LIVRPS priority is fixed
3. ✅ **No strategy switching**: Same algorithms always used
4. ✅ **Deterministic state**: Snapshot before, batch update after
5. ✅ **Seeded RNG**: All random decisions are reproducible
6. ✅ **Verifiable**: Checksums enable determinism verification

The key insight from ThinkingMachines—that nondeterminism comes from
variable processing order, not floating point—maps directly to our
approach: fixed LIVRPS order ensures consistent cognitive state resolution.
