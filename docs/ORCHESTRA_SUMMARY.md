# Otto: Complete Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           QUICK REFERENCE                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Otto = USD Composition Semantics for Human Cognitive State           │
│                                                                             │
│   Same signals → Same routing → Same behavior                               │
│   (application-layer determinism, inspired by [He2025])                     │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│ Product:  Otto (this repo)                                             │
│ Research: usd-cognitive-substrate                                           │
│ Website:  aiconductor.studio                                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## The Core Thesis

**Otto is a cognitive prosthetic** — not a task automation tool, but a brain extension that scaffolds human cognition where it's biologically limited.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  USD (Universal Scene Description) as Universal STATE Description           │
│                                                                             │
│  Pixar invented LIVRPS to resolve conflicting opinions in 3D pipelines.    │
│  We repurpose these semantics for COGNITIVE STATE MANAGEMENT:               │
│                                                                             │
│    Scene graph    →  Cognitive architecture                                 │
│    Prim attributes →  Behavioral parameters                                 │
│    Composition arcs →  Priority resolution (emotional > mode > domain)     │
│    Variants       →  Mode switching (focused/exploring/recovery)           │
│    Layers         →  Cognitive subsystems (14 layers)                      │
│    Payloads       →  Domain knowledge (loaded on demand)                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## What Makes Otto Unique

| Traditional AI Tools | Otto |
|---------------------|-----------|
| Assist with tasks | Scaffolds human cognition |
| Optional helpers | Foundational (no toggle) |
| Select best expert | Weighted blend of ALL frameworks |
| Auto-resolve conflicts | Surface tensions for human decision |
| Stateless per-message | Persistent cognitive state (37 fields) |
| Generic for all users | ADHD-first design that helps everyone |

---

## The 5-Phase NEXUS Pipeline

Every message flows through this deterministic pipeline:

```
┌─────────────────┐
│ 1. DETECT       │  PRISM extracts signals across 6 perspectives
│    (PRISM)      │  emotional > mode > domain > task > energy
└────────┬────────┘
         ▼
┌─────────────────┐
│ 2. CASCADE      │  Safety gates + 7-expert Cognitive Safety MoE
│ (CogSafety MoE) │  First-match-wins: Validator → ... → Direct
└────────┬────────┘
         ▼
┌─────────────────┐
│ 3. LOCK         │  MAX3 bounded reflection + safety gating
│    (MAX3)       │  Deterministic checksums before generation
└────────┬────────┘
         ▼
┌─────────────────┐
│ 4. EXECUTE      │  Claude generates with locked params
│   (Claude)      │  Anchor: [EXEC:a3f2b8|direct|Cortex|30000ft|standard]
└────────┬────────┘
         ▼
┌─────────────────┐
│ 5. UPDATE       │  RC^+xi convergence tracking
│   (RC^+xi)      │  Attractor basins: focused|exploring|recovery|teaching
└─────────────────┘
```

**Determinism (inspired by [He2025])**: Same signals --> Same routing --> Same behavior (98/100 score)

---

## The 7 Intervention Experts

Fixed priority, first-match-wins semantics:

| # | Expert | Triggers | Response Philosophy |
|---|--------|----------|---------------------|
| 1 | Validator | frustrated, RED, CAPS | Empathy first, normalize struggle |
| 2 | Scaffolder | overwhelmed, stuck | Break down, reduce scope |
| 3 | Restorer | depleted, ORANGE | Easy wins, rest is productive |
| 4 | Refocuser | tangent, distracted | Gentle redirect to goal |
| 5 | Celebrator | task_complete | Acknowledge win, dopamine boost |
| 6 | Socratic | exploring, what_if | Guide discovery, follow threads |
| 7 | Direct | focused, flow | Minimal friction, stay out of way |

---

## Cognitive State Tracking (37 Fields)

```
Burnout:    GREEN ──→ YELLOW ──→ ORANGE ──→ RED
Momentum:   COLD_START → BUILDING → ROLLING → PEAK → CRASHED
Energy:     HIGH ──→ MEDIUM ──→ LOW ──→ DEPLETED
Mode:       FOCUSED | EXPLORING | TEACHING | RECOVERY
Altitude:   30000ft (Vision) → 15000ft (Arch) → 5000ft (Components) → Ground
```

**Safety Gating** (state ALWAYS overrides user request):
- depleted → minimal thinking (1K tokens)
- RED burnout → minimal thinking
- high energy → ultradeep allowed (128K tokens)

---

## The v7.0 Substrate Runtime

The latest evolution adds three critical subsystems:

```
┌─────────────────────────────────────────────────────────────────┐
│ KNOWLEDGE PRIMS - O(1) Factual Retrieval                        │
│   "What is LIVRPS?" → Direct retrieval (0.001ms vs 150ms LLM)  │
│   89 prims loaded | 357 triggers indexed | 17 domains          │
├─────────────────────────────────────────────────────────────────┤
│ EXTERNAL WORKING MEMORY (EWM)                                   │
│   SessionAnchor: "What's the goal?" resurfaces every 10 exch   │
│   TimeBeacon: Exchange count as time proxy (20 exch ≈ 90 min)  │
│   ProjectFriction: Surface open projects before starting new   │
├─────────────────────────────────────────────────────────────────┤
│ HARDENING - Production Grade                                    │
│   StateManager: Atomic writes, graceful degradation            │
│   HandoffManager: Cross-session continuity, "lost the thread"  │
│   Backups: Auto-backup before state modifications              │
└─────────────────────────────────────────────────────────────────┘
```

---

## USD Composition (LIVRPS) for Cognitive State

```
L - LOCAL        Session state (mutable, highest priority)
I - INHERITS     Parent task context
V - VARIANTSETS  Mode switching (focused/exploring/recovery)
R - REFERENCES   Calibration data (cross-session learning)
P - PAYLOADS     Domain knowledge (VFX, WebDev, AI Research)
S - SPECIALIZES  Constitutional principles (IMMUTABLE safety floors)
```

**Key insight**: Higher layers override, but lower layers are ALWAYS consulted. Constitutional principles don't "win" — they establish inviolable floors.

---

## The ADHD-First Philosophy

Otto was designed around cognitive science, not diagnosis:

| Cognitive Challenge | Otto's Compensation |
|--------------------|--------------------------|
| Working memory (~3-4 items) | External structure, max 5 visible subtasks |
| Time blindness | Exchange counting, body checks every 20 exchanges |
| Task initiation | Momentum tracking, easy wins for cold start |
| Hyperfocus exit | Burnout detection, checkpoint suggestions |
| Perfectionism | "Is this blocking ship? Ship it. Polish later." |
| Context switching | State persistence, handoff protocols |
| Tangent spirals | Tangent budget (5 per session), explicit tracking |

**Guiding Principle**: The principles that help neurodivergent minds are simply good cognitive ergonomics. Everyone benefits.

---

## Architecture Overview

```
Otto/
├── src/otto/
│   ├── cognitive_ottotor.py   # 5-Phase NEXUS Pipeline
│   ├── prism_detector.py           # Signal detection (6 perspectives)
│   ├── expert_router.py            # Cognitive Safety MoE (7 experts)
│   ├── parameter_locker.py         # MAX3 + safety gating
│   ├── convergence_tracker.py      # RC^+xi attractor basins
│   ├── cognitive_state.py          # 37-field state management
│   ├── adhd_support.py             # Cognitive safety constraints
│   ├── tension_surfacer.py         # Conflict detection
│   ├── decision_engine.py          # Work/Delegate/Protect routing
│   ├── claude_code_hook.py         # Hookify integration
│   ├── dashboard.py                # CLI visualization
│   └── substrate/                  # v7.0 Runtime
│       ├── knowledge/              # O(1) retrieval engine
│       ├── ewm/                    # External working memory
│       └── hardening/              # Production stability
├── config/
│   ├── frameworks/
│   │   └── cognitive_safety_moe/   # Safety-tier payload
│   └── domains/                    # Domain configs (VFX, WebDev, AI)
├── hooks/                          # Claude Code integration
└── tests/                          # 685+ tests
```

---

## Key Innovations

1. **Cognitive Prosthetic as Architecture** — Not optional support, foundational design
2. **USD Composition for Cognition** — Pixar's scene resolution for human state
3. **Weighted Blend, Not Selection** — All frameworks contribute proportionally
4. **Tension Surfacing** — Conflicts shown to human, not auto-resolved
5. **Attractor Basin Convergence** — Cognitive state as dynamic system
6. **Determinism Compliance [He2025]** — Deterministic, reproducible behavior
7. **ADHD-First Universal Design** — Biology-respecting defaults for everyone

---

## The Constitutional Principles (Never Violated)

1. **Safety first** — Emotional safety before productivity
2. **Ship over perfect** — Working beats polished
3. **Protect momentum** — Don't break flow unnecessarily
4. **External over internal** — Write it down
5. **Recover without guilt** — Rest is productive
6. **One at a time** — Complete before switching
7. **User knows best** — Their signal trumps Claude's guess

---

## Integration with Claude Code

```bash
otto install-hook   # Install hookify integration
otto status         # View cognitive state
otto calibrate      # Quick depth assessment
```

Every message you send passes through the 5-phase pipeline, with the dashboard showing real-time cognitive state via WebSocket.

---

## The Big Picture

Otto transforms Claude Code from a coding assistant into a cognitive partner that:

- **Knows when you're frustrated** and responds with empathy first
- **Knows when you're depleted** and protects you from overextension
- **Knows when you're in flow** and stays out of the way
- **Remembers your session goal** and resurfaces it periodically
- **Tracks your momentum** and celebrates wins
- **Never lets you spiral** into perfectionism without a checkpoint

It's not about making Claude smarter. It's about making the human-AI collaboration **cognitively sustainable**.

---

## References

- **[He2025]**: https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/
- **Otto GitHub**: https://github.com/JosephOIbrahim/Otto
- **USD Cognitive Substrate (Research)**: https://github.com/JosephOIbrahim/usd-cognitive-substrate
- **aiconductor.studio**: https://aiconductor.studio

---

*Document generated: January 2026*
*Version: Otto v7.0 with Substrate Runtime*
