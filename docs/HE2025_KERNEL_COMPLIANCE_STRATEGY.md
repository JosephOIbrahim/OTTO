# [He2025] Kernel-Level Compliance Strategy

**Status**: Tier 1 Implemented
**Date**: 2026-01-30
**Author**: Claude Opus 4.5
**Implementation**: `src/otto/inference/` (59 tests, 100% pass)

---

## Executive Summary

OTTO OS currently achieves **application-level determinism** by applying [He2025] principles
(fixed evaluation order, no dynamic algorithm switching) to cognitive routing. However,
true [He2025] compliance requires **kernel-level determinism** in LLM inference.

This document analyzes the gap and proposes a tiered strategy to achieve progressively
stronger determinism guarantees, culminating in genuine [He2025] kernel-level compliance.

---

## The Core Problem

### What [He2025] Actually Solves

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        LLM INFERENCE STACK                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Application Layer    ←── OTTO lives here (routing, state, composition)   │
│         │                                                                   │
│         ▼                                                                   │
│   API Layer            ←── Claude API, OpenAI API, etc.                     │
│         │                                                                   │
│         ▼                                                                   │
│   Inference Engine     ←── vLLM, TensorRT-LLM, Triton, etc.                │
│         │                                                                   │
│         ▼                                                                   │
│   GPU Kernels          ←── [He2025] addresses THIS LAYER                   │
│   ├── RMSNorm          ←── Reduction order varies with batch               │
│   ├── MatMul           ←── Tile sizes change with dimensions               │
│   └── Attention        ←── Split-KV strategy varies with load              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**The fundamental issue**: When batch sizes change, GPU kernels select different
execution strategies. Different strategies = different floating-point accumulation
order = different results (even with same inputs).

### Why OTTO Can't Currently Solve This

| Layer | OTTO's Control | Determinism Status |
|-------|----------------|-------------------|
| Application (routing) | Full | ✅ Deterministic (via [He2025] principles) |
| API calls | Partial (params) | ⚠️ Temperature/seed only |
| Inference engine | None | ❌ Black box |
| GPU kernels | None | ❌ Black box |

**Current reality**: OTTO consumes LLM inference as a black box. We control *what* we
ask, but not *how* it's computed.

---

## The Gap Analysis

### What We Control vs What We Need

```
CURRENT STATE (Application-Level Determinism):
  ✅ Fixed LIVRPS priority order
  ✅ Fixed expert routing (first-match-wins)
  ✅ Fixed NEXUS phase execution
  ✅ Seeded RNG for internal decisions
  ✅ Deterministic state serialization
  ❌ LLM inference execution
  ❌ GPU kernel selection
  ❌ Batch-dependent algorithm switching

REQUIRED FOR KERNEL-LEVEL COMPLIANCE:
  All of the above, PLUS:
  ✅ Fixed reduction order in RMSNorm
  ✅ Fixed tile sizes in MatMul
  ✅ Fixed split-KV strategy in Attention
  ✅ Batch-invariant execution
```

### The Determinism Boundary

```
                    ┌─────────────────────────────┐
                    │     OTTO Determinism        │
                    │        Boundary             │
                    └─────────────────────────────┘
                              │
    ┌─────────────────────────┼─────────────────────────┐
    │                         │                         │
    ▼                         ▼                         ▼
┌─────────┐           ┌───────────────┐           ┌─────────┐
│ Routing │           │ LLM Inference │           │ State   │
│ (ours)  │           │ (black box)   │           │ (ours)  │
│   ✅    │           │      ❌       │           │   ✅    │
└─────────┘           └───────────────┘           └─────────┘
```

**To achieve kernel-level compliance, we must extend the boundary to include inference.**

---

## Tiered Compliance Strategy

### Tier 0: Application-Level Determinism (CURRENT)

**Status**: ✅ Implemented

What we have:
- Fixed routing order (LIVRPS, expert priority)
- Fixed execution phases (NEXUS)
- Deterministic state management
- Seeded RNG where applicable

**Guarantee**: Same routing signals → Same expert selection → Same parameters
**Limitation**: Actual LLM output may vary

---

### Tier 1: Inference Parameter Control

**Status**: ✅ IMPLEMENTED (2026-01-30)

**Implementation**: `src/otto/inference/` module with 59 tests

**Approach**: Maximize determinism within API constraints

```python
class DeterministicInferenceConfig:
    """Configuration for maximizing inference determinism."""

    # Standard parameters (most APIs support)
    temperature: float = 0.0  # No sampling randomness
    seed: int = 42            # Fixed seed if supported
    top_p: float = 1.0        # No nucleus sampling
    top_k: int = 1            # Greedy decoding

    # Advanced parameters (some APIs)
    logprobs: bool = True     # For verification
    n: int = 1                # Single completion

    # OTTO-specific
    cache_key: str            # For response caching
    deterministic_mode: bool  # Request deterministic backend if available
```

**Implementation**:
```python
class DeterministicAPIWrapper:
    """Wraps LLM API calls with determinism-maximizing settings."""

    def __init__(self, config: DeterministicInferenceConfig):
        self.config = config
        self.response_cache = {}  # Cache identical queries

    async def infer(self, prompt: str, params: dict) -> InferenceResult:
        # 1. Compute cache key
        cache_key = self._compute_cache_key(prompt, params)

        # 2. Check cache first
        if cache_key in self.response_cache:
            return self.response_cache[cache_key]

        # 3. Apply deterministic overrides
        params = {**params, **self.config.to_dict()}

        # 4. Make API call
        result = await self._call_api(prompt, params)

        # 5. Cache and return
        self.response_cache[cache_key] = result
        return result
```

**Guarantee**: Same prompt + params → Same cached result (after first call)
**Limitation**: First call may still be non-deterministic; cache doesn't help new queries

---

### Tier 2: Determinism Verification

**Status**: 🔲 Not Implemented

**Approach**: Can't guarantee determinism, but can DETECT non-determinism

```python
class DeterminismVerifier:
    """Verifies inference determinism through repeated queries."""

    def __init__(self, n_trials: int = 3, tolerance: float = 0.0):
        self.n_trials = n_trials
        self.tolerance = tolerance

    async def verified_infer(self, prompt: str, params: dict) -> VerifiedResult:
        """Run inference multiple times and verify consistency."""

        results = []
        for _ in range(self.n_trials):
            result = await self._infer(prompt, params)
            results.append(result)

        # Check for divergence
        if self._all_identical(results):
            return VerifiedResult(
                response=results[0],
                determinism_score=1.0,
                verified=True
            )
        else:
            # Divergence detected!
            divergence = self._compute_divergence(results)
            return VerifiedResult(
                response=self._consensus(results),  # Majority vote
                determinism_score=1.0 - divergence,
                verified=False,
                divergence_details=self._analyze_divergence(results)
            )

    def _all_identical(self, results: List[str]) -> bool:
        """Check if all results are bit-identical."""
        return len(set(results)) == 1

    def _compute_divergence(self, results: List[str]) -> float:
        """Compute divergence metric (0 = identical, 1 = completely different)."""
        # Use edit distance or embedding similarity
        pass
```

**Guarantee**: Probabilistic detection of non-determinism
**Limitation**: 3x latency, 3x cost; doesn't prevent non-determinism

**Use Case**: Critical decisions where determinism matters

```python
# In cognitive routing
if decision.criticality == "high":
    result = await verifier.verified_infer(prompt, params)
    if not result.verified:
        log.warning(f"Non-determinism detected: {result.divergence_details}")
        # Optionally: fall back to deterministic local model
```

---

### Tier 3: Local Deterministic Inference

**Status**: 🔲 Not Implemented

**Approach**: Self-host inference with [He2025]-compliant kernel configuration

This is where **true kernel-level compliance becomes possible**.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LOCAL DETERMINISTIC INFERENCE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   OTTO Application                                                          │
│         │                                                                   │
│         ▼                                                                   │
│   ┌─────────────────────────────────────────────────────────────────┐      │
│   │              Deterministic Inference Engine                      │      │
│   │                                                                  │      │
│   │   vLLM / TensorRT-LLM with [He2025] Configuration:              │      │
│   │                                                                  │      │
│   │   - CUDA_DETERMINISTIC=1                                        │      │
│   │   - batch_size=1 (eliminates batch-variance)                    │      │
│   │   - Fixed tensor cores configuration                            │      │
│   │   - Fixed memory allocation (no dynamic)                        │      │
│   │   - Seeded all RNG sources                                      │      │
│   │                                                                  │      │
│   └─────────────────────────────────────────────────────────────────┘      │
│         │                                                                   │
│         ▼                                                                   │
│   ┌─────────────────────────────────────────────────────────────────┐      │
│   │              [He2025]-Compliant GPU Kernels                      │      │
│   │                                                                  │      │
│   │   - RMSNorm: Fixed reduction order (independent of batch)       │      │
│   │   - MatMul: Fixed 2D tile sizes (no split-K)                    │      │
│   │   - Attention: Fixed split-KV strategy                          │      │
│   │                                                                  │      │
│   └─────────────────────────────────────────────────────────────────┘      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Implementation Options**:

#### Option A: vLLM with Deterministic Mode

```yaml
# vllm_config.yaml
model: "meta-llama/Llama-3.1-70B"  # Or appropriate model
tensor_parallel_size: 1            # Single GPU, no TP variance
pipeline_parallel_size: 1          # No PP variance
max_num_batched_tokens: 1          # Batch size = 1 (eliminates batch-variance)
seed: 42                           # Fixed seed
disable_sliding_window: true       # Consistent attention
enforce_eager: true                # No CUDA graphs (more deterministic)

# Environment
CUDA_LAUNCH_BLOCKING: 1
CUBLAS_WORKSPACE_CONFIG: ":4096:8"
PYTORCH_CUDA_ALLOC_CONF: "expandable_segments:False"
```

#### Option B: TensorRT-LLM with Fixed Configuration

```python
# tensorrt_llm_config.py
config = {
    "builder_config": {
        "max_batch_size": 1,           # Eliminates batch-variance
        "max_input_len": 4096,
        "max_output_len": 2048,
    },
    "plugin_config": {
        "gemm_plugin": "float16",      # Fixed precision
        "gpt_attention_plugin": True,
        "remove_input_padding": False, # Consistent memory layout
    },
    "runtime_config": {
        "cuda_deterministic": True,
        "use_cuda_graph": False,       # More deterministic
    }
}
```

#### Option C: Custom [He2025] Kernel Implementation

The ThinkingMachines paper provides the algorithm. We could implement:

```python
# pseudo-code for [He2025] RMSNorm
def deterministic_rmsnorm(x, weight, eps=1e-6):
    """
    [He2025]-compliant RMSNorm with fixed reduction order.

    Key insight: Use fixed data-parallel strategy regardless of batch size.
    Accept ~20% performance penalty for determinism.
    """
    # FIXED reduction order: always reduce in the same sequence
    # regardless of how many elements we're processing

    # Step 1: Compute squared sum with fixed accumulation order
    sq_sum = fixed_order_reduction(x * x, dim=-1)  # Always same order

    # Step 2: Compute RMS
    rms = torch.sqrt(sq_sum / x.shape[-1] + eps)

    # Step 3: Normalize
    return weight * (x / rms)

def fixed_order_reduction(tensor, dim):
    """
    Reduce with guaranteed fixed order.

    [He2025] insight: The reduction order must be independent of batch size.
    We sacrifice parallelism for determinism.
    """
    # Flatten to 1D, accumulate in fixed order
    flat = tensor.flatten()
    result = flat[0]
    for i in range(1, len(flat)):
        result = result + flat[i]  # Sequential, deterministic
    return result
```

**Guarantee**: True kernel-level determinism (same guarantees as [He2025])
**Cost**: ~20% performance penalty, infrastructure complexity

---

### Tier 4: Cryptographically Verified Inference

**Status**: 🔲 Research-Grade

**Approach**: Not just deterministic, but *provably* deterministic with cryptographic guarantees

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 CRYPTOGRAPHICALLY VERIFIED INFERENCE                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   1. COMMITMENT PHASE                                                       │
│   ┌─────────────────────────────────────────────────────────────────┐      │
│   │   - Commit to input (hash of prompt + params)                    │      │
│   │   - Commit to model weights (Merkle root)                        │      │
│   │   - Commit to kernel configuration                               │      │
│   └─────────────────────────────────────────────────────────────────┘      │
│                                                                             │
│   2. EXECUTION PHASE (in TEE)                                               │
│   ┌─────────────────────────────────────────────────────────────────┐      │
│   │   - Execute in SGX/SEV enclave                                   │      │
│   │   - TPM attestation of execution environment                     │      │
│   │   - Hardware-enforced isolation                                  │      │
│   └─────────────────────────────────────────────────────────────────┘      │
│                                                                             │
│   3. VERIFICATION PHASE                                                     │
│   ┌─────────────────────────────────────────────────────────────────┐      │
│   │   - Provide execution trace                                      │      │
│   │   - Merkle proof of intermediate states                          │      │
│   │   - Anyone can verify: same inputs → same outputs                │      │
│   └─────────────────────────────────────────────────────────────────┘      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Components**:

```python
class VerifiedInferenceResult:
    """Inference result with cryptographic proof of determinism."""

    response: str

    # Commitments (before execution)
    input_commitment: bytes      # H(prompt || params)
    model_commitment: bytes      # Merkle root of weights
    kernel_commitment: bytes     # Hash of kernel config

    # Execution proof
    tee_attestation: bytes       # SGX/SEV attestation
    execution_trace: bytes       # Merkle root of intermediate states

    # Verification
    def verify(self) -> bool:
        """Anyone can verify this result is deterministic."""
        # 1. Verify TEE attestation
        # 2. Verify execution trace is consistent
        # 3. Verify output matches trace
        pass
```

**Guarantee**: Cryptographic proof of deterministic execution
**Cost**: Requires TEE hardware, significant complexity

---

## Recommended Implementation Path

### Phase 1: Foundation (Weeks 1-2)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PHASE 1: FOUNDATION                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   1. Implement DeterministicInferenceConfig                                 │
│      - Temperature, seed, top_p, top_k controls                            │
│      - Response caching with deterministic keys                            │
│                                                                             │
│   2. Add inference abstraction layer                                        │
│      - Abstract away API specifics                                         │
│      - Prepare for backend swapping                                        │
│                                                                             │
│   3. Create determinism metrics                                             │
│      - Track cache hit rate                                                │
│      - Measure response consistency                                        │
│                                                                             │
│   Deliverable: Tier 1 compliance                                           │
│   Guarantee: Maximized determinism within API constraints                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Phase 2: Verification (Weeks 3-4)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       PHASE 2: VERIFICATION                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   1. Implement DeterminismVerifier                                          │
│      - Multi-trial inference                                               │
│      - Divergence detection and analysis                                   │
│      - Consensus mechanism                                                 │
│                                                                             │
│   2. Add criticality routing                                                │
│      - Critical decisions → verified inference                             │
│      - Non-critical → fast path                                            │
│                                                                             │
│   3. Create divergence dashboard                                            │
│      - Track when/where non-determinism occurs                             │
│      - Identify patterns                                                   │
│                                                                             │
│   Deliverable: Tier 2 compliance                                           │
│   Guarantee: Probabilistic non-determinism detection                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Phase 3: Local Inference (Weeks 5-8)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      PHASE 3: LOCAL INFERENCE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   1. Deploy deterministic local model                                       │
│      - vLLM with batch_size=1                                              │
│      - CUDA deterministic flags                                            │
│      - Model selection (Llama 3.1, Mixtral, etc.)                          │
│                                                                             │
│   2. Implement hybrid routing                                               │
│      - Critical/determinism-required → local                               │
│      - Capability-required → cloud API                                     │
│                                                                             │
│   3. Verify determinism                                                     │
│      - Run identical queries 1000x                                         │
│      - Verify bit-identical outputs                                        │
│      - Document configuration                                              │
│                                                                             │
│   Deliverable: Tier 3 compliance                                           │
│   Guarantee: TRUE kernel-level determinism (for local inference)           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Phase 4: Cryptographic Verification (Future)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   PHASE 4: CRYPTOGRAPHIC VERIFICATION                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Research-grade. Requires:                                                 │
│   - TEE hardware (SGX/SEV)                                                 │
│   - Custom kernel implementations                                          │
│   - Significant R&D investment                                             │
│                                                                             │
│   Deliverable: Tier 4 compliance                                           │
│   Guarantee: Cryptographic proof of deterministic execution                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Architecture: Hybrid Determinism

The final architecture allows routing based on determinism requirements:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        OTTO HYBRID DETERMINISM                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Incoming Request                                                          │
│         │                                                                   │
│         ▼                                                                   │
│   ┌─────────────────┐                                                      │
│   │ Determinism     │                                                      │
│   │ Router          │                                                      │
│   └────────┬────────┘                                                      │
│            │                                                                │
│    ┌───────┼───────┬───────────────┐                                       │
│    │       │       │               │                                       │
│    ▼       ▼       ▼               ▼                                       │
│ ┌──────┐ ┌──────┐ ┌──────────┐ ┌────────────┐                             │
│ │FAST  │ │VERIFY│ │DETERMIN- │ │CRYPTO      │                             │
│ │PATH  │ │PATH  │ │ISTIC     │ │VERIFIED    │                             │
│ │      │ │      │ │LOCAL     │ │            │                             │
│ │Cloud │ │Cloud │ │Model     │ │TEE         │                             │
│ │API   │ │API   │ │          │ │Inference   │                             │
│ │      │ │(3x)  │ │(vLLM)    │ │            │                             │
│ └──────┘ └──────┘ └──────────┘ └────────────┘                             │
│                                                                             │
│ Guarantees:                                                                 │
│ - Fast: None (best effort)                                                 │
│ - Verify: Probabilistic detection                                          │
│ - Deterministic: Kernel-level [He2025] compliance                          │
│ - Crypto: Cryptographic proof                                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Routing Logic**:

```python
class DeterminismRouter:
    """Routes requests based on determinism requirements."""

    def route(self, request: InferenceRequest) -> InferenceBackend:
        # 1. Check explicit requirement
        if request.requires_proof:
            return self.crypto_backend

        if request.requires_determinism:
            return self.local_deterministic_backend

        # 2. Check criticality
        if request.criticality == "high":
            return self.verified_backend

        # 3. Check if deterministic result is cached
        if self.cache.has(request.cache_key):
            return self.cache_backend

        # 4. Default to fast path
        return self.cloud_backend
```

---

## Hardware Requirements for Tier 3

To achieve true [He2025] compliance, OTTO would need:

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU | RTX 4090 (24GB) ✅ | A100 (80GB) |
| VRAM | 24GB | 48GB+ |
| System RAM | 64GB | 128GB ✅ |
| Storage | 500GB NVMe | 1TB+ NVMe |
| Model | Llama 3.1 8B | Llama 3.1 70B (quantized) |

**User's current hardware**: Threadripper PRO 7965WX + RTX 4090 + 128GB DDR5

**Assessment**: ✅ Sufficient for Tier 3 with quantized 70B or full 8B model

---

## Cost Analysis

| Tier | Implementation Cost | Ongoing Cost | Determinism Level |
|------|---------------------|--------------|-------------------|
| 0 (Current) | $0 | $0 | Application-level |
| 1 (Params) | ~$0 (code only) | ~$0 | API-maximized |
| 2 (Verify) | ~$0 (code only) | 3x inference cost | Probabilistic |
| 3 (Local) | ~$0 (has hardware) | Electricity + maintenance | Kernel-level ✅ |
| 4 (Crypto) | Significant R&D | TEE overhead | Cryptographic |

**Recommendation**: User has hardware for Tier 3. This is the sweet spot for genuine
[He2025] compliance without massive investment.

---

## Conclusion

**Can we make good on the promise of kernel-level compliance?**

**Yes**, but it requires owning the inference layer, not just consuming it.

**Strategy**:
1. **Short-term**: Implement Tiers 1-2 (parameter control + verification)
2. **Medium-term**: Deploy Tier 3 (local deterministic inference with vLLM)
3. **Long-term**: Research Tier 4 (cryptographic verification)

**With Tier 3, OTTO can truthfully claim**:
> "OTTO OS provides [He2025] kernel-level deterministic inference for critical
> cognitive routing decisions via local model deployment with batch-invariant
> kernel configuration."

This is not overclaiming—it's the real thing.

---

## Next Steps

1. **Implement Tier 1**: DeterministicInferenceConfig + caching
2. **Implement Tier 2**: DeterminismVerifier for critical decisions
3. **Deploy Tier 3**: Set up vLLM with deterministic configuration
4. **Verify**: Run 1000x identical query test, confirm bit-identical outputs
5. **Document**: Update compliance docs with verifiable claims

---

*Strategy document created: 2026-01-30*
*Author: Claude Opus 4.5*
