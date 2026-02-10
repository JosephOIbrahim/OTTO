# OTTO v5.0 — Cognitive Commitment Engine

## Complete Instruction Set for Claude Code (Opus 4.6 + Agent SDK)

**Version:** 5.0.0
**Date:** February 10, 2026
**Author:** Joe Ibrahim — Creative Director / Systems Architect
**Builder:** Claude Code (Opus 4.6) via Agent SDK
**Platform:** Windows (WSL2) — Python 3.11+

---

## POSITIONING

> **"Manage the noise without falling into it."**

OTTO detects the signals buried in your messages — commitments, actions, deadlines — and follows up so you don't have to hold them in your head. But unlike every other reminder tool, OTTO is constitutionally prevented from becoming noise itself. When you're depleted, it goes quiet. When you're overwhelmed, it reduces options. When you're in flow, it stays out of the way.

This is the difference between a reminder app and a cognitive engine.

---

## WHAT EXISTS (v4.0 — Working Today)

825 lines. 93 tests. 8 files. The commitment loop works end-to-end:

```
MESSAGE IN → DETECT → STORE → WAIT → FOLLOW UP → UPDATE
(WhatsApp)   (Claude)  (SQLite) (???)  (template)  (store)
```

**What v4.0 proved:** The Executor mode works. It just doesn't know it's the Executor mode.

**What v4.0 is missing:** The `???` in WAIT. No scheduler. No outbound. No cognitive awareness. OTTO is a ledger that you have to remember to check — which defeats the purpose for the exact users it's designed to serve.

---

## THE ARCHITECTURAL INSIGHT

v4.0 didn't strip the cognitive architecture. It accidentally implemented one mode (Executor) without the framework that makes it intelligent. The existing code maps directly:

| v4.0 File | Is Actually | Cognitive Role |
|-----------|-------------|----------------|
| `detector.py` | PRISM signal detection (commitment type) | Classifies input signals |
| `store.py` | Persistence layer | State storage |
| `nudge.py` | Executor mode's follow-up behavior | One mode's output |
| `watcher.py` | Transport layer (WhatsApp) | Input surface |
| `cli.py` | Transport layer (terminal) | Input/output surface |
| `models.py` | Cognitive state (commitment subset) | Domain model |

**The merge is not a rewrite. It's naming what's already there and adding the layers that make OTTO more than a reminder bot.**

---

## THE COGNITIVE ARCHITECTURE (What We're Building)

```
┌─────────────────────────────────────────────────────────────┐
│                    TRANSPORT LAYER                           │
│  WhatsApp (watcher.py) | CLI (cli.py) | [future: Telegram]  │
├─────────────────────────────────────────────────────────────┤
│                 CONSTITUTIONAL LAYER                         │
│  Safety floors | Energy gates | "Don't become noise"         │
│  ⚠️  This layer can SUPPRESS output from any mode below     │
├─────────────────────────────────────────────────────────────┤
│               PRISM SIGNAL DETECTION                         │
│  commitment | action_required | meeting_proposed             │
│  frustrated | overwhelmed | depleted | stuck | exploring     │
│  focused | burst_detected | crash_zone | spiral              │
├─────────────────────────────────────────────────────────────┤
│                  NEXUS ROUTING                               │
│  ACTIVATE → WEIGHT → BOUND → SELECT → EXECUTE               │
│  Same signals + same state = same routing (always)           │
├─────────────────────────────────────────────────────────────┤
│                 SPECIALIST MODES (7)                          │
│  Protector(10%) | Decomposer(5%) | Restorer(5%)             │
│  Redirector | Acknowledger | Guide | Executor                │
├─────────────────────────────────────────────────────────────┤
│              ENERGY STATE MANAGER                            │
│  Burnout level (GREEN→YELLOW→ORANGE→RED)                     │
│  Momentum phase (cold_start→building→rolling→peak→crashed)   │
│  Energy level (high | medium | low | depleted)               │
├─────────────────────────────────────────────────────────────┤
│                  PERSISTENCE                                 │
│  SQLite: commitments + cognitive_state + trails              │
│  Pheromone trails: reinforce what works, decay what doesn't  │
├─────────────────────────────────────────────────────────────┤
│               PHEROMONE TRAILS                               │
│  deposit(action, strength) → follow(context) → decay(half_life) │
│  No central coordinator. Patterns emerge from usage.         │
└─────────────────────────────────────────────────────────────┘
```

**The constitutional layer sits ABOVE the modes.** This is the key architectural decision. OTTO can detect a commitment (PRISM), route it to the Executor (NEXUS), generate a nudge (Executor mode), and then the constitutional layer SUPPRESSES the nudge because the user is in RED burnout. That suppression is what makes OTTO different from every other tool. That's "manage the noise without falling into it."

---

## CONSTITUTIONAL PRINCIPLES (IMMUTABLE)

These are frozen. They cannot be overridden at runtime. They are not configuration.

1. **Safety First** — Protector mode has a 10% floor. It always runs. It can suppress any other mode's output.
2. **Don't Become Noise** — OTTO monitors its own output frequency. If nudges aren't leading to completions, it backs off. It never escalates into nagging.
3. **User Knows Best** — "Park it" is a first-class action, not a failure. No guilt. No judgment. No "are you sure?"
4. **Ship Over Perfect** — First draft privilege. Ugly code that works beats beautiful code that doesn't.
5. **Rest Is Productive** — The Restorer mode can grant permission to stop. This is not a suggestion; it's an authority.
6. **One At A Time** — When overwhelmed, reduce to one choice. Not three. One.
7. **Write It Down** — If OTTO detects it, OTTO stores it. The user's memory is not a reliable system.
8. **Dignity Always** — No clinical labels. No "ADHD mode." No "disability accommodation." Just a system that works the way brains actually work.
9. **Privacy Is Sovereignty** — Cognitive data stays local. No cloud sync. No analytics. No "improving our service."
10. **Variable Attention Is Architecture** — Fluctuating attention is the native state, not the exception. Design for it.

---

## SPECIALIST MODES

| Mode | Role | Safety Floor | Triggers | v4.0 Equivalent |
|------|------|-------------|----------|-----------------|
| **Protector** | Emotional safety, crisis intervention, suppress harmful nudges | **10% (immutable)** | RED burnout, caps, negativity, crisis, nudge-fatigue | *Not implemented* |
| **Decomposer** | Break overwhelming tasks into steps | **5% (immutable)** | "too much", overwhelmed, stuck | *Not implemented* |
| **Restorer** | Permission to rest, energy management | **5% (immutable)** | depleted, ORANGE burnout, low energy | *Not implemented* |
| **Redirector** | Gentle refocus from tangents | 0% | topic drift, tangent budget exceeded | *Not implemented* |
| **Acknowledger** | Validate emotions and progress | 0% | frustration, milestone reached, completion | *Not implemented* |
| **Guide** | Socratic exploration, what-if threads | 0% | exploring, "what if", curiosity | *Not implemented* |
| **Executor** | Direct action, commitment tracking, follow-up | 0% | focused, clear task, commitment detected | **`detector.py` + `nudge.py` + `store.py`** |

**Safety floors are constitutional.** Protector at 10%, Decomposer at 5%, Restorer at 5% means 20% of OTTO's attention is always on user safety. This is not adjustable.

---

## NEXUS ROUTING (5 Phases, Deterministic)

```python
# Phase 1: ACTIVATE — Which modes respond to this input?
activated = [mode for mode in modes if mode.responds_to(signals)]

# Phase 2: WEIGHT — Score each activated mode (0.0–1.0)
weights = {mode: mode.weight(signals, state) for mode in activated}

# Phase 3: BOUND — Apply safety floors
weights["protector"] = max(weights.get("protector", 0), 0.10)
weights["decomposer"] = max(weights.get("decomposer", 0), 0.05)
weights["restorer"] = max(weights.get("restorer", 0), 0.05)

# Phase 4: SELECT — Primary mode + supporting team
primary = max(weights, key=weights.get)
support = [m for m in weights if m != primary and weights[m] > 0.05]

# Phase 5: EXECUTE — Route to selected modes
response = primary.execute(input, state)
for mode in support:
    response = mode.augment(response, state)
```

**Invariant:** Same signals + same state = same routing. Always. Application-level determinism: no randomness, no batch-size dependence, no floating-point order ambiguity. Presentation layer variation is intentional and documented.

---

## PRISM SIGNAL DETECTION

PRISM classifies input into cognitive signals. In v4.0, `detector.py` detects ONE signal type: `commitment_detected`. PRISM extends this to detect ALL signal types.

```python
class SignalType(Enum):
    # Action signals (v4.0 has this one)
    COMMITMENT_DETECTED = "commitment_detected"
    ACTION_REQUIRED = "action_required"
    MEETING_PROPOSED = "meeting_proposed"
    DEADLINE_MENTIONED = "deadline_mentioned"

    # Cognitive state signals (new)
    FRUSTRATED = "frustrated"
    OVERWHELMED = "overwhelmed"
    DEPLETED = "depleted"
    STUCK = "stuck"
    EXPLORING = "exploring"
    FOCUSED = "focused"

    # Alert signals (new)
    BURST_DETECTED = "burst_detected"
    CRASH_ZONE = "crash_zone"
    SPIRAL = "spiral"
    NUDGE_FATIGUE = "nudge_fatigue"
```

**Key decision:** Action signals (commitment, meeting, deadline) are detected from MESSAGE content. Cognitive state signals (frustrated, depleted) are detected from USER BEHAVIOR patterns (response time, typo rate, message length changes, explicit statements). These are different detection paths.

---

## ENERGY STATE MANAGER

```python
@dataclass
class CognitiveState:
    burnout: Literal["GREEN", "YELLOW", "ORANGE", "RED"] = "GREEN"
    momentum: Literal["cold_start", "building", "rolling", "peak", "crashed"] = "cold_start"
    energy: Literal["high", "medium", "low", "depleted"] = "medium"
    last_interaction: datetime | None = None
    nudges_sent_today: int = 0
    nudges_completed_today: int = 0
    last_nudge_at: datetime | None = None
    suppressed_count: int = 0  # nudges constitutional layer blocked

    @property
    def nudge_effectiveness(self) -> float:
        """If nudges aren't leading to completions, back off."""
        if self.nudges_sent_today == 0:
            return 1.0
        return self.nudges_completed_today / self.nudges_sent_today

    @property
    def should_suppress_nudge(self) -> bool:
        """Constitutional check: should we suppress outbound?"""
        if self.burnout == "RED":
            return True  # Never nudge in RED
        if self.burnout == "ORANGE" and self.energy in ("low", "depleted"):
            return True  # Don't pile on
        if self.nudge_effectiveness < 0.1 and self.nudges_sent_today > 3:
            return True  # Nudges aren't helping. Back off.
        return False
```

**This is the "without falling into it" in code.** The constitutional layer tracks its own effectiveness and self-suppresses when it's not helping.

---

## PHEROMONE TRAILS

```python
class Trail:
    """Stigmergic learning. No central coordinator."""

    def deposit(self, action: str, context: dict, strength: float = 1.0):
        """Record: this action worked in this context."""

    def follow(self, context: dict) -> list[TrailEntry]:
        """What has worked before in similar contexts?"""

    def decay(self, half_life_hours: float = 168):
        """Unused trails weaken. Kahan summation for numerical stability."""
```

**Example:** User gets nudged about commitment X, marks it done within 2 hours → trail deposits `{signal: "commitment_nudge", response: "completed", latency: "fast", strength: 1.0}`. Next time a similar commitment is detected, OTTO knows nudging works for this type. Conversely, if nudges about meeting proposals are consistently ignored → trail decays → OTTO backs off on meeting nudges.

---

## CLAUDE AGENT SDK ARCHITECTURE

The Agent SDK maps naturally to OTTO's cognitive architecture:

```python
from claude_agent_sdk import (
    tool, create_sdk_mcp_server,
    ClaudeAgentOptions, ClaudeSDKClient,
    HookMatcher, HookContext
)

# === CONSTITUTIONAL LAYER AS HOOKS ===
# Hooks run BEFORE tool execution — perfect for safety gating

async def constitutional_gate(
    input_data: dict, tool_use_id: str | None, context: HookContext
) -> dict:
    """Constitutional layer: suppress actions that violate principles."""
    state = await get_cognitive_state()

    if state.should_suppress_nudge and input_data.get("tool_name") == "send_nudge":
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Nudge suppressed: burnout={state.burnout}, energy={state.energy}"
            }
        }
    return {}


# === SPECIALIST MODES AS MCP TOOLS ===
# Each mode is a tool the orchestrator can invoke

@tool("protector_check", "Check if user needs emotional safety intervention", {
    "signals": list, "state": dict
})
async def protector_check(args):
    """Protector mode: always-on safety check."""
    signals = args["signals"]
    state = args["state"]

    if any(s in signals for s in ["frustrated", "crash_zone", "spiral"]):
        return {"content": [{"type": "text", "text": json.dumps({
            "action": "intervene",
            "message": "I'm noticing some strain. Want to pause, or should I simplify what we're working on?",
            "suppress_other_modes": True
        })}]}
    return {"content": [{"type": "text", "text": json.dumps({"action": "pass"})}]}


@tool("executor_nudge", "Generate and optionally send a commitment follow-up", {
    "commitment_id": str, "channel": str
})
async def executor_nudge(args):
    """Executor mode: the v4.0 nudge system, now mode-aware."""
    # This wraps the existing nudge.py logic
    commitment = store.get(args["commitment_id"])
    nudge_text = generate_nudge(commitment)  # existing template system
    return {"content": [{"type": "text", "text": json.dumps({
        "action": "nudge",
        "text": nudge_text,
        "channel": args["channel"],
        "commitment_id": args["commitment_id"]
    })}]}


@tool("restorer_check", "Check if user needs permission to rest", {
    "state": dict
})
async def restorer_check(args):
    """Restorer mode: energy management and rest permission."""
    state = args["state"]
    if state.get("energy") in ("low", "depleted"):
        return {"content": [{"type": "text", "text": json.dumps({
            "action": "grant_permission",
            "message": "Permission granted: rest is productive. Your commitments will be here tomorrow.",
            "suppress_nudges_hours": 12
        })}]}
    return {"content": [{"type": "text", "text": json.dumps({"action": "pass"})}]}


@tool("decomposer_break", "Break an overwhelming commitment into steps", {
    "commitment_id": str, "context": str
})
async def decomposer_break(args):
    """Decomposer mode: make big things small."""
    # Uses Claude to break commitment into micro-steps
    pass


# === NEXUS ROUTER AS ORCHESTRATOR AGENT ===

otto_tools = create_sdk_mcp_server(
    name="otto-cognitive",
    version="5.0.0",
    tools=[protector_check, executor_nudge, restorer_check, decomposer_break]
)

ORCHESTRATOR_PROMPT = """You are OTTO's cognitive router (NEXUS).

Given user signals and cognitive state, route to the appropriate specialist mode.

ROUTING RULES (deterministic, first-match-wins):
1. If signals contain [frustrated, crash_zone, spiral, RED] → protector_check FIRST
2. If state.energy is [depleted, low] and state.burnout is [ORANGE, RED] → restorer_check
3. If signals contain [overwhelmed, stuck] → decomposer_break
4. If signals contain [commitment_detected, action_required] → executor_nudge
5. Default → pass through (no mode activation)

SAFETY FLOORS (always check, even if not primary):
- protector_check: ALWAYS run if confidence > 0 (10% floor)
- restorer_check: ALWAYS run if energy < medium (5% floor)
- decomposer_break: ALWAYS run if overwhelmed signals present (5% floor)

CONSTITUTIONAL OVERRIDE:
If the constitutional hook denies an action, respect it. Do not retry.
Do not explain the denial to the user in clinical terms. Just be quiet.
"""

options = ClaudeAgentOptions(
    model="claude-opus-4-6",
    system_prompt=ORCHESTRATOR_PROMPT,
    mcp_servers={"otto": otto_tools},
    allowed_tools=[
        "mcp__otto__protector_check",
        "mcp__otto__executor_nudge",
        "mcp__otto__restorer_check",
        "mcp__otto__decomposer_break",
    ],
    pre_tool_use_hook=constitutional_gate
)
```

**Key insight:** The Agent SDK's hook system IS the constitutional layer. Hooks run before tool execution. Safety gating is literally built into the framework.

---

## FILE STRUCTURE (v5.0)

```
otto/
├── CLAUDE.md                      # THIS FILE
├── README.md                      # Three sentences + setup
├── pyproject.toml                 # Dependencies
├── src/otto/
│   ├── __init__.py
│   ├── __main__.py
│   │
│   ├── # === COGNITIVE CORE (NEW) ===
│   ├── constitutional.py          # Safety floors, energy gates, self-suppression
│   ├── signals.py                 # PRISM: wraps detector.py + adds cognitive signals
│   ├── router.py                  # NEXUS: deterministic mode routing
│   ├── state.py                   # CognitiveState dataclass + persistence
│   ├── trails.py                  # Pheromone trail system (SQLite-backed)
│   │
│   ├── # === SPECIALIST MODES (NEW) ===
│   ├── modes/
│   │   ├── __init__.py
│   │   ├── base.py                # Mode protocol (responds_to, weight, execute, augment)
│   │   ├── protector.py           # Safety, crisis, nudge suppression
│   │   ├── executor.py            # Commitment loop (WRAPS existing nudge.py + store.py)
│   │   ├── restorer.py            # Energy management, rest permission
│   │   ├── decomposer.py          # Task breakdown
│   │   ├── redirector.py          # Tangent management
│   │   ├── acknowledger.py        # Validation, celebration
│   │   └── guide.py               # Socratic exploration
│   │
│   ├── # === TRANSPORT (REFACTORED) ===
│   ├── transport/
│   │   ├── __init__.py
│   │   ├── base.py                # Transport protocol (receive, send)
│   │   ├── whatsapp.py            # Existing watcher.py, refactored
│   │   └── cli_transport.py       # CLI as a transport surface
│   │
│   ├── # === AGENT SDK INTEGRATION (NEW) ===
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── orchestrator.py        # NEXUS as Agent SDK orchestrator
│   │   ├── tools.py               # Modes as MCP tools
│   │   └── hooks.py               # Constitutional layer as hooks
│   │
│   ├── # === EXISTING v4.0 (PRESERVED) ===
│   ├── detector.py                # KEPT: commitment detection (becomes PRISM input)
│   ├── store.py                   # KEPT: SQLite CRUD (extended with state + trails tables)
│   ├── nudge.py                   # KEPT: templates (wrapped by Executor mode)
│   ├── models.py                  # KEPT: Commitment dataclass (extended)
│   ├── cli.py                     # KEPT: Click commands (extended with `otto energy`, `otto snooze`)
│   └── log.py                     # NEW: structured logging (replaces print())
│
├── tests/
│   ├── # === EXISTING v4.0 TESTS (ALL PRESERVED) ===
│   ├── conftest.py
│   ├── test_models.py             # 4 tests
│   ├── test_detector.py           # 8 + 4 integration
│   ├── test_store.py              # 23 tests
│   ├── test_nudge.py              # 19 tests
│   ├── test_cli.py                # 20 tests
│   ├── test_watcher.py            # 13 tests
│   │
│   ├── # === NEW COGNITIVE TESTS ===
│   ├── test_constitutional.py     # Safety floor enforcement
│   ├── test_signals.py            # PRISM signal classification
│   ├── test_router.py             # NEXUS determinism (same input → same output)
│   ├── test_state.py              # CognitiveState transitions
│   ├── test_trails.py             # Deposit, follow, decay, Kahan summation
│   ├── test_modes/
│   │   ├── test_protector.py      # Suppression, crisis intervention
│   │   ├── test_executor.py       # Wraps existing nudge tests
│   │   ├── test_restorer.py       # Rest permission, energy gates
│   │   └── test_decomposer.py     # Task breakdown
│   └── test_agent/
│       ├── test_orchestrator.py   # End-to-end routing
│       └── test_hooks.py          # Constitutional hook enforcement
```

**Principle: WRAP, DON'T REWRITE.** Every existing v4.0 file stays. New code wraps and extends. The 93 existing tests must continue to pass at every phase.

---

# BUILD PHASES

## Phase 0: Foundation (No Behavior Change)

> **Goal:** Add the cognitive skeleton without changing any existing behavior. All 93 tests still pass.

### 0.1: Structured Logging

```
FILES: Create src/otto/log.py
MODIFY: detector.py, watcher.py, nudge.py (replace print() with logger)
TEST: test_detector.py gains caplog assertion
DONE: All 93 tests pass + print() only in CLI user-facing output
```

### 0.2: Energy State

```
FILES: Create src/otto/state.py
MODIFY: store.py (add cognitive_state table)
MODIFY: models.py (add CognitiveState dataclass)
MODIFY: cli.py (add `otto energy [high|medium|low|depleted]` command)
TEST: test_state.py — transitions, persistence, defaults
DONE: `otto energy low` sets state. `otto energy` shows current. 93+ tests pass.
```

### 0.3: Constitutional Layer (Passive)

```
FILES: Create src/otto/constitutional.py
TEST: test_constitutional.py
  - test_red_burnout_suppresses_nudge
  - test_green_allows_nudge
  - test_low_effectiveness_suppresses_after_threshold
  - test_orange_depleted_suppresses
  - test_constitutional_never_suppresses_protector
DONE: Constitutional checks exist. Not yet wired into nudge pipeline. Tests pass.
```

**Phase 0 quality gate:** 93 existing tests + ~25 new tests pass. No behavior change for user. Energy state can be set and read.

---

## Phase 1: Wire the Constitution

> **Goal:** The constitutional layer is live. Nudges are suppressed when user is in RED burnout.

### 1.1: Wire Constitutional → Nudge

```
MODIFY: nudge.py — check_and_nudge() calls constitutional.should_suppress() before generating
MODIFY: cli.py — `otto nudge` respects energy state
TEST:
  - test_nudge_suppressed_in_red (set energy RED, verify no nudges)
  - test_nudge_allowed_in_green (set energy GREEN, verify nudges work)
  - test_suppression_logged (verify suppressed nudges are logged, not silent)
DONE: `otto energy depleted` then `otto nudge` → "OTTO is giving you space. Your commitments are safe."
```

### 1.2: Snooze and WIP Commands

```
MODIFY: cli.py — add `otto snooze <id> <duration>` and `otto wip <id> "note"`
MODIFY: store.py — add snoozed_until column, add notes column
TEST: test_cli.py gains snooze/wip tests
DONE: Users can respond to nudges before we add outbound. Response loop closed.
```

### 1.3: Scheduler

```
MODIFY: cli.py — `otto watch --schedule --interval 60`
MODIFY: pyproject.toml — re-add apscheduler
CREATE: tests/test_scheduler.py
DONE: `otto watch --schedule` runs nudge checks automatically, respecting constitutional layer.
```

**Phase 1 quality gate:** Constitutional layer is live. User can set energy, snooze commitments, and OTTO self-suppresses in depleted states. Scheduler runs automatically. ~130 tests pass.

---

## Phase 2: Signal Detection (PRISM)

> **Goal:** OTTO detects more than commitments. It detects cognitive state from message patterns.

### 2.1: PRISM Framework

```
FILES: Create src/otto/signals.py
  - SignalType enum (all types listed above)
  - detect_signals(message, history) → list[Signal]
  - Wraps existing detector.py for commitment signals
  - Adds pattern-based detection for cognitive signals
TEST: test_signals.py
  - test_commitment_detection_delegates_to_detector (existing behavior preserved)
  - test_caps_detected_as_frustrated
  - test_short_responses_detected_as_depleted
  - test_question_marks_detected_as_exploring
  - test_multiple_signals_from_one_message
DONE: signals.py returns richer signal set. detector.py untouched.
```

### 2.2: Behavioral Pattern Detection

```
MODIFY: signals.py — add HistoryAnalyzer class
  - Tracks: message lengths, response times, typo rates, topic switches
  - Detects: depleted (declining length), burst (rapid fire), crash_zone (stop after burst)
MODIFY: store.py — add interaction_log table for pattern tracking
TEST:
  - test_declining_message_length_signals_depleted
  - test_rapid_messages_signal_burst
  - test_burst_then_silence_signals_crash
DONE: PRISM detects cognitive state from behavior, not just content.
```

**Phase 2 quality gate:** PRISM detects 6+ signal types. Existing commitment detection unchanged. ~155 tests pass.

---

## Phase 3: Mode Architecture

> **Goal:** Specialist modes exist as a framework. Executor wraps existing code. Protector is live.

### 3.1: Mode Protocol

```
FILES: Create src/otto/modes/base.py
  - Protocol: responds_to(signals) → bool
  - Protocol: weight(signals, state) → float
  - Protocol: execute(input, state) → ModeResponse
  - Protocol: augment(response, state) → ModeResponse
TEST: test_modes/test_base.py — protocol compliance
DONE: Mode interface defined. No modes implemented yet.
```

### 3.2: Executor Mode (Wraps v4.0)

```
FILES: Create src/otto/modes/executor.py
  - Implements Mode protocol
  - responds_to: commitment_detected, action_required
  - execute: delegates to existing nudge.py + store.py
  - NO new behavior — this is a wrapper
TEST: test_modes/test_executor.py
  - test_executor_responds_to_commitment_signal
  - test_executor_delegates_to_nudge (existing nudge behavior)
  - test_executor_respects_constitutional_gate
DONE: Executor mode works identically to direct nudge.py calls. Existing tests still pass.
```

### 3.3: Protector Mode (NEW — First Cognitive Feature)

```
FILES: Create src/otto/modes/protector.py
  - responds_to: frustrated, crash_zone, spiral, RED burnout
  - execute: suppress other modes, offer simplified options, validate feelings
  - 10% safety floor: always runs, can override any other mode
TEST: test_modes/test_protector.py
  - test_protector_suppresses_executor_in_crisis
  - test_protector_10_percent_floor_enforced
  - test_protector_offers_max_three_options_when_overwhelmed
  - test_protector_validates_before_problem_solving
DONE: When frustrated signals detected, Protector activates and suppresses nudges.
```

### 3.4: Restorer Mode (NEW)

```
FILES: Create src/otto/modes/restorer.py
  - responds_to: depleted, low energy, ORANGE burnout
  - execute: grant permission to rest, suggest easy wins, suppress demanding tasks
  - 5% safety floor
TEST: test_modes/test_restorer.py
DONE: Restorer grants rest permission and suppresses nudges when depleted.
```

**Phase 3 quality gate:** 3 modes operational (Executor, Protector, Restorer). Constitutional layer gates all mode output. ~185 tests pass.

---

## Phase 4: NEXUS Routing

> **Goal:** Signals are automatically routed to the right mode. Deterministic.

### 4.1: Router Implementation

```
FILES: Create src/otto/router.py
  - route(signals, state, modes) → RoutingDecision
  - 5-phase pipeline: ACTIVATE → WEIGHT → BOUND → SELECT → EXECUTE
  - Deterministic: same signals + same state = same routing
TEST: test_router.py
  - test_commitment_routes_to_executor
  - test_frustrated_routes_to_protector
  - test_depleted_routes_to_restorer
  - test_safety_floors_enforced (protector always ≥ 10%)
  - test_determinism (run 100 times with same input, same output every time)
  - test_multiple_signals_routes_to_highest_weight
DONE: Router connects PRISM → Modes automatically.
```

### 4.2: Wire End-to-End

```
MODIFY: watcher.py — incoming message → signals.detect() → router.route() → mode.execute()
MODIFY: cli.py — incoming command → signals.detect() → router.route() → mode.execute()
TEST: test_agent/test_orchestrator.py — end-to-end flow
DONE: Messages flow through the full cognitive pipeline.
```

**Phase 4 quality gate:** Full pipeline operational. PRISM → NEXUS → Modes → Constitutional gate → Output. ~210 tests pass. Determinism test passes 100/100.

---

## Phase 5: Pheromone Trails

> **Goal:** OTTO learns what works and does more of it.

### 5.1: Trail System

```
FILES: Create src/otto/trails.py
  - SQLite-backed: trail_deposits table
  - deposit(action, context, strength)
  - follow(context) → ranked list of what worked before
  - decay(half_life_hours=168) — Kahan summation for numerical stability
TEST: test_trails.py
  - test_deposit_and_follow
  - test_decay_reduces_strength
  - test_kahan_summation_numerical_stability
  - test_successful_nudge_strengthens_trail
  - test_ignored_nudge_weakens_trail
DONE: Trails persist in SQLite. Successful patterns strengthen. Failed patterns decay.
```

### 5.2: Wire Trails → Router

```
MODIFY: router.py — consult trails when weighting modes
  - If trails show "nudges about meetings are always ignored" → lower executor weight for meeting signals
  - If trails show "decomposer helps with stuck states" → boost decomposer weight for stuck signals
TEST:
  - test_trails_influence_routing_weights
  - test_strong_trail_boosts_mode_weight
  - test_decayed_trail_has_minimal_influence
DONE: OTTO's routing improves over time based on what actually works.
```

**Phase 5 quality gate:** Trails operational. OTTO adapts routing based on usage patterns. ~235 tests pass.

---

## Phase 6: Transport Abstraction + Outbound

> **Goal:** OTTO sends nudges back through WhatsApp. Transport is pluggable.

### 6.1: Transport Protocol

```
FILES: Create src/otto/transport/base.py
  - Protocol: receive() → Message
  - Protocol: send(recipient, text) → bool
FILES: Create src/otto/transport/whatsapp.py (refactor from watcher.py)
FILES: Create src/otto/transport/cli_transport.py
TEST: test_transport.py — protocol compliance for both implementations
DONE: WhatsApp and CLI implement same interface. Future transports (Telegram, SMS) are pluggable.
```

### 6.2: WhatsApp Outbound

```
FILES: Create src/otto/sender.py (WhatsApp Cloud API)
MODIFY: nudge.py — can optionally send via transport
TEST: test_sender.py — mocked API calls
DONE: `otto nudge` can send nudges to WhatsApp, gated by constitutional layer.
```

**Phase 6 quality gate:** Transport is abstract. Outbound works. Constitutional layer suppresses outbound when appropriate. ~255 tests pass.

---

## Phase 7: Agent SDK Integration

> **Goal:** OTTO's modes run as Agent SDK tools. Constitutional layer runs as hooks.

### 7.1: Mode → MCP Tools

```
FILES: Create src/otto/agent/tools.py
  - Each mode becomes an @tool decorated function
  - create_sdk_mcp_server("otto-cognitive", tools=[...])
TEST: test_agent/test_tools.py — tools return valid responses
DONE: All modes callable as MCP tools.
```

### 7.2: Constitutional → Hooks

```
FILES: Create src/otto/agent/hooks.py
  - pre_tool_use_hook that checks constitutional layer
  - Denies tool execution when safety floors are violated
TEST: test_agent/test_hooks.py
  - test_hook_denies_nudge_in_red_burnout
  - test_hook_allows_protector_always
DONE: Constitutional safety enforced at Agent SDK level.
```

### 7.3: Orchestrator Agent

```
FILES: Create src/otto/agent/orchestrator.py
  - ClaudeSDKClient with NEXUS system prompt
  - Routes to mode-tools based on signals
  - Supports subagent delegation for complex tasks
TEST: test_agent/test_orchestrator.py — end-to-end with Agent SDK
DONE: OTTO can run as an Agent SDK orchestrator with subagent specialist modes.
```

**Phase 7 quality gate:** Agent SDK integration operational. Same behavior whether run via CLI pipeline or Agent SDK. ~275 tests pass.

---

## Phase 8: Remaining Modes

> **Goal:** Complete the 7-mode set.

### 8.1: Decomposer
### 8.2: Redirector
### 8.3: Acknowledger
### 8.4: Guide

Each follows the same pattern: implement Mode protocol, write tests, wire into router.

**Phase 8 quality gate:** All 7 modes operational. ~320 tests pass.

---

## Phase 9: Message Deduplication + Hardening

### 9.1: Dedup (from v4.0 Task 2)
### 9.2: Database indices (if >100 commitments)
### 9.3: Stable short IDs (hash-based, not positional)

---

## WHAT NOT TO BUILD (STILL TRUE)

| Don't Build | Why Not |
|------------|---------|
| Web dashboard | CLI + WhatsApp is the surface |
| Multi-user | OTTO is personal |
| AI-powered nudge text | Templates are cheaper and more predictable |
| Docker | `pip install -e .` is the deploy |
| Database migrations framework | Schema changes are manual + tested |
| Abstract base classes with single impls | If there's one impl, there's no interface |

---

## DETERMINISM GUARANTEES

Application-level determinism: same inputs produce same outputs in all Python control flow paths. Inspired by He2025's principle that determinism matters, but operating at a different layer — OTTO is application logic, not GPU kernels.

| Layer | Determinism | Reason |
|-------|-------------|--------|
| PRISM signal detection | ✅ REQUIRED | Same message → same signals |
| NEXUS routing | ✅ REQUIRED | Same signals + state → same routing |
| Mode selection | ✅ REQUIRED | Fixed priority, safety floors |
| Constitutional gating | ✅ REQUIRED | Same state → same suppression decision |
| Trail decay | ✅ REQUIRED | Kahan summation for numerical stability |
| Nudge template selection | ✅ REQUIRED | Deterministic hash-based |
| Presentation phrasing | ❌ INTENTIONAL | Natural variation in human-facing text |
| Retry jitter | ❌ INTENTIONAL | Prevents thundering herd |

---

## CITATIONS

- **Pixar/USD** — LIVRPS composition semantics adapted for cognitive state resolution
- **He (2025)** — "Defeating Non-determinism in LLM Inference" — ThinkingMachines blog (inspiration for determinism-first design; addresses GPU kernel nondeterminism, a different stack layer than OTTO)
- **Anthropic** — Constitutional AI adapted for cognitive augmentation safety
- **Dorigo et al.** — Ant Colony Optimization / stigmergic coordination for pheromone trail system

---

## THE ONE-PARAGRAPH SUMMARY

OTTO v5.0 is a cognitive commitment engine that watches your messages for commitments and follows up — but unlike every other reminder tool, it's constitutionally aware of your cognitive state. When you're depleted, it goes quiet. When you're overwhelmed, it simplifies. When you're in flow, it stays invisible. The v4.0 commitment loop (825 lines, 93 tests, working today) becomes the Executor mode inside a 7-mode cognitive architecture with deterministic routing, self-suppressing safety floors, and emergent learning through pheromone trails. The positioning is: "Manage the noise without falling into it." The moat is that OTTO is the only productivity tool that can decide NOT to remind you — and that decision is the product.