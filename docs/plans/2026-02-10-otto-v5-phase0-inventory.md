# OTTO OS v5.0 — Definitive Inventory

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Honest 30,000-foot view of what shipped, what it can do, and where it stands against three axes: production readiness, AI frontier worthiness, and real-world utility.

**Snapshot:** 2026-02-10, commit `8d3751e`, branch `master`

**Reconciles:** This document supersedes both `2026-02-10-otto-v4-inventory.md` (pre-Phase 0) and the previous v5 inventory. All numbers verified by grep + pytest.

---

## What Shipped

### Git History

**75 total commits on master.** 63 from v3 (all dead code, deleted in `542c565`). 12 from v4.0 + Phase 0:

```
0c2525d  feat: OTTO v4.0 — commitment tracker rebuild (phases 0-5)
ca136a1  docs: replace v3 CLAUDE.md with v4.0
0cbc5ab  fix: resolve 9 issues from codebase audit
542c565  chore: remove v3 codebase — 255,798 lines of dead code
e43e7ed  fix: strip markdown code fences from Claude detector response
8145c97  fix: nudge cap 5→3 (interaction budget), update stale CLAUDE.md numbers
7f24289  fix: make nudge template tests hash-seed independent
7c42fd8  v4.0: Strip to commitment loop                          ← PR #1 merged
b9be25e  refactor: replace print() with structured logging (Phase 0.1)
3505c42  feat: add cognitive state tracking + otto energy (Phase 0.2)
11847c3  feat: add constitutional layer — passive safety gates (Phase 0.3)
8d3751e  docs: fix He2025 overclaiming in CLAUDE.md
```

### Source Files (11 files, 1,545 lines)

| File | Lines | Role | Era |
|------|-------|------|-----|
| `__init__.py` | 3 | Version string (`4.0.0-dev`) | v4.0 |
| `__main__.py` | 5 | `python -m otto` entry point | v4.0 |
| `models.py` | 77 | Commitment dataclass (13 fields, serialization) | v4.0 |
| `detector.py` | 103 | Claude Sonnet commitment detection + fence stripping | v4.0 |
| `store.py` | 330 | SQLite CRUD (14 public methods, no ORM) | v4.0 |
| `nudge.py` | 188 | Template-based follow-ups (6 templates, hash rotation) | v4.0 |
| `watcher.py` | 189 | FastAPI webhook server (WhatsApp Cloud API) | v4.0 |
| `cli.py` | 301 | 9 Click commands (list/add/done/park/nudge/stats/energy/watch/nuke) | v4.0 + Phase 0.2 |
| `log.py` | 50 | Structured logging (stdlib, OTTO_LOG_LEVEL env) | Phase 0.1 |
| `state.py` | 213 | CognitiveState + StateStore (SQLite cognitive_state table) | Phase 0.2 |
| `constitutional.py` | 86 | should_suppress() — safety gates (passive, not wired) | Phase 0.3 |

### Test Files (9 files, 152 test functions)

Counts verified by `grep -c "def test_"` on each file, cross-checked with `pytest --co`:

| File | Tests | What's Tested |
|------|-------|---------------|
| `test_models.py` | 4 | Dataclass defaults, serialization roundtrip |
| `test_detector.py` | 10 unit + 4 integ | API mock, confidence gate, fence strip, caplog, real Claude API |
| `test_store.py` | 28 | All 14 CRUD methods, ordering, edge cases, nuke, dir creation |
| `test_nudge.py` | 19 | Templates, cooldown, max cap, hash rotation, escalation |
| `test_watcher.py` | 14 | Webhook verify (4), message handling (7), HMAC signature (3) |
| `test_cli.py` | 26 | All 9 commands via CliRunner, energy show/set/persist |
| `test_state.py` | 28 | CognitiveState defaults, effectiveness, persistence, setters, counters |
| `test_constitutional.py` | 19 | RED/GREEN/ORANGE/YELLOW, effectiveness threshold, protector immunity |
| **conftest.py** | — | Shared `store` fixture (tmp SQLite) |

**148 unit tests pass in 1.95s. 4 integration tests deselected in CI (`-m "not integration"`).**

**Correction from prior inventories:** Both the v4 and v5 inventories reported test_store as 23 and test_watcher as 13. Actual counts are 28 and 14 respectively. The totals (93 pre-Phase 0, 148 post-Phase 0) were correct — the per-file errors cancelled out.

### Phase 0 Delta

| What Changed | v4.0 Baseline | After Phase 0 | Delta |
|-------------|--------------|---------------|-------|
| Source files | 8 | 11 | +3 (log, state, constitutional) |
| Source lines | ~1,140 | 1,545 | +405 |
| Test functions (unit) | 93 | 148 | +55 |
| Test functions (total) | 97 | 152 | +55 |
| Database tables | 1 | 2 | +1 (cognitive_state) |
| CLI commands | 8 | 9 | +1 (energy) |
| print() in non-CLI code | ~12 | 0 | -12 |

### Database Schema (2 tables)

```sql
-- Table 1: commitments (13 columns, v4.0)
CREATE TABLE commitments (
    id              TEXT PRIMARY KEY,    -- UUID4
    raw_message     TEXT NOT NULL,       -- Original WhatsApp text
    commitment_text TEXT NOT NULL,       -- Extracted promise
    who_to          TEXT NOT NULL,       -- Recipient
    who_from        TEXT DEFAULT 'me',
    direction       TEXT DEFAULT 'outbound',
    deadline        TEXT,                -- ISO datetime or NULL
    deadline_source TEXT DEFAULT 'none',
    status          TEXT DEFAULT 'active',
    created_at      TEXT NOT NULL,       -- ISO datetime UTC
    updated_at      TEXT NOT NULL,
    follow_up_count INTEGER DEFAULT 0,
    source_chat     TEXT DEFAULT 'unknown'
);
-- No indices. Fine for <10k rows.

-- Table 2: cognitive_state (3 columns, Phase 0.2)
CREATE TABLE cognitive_state (
    key        TEXT PRIMARY KEY,  -- energy, burnout, momentum, counters
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### Configuration

| Env Var | Default | Where Read | Required? |
|---------|---------|-----------|-----------|
| `ANTHROPIC_API_KEY` | None | anthropic SDK (implicit) | YES |
| `WHATSAPP_VERIFY_TOKEN` | `"otto_verify"` | watcher.py | No |
| `WHATSAPP_APP_SECRET` | `""` | watcher.py | No (enables HMAC if set) |
| `OTTO_WATCHER_PORT` | `8000` | watcher.py, cli.py | No |
| `OTTO_CONFIDENCE_THRESHOLD` | `0.7` | detector.py | No |
| `OTTO_LOG_LEVEL` | `WARNING` | log.py | No |

### Dependencies (5 production, 2 dev)

```toml
anthropic>=0.40.0      # detector.py (AsyncAnthropic)
click>=8.0             # cli.py (9 commands)
fastapi>=0.100.0       # watcher.py (webhook server)
uvicorn>=0.20.0        # watcher.py (ASGI runner)
pydantic>=2.0.0        # watcher.py (request models)
pytest>=8.0            # all tests
pytest-asyncio>=0.23   # async detector tests
```

APScheduler was removed from deps during the v4 codebase audit. It will be re-added when the scheduler is wired (Phase 1.3).

### CLI Commands

| Command | Options | What It Does |
|---------|---------|-------------|
| `otto list` | `--all`, `--due` | Show active (or all/overdue) commitments |
| `otto add "text"` | `--to NAME`, `--by DATE` | Manually create commitment |
| `otto done <id>` | — | Mark #id as done |
| `otto park <id>` | — | Mark #id as parked (guilt-free) |
| `otto nudge` | — | Run follow-up check now, print messages |
| `otto stats` | — | Counts by status + avg follow-ups |
| `otto energy` | `[high\|medium\|low\|depleted]` | Show/set cognitive state |
| `otto watch` | `--port N` | Start FastAPI webhook server |
| `otto nuke` | — | Delete ALL data (confirmation required) |

### The Loop (What Actually Works)

```
MESSAGE IN ──> DETECT ──> STORE ──> ??? ──> FOLLOW UP ──> UPDATE
  (WhatsApp)  (Claude)  (SQLite)  (manual)  (template)   (count++)
  watcher.py  detector   store      user     nudge.py    store.py
                .py       .py     types
                                 "otto
                                  nudge"
```

**Proven 2026-02-10:** "I'll send you the proposal by Friday" → detected (0.95) → stored → `otto list` shows it. Live webhook test via curl. Code fence stripping required (Claude wraps JSON in markdown despite "respond ONLY with JSON" prompt).

**Entry point conflict:** Old `otto-os` 0.6.0 in `C:\Python314\` shadows `otto` command. Workaround: `python -m otto`.

---

## The Three Ratings

### 1. Production Readiness: 4/10

**What's solid:**
- 148 unit tests, zero flaky, 1.95s runtime
- Comprehensive error handling (API down → None, bad JSON → None, low confidence → None)
- Code fence stripping (Claude wraps JSON in markdown despite instructions)
- HMAC-SHA256 webhook signature validation
- Timezone-aware datetimes everywhere
- Structured logging — zero print() outside CLI user-facing output (Phase 0.1)
- Clean dependency graph (no circular imports, stdlib where possible)
- Cognitive state persisted in SQLite (Phase 0.2)
- Constitutional safety gates exist and are tested (Phase 0.3)

**What's missing for production:**
- **No scheduler.** The `???` in the loop. `otto nudge` must be run manually. A commitment tracker you have to remember to check is a contradiction.
- **No outbound.** Nudges print to stdout. They don't go back to WhatsApp. OTTO is a ledger, not an assistant.
- **No message dedup.** WhatsApp Cloud API delivers at-least-once. Retries create duplicate commitments.
- **No real WhatsApp connection.** Proven with `curl`, not a real Business Account.
- **Fragile short IDs.** `#1`, `#2` rebuild from `get_active()` per call. Park one, IDs shift.
- **Version still `4.0.0-dev`.** Not bumped to 5.0.
- **No database indices.** Fine for personal use, won't scale.
- **Constitutional layer is passive.** `should_suppress()` exists and is tested but nothing calls it.
- **Energy state is stored and ignored.** `otto energy depleted` persists in SQLite. No code reads it to suppress nudges.

**The honest story:** The foundation is well-engineered. Tests are thorough, error handling is robust, the architecture is clean. Phase 0 added logging, cognitive state, and constitutional gates — real infrastructure, not spec. But "production ready" means it runs autonomously and delivers value without the user remembering to invoke it. OTTO doesn't do that yet. It's a well-tested prototype with a well-tested safety net that isn't connected to anything.

**What v4.0 alone would score:** 3/10 (no logging, no state tracking, print-to-stderr debugging). Phase 0 earned one point by replacing the debugging surface and building the constitutional skeleton.

---

### 2. AI Frontier Worthiness: 3/10

**What's genuinely novel (in the spec — CLAUDE.md, 854 lines):**
- **Self-suppressing nudges.** A tool that monitors its own effectiveness and backs off when it's not helping. No reminder app does this. The `nudge_effectiveness < 0.1` check is the "without falling into it" in code.
- **Constitutional layer above modes.** Safety floors that can veto any mode's output. Protector at 10% floor. Borrowed from Anthropic's Constitutional AI, adapted for personal tools.
- **Cognitive state awareness.** Energy/burnout/momentum tracking that gates behavior. When you're depleted, OTTO goes quiet — not because you configured it, but because the architecture requires it.
- **Pheromone trails.** Stigmergic learning (Dorigo et al.) applied to nudge routing. No central coordinator. Patterns emerge from usage.
- **Variable attention as architecture.** Not "ADHD accommodation" — a system designed for how brains actually work. Dignity-first framing.

**What actually exists in code (not spec):**
- **One LLM call.** Claude Sonnet in `detector.py`. That's the entire AI surface.
- **6 nudge templates.** No LLM, no generation, no personalization. `hash(id + count) % len(templates)`.
- **A passive constitutional layer.** `should_suppress()` is an 86-line pure function with 19 tests. It checks RED burnout, ORANGE+depleted, and low effectiveness. Nothing calls it.
- **A cognitive state store.** CognitiveState dataclass + SQLite persistence + CLI command. 213 lines, 28 tests. Nothing reads it except `otto energy`.
- **Application-level determinism.** Hash-based template rotation, no randomness in routing. But there's no routing yet — just one code path.

**The honest story:** The spec is an 8/10 vision for personal AI tools. The code is a 3/10 implementation of that vision. The gap is not quality — the code that exists is well-tested and well-structured. The gap is scope: 3 of 20 planned phases are done, and all 3 are infrastructure (logging, state, passive safety). The frontier-worthy ideas exist as tested pure functions that don't compose into a system yet.

**What v4.0 alone would score:** 2/10 (one API call, some templates). Phase 0 earned one point by implementing the constitutional safety logic and cognitive state model — real code with real tests, not just spec.

---

### 3. Real-World Utility: 3/10

**What a user can do today:**
1. Run `otto watch` → webhook server starts on port 8000
2. Connect WhatsApp (via ngrok or public URL) → messages flow in
3. Claude detects commitments at 0.95 confidence → stored in SQLite
4. Run `otto list` → see what you promised to whom, with deadlines and follow-up counts
5. Run `otto list --due` → see only overdue commitments
6. Run `otto nudge` → see template-based reminders (stdout only)
7. Run `otto done 1` / `otto park 1` → manage commitments (guilt-free parking)
8. Run `otto add "text" --to Boss --by 2026-03-15` → manual add with deadline
9. Run `otto energy low` → record your energy level
10. Run `otto energy` → see current energy/burnout/momentum state
11. Run `otto stats` → counts by status + average follow-ups before completion
12. Run `otto nuke --yes` → clean slate

**What a user actually needs:**
1. **Not to type `otto nudge`.** The whole point is OTTO remembers so you don't have to. If you have to remember to check OTTO, you've just moved the failure point.
2. **Nudges sent TO them.** A reminder printed to a terminal nobody's watching is not a reminder.
3. **No duplicate commitments.** Same message hitting the webhook twice shouldn't create two entries.
4. **Constitutional gating working.** Setting energy to "depleted" should actually suppress nudges. Right now it's stored and ignored.

**The honest story:** The detection is genuinely useful. Claude at 0.95 confidence correctly identifying "I'll send you the proposal by Friday" as a commitment to Sandra with a deadline — that's real value. The storage and CLI are competent. The energy command is a real user-facing feature, even if it doesn't gate behavior yet.

But the product promise is "OTTO comes to you. You never go to OTTO." Right now, you go to OTTO for everything. The push architecture exists only in the spec.

**Who would use this today:** Someone who wants a commitment log they manually check. A smart journal that auto-extracts promises from WhatsApp. That's useful, but it's not the product vision. The product vision — a cognitive safety net that nudges you at the right time and goes quiet when you're depleted — requires Phases 1-6.

**What v4.0 alone would score:** 3/10 (same — detection works, push doesn't exist). Phase 0 didn't change the user-facing utility. `otto energy` is new but cosmetic until it gates behavior.

---

## What Exists vs. What's Designed

| Component | In Code | In Spec | Gap |
|-----------|---------|---------|-----|
| Commitment detection | Claude Sonnet, 0.7 threshold | PRISM: 14 signal types | 13 signal types |
| Storage | SQLite, 14 methods, 2 tables | + trails table | trails table |
| Follow-up | 6 templates, hash rotation | 7 specialist modes | 6 modes |
| Routing | Direct: detect → store → nudge | NEXUS: 5-phase deterministic | 5 phases |
| Safety | should_suppress() passive, 19 tests | Constitutional layer gating all output | Wiring |
| State | CognitiveState persisted, 28 tests | Same | **Done** |
| Logging | stdlib logging, 0 print() in non-CLI | Same | **Done** |
| Scheduler | None | APScheduler + constitutional gate | All |
| Outbound | None | WhatsApp Cloud API sender | All |
| Dedup | None | Message ID upsert | All |
| Learning | None | Pheromone trails, Kahan summation | All |
| Agent SDK | None | MCP tools, hooks, orchestrator | All |
| Transport | WhatsApp webhook only | Transport protocol + CLI transport | Abstraction |

---

## Phase Completion Status

| Phase | Name | Status | Tests Added |
|-------|------|--------|-------------|
| 0.1 | Structured Logging | **DONE** | +2 (caplog) |
| 0.2 | Energy State | **DONE** | +34 (28 state + 6 CLI) |
| 0.3 | Constitutional Layer (Passive) | **DONE** | +19 |
| 1.1 | Wire Constitutional → Nudge | NOT STARTED | — |
| 1.2 | Snooze + WIP Commands | NOT STARTED | — |
| 1.3 | Scheduler | NOT STARTED | — |
| 2.1 | PRISM Framework | NOT STARTED | — |
| 2.2 | Behavioral Pattern Detection | NOT STARTED | — |
| 3.1 | Mode Protocol | NOT STARTED | — |
| 3.2 | Executor Mode (wraps v4.0) | NOT STARTED | — |
| 3.3 | Protector Mode | NOT STARTED | — |
| 3.4 | Restorer Mode | NOT STARTED | — |
| 4.1 | Router Implementation | NOT STARTED | — |
| 4.2 | Wire End-to-End | NOT STARTED | — |
| 5.1 | Trail System | NOT STARTED | — |
| 5.2 | Wire Trails → Router | NOT STARTED | — |
| 6.1 | Transport Protocol | NOT STARTED | — |
| 6.2 | WhatsApp Outbound | NOT STARTED | — |
| 7.1-7.3 | Agent SDK Integration | NOT STARTED | — |
| 8.1-8.4 | Remaining Modes | NOT STARTED | — |
| 9.1-9.3 | Dedup + Hardening | NOT STARTED | — |

**3 of 20 phases complete. All 3 are infrastructure.**

---

## What NOT to Build (Still True)

| Don't Build | Why Not |
|------------|---------|
| Web dashboard | CLI + WhatsApp is the surface |
| Multi-user support | OTTO is personal, not a SaaS |
| AI-powered nudge text | Templates are cheaper, faster, and more predictable |
| Docker/containerization | `pip install -e .` is the deploy story |
| Database migrations framework | Schema changes are manual + tested |
| Abstract base classes with single impls | If there's one impl, there's no interface |
| Connection pooling | Per-operation connections fine for single-user |
| Rate limiting | Single user, single webhook, no abuse vector |
| Encryption at rest | SQLite on your machine, not a server |
| Database indices | <100 rows, SQLite is fast enough |

---

## The Numbers

| Metric | v4.0 Baseline | Post-Phase 0 |
|--------|--------------|-------------|
| Source files | 8 | 11 |
| Source lines | ~1,140 | 1,545 |
| Test files | 6 | 9 |
| Test functions (unit) | 93 | 148 |
| Test functions (total) | 97 | 152 |
| Test runtime | ~1.7s | 1.95s |
| Production deps | 5 | 5 |
| Dev deps | 2 | 2 |
| Database tables | 1 | 2 |
| CLI commands | 8 | 9 |
| Nudge templates | 6 | 6 |
| LLM calls per detection | 1 | 1 |
| LLM calls per nudge | 0 | 0 |
| Confidence threshold | 0.7 | 0.7 |
| Max nudges per check | 3 | 3 |
| Cooldown between nudges | 24h | 24h |
| Stale threshold | 3 days | 3 days |
| Message age limit | 1 hour | 1 hour |
| CLAUDE.md spec lines | 854 | 854 |
| Git commits on master | 75 (63 v3 dead) | 75 |
| v3 lines deleted | 255,798 | 255,798 |
| v5 lines added (Phase 0) | — | ~405 |

---

## The One-Paragraph Truth

OTTO OS has a well-engineered foundation (Production 4/10), an ambitious and genuinely novel cognitive architecture spec (AI Frontier 3/10 implemented, 8/10 designed), and real detection capability that works today (Utility 3/10 because push architecture doesn't exist yet). Phase 0 moved Production from 3→4 and AI Frontier from 2→3 by adding logging, cognitive state, and constitutional safety — real code with real tests, not spec. The thing that would move all three ratings the most is Phase 1: wire the constitutional layer to the nudge pipeline, add the scheduler, and close the response loop. That turns OTTO from "a smart commitment log you manually check" into "a tool that checks on you and knows when to shut up." Everything after Phase 1 is refinement. Phase 1 is the product.

---

## What Would Move the Ratings

**Production 4 → 7:** Phase 1 (wire constitutional + scheduler + snooze). OTTO runs autonomously, respects energy state, user can respond to nudges.

**AI Frontier 3 → 6:** Phase 3 (modes) + Phase 4 (NEXUS routing). Specialist modes compose with deterministic routing. The self-suppressing safety net is live and testable.

**Real-World Utility 3 → 7:** Phase 1 (scheduler) + Phase 6 (WhatsApp outbound). Nudges arrive on your phone. Constitutional layer suppresses them when you're depleted. The product promise is delivered.

**All three to 8+:** Phase 5 (pheromone trails). OTTO learns what works. The system improves without configuration. That's the moat.
