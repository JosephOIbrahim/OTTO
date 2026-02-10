# OTTO v4.0 — CLAUDE.md

## What OTTO Is

OTTO watches your WhatsApp messages.
When you make a commitment ("I'll send that Monday"), OTTO remembers.
When you haven't followed through, OTTO asks — without judgment.

That's it. If removing a component doesn't prevent OTTO from detecting a commitment and following up on it, the component is not in v4.0.

---

## Quick Reference

```
Language:    Python 3.11+
Codebase:    otto_v4/src/otto/   (8 files, ~1,126 lines)
Tests:       otto_v4/tests/      (5 files, 71 tests)
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
    ├── test_models.py          # 4 tests
    ├── test_detector.py        # 5 unit + 4 integration
    ├── test_store.py           # 23 tests
    ├── test_nudge.py           # 19 tests
    └── test_cli.py             # 20 tests
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
| Scheduling | APScheduler (for cron nudges) | Not yet wired |

---

## Commitment Model

```python
@dataclass
class Commitment:
    raw_message: str          # Original WhatsApp text
    commitment_text: str      # Extracted promise ("send proposal to Sandra")
    who_to: str               # Recipient
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
- Max 5 nudges per check
- 24-hour cooldown between nudges for the same commitment
- Escalation at follow_up_count > 2 ("want to park it guilt-free?")

---

## Dependencies

```toml
dependencies = [
    "anthropic>=0.40.0",     # Claude API
    "click>=8.0",            # CLI
    "apscheduler>=3.10",     # Cron scheduling
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
| 1. Model + Detector | DONE | `models.py`, `detector.py`, 9 tests |
| 2. Store | DONE | `store.py`, 23 tests |
| 3. Watcher | DONE | `watcher.py`, WhatsApp webhooks wired to detector |
| 4. Nudge | DONE | `nudge.py`, template-based follow-ups, 19 tests |
| 5. CLI | DONE | `cli.py`, 8 commands, 20 tests |
| 6. Real test | PENDING | Real WhatsApp message -> real database entry |

**Merge gate:** Phase 6 passes — a real commitment from a real WhatsApp message in `~/.otto/commitments.db`.

---

## What's NOT Built Yet

- Cron scheduling (APScheduler wiring for automatic nudge checks)
- WhatsApp outbound (sending nudges back via WhatsApp, not just printing)
- Multi-chat support (currently one webhook endpoint)
- Message deduplication
- Dashboard / web UI

These are post-merge. The loop works end-to-end with manual `otto nudge`.

---

## Tone

OTTO's voice is warm, brief, and guilt-free.

```
NEVER: "You failed to...", "You should have...", "Overdue!"
ALWAYS: "Hey, just checking...", "No judgment", "Want to park it guilt-free?"

NEVER: clinical language, diagnostic framing, shame
ALWAYS: "that's a lot to hold", "permission granted: rest is productive"
```

---

## Dev Environment

- **Python:** 3.11+ (developed on 3.14.2)
- **Platform:** Windows (Threadripper PRO + RTX 4090 + 128GB DDR5)
- **Repo:** `C:\Users\User\OTTO_OS\` on branch `v4-reset`
- **v3 code:** Still in `src/` — left as reference, not actively maintained

---

## History

v1-v3 were an overengineered "cognitive OS" with 100+ source files, 5,000+ tests, and architecture borrowed from Pixar's USD composition system. It worked technically but never shipped the one thing that mattered: watching messages and following up on commitments.

v4 strips everything back to the commitment loop. Eight files. Seventy-one tests. One job.
