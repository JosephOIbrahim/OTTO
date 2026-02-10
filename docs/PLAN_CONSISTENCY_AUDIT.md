# OTTO OS Plan Consistency Audit

> **Generated**: 2026-02-01
> **Auditor**: Claude (deep analysis mode)
> **Source**: Path to 10/10 implementation plan
> **Reference**: [He2025] — Defeating nondeterminism in LLM inference

---

## Executive Summary

The plan is **structurally sound** but contains **12 consistency issues** that must be fixed before execution. Most issues are import path mismatches and violations in the proposed code.

| Category | Issues Found | Severity |
|----------|-------------|----------|
| Violations | 4 | **CRITICAL** |
| Import Path Errors | 3 | HIGH |
| Factual Inaccuracies | 3 | MEDIUM |
| Missing Context | 2 | LOW |

---

## Critical: Violations in Plan Code

### Issue 1: Non-deterministic shuffle in `generate_synthetic.py`

**Location**: Phase 2.1 - `benchmarks/state_detection/generate_synthetic.py`

**Problem**:
```python
random.shuffle(samples)  # ❌ No seed - violates
```

**Principle Violated**: Fixed reduction order. Different runs produce different orderings.

**Fix**:
```python
random.seed(0xCAFEBABE)  # deterministic seed
random.shuffle(samples)
```

---

### Issue 2: Non-deterministic message generation

**Location**: Phase 2.1 - `generate_synthetic.py`

**Problem**:
```python
def generate_message(state: str) -> str:
    base = random.choice(PATTERNS[state])  # ❌ No seed
    if random.random() < 0.3:              # ❌ No seed
```

**Fix**:
```python
# At module level
_rng = random.Random(0xCAFEBABE)  # fixed seed generator

def generate_message(state: str, seed_offset: int = 0) -> str:
    local_rng = random.Random(0xCAFEBABE + seed_offset)
    base = local_rng.choice(PATTERNS[state])
    if local_rng.random() < 0.3:
```

---

### Issue 3: Set iteration without sorting

**Location**: Phase 2.1 - `run_benchmark.py`

**Problem**:
```python
for state, counts in results.items():  # Dict iteration order is preserved in Python 3.7+
```

This is actually **OK** in Python 3.7+ (insertion order preserved), but for extra safety:

**Recommendation**:
```python
for state in sorted(results.keys()):  # explicit determinism
    counts = results[state]
```

---

### Issue 4: Trail crystallization uses non-deterministic time comparison

**Location**: Phase 3.3 - `crystallization.py`

**Problem**:
```python
current_time = time.time()  # Runtime-dependent
age_seconds = current_time - created_at
if age_seconds < min_age_seconds:
    continue
```

**Why it's a problem**: The set of trails crystallized depends on when you run, not just trail properties.

**Fix**: Pass timestamp as parameter for deterministic testing:
```python
def find_crystallization_candidates(
    self,
    as_of: Optional[float] = None  # Allow fixed timestamp for testing
) -> list[Trail]:
    current_time = as_of if as_of is not None else time.time()
```

---

## High: Import Path Errors

### Issue 5: Wrong path for prism_detector

**Plan says**:
```python
from otto.core.prism_detector import PRISMDetector
```

**Actual path** (from `src/otto/__init__.py`):
```python
from otto.prism_detector import PRISMDetector
```

**Fix all occurrences**:
- `benchmarks/state_detection/run_benchmark.py`
- `tests/test_multi_agent_coordination.py`

---

### Issue 6: Wrong path for cognitive_orchestrator

**Plan says**:
```python
from otto.core.cognitive_orchestrator import create_orchestrator
```

**Actual path**:
```python
from otto.cognitive_orchestrator import create_orchestrator
```

---

### Issue 7: Wrong MCP tool imports

**Plan says**:
```python
from otto.mcp.orchestra import otto_status, otto_protection
from otto.mcp.trails import otto_read_trails, otto_deposit_trail
```

**Actual structure**:
```
packages/orchestra-mcp/src/otto_mcp/server.py
packages/otto-trails-mcp/src/otto_trails_mcp/server.py
```

**Fix**: Import from actual MCP package structure or create wrapper module.

---

## Medium: Factual Inaccuracies

### Issue 8: "4 skipped tests to fix" is misleading

**Plan says**: "Fix 4 skipped tests"

**Reality**: The skips are **conditional** based on optional dependencies:
- `cryptography` not installed → encryption tests skip
- `liboqs` not installed → post-quantum tests skip
- `argon2-cffi` not installed → key derivation tests skip
- `OTel` not installed → telemetry tests skip

**These are correct behavior**, not bugs. The tests run when dependencies are present.

**Fix**: Update Phase 0.1 to:
```markdown
### 0.1 Resolve Conditional Dependencies

The 4 skipped tests are conditional on optional dependencies.

**Decision needed**:
- Option A: Install `cryptography`, `argon2-cffi`, etc. and verify all tests pass
- Option B: Document these as optional features and keep skips
- Option C: Mark as integration tests, separate from unit tests

**Recommended**: Option A for production deployment
```

---

### Issue 9: Inference layer already exists with Determinism

**Plan says**: "Verify inference layer works with Claude API before building Telegram adapter"

**Reality**: The inference layer is already **extensively implemented** with 4 tiers:
- Tier 1: API-Maximized Determinism
- Tier 2: Multi-trial Verification
- Tier 3: Kernel-Level (strict)
- Tier 4: Cryptographic Proofs

**Documentation**: `docs/HE2025_KERNEL_COMPLIANCE_STRATEGY.md`

**Fix**: Phase 1.1 should be:
```markdown
### 1.1 Validate Existing Inference Layer

The inference layer already implements 4-tier Determinism.

**Task**: Run integration tests to verify Claude backend works.

```bash
pytest tests/test_inference_integration.py -v
```

**If tests fail**: Debug specific backend issues.
**If tests pass**: Proceed to Telegram adapter.
```

---

### Issue 10: Test count is actually 3853, not "3849 passing, 4 skipped"

**From the previous session**: 3848 passed, 1 failed (now fixed), 4 skipped

**Current state after fix**: 3849 passing, 4 conditional skips

**The 3853 total** is correct but the breakdown needs updating.

---

## Low: Missing Context

### Issue 11: Intake form already exists

**Plan creates**: `web/intake/` with new HTML/CSS/JS

**Already exists**: `src/otto/intake/game.py` with Rich CLI interface

**Recommendation**:
- The web version is additional (for mobile/browser users)
- Should integrate with existing `IntakeGame` backend
- Add explicit integration note in plan

---

### Issue 12: Missing cryptography dependency causing collection errors

**Symptom**:
```
E   ModuleNotFoundError: No module named 'cryptography'
```

**Fix**: Add to Phase 0:
```bash
pip install cryptography argon2-cffi
```

Or ensure requirements.txt includes:
```
cryptography>=41.0.0
argon2-cffi>=23.1.0
```

---

## Determinism Checklist for Plan Code

| File | Pattern | Status | Fix Needed |
|------|---------|--------|------------|
| `generate_synthetic.py` | `random.shuffle()` | ❌ | Add seed |
| `generate_synthetic.py` | `random.choice()` | ❌ | Add seed |
| `generate_synthetic.py` | `random.random()` | ❌ | Add seed |
| `run_benchmark.py` | `defaultdict` | ✅ | OK (counting) |
| `run_benchmark.py` | `dict.items()` | ⚠️ | Use `sorted()` |
| `run_1000.py` | `hash_result()` | ✅ | Uses `sort_keys=True` |
| `crystallization.py` | `time.time()` | ⚠️ | Parameterize for testing |
| `metrics.py` | `list.append()` | ✅ | OK (observability) |
| `adapter.py` | Session dict | ✅ | OK (keyed by user_id) |

---

## Revised Phase 0 (Incorporating Fixes)

```markdown
### 0.1 Install Missing Dependencies

```bash
cd C:\Users\User\OTTO_OS
pip install cryptography argon2-cffi
pytest --collect-only  # Verify collection succeeds
```

### 0.2 Verify Test Status

```bash
pytest -v --tb=short 2>&1 | tail -20
# Expected: 3849+ passed, ~4 conditional skips
```

**Conditional skips are OK** if they're for optional features.

### 0.3 Fix Violations in Benchmark Code

Before writing benchmark code, apply these patterns:

```python
# All random operations use fixed seed
import random
_DETERMINISM_SEED = 0xCAFEBABE
random.seed(_DETERMINISM_SEED)

# All dict iterations use sorted keys
for key in sorted(my_dict.keys()):
    value = my_dict[key]

# All set iterations use sorted
for item in sorted(my_set):
    process(item)

# Float precision always 6 decimals
value = round(value, 6)
```

### 0.4 Verify Import Paths

Use correct imports throughout:

```python
# Correct
from otto.prism_detector import PRISMDetector
from otto.cognitive_orchestrator import create_orchestrator
from otto.cognitive_state import CognitiveState, CognitiveStateManager

# NOT
from otto.core.prism_detector import PRISMDetector  # Wrong path
```
```

---

## Summary of Required Changes

### Before Starting Phase 0:
1. Install `cryptography` and `argon2-cffi`
2. Verify test collection works

### In Plan Phase 0:
1. Update "fix skipped tests" to "verify conditional skips"
2. Add Determinism checklist

### In Plan Phase 1:
1. Update inference layer section to "validate existing"
2. Fix import paths in Telegram adapter

### In Plan Phase 2:
1. Add fixed seeds to synthetic data generator
2. Add sorted iteration to benchmark runner
3. Parameterize time in crystallization for testing

### Throughout Plan:
1. Fix all import paths from `otto.core.*` to `otto.*`
2. Apply patterns to all new code

---

## Verification Command

After applying fixes, run:

```bash
cd C:\Users\User\OTTO_OS

# Install deps
pip install cryptography argon2-cffi

# Full test suite
pytest -v --tb=short

# Determinism check
python -c "
from otto.inference import DeterministicAPIWrapper, DeterminismLevel
print('Inference layer OK')
print(f'Determinism levels: {list(DeterminismLevel)}')
"
```

Expected output:
```
3849+ passed, ~4 skipped (conditional)
Inference layer OK
Determinism levels: [<DeterminismLevel.API_MAXIMIZED: 1>, ...]
```

---

*Audit complete. Plan is executable after applying 12 fixes.*
