# Unified Handoff: Graphics for USD Cognitive Substrate + Framework Ottotor

**Project:** USD Cognitive Substrate Arxiv Publication + Framework Ottotor Documentation
**Author:** Joseph O. Ibrahim
**Created:** 2026-01-21
**Purpose:** Add publication-quality figures to BOTH repositories

---

## Executive Summary

Two related repositories need graphics:

1. **usd-cognitive-substrate** - Academic specification (Arxiv papers)
2. **framework-ottotor** - Reference implementation (documentation + README)

This handoff covers ALL graphics needs across both repositories.

---

## Repository Locations

```
C:\Users\User\usd-cognitive-substrate\           # SPECIFICATION REPO
├── arxiv/                                       # Arxiv LaTeX package
│   ├── usd-cognitive-substrate/main.tex         # Main paper
│   ├── persistent-state-hypothesis/main.tex     # Hypothesis paper
│   └── determinism/main.tex                     # Determinism paper
├── USD_COGNITIVE_SUBSTRATE.md                   # Source markdown
├── PERSISTENT_STATE_HYPOTHESIS.md
└── DETERMINISM.md

C:\Users\User\framework-ottotor-update\     # IMPLEMENTATION REPO
├── README.md                                    # Main documentation
├── docs/
│   ├── ARCHITECTURE.md                          # System design
│   ├── AGENTS.md                                # Agent documentation
│   └── CONFIGURATION.md                         # Config reference
└── spec/                                        # Mirrors of Arxiv papers
    ├── USD_COGNITIVE_SUBSTRATE.md
    ├── PERSISTENT_STATE_HYPOTHESIS.md
    └── DETERMINISM.md
```

**GitHub URLs:**
- https://github.com/JosephOIbrahim/usd-cognitive-substrate
- https://github.com/JosephOIbrahim/framework-ottotor

---

## PART 1: USD-COGNITIVE-SUBSTRATE (Arxiv Papers)

### Figures for LaTeX Papers

| # | Figure | Paper | Type | Priority |
|---|--------|-------|------|----------|
| 1 | 5-Phase Routing Flow | USD Cognitive Substrate | Flowchart | HIGH |
| 2 | LIVRPS Composition Resolution | USD Cognitive Substrate | Cascade | HIGH |
| 3 | Determinism Boundary | USD Cognitive Substrate | Architecture | HIGH |
| 4 | CogRoute-Bench Results | USD Cognitive Substrate | Bar chart | HIGH |
| 5 | Energy Comparison | Persistent State Hypothesis | Comparison | HIGH |
| 6 | Batch vs Determinism | Determinism | Diagram | MEDIUM |

### Figure 1: 5-Phase Routing Flow

**Location:** `arxiv/usd-cognitive-substrate/figures/figure1-routing-flow.pdf`

```
                            USER INPUT
                                │
                                ▼
┌───────────────────────────────────────────────────────────────────────┐
│  PHASE 1: ACTIVATE                                                    │
│  Signal → Pattern Match → Activation Vector                           │
│  "stuck" → L0D Dictionary → [0, 0.8, 0, 0, 0, 0.2, 0]                │
└───────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────────────┐
│  PHASE 2: WEIGHT                                                      │
│  activation × expert_weights = weighted_scores                        │
└───────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────────────┐
│  PHASE 3: BOUND                                                       │
│  Safety Floors → Homeostatic Norm → Constitutional Constraints        │
│  Protector ≥ 0.10 (HARD)                                             │
└───────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────────────┐
│  PHASE 4: SELECT                                                      │
│  expert = argmax(bounded_scores)                                      │
│  Tiebreaker: lower priority index wins                                │
└───────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────────────┐
│  PHASE 5: UPDATE (Mycelium)                                           │
│  Outcome → Hebbian Learning → Updated Weights                         │
└───────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                          EXPERT RESPONSE
```

**Style:** Vertical flowchart, 5 color-coded phases, arrows showing data flow.
**Colors:** Phase 1 (Blue), Phase 2 (Teal), Phase 3 (Orange), Phase 4 (Purple), Phase 5 (Green)

---

### Figure 2: LIVRPS Composition Resolution

**Location:** `arxiv/usd-cognitive-substrate/figures/figure2-livrps.pdf`

```
                    QUERY: "What is energy?"
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LIVRPS RESOLUTION ORDER (Strongest → Weakest)                      │
├─────────────────────────────────────────────────────────────────────┤
│  L: LOCAL ────────────► current.usda ──────► energy = 0.3 ✓ WINS   │
│            │                                                        │
│            ▼ if not found                                           │
│  I: INHERITS ─────────► daily/*.usda ──────► (not set)             │
│            │                                                        │
│            ▼ if not found                                           │
│  V: VARIANTSETS ──────► mode_variants ─────► (not set)             │
│            │                                                        │
│            ▼ if not found                                           │
│  R: REFERENCES ───────► calibration.usda ──► energy = 0.7          │
│            │                                                        │
│            ▼ if not found                                           │
│  P: PAYLOADS ─────────► adhd.usda ─────────► (not set)             │
│            │                                                        │
│            ▼ if not found                                           │
│  S: SPECIALIZES ──────► profile.usda ──────► energy = 0.5          │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    RESULT: energy = 0.3
```

**Style:** Waterfall diagram, winning layer highlighted green, shadowed values gray.

---

### Figure 3: Determinism Boundary

**Location:** `arxiv/usd-cognitive-substrate/figures/figure3-determinism.pdf`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         STOCHASTIC (Irreducible)                            │
│                              Human Agency                                   │
│  ┌─────────────────┐                              ┌─────────────────┐      │
│  │   USER INPUT    │                              │  USER RESPONSE  │      │
│  └────────┬────────┘                              └────────▲────────┘      │
└───────────┼────────────────────────────────────────────────┼───────────────┘
            │                                                │
            ▼                                                │
┌───────────────────────────────────────────────────────────────────────────┐
│                    DETERMINISTIC (With Batch-Invariant Kernels [He2025])   │
│                                                                           │
│   Signal Detection → 5-Phase Routing → Expert Selection → LLM → Update   │
│                                                                           │
│  GUARANTEE: Same input + Same state → Same output + Same state update     │
└───────────────────────────────────────────────────────────────────────────┘
```

**Style:** Two-zone diagram - stochastic (red/orange outer), deterministic (green/blue inner).

---

### Figure 4: CogRoute-Bench Results

**Location:** `arxiv/usd-cognitive-substrate/figures/figure4-benchmark.pdf`

```
OVERALL METRICS
────────────────────────────────────────────────────────────────
Accuracy        ████████████████████████████████████████░░  94.6%
Determinism     ████████████████████████████████████████████ 100.0%
Explainability  ████████████████████████████████████████░░░  95.1%

BY CATEGORY
────────────────────────────────────────────────────────────────
safety_critical  ████████████████████████████████████████████ 100%
recovery         ████████████████████████████████████████████ 100%
redirection      ████████████████████████████████████████████ 100%
acknowledgment   ████████████████████████████████████████████ 100%
exploration      ████████████████████████████████████████████ 100%
ambiguous        ████████████████████████████████████████████ 100%
complexity       ████████████████████████████████░░░░░░░░░░░░  80%
execution        ████████████████████████████████████░░░░░░░░  83%
```

**Style:** Horizontal bar chart, 100% green, <100% yellow/orange. Clear labels.

---

### Figure 5: Energy Comparison (Persistent State Hypothesis)

**Location:** `arxiv/persistent-state-hypothesis/figures/figure1-energy.pdf`

```
DIRECT FACT LOOKUP
────────────────────────────────────────────────────────────────
Transformer │████████████████████████████████████████│ O(L·n²d) ~10¹³ ops
USD Substrate │█                                     │ O(1) path traversal

RELATIONSHIP QUERY
────────────────────────────────────────────────────────────────
Transformer │████████████████████████████████████████│ O(L·n²d)
USD Substrate │████                                  │ O(e) edge count

KNOWLEDGE UPDATE
────────────────────────────────────────────────────────────────
Transformer │████████████████████████████████████████│ Retraining (hours-days)
USD Substrate │█                                     │ O(1) opinion insertion
```

**Style:** Side-by-side comparison, Transformer (red), USD (green), log scale.

---

## PART 2: FRAMEWORK-ORCHESTRATOR (Implementation Docs)

### Figures for Documentation

| # | Figure | File | Type | Priority |
|---|--------|------|------|----------|
| A | 7-Agent Architecture | README.md + ARCHITECTURE.md | Architecture | HIGH |
| B | Task Processing Pipeline | ARCHITECTURE.md | Flowchart | MEDIUM |
| C | V5 Expert Routing | AGENTS.md | Diagram | HIGH |
| D | LIVRPS Memory Layers | ARCHITECTURE.md | Layer diagram | MEDIUM |
| E | Agent Interaction | AGENTS.md | Sequence diagram | MEDIUM |

### Figure A: 7-Agent Architecture (Main)

**Location:** `docs/images/architecture.png` (or SVG)
**Used in:** README.md, docs/ARCHITECTURE.md

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Otto                                   │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                        Task Router                               │   │
│  │  Analyzes task → Activates relevant agents → Manages execution  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                    │                                     │
│            ┌───────────────────────┼───────────────────────┐            │
│            ▼                       ▼                       ▼            │
│  ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐   │
│  │   ECHO Curator   │   │     Domain       │   │    MoE Router    │   │
│  │                  │   │   Intelligence   │   │                  │   │
│  │  Memory (LIVRPS) │   │  (Phoenix+PRISM) │   │  Expert Select   │   │
│  └──────────────────┘   └──────────────────┘   └──────────────────┘   │
│            │                       │                       │            │
│            └───────────────────────┼───────────────────────┘            │
│                                    ▼                                     │
│  ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐   │
│  │  World Modeler   │   │  Code Generator  │   │   Determinism    │   │
│  │                  │   │                  │   │     Guard        │   │
│  │  Context Graph   │   │   NEXUS Output   │   │  Batch=1 Check   │   │
│  └──────────────────┘   └──────────────────┘   └──────────────────┘   │
│                                    │                                     │
│                                    ▼                                     │
│                       ┌──────────────────┐                              │
│                       │  Self Reflector  │                              │
│                       │    (RC^+xi)      │                              │
│                       │  Convergence     │                              │
│                       └──────────────────┘                              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**Style:** Clean box diagram with 7 agents, show connections and data flow.
**Colors:** Each agent a different color, grouped by tier.

---

### Figure B: Task Processing Pipeline

**Location:** `docs/images/task-pipeline.png`
**Used in:** docs/ARCHITECTURE.md

```
Input Task
    │
    ▼
┌─────────────────────┐
│   Task Analysis     │
│  (keyword matching) │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│   Agent Selection   │
│  (always: echo,     │
│   determinism)      │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  Parallel Execution │
│  (max 3 concurrent) │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  Result Aggregation │
│  (with checksums)   │
└─────────────────────┘
    │
    ▼
Output (JSON with master_checksum)
```

**Style:** Vertical flowchart, simple and clean.

---

### Figure C: V5 Expert Routing

**Location:** `docs/images/v5-routing.png`
**Used in:** docs/AGENTS.md

```
┌────────────────────────────────────────────────────────────────────┐
│                    V5 INTERVENTION EXPERTS                          │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Pri  Expert        Floor   Triggers                               │
│  ───  ────────────  ──────  ─────────────────────────────────     │
│  1    Protector     10%     frustrated, overwhelmed, safety        │
│  2    Decomposer    5%      stuck, complex, break_down             │
│  3    Restorer      5%      depleted, burnout, tired               │
│  4    Redirector    0%      tangent, distracted, off_topic         │
│  5    Acknowledger  0%      done, complete, milestone              │
│  6    Guide         0%      exploring, what_if, curious            │
│  7    Executor      0%      implement, code, execute               │
│                                                                    │
│  SAFETY FLOORS ARE HARD MINIMUMS - NEVER VIOLATED                 │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

**Style:** Table-style diagram with color-coding for safety-critical experts (1-3 in orange).

---

### Figure D: LIVRPS Memory Layers

**Location:** `docs/images/livrps-layers.png`
**Used in:** docs/ARCHITECTURE.md

```
                    LIVRPS Memory Priority
                    (Strongest → Weakest)
    ┌─────────────────────────────────────────────────┐
    │  L: LOCAL        │ Session state    │ Compress │ ← Highest
    ├──────────────────┼──────────────────┼──────────┤
    │  I: INHERITS     │ Parent context   │ Compress │
    ├──────────────────┼──────────────────┼──────────┤
    │  V: VARIANTSETS  │ Memory modes     │ Protected│
    ├──────────────────┼──────────────────┼──────────┤
    │  R: REFERENCES   │ Calibration      │ Protected│
    ├──────────────────┼──────────────────┼──────────┤
    │  P: PAYLOADS     │ Domain knowledge │ Unload   │
    ├──────────────────┼──────────────────┼──────────┤
    │  S: SPECIALIZES  │ Principles       │ NEVER    │ ← Lowest (immutable)
    └─────────────────────────────────────────────────┘
```

**Style:** Stacked layer diagram, protected layers highlighted, compression arrows.

---

## PART 3: FORMAT RECOMMENDATIONS

### For Arxiv (LaTeX Papers)

| Format | Pros | Cons |
|--------|------|------|
| **TikZ/PGF** | Vector, native LaTeX, no external files | Learning curve |
| **PDF (from Inkscape)** | Vector, easy editing | External file |
| **PNG (from matplotlib)** | Easy to generate programmatically | Raster |

**Recommendation:** TikZ for diagrams, matplotlib for charts.

### For GitHub (Markdown Docs)

| Format | Pros | Cons |
|--------|------|------|
| **SVG** | Vector, scales perfectly | Limited browser support |
| **PNG** | Universal support | Raster, large files |
| **Mermaid** | Native GitHub rendering | Limited styling |

**Recommendation:** PNG at 2x resolution (for Retina), with SVG alternative.

---

## PART 4: COLOR PALETTE

Use consistent colors across ALL figures:

```
Primary Blue:    #2563EB (main elements)
Success Green:   #10B981 (positive/deterministic)
Warning Orange:  #F59E0B (safety/caution)
Error Red:       #EF4444 (stochastic/critical)
Purple:          #8B5CF6 (special/selection)
Gray:            #6B7280 (disabled/shadow)
Light Gray:      #F3F4F6 (backgrounds)
```

---

## PART 5: DIRECTORY STRUCTURE AFTER COMPLETION

```
usd-cognitive-substrate/
├── arxiv/
│   ├── usd-cognitive-substrate/
│   │   ├── main.tex
│   │   └── figures/
│   │       ├── figure1-routing-flow.pdf
│   │       ├── figure2-livrps.pdf
│   │       ├── figure3-determinism.pdf
│   │       └── figure4-benchmark.pdf
│   ├── persistent-state-hypothesis/
│   │   ├── main.tex
│   │   └── figures/
│   │       └── figure1-energy.pdf
│   └── determinism/
│       ├── main.tex
│       └── figures/
│           └── figure1-batch.pdf

framework-ottotor/
├── README.md
├── docs/
│   ├── ARCHITECTURE.md
│   ├── AGENTS.md
│   └── images/
│       ├── architecture.png
│       ├── architecture.svg
│       ├── task-pipeline.png
│       ├── v5-routing.png
│       └── livrps-layers.png
```

---

## PART 6: [He2025] VERIFICATION

When creating figures that reference [He2025], use EXACT values:

| Claim | Value | Use In |
|-------|-------|--------|
| Unique completions at temp=0 | 80 from 1000 | Figure 3 |
| Unoptimized overhead | 2.1× | Figure 5 |
| Optimized overhead | 1.6× | Figure 5 |
| MatMul loss vs cuBLAS | ~20% | Figure 5 |
| RMSNorm strategy | Data-parallel | Text |
| Attention strategy | Fixed split-SIZE | Text |

**Source:** https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/
**DOI:** 10.64434/tml.20250910

---

## PART 7: IMPLEMENTATION CHECKLIST

### For usd-cognitive-substrate (Arxiv)

- [ ] Create Figure 1: 5-Phase Routing Flow
- [ ] Create Figure 2: LIVRPS Composition Resolution
- [ ] Create Figure 3: Determinism Boundary
- [ ] Create Figure 4: CogRoute-Bench Results
- [ ] Create Figure 5: Energy Comparison
- [ ] Insert figures into LaTeX files
- [ ] Test compilation with `compile_all.bat`
- [ ] Verify figure references work
- [ ] Commit and push

### For framework-ottotor (Docs)

- [ ] Create Figure A: 7-Agent Architecture
- [ ] Create Figure B: Task Processing Pipeline
- [ ] Create Figure C: V5 Expert Routing
- [ ] Create Figure D: LIVRPS Memory Layers
- [ ] Update README.md with image references
- [ ] Update docs/ARCHITECTURE.md with images
- [ ] Update docs/AGENTS.md with images
- [ ] Commit and push

---

## PART 8: QUICK START FOR NEXT SESSION

1. **Read this document** for full context
2. **Choose graphics approach:**
   - Option A: TikZ for LaTeX, PNG for markdown
   - Option B: External tool (Figma/draw.io) for all
   - Option C: Python matplotlib for charts, manual for diagrams
3. **Create figures** following ASCII sources and style guides
4. **Insert into documents**
5. **Test and verify**
6. **Commit to both repos**
7. **Notify user** papers are ready

---

*Unified Handoff created: 2026-01-21*
*Covers: usd-cognitive-substrate + framework-ottotor*
*Total figures needed: 10-11*
