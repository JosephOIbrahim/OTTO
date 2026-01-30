# Decision Engine Migration Guide (v4.3.0)

## Overview

Otto v4.3.0 introduces `DecisionEngine` as the primary entry point for task routing, implementing the work/delegate/protect model with ThinkingMachines [He2025] batch-invariance compliance.

**One-Liner:** "Otto helps you finish projects by knowing when to do the work yourself, when to delegate to agents, and when to protect your flow."

## What Changed

### New 7-Phase Execution Model

```
PHASE 1: SNAPSHOT    → CognitiveState snapshot + context hash
PHASE 2: DETECT      → PRISM signals (FIXED order: emotional > mode > domain > task)
PHASE 3: SAFETY GATE → ADHD constraints (burnout=RED → recovery menu)
PHASE 4: ROUTE       → DecisionEngine.process_task() with pre-computed table
PHASE 5: EXECUTE     → Branch by DecisionMode (WORK/DELEGATE/PROTECT)
PHASE 6: COLLECT     → Gather results, determinism guard, checksum
PHASE 7: UPDATE      → Batch update state, persist, return synthesis
```

### Decision Modes

| Mode | When | Behavior |
|------|------|----------|
| **WORK** | Simple tasks, low budget, can't spawn | Direct action, minimal agents (1-2) |
| **DELEGATE** | Complex/parallel tasks, high budget | Spawn agents per ExecutionPlan |
| **PROTECT** | Peak flow, emotional signals, RED burnout | Queue task, preserve momentum |

### Pre-Computed Routing Table

Routing is now table-driven for determinism:

```python
ROUTING_TABLE = [
    # (signal, complexity, budget, flow) → (mode, agents, rationale)
    (("emotional", "*", "*", "*"), (DecisionMode.PROTECT, [], "Safety first")),
    (("*", "*", "*", "peak"), (DecisionMode.PROTECT, [], "Protecting flow")),
    (("*", "complex", "high", "*"), (DecisionMode.DELEGATE, [...], "Parallel delegation")),
    # ... more patterns
    (("*", "*", "*", "*"), (DecisionMode.WORK, [...], "Default")),
]
```

## Migration Path

| Phase | Action | Status |
|-------|--------|--------|
| 1 | DecisionEngine integration with feature flag | ✅ Complete |
| 2 | A/B testing (run both paths, log differences) | Available |
| 3 | Default `use_decision_engine=True`, deprecate `_route_task()` | ✅ Current |
| 4 | Remove `_route_task()` | Future (breaking) |

## How to Use

### Default Behavior (Recommended)

No changes needed. `FrameworkOttotor` uses `DecisionEngine` by default.

```python
ottotor = FrameworkOttotor()
result = await ottotor.ottote("Your task here")

# Result includes decision info
print(result["decision_mode"])      # "work", "delegate", or "protect"
print(result["decision_rationale"]) # Explanation
```

### Legacy Mode (Backward Compatibility)

To use the old `_route_task()` behavior:

```python
ottotor = FrameworkOttotor()
ottotor.use_decision_engine = False
```

Note: `_route_task()` is deprecated and will be removed in a future version.

### Direct DecisionEngine Usage

For custom integrations:

```python
from otto.decision_engine import DecisionEngine, TaskRequest, TaskCategory

engine = DecisionEngine(cognitive_stage=your_stage)

request = TaskRequest(
    description="Implement feature X",
    category=TaskCategory.IMPLEMENTATION,
    files_involved=["file1.py", "file2.py"],
    estimated_scope="medium"
)

plan = engine.process_task(request, context={})

if plan.decision.mode == DecisionMode.WORK:
    # Direct action
    agents = plan.get_routed_agents()
elif plan.decision.mode == DecisionMode.DELEGATE:
    # Parallel execution
    agents = plan.get_routed_agents()
elif plan.decision.mode == DecisionMode.PROTECT:
    # Queue and preserve flow
    pass
```

## Feature Flag

The feature flag `use_decision_engine` controls routing:

| Value | Behavior |
|-------|----------|
| `True` (default) | Uses `DecisionEngine` with table routing |
| `False` | Uses legacy `_route_task()` with keyword matching |

## PROTECT Mode: Result Queuing

When in PROTECT mode (peak flow or emotional signals), results are queued:

```python
# Results queued during peak flow
coordinator = engine.coordinator

# Check for pending results at natural break points
pending = coordinator.get_pending_results_for_delivery()
if pending:
    for result in pending:
        print(f"Queued: {result.summary}")

# Queue is persisted to ~/.otto/state/result_queue.json
```

## Testing

Run the verification tests:

```bash
cd Otto
python -m pytest tests/test_decision_engine.py -v
```

Tests verify:
- Determinism (same input → same checksum)
- Batch invariance (Task B routing identical regardless of Task A)
- Safety gating (burnout=RED forces recovery)
- PROTECT mode (peak flow queues results)

## Breaking Changes

None in v4.3.0. The migration is backward compatible.

Future v4.4.0 will remove `_route_task()`.

## Troubleshooting

### Deprecation Warning

If you see:
```
DeprecationWarning: _route_task() is deprecated. Use DecisionEngine.process_task() instead.
```

Update your code to use `DecisionEngine` or set `use_decision_engine=True`.

### Result Not Delivered

If results aren't being delivered:
1. Check if flow protection is active: `coordinator.flow_protection_active`
2. Check momentum phase: `context.momentum_phase`
3. Results queue during `peak` momentum

### Determinism Verification

To verify determinism:

```python
results = [engine.process_task(task, {}) for _ in range(100)]
assert len(set(r.checksum for r in results)) == 1
```

## References

- [He2025] He, Horace and Thinking Machines Lab, "Defeating Nondeterminism in LLM Inference"
- Architecture plan: `docs/architecture/decision_engine_plan.md`
- Tests: `tests/test_decision_engine.py`
