# Determinism in Framework Ottotor

## Overview

Framework Ottotor achieves deterministic behavior through batch-invariant design principles. This document explains how determinism is enforced and its relationship to the ThinkingMachines research on defeating nondeterminism in LLM inference.

## The Problem: Why LLMs Are Non-Deterministic

Common belief: "LLM randomness comes from temperature and sampling."

**Reality**: Even at temperature=0, LLMs produce different outputs. ThinkingMachines (2025) demonstrated **80 unique completions from 1000 identical requests** at temperature=0.

### Root Cause: Batch Invariance Failure

The primary source of nondeterminism is **batch-size variance affecting kernel outputs**:

```
Different batch sizes → Different reduction orders → Different floating-point results
```

This occurs because:
- Matrix multiplication implementations change reduction strategies based on batch dimensions
- Attention kernels apply different split-reduction strategies across varying loads
- Different tensor-core instructions activate at different batch sizes

**Key insight**: `(a + b) + c ≠ a + (b + c)` in floating-point arithmetic. When reduction order changes, numerics change.

## The Solution: Batch-Invariant Design

### Framework Ottotor's Approach

```python
# DeterminismGuard configuration (framework_ottotor.py)
determinism_config = {
    "batch_size": 1,                    # Critical: eliminates batch variance
    "cudnn_deterministic": True,        # Deterministic CUDA operations
    "cudnn_benchmark": False,           # Disable autotuning
    "float32_matmul_precision": "highest",
    "seed": seed                        # Reproducible randomness
}
```

### Why `batch_size=1` Matters

| Batch Size | Reduction Order | Determinism |
|------------|-----------------|-------------|
| Variable | Changes with load | **Non-deterministic** |
| Fixed (any) | Consistent | Deterministic within batch |
| **1** | Single element | **Fully deterministic** |

With `batch_size=1`, there's no reduction variance—each inference is independent and reproducible.

## Determinism Guarantees

### What IS Deterministic

| Component | Determinism | How |
|-----------|-------------|-----|
| Task routing | **YES** | Hash-based expert selection |
| Agent activation | **YES** | Fixed keyword matching rules |
| Expert selection | **YES** | `md5(task) % len(experts)` |
| State updates | **YES** | LIVRPS priority resolution |
| Checksum computation | **YES** | Sorted JSON serialization |

### What Requires ThinkingMachines Kernels

| Component | Without TM | With ThinkingMachines |
|-----------|------------|----------------------|
| LLM signal detection | Partial | **Fully deterministic** |
| LLM generation | **NO** | **YES** |
| Semantic parsing | **NO** | **YES** |

### Irreducible Stochasticity

These are inherently non-deterministic and no architecture can fix them:
- Human input (what the user types)
- Human response (how the user reacts)
- Real-world timestamps (unless mocked)

## Reproducibility Contract

```
GIVEN:
  1. Identical user input string
  2. Identical ottotor state
  3. Identical timestamp (or deterministic mock)
  4. Same model version
  5. Same hardware configuration

GUARANTEE:
  ✓ Identical routing decision
  ✓ Identical agent activation
  ✓ Identical expert selection
  ✓ Identical state update
  ✓ Identical checksum

REQUIRES ThinkingMachines:
  ✓ Identical LLM response
  ✓ Identical signal detection
```

## Implementation Details

### Hash-Based Expert Selection

```python
# MoERouterAgent - Deterministic routing
routing_input = f"{task}:{seed}"
query_hash = hashlib.sha256(routing_input.encode()).hexdigest()

for i, expert in enumerate(self.EXPERTS.keys()):
    segment = query_hash[i*8:(i+1)*8]
    score = int(segment, 16) / (16**8)
    expert_scores[expert] = round(score, 4)
```

Same `task` + `seed` → Same hash → Same expert scores → Same routing.

### Checksum Generation

```python
# Every agent output includes a reproducible checksum
output_str = json.dumps(output, sort_keys=True, default=str)
checksum = hashlib.sha256(output_str.encode()).hexdigest()[:16]
```

`sort_keys=True` ensures dictionary order doesn't affect the hash.

### Master Checksum

```python
# Aggregated checksum across all agents
all_checksums = sorted([r.checksum for r in result_map.values()])
combined = "".join(all_checksums)
master_checksum = hashlib.sha256(combined.encode()).hexdigest()[:32]
```

The master checksum changes if ANY agent's output changes.

## ThinkingMachines Integration

### What ThinkingMachines Provides

Batch-invariant kernels for:
- **RMSNorm**: Data-parallel strategies (one batch element per core)
- **Matrix multiplication**: Consistent tile sizes across all batch sizes
- **Attention**: Fixed split-size (not fixed split count)

### Performance Trade-off

| Configuration | Performance | Determinism |
|---------------|-------------|-------------|
| Standard vLLM | Baseline | Non-deterministic |
| TM initial | 2.1× slower | **Deterministic** |
| TM optimized | 1.6× slower | **Deterministic** |

The 1.6× overhead is acceptable for applications requiring reproducibility.

### Integration Pattern

```python
# Hypothetical ThinkingMachines integration
from thinkingmachines import BatchInvariantEngine

engine = BatchInvariantEngine(
    model="your-model",
    batch_size=1,
    deterministic_attention=True
)

# Guaranteed: same prompt → same output
response = engine.generate(prompt)
```

## Verification

### Testing Determinism

```python
# Run same task twice, compare checksums
result1 = await ottotor.ottote("test task", context)
result2 = await ottotor.ottote("test task", context)

assert result1["master_checksum"] == result2["master_checksum"]
```

### Debugging Non-Determinism

If checksums differ:
1. Check `batch_size` configuration
2. Verify `cudnn_deterministic=True`
3. Ensure fixed `seed` value
4. Compare individual agent checksums to isolate the source

## References

1. He, Horace and Thinking Machines Lab. (2025). "Defeating Nondeterminism in LLM Inference." *Thinking Machines Lab: Connectionism*, September 2025. https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/

2. NVIDIA. (2024). *cuDNN Developer Guide: Reproducibility*. https://docs.nvidia.com/deeplearning/cudnn/developer-guide/index.html

3. PyTorch. (2024). *Reproducibility*. https://pytorch.org/docs/stable/notes/randomness.html

---

## Summary

| Aspect | Framework Ottotor | With ThinkingMachines |
|--------|------------------------|----------------------|
| Routing | Deterministic | Deterministic |
| Expert selection | Deterministic | Deterministic |
| State management | Deterministic | Deterministic |
| LLM generation | Non-deterministic | **Deterministic** |
| **Overall** | **Routing deterministic** | **Fully deterministic** |

Framework Ottotor guarantees deterministic *routing and state management*. Full end-to-end determinism (including LLM generation) requires ThinkingMachines batch-invariant kernels.
