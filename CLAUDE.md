# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What Is OTTO

A cognitive commitment engine. Watches messages for commitments ("I'll send that Monday"), stores them, and follows up — but constitutionally aware of user cognitive state. When depleted, it goes quiet. When overwhelmed, it simplifies. Positioning: **"Manage the noise without falling into it."**

## Build & Test

```bash
cd otto_v4
pip install -e ".[dev]"          # Install with dev deps (pytest, pytest-asyncio)

# Run all core tests (493 tests)
python -m pytest tests/ -v -m "not integration"

# Run agent tests (56 tests)
python -m pytest otto_agent/tests/ -v

# Run a single test file or test
python -m pytest tests/test_store.py -v
python -m pytest tests/test_cli.py::TestSnooze::test_snooze_valid -v

# Run everything (549 tests, integration tests need ANTHROPIC_API_KEY)
python -m pytest tests/ otto_agent/tests/ -v
```

**Markers:** `integration` — tests that hit real Claude API. Deselect with `-m "not integration"`.
**asyncio_mode:** `auto` in pyproject.toml — no need for `@pytest.mark.asyncio` on async tests.
**No pytest-timeout** installed. No `--timeout` flag.

## Entry Points

| Command | Entry | Purpose |
|---------|-------|---------|
| `otto` | `otto.cli:main` (Click) | Primary CLI interface |
| `otto-agent` | `otto_agent.otto_agent:main` | Agent SDK orchestrator |
| `python -m otto` | `otto/__main__.py` | Same as `otto` |

## Code Layout

```
otto_v4/
├── src/otto/               # Core package
│   ├── cli.py              # Click CLI: list, add, done, park, snooze, wip, nudge, stats, energy, watch, nuke
│   ├── store.py            # SQLite persistence (commitments table)
│   ├── nudge.py            # Template-based follow-up (deterministic hash selection)
│   ├── detector.py         # Claude Sonnet API call to extract commitments from messages
│   ├── models.py           # Commitment dataclass + shared helpers (build_id_map, parse_duration)
│   ├── state.py            # CognitiveState + StateStore + interaction_log table
│   ├── constitutional.py   # Safety gating: should_suppress(state, action)
│   ├── signals.py          # PRISM: 14 signal types, 9 pattern banks, HistoryAnalyzer
│   ├── router.py           # NEXUS: 5-phase deterministic routing + trail adjustments
│   ├── trails.py           # Pheromone trails: deposit/follow/decay with Kahan summation
│   ├── sender.py           # NudgeSender: constitutional gate -> transport.send()
│   ├── modes/              # 7 specialist modes (Mode protocol)
│   │   ├── base.py         # Mode protocol: responds_to, weight, execute, augment
│   │   ├── executor.py     # Wraps v4.0 nudge.py (commitment tracking)
│   │   ├── protector.py    # 10% safety floor (crisis, frustration)
│   │   ├── restorer.py     # 5% safety floor (energy, rest permission)
│   │   ├── decomposer.py   # 5% safety floor (task breakdown)
│   │   ├── acknowledger.py # Validation, celebration
│   │   ├── redirector.py   # Gentle refocus from tangents
│   │   └── guide.py        # Socratic exploration
│   ├── transport/          # Pluggable transport layer
│   │   ├── base.py         # Transport protocol, Message, DeliveryResult
│   │   └── cli_transport.py # CLI transport (stdout + capture mode)
│   ├── scheduler.py        # Background thread nudge scheduler
│   ├── watcher.py          # FastAPI webhook for WhatsApp Cloud API
│   └── log.py              # Structured logging (get_logger)
├── otto_agent/             # Agent SDK integration (separate package)
│   ├── otto_agent.py       # Orchestrator: tool-use message loop
│   ├── otto_tools.py       # MCP tool definitions (8 tools mirror CLI)
│   ├── otto_hooks.py       # Pre-tool-use constitutional hooks
│   └── CLAUDE.md           # Agent personality prompt
├── tests/                  # 493+ tests
└── pyproject.toml
OTTO_Agents/                # Claude Agent SDK agents (separate package)
├── otto_agents/            # 3 agents: NEXUS orchestrator, consistency auditor, builder
│   ├── tools/              # 10 MCP tools wrapping OTTO modules
│   └── hooks/              # Constitutional PreToolUse hooks
└── tests/                  # 30 tests
```

## Architecture

The core loop:

```
MESSAGE IN → DETECT → STORE → SCHEDULE → NUDGE → CONSTITUTIONAL GATE → OUTPUT
(WhatsApp)   (Claude)  (SQLite) (scheduler) (template) (suppress if RED)  (CLI/WhatsApp)
```

**Constitutional layer sits ABOVE all output.** Any nudge or action can be suppressed based on cognitive state. This is the product differentiator — OTTO can decide NOT to remind you.

**Agent SDK path:** Same logic, different surface. `otto_agent.py` orchestrates via Claude tool-use loop → `otto_tools.py` calls the same `store.py`/`nudge.py`/`state.py` code → `otto_hooks.py` enforces constitutional gating before tool execution.

## Key Design Decisions

### Constitutional Principles (Immutable)
1. **Safety First** — Protector has 10% floor. Can suppress any output.
2. **Don't Become Noise** — Self-monitors nudge effectiveness. Backs off when nudges aren't leading to completions.
3. **User Knows Best** — "Park it" is first-class, not failure.
4. **Rest Is Productive** — System can grant permission to stop.
5. **One At A Time** — When overwhelmed, reduce to ONE choice.
6. **Dignity Always** — No clinical labels. No "ADHD mode."
7. **Privacy Is Sovereignty** — All data local. No cloud sync.

### Determinism (inspired by He2025)
Application-level determinism in all Python control flow. He2025 (Horace He, ThinkingMachines, Sept 2025) addresses GPU kernel-level batch invariance — OTTO applies the same *principle* (same inputs = same outputs) at the application layer:
- `sort_keys=True` in all JSON serialization
- Nudge template selection via `hashlib.sha256()` — PYTHONHASHSEED-independent
- Same signals + same state = same routing (no randomness in control flow)
- Trail decay uses Kahan summation for numerical stability (separate technique, not from He2025)

### Cognitive State Model
```
Energy:   high | medium | low | depleted
Burnout:  GREEN | YELLOW | ORANGE | RED
Momentum: cold_start | building | rolling | peak | crashed
```

**Suppression rules in `constitutional.py`:**
- RED burnout → suppress everything
- ORANGE + low/depleted energy → suppress nudges
- Nudge effectiveness < 10% after 3+ nudges → back off

## Database

SQLite at `~/.otto/commitments.db` with WAL mode enabled. Three tables: `commitments`, `cognitive_state`, `trail_deposits`. No ORM, no migrations framework. Schema changes are manual + tested.

**Test fixtures** use `tmp_path` — every test gets an isolated SQLite database (see `conftest.py`).

## Implementation Status

**v5.0 is CLI-first.** WhatsApp outbound transport is deferred to v5.1. The webhook (watcher.py) receives messages; outbound delivery is via CLI only.

**Complete (Phases 0-8 + hardening):**
- Phase 0-1: Structured logging, cognitive state, constitutional layer, snooze/WIP, scheduler, agent SDK
- Phase 2: PRISM signal detection (14 signal types, 9 pattern banks) + HistoryAnalyzer (behavioral patterns)
- Phase 3: Mode architecture — base protocol + Executor (wraps v4.0), Protector (10% floor), Restorer (5% floor)
- Phase 4: NEXUS deterministic router — 5-phase pipeline (ACTIVATE->WEIGHT->BOUND->SELECT->EXECUTE)
- Phase 5: Pheromone trails — SQLite deposit/follow/decay with Kahan summation, wired into router
- Phase 6: Transport abstraction (pluggable protocol) + NudgeSender with constitutional gate before send
- Phase 8: All 7 modes (Executor, Protector, Restorer, Decomposer, Acknowledger, Redirector, Guide)
- Hardening: Message dedup, stable short IDs, DB indices, SQLite WAL mode, rate limiting, pinned deps, CI

**549 tests passing** (493 core + 56 agent).

**Not yet implemented:**
- WhatsApp outbound transport (v5.1)
- Optional LLM-powered response generation (gated by env var)
- Plasticity layer (learning rate amplification during crisis)

## Conventions

- **Wrap, don't rewrite** — existing v4.0 files stay. New code wraps and extends.
- **Constitutional language** — never use "just" or "simply" (minimizing). Use "achievable" or "small."
- **Sorted dict iteration** — all dict iteration uses `sorted()` for determinism.
- **No abstract bases with single impls** — if there's one impl, there's no interface.
- **Templates over AI-generated text** — nudge text uses deterministic templates, not LLM generation.
- **ASCII only** — use `<-` not Unicode arrows. cp1252 breaks on Windows.

## Environment

- Python >= 3.11 (developed on 3.14)
- Windows 11 (Threadripper PRO, RTX 4090)
- `ANTHROPIC_API_KEY` in `.env` for detector.py and agent
- detector.py uses `claude-sonnet-4-5-20250929` for commitment extraction
