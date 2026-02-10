# OTTO v4.0 — Complete Inventory & Next Steps

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Comprehensive 30k-foot inventory of everything OTTO v4.0 is today, what works, what doesn't, and the honest next steps to make it real.

**Architecture:** 8 Python files serving one loop — WhatsApp message in, Claude detects commitment, SQLite stores it, template nudges follow up, Click CLI manages it. No frameworks, no ORM, no overengineering.

**Tech Stack:** Python 3.11+ | Claude Sonnet (detection) | SQLite (storage) | FastAPI/uvicorn (webhooks) | Click (CLI) | Pydantic (validation)

---

## Part I: What Exists (The Honest Map)

### The Commitment Loop

```
MESSAGE IN --> DETECT --> STORE --> WAIT --> FOLLOW UP --> UPDATE
 (WhatsApp)  (Claude)  (SQLite)  (cron)   (template)   (count++)
     |           |         |        |          |            |
  watcher.py  detector.py store.py  ???     nudge.py    store.py
```

That `???` on WAIT is the honest gap. There's no scheduler. `otto nudge` works manually, but nobody's running it on a cron. APScheduler is declared as a dependency but never imported anywhere.

### Source Files (8 files, 1,140 lines, 825 lines of actual code)

| File | Lines | Code Lines | What It Does | Depends On |
|------|-------|-----------|--------------|------------|
| `models.py` | 77 | 61 | Commitment dataclass (13 fields), to/from dict serialization | stdlib only |
| `detector.py` | 100 | 50 | Calls Claude Sonnet, parses JSON, strips markdown fences, returns Commitment or None | anthropic, models |
| `store.py` | 330 | 255 | SQLite CRUD. 14 public methods. Opens/closes connection per operation. | models |
| `nudge.py` | 188 | 123 | 6 templates (3 overdue, 2 stale, 1 escalation). Deterministic selection via hash. Max 5/check, 24h cooldown. | models, store |
| `watcher.py` | 187 | 142 | FastAPI server. WhatsApp webhook verification + message ingestion. HMAC-SHA256 validation. Skips messages >1h old. | fastapi, pydantic, detector, store |
| `cli.py` | 250 | 190 | 8 Click commands. Short IDs (#1, #2) mapped to UUIDs dynamically. | click, models, store, watcher (dynamic), nudge (dynamic) |
| `__init__.py` | 3 | 1 | `__version__ = "4.0.0-dev"` | - |
| `__main__.py` | 5 | 3 | `python -m otto` entry point | cli |

### Test Files (6 files, 93 unit tests + 4 integration)

| File | Tests | What's Tested | What's Mocked |
|------|-------|---------------|---------------|
| `conftest.py` | 1 fixture | Shared `store` fixture (temp SQLite) | - |
| `test_models.py` | 4 | Instantiation, defaults, serialization roundtrip | Nothing |
| `test_detector.py` | 8+4 | API call, no-commit, errors, low confidence, deadlines, code fences, invalid JSON. 4 real API tests (integration). | `AsyncAnthropic` (unit tests) |
| `test_store.py` | 23 | All 14 public methods. Add/get, active/due/stale, done/park, count, nuke, directory creation. | Nothing (real SQLite on tmp_path) |
| `test_nudge.py` | 19 | Overdue/stale nudges, cooldown, escalation, template rotation, max cap, format. | Nothing (real store) |
| `test_cli.py` | 20 | All 8 commands via CliRunner. List variants, add with options, done/park, stats, nuke confirmation, nudge. | `_get_store()` monkeypatched |
| `test_watcher.py` | 13 | Webhook verification (4), message processing (7), HMAC signature (3). | `detect_commitment`, `store.add` |

### Configuration

| Env Var | Default | Where Read | Required? |
|---------|---------|-----------|-----------|
| `ANTHROPIC_API_KEY` | None | anthropic SDK (implicit) | YES |
| `WHATSAPP_VERIFY_TOKEN` | `"otto_verify"` | watcher.py:80 | No |
| `WHATSAPP_APP_SECRET` | `""` | watcher.py:81 | No (enables HMAC if set) |
| `OTTO_WATCHER_PORT` | `8000` | watcher.py:177, cli.py:196 | No |
| `OTTO_CONFIDENCE_THRESHOLD` | `0.7` | detector.py:44 | No |

### Database (Single Table)

```sql
CREATE TABLE commitments (
    id              TEXT PRIMARY KEY,    -- UUID4
    raw_message     TEXT NOT NULL,       -- Original WhatsApp text
    commitment_text TEXT NOT NULL,       -- Extracted promise
    who_to          TEXT NOT NULL,       -- Recipient
    who_from        TEXT NOT NULL DEFAULT 'me',
    direction       TEXT NOT NULL DEFAULT 'outbound',
    deadline        TEXT,                -- ISO datetime or NULL
    deadline_source TEXT NOT NULL DEFAULT 'none',
    status          TEXT NOT NULL DEFAULT 'active',
    created_at      TEXT NOT NULL,       -- ISO datetime UTC
    updated_at      TEXT NOT NULL,       -- ISO datetime UTC
    follow_up_count INTEGER NOT NULL DEFAULT 0,
    source_chat     TEXT NOT NULL DEFAULT 'unknown'
);
```

No indices. No migrations. No versioning. Fine for <10k rows.

### CLI Commands

| Command | Options | What It Does |
|---------|---------|-------------|
| `otto list` | `--all`, `--due` | Show active (or all/overdue) commitments |
| `otto add "text"` | `--to NAME`, `--by DATE` | Manually create commitment |
| `otto done <id>` | - | Mark #id as done |
| `otto park <id>` | - | Mark #id as parked (guilt-free) |
| `otto nudge` | - | Run follow-up check now, print messages |
| `otto stats` | - | Counts by status + avg follow-ups |
| `otto watch` | `--port N` | Start FastAPI webhook server |
| `otto nuke` | - | Delete ALL data (confirmation required) |

### Git State

```
Branch: v4-reset (pushed to origin)
PR: #1 (v4-reset -> master) — open

Commits:
  e43e7ed  fix: strip markdown code fences from Claude detector response
  542c565  chore: remove v3 codebase (−255,798 lines)
  0cbc5ab  fix: resolve 9 issues from codebase audit (92 tests)
  ca136a1  docs: replace v3 CLAUDE.md with v4.0
  0c2525d  feat: OTTO v4.0 build (phases 0-5)
```

### Dependencies

```toml
# Production (5)
anthropic>=0.40.0      # USED - detector.py
click>=8.0             # USED - cli.py
fastapi>=0.100.0       # USED - watcher.py
uvicorn>=0.20.0        # USED - watcher.py
pydantic>=2.0.0        # USED - watcher.py

# Dev (2)
pytest>=8.0            # USED
pytest-asyncio>=0.23   # USED
```

**APScheduler was removed from deps** in the codebase audit. If we need scheduling, we add it back when we wire it.

---

## Part II: What Works (Proven Today)

### Phase 6 — The Live Test (2026-02-10)

We ran `otto watch`, sent a WhatsApp-format webhook:

```json
{
  "text": {"body": "I'll send you the proposal by Friday"},
  "from": "1234567890",
  "contacts": [{"profile": {"name": "Sandra"}, "wa_id": "1234567890"}]
}
```

Claude Sonnet returned (confidence 0.95):
```json
{
  "found": true,
  "commitment_text": "send you the proposal",
  "who_to": "Sandra",
  "deadline": "2024-12-13T23:59:59Z",
  "confidence": 0.95
}
```

`otto list` showed:
```
#1  [just now]  send you the proposal
    From: WhatsApp/Sandra | Due: Dec 13 | Followed up: 0x
```

**The loop works.** Message in, commitment detected, stored, visible in CLI.

### What Broke During Live Test

Claude wrapped JSON in markdown code fences (` ```json ... ``` `) despite the system prompt saying "Respond ONLY with JSON." Fixed by stripping fences before parsing. Test added. 93 tests pass.

### Entry Point Conflict

Old `otto-os` 0.6.0 package in `C:\Python314\` shadows our `otto` command (needs admin to uninstall). Workaround: `python -m otto` works fine.

---

## Part III: What Doesn't Exist Yet (The Honest Gaps)

### Gap 1: No Scheduler (WAIT phase is manual)

The nudge system works — `otto nudge` checks for overdue/stale and prints messages. But nobody runs it automatically. There's no cron, no APScheduler wiring, no background thread.

**Impact:** OTTO only follows up when the user remembers to type `otto nudge`. Defeats the purpose.

### Gap 2: Nudges Don't Go Anywhere

`check_and_nudge()` returns a list of strings. The CLI prints them to stdout. That's it. No WhatsApp outbound, no email, no notification. OTTO can detect and store commitments from WhatsApp, but can't send reminders back.

**Impact:** The user has to manually check. OTTO is a ledger, not an assistant.

### Gap 3: No Message Deduplication

WhatsApp Cloud API can send the same webhook multiple times (at-least-once delivery). OTTO will create duplicate commitments.

**Impact:** Cluttered commitment list, double-nudging.

### Gap 4: No Logging

Everything goes to `print()` on stdout/stderr. No structured logging, no log levels, no log files.

**Impact:** Can't debug production issues without watching the terminal.

### Gap 5: Database Has No Indices

Fine for personal use (<100 commitments). Would degrade on larger datasets.

### Gap 6: Short IDs Are Fragile

`#1`, `#2` are rebuilt from `get_active()` on each CLI call. If a commitment gets parked between listing and acting, the IDs shift. User marks the wrong one as done.

### Gap 7: No Real WhatsApp Connection Yet

Phase 6 proved the webhook works with a `curl` test. But OTTO isn't connected to an actual WhatsApp Business Account. That requires:
- Meta Business verification
- WhatsApp Business API setup
- Webhook URL exposed via ngrok or a public server
- Cloud API access token for outbound messages

---

## Part IV: The Natural Next Steps

These are ordered by "what makes OTTO actually useful" not "what's technically interesting."

### Task 1: Wire the Scheduler

**Why:** Without this, OTTO only nudges when you remember to ask. That's not a commitment tracker — that's a todo list with extra steps.

**Files:**
- Modify: `otto_v4/src/otto/cli.py` (add `--schedule` flag to `watch` command)
- Modify: `otto_v4/pyproject.toml` (re-add `apscheduler>=3.10`)
- Create: `otto_v4/tests/test_scheduler.py`

**Step 1: Write the failing test**

```python
def test_nudge_runs_on_schedule(tmp_path, monkeypatch):
    """Verify that watch --schedule triggers check_and_nudge periodically."""
    from unittest.mock import MagicMock, patch
    mock_nudge = MagicMock(return_value=[])
    with patch("otto.nudge.check_and_nudge", mock_nudge):
        # Start scheduler, advance time, verify nudge was called
        pass  # TDD: define the interface first
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest otto_v4/tests/test_scheduler.py -v`
Expected: FAIL

**Step 3: Implement minimal scheduler**

Wire APScheduler's `BackgroundScheduler` to call `check_and_nudge()` every N minutes inside the watcher's event loop. Add `--schedule` flag (default: off) and `--interval` option (default: 60 minutes).

**Step 4: Run tests**

Run: `python -m pytest otto_v4/tests/ -v -m "not integration"`
Expected: All pass

**Step 5: Commit**

```bash
git add otto_v4/src/otto/cli.py otto_v4/pyproject.toml otto_v4/tests/test_scheduler.py
git commit -m "feat: wire APScheduler for automatic nudge checks"
```

---

### Task 2: Message Deduplication

**Why:** WhatsApp sends webhooks at-least-once. Without dedup, every retry creates a duplicate commitment.

**Files:**
- Modify: `otto_v4/src/otto/store.py` (add `message_id` column, upsert logic)
- Modify: `otto_v4/src/otto/watcher.py` (pass `message.id` through)
- Modify: `otto_v4/src/otto/models.py` (add `message_id` field)
- Create: `otto_v4/tests/test_dedup.py`

**Step 1: Write the failing test**

```python
def test_duplicate_message_not_stored_twice(store):
    """Same WhatsApp message ID should not create two commitments."""
    c1 = _make_commitment(message_id="wamid.123")
    c2 = _make_commitment(message_id="wamid.123", commitment_text="different text")
    store.add(c1)
    store.add(c2)
    assert len(store.get_active()) == 1
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest otto_v4/tests/test_dedup.py -v`
Expected: FAIL (2 commitments stored)

**Step 3: Implement dedup**

Add `message_id TEXT` column to schema (nullable for manual adds). In `store.add()`, check `SELECT 1 FROM commitments WHERE message_id = ?` before inserting. Return existing ID if duplicate.

**Step 4: Run tests**

Run: `python -m pytest otto_v4/tests/ -v -m "not integration"`
Expected: All pass

**Step 5: Commit**

```bash
git add otto_v4/src/otto/store.py otto_v4/src/otto/watcher.py otto_v4/src/otto/models.py otto_v4/tests/test_dedup.py
git commit -m "feat: deduplicate WhatsApp messages by message ID"
```

---

### Task 3: Structured Logging

**Why:** `print()` to stderr is invisible in production. Need log levels, timestamps, and optionally file output.

**Files:**
- Create: `otto_v4/src/otto/log.py` (thin wrapper around stdlib `logging`)
- Modify: `otto_v4/src/otto/detector.py` (replace prints with logger)
- Modify: `otto_v4/src/otto/watcher.py` (replace prints with logger)
- Modify: `otto_v4/src/otto/nudge.py` (add logging)

**Step 1: Write the failing test**

```python
def test_detector_logs_api_error(caplog):
    """API errors should be logged at WARNING level, not just printed."""
    with patch("otto.detector.anthropic.AsyncAnthropic") as mock:
        mock.return_value.messages.create = AsyncMock(side_effect=Exception("boom"))
        result = await detect_commitment("I'll do it", "Chat")
    assert "API" in caplog.text
    assert caplog.records[0].levelname == "WARNING"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest otto_v4/tests/test_detector.py::test_detector_logs_api_error -v`
Expected: FAIL (caplog empty, print goes to stderr)

**Step 3: Implement logging**

Create `log.py` with `get_logger(name)` that returns stdlib logger. Replace all `print(..., file=sys.stderr)` with `logger.warning(...)`. Keep `print()` only for user-facing CLI output.

**Step 4: Run tests**

Run: `python -m pytest otto_v4/tests/ -v -m "not integration"`
Expected: All pass

**Step 5: Commit**

```bash
git add otto_v4/src/otto/log.py otto_v4/src/otto/detector.py otto_v4/src/otto/watcher.py otto_v4/src/otto/nudge.py
git commit -m "refactor: replace print statements with stdlib logging"
```

---

### Task 4: WhatsApp Outbound (Send Nudges Back)

**Why:** This is what makes OTTO an assistant instead of a ledger. When a commitment is overdue, OTTO should message you on WhatsApp — not wait for you to check the CLI.

**Files:**
- Create: `otto_v4/src/otto/sender.py` (WhatsApp Cloud API outbound)
- Modify: `otto_v4/src/otto/nudge.py` (call sender after formatting)
- Modify: `otto_v4/src/otto/.env.example` (add `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`)
- Create: `otto_v4/tests/test_sender.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_send_whatsapp_message():
    """Verify outbound message is sent via WhatsApp Cloud API."""
    with patch("otto.sender.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value.post = AsyncMock(return_value=MagicMock(status_code=200))

        result = await send_nudge("1234567890", "Hey, did you send the deck?")

        assert result is True
        mock_client.return_value.post.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest otto_v4/tests/test_sender.py -v`
Expected: FAIL (module doesn't exist)

**Step 3: Implement sender**

```python
async def send_nudge(phone_number: str, message: str) -> bool:
    """Send a WhatsApp message via Cloud API."""
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "text",
        "text": {"body": message}
    }
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers)
        return resp.status_code == 200
```

**Step 4: Run tests**

Run: `python -m pytest otto_v4/tests/ -v -m "not integration"`
Expected: All pass

**Step 5: Commit**

```bash
git add otto_v4/src/otto/sender.py otto_v4/src/otto/nudge.py otto_v4/tests/test_sender.py
git commit -m "feat: WhatsApp outbound messaging for nudges"
```

---

### Task 5: Connect to Real WhatsApp

**Why:** Everything above is local. This makes OTTO real.

**This is a manual task, not a code task.** Steps:

1. Create Meta Business Account (if not already)
2. Set up WhatsApp Business API in Meta Developer Console
3. Get permanent access token (System User token, not temporary)
4. Get Phone Number ID from the dashboard
5. Configure webhook URL:
   - Option A: ngrok for local dev (`ngrok http 8000`)
   - Option B: Deploy to a VPS/cloud function
6. Set webhook fields: `messages`
7. Update `.env` with real credentials
8. Run `otto watch` and send a real WhatsApp message
9. Verify commitment appears in `otto list`

**This is the real Phase 6.** The curl test proved the code works. This proves the product works.

---

## Part V: What NOT to Build

These are tempting but would be overengineering at this stage:

| Don't Build | Why Not |
|------------|---------|
| Web dashboard | CLI is fine for one user |
| Database indices | <100 rows, SQLite is fast enough |
| Connection pooling | Per-operation connections are fine for single-user |
| Multi-user support | OTTO is personal, not a SaaS |
| AI-powered nudge text | Templates are cheaper, faster, and more predictable |
| Status enum class | Strings work, 3 values, no bugs yet |
| Database migrations | Schema is stable, one table, 13 columns |
| Docker/containerization | `pip install -e .` is the deploy story |
| Rate limiting | Single user, single webhook, no abuse vector |
| Encryption at rest | SQLite on your machine, not a server |

---

## Part VI: Numbers That Matter

| Metric | Value |
|--------|-------|
| Source files | 8 |
| Lines of code | 825 (excluding blanks/comments) |
| Tests | 93 unit + 4 integration |
| Test run time | ~1.7s |
| Dependencies (production) | 5 |
| CLI commands | 8 |
| Database tables | 1 |
| Nudge templates | 6 |
| TODO/FIXME comments | 0 |
| Circular dependencies | 0 |
| v3 remnants | 0 |
| Claude model | claude-sonnet-4-5-20250929 |
| Confidence threshold | 0.7 |
| Cooldown | 24 hours |
| Max nudges per check | 5 |
| Stale threshold | 3 days |
| Message age limit | 1 hour |

---

## Part VII: The One-Sentence Summary

OTTO v4.0 is 825 lines of Python that watch WhatsApp for commitments and remind you to follow through — it works end-to-end today via CLI, and needs a scheduler + outbound messaging to work autonomously.
