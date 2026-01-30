# V5 Framework Ottotor - Framework Synthesis Document

## Source Frameworks → V5 Component Mapping

This document maps the underlying research frameworks to V5 implementation components,
providing theoretical grounding and implementation references.

---

## Component 1: MoE Router with 7 Intervention Experts

### V5 Implementation
```python
EXPERTS = {
    "protector":    {"priority": 1, "triggers": ["frustrated", "overwhelmed", "safety"]},
    "decomposer":   {"priority": 2, "triggers": ["stuck", "complex", "too_many"]},
    "restorer":     {"priority": 3, "triggers": ["depleted", "burnout", "tired"]},
    "redirector":   {"priority": 4, "triggers": ["tangent", "distracted", "off_topic"]},
    "acknowledger": {"priority": 5, "triggers": ["done", "complete", "milestone"]},
    "guide":        {"priority": 6, "triggers": ["exploring", "what_if", "curious"]},
    "executor":     {"priority": 7, "triggers": ["implement", "code", "do", "execute"]}
}
```

### Framework Sources

| V5 Expert | Source Framework | Original Name | Key Behavior |
|-----------|-----------------|---------------|--------------|
| **Protector** | ADHD Support Framework | Validator/Calmer | Empathy first, de-escalation, normalization |
| **Decomposer** | ADHD Support Framework | Scaffolder | Task breakdown, working memory reduction |
| **Restorer** | ADHD Support Framework | Restorer | Easy wins, recovery mode, rest validation |
| **Redirector** | ADHD Support Framework | Refocuser | Gentle nudges, context summarization |
| **Acknowledger** | ADHD Support Framework | Celebrator | Dopamine hits, milestone recognition |
| **Guide** | ADHD Support Framework | Socratic Inquisitor | Discovery questions, hypothesis exploration |
| **Executor** | ADHD Support Framework | Direct Executor | Minimal friction, flow protection |

### Reference Files
- `ADHD Support Framework.txt` (Lines 62-95: Expert definitions)
- `MAX 3 Framework.txt` (Thought Leader Integration Pattern)

---

## Component 2: Safety Floors (Hard Minimums)

### V5 Implementation
```python
SAFETY_FLOORS = {
    "protector":  0.10,  # 10% minimum - NEVER violated
    "decomposer": 0.05,  # 5% minimum
    "restorer":   0.05,  # 5% minimum
    "redirector": 0.00,
    "acknowledger": 0.00,
    "guide":      0.00,
    "executor":   0.00
}
```

### Framework Sources

**ADHD Support Framework** - Emotional Self-Regulation (DESR):
- RED burnout → Validator only, minimal complexity
- ORANGE depleted → Restorer + max 2 others
- Working memory hard limit: 3 items without structure

**ECHO 2.0 Framework** - Constitutional Field:
- L0 Primitives always active
- Safety first > productivity
- User signal > Claude's guess

**Cortex_Mycelium Framework** - Biological Constraints:
- Homeostatic regulation prevents runaway specialization
- Target activation balance across expert pool

### Reference Files
- `ADHD Support Framework.txt` (Lines 50-57: Safety constraints)
- `ECHO 2.0 Framework.txt` (Lines 584-662: Constitutional Field)

---

## Component 3: 5-Phase Routing (ACTIVATE→WEIGHT→BOUND→SELECT→UPDATE)

### V5 Implementation
```python
async def execute(self, task, context):
    activation = self._activate(task, context)   # Phase 1
    weighted = self._weight(activation, context) # Phase 2
    bounded = self._bound(weighted)              # Phase 3
    selected = self._select(bounded)             # Phase 4
    update = self._prepare_update(...)           # Phase 5
```

### Framework Sources

**NEXUS Framework** - 5-Phase Execution Loop:
```
1. DETECT    → Signal extraction (PRISM)
2. CASCADE   → Expert routing (MoE priority chain)
3. LOCK      → Parameter locking (no runtime mutation)
4. EXECUTE   → Generation with locked params
5. UPDATE    → State mutation + convergence check
```

**MAX 3 Framework** - HAS Adaptive Parameters:
- Confidence-based expert blending
- Single expert: confidence > 0.8
- Multi-expert blend: 0.4 < confidence < 0.7

### Reference Files
- `NEXUS Framework (Code + Annotations).txt` (Lines 52-172)
- `MAX 3 Framework.txt` (Lines 48-75: HAS levels)

---

## Component 4: Mycelium Neuroplasticity

### V5 Implementation
```python
class Mycelium:
    def __init__(self):
        self.expert_weights = {e: 1/7 for e in experts}
        self.learning_rate = 0.1
        self.outcomes = []

    def record_outcome(self, expert, outcome, task_hash):
        # Hebbian: w_new = w_old + α(outcome - expected) × activation
        pass
```

### Framework Sources

**Cortex_Mycelium Framework** - Emergent Specialization:
- Local connection strengthening via Hebbian learning
- Correlations strengthen connections
- Temporal decay (half-life: 100 exchanges)

**Mycelium Properties**:
1. **Homeostatic Plasticity**: Prevent winner-take-all
2. **Critical Periods**: Fast learning at session start
3. **Metaplasticity**: Learning rates themselves adapt
4. **Distributed**: No central controller, pure local rules

### Reference Files
- `Cortex_Mycelium Framework.txt` (Lines 142-250: MYCELIUM paradigm)
- `ECHO 2.0 Framework.txt` (Evolution algorithms)

---

## Component 5: ADHD Support (Working Memory, Burnout)

### V5 Context
The Framework Ottotor's ADHD support is implicit in:
- Expert priority ordering (safety experts first)
- Safety floor enforcement
- Burnout signal detection in triggers

### Framework Sources

**ADHD Support Framework** - Core Constraints:
```
Working Memory Hard Limits:
├─ Max 3 items without explicit structure
├─ Max 5 visible subtasks
├─ Context window: 50K tokens = checkpoint trigger
└─ Body check interval: 20 rapid exchanges

Burnout Levels:
├─ GREEN: Normal → Continue
├─ YELLOW: Fatigue → Monitor, suggest break
├─ ORANGE: Depleted → Restorer + simplify
└─ RED: Crisis → Validator only, full stop
```

**Momentum Tracking** (Distinct from burnout):
- cold_start → building → rolling → peak → declining → crashed
- Transition detection via engagement patterns

### Reference Files
- `ADHD Support Framework.txt` (Complete specification)
- `Nova adhd.txt` (Additional patterns)

---

## Component 6: Convergence Tracking (RC^+xi)

### V5 Implementation
```python
# In execute() output:
"raw_winner": raw_winner,
"safety_intervention": safety_intervention,
"update_context": {
    "selected_expert": selected,
    "task_hash": hash,
    "awaiting_outcome": True,
    "hebbian_ready": True
}
```

### Framework Sources

**RC^+ξ Framework** - Epistemic Tension:
```
Core Formula:
ξ_n = ||A_{n+1} - A_n||_2  (state distance)

Convergence:
- Epsilon threshold: 0.1
- Stable: 3 consecutive exchanges with ξ < epsilon
- Attractor basins: focused, exploring, recovery, teaching
```

**Resonance Framework** - Reflection Triggers:
- ξ > 0.3 → Convergence check
- context_length > 50% → Coherence check
- expert_switch_count > 3 → Stability check
- energy drops 2+ levels → Trajectory check

### Reference Files
- `RC^+ξ^ framework - Research ( _the soul_).txt` (Lines 21-52)
- `MAX 3 Framework.txt` (Lines 184-280: RCXiEngine)
- `Resonance Framework (SelfReflect).txt` (Lines 198-246)

---

## Cross-Framework Integration Map

```
┌─────────────────────────────────────────────────────────────────┐
│                    V5 Framework Ottotor                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────────────┐   │
│  │ PRISM       │──▶│ ADHD_MoE    │──▶│ NEXUS 5-Phase       │   │
│  │ (Signals)   │   │ (Experts)   │   │ (Execution)         │   │
│  └─────────────┘   └─────────────┘   └─────────────────────┘   │
│         │                │                     │                │
│         ▼                ▼                     ▼                │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────────────┐   │
│  │ ECHO        │   │ Cortex/     │   │ RC^+xi              │   │
│  │ (Memory)    │   │ Mycelium    │   │ (Convergence)       │   │
│  │             │   │ (Paradigm)  │   │                     │   │
│  └─────────────┘   └─────────────┘   └─────────────────────┘   │
│         │                │                     │                │
│         └────────────────┴─────────────────────┘                │
│                          │                                      │
│                          ▼                                      │
│               ┌─────────────────────┐                          │
│               │ ThinkingMachines    │                          │
│               │ (Determinism)       │                          │
│               └─────────────────────┘                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Framework File Index

| Framework | File | Size | V5 Relevance |
|-----------|------|------|--------------|
| ADHD Support | `ADHD Support Framework.txt` | 56KB | MoE experts, safety floors, working memory |
| Cortex/Mycelium | `Cortex_Mycelium Framework.txt` | 21KB | Paradigm switching, Hebbian learning |
| NEXUS | `NEXUS Framework (Code + Annotations).txt` | 27KB | 5-phase execution |
| ECHO 2.0 | `ECHO 2.0 Framework.txt` | 47KB | Memory management, constitutional |
| MAX 3 | `MAX 3 Framework.txt` | 50KB | RC^+xi engine, HAS adaptation |
| RC^+xi | `RC^+ξ^ framework - Research.txt` | - | Convergence math, attractors |
| Resonance | `Resonance Framework (SelfReflect).txt` | - | Reflection triggers |
| PRISM | `PRISM - Framework - Research.txt` | - | Signal detection |
| Phoenix | `Phoenix_Framework_v6.txt` | - | Domain analysis |

---

## Implementation Status

| Component | Implemented | Framework Grounded | Test Coverage |
|-----------|------------|-------------------|---------------|
| 7 Experts | ✅ | ✅ ADHD Support | ✅ 10 tests |
| Safety Floors | ✅ | ✅ ADHD + ECHO | ✅ |
| 5-Phase Routing | ✅ | ✅ NEXUS | ✅ |
| Mycelium Foundation | ✅ | ✅ Cortex/Mycelium | ✅ 3 tests |
| DISPLAY_NAMES | ✅ | Human-friendly layer | - |
| safety_intervention | ✅ | ThinkingMachines audit | - |

---

## Citations

- **ADHD Support Framework**: Intervention experts, working memory limits, burnout detection
- **NEXUS Framework**: 5-phase execution loop, execution-guided learning
- **Cortex_Mycelium Framework**: Paradigm switching, Hebbian neuroplasticity
- **ECHO 2.0 Framework**: Memory architecture (LIVRPS), constitutional field
- **MAX 3 Framework**: RC^+xi convergence, HAS adaptive parameters
- **RC^+xi Research**: Epistemic tension formula, attractor basin theory
- **Resonance Framework**: Self-reflection triggers, ancestral wisdom synthesis
- **PRISM Framework**: 7-perspective signal analysis
- **ThinkingMachines [He2025]**: Batch-invariance, determinism guarantees

---

*Generated: 2026-01-21*
*Location: C:\Users\User\.claude\substrate\docs\Framework_Ottotor*
