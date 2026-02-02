# OTTO OS: Complete System Index

> **Generated**: 2026-02-01
> **Version**: 0.5.0
> **Purpose**: Comprehensive reference for Claude Desktop discussion
> **Tests**: 3849 passing / 3853 total

---

## Executive Summary

**OTTO OS is an operating system for variable attention** — the first computing layer where neurodivergent cognitive patterns are the native architecture, not an accommodation.

**Core Thesis**: Attention fluctuates, crashes, surges, and drifts — and that variation is **feature, not failure**.

**Key Innovation**: A 5-phase deterministic cognitive pipeline (DETECT → CASCADE → LOCK → EXECUTE → UPDATE) routes requests through 7 specialist modes based on detected cognitive state, with [He2025] batch-invariant execution guarantees.

---

## 1. Foundation Documents

| Document | Purpose | Location |
|----------|---------|----------|
| **PHILOSOPHY.md** | The Soul — Why we build, language standards, stealth accommodation | `docs/PHILOSOPHY.md` |
| **STRATEGY.md** | The Nervous System — Technical foundation, runtime decisions | `docs/STRATEGY.md` |
| **BLUEPRINT.md** | The Body — What we build, development phases, testing | `BLUEPRINT.md` |
| **README.md** | Public-facing overview | `README.md` |

**Ground Truth Hierarchy**: BLUEPRINT > Code > Implementation Details

---

## 2. Architecture Overview

### 2.1 System Layers (Bottom to Top)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 4: USER INTERFACE                                                     │
│  CLI / TUI / API                                                             │
│  Human-readable output • Dignity-first language • Adaptive verbosity         │
├─────────────────────────────────────────────────────────────────────────────┤
│  LAYER 3: HUMAN RENDER                                                       │
│  Natural language generation • State-aware verbosity • No clinical terms     │
│  Transforms structured data → human-friendly output                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  LAYER 2: OTTO CORE                                                          │
│  JSON-RPC Protocol • Cognitive Engine • State Management • Protection        │
│  The brain — deterministic routing, safety gating, convergence               │
├─────────────────────────────────────────────────────────────────────────────┤
│  LAYER 1: AGENT KERNEL                                                       │
│  Binary Protocol (MessagePack) • Agent ↔ Agent Communication                 │
│  Maximum speed • No human rendering overhead • Typed messages                │
├─────────────────────────────────────────────────────────────────────────────┤
│  LAYER 0: PERSISTENCE                                                        │
│  USD State Files • Encrypted Storage • Session Continuity                    │
│  ~/.otto/ directory structure • Atomic writes • Backup on modify             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Cognitive Pipeline (5-Phase NEXUS)

```
DETECT → CASCADE → LOCK → EXECUTE → UPDATE
   │         │        │        │         │
   │         │        │        │         └─ RC^+xi convergence tracking
   │         │        │        └─ Generate response with locked params
   │         │        └─ Lock parameters (MAX3 bounds, safety gating)
   │         └─ Route through ADHD_MoE (7 experts, first-match-wins)
   └─ PRISM signal extraction (6 categories, fixed order)
```

### 2.3 LIVRPS Composition (USD-Based Priority)

Personality/state resolution follows USD composition semantics:

| Layer | Priority | Content |
|-------|----------|---------|
| **L**ocal | Highest | Session state (mutable at runtime) |
| **I**nherits | High | Inherited from parent context |
| **V**ariantSets | Medium | Mode switching (focused/exploring/recovery) |
| **R**eferences | Medium | Calibration data (cross-session learning) |
| **P**ayloads | Low | Personality profile (from intake) |
| **S**pecializes | Lowest | Base defaults |

---

## 3. The Seven Specialist Modes

| Priority | Expert | Triggers | Behavior |
|----------|--------|----------|----------|
| 1 | **Validator** | frustrated, RED, caps, negative | Empathy first, normalize |
| 2 | **Scaffolder** | overwhelmed, stuck, too_many | Break down, reduce scope |
| 3 | **Restorer** | depleted, ORANGE, post-crash | Easy wins, rest is OK |
| 4 | **Refocuser** | distracted, tangent_over | Gentle redirect to goal |
| 5 | **Celebrator** | task_complete, milestone | Acknowledge win |
| 6 | **Socratic** | exploring, high_energy, what_if | Guide discovery |
| 7 | **Direct** | focused, hyperfocused, flow | Stay out of the way |

**Routing Rule**: First match wins. Fixed priority order for determinism.

---

## 4. State Management

### 4.1 Cognitive State (62 Fields in v7.1.0)

**Core Fields:**
- `burnout_level`: GREEN → YELLOW → ORANGE → RED
- `momentum_phase`: cold_start → building → rolling → peak → crashed
- `energy_level`: high | medium | low | depleted
- `detected_state`: focused | stuck | overwhelmed | frustrated | hyperfocused | depleted

**Grounding State (v6.0):**
- `grounding_mode`: LEARN | ACCESS | HYBRID
- `oracle_cache_age`, `evidence_chain_length`, `hallucination_score`

**BCM Trails (v7.0):**
- `bcm_expert_confidence`: Trail-based learning per expert
- `bcm_plasticity_sigma`: Learning rate multiplier (0.0-1.0)

### 4.2 File Locations

```
~/.otto/
├── profile.usda              # Personality (from intake)
├── calibration.usda          # Learned overrides
├── state/
│   ├── session.json          # Current session
│   ├── cognitive.json        # Cognitive state (62 fields)
│   └── checkpoints/          # Recovery points
├── knowledge/                # Knowledge prims
├── sessions/                 # Session archive
├── agents/                   # Agent state
└── config/                   # User preferences
```

---

## 5. Module Index

### 5.1 Source Code (`src/otto/` — 217 files)

| Directory | Files | Purpose |
|-----------|-------|---------|
| `agents/` | Agent implementations (coordinator, decision, protocol) |
| `api/` | REST/WebSocket API for external integration |
| `calibration/` | Cross-session learning, pattern detection |
| `cli/` | Command-line interface, TUI dashboard |
| `core/` | ProfileManager, CognitiveStateManager, LIVRPS composition |
| `crypto/` | Encryption utilities |
| `hooks/` | Tool hooks (AutoValidate, TrailContext, Work) |
| `inference/` | LLM integration layer |
| `input/` | Platform-agnostic input handling |
| `intake/` | 10-minute personality game |
| `integration/` | Calendar, tasks, external services |
| `messaging/` | Protocol handling |
| `mobile/` | Mobile abstraction layers |
| `output/` | Formatters (Plain, JSON, status rendering) |
| `protection/` | Burnout detection, boundary enforcement |
| `protocol/` | JSON-RPC and binary protocol definitions |
| `render/` | Human-friendly output generation |
| `schema/` | USD schema definitions |
| `security/` | Keyring abstraction, credential management |
| `storage/` | Platform-agnostic storage providers |
| `substrate/` | Knowledge prims, EWM, handoff management |
| `sync/` | State synchronization |
| `trails/` | Pheromone trail system (stigmergic learning) |
| `tui/` | Terminal UI components |

### 5.2 Key Modules (Cognitive Engine)

| Module | Purpose | Key Exports |
|--------|---------|-------------|
| `cognitive_state.py` | State tracking (62 fields) | `CognitiveState`, `CognitiveStateManager`, `BurnoutLevel`, `MomentumPhase` |
| `prism_detector.py` | Signal extraction (6 categories) | `PRISMDetector`, `SignalVector`, `SIGNAL_PATTERNS` |
| `expert_router.py` | Cognitive Safety MoE routing | `ExpertRouter`, `Expert`, `EXPERT_PRIORITY` |
| `parameter_locker.py` | MAX3 bounds + safety gating | `ParameterLocker`, `LockedParams`, `DEPTH_BUDGETS` |
| `convergence_tracker.py` | RC^+xi tension tracking | `ConvergenceTracker`, `AttractorBasin`, `StateVector` |
| `cognitive_orchestrator.py` | 5-phase NEXUS pipeline | `CognitiveOrchestrator`, `NexusResult`, `create_orchestrator` |

### 5.3 Core Subsystems

| Module | Purpose | Key Exports |
|--------|---------|-------------|
| `core/profile.py` | Profile management with LIVRPS | `ProfileManager`, `Profile`, `ProfileSource` |
| `core/livrps.py` | USD composition implementation | `LIVRPSResolver`, `LayerType`, `resolve_livrps` |
| `core/cognitive_state_manager.py` | Unified state management | `CognitiveStateManager` |
| `render/human_render.py` | Dignity-first language | `HumanRender`, `render_status`, `FORBIDDEN_WORDS` |
| `intake/game.py` | Personality intake experience | `IntakeGame`, `run_intake` |
| `trails/store.py` | Pheromone trail persistence | `TrailStore`, `Trail`, `TrailType` |
| `hooks/auto_validate.py` | [He2025] compliance checking | `AutoValidateHook` |

---

## 6. MCP Tool Integration

### 6.1 Orchestra MCP (`packages/orchestra-mcp/`) — 9 Tools

| Tool | Purpose |
|------|---------|
| `otto_status` | Get current cognitive state |
| `otto_calibrate` | Trigger calibration assessment |
| `otto_session` | Session management commands |
| `otto_goal` | Set/get session goal |
| `otto_protection` | Query protection status |
| `otto_intake` | Run personality intake |
| `otto_verify_determinism` | [He2025] compliance check |
| `otto_get_test_coverage` | Module test coverage |
| `otto_run_module_tests` | Run specific module tests |

### 6.2 Trails MCP (`packages/otto-trails-mcp/`) — 6 Tools

| Tool | Purpose |
|------|---------|
| `otto_read_trails` | Read trails for a file path |
| `otto_deposit_trail` | Create/reinforce a trail |
| `otto_reinforce_trail` | Strengthen existing trail |
| `otto_query_trails` | Flexible trail search |
| `otto_get_related` | Follow CONTEXT trails |
| `otto_decay_trails` | Run decay + pruning |

---

## 7. Trail System (Pheromone Architecture)

### 7.1 Trail Types

| Type | Purpose | Example Signals |
|------|---------|-----------------|
| `QUALITY` | Code quality signals | `he2025_compliant`, `imports_clean` |
| `CONTEXT` | Dependency relationships | `depends_on:X`, `used_by:Y` |
| `DECISION` | Why choices were made | `chose:sorted_max\|reason:determinism` |
| `PATTERN` | Recurring approaches | `when_stuck:check_LIVRPS` |
| `WORK` | Current activity | `recently_edited`, `mid_refactor` |

### 7.2 Trail Properties

- **Strength**: 0.0 - 1.0 (decays over time)
- **Half-life**: Default 7 days
- **Reinforcement**: Successful patterns strengthen trails
- **Decay**: Unused trails weaken and prune at < 0.1

---

## 8. [He2025] Determinism Compliance

### 8.1 Core Patterns (MUST Use)

| Pattern | Wrong | Correct |
|---------|-------|---------|
| Dict max | `max(d.items(), key=...)` | `sorted_max(d)` |
| Float sum | `sum(values)` | `kahan_sum(sorted(values))` |
| Set iteration | `for x in set(...)` | `for x in sorted(set(...))` |
| Dict iteration | `for k in dict.keys()` | `for k in sorted(dict.keys())` |
| Random | `random.choice(...)` | `random.seed(FIXED); random.choice(...)` |

### 8.2 Verification Tools

```python
# Round to 6 decimals for reproducibility
value = round(value, 6)

# Determinism test pattern
results = [function(inputs) for _ in range(100)]
assert all(r == results[0] for r in results)
```

---

## 9. Protection Systems

### 9.1 Burnout Detection

| Level | Signals | Response |
|-------|---------|----------|
| GREEN | Normal pace | Continue |
| YELLOW | Short responses, typos | "Quick break soon?" |
| ORANGE | Frustration, repetition | "What's the blocker?" |
| RED | Caps, negativity | Full stop + recovery |

### 9.2 Safety Gating

**Rule**: User's cognitive state OVERRIDES their depth request.

| State | Max Depth Allowed |
|-------|-------------------|
| `energy=depleted` | minimal |
| `energy=low` | standard |
| `burnout>=ORANGE` | standard |
| `burnout=RED` | minimal |

---

## 10. Test Coverage

### 10.1 Test Metrics

| Category | Tests | Status |
|----------|-------|--------|
| **Total** | 3853 | 3849 passing, 4 skipped |
| Unit tests | ~2500 | Full coverage |
| Integration | ~800 | End-to-end flows |
| Determinism | ~200 | [He2025] compliance |
| Chaos engineering | ~100 | Failure scenarios |

### 10.2 Test Locations (`tests/` — 128 files)

| Directory | Purpose |
|-----------|---------|
| `tests/test_core/` | ProfileManager, LIVRPS, state management |
| `tests/test_intake/` | Intake game, profile integration |
| `tests/test_trails.py` | Trail system (36 tests) |
| `tests/test_hooks.py` | Hook system (21 tests) |
| `tests/test_mcp_new_tools.py` | MCP tools (12 tests) |
| `tests/test_human_render.py` | Dignity-first rendering |
| `tests/test_cognitive_*.py` | Cognitive engine components |

---

## 11. Documentation Index (53 files)

### 11.1 Core Docs

| Document | Purpose |
|----------|---------|
| `docs/ARCHITECTURE.md` | Technical deep-dive |
| `docs/QUICKSTART.md` | 5-minute getting started |
| `docs/USER_GUIDE.md` | Complete usage documentation |
| `docs/INTEGRATION_GUIDE.md` | External service connections |
| `docs/API.md` | API reference |
| `docs/DETERMINISM.md` | [He2025] compliance guide |

### 11.2 Technical Specs

| Document | Purpose |
|----------|---------|
| `docs/DETERMINISM_SPECIFICATION.md` | Formal determinism requirements |
| `docs/THINKINGMACHINES_COMPLIANCE.md` | Batch invariance spec |
| `docs/HE2025_DEEP_CONSISTENCY_AUDIT.md` | Compliance audit results |
| `docs/USD_COGNITIVE_SUBSTRATE_V5.md` | USD architecture decisions |

### 11.3 Development

| Document | Purpose |
|----------|---------|
| `docs/development/contributing.md` | Contribution guidelines |
| `docs/development/testing.md` | Testing strategy |
| `docs/API_IMPLEMENTATION_INDEX.md` | API implementation status |

---

## 12. CLI Commands

```bash
# Installation
pip install -e ".[dev]"

# Personality intake (first run)
otto-intake

# Daily use
otto                    # Start OTTO
otto status             # Show cognitive state
otto tui                # Terminal dashboard

# Development
pytest                  # Run all 3853 tests
pytest tests/test_trails.py -v  # Specific module
pytest --cov=src/otto   # Coverage report
```

---

## 13. Key Design Principles

### 13.1 Constitutional (Never Violate)

1. **Safety first**: Emotional safety before productivity
2. **Ship over perfect**: Working beats polished
3. **Protect momentum**: Don't break flow unnecessarily
4. **External over internal**: Write it down
5. **Recover without guilt**: Rest is productive
6. **One at a time**: Complete before switching
7. **User knows best**: Their signal trumps Claude's guess

### 13.2 Language Standards (FORBIDDEN)

Never use clinical/diagnostic terms:
- ADHD, ADD, executive dysfunction
- Disorder, deficit, symptoms
- Diagnosis, treatment, therapy

**Instead use**:
- "You seem tired" (not "burnout detected")
- "Let's slow down" (not "overload warning")
- "Variable attention" (not "attention deficit")

---

## 14. Implementation Status

### 14.1 Completed Phases

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Core integration (LIVRPS, ProfileManager, CognitiveStateManager) | ✅ |
| 2 | Intake form system | ✅ |
| 3 | MCP tools (Orchestra + Trails) | ✅ |
| 4 | Test suite (3849 passing) | ✅ |

### 14.2 Pheromone Trail Architecture

| Component | Status |
|-----------|--------|
| Trail data model (`Trail`, `TrailType`, `TrailQuery`) | ✅ |
| Trail store (SQLite-backed CRUD + decay) | ✅ |
| Hook system (AutoValidate, TrailContext, Work) | ✅ |
| MCP integration (6 trail tools) | ✅ |

---

## 15. Quick Reference

### 15.1 State Flow

```
User Input → PRISM Detect → Expert Route → Safety Gate → Execute → Update State
                │                │              │
                ├─ emotional?    ├─ Validator   ├─ depth limit
                ├─ grounding?    ├─ Scaffolder  ├─ burnout check
                ├─ mode switch?  ├─ Restorer    ├─ momentum track
                └─ task type?    └─ Direct      └─ convergence
```

### 15.2 Key Formulas

```python
# Epistemic tension (convergence)
xi_n = ||A_{n+1} - A_n||_2

# BCM confidence
confidence = 0.6 × success_rate + 0.4 × strength_normalized

# Trail decay
strength *= 0.5 ** (hours_elapsed / half_life_hours)
```

### 15.3 File Patterns

```python
# All source files
src/otto/**/*.py  # 217 files

# All tests
tests/**/*.py  # 128 files

# Configuration
*.usda, *.yaml, *.json
```

---

## 16. Discussion Topics for Claude Desktop

1. **Stealth Accommodation Design**: How the system serves neurodivergent users without labeling them

2. **Determinism Strategy**: [He2025] compliance at application level vs kernel level

3. **Trail-Based Learning**: Stigmergic patterns from ant colony optimization applied to code intelligence

4. **LIVRPS Composition**: Repurposing Pixar's USD semantics for cognitive state management

5. **7-Expert Architecture**: Why first-match-wins routing is both simpler and more deterministic

6. **Safety Gating Philosophy**: Why user state should override user requests

7. **Dignity-First Language**: The forbidden words list and alternative vocabulary

8. **Production Hardening**: 3849 tests, chaos engineering, graceful degradation

---

*Generated from OTTO OS v0.5.0 | 217 source files | 128 test files | 53 docs*
