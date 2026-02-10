# Contributing to Otto

Thank you for your interest in Otto! This document provides guidelines for contributing.

---

## Development Setup

### Prerequisites

- Python 3.10+
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/JosephOIbrahim/Otto.git
cd Otto

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install with development dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/otto

# Run specific test file
pytest tests/test_cognitive_engine.py -v
```

---

## Architecture Overview

Otto implements a **5-Phase NEXUS Pipeline** based on ThinkingMachines batch-invariance principles.

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   DETECT    │ ──▶ │   CASCADE   │ ──▶ │    LOCK     │
│   (PRISM)   │     │ (CogSafeMoE)│     │   (MAX3)    │
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
┌─────────────┐     ┌─────────────┐            │
│   UPDATE    │ ◀── │   EXECUTE   │ ◀──────────┘
│  (RC^+xi)   │     │  (Claude)   │
└─────────────┘     └─────────────┘
```

### Core Modules

| Module | File | Purpose |
|--------|------|---------|
| `PRISMDetector` | `prism_detector.py` | Signal extraction (emotional > mode > domain > task) |
| `ExpertRouter` | `expert_router.py` | Cognitive Safety MoE routing (7 experts, fixed priority) |
| `ParameterLocker` | `parameter_locker.py` | MAX3 bounded reflection, safety gating |
| `ConvergenceTracker` | `convergence_tracker.py` | RC^+xi epistemic tension tracking |
| `CognitiveOttotor` | `cognitive_ottotor.py` | 5-Phase pipeline coordination |
| `CognitiveState` | `cognitive_state.py` | State persistence and management |

---

## Coding Standards

### ThinkingMachines Determinism

All contributions must maintain batch-invariance:

1. **Fixed Evaluation Order** — Never reorder phase execution or priority lists
2. **No Dynamic Switching** — Algorithm selection must be deterministic
3. **Parameter Locking** — Lock all params before generation
4. **Reproducible Checksums** — Same inputs must produce same outputs

### Code Style

```python
# Good: Fixed priority, explicit ordering
EXPERT_PRIORITY = [
    Expert.VALIDATOR,   # 1 - Always first (safety)
    Expert.SCAFFOLDER,  # 2
    Expert.RESTORER,    # 3
    ...
]

# Bad: Dynamic ordering based on runtime conditions
experts = sorted(experts, key=lambda e: compute_priority(e, state))
```

### Testing Requirements

- All new features require tests
- Tests must verify determinism (same input → same output)
- Use `pytest` fixtures for state setup

```python
def test_routing_determinism():
    """Same signals must route to same expert."""
    router = ExpertRouter()

    result1 = router.route(signals, burnout, energy, momentum)
    result2 = router.route(signals, burnout, energy, momentum)

    assert result1.expert == result2.expert
    assert result1.trigger == result2.trigger
```

---

## Pull Request Process

### Before Submitting

1. **Run tests:** `pytest`
2. **Check determinism:** Verify fixed evaluation order
3. **Update docs:** If adding features, update relevant docs
4. **Add citations:** If using new research, add to `CITATIONS.md`

### PR Template

```markdown
## Summary
[1-3 sentence description]

## Changes
- [ ] Added/modified feature X
- [ ] Updated tests
- [ ] Updated documentation

## ThinkingMachines Compliance
- [ ] Fixed evaluation order maintained
- [ ] No dynamic algorithm switching
- [ ] Deterministic checksums verified

## Testing
- [ ] All existing tests pass
- [ ] New tests added for new functionality
```

---

## Adding New Experts

To add a new intervention expert:

1. Add to `Expert` enum in `expert_router.py`:
```python
class Expert(Enum):
    ...
    NEW_EXPERT = "new_expert"  # Add at correct priority position
```

2. Add triggers in `EXPERT_TRIGGERS`:
```python
Expert.NEW_EXPERT: {
    "emotional": ["trigger_emotion"],
    "signals": ["trigger_phrase"],
    "description": "What this expert does"
}
```

3. **Critical:** Add to `EXPERT_PRIORITY` at the correct position:
```python
EXPERT_PRIORITY = [
    Expert.VALIDATOR,
    Expert.SCAFFOLDER,
    Expert.NEW_EXPERT,  # Insert at correct priority
    ...
]
```

4. Add tests for the new expert routing.

---

## Adding New Signal Categories

To add a new signal category to PRISM:

1. Add to `SignalCategory` enum (respecting priority order)
2. Add patterns to `SIGNAL_PATTERNS`
3. Update `SignalVector` dataclass
4. Update `PRISMDetector.detect()` method
5. Add tests

**Warning:** Signal priority order (emotional > mode > domain > task > energy) is part of the core specification. Changes require careful consideration.

---

## Issue Guidelines

### Bug Reports

```markdown
**Describe the bug**
A clear description of what the bug is.

**To Reproduce**
1. Input: "..."
2. Expected expert: ...
3. Actual expert: ...

**State**
- Burnout: GREEN/YELLOW/ORANGE/RED
- Energy: high/medium/low/depleted
- Momentum: cold_start/building/rolling/peak/crashed

**Checksums**
If relevant, include the EXEC anchor: [EXEC:abc123|...]
```

### Feature Requests

```markdown
**Is this related to a problem?**
Description of the problem.

**Proposed solution**
How this feature would work.

**ThinkingMachines consideration**
How does this maintain determinism?
```

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

## Questions?

- Open an issue: https://github.com/JosephOIbrahim/Otto/issues
- See CITATIONS.md for theoretical background

---

*Otto v5.0.1 — Contributions welcome!*
