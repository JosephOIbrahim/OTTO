# OTTO v4.0 — CLAUDE.md

## Soul

**"Manage the noise without falling into it."**

This is not a tagline. It is the decision gate for every line of code, every feature, every interaction, every UI element in this project. If something adds noise, it doesn't ship. If something requires the user to fall into it — to configure, to check, to manage, to learn — it doesn't ship.

OTTO is a safety net, not a cockpit.

---

## What OTTO Is

A follow-through engine. It watches your WhatsApp messages. When you make a commitment ("I'll send that Monday"), OTTO remembers. When you haven't followed through, OTTO asks — without judgment.

That's it. If removing a component doesn't prevent OTTO from detecting a commitment and following up on it, the component is not in v4.0.

The best version of OTTO is one the user forgets is running. They just notice, over time, that they're more reliable.

---

## What OTTO Is Not

- Not a task manager. Tasks are things you assign yourself. Commitments are things you owe people.
- Not a CRM. CRMs track contacts and pipelines. OTTO tracks promises.
- Not a personal OS. Personal OSes want to be your everything. OTTO wants to disappear.
- Not a productivity tool. Productivity tools help you do more. OTTO helps you not fail the people you care about.
- Not an AI assistant. Assistants wait for commands. OTTO watches without being asked.

---

## The Noise Test

Before adding ANY feature, UI element, configuration option, or interaction:

```
1. Does this add noise to the user's life?
   YES → Don't build it.
   NO  → Continue.

2. Does this require the user to fall into it?
   (Check, configure, learn, manage, maintain, remember to use)
   YES → Redesign until the answer is NO, or don't build it.
   NO  → Continue.

3. Does this serve the core promise?
   (Helping the user keep their word to real people)
   YES → Build it.
   NO  → Park it. It belongs to a different product.
```

**If you're unsure, don't build it.** OTTO's power is in what it doesn't do.

---

## Design Principles

### 1. Push, Never Pull
OTTO comes to you. You never go to OTTO. No dashboards to check. No inboxes to clear. No timelines to scroll. If the user has to open OTTO to get value from it, the design has failed.

### 2. Shorter Than the Thing It's About
Every OTTO interaction must take less time than the commitment it references. If reminding someone about a promise takes longer than just keeping the promise, the reminder is noise.

### 3. Zero Configuration Is the Only Configuration
The user should never set up, tune, or maintain OTTO. No onboarding flow. No preference screens. No "customize your notifications." Sane defaults or nothing. If a feature requires configuration to be useful, it's the wrong feature.

### 4. Silence Is a Feature
OTTO should be quiet most of the time. No daily digests unless something is due. No weekly summaries unless something was missed. No "you're doing great!" No engagement farming. Silence means everything is fine. Sound means something needs attention.

### 5. People, Not Tasks
The data model is `commitment(you → person, what, by_when)`. Not `task(description, priority, status)`. The person you made the promise to is always present. This is what makes OTTO different from everything else. Never lose this.

### 6. Gentle, Not Guilty
Tone is critical. OTTO is not a disappointed parent. OTTO is the friend who texts "hey did you send that thing to Sarah?" — no judgment, just a heads up. The user already feels bad about forgetting. OTTO's job is to catch it early, not to make it worse.

### 7. Local by Default
The user's conversations are intimate. Commitments reveal relationships, priorities, reliability patterns. This data stays local unless the user explicitly pushes it somewhere. Privacy isn't a feature — it's the architecture.

---

## Interaction Budget

OTTO gets a limited number of interactions per day before it becomes noise itself.

- **Hard rule:** If OTTO sends more than 3 nudges in a day, something is wrong with the extraction or the thresholds.
- **Batching:** Multiple commitments due the same day = one message, not three.
- **Escalation, not repetition:** If a nudge was ignored, don't repeat it louder. One follow-up after the deadline passes, framed as "this one slipped — want to reach out to [person]?" Then silence.

---

## Tone

OTTO's voice is warm, brief, and guilt-free.

```
DO:    "Heads up — you told Sarah you'd send the report by Friday. That's tomorrow."
DO:    "This one slipped: you mentioned to Mike you'd review his doc last week."
DO:    "You've got 2 things due this week for James and Laura."

DON'T: "You have 5 overdue commitments! Take action now."
DON'T: "Great job keeping 80% of your promises this month! 🎉"
DON'T: "Don't forget! You promised Sarah..."
DON'T: "Your reliability score is 73%."

NEVER: clinical language, diagnostic framing, shame
ALWAYS: "that's a lot to hold", "permission granted: park it guilt-free"
```

The voice is a thoughtful friend with a good memory. Not a coach. Not a scorekeeper. Not a parent.

---

## Competitive Position

- **OpenClaw** is a power tool. OTTO is a safety net. Don't compete on capability.
- **Personal CRMs** (Clay, Dex, Folk) track contacts. OTTO tracks promises. Different data model.
- **WhatsNext** extracts tasks from WhatsApp. OTTO extracts commitments to people. Different framing.
- **Productivity tools** help you do more. OTTO helps you fail less.
- If a competitor requires the user to do more work, that's OTTO's advantage. Protect it.

---

## What Success Looks Like

The user says: "I don't really think about OTTO. I just... haven't dropped the ball in a while."

That's it. That's the whole product.

---

# Technical Reference

## Quick Reference

```
Language:    Python 3.11+
Codebase:    otto_v4/src/otto/   (8 files, ~1,140 lines)
Tests:       otto_v4/tests/      (6 files, 93 tests)
Install:     cd otto_v4 && pip install -e ".[dev]"
Run tests:   cd otto_v4 && python -m pytest tests/ -v -m "not integration"
Entry point: otto (CLI) or python -m otto
Branch:      v4-reset
```

---

## The Loop

```
MESSAGE IN ──> DETECT ──> EXTRACT ──> STORE ──> WAIT ──> FOLLOW UP ──> UPDATE
  (WhatsApp)  (Claude)   (fields)   (SQLite)  (cron)   (template)    (count++)
```

Every component exists to serve this loop. Nothing else.

---

## Architecture

```
otto_v4/
├── pyproject.toml              # Dependencies, entry point, pytest config
├── README.md
├── src/otto/
│   ├── __init__.py             # version = "4.0.0-dev"
│   ├── __main__.py             # python -m otto entry point
│   ├── models.py               # Commitment dataclass (13 fields)
│   ├── detector.py             # Claude Sonnet → commitment extraction
│   ├── store.py                # SQLite CRUD (stdlib only, no ORM)
│   ├── watcher.py              # WhatsApp Cloud API webhook server
│   ├── nudge.py                # Template-based follow-up system
│   └── cli.py                  # Click CLI (list/add/done/park/stats/nudge/nuke/watch)
└── tests/
    ├── conftest.py             # shared store fixture
    ├── test_models.py          # 4 tests
    ├── test_detector.py        # 9 unit + 4 integration
    ├── test_store.py           # 23 tests
    ├── test_nudge.py           # 19 tests
    ├── test_cli.py             # 20 tests
    └── test_watcher.py         # 14 tests
```

**No** LIVRPS. **No** NEXUS. **No** PRISM. **No** pheromone trails. **No** MoE.
**No** encryption layer. **No** ambient signals. **No** TUI.
Those were v3. They're gone.

---

## Stack

| Layer | Implementation | Notes |
|-------|---------------|-------|
| Input | WhatsApp Cloud API webhooks (FastAPI) | `watcher.py` |
| Detection | Claude Sonnet via `anthropic` SDK | `detector.py`, confidence >= 0.7 |
| Storage | SQLite via stdlib `sqlite3` | `store.py`, `~/.otto/commitments.db` |
| Follow-up | Template-based, zero LLM cost | `nudge.py`, max 5/check, 24h cooldown |
| Interface | Click CLI | `cli.py`, 8 commands |
| Scheduling | Not yet wired | Post-merge |

---

## Commitment Model

```python
@dataclass
class Commitment:
    raw_message: str          # Original WhatsApp text
    commitment_text: str      # Extracted promise ("send proposal to Sandra")
    who_to: str               # Recipient — THIS IS THE POINT. Never flatten to generic task.
    who_from: str = "me"
    deadline: datetime | None  # Explicit or inferred
    deadline_source: str       # "explicit" | "inferred" | "none"
    status: str = "active"    # "active" | "done" | "parked"
    follow_up_count: int = 0
    source_chat: str           # "WhatsApp/Sandra" or "manual"
    direction: str = "outbound"
    id: str                    # UUID4
    created_at: datetime       # UTC
    updated_at: datetime       # UTC
```

---

## CLI Commands

```
otto list                 Show active commitments
otto list --all           Show all including done/parked
otto list --due           Show only overdue
otto add "text"           Manually add a commitment
otto add "text" --to X    Specify recipient
otto add "text" --by DATE Specify deadline (YYYY-MM-DD)
otto done <id>            Mark commitment as done
otto park <id>            Park a commitment (guilt-free)
otto nudge                Run follow-up check now
otto stats                Counts and follow-through stats
otto watch                Start WhatsApp webhook server
otto nuke                 Delete ALL data (requires --yes)
```

Short IDs (`#1`, `#2`) map to UUIDs internally. IDs are rebuilt from `get_active()` on each call.

---

## Detector

Uses `claude-sonnet-4-5-20250929` (Sonnet for cost, not Opus).

- System prompt defines commitment vs. non-commitment examples
- Returns structured JSON: `{found, commitment_text, who_to, deadline, confidence}`
- Confidence threshold: 0.7 (configurable via `OTTO_CONFIDENCE_THRESHOLD` env var)
- Graceful failure: API errors, bad JSON, low confidence all return `None`

---

## Watcher (WhatsApp)

FastAPI server receiving WhatsApp Cloud API webhooks at `/webhook/whatsapp`.

**Env vars:**
- `WHATSAPP_VERIFY_TOKEN` — webhook verification (default: `"otto_verify"`)
- `WHATSAPP_APP_SECRET` — HMAC-SHA256 signature validation (optional)
- `ANTHROPIC_API_KEY` — for Claude detector
- `OTTO_WATCHER_PORT` — server port (default: 8000)

**Behavior:**
- Skips non-text messages
- Skips messages older than 1 hour (catch-up protection)
- Routes text through `detect_commitment()` → `store.add()`

---

## Nudge System

Template-only, zero LLM cost.

- 3 overdue templates, 2 stale templates, 1 escalation template
- Template rotation: `hash(id + follow_up_count) % len(templates)` (deterministic)
- Max 3 nudges per check (interaction budget — more than 3/day means thresholds are wrong)
- 24-hour cooldown between nudges for the same commitment
- Escalation at follow_up_count > 2 ("want to park it guilt-free?")

---

## Dependencies

```toml
dependencies = [
    "anthropic>=0.40.0",     # Claude API
    "click>=8.0",            # CLI
    "fastapi>=0.100.0",      # Webhook server
    "uvicorn>=0.20.0",       # ASGI server
    "pydantic>=2.0.0",       # Request validation
]
```

Dev: `pytest>=8.0`, `pytest-asyncio>=0.23`

---

## Testing

```bash
# Unit tests only (no API calls)
python -m pytest tests/ -v -m "not integration"

# Full suite including real Claude API
python -m pytest tests/ -v
```

- `asyncio_mode = "auto"` in pyproject.toml (required for Python 3.14)
- Integration tests in `test_detector.py` are marked `@pytest.mark.integration`
- All tests use `tmp_path` for isolated SQLite databases
- CLI tests use Click's `CliRunner` with patched `_get_store`

---

## Phases

| Phase | Status | What |
|-------|--------|------|
| 0. Scaffold | DONE | pyproject.toml, directory structure, `pip install -e` works |
| 1. Model + Detector | DONE | `models.py`, `detector.py`, 13 tests |
| 2. Store | DONE | `store.py`, 23 tests |
| 3. Watcher | DONE | `watcher.py`, 14 tests, WhatsApp webhooks wired to detector |
| 4. Nudge | DONE | `nudge.py`, template-based follow-ups, 19 tests |
| 5. CLI | DONE | `cli.py`, 8 commands, 20 tests |
| 6. Real test | DONE | Webhook curl → Claude detection (0.95) → SQLite → `otto list` (2026-02-10) |

**Phase 6 proven:** "I'll send you the proposal by Friday" → detected → stored → visible in CLI.

---

## What's NOT Built Yet

- Cron scheduling (APScheduler wiring for automatic nudge checks)
- WhatsApp outbound (sending nudges back via WhatsApp, not just printing)
- Multi-chat support (currently one webhook endpoint)
- Message deduplication
- Dashboard / web UI

These are post-merge. The loop works end-to-end with manual `otto nudge`.

---

## Dev Environment

- **Python:** 3.11+ (developed on 3.14.2)
- **Platform:** Windows (Threadripper PRO + RTX 4090 + 128GB DDR5)
- **Repo:** `C:\Users\User\OTTO_OS\` on branch `v4-reset`
- **PR:** #1 (v4-reset → master) — open, branch protection on master

---

## History

v1-v3 were an overengineered "cognitive OS" with 100+ source files, 5,000+ tests, and architecture borrowed from Pixar's USD composition system. It worked technically but never shipped the one thing that mattered: watching messages and following up on commitments.

v4 strips everything back to the commitment loop. Eight files. Ninety-three tests. One job.