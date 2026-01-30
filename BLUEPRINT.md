# OTTO OS: Master Blueprint

> **Document Status**: Living specification
> **Version**: 0.5.0
> **Last Updated**: 2026-01-29
> **Authority**: This document is the ground truth. Code follows blueprint.

## The Three Documents

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         OTTO OS FOUNDATION                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PHILOSOPHY.md          STRATEGY.md           BLUEPRINT.md                  │
│  ══════════════         ═══════════           ════════════                  │
│  The Soul               The Nervous System    The Body                      │
│                                                                              │
│  • Why we build         • Where we came from  • What we build               │
│  • How we speak         • Technical foundation• How it works                │
│  • Stealth accomm.      • Moat analysis       • Development phases          │
│  • Language standards   • Runtime decisions   • Testing strategy            │
│                                                                              │
│  "Variable attention    "OTTO OS is you,      "5-phase pipeline,            │
│   is feature, not        externalized"         7 experts, USD"              │
│   failure"                                                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**When in doubt:**
- For *why* and *language* → PHILOSOPHY.md
- For *origin* and *strategy* → STRATEGY.md
- For *implementation* → BLUEPRINT.md (this document)

---

## Table of Contents

1. [Vision & Philosophy](#1-vision--philosophy)
2. [Architecture Overview](#2-architecture-overview)
3. [Core Systems](#3-core-systems)
4. [Communication Protocol](#4-communication-protocol)
5. [Cognitive Engine](#5-cognitive-engine)
6. [Personality System](#6-personality-system)
7. [Protection Mechanisms](#7-protection-mechanisms)
8. [Agent Orchestration](#8-agent-orchestration)
9. [Knowledge Layer](#9-knowledge-layer)
10. [Privacy & Security](#10-privacy--security)
11. [Integration Layer](#11-integration-layer)
12. [User Experience](#12-user-experience)
13. [Development Phases](#13-development-phases)
14. [Testing Strategy](#14-testing-strategy)
15. [Success Metrics](#15-success-metrics)
16. [Open Questions](#16-open-questions)

---

## 1. Vision & Philosophy

### 1.1 The Thesis

**OTTO OS is an operating system for variable attention.**

Most productivity tools assume human attention is linear and infinite. OTTO OS assumes what neuroscience already knows: attention fluctuates, crashes, surges, and drifts—and that variation is **feature, not failure**.

### 1.2 Core Beliefs

| Belief | Implication |
|--------|-------------|
| Attention varies | System adapts to state, not the reverse |
| Labels harm | No diagnostic language, no "ADHD mode" |
| Safety > Productivity | Emotional safety precedes task completion |
| Privacy is dignity | Data stays local unless explicitly shared |
| Rest is productive | Recovery is not failure |
| Stealth accommodation | Designed for neurodivergent, works for everyone |

### 1.3 The Curb Cut Principle

Like curb cuts designed for wheelchairs but used by everyone with strollers and luggage, OTTO's neurodivergent-native architecture benefits **all humans** who have off-days, crash cycles, or non-linear work patterns.

The system never asks "do you have ADHD?" It simply works differently—in ways that happen to be exactly what neurodivergent users need and that neurotypical users experience as "finally, a computer that gets me."

### 1.4 What OTTO Is Not

- Not a productivity app (doesn't optimize for output)
- Not a therapist (doesn't diagnose or treat)
- Not a tracker (doesn't surveil or report)
- Not a nanny (doesn't moralize about behavior)
- Not an attention-capture tool (doesn't maximize engagement)

### 1.5 What OTTO Is

- A conductor for your cognitive orchestra
- A membrane between you and AI systems
- A guardian of sustainable engagement
- A memory you don't have to maintain
- A system that knows when to disappear

---

## 2. Architecture Overview

### 2.1 System Layers

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                OTTO OS                                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                        LAYER 4: USER INTERFACE                             │ │
│  │  CLI / TUI / Future GUI                                                    │ │
│  │  Human-readable output • Dignity-first language • Adaptive verbosity       │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                     ▲                                            │
│                                     │                                            │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                        LAYER 3: HUMAN RENDER                               │ │
│  │  Natural language generation • State-aware verbosity • No clinical terms   │ │
│  │  Transforms structured data → human-friendly output                        │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                     ▲                                            │
│                                     │                                            │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                        LAYER 2: OTTO CORE                                  │ │
│  │  JSON-RPC Protocol • Cognitive Engine • State Management • Protection      │ │
│  │  The brain of OTTO - deterministic routing, safety gating, convergence     │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                     ▲                                            │
│                                     │                                            │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                        LAYER 1: AGENT KERNEL                               │ │
│  │  Binary Protocol (MessagePack) • Agent ↔ Agent Communication               │ │
│  │  Maximum speed • No human rendering overhead • Typed messages              │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                     ▲                                            │
│                                     │                                            │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                        LAYER 0: PERSISTENCE                                │ │
│  │  USD State Files • Encrypted Storage • Session Continuity                  │ │
│  │  ~/.otto/ directory structure • Atomic writes • Backup on modify           │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Directory Structure

```
~/.otto/
├── profile.usda              # Base personality (from intake)
├── calibration.usda          # Learned overrides (OTTO populates)
├── state/
│   ├── session.json          # Current session state
│   ├── cognitive.json        # Cognitive state (37 fields)
│   └── checkpoints/          # Recovery checkpoints
├── knowledge/
│   ├── personal.usda         # Personal knowledge prims
│   └── contexts/             # Domain-specific knowledge
├── sessions/
│   ├── current/              # Active session data
│   └── archive/              # Past session summaries
├── agents/
│   ├── registry.json         # Registered agent types
│   └── state/                # Per-agent state
├── config/
│   ├── otto.yaml             # User preferences
│   ├── integrations.yaml     # External service config
│   └── privacy.yaml          # Privacy settings
├── logs/
│   ├── otto.log              # Main log (local only)
│   └── protection.log        # Protection event log
└── backup/
    └── [timestamped backups]
```

### 2.3 Component Map

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            OTTO OS COMPONENTS                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  COGNITIVE ENGINE (from Orchestra)          PERSONALITY SYSTEM                  │
│  ├── prism_detector.py                      ├── intake/                         │
│  ├── expert_router.py                       │   ├── game.py                     │
│  ├── parameter_locker.py                    │   ├── scenarios.py                │
│  ├── convergence_tracker.py                 │   └── profile_writer.py           │
│  ├── cognitive_state.py                     ├── profile_loader.py               │
│  └── cognitive_orchestrator.py              └── calibration_engine.py           │
│                                                                                  │
│  PROTECTION SYSTEM                          AGENT KERNEL                        │
│  ├── overuse_detector.py                    ├── protocol.py                     │
│  ├── boundary_enforcer.py                   ├── message_types.py                │
│  ├── recovery_suggester.py                  ├── agent_registry.py               │
│  └── pattern_learner.py                     └── coordinator.py                  │
│                                                                                  │
│  COMMUNICATION LAYERS                       KNOWLEDGE LAYER                     │
│  ├── layer0_binary.py                       ├── knowledge_store.py              │
│  ├── layer1_jsonrpc.py                      ├── context_manager.py              │
│  ├── layer2_render.py                       └── memory_retrieval.py             │
│  └── layer3_interface.py                                                        │
│                                                                                  │
│  INTEGRATION LAYER                          CLI / TUI                           │
│  ├── calendar/                              ├── cli/main.py                     │
│  ├── notifications/                         ├── cli/status.py                   │
│  └── external_apis/                         └── tui/dashboard.py                │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Core Systems

### 3.1 System Registry

| System | Priority | Status | Dependencies |
|--------|----------|--------|--------------|
| Cognitive Engine | P0 | ✅ Complete (inherited from Orchestra) | None |
| Personality System | P0 | ✅ Complete (intake game + profile loading) | Cognitive Engine |
| Protection System | P0 | ✅ Complete (overuse detection, protection engine, calibration learning) | Cognitive Engine, Personality |
| Communication Protocol | P1 | ✅ Complete (Layer 0 binary, Layer 1 JSON-RPC, Layer 2 render) | None |
| Agent Kernel | P1 | 🟡 Inherited, needs adaptation | Communication Protocol |
| Knowledge Layer | P2 | ✅ Complete (USDA prims, personal knowledge, unified search) | Persistence |
| Integration Layer | P3 | 🟡 Framework complete (adapters for WebDAV, S3) | All core systems |
| Privacy/Encryption | P1 | ✅ Complete (E2E encryption for cloud sync) | Persistence |
| Cloud Sync | P2 | ✅ Complete (WebDAV, S3, E2E encrypted) | Privacy/Encryption |

### 3.2 System Interactions

```
                                    USER INPUT
                                        │
                                        ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                              OTTO CORE                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
│  │   DETECT    │───▶│   CASCADE   │───▶│    LOCK     │───▶│   EXECUTE   │    │
│  │   (PRISM)   │    │  (Experts)  │    │  (Safety)   │    │  (Generate) │    │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘    │
│        │                  │                  │                  │              │
│        ▼                  ▼                  ▼                  ▼              │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                         STATE MANAGEMENT                                 │  │
│  │  Profile ←→ Calibration ←→ Session ←→ Cognitive State                   │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│        │                                                        │              │
│        ▼                                                        ▼              │
│  ┌─────────────┐                                        ┌─────────────┐       │
│  │ PROTECTION  │                                        │   UPDATE    │       │
│  │   SYSTEM    │◀───────────────────────────────────────│ (RC^+xi)    │       │
│  └─────────────┘                                        └─────────────┘       │
│        │                                                                       │
│        ▼                                                                       │
│  [Protection Decision: Allow / Suggest Break / Gentle Refuse / Firm Stop]     │
│                                                                                │
└───────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
                              AGENT KERNEL (if needed)
                                        │
                                        ▼
                               HUMAN RENDER LAYER
                                        │
                                        ▼
                                  USER OUTPUT
```

---

## 4. Communication Protocol

### 4.1 Three-Layer Stack

```
LAYER 2: HUMAN RENDER
────────────────────────────────────────────────────────────────────────────────
Purpose:    Transform structured data into natural, dignity-first language
Format:     Natural language (Markdown-capable)
When used:  Any output going to a human
Properties: State-aware verbosity, no clinical terms, empathetic tone

Example Output (depleted state):
  "You've been going for a while. Want to wrap up for today?"

Example Output (focused state):
  "Done."
────────────────────────────────────────────────────────────────────────────────

LAYER 1: OTTO CORE (JSON-RPC)
────────────────────────────────────────────────────────────────────────────────
Purpose:    Structured communication for inspection and debugging
Format:     JSON-RPC 2.0
When used:  User ↔ OTTO Core, External integrations, Logging

Example Request:
{
  "jsonrpc": "2.0",
  "method": "otto.process",
  "params": {
    "input": "help me plan my week",
    "context": {"session_id": "abc123"}
  },
  "id": 1
}

Example Response:
{
  "jsonrpc": "2.0",
  "result": {
    "routing": {
      "expert": "scaffolder",
      "reason": "planning_request_detected"
    },
    "protection": {
      "decision": "allow",
      "energy_level": "medium",
      "suggestion": null
    },
    "output": {
      "type": "structured",
      "content": {...}
    }
  },
  "id": 1
}
────────────────────────────────────────────────────────────────────────────────

LAYER 0: AGENT KERNEL (Binary)
────────────────────────────────────────────────────────────────────────────────
Purpose:    Maximum speed agent-to-agent communication
Format:     MessagePack (or Protocol Buffers)
When used:  Agent ↔ Agent, Internal state sync, High-frequency operations

Message Structure:
┌──────────┬──────────┬──────────┬───────────────────────────────┐
│ Version  │ Type     │ Length   │ Payload                       │
│ (1 byte) │ (2 bytes)│ (4 bytes)│ (variable)                    │
└──────────┴──────────┴──────────┴───────────────────────────────┘

Message Types:
  0x0001  STATE_SYNC        Synchronize cognitive state
  0x0002  AGENT_SPAWN       Request agent spawn
  0x0003  AGENT_RESULT      Return agent result
  0x0004  PROTECTION_CHECK  Check if action allowed
  0x0005  KNOWLEDGE_QUERY   Query knowledge store
  0x0006  HEARTBEAT         Agent health check
────────────────────────────────────────────────────────────────────────────────
```

### 4.2 Protocol Principles

1. **Layer isolation**: Each layer only talks to adjacent layers
2. **Upward rendering**: Lower layers never render to human language
3. **Downward structuring**: Higher layers compile to structured formats
4. **State propagation**: Cognitive state flows through all layers
5. **Protection everywhere**: Every layer respects protection decisions

### 4.3 Message Flow Example

```
User types: "help me plan my week"
    │
    ▼
[LAYER 2: Parse natural language input]
    │
    ▼
[LAYER 1: JSON-RPC request to OTTO Core]
{
  "method": "otto.process",
  "params": {"input": "help me plan my week"}
}
    │
    ▼
[OTTO CORE: Cognitive processing]
  - PRISM detects: planning_request, potential_overwhelm
  - Expert routes to: Scaffolder
  - Protection checks: energy=medium, allow with suggestion
    │
    ▼
[LAYER 0: Agent spawn if needed]
MessagePack: [0x0002, agent_type="planner", task="week_planning"]
    │
    ▼
[Agent completes, returns via Layer 0]
MessagePack: [0x0003, result={...}]
    │
    ▼
[LAYER 1: JSON-RPC response]
{
  "result": {
    "plan": [...],
    "protection_note": "Consider doing just Mon-Wed first"
  }
}
    │
    ▼
[LAYER 2: Render to human]
"Here's a start for your week. I've focused on Monday through
Wednesday—want to tackle the full week, or keep it light?"
```

---

## 5. Cognitive Engine

### 5.1 Inherited from Orchestra

The cognitive engine is the production-tested core from Orchestra (796 tests passing).

```
5-PHASE NEXUS PIPELINE
══════════════════════════════════════════════════════════════════════════════

PHASE 1: DETECT
  └─ PRISM signal extraction
  └─ Priority: emotional > mode > domain > task > energy
  └─ Fixed evaluation order (deterministic)

PHASE 2: CASCADE
  └─ Constitutional gates (never violate)
  └─ Safety gates (burnout, energy)
  └─ Expert routing (7 experts, first-match-wins)

PHASE 3: LOCK
  └─ Parameter locking before generation
  └─ MAX3 bounded reflection
  └─ Checksum generation for determinism

PHASE 4: EXECUTE
  └─ Generate with locked parameters
  └─ Respect protection decisions
  └─ Emit execution anchor

PHASE 5: UPDATE
  └─ RC^+xi convergence tracking
  └─ Attractor basin dynamics
  └─ State persistence

══════════════════════════════════════════════════════════════════════════════
```

### 5.2 Adaptations for OTTO OS

| Orchestra Concept | OTTO OS Adaptation |
|-------------------|-------------------|
| Dev-focused signals | Life-focused signals (see 5.3) |
| Code task routing | Life task routing |
| Development experts | Life context experts |
| Session = coding session | Session = any interaction period |
| Claude Code hook | Standalone + integration hooks |

### 5.3 Life Signal Categories

```
EMOTIONAL SIGNALS (Priority 1 - Always routes first)
────────────────────────────────────────────────────────────────────────────────
frustrated       User is frustrated (caps, short responses, negative words)
overwhelmed      User is overwhelmed ("too much", "can't handle", "everything")
anxious          User is anxious ("worried", "nervous", "what if [bad]")
sad              User is sad ("down", "depressed", "not great")
angry            User is angry (profanity, blame, aggression)
excited          User is excited ("amazing", "can't wait", rapid messages)

MODE SIGNALS (Priority 2)
────────────────────────────────────────────────────────────────────────────────
exploring        User is exploring ("what if", "I wonder", "could we")
planning         User is planning ("need to", "want to", "going to")
deciding         User is deciding ("should I", "which", "or")
venting          User is venting (long messages, no questions, emotional content)
reflecting       User is reflecting ("I've been thinking", "looking back")
urgent           User is urgent ("now", "asap", "immediately", "deadline")

DOMAIN SIGNALS (Priority 3 - from active life domains)
────────────────────────────────────────────────────────────────────────────────
work             Professional context triggers
health           Health/wellness triggers
finance          Money/budget triggers
relationships    Social/relationship triggers
creative         Creative project triggers
learning         Education/skill triggers

ENERGY SIGNALS (Priority 4 - feeds into protection, not routing)
────────────────────────────────────────────────────────────────────────────────
tired            "exhausted", "tired", "drained", "wiped"
wired            "can't sleep", "buzzing", "too much energy"
low              "not feeling it", "meh", "whatever"
depleted         "nothing left", "empty", "done"
recovering       "getting better", "coming back", "slowly"

TASK SIGNALS (Priority 5)
────────────────────────────────────────────────────────────────────────────────
remember         "remind me", "don't let me forget", "remember"
find             "where is", "find", "look for"
organize         "sort", "organize", "clean up"
track            "track", "follow up", "check on"
create           "make", "create", "write", "draft"
────────────────────────────────────────────────────────────────────────────────
```

### 5.4 Expert Adaptations

| Expert | Orchestra Context | OTTO OS Context |
|--------|-------------------|-----------------|
| **Validator** | Frustrated developer | Any frustration, distress, or emotional overwhelm |
| **Scaffolder** | Stuck on code | Stuck on any life task, decision paralysis |
| **Restorer** | Post-coding crash | Any depletion, burnout recovery |
| **Refocuser** | Code tangent | Any tangent, conversation drift |
| **Celebrator** | Shipped feature | Any accomplishment, progress milestone |
| **Socratic** | Code exploration | Life exploration, decision support |
| **Direct** | Coding flow | Any flow state, quick interactions |

---

## 6. Personality System

### 6.1 USD Profile Structure

```usda
#usda 1.0

def "OttoProfile" (kind = "personality")
{
    # ═══════════════════════════════════════════════════════════════════════
    # CHRONOTYPE - When you're sharp, when you need protection
    # ═══════════════════════════════════════════════════════════════════════
    string chronotype = "night_owl"           # night_owl | early_bird | variable
    int[] peak_hours = [21, 22, 23, 0, 1]     # Your power hours
    int[] recovery_hours = [6, 7, 8, 9, 10]   # Hours to protect most

    # ═══════════════════════════════════════════════════════════════════════
    # WORK STYLE - How you approach tasks
    # ═══════════════════════════════════════════════════════════════════════
    string work_style = "deep_work"           # deep_work | task_switcher | burst
    int focus_duration_minutes = 90           # Typical focus block
    float context_switch_cost = 0.8           # 0 = easy, 1 = devastating
    int interruption_recovery_minutes = 30    # Time to recover focus
    float notification_sensitivity = 0.9      # Sensitivity to interrupts

    # ═══════════════════════════════════════════════════════════════════════
    # STRESS RESPONSE - How you handle overwhelm
    # ═══════════════════════════════════════════════════════════════════════
    string stress_response = "process"        # avoid | confront | process | deflect
    float overwhelm_threshold = 0.5           # When Scaffolder activates

    # ═══════════════════════════════════════════════════════════════════════
    # PROTECTION PREFERENCES - How OTTO guards your wellbeing
    # ═══════════════════════════════════════════════════════════════════════
    float protection_firmness = 0.5           # 0 = gentle, 1 = firm
    bool allow_override = true                # Can user override protection?
    int override_cooldown_minutes = 30        # Cooldown after override
    string otto_role = "companion"            # guardian | tool | companion
    string intervention_style = "adaptive"    # proactive | minimal | adaptive

    # ═══════════════════════════════════════════════════════════════════════
    # RECOVERY STYLE - What helps when depleted
    # ═══════════════════════════════════════════════════════════════════════
    string preferred_recovery = "solitude"    # solitude | social | activity | rest
    float recovery_social_need = 0.0          # Social component of recovery

    # ═══════════════════════════════════════════════════════════════════════
    # ENERGY PATTERNS - Decision capacity, fatigue
    # ═══════════════════════════════════════════════════════════════════════
    float decision_fatigue_sensitivity = 0.6  # How quickly decisions tire you
    int max_daily_decisions = 25              # Before fatigue sets in
}

def "OttoProfile/Calibration" (
    doc = "Learned overrides from usage patterns"
)
{
    # OTTO populates this layer over time
    # Via LIVRPS, these values override base profile

    # Example learned overrides:
    # float protection_firmness = 0.7    # You ignore gentle nudges
    # int focus_duration_minutes = 120   # You focus longer than you said
}

def "OttoProfile/Session" (
    doc = "Current session state - highest priority"
)
{
    # Real-time state during a session
    string current_energy = "medium"
    string current_mood = "focused"
    int exchanges_this_session = 0
    bool user_requested_no_protection = false
    string[] active_contexts = []
}
```

### 6.2 LIVRPS Resolution

USD composition semantics resolve conflicting values:

```
Priority (highest to lowest):
  1. Session         (current state)
  2. Calibration     (learned patterns)
  3. Base Profile    (from intake)
  4. Defaults        (system defaults)

Example:
  Base Profile:      focus_duration_minutes = 90
  Calibration:       focus_duration_minutes = 120  ← OTTO learned you go longer
  Session:           [not set]

  Resolved value:    120 (Calibration wins over Base)
```

### 6.3 Calibration Learning

OTTO learns profile adjustments from behavior:

```
CALIBRATION TRIGGERS
══════════════════════════════════════════════════════════════════════════════

Override Pattern Learning:
  IF user overrides protection 3+ times with same pattern
  THEN adjust protection_firmness down by 0.1
  AND log: "Learning: You push through [pattern]. Adjusting."

Focus Duration Learning:
  IF user consistently focuses beyond focus_duration_minutes
  THEN update calibration: focus_duration_minutes += 15
  MAX: 180 minutes

Energy Pattern Learning:
  IF user consistently performs well at unexpected hours
  THEN update peak_hours array

Recovery Style Learning:
  IF user recovers faster with [method] than stated preference
  THEN note in calibration for future suggestions

══════════════════════════════════════════════════════════════════════════════
```

---

## 7. Protection Mechanisms

### 7.1 The Protection Philosophy

OTTO's protection is **advocacy, not control**.

- Guardian: "I care about you, so I'm saying no."
- Tool: "You could stop... but here's your answer anyway."
- Companion: "I notice you're tired. What do you want to do?"

The `otto_role` setting from intake determines the baseline, but protection adapts.

### 7.2 Protection Decision Tree

```
                            USER REQUEST
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │   Is this harmful?     │
                    │   (self-harm, crisis)  │
                    └────────────────────────┘
                         │              │
                        YES            NO
                         │              │
                         ▼              ▼
               ┌─────────────┐  ┌────────────────────────┐
               │ STOP        │  │ Check cognitive state  │
               │ + Resources │  │ (energy, burnout, etc) │
               └─────────────┘  └────────────────────────┘
                                         │
                         ┌───────────────┼───────────────┐
                         │               │               │
                       GREEN          YELLOW          RED
                         │               │               │
                         ▼               ▼               ▼
                    ┌─────────┐    ┌─────────┐    ┌─────────┐
                    │ ALLOW   │    │ ALLOW + │    │ Check   │
                    │         │    │ SUGGEST │    │ firmness│
                    └─────────┘    └─────────┘    └─────────┘
                                                       │
                                       ┌───────────────┼───────────────┐
                                       │               │               │
                                    LOW (0-0.3)    MED (0.3-0.7)   HIGH (0.7-1.0)
                                       │               │               │
                                       ▼               ▼               ▼
                                  ┌─────────┐    ┌─────────┐    ┌─────────┐
                                  │ ALLOW + │    │ SUGGEST │    │ BLOCK + │
                                  │ MENTION │    │ BREAK + │    │ REQUIRE │
                                  │         │    │ CONFIRM │    │ OVERRIDE│
                                  └─────────┘    └─────────┘    └─────────┘
```

### 7.3 Protection Actions

| Action | Description | Example |
|--------|-------------|---------|
| **ALLOW** | No intervention | [No protection message] |
| **MENTION** | Brief acknowledgment | "You've been going a while." |
| **SUGGEST** | Offer alternative | "Want to wrap up soon?" |
| **CONFIRM** | Request acknowledgment | "You seem tired. Continue anyway?" |
| **BLOCK** | Prevent action | "Let's pick this up tomorrow." |
| **REQUIRE_OVERRIDE** | Explicit override needed | "Type 'override' to continue." |

### 7.4 Overuse Detection

```
OVERUSE SIGNALS
══════════════════════════════════════════════════════════════════════════════

Time-Based:
  - Session duration > 2 hours → YELLOW
  - Session duration > 4 hours → ORANGE
  - Late night (after 11 PM, if early_bird) → YELLOW
  - Very late (after 2 AM, any chronotype) → ORANGE

Pattern-Based:
  - Same question asked 3+ times → SUGGEST scaffolder
  - Rapid-fire short messages → Check for frustration
  - Long gaps between messages → Check for stuck/distraction
  - Response quality declining → SUGGEST break

Behavioral-Based:
  - Decision avoidance → Reduce options
  - Circular thinking → Gentle interrupt
  - Perfectionism language → "Ship it" nudge
  - Self-criticism → Validate first

Energy-Based:
  - energy=depleted → Block deep work
  - energy=low → Suggest easy wins
  - burnout=RED → Full stop, recovery only

══════════════════════════════════════════════════════════════════════════════
```

### 7.5 Protection Messaging (Dignity-First)

```
NEVER SAY                           INSTEAD SAY
────────────────────────────────    ────────────────────────────────
"Executive dysfunction detected"    "You seem stuck"
"Burnout risk: HIGH"                "You've been going hard"
"Session limit exceeded"            "It's been a while"
"Cognitive load too high"           "That's a lot to hold"
"ADHD symptom detected"             [Never mention, just adapt]
"You should take a break"           "Want to pause here?"
"You're not being productive"       [Never judge productivity]
"You failed to..."                  "That didn't work out"
```

---

## 8. Agent Orchestration

### 8.1 Agent Types

```
CORE AGENTS (Always Available)
══════════════════════════════════════════════════════════════════════════════

Planner Agent
  Purpose:   Break down goals into steps
  Triggers:  "plan", "organize", "schedule", "week", "month"
  Output:    Structured plan with protection-aware timing

Researcher Agent
  Purpose:   Gather information, explore topics
  Triggers:  "find out", "research", "learn about", "what is"
  Output:    Summarized findings with relevance ranking

Memory Agent
  Purpose:   Store and retrieve personal knowledge
  Triggers:  "remember", "remind", "what was", "when did"
  Output:    Retrieved memory or confirmation of storage

Reflection Agent
  Purpose:   Help process thoughts and decisions
  Triggers:  "think about", "decide", "figure out", "understand"
  Output:    Structured reflection, decision framework

DOMAIN AGENTS (Loaded per active context)
══════════════════════════════════════════════════════════════════════════════

Work Agent
  Loaded when: work domain active
  Capabilities: Task management, meeting prep, email drafting

Health Agent
  Loaded when: health domain active
  Capabilities: Habit tracking, exercise suggestions, sleep patterns

Finance Agent
  Loaded when: finance domain active
  Capabilities: Budget tracking, expense categorization, goal progress

Creative Agent
  Loaded when: creative domain active
  Capabilities: Brainstorming, project tracking, inspiration gathering

══════════════════════════════════════════════════════════════════════════════
```

### 8.2 Agent Communication Protocol

```
AGENT SPAWN (0x0002)
────────────────────────────────────────────────────────────────────────────────
Header:
  version:     uint8   = 1
  type:        uint16  = 0x0002
  length:      uint32  = [payload length]

Payload (MessagePack):
  {
    "agent_type": string,        # e.g., "planner"
    "task": string,              # Task description
    "context": {                 # Inherited context
      "session_id": string,
      "cognitive_state": {...},
      "protection_level": string,
      "parent_agent": string | null
    },
    "constraints": {
      "max_turns": int,          # Max agent iterations
      "timeout_ms": int,         # Timeout
      "budget_tokens": int       # Token budget
    }
  }

AGENT RESULT (0x0003)
────────────────────────────────────────────────────────────────────────────────
Payload (MessagePack):
  {
    "agent_id": string,
    "status": "complete" | "partial" | "failed",
    "result": {...},             # Agent-specific result
    "metadata": {
      "turns_used": int,
      "tokens_used": int,
      "duration_ms": int
    }
  }
```

### 8.3 Agent Orchestration Rules

```
RULES (from Orchestra, adapted for OTTO OS)
══════════════════════════════════════════════════════════════════════════════

1. Max parallel agents: 3
   └─ Reason: More overwhelms user with status updates

2. Max chain depth: 3
   └─ Reason: Deep chains lose coherence

3. On burnout >= ORANGE: NO agents
   └─ Reason: Simplify, don't add moving parts

4. Progress ALWAYS visible
   └─ Format: "Working on [task]... (step 2/5)"

5. On agent failure: Report immediately
   └─ Format: "[Agent] couldn't complete [task]. [Alternative]?"

6. State handoff required
   └─ Parent → Child: burnout_level, session_id, protection_level
   └─ Child → Parent: result, errors, insights

7. No silent background work
   └─ User always knows what's happening

══════════════════════════════════════════════════════════════════════════════
```

---

## 9. Knowledge Layer

### 9.1 Knowledge Types

```
KNOWLEDGE CATEGORIES
══════════════════════════════════════════════════════════════════════════════

PERSONAL FACTS (High confidence, user-provided)
  - Name, preferences, relationships
  - Important dates, recurring events
  - Explicit "remember this" items
  - Stored in: ~/.otto/knowledge/personal.usda

LEARNED PATTERNS (Medium confidence, observed)
  - Work habits, energy patterns
  - Communication preferences
  - Stored in: ~/.otto/calibration.usda

CONTEXTUAL KNOWLEDGE (Session-scoped)
  - Current project details
  - Conversation context
  - Stored in: ~/.otto/sessions/current/

EPHEMERAL (Not persisted)
  - Current task state
  - Working memory during agent execution

══════════════════════════════════════════════════════════════════════════════
```

### 9.2 Knowledge Storage (USD Format)

```usda
#usda 1.0

def "PersonalKnowledge" {

    def "Facts" {
        def "Identity" {
            string name = "User's preferred name"
            string[] nicknames = ["nickname1"]
        }

        def "Relationships" {
            def "Partner" {
                string name = "Partner name"
                string relationship = "partner"
            }
        }

        def "Preferences" {
            string coffee_order = "oat milk latte"
            string[] food_restrictions = ["vegetarian"]
        }
    }

    def "Reminders" {
        def "Reminder_001" {
            string content = "Call mom on Sundays"
            string recurrence = "weekly"
            int day_of_week = 0  # Sunday
        }
    }
}
```

### 9.3 Memory Retrieval

```
RETRIEVAL MODES (adapted from Orchestra)
══════════════════════════════════════════════════════════════════════════════

Focused Recall (for specific queries):
  - Deep search, narrow scope
  - High relevance threshold
  - Used when: User asks specific question

Exploratory Recall (for brainstorming):
  - Shallow search, wide scope
  - Lower relevance threshold
  - Used when: User is exploring, "what if"

Recovery Recall (for depleted states):
  - Minimal search, principles only
  - Used when: Burnout >= ORANGE
  - Returns: Only most essential info

══════════════════════════════════════════════════════════════════════════════
```

---

## 10. Privacy & Security

### 10.1 Privacy Principles

1. **Local by default**: All data lives on user's machine
2. **No telemetry**: OTTO doesn't phone home
3. **Encryption at rest**: Sensitive data encrypted with user key
4. **Explicit consent**: Any cloud feature requires opt-in
5. **Data portability**: Export everything, anytime
6. **Right to delete**: One command removes all data

### 10.2 Data Classification

```
PUBLIC (No encryption needed)
────────────────────────────────────────────────────────────────────────────────
  - Configuration preferences
  - UI settings
  - Non-personal system state

PRIVATE (Encrypted at rest)
────────────────────────────────────────────────────────────────────────────────
  - Personality profile
  - Personal knowledge
  - Calibration data
  - Session history

SENSITIVE (Encrypted + additional protection)
────────────────────────────────────────────────────────────────────────────────
  - Health information
  - Financial data
  - Relationship details
  - Crisis event history
```

### 10.3 Encryption Implementation

```
ENCRYPTION SPEC
══════════════════════════════════════════════════════════════════════════════

Algorithm:    AES-256-GCM
Key derivation: Argon2id (from user passphrase)
Key storage:  OS keychain (Keychain/Credential Manager/libsecret)

File encryption:
  ~/.otto/knowledge/personal.usda     → personal.usda.enc
  ~/.otto/calibration.usda            → calibration.usda.enc
  ~/.otto/sessions/                   → sessions.enc/

Decryption:
  On OTTO start, prompt for passphrase (or use OS keychain)
  Files decrypted to memory only
  Never written decrypted to disk

Recovery:
  User maintains recovery key (displayed once at setup)
  No "forgot password" - we can't decrypt your data

══════════════════════════════════════════════════════════════════════════════
```

### 10.4 Cloud Sync (Future, Optional)

```
CLOUD SYNC SPEC (Not in v0.1, planned for v0.3)
══════════════════════════════════════════════════════════════════════════════

Architecture:  End-to-end encrypted
Encryption:    Client-side (OTTO encrypts before upload)
Key:           User-held (server never has key)
Storage:       User's cloud storage (Dropbox/Drive/iCloud)
               OR self-hosted (Nextcloud, etc.)

Sync process:
  1. User enables sync, provides cloud credentials
  2. OTTO encrypts relevant files
  3. Encrypted blobs uploaded to user's cloud
  4. Other devices pull encrypted blobs
  5. Decryption happens locally with user's key

Server never sees:
  - User's passphrase
  - Decrypted content
  - Personal data

══════════════════════════════════════════════════════════════════════════════
```

---

## 11. Integration Layer

### 11.1 Integration Philosophy

OTTO integrations are **information sources, not control mechanisms**. OTTO reads from services to understand your context. OTTO rarely writes to services (and only with explicit action).

### 11.2 Planned Integrations

```
PHASE 1 (v0.2) - Read-only context gathering
══════════════════════════════════════════════════════════════════════════════

Calendar (Google Calendar, Outlook, Apple Calendar)
  - Read: Today's events, upcoming deadlines
  - Purpose: Context for "busy" signals, deadline awareness
  - No write access by default

Local Files
  - Read: Working directory context
  - Purpose: Project awareness, file references
  - No modification without explicit request

PHASE 2 (v0.3) - Bidirectional with consent
══════════════════════════════════════════════════════════════════════════════

Task Managers (Todoist, Things, Reminders)
  - Read: Task lists, due dates
  - Write: Add tasks (with confirmation)
  - Purpose: Task capture, deadline tracking

Notes (Obsidian, Notion, Apple Notes)
  - Read: Search notes for context
  - Write: Create notes (with confirmation)
  - Purpose: Knowledge retrieval, note capture

PHASE 3 (v0.4) - Communication awareness
══════════════════════════════════════════════════════════════════════════════

Email (Gmail, Outlook) - Read-only
  - Read: Unread count, sender names (not content)
  - Purpose: "Inbox load" awareness
  - Privacy: Never reads email content

Messaging (Slack, Discord) - Optional
  - Read: Unread count, channel activity (not content)
  - Purpose: Communication load awareness
  - Privacy: Never reads message content

══════════════════════════════════════════════════════════════════════════════
```

### 11.3 Integration Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          INTEGRATION LAYER                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     ADAPTER INTERFACE                                │    │
│  │  class IntegrationAdapter:                                          │    │
│  │    def get_context() -> Context                                     │    │
│  │    def can_write() -> bool                                          │    │
│  │    def write(action: Action) -> Result                              │    │
│  │    def get_health() -> HealthStatus                                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              │                                               │
│       ┌──────────────────────┼──────────────────────┐                       │
│       │                      │                      │                        │
│       ▼                      ▼                      ▼                        │
│  ┌─────────┐           ┌─────────┐           ┌─────────┐                    │
│  │ Calendar│           │  Tasks  │           │  Notes  │                    │
│  │ Adapter │           │ Adapter │           │ Adapter │                    │
│  └─────────┘           └─────────┘           └─────────┘                    │
│       │                      │                      │                        │
│       ▼                      ▼                      ▼                        │
│  [Google/Outlook]      [Todoist/Things]      [Obsidian/Notion]              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 12. User Experience

### 12.1 CLI Design

```
COMMAND STRUCTURE
══════════════════════════════════════════════════════════════════════════════

otto                          # Start interactive session
otto [message]                # Quick message, respond, exit
otto status                   # Show current state
otto status --detailed        # Full state dump

otto intake                   # Run personality intake
otto intake --reset           # Reset and re-run intake

otto config                   # Open config in editor
otto config set [key] [value] # Set config value
otto config get [key]         # Get config value

otto protect --off            # Disable protection (session only)
otto protect --on             # Re-enable protection
otto protect --status         # Show protection state

otto remember [text]          # Store knowledge
otto forget [query]           # Remove knowledge

otto session save             # Save session state
otto session restore          # Restore last session
otto session clear            # Clear current session

otto export                   # Export all data
otto wipe                     # Delete all OTTO data

══════════════════════════════════════════════════════════════════════════════
```

### 12.2 Interactive Session UX

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ OTTO OS v0.1.0                                          [~45m | GREEN | 📍] │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  OTTO: What are we working on today?                                        │
│                                                                              │
│  > help me plan my week                                                     │
│                                                                              │
│  OTTO: Let's start with the next few days. What's the most important       │
│        thing you need to get done by Wednesday?                             │
│                                                                              │
│  > I have a presentation on Thursday                                        │
│                                                                              │
│  OTTO: Got it. Let's work backward from Thursday.                          │
│                                                                              │
│        Monday:   Outline presentation structure                             │
│        Tuesday:  Draft slides                                               │
│        Wednesday: Review and practice                                       │
│                                                                              │
│        Want to break any of these down further?                             │
│                                                                              │
│  > yeah monday                                                              │
│                                                                              │
│  OTTO: Monday's outline task:                                              │
│                                                                              │
│        1. Brain dump all topics (30 min)                                   │
│        2. Group into sections (20 min)                                     │
│        3. Order sections by flow (15 min)                                  │
│        4. Identify key messages (15 min)                                   │
│                                                                              │
│        That's about 90 minutes total. Schedule it for your peak time?      │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│ Session: 15m | Energy: MEDIUM | Mode: Scaffolder                [Type /help]│
└─────────────────────────────────────────────────────────────────────────────┘
```

### 12.3 TUI Dashboard

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              OTTO OS DASHBOARD                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ╭──────────────────────────────────────────────────────────────────────╮   │
│  │ CURRENT STATE                                                        │   │
│  ├──────────────────────────────────────────────────────────────────────┤   │
│  │ Energy:     ████████████░░░░░░░░  MEDIUM                            │   │
│  │ Burnout:    GREEN                                                    │   │
│  │ Momentum:   building → rolling                                       │   │
│  │ Mode:       Scaffolder                                               │   │
│  │ Session:    45 minutes                                               │   │
│  ╰──────────────────────────────────────────────────────────────────────╯   │
│                                                                              │
│  ╭──────────────────────────────────────────────────────────────────────╮   │
│  │ TODAY                                                                │   │
│  ├──────────────────────────────────────────────────────────────────────┤   │
│  │ ✓ Morning email triage                                              │   │
│  │ ◐ Presentation outline                                              │   │
│  │ ○ Team sync at 3pm                                                  │   │
│  │ ○ Review budget                                                     │   │
│  ╰──────────────────────────────────────────────────────────────────────╯   │
│                                                                              │
│  ╭──────────────────────────────────────────────────────────────────────╮   │
│  │ PROTECTION STATUS                                                    │   │
│  ├──────────────────────────────────────────────────────────────────────┤   │
│  │ Level: NORMAL                                                        │   │
│  │ Next suggestion: ~60 minutes (based on your focus pattern)          │   │
│  │ Overrides today: 0                                                  │   │
│  ╰──────────────────────────────────────────────────────────────────────╯   │
│                                                                              │
│                                                         [q]uit  [r]efresh  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 12.4 Verbosity Levels

| State | Verbosity | Example |
|-------|-----------|---------|
| **depleted** | Minimal | "Done." |
| **low_energy** | Brief | "Here's the summary." |
| **medium** | Standard | Full helpful response |
| **high_energy** | Can expand | Detailed with options |
| **exploring** | Verbose OK | Deep exploration welcome |

---

## 13. Development Phases

### Phase 0: Foundation (COMPLETE)
**Goal**: Establish base from Orchestra

| Task | Status | Notes |
|------|--------|-------|
| Clone Orchestra | ✅ | Renamed to OTTO |
| Rename imports | ✅ | orchestra → otto |
| Verify tests pass | ✅ | 796 passing |
| Write README | ✅ | Vision-aligned |
| Design intake game | ✅ | 8 scenarios |
| Create blueprint | ✅ | This document |

### Phase 1: Core Personal OS (COMPLETE - v0.1.0)
**Goal**: Minimum viable personal OS

| Task | Priority | Dependencies | Status |
|------|----------|--------------|--------|
| Life signal detection | P0 | None | ✅ |
| Human render layer | P0 | None | ✅ |
| Profile loading | P0 | Intake complete | ✅ |
| CLI interactive mode | P0 | Render layer | ✅ |
| Basic protection | P0 | Signal detection | ✅ |
| Session persistence | P1 | None | ✅ |
| USD profile read/write | P1 | Profile loading | ✅ |
| Status command | P1 | State management | ✅ |
| TUI dashboard | P1 | Render layer | ✅ |

**Definition of Done**: ✅ User can run intake, have conversation with protection, save/restore session.

### Phase 2: Communication Protocol (COMPLETE - v0.1.5)
**Goal**: Proper layer separation

| Task | Priority | Dependencies | Status |
|------|----------|--------------|--------|
| Layer 0 binary protocol | P0 | MessagePack dep | ✅ |
| Layer 1 JSON-RPC | P0 | None | ✅ |
| Layer 2 human render | P0 | None | ✅ |
| Message type definitions | P1 | Layer 0 | ✅ |
| Protocol router | P1 | All layers | ✅ |
| Protocol validator | P1 | Message types | ✅ |
| Protocol tests | P1 | All layers | ✅ |

**Definition of Done**: ✅ Clean separation between layers, agents communicate via Layer 0.

### Phase 3: Protection & Calibration (COMPLETE - v0.2.0)
**Goal**: Full protection system

| Task | Priority | Dependencies | Status |
|------|----------|--------------|--------|
| Overuse detection | P0 | Signal detection | ✅ |
| Protection decision tree | P0 | Overuse detection | ✅ |
| Override handling | P0 | Protection tree | ✅ |
| Calibration learning | P1 | Override handling | ✅ |
| Pattern recognition | P1 | Calibration | ✅ |
| Protection messaging | P1 | Human render | ✅ |

**Definition of Done**: ✅ OTTO detects overuse, suggests breaks, learns from overrides.

### Phase 4: Privacy & Encryption (COMPLETE - v0.2.5)
**Goal**: Secure local storage and cloud sync

| Task | Priority | Dependencies | Status |
|------|----------|--------------|--------|
| Encryption library integration | P0 | None | ✅ (cryptography) |
| Key derivation | P0 | Encryption lib | ✅ (Argon2) |
| File encryption | P0 | Key derivation | ✅ (AES-256-GCM) |
| E2E encrypted sync | P1 | Encryption | ✅ |
| Cloud storage adapters | P1 | Encryption | ✅ (WebDAV, S3) |

**Definition of Done**: ✅ All sensitive data encrypted, E2E encrypted cloud sync available.

### Phase 5: Integrations (COMPLETE - v0.3.0)
**Goal**: External context gathering

| Task | Priority | Dependencies | Status |
|------|----------|--------------|--------|
| Integration adapter interface | P0 | None | ✅ |
| Storage adapters (WebDAV, S3) | P0 | Interface | ✅ |
| Calendar adapter (ICalAdapter) | P1 | Interface | ✅ |
| Task manager adapter (JsonTaskAdapter) | P2 | Interface | ✅ |
| Context-aware coordinator | P1 | Adapters | ✅ |
| Notes adapter | P3 | Interface | ✅ (Phase 8) |
| Integration config UI | P2 | Adapters | ✅ (Phase 8) |

**Definition of Done**: ✅ OTTO can read calendar, tasks for context awareness.

### Phase 6: Agent System (COMPLETE - v0.4.0)
**Goal**: Multi-agent orchestration

| Task | Priority | Dependencies | Status |
|------|----------|--------------|--------|
| Agent registry (EXECUTOR_REGISTRY) | P0 | Layer 0 protocol | ✅ |
| Planner agent (PlannerAgent) | P0 | Registry | ✅ |
| Memory agent (MemoryAgent) | P0 | Knowledge layer | ✅ |
| Researcher agent (ResearcherAgent) | P0 | Registry | ✅ |
| Reflection agent (ReflectionAgent) | P0 | Registry | ✅ |
| Agent coordinator (ContextAwareCoordinator) | P0 | All agents | ✅ |
| Agent protocol bridge | P0 | Protocol layer | ✅ |
| Progress visibility (ProgressTracker) | P1 | Coordinator | ✅ |

**Definition of Done**: ✅ Agents can be spawned, coordinated, and visible to user.

### Phase 7: TUI & Polish (COMPLETE - v0.5.0)
**Goal**: Rich terminal experience

| Task | Priority | Dependencies | Status |
|------|----------|--------------|--------|
| TUI dashboard (tui_enhanced.py) | P0 | All core systems | ✅ |
| State visualization (burnout, momentum, energy) | P0 | TUI | ✅ |
| Interactive widgets (keyboard controls) | P1 | TUI | ✅ |
| Theme support (auto/light/dark) | P2 | TUI | ✅ |

**Definition of Done**: ✅ Beautiful, informative TUI dashboard.

### Phase 8: Hardening & Documentation (Target: v0.6.0)
**Goal**: Production readiness

| Task | Priority | Dependencies | Status |
|------|----------|--------------|--------|
| End-to-end integration tests | P0 | All systems | ✅ (15 tests) |
| Notes adapter | P2 | Interface | ✅ (30 tests) |
| Integration config UI | P2 | Adapters | ✅ (15 tests) |
| User documentation | P1 | All phases | ✅ |
| Performance profiling | P2 | All systems | ✅ (15 benchmarks) |

**Definition of Done**: ✅ Production-ready with full documentation and E2E tests.

### Future Phases (v1.0+)
- Mobile companion app
- Voice interface
- Team features (shared contexts)
- Plugin system
- Public API for third-party integrations

---

## 14. Testing Strategy

### 14.1 Test Categories

```
TEST PYRAMID
══════════════════════════════════════════════════════════════════════════════

                           ╱╲
                          ╱  ╲         E2E Tests
                         ╱────╲        (10-20 tests)
                        ╱      ╲       Full user journeys
                       ╱────────╲
                      ╱          ╲     Integration Tests
                     ╱────────────╲    (100-200 tests)
                    ╱              ╲   Component interactions
                   ╱────────────────╲
                  ╱                  ╲  Unit Tests
                 ╱────────────────────╲ (500-800 tests)
                                        Individual functions

══════════════════════════════════════════════════════════════════════════════
```

### 14.2 Test Categories by System

| System | Unit Tests | Integration Tests | E2E Tests |
|--------|------------|-------------------|-----------|
| Cognitive Engine | ✅ Inherited | ✅ Inherited | ✅ |
| Personality System | ✅ Complete | ✅ Complete | ✅ |
| Protection System | ✅ 30 tests | ✅ Complete | ✅ |
| Communication Protocol | ✅ 85 tests | ✅ Complete | - |
| Knowledge Layer | ✅ 34 tests | ✅ Complete | - |
| Cloud Sync | ✅ 158 tests | ✅ Complete | - |
| Agent Orchestration | ✅ Inherited | ✅ Inherited | 🔴 Needed |
| CLI/TUI | ✅ Complete | ✅ Complete | ✅ |

**Total Test Count: ~1991 tests passing**

### 14.3 Critical Test Scenarios

```
PROTECTION TESTS (must pass)
══════════════════════════════════════════════════════════════════════════════

test_depleted_blocks_deep_work
  Given: User is depleted
  When:  User requests complex task
  Then:  OTTO suggests simpler alternative

test_override_is_respected
  Given: User is warned about overuse
  When:  User explicitly overrides
  Then:  OTTO allows but logs override

test_protection_firmness_calibration
  Given: User overrides 3+ times with same pattern
  When:  Same protection trigger occurs
  Then:  Protection is less firm

test_crisis_language_detected
  Given: User uses crisis language
  When:  Processing message
  Then:  OTTO stops and offers resources

DETERMINISM TESTS (must pass)
══════════════════════════════════════════════════════════════════════════════

test_same_input_same_routing
  Given: Fixed cognitive state
  When:  Same input processed twice
  Then:  Same expert routing both times

test_checksum_reproducible
  Given: Fixed input and state
  When:  Checksum generated twice
  Then:  Identical checksums

══════════════════════════════════════════════════════════════════════════════
```

### 14.4 Test Commands

```bash
# All tests
python -m pytest tests/ -v

# By category
python -m pytest tests/ -m unit
python -m pytest tests/ -m integration
python -m pytest tests/ -m e2e

# By system
python -m pytest tests/test_protection*.py -v
python -m pytest tests/test_personality*.py -v
python -m pytest tests/test_protocol*.py -v

# Coverage
python -m pytest tests/ --cov=src/otto --cov-report=html

# Determinism tests only
python -m pytest tests/ -m determinism
```

---

## 15. Success Metrics

### 15.1 User-Centric Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Session duration** | Healthy distribution | Not always maxed out |
| **Break acceptance** | > 50% | User takes suggested breaks |
| **Override frequency** | Declining over time | OTTO learns patterns |
| **Return rate** | > 70% | Users come back |
| **Session continuity** | > 80% | Users resume where they left |

### 15.2 Technical Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Response latency** | < 500ms | Time to first response |
| **Test coverage** | > 85% | Lines covered |
| **Test pass rate** | 100% | No flaky tests |
| **Determinism** | 100% | Same input = same output |
| **State persistence** | 100% | No lost sessions |

### 15.3 Anti-Metrics (What We Don't Optimize)

| Anti-Metric | Why |
|-------------|-----|
| Total usage time | More isn't better |
| Messages per session | Efficiency varies |
| Features used | Simplicity is fine |
| Daily active use | Taking breaks is good |

---

## 16. Open Questions

### 16.1 Design Questions

| Question | Options | Decision Status |
|----------|---------|-----------------|
| How firm should default protection be? | Gentle / Medium / Firm | **Medium** (adaptive) |
| Should intake be required? | Required / Optional / Skip-able | **Required first run** |
| Multi-device sync timing? | v0.3 / v0.5 / v1.0 | TBD |
| Voice interface priority? | High / Medium / Low | Low (text-first) |

### 16.2 Technical Questions

| Question | Options | Decision Status |
|----------|---------|-----------------|
| Binary protocol format? | MessagePack / Protobuf / Custom | **MessagePack** (simpler) |
| Encryption library? | cryptography / PyNaCl / age | TBD |
| TUI framework? | Textual / Rich / urwid | **Textual** (modern) |
| Agent execution model? | Async / Thread pool / Process | TBD |

### 16.3 Questions to Resolve During Development

- How to handle multiple simultaneous OTTO instances?
- What's the migration path for profile schema changes?
- How to handle integration auth token refresh?
- What telemetry (if any) is acceptable? (Current answer: none)

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **OTTO** | The conductor interface for the OS |
| **Cognitive Substrate** | USD-based state representation system |
| **LIVRPS** | USD composition priority (Local > Inherits > Variants > References > Payloads > Specializes) |
| **Protection** | System of detecting and responding to overuse |
| **Calibration** | Learned adjustments to personality profile |
| **Intake** | Initial personality assessment game |
| **Expert** | One of 7 intervention modes (Validator, Scaffolder, etc.) |
| **Layer 0/1/2** | Communication protocol layers (binary/JSON-RPC/human) |

---

## Appendix B: File Manifest

```
OTTO_OS/
├── BLUEPRINT.md              # This document (ground truth)
├── PHILOSOPHY.md             # The Soul - why we build
├── STRATEGY.md               # The Nervous System - technical foundation
├── README.md                 # Public-facing README
├── pyproject.toml            # Package configuration
├── src/otto/
│   ├── __init__.py
│   ├── cognitive_orchestrator.py   # 5-phase pipeline
│   ├── cognitive_state.py          # State management
│   ├── prism_detector.py           # Signal detection
│   ├── expert_router.py            # Expert routing
│   ├── parameter_locker.py         # Safety gating
│   ├── convergence_tracker.py      # RC^+xi tracking
│   ├── intake/                     # ✅ COMPLETE
│   │   ├── __init__.py
│   │   ├── game.py                 # Hybrid CLI game
│   │   ├── scenarios.py            # 8 intake scenarios
│   │   └── profile_writer.py       # USD output
│   ├── protection/                 # ✅ COMPLETE
│   │   ├── __init__.py
│   │   ├── overuse_detector.py     # Overuse signal detection
│   │   ├── protection_engine.py    # Protection decision tree
│   │   └── calibration.py          # Calibration learning engine
│   ├── protocol/                   # ✅ COMPLETE
│   │   ├── __init__.py
│   │   ├── message_types.py        # Message type definitions
│   │   ├── layer0_binary.py        # MessagePack binary protocol
│   │   ├── layer1_jsonrpc.py       # JSON-RPC 2.0 layer
│   │   ├── protocol_router.py      # Format detection & routing
│   │   └── validator.py            # Message validation
│   ├── render/                     # ✅ COMPLETE
│   │   ├── __init__.py
│   │   └── human_render.py         # Dignity-first output rendering
│   ├── substrate/                  # ✅ COMPLETE
│   │   ├── knowledge/
│   │   │   ├── __init__.py
│   │   │   ├── retriever.py        # O(1) knowledge retrieval
│   │   │   ├── schemas.py          # KnowledgePrim, RetrievalResult
│   │   │   ├── personal_store.py   # Personal knowledge (remember cmd)
│   │   │   ├── unified_search.py   # Combined search
│   │   │   └── prims/
│   │   │       └── otto_os_prims.usda  # 20 OTTO OS knowledge prims
│   │   ├── ewm/                    # External Working Memory
│   │   └── hardening/              # State management
│   ├── sync/                       # ✅ COMPLETE
│   │   ├── __init__.py
│   │   ├── sync_engine.py          # Core sync orchestration
│   │   ├── storage_adapter.py      # Abstract adapter interface
│   │   ├── local_adapter.py        # Local filesystem (testing)
│   │   ├── webdav_adapter.py       # WebDAV (Nextcloud, ownCloud)
│   │   ├── s3_adapter.py           # S3 (AWS, MinIO)
│   │   └── crypto.py               # E2E encryption (AES-256-GCM)
│   └── cli/                        # ✅ COMPLETE
│       ├── __init__.py
│       ├── main.py                 # CLI entry point
│       ├── status.py               # Status command
│       ├── interactive.py          # Interactive mode
│       └── tui.py                  # TUI dashboard
└── tests/                          # ~1991 tests
    ├── test_intake.py
    ├── test_protection.py
    ├── test_calibration.py         # 30 tests
    ├── test_protocol_*.py          # 85 tests
    ├── test_personal_knowledge.py  # 34 tests
    ├── test_sync_*.py              # 158 tests
    ├── test_e2e_full_stack.py      # 15 tests (Phase 8)
    └── [inherited tests]
```

---

**End of Blueprint**

*This document is the ground truth. When in doubt, consult the blueprint.*
*Code follows spec. If code diverges, it's a bug.*
