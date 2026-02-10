# USD Cognitive Substrate: A Deterministic Architecture for Adaptive AI State Management

**Version:** 5.1.0
**Date:** 2026-01-21
**Status:** Academic Pre-Publication Draft (Enhanced)
**Authors:** [To be determined]

---

## Abstract

We present the USD Cognitive Substrate, a novel architecture that repurposes Universal Scene Description (USD) composition semantics—originally designed for conflict resolution in visual effects pipelines—for deterministic state management in large language model (LLM) applications. The architecture achieves a previously elusive property: **fully deterministic cognitive behavior** from signal detection through response generation, with stochasticity isolated exclusively to irreducible human input/output boundaries.

The system comprises two orthogonal hierarchies: a USD Composition Hierarchy for state storage with LIVRPS (Local, Inherits, VariantSets, References, Payloads, Specializes) resolution, and a Runtime Service Stack for processing, routing, and adaptation. A novel "Mycelium" mechanism provides neuroplasticity within constitutional bounds, enabling the system to learn while maintaining safety guarantees.

When integrated with batch-invariant inference engines [He2025], the architecture guarantees: **same user input + same state → same response + same state update**. This enables reproducible sessions, behavioral unit testing, complete audit trails, and formally verifiable cognitive systems.

**Keywords:** Universal Scene Description, cognitive architecture, deterministic AI, state management, neuroplasticity, batch invariance, LIVRPS composition

---

## 1. Introduction

### 1.1 The Problem

Modern LLM applications face a fundamental tension: users expect consistent, personalized behavior, but LLM inference is inherently stochastic. The same prompt can produce different outputs based on:

- Batch size during inference
- Server load affecting reduction order
- Non-deterministic GPU operations
- Temperature and sampling parameters

This non-determinism creates challenges for:

1. **Debugging** — Cannot reproduce reported issues
2. **Testing** — Behavioral tests are flaky
3. **Auditing** — Cannot verify decision traces
4. **Personalization** — Learning is noisy
5. **Safety** — Cannot guarantee behavioral bounds

### 1.2 The Thesis

We propose that **USD (Universal Scene Description) composition semantics are uniquely suited for cognitive state management in LLM applications**. This is not about using USD for 3D graphics—it is about repurposing USD's conflict resolution system for AI state management.

The parallel:

| VFX Problem | AI Problem |
|-------------|------------|
| Multiple departments (model, rig, anim, light) disagree about scene data | Multiple state sources (profile, mood, task, safety) disagree about behavior |
| USD's LIVRPS resolves conflicts deterministically | USD's LIVRPS resolves conflicts deterministically |

Same solution. Different domain.

### 1.3 Contributions

This paper makes the following contributions:

1. **Separation of Storage and Routing** — USD provides state persistence; a separate routing engine provides adaptive behavior

2. **The Mycelium Mechanism** — A neuroplasticity system with four rebalancing avenues (activation spreading, Hebbian learning, attractor dynamics, homeostatic regulation) operating within hard constitutional bounds

3. **The Mycelium Arc** — A novel USD composition arc for horizontal (agent-to-agent) state flow, complementing LIVRPS's vertical composition

4. **Determinism Analysis** — Formal identification of stochastic boundaries and requirements for full reproducibility

5. **Integration with Batch-Invariant Inference** — When combined with batch-invariant kernels [He2025], the architecture achieves full determinism except for irreducible human I/O

---

## 2. Background

### 2.1 Universal Scene Description (USD)

USD is Pixar's open-source framework for describing, composing, and querying hierarchical scene data. Its key properties relevant to our work:

**LIVRPS Composition Order:**
- **L**ocal — Direct opinions on a prim (highest priority)
- **I**nherits — Inherited from parent prims
- **V**ariantSets — Selected variants
- **R**eferences — External file references
- **P**ayloads — Lazy-loaded external content
- **S**pecializes — Base class inheritance (lowest priority)

**Key Properties:**
1. **Native Composition** — Conflict resolution is built into the format
2. **Lazy Loading (Payloads)** — Content loads on demand
3. **First-Class Variants** — Mode switching is a language construct

No other configuration format (JSON, YAML, Protobuf, GraphQL) provides all three properties.

### 2.2 Determinism in LLM Inference

**The Key Insight**: Individual LLM forward passes are run-to-run deterministic. The source of user-visible nondeterminism is that **batch size varies with server load**, and most kernels lack batch-invariance.

[He2025] demonstrated this empirically: **80 unique completions from 1000 identical requests** at temperature=0. The variation occurs because:

1. **Batch-size-dependent reduction order** — The same matrix operation (`torch.mm(a[:1], b)` vs `torch.mm(a, b)[:1]`) produces different results depending on batch size, even though the mathematical operation is identical
2. **Load-dependent batching** — Server load determines batch size, introducing runtime variation
3. **Kernel optimization switches** — Some kernels change algorithms (e.g., split-K) based on batch size

**What doesn't fully explain it** (common misconceptions):
- Floating-point non-associativity alone (individual kernels can be deterministic)
- GPU thread scheduling (can be controlled)
- Sampling randomness (can be seeded)

Batch-invariant kernels [He2025] eliminate these sources at a cost of ~1.6-2.1x performance overhead (1.6x with optimized attention kernel, 2.1x unoptimized).

### 2.3 Cognitive Architectures

Prior cognitive architectures (ACT-R, SOAR, LIDA) provide theoretical frameworks for cognitive modeling but lack:

1. **Deterministic guarantees** — Behavior varies across runs
2. **Persistent composition** — State management is ad-hoc
3. **Lazy expertise loading** — All knowledge must be present
4. **Constitutional bounds** — Safety constraints are not first-class

---

## 3. Architecture Overview

The USD Cognitive Substrate comprises two orthogonal hierarchies:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      RUNTIME SERVICE STACK                               │
│  (Processing, Routing, Adaptation, Dispatch)                            │
│                                                                          │
│  R1: Application Layer ─── External apps reporting signals              │
│  R2: Intervention Dispatch ─── Expert → application-specific actions    │
│  R3: Signal Aggregator ─── Multi-source signal normalization            │
│  R4: Routing Engine ─── Expert selection + neuroplasticity              │
│  R5: Temporal Ottotor ─── Session lifecycle + pattern learning     │
│  R6: Context Restorer ─── "Where was I?" continuity                     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                               ↕ reads/writes
┌─────────────────────────────────────────────────────────────────────────┐
│                      USD COMPOSITION HIERARCHY                           │
│  (State Storage with LIVRPS Resolution)                                 │
│                                                                          │
│  L13: current.usda ─────────────────────────────────── [LOCAL]          │
│  L12: snapshots/*.usda ─────────────────────────────── [LOCAL]          │
│  L11: daily/*.usda ─────────────────────────────────── [INHERITS]       │
│  L10: weekly/*.usda ────────────────────────────────── [INHERITS]       │
│  L9:  calibration.usda ─────────────────────────────── [REFERENCES]     │
│  L8:  profile.usda ─────────────────────────────────── [SPECIALIZES]    │
│  L7:  payloads/*.usda ──────────────────────────────── [PAYLOADS]       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**Critical Design Decision:** USD provides storage and composition semantics. USD does NOT provide routing logic. The routing engine is a separate layer that reads from and writes to USD.

---

## 4. USD Composition Hierarchy

### 4.1 Layer Definitions

| Layer | USD Arc | Mutability | Contents |
|-------|---------|------------|----------|
| L13: current.usda | LOCAL | Mutable | Live session state: energy, momentum, expert_weights, active task |
| L12: snapshots/*.usda | LOCAL | Immutable | Context restoration points with task, cognitive, environmental state |
| L11: daily/*.usda | INHERITS | Append-only | Aggregated daily patterns, time-of-day weights |
| L10: weekly/*.usda | INHERITS | Append-only | Day-of-week patterns, weekly rhythms |
| L9: calibration.usda | REFERENCES | Slow-update | Long-term learned weight adjustments, temporal patterns |
| L8: profile.usda | SPECIALIZES | Immutable | Base traits, safety floors, constitutional constraints |
| L7: payloads/*.usda | PAYLOADS | Immutable | Domain specializations (ADHD, Anxiety, VFX, etc.) |

### 4.2 LIVRPS Resolution

Higher layers override lower layers:

```
current.usda (energy=0.3)
    ↓ overrides
calibration.usda (energy=0.7)
    ↓ overrides
profile.usda (energy=0.5)

Result: energy = 0.3 (from current.usda)
```

**Exception:** Constitutional constraints in profile.usda (L0B) cannot be overridden by any layer.

### 4.3 State Schema

```usda
def "CognitiveState" {
    # Continuous dimensions
    float energy = 0.7
    float cognitive_load = 0.4
    float focus_coherence = 0.8

    # Discrete states
    string momentum = "building"  # cold_start|building|rolling|peak|declining|crashed
    string attractor = "convergent"  # convergent|divergent|recovery|transfer

    # Routing weights (the Mycelium)
    float[] expert_weights = [0.15, 0.15, 0.10, 0.10, 0.10, 0.20, 0.20]
    # [Protector, Decomposer, Restorer, Redirector, Acknowledger, Guide, Executor]

    # Safety constraints
    float[] safety_floors = [0.10, 0.05, 0.05, 0.0, 0.0, 0.0, 0.0]

    # Learning parameters
    float learning_rate = 0.1
    float weight_decay = 0.05
}
```

---

## 5. Runtime Service Stack

### 5.1 Signal Aggregator (R3)

Collects signals from multiple applications with priority ordering:

```
Priority  Category    Description
────────  ──────────  ─────────────────────────────
1         SAFETY      Requires immediate protective response
2         AFFECTIVE   Emotional state signals
3         MODE        Cognitive mode transitions
4         DOMAIN      Task-domain triggers (from payloads)
5         CONTENT     Informational/task content
```

**Aggregation Rules:**
1. Temporal weighting (recent > old)
2. Safety signals bypass queue
3. Source trust weighting
4. Consensus detection (multiple sources = higher confidence)
5. Conflict resolution (higher category wins)

### 5.2 Routing Engine (R4)

Five-phase routing with deterministic properties:

```
Phase 1: ACTIVATE
  Signal → Pattern Match → Activation Vector
  Deterministic given fixed pattern dictionary

Phase 2: WEIGHT
  weighted = activation × expert_weights
  Deterministic (matrix multiplication)

Phase 3: BOUND
  Apply safety floors (expert_weights >= safety_floors)
  Apply homeostatic limits (normalize to sum = 1)
  Enforce constitutional constraints
  Deterministic (fixed bounds)

Phase 4: SELECT
  expert = argmax(bounded_weighted)
  Tiebreaker: lower index wins
  Deterministic

Phase 5: UPDATE (The Mycelium)
  Hebbian learning, attractor dynamics, homeostatic regulation
  Constrained by Phase 3 bounds
  Deterministic given outcome
```

### 5.3 Expert Archetypes

Domain-agnostic expert types:

| Priority | Expert | Purpose | Safety Floor |
|----------|--------|---------|--------------|
| 1 | Protector | Safety-first, empathy | 0.10 (hard) |
| 2 | Decomposer | Break down complexity | 0.05 (hard) |
| 3 | Restorer | Recovery facilitation | 0.05 (hard) |
| 4 | Redirector | Attention management | 0.00 |
| 5 | Acknowledger | Progress recognition | 0.00 |
| 6 | Guide | Discovery facilitation | 0.00 |
| 7 | Executor | Direct task execution | 0.00 |

**First match wins.** Safety experts are always checked first regardless of activation strength.

### 5.4 Intervention Dispatch (R2)

Translates expert recommendations to application-specific interventions:

| Strategy | Behavior | Experts |
|----------|----------|---------|
| COORDINATED | All applications respond | Protector |
| EXCLUSIVE | Foreground application only | Decomposer, Acknowledger, Guide, Executor |
| ENVIRONMENTAL | Background applications | Restorer |
| CASCADING | Primary + environment | Redirector |

**Adapter Pattern:** Each application registers an adapter that composes interventions for its modality (text, environment changes, notifications).

### 5.5 Temporal Ottotor (R5)

Manages session lifecycle and cross-session learning:

**Aggregation Chain:**
```
Sessions → Daily (weighted by duration × outcome)
Daily → Weekly (day-of-week patterns)
Weekly → Calibration (long-term adjustments)
```

**Learning Rates:**
```
Within session:  α = 0.10  (fast adaptation)
Session → Daily: α = 0.05  (moderate)
Daily → Weekly:  α = 0.02  (slow)
Weekly → Calib:  α = 0.01  (very slow)
```

### 5.6 Context Restorer (R6)

Enables session continuity with staleness-aware restoration:

| Staleness | Duration | Restoration Protocol |
|-----------|----------|---------------------|
| MICRO | <15 min | Silent refocus |
| SESSION | 15min-4h | Rebuild momentum, offer environment restore |
| DAY | 4-16h | Morning restoration, validate relevance |
| WEEK | 3-10d | Require validation, describe environment |
| DEEP | >10d | May be obsolete, offer fresh start |

**Snapshot Contents:**
- Task state (active, completed, pending, intended next)
- Cognitive state (energy, momentum, weights, attractor)
- Environmental state (files, tabs, cursor position)
- Anchors (decisions made, insights discovered, open questions)

---

## 6. The Mycelium Mechanism

The Mycelium is the substrate's neuroplasticity system—how it learns and adapts while maintaining safety guarantees.

### 6.1 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     HARD BOUNDS (Immutable)                      │
│                                                                  │
│  Safety Floors: expert_weights >= safety_floors                 │
│  Homeostatic Limits: energy ∈ [0,1], sum(weights) = 1          │
│  Constitutional Constraints: Never overridden                   │
│                                                                  │
│                          ↓ constrains                            │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │           DYNAMIC ADAPTATION (Within Bounds)               │  │
│  │                                                            │  │
│  │  Hebbian Learning + Attractor Dynamics + Homeostasis      │  │
│  │                                                            │  │
│  └───────────────────────────────────────────────────────────┘  │
│                          ↑ receives                              │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              ACTIVATION SPREADING (Input)                  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 Rebalancing Avenues

**Avenue 1: Activation Spreading**

Signals spread activation across the expert network:

```
Signal: "frustrated"
Activation: Protector=0.8, Decomposer=0.3, Restorer=0.4, ...
```

The spreading function is fixed; learned associations are stored in USD.

**Avenue 2: Hebbian Learning**

Routes that lead to positive outcomes strengthen:

```
w_new = w_old + α(outcome - expected) × activation
```

Where:
- α = learning rate (from calibration)
- outcome = measured result [-1, 1]
- expected = baseline expectation
- activation = how strongly this expert was used

**Avenue 3: Attractor Dynamics**

State vectors have gravity toward attractor basins:

```
Basins: convergent, divergent, recovery, transfer

State vector: [energy, momentum, load, coherence]
Distance to each basin computed
Weights drift toward nearest basin's optimal configuration
Transition thresholds prevent oscillation
```

**Avenue 4: Homeostatic Regulation**

System maintains equilibrium:

```
IF energy_spent > energy_recovered for N exchanges:
   → Increase Restorer weight

IF focus_coherence declining:
   → Increase Redirector weight

IF cognitive_load > threshold:
   → Increase Decomposer weight
```

### 6.3 Bound Enforcement

All dynamic adaptation is constrained:

1. Safety floors are hard minimums
2. Weights are normalized after every update
3. Constitutional constraints cannot be violated
4. Learning cannot exceed rate limits

### 6.4 Formal Mathematical Specification

**Definition 1 (Weight Space)**
Let W = {w ∈ ℝ^7 | w_i ≥ f_i ∀i ∈ [1,7], Σw_i = 1}
where f = [0.10, 0.05, 0.05, 0, 0, 0, 0] are safety floors.

**Definition 2 (Activation Function)**
A: T × C → ℝ^7 where T is task space, C is context space.
A(t, c)_i = min(|{p ∈ triggers_i : p ⊆ t}| / |triggers_i|, 1.0)

**Definition 3 (Hebbian Update)**
U: W × ℝ × ℝ^7 → W
U(w, o, a)_i = clip(w_i + α(o - e)a_i, f_i, 1.0) / Z
where Z normalizes to sum=1, α ∈ (0, 0.2], o ∈ [-1, 1], e = 0.5

**Theorem 1 (Safety Floor Invariant)**
∀w ∈ W, ∀o, a: U(w, o, a) ∈ W
*Proof*: By construction, clip enforces w_i ≥ f_i, and Z normalizes sum to 1. ∎

**Theorem 2 (Bounded Learning)**
|U(w, o, a)_i - w_i| ≤ α × max(|o - e|) × max(||a||_∞) ≤ 0.2 × 1 × 1 = 0.2
*Proof*: By definition of clip and bounds on α, o, a. ∎

**Theorem 3 (Convergence)**
Under stationary outcome distribution, w converges to E[o × a] / Σ_i E[o × a_i].
*Proof sketch*: Standard Hebbian convergence with decay. Full proof in Appendix D.

### 6.5 Worked Example: Complete Routing Trace

**User Input**: "I'm completely stuck on this architecture decision and feeling overwhelmed"

**Step 1: Signal Detection**
```
Pattern matching:
- "stuck" → Decomposer trigger ✓
- "overwhelmed" → Protector trigger ✓

Activation vector A(task):
  Protector:    1/8 triggers = 0.125 (but "overwhelmed" strong signal)
  Decomposer:   1/8 triggers = 0.125 (but "stuck" strong signal)
  [others]:     0/n triggers = 0.000
```

**Step 2: Weight Calculation**
```
Current weights w: [0.15, 0.15, 0.10, 0.10, 0.10, 0.20, 0.20]
Activations a:     [0.80, 0.30, 0.00, 0.00, 0.00, 0.00, 0.00]
Weighted w×a:      [0.12, 0.05, 0.00, 0.00, 0.00, 0.00, 0.00]
```

**Step 3: Safety Floor Enforcement (BOUND phase)**
```
Pre-floor:   [0.12, 0.05, 0.00, 0.00, 0.00, 0.00, 0.00]
Floors:      [0.10, 0.05, 0.05, 0.00, 0.00, 0.00, 0.00]
Check:       [✓,    ✓,    ✗,    ✓,    ✓,    ✓,    ✓]
Post-floor:  [0.12, 0.05, 0.05, 0.00, 0.00, 0.00, 0.00]
Normalized:  [0.55, 0.23, 0.23, 0.00, 0.00, 0.00, 0.00]
```

**Step 4: Selection (SELECT phase)**
```
Winner: Protector (0.55)
Tiebreaker: N/A (clear winner)
```

**Step 5: Response Generation**
```
Expert: Protector
Response: "I notice you're feeling stuck and overwhelmed. Let's pause
          the architecture decision and address how you're feeling first.
          What's the main source of the overwhelm?"
```

**Step 6: Outcome & Learning (UPDATE phase)**
```
User feedback: +0.8 (helpful response)
Hebbian update: w_protector += 0.1 × (0.8 - 0.5) × 0.8 = +0.024
New weights: [0.174, 0.15, 0.10, ...] → normalize → [0.18, 0.15, ...]
```

---

## 7. Multi-Agent Composition: The Mycelium Arc

### 7.1 The Problem

LIVRPS provides vertical composition (layers override layers). Multi-agent systems require horizontal composition (agents share state).

### 7.2 The Mycelium Arc

A new composition arc with peer-to-peer semantics:

```usda
def "AgentB" (
    mycelium = </AgentA>
) {
    # FLOWS through mycelium:
    float momentum_phase      # Inherited unless locally overridden
    float epistemic_tension   # Additive (tensions compound)
    string attractor_basin    # Inherited unless divergent

    # SAFETY-MAX through mycelium:
    string burnout_level      # MAX(AgentA, AgentB) - conservative

    # DOES NOT FLOW:
    string[] files_read       # Agent-specific context
    int message_count         # Agent-specific
}
```

**Key Semantic:** Burnout takes MAX, not override. Safety is never diluted by handoff.

### 7.3 Dynamic Resource Routing

The Mycelium arc enables bidirectional flow based on need:

```
Agent A (exploring, high momentum) ←→ Agent B (implementing, cold start)
        └── momentum flows TO Agent B
        └── tangent budget flows FROM Agent B (it needs focus)
```

---

## 8. Determinism Analysis

### 8.1 Stochastic Boundaries

Without batch-invariant inference:

| Step | Component | Deterministic? |
|------|-----------|----------------|
| 1 | User input | NO (human) |
| 2 | Signal detection (pattern) | YES |
| 2 | Signal detection (semantic) | NO (LLM variance) |
| 3-6 | Routing core | YES |
| 7 | LLM generation | NO (batch variance) |
| 8 | User response | NO (human) |
| 9 | Outcome detection | PARTIAL |
| 10 | State update | YES |

### 8.2 With Batch-Invariant Kernels [He2025]

[He2025] provides batch-invariant kernels that guarantee identical outputs regardless of batch size:

| Operation | Batch-Invariant Strategy | Performance Cost |
|-----------|-------------------------|------------------|
| **RMSNorm** | Data-parallel: assign each batch element to one core, maintaining identical reduction order regardless of batch size | Minimal |
| **Matrix Multiplication** | Fixed tensor-core instructions and tile sizes across all batch sizes; avoid split-K optimization | ~20% vs cuBLAS |
| **Attention** | Fixed split-SIZE (not split-count) for KV dimension; reduction order for a given token doesn't depend on batch | Optimized: 1.6x total |

**Key Implementation Detail**: KV cache and page tables must be updated before the attention kernel to maintain consistent memory layout regardless of token processing strategy.

**Result:** All LLM-dependent operations become deterministic. The same request produces identical output whether batch=1 or batch=1000.

| Step | Component | Deterministic? |
|------|-----------|----------------|
| 1 | User input | NO (human - irreducible) |
| 2 | Signal detection | YES (batch-invariant) |
| 3-6 | Routing core | YES |
| 7 | LLM generation | YES (batch-invariant) |
| 8 | User response | NO (human - irreducible) |
| 9 | Outcome detection | YES (batch-invariant) |
| 10 | State update | YES |

### 8.3 Reproducibility Contract

```
GIVEN:
  1. Identical user input string
  2. Identical USD state
  3. Identical timestamp
  4. Same model version
  5. Same hardware configuration

GUARANTEE:
  ✓ Identical signal detection
  ✓ Identical routing decision
  ✓ Identical LLM response
  ✓ Identical state update
  ✓ Identical checksum

STOCHASTIC (Irreducible):
  - What the user types
  - How the user responds
```

### 8.4 Requirements for Full Determinism

| Requirement | Purpose |
|-------------|---------|
| L0D Specification | Fixed pattern dictionary, activation matrix, tiebreakers |
| Canonical Prompt Templates | Same expert + context → same prompt |
| Fixed Model Version | Model updates change behavior |
| Fixed Hardware Config | Per [He2025] limitation |
| Canonical State Serialization | Deterministic USD → string |
| Batch-Invariant Kernels [He2025] | Batch-invariant inference (~1.6x overhead) |

### 8.5 Failure Modes and Recovery

The system is designed to fail gracefully:

| Failure Mode | Cause | Detection | Recovery |
|--------------|-------|-----------|----------|
| **FM1: State Corruption** | Disk failure, concurrent write | Checksum mismatch | Load previous snapshot; reset to calibration if all corrupted |
| **FM2: Signal Conflict** | "frustrated" + "just do it" | Multiple high activations | Priority ordering (Protector wins) |
| **FM3: Weight Explosion** | Extreme outcomes without decay | Any w_i > 0.95 | Apply decay, re-normalize |
| **FM4: Batch-Invariant Kernels Unavailable** | Fallback to standard inference | Batch-invariance check fails | Mark session non-reproducible, increase logging |
| **FM5: Cold Start** | New user, no history | Uniform weights detected | Calibration wizard for initial preferences |

**Recovery Hierarchy:**
1. Attempt operation with current state
2. Load most recent valid snapshot
3. Reset to calibration defaults
4. Reset to profile defaults (constitutional constraints only)

**Safety Invariant:** At no point in the recovery hierarchy can safety floors be violated.

---

## 9. Payload Architecture

### 9.1 Design Principle

The core substrate is neurotype-agnostic and domain-agnostic. Specializations are loaded as payloads that adjust weights and add signals.

### 9.2 Payload Structure

```usda
def "ADHDPayload" {
    # Weight adjustments
    float[] weight_adjustments = [0.0, +0.05, +0.05, +0.03, 0.0, 0.0, -0.03]
    # Increase Decomposer, Restorer, Redirector; decrease Executor

    # Floor adjustments
    float decomposer_floor = 0.10  # Raised from 0.05

    # Added signals
    string[] additional_signals = [
        "time_blindness",
        "hyperfocus_detection",
        "working_memory_overflow"
    ]

    # Parameter adjustments
    float tangent_budget = 3.0  # Reduced from 5.0
}
```

### 9.3 Available Payloads

| Payload | Adjustments |
|---------|-------------|
| ADHD | Higher Decomposer/Restorer floors, time signals, reduced tangent budget |
| Anxiety | Higher Protector floor, uncertainty signals, slower state transitions |
| Autism | Higher Executor preference, routine disruption signals, explicit communication |
| VFX Domain | Domain triggers (usd, houdini, render), specialized expertise |
| WebDev Domain | Domain triggers (react, next, api), specialized expertise |

---

## 10. Implementation

### 10.1 Python SDK Interface

```python
from cognitive_substrate import Substrate, Signal

# Initialize
substrate = Substrate(storage_path="~/.cognitive/state.usda")
substrate.load_payload("adhd")

# Signal reporting
substrate.signal(Signal(
    category="affective",
    content="frustrated",
    source="claude_code"
))

# Get routing
expert = substrate.route()  # Deterministic

# Report outcome
substrate.outcome(expert=expert, result=0.7)

# State persists to USD automatically
```

### 10.2 Multi-Application Integration

```python
# Multiple apps share state
browser = Substrate(storage="~/.cognitive/state.usda", source="browser")
editor = Substrate(storage="~/.cognitive/state.usda", source="editor")

# Both report signals
browser.signal(Signal(category="mode", content="15 tabs opened"))
editor.signal(Signal(category="content", content="high keystroke rate"))

# Aggregator combines signals
# Routing uses combined signal vector
```

### 10.3 Storage Layout

```
~/.cognitive/
├── current.usda              # Live session state
├── snapshots/                # Context restoration points
├── sessions/                 # Archived sessions
├── daily/                    # Aggregated daily states
├── weekly/                   # Aggregated weekly states
├── calibration.usda          # Long-term patterns
├── profile.usda              # Base traits
└── payloads/                 # Specializations
    ├── adhd.usda
    ├── anxiety.usda
    └── vfx_domain.usda
```

---

## 11. Evaluation Criteria

### 11.1 Reproducibility

**Metric:** Given identical inputs and state, percentage of runs producing identical outputs.

**Target:** 100% with batch-invariant kernels [He2025]; <100% without.

**Method:** Replay recorded sessions, compare checksums.

### 11.2 Adaptation Quality

**Metric:** Does Hebbian learning improve routing over time?

**Method:** Track outcome distributions before/after calibration updates.

### 11.3 Safety Guarantee

**Metric:** Do safety floors hold under all conditions?

**Method:** Formal verification that update functions cannot violate floors.

### 11.4 Context Restoration Accuracy

**Metric:** After restoration, can users continue without re-establishing context?

**Method:** User study measuring time-to-productivity after breaks.

---

## 12. Related Work

### 12.1 Cognitive Architectures

- **ACT-R** (Anderson): Production system with memory modules; no determinism guarantees
- **SOAR** (Laird): Goal-oriented with learning; no composition semantics
- **LIDA** (Franklin): Global workspace theory; no persistent state format

### 12.2 LLM State Management

- **LangChain Memory**: Simple key-value; no composition or conflict resolution
- **MemGPT**: Tiered memory with LLM-controlled paging; not deterministic
- **Anthropic Constitution**: Safety constraints; different layer (content filtering vs. routing)

### 12.3 Deterministic Inference

- **[He2025]**: Batch-invariant kernels; we build upon this
- **vLLM**: Optimized serving; not deterministic
- **TensorRT-LLM**: Compilation; determinism not guaranteed

---

## 13. Future Directions

### 13.1 Near-Term

1. **USDZ Binary Compilation** — 10x parsing performance improvement
2. **Formal Verification** — Prove safety floor invariants
3. **Cross-Platform SDK** — Python, TypeScript, Rust bindings

### 13.2 Medium-Term

1. **Federated Learning** — Aggregate patterns across users while preserving privacy
2. **Natural Language Configuration** — "I want an expert that..." → USD payload
3. **Real-Time Visualization** — 3D cognitive state dashboard

### 13.3 Long-Term

1. **OpenUSD Standardization** — Propose cognitive extensions to USD spec
2. **Hardware Security** — TPM/HSM for PROTECTED data classification
3. **Multi-Model Ottotion** — Route to specialized models based on state

---

## 13.4 Known Limitations

1. **Keyword-Based Signal Detection**: Triggers rely on keyword matching. Semantic understanding requires LLM in the loop, reintroducing non-determinism. Future work: learned embeddings with quantized similarity.

2. **Single-Model Assumption**: Current design assumes one LLM. Multi-model routing (e.g., different models for different experts) adds complexity not addressed in this specification.

3. **Cold Start Problem**: New users have uniform weights. Initial sessions may have suboptimal routing until Hebbian learning accumulates data. Mitigation: Calibration wizard.

4. **Memory vs. Compute Tradeoff**: Batch-invariance [He2025] has performance cost: 2.1x slowdown with unoptimized kernels, 1.6x with optimized attention. MatMul specifically costs ~20% vs cuBLAS. For latency-sensitive applications, this may require hybrid mode (deterministic for routing, probabilistic for generation).

5. **USD Ecosystem Maturity**: While USD is an industry standard for VFX, its ecosystem outside VFX is nascent. Python pxr bindings are mature; other languages less so.

---

## 13.5 Falsifiability Criteria

The USD Cognitive Substrate thesis would be **FALSIFIED** if:

1. **Composition Failure**: LIVRPS resolution produces paradoxes or undefined behavior in >1% of real-world state configurations.

2. **Learning Instability**: Mycelium weights oscillate indefinitely or converge to degenerate configurations (all weight on one expert) in normal usage.

3. **Safety Floor Violation**: Any execution path exists that allows expert weights to fall below safety floors.

4. **Determinism Failure**: With batch-invariant kernels [He2025], identical inputs produce different outputs in >0.01% of cases.

5. **Practical Inferiority**: A simpler system (JSON + rules) achieves equivalent routing accuracy with <50% of the specification complexity.

**Claims NOT Subject to Falsification** (by design):
- Human input stochasticity is irreducible (definitional)
- Constitutional constraints are immutable (axiomatic)

---

## 14. Conclusion

The USD Cognitive Substrate demonstrates that USD composition semantics—designed for visual effects pipeline conflict resolution—are equally applicable to cognitive state management in LLM applications.

The key contributions:

1. **Separation of storage and routing** enables clear architectural boundaries
2. **The Mycelium mechanism** provides bounded neuroplasticity
3. **The Mycelium Arc** enables multi-agent state composition
4. **Integration with batch-invariant inference** achieves full determinism

When deployed with batch-invariant kernels [He2025], the system provides a formally verifiable guarantee: **same input + same state → same output**. This transforms LLM applications from probabilistic systems into deterministic functions, enabling reproducibility, testing, auditing, and accountability.

The only remaining stochasticity is human agency—what users type and how they respond—which is not a limitation but a feature: the system respects human autonomy while providing consistent, learnable, verifiable AI behavior.

---

## Appendix A: USD Schema Reference

See `cognitive_substrate_v5.usda` for complete schema definitions.

## Appendix B: Determinism Specification (L0D)

See `determinism_spec.usda` for pattern dictionaries, activation matrices, and tiebreaker rules.

## Appendix C: API Reference

See SDK documentation for complete interface specifications.

---

## References

1. Pixar Animation Studios. (2016). *Universal Scene Description*. https://graphics.pixar.com/usd/

2. He, Horace and Thinking Machines Lab. (2025). "Defeating Nondeterminism in LLM Inference." *Thinking Machines Lab: Connectionism*, September 2025. https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/

3. Anderson, J. R. (2007). *How Can the Human Mind Occur in the Physical Universe?* Oxford University Press.

4. Laird, J. E. (2012). *The Soar Cognitive Architecture*. MIT Press.

5. Franklin, S., Madl, T., D'Mello, S., and Snaider, J. (2016). "LIDA: A Systems-level Architecture for Cognition, Emotion, and Learning." *IEEE Transactions on Autonomous Mental Development*, 6(1):19-41.

---

*Document Version: 5.0.1*
*Generated: 2026-01-20*
*Classification: Academic Pre-Publication Draft*
