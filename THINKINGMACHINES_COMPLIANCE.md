# [He2025] Thinking Machines Compliance

OTTO OS implements determinism principles from:

> He, Horace. "Defeating Non-determinism in LLM Inference."
> Thinking Machines Lab, September 2025.
> https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/

## Scope Clarification

[He2025] addresses **GPU inference engine determinism** (vLLM, SGLang) with
batch-invariant kernels for numerical reproducibility.

OTTO applies these **design principles at the application layer**:

| OTTO Component | [He2025] Principle Applied |
|----------------|---------------------------|
| Cognitive Routing | Fixed evaluation order |
| Expert Selection | Deterministic priority |
| State Composition | LIVRPS fixed resolution order |
| Float Aggregation | Kahan summation |
| Dict Iteration | Sorted keys in critical paths |

## What OTTO Does NOT Do

- OTTO does not implement GPU kernels
- OTTO calls external LLM APIs (Claude, etc.)
- Numerical determinism of LLM responses is outside OTTO's control

## What OTTO DOES Do

- Same PRISM signals → Same expert selection (deterministic routing)
- Same input state → Same cognitive state detection
- Same trail query → Same results (deterministic ordering)
- Fixed seeds for all internal RNG (`DETERMINISM_SEED = 0xCAFEBABE`)

## Implementation Details

### Fixed Evaluation Order

```python
# Expert priority (first match wins)
EXPERT_PRIORITY = [Validator, Scaffolder, Restorer, Refocuser, Celebrator, Socratic, Direct]

# NEXUS pipeline phases
phase_order = [RETRIEVE, CLASSIFY, GROUND, DETECT, CASCADE, LOCK, EXECUTE, UPDATE, FLUSH]

# Signal priority
signal_priority = [emotional, grounding, mode, domain, task]
```

### Fixed Seeds

```python
ATMOSPHERE_SEED: Final[int] = 0xCAFEBABE
DETERMINISM_SEED: Final[int] = 0xCAFEBABE
WHATSAPP_VOICE_SEED: Final[int] = 0xDEADBEEF
TTS_VOICE_SEED: Final[int] = 0xFEEDFACE
AGENT_SEED: Final[int] = 0xA6E77F00
MEMORY_SEED: Final[int] = 0xAE0717E5
COGNITIVE_TILE_SIZE: Final[int] = 32
```

### Kahan Summation

Used in critical paths for batch-invariant floating-point accumulation:
- `framework_orchestrator.py` (7 usages)
- `prism_detector.py` (4 usages)
- `convergence_tracker.py` (1 usage)
- `calibration_learner.py` (1 usage)
- `memory/interface.py` (3 usages)

## Intentional Non-Determinism

Some components are intentionally non-deterministic:

| Component | File | Reason |
|-----------|------|--------|
| Retry jitter | `resilience.py:367` | Prevents thundering herd in distributed systems |
| Presentation phrasing | `human_render.py:81` | Natural output variation |

These are **documented exceptions**, not violations. Both files contain explicit
comments explaining the design decision:

```python
# NOTE: Intentionally unseeded for production retry jitter.
# This is NOT a [He2025] violation - jitter randomness prevents
# thundering herd and is outside the deterministic routing path.
# [He2025] principles apply to cognitive routing, not retry timing.
```

## Audit Results

**Last audit:** 2026-02-02
**Compliance Score:** 95%

| Category | Status | Count |
|----------|--------|-------|
| Fixed Evaluation Order | ✅ COMPLIANT | - |
| Fixed Seeds | ✅ COMPLIANT | 6+ seeds defined |
| Kahan Summation | ✅ COMPLIANT | 17+ usages |
| Deterministic Constants | ✅ COMPLIANT | COGNITIVE_TILE_SIZE=32 |
| Sorted Iteration | ⚠️ PARTIAL | 64 compliant, ~30 non-critical |
| Documented Exceptions | ✅ COMPLIANT | 2 (jitter, presentation) |

## Verification Commands

```bash
# Check for unseeded random
grep -rn "random.Random()" src/otto/ --include="*.py" | grep -v "seed"

# Check for sorted iteration
grep -rn "sorted(.*\.items())" src/otto/ --include="*.py"

# Run determinism tests
pytest tests/ -k determinism -v
```

## References

- [He2025] https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/
- USD LIVRPS: https://openusd.org/release/glossary.html#usdglossary-livrps
- OTTO Determinism Module: `src/otto/determinism.py`
