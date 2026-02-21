# OTTO Production Hardening Blueprint

## For Claude Code with Agent Teams

**Version:** 1.0.0
**Date:** 2026-02-20
**Scope:** Take OTTO from v5.0-beta to production-ready v6.0
**Codebase:** `otto_v4/` directory (579 core tests + 56 agent tests passing)

---

## Execution Model

This blueprint uses **6 phases** with **MoE (Mixture of Experts) agent teams**. Each phase has 2-4 specialist agents with non-overlapping blast radii. Agents within a phase can run in parallel. Phases are sequential -- each phase gate must pass before the next begins.

**Agent conventions:**
- Every agent gets a `SCOPE` (files it may touch), `INPUTS` (what it reads), `OUTPUTS` (what it produces), and `DONE_WHEN` (binary completion criteria)
- No agent modifies files outside its SCOPE
- Every agent writes tests FIRST, then implementation
- All agents respect existing conventions: `sorted()` on dicts, `hashlib` not `random`, ASCII only, no "just/simply"

**Phase gate:** ALL agents in a phase must reach DONE_WHEN. Verify with:
```bash
cd otto_v4
python -m pytest tests/ otto_agent/tests/ -v -m "not integration" --tb=short
```
Zero failures = gate passed.

---

## Phase 0: Security Hardening (BLOCKS EVERYTHING)

**Why first:** The repo is public. These fixes must land before anything else.

### Agent 0A: SecOps Auditor

**Mission:** Eliminate leaked secrets, harden defaults, audit git history.

**SCOPE:**
- `otto_v4/src/otto/watcher.py`
- `otto_v4/.env.example`
- `OTTO_Agents/.env.example`
- `.gitignore`

**TASK LIST:**

1. **Kill the default verify token.** In `watcher.py` line 86, replace:
   ```python
   VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "otto_verify")
   ```
   with:
   ```python
   VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
   ```
   Then in `verify_webhook()`, add an early guard:
   ```python
   if not VERIFY_TOKEN:
       raise HTTPException(status_code=503, detail="WHATSAPP_VERIFY_TOKEN not configured")
   ```
   Log a startup warning in `_lifespan` if VERIFY_TOKEN is empty.

2. **Require APP_SECRET in production.** Add a new env var `OTTO_ENV` (default `"development"`). When `OTTO_ENV=production` and `APP_SECRET` is empty, refuse to start (raise `SystemExit` in `main()`).

3. **Scrub .env.example files.** Remove `sk-ant-...` placeholder. Replace with:
   ```
   ANTHROPIC_API_KEY=  # Get from console.anthropic.com
   WHATSAPP_VERIFY_TOKEN=  # Generate: python -c "import secrets; print(secrets.token_urlsafe(32))"
   WHATSAPP_APP_SECRET=  # From Meta Business dashboard
   ```

4. **Audit git history for secrets.** Run:
   ```bash
   git log --all -p | grep -iE "sk-ant-|Bearer [a-zA-Z0-9]|password\s*=" | head -50
   ```
   If any real secrets found, document them for the user to handle (BFG Repo-Cleaner or `git filter-branch`). Do NOT attempt to rewrite history automatically.

5. **Add .gitignore entries:**
   ```
   # Secrets
   *.pem
   *.key
   secrets/
   ```

6. **Sanitize logging.** In `watcher.py` line 293, the verify token is logged on startup:
   ```python
   _log.info("Verify token: %s", VERIFY_TOKEN)
   ```
   Replace with:
   ```python
   _log.info("Verify token: %s", "****" + VERIFY_TOKEN[-4:] if len(VERIFY_TOKEN) > 4 else "[not set]")
   ```

**TESTS TO WRITE:** `tests/test_watcher_security.py`
- `test_missing_verify_token_returns_503` -- webhook verify returns 503 when token unconfigured
- `test_production_requires_app_secret` -- main() exits when OTTO_ENV=production and no APP_SECRET
- `test_verify_token_not_logged_in_full` -- capture log output, assert full token not present

**DONE_WHEN:** All 3 new tests pass. No default "otto_verify" anywhere in codebase. `grep -r "otto_verify" otto_v4/` returns zero results (excluding test fixtures that explicitly set it).

---

### Agent 0B: Encryption Engineer

**Mission:** Add at-rest encryption for sensitive fields in SQLite.

**SCOPE:**
- `otto_v4/src/otto/crypto.py` (NEW)
- `otto_v4/src/otto/store.py` (modify)
- `otto_v4/src/otto/models.py` (modify)

**TASK LIST:**

1. **Create `crypto.py` -- field-level encryption module.**
   ```python
   """Field-level AES-256-GCM encryption for sensitive commitment data.

   Key derivation: PBKDF2-HMAC-SHA256 from user passphrase + salt.
   Key storage: ~/.otto/otto.key (chmod 600, created on first use).
   If no key exists, generate one automatically (random 32 bytes, hex-encoded).

   Encrypted fields: raw_message, commitment_text, who_to, source_chat, sender_phone
   Unencrypted fields: id, status, deadline, follow_up_count, timestamps (needed for queries)
   """
   ```

   Implementation requirements:
   - Use `cryptography` library (Fernet is too limited, use `AESGCM` directly)
   - Key file at `~/.otto/otto.key`, created with `os.chmod(path, 0o600)` on Unix
   - Each encrypted value: `nonce (12 bytes) || ciphertext || tag` base64-encoded
   - Provide `encrypt_field(plaintext: str, key: bytes) -> str` and `decrypt_field(ciphertext: str, key: bytes) -> str`
   - Provide `load_or_create_key(key_path: str = "~/.otto/otto.key") -> bytes`
   - All operations deterministic given same key + nonce (but nonce is random per encryption, so ciphertext varies -- this is correct and expected)

2. **Add `cryptography` to dependencies** in `pyproject.toml`:
   ```toml
   dependencies = [
       "anthropic>=0.30",
       "click>=8.0",
       "fastapi>=0.100",
       "uvicorn>=0.20",
       "cryptography>=42.0",
   ]
   ```

3. **Modify `store.py` to encrypt/decrypt on write/read.**
   - Add optional `encryption_key: bytes | None = None` parameter to `CommitmentStore.__init__`
   - When key is provided, encrypt `raw_message`, `commitment_text`, `who_to`, `source_chat`, `sender_phone` on `add()`
   - Decrypt same fields in `_row_to_commitment()`
   - When key is None (default), operate unencrypted (backward compatible)
   - Add `is_encrypted` column to schema (migration: default False for existing rows)

4. **Add `otto encrypt` and `otto decrypt` CLI commands** (deferred to Phase 4 -- just wire the library now).

5. **Migration path:** Existing unencrypted databases continue working. Encryption is opt-in via `OTTO_ENCRYPTION_KEY` env var or `--encrypt` flag. A future `otto encrypt` command will encrypt existing data in-place.

**TESTS TO WRITE:** `tests/test_crypto.py`
- `test_roundtrip_encryption` -- encrypt then decrypt returns original
- `test_different_nonces` -- same plaintext + key produces different ciphertext
- `test_wrong_key_fails` -- decrypt with wrong key raises
- `test_key_file_creation` -- creates key file with correct permissions
- `test_store_encrypted_roundtrip` -- store.add() then store.get() with encryption key
- `test_store_unencrypted_backward_compat` -- store works without key (existing behavior)
- `test_encrypted_fields_not_plaintext_in_db` -- raw SQL SELECT shows encrypted data

**DONE_WHEN:** All 7 tests pass. `store.py` accepts optional encryption. Existing 579 tests still pass (backward compatibility).

---

### Agent 0C: Package Surgeon

**Mission:** Remove the broken `OTTO_Agents/` package from main or make it installable.

**SCOPE:**
- `OTTO_Agents/` directory
- Root `README.md`

**TASK LIST:**

1. **Decision: REMOVE.** The `OTTO_Agents/` package depends on `claude-agent-sdk>=0.1.35` (not publicly available) and uses a broken `file:///` path reference. The `otto_v4/otto_agent/` package already provides working agent functionality. Keeping `OTTO_Agents/` signals unfinished work.

2. **Move to branch:**
   ```bash
   git checkout -b archive/otto-agents-v1
   git checkout main
   git rm -r OTTO_Agents/
   ```

3. **Update root README.md** -- remove any reference to OTTO_Agents. Keep the README focused on `otto_v4/`.

4. **Update root CLAUDE.md** -- remove `OTTO_Agents/` from the Code Layout section.

**DONE_WHEN:** `OTTO_Agents/` is not on main branch. Root README references only `otto_v4/`. All existing tests in `otto_v4/` still pass.

---

## Phase 0 Gate

```bash
# All tests pass
cd otto_v4 && python -m pytest tests/ otto_agent/tests/ -v -m "not integration" --tb=short

# No default verify token
grep -r "otto_verify" otto_v4/src/ && echo "FAIL: default token still present" || echo "PASS"

# Encryption module exists and tests pass
python -m pytest tests/test_crypto.py -v

# OTTO_Agents removed from main
test -d OTTO_Agents && echo "FAIL: OTTO_Agents still exists" || echo "PASS"
```

---

## Phase 1: Determinism & Architecture Surgery

### Agent 1A: Determinism Auditor

**Mission:** Fix every place where determinism breaks, including the `_days_since` bug and any `datetime.now()` calls buried in logic functions.

**SCOPE:**
- `otto_v4/src/otto/nudge.py`
- `otto_v4/src/otto/state.py`
- `otto_v4/src/otto/store.py`

**TASK LIST:**

1. **Fix `_days_since()` in `nudge.py` (line 175).** Currently calls `datetime.now(timezone.utc)` internally. Refactor to accept `now` parameter:
   ```python
   def _days_since(commitment: Commitment, reason: str, *, now: datetime | None = None) -> int:
       if now is None:
           now = datetime.now(timezone.utc)
       ...
   ```
   Update `format_nudge()` to accept and pass `now`:
   ```python
   def format_nudge(commitment: Commitment, reason: str, *, now: datetime | None = None) -> str:
       days = _days_since(commitment, reason, now=now)
       ...
   ```
   Update all callers of `format_nudge()` in `nudge.py` and `cli.py`.

2. **Audit every `datetime.now()` call in non-test code.** Ensure all are either:
   - (a) At the boundary (CLI entry point, API handler) -- acceptable
   - (b) Behind a `now: datetime | None = None` parameter -- acceptable
   - (c) Buried in logic -- FIX IT

   Run:
   ```bash
   grep -rn "datetime.now\|datetime.utcnow" otto_v4/src/otto/ --include="*.py"
   ```
   Every hit in a non-boundary function must get a `now` parameter.

3. **Verify `_utcnow_iso()` in `store.py`.** This is a boundary call (always represents "right now" for the write timestamp). Acceptable as-is, but document it with a comment:
   ```python
   @staticmethod
   def _utcnow_iso() -> str:
       """Wall-clock timestamp for write operations. Not injected because
       updated_at should always reflect real time, not test time."""
       return datetime.now(timezone.utc).isoformat()
   ```

**TESTS TO WRITE:** `tests/test_determinism.py`
- `test_format_nudge_deterministic_with_frozen_time` -- same commitment + same `now` = same output
- `test_days_since_boundary` -- verify day calculation at exact midnight boundary
- `test_all_logic_functions_accept_now` -- introspect function signatures, assert `now` parameter exists on all functions that compute time-dependent results (use `inspect` module)

**DONE_WHEN:** All new tests pass. `grep -rn "datetime.now" otto_v4/src/otto/` shows zero hits in functions that don't either (a) have a `now` parameter or (b) are explicitly documented as boundary calls.

---

### Agent 1B: Mode Consolidator

**Mission:** Simplify 7 specialist modes to 4 essential modes.

**SCOPE:**
- `otto_v4/src/otto/modes/` (all files)
- `otto_v4/src/otto/router.py` (`_SIGNAL_TO_MODE` mapping)
- `otto_v4/tests/test_modes/` (all files)
- `otto_v4/tests/test_router.py`
- `otto_v4/tests/test_wiring.py`

**TASK LIST:**

The 4 retained modes and their absorption plan:

| Keep | Absorbs | Rationale |
|------|---------|-----------|
| **Executor** | -- | Core commitment loop, irreplaceable |
| **Protector** | -- | Constitutional safety, 10% floor, irreplaceable |
| **Restorer** | Guide (exploration prompts become rest-state suggestions) | Both serve low-energy states |
| **Decomposer** | Acknowledger (celebration becomes step-completion acknowledgment), Redirector (refocus becomes "here's the next step") | All three serve "what do I do next" |

1. **Merge Guide into Restorer.**
   - Move `EXPLORING` signal handling from Guide to Restorer
   - In Restorer, add exploration support: when energy is medium+ and signal is EXPLORING, offer Socratic prompts (current Guide behavior)
   - When energy is low/depleted, keep current Restorer behavior
   - Update `responds_to()` to include EXPLORING signals
   - Delete `guide.py`

2. **Merge Acknowledger and Redirector into Decomposer.**
   - Move `FOCUSED` signal handling (celebration/validation) into Decomposer as an augment behavior
   - Move `BURST_DETECTED` signal handling (gentle refocus) into Decomposer
   - Decomposer already handles STUCK -- now it handles the full "task management" spectrum: stuck (break down), focused (acknowledge progress), burst (redirect gently)
   - Delete `acknowledger.py` and `redirector.py`

3. **Update `_SIGNAL_TO_MODE` in `router.py`:**
   ```python
   _SIGNAL_TO_MODE: dict[SignalType, str] = {
       SignalType.COMMITMENT_DETECTED: "executor",
       SignalType.ACTION_REQUIRED: "executor",
       SignalType.DEADLINE_MENTIONED: "executor",
       SignalType.FRUSTRATED: "protector",
       SignalType.OVERWHELMED: "protector",
       SignalType.CRASH_ZONE: "protector",
       SignalType.SPIRAL: "protector",
       SignalType.DEPLETED: "restorer",
       SignalType.EXPLORING: "restorer",
       SignalType.STUCK: "decomposer",
       SignalType.BURST_DETECTED: "decomposer",
       SignalType.FOCUSED: "decomposer",
   }
   ```

4. **Update `modes/__init__.py`** to only export 4 modes.

5. **Update all test files.** Replace 7-mode test suites with 4-mode equivalents. Ensure every signal type still has a mode that handles it.

6. **Update `simulate.py`** to use 4 modes.

7. **Update `CLAUDE.md`** -- "4 specialist modes" everywhere.

**TESTS TO WRITE:** Update existing mode tests + add:
- `test_all_signal_types_have_handler` -- every SignalType in `_SIGNAL_TO_MODE` maps to a mode that exists
- `test_restorer_handles_exploring` -- EXPLORING signal activates restorer
- `test_decomposer_handles_focused` -- FOCUSED signal activates decomposer
- `test_decomposer_handles_burst` -- BURST_DETECTED signal activates decomposer
- `test_four_modes_cover_all_signals` -- comprehensive coverage check

**DONE_WHEN:** Only 4 mode files exist in `modes/`. All tests pass. `_SIGNAL_TO_MODE` maps every signal type. Simulation runs with 4 modes and converges.

---

### Agent 1C: Connection Pooler

**Mission:** Replace open-and-close-per-operation SQLite with connection pooling.

**SCOPE:**
- `otto_v4/src/otto/db.py` (NEW -- shared database module)
- `otto_v4/src/otto/store.py`
- `otto_v4/src/otto/state.py`
- `otto_v4/src/otto/trails.py`
- `otto_v4/tests/conftest.py`

**TASK LIST:**

1. **Create `db.py` -- centralized database connection manager.**
   ```python
   """Centralized SQLite connection management for OTTO.

   Provides a thread-safe connection pool (actually a per-thread connection
   cache, since SQLite connections aren't safely shared across threads).

   Usage:
       db = Database("~/.otto/commitments.db")
       with db.connect() as conn:
           conn.execute("SELECT ...")
       db.close()  # Call on shutdown
   """

   import os
   import sqlite3
   import threading
   from contextlib import contextmanager
   from pathlib import Path

   class Database:
       def __init__(self, db_path: str) -> None:
           expanded = os.path.expanduser(db_path)
           self._db_path = Path(expanded)
           self._db_path.parent.mkdir(parents=True, exist_ok=True)
           self._local = threading.local()

       def _get_connection(self) -> sqlite3.Connection:
           if not hasattr(self._local, "conn") or self._local.conn is None:
               self._local.conn = sqlite3.connect(
                   str(self._db_path),
                   check_same_thread=False,
               )
               self._local.conn.execute("PRAGMA journal_mode=WAL")
               self._local.conn.execute("PRAGMA foreign_keys=ON")
           return self._local.conn

       @contextmanager
       def connect(self):
           conn = self._get_connection()
           try:
               yield conn
               conn.commit()
           except Exception:
               conn.rollback()
               raise

       def close(self) -> None:
           if hasattr(self._local, "conn") and self._local.conn:
               self._local.conn.close()
               self._local.conn = None
   ```

2. **Refactor `CommitmentStore`, `StateStore`, `TrailStore`** to accept a `Database` instance instead of raw `db_path`. Keep backward compatibility:
   ```python
   class CommitmentStore:
       def __init__(self, db_path: str = "~/.otto/commitments.db", *, db: Database | None = None) -> None:
           self._db = db or Database(db_path)
           self._ensure_table()
   ```
   Replace all `conn = self._connect(); try: ... finally: conn.close()` patterns with:
   ```python
   with self._db.connect() as conn:
       ...
   ```

3. **Share a single `Database` instance** across all stores in `cli.py` and `watcher.py`:
   ```python
   db = Database("~/.otto/commitments.db")
   store = CommitmentStore(db=db)
   state_store = StateStore(db=db)
   trail_store = TrailStore(db=db)
   ```

4. **Update `conftest.py`** to create `Database` instances from `tmp_path`.

**TESTS TO WRITE:** `tests/test_db.py`
- `test_connection_reuse` -- two `connect()` calls return same connection object
- `test_thread_isolation` -- connections differ across threads
- `test_rollback_on_exception` -- exception in context manager triggers rollback
- `test_close_releases_connection` -- after close(), next connect() creates new
- `test_shared_db_across_stores` -- CommitmentStore and StateStore share Database instance

**DONE_WHEN:** All stores use `Database` context manager. Zero `conn.close()` calls remain in store/state/trails (replaced by context manager). All existing tests pass. New db tests pass.

---

## Phase 1 Gate

```bash
cd otto_v4 && python -m pytest tests/ otto_agent/tests/ -v -m "not integration" --tb=short
# Verify: only 4 mode files
ls src/otto/modes/*.py | grep -v __init__ | wc -l  # Should be 4: base, executor, protector, restorer, decomposer (base + 4)
# Verify: no bare datetime.now in logic
grep -rn "datetime.now" src/otto/ --include="*.py" | grep -v "# boundary" | grep -v "now is None"
```

---

## Phase 2: Signal Intelligence

### Agent 2A: Signal Refiner

**Mission:** Reduce false positive rate in pattern-based signal detection, especially for passive WhatsApp monitoring.

**SCOPE:**
- `otto_v4/src/otto/signals.py`
- `otto_v4/tests/test_signals.py`

**TASK LIST:**

1. **Add message context parameter.** Signals should know if the message is directed at OTTO (CLI input, direct message) vs. observed (WhatsApp group message):
   ```python
   def detect_signals(
       message: str,
       *,
       threshold: float = 0.5,
       context: Literal["direct", "observed"] = "direct",
   ) -> list[Signal]:
   ```
   When `context="observed"`, raise thresholds by 0.2 for cognitive signals (frustrated, overwhelmed, depleted, stuck, exploring, focused). Action signals (commitment, deadline, meeting) keep original thresholds.

2. **Add minimum message length for cognitive signals.** Short WhatsApp messages like "let's go" or "what about 3pm" are conversational, not cognitive state indicators. When `context="observed"`, require minimum 20 characters for cognitive signal detection.

3. **Tighten false-positive-prone patterns:**
   - `"help"` at 0.5 confidence is too aggressive. Change to `r"\bhelp me\b|\bneed help\b"` at 0.6
   - `"what about"` at 0.6 fires on "what about 3pm?" (scheduling, not exploring). Add negative lookahead: `r"\bwhat about(?!\s+\d)"`
   - `"let's"` at 0.6 fires on "let's grab lunch" (social, not focused-directive). Tighten to `r"\blet'?s (do|start|go ahead|proceed|build|implement|fix)\b"` at 0.7
   - `"next"` at 0.6 is too broad. Remove from FOCUSED patterns entirely.

4. **Add compound signal detection.** Some signals are only meaningful in combination:
   - `FRUSTRATED` + `DEPLETED` co-occurrence → elevate to `CRASH_ZONE` at confidence 0.8
   - `BURST_DETECTED` + `DEPLETED` co-occurrence → elevate to `CRASH_ZONE` at confidence 0.7
   Add a `_post_process_signals()` function that runs after initial detection.

5. **Add `detect_signals_observed()` convenience wrapper** for WhatsApp pipeline:
   ```python
   def detect_signals_observed(message: str) -> list[Signal]:
       """Detect signals from observed messages (higher thresholds, context-aware)."""
       return detect_signals(message, context="observed", threshold=0.6)
   ```

**TESTS TO WRITE:** Add to `tests/test_signals.py`:
- `test_observed_context_raises_thresholds` -- "help" alone doesn't trigger STUCK in observed mode
- `test_direct_context_keeps_thresholds` -- "help" still triggers in direct mode
- `test_short_observed_message_no_cognitive` -- "let's go" in observed mode produces no cognitive signals
- `test_compound_frustrated_depleted_escalates` -- co-occurrence produces CRASH_ZONE
- `test_what_about_time_not_exploring` -- "what about 3pm?" doesn't trigger EXPLORING
- `test_lets_lunch_not_focused` -- "let's grab lunch" doesn't trigger FOCUSED
- `test_lets_implement_is_focused` -- "let's implement the router" does trigger FOCUSED

**DONE_WHEN:** All new signal tests pass. All existing signal tests still pass (direct mode is default, backward compatible). False positive patterns documented in CLAUDE.md.

---

### Agent 2B: Watcher Hardener

**Mission:** Wire signal intelligence into the WhatsApp watcher and add burst message handling.

**SCOPE:**
- `otto_v4/src/otto/watcher.py`
- `otto_v4/tests/test_watcher.py`

**TASK LIST:**

1. **Wire observed-context signal detection into `_handle_message()`.** After commitment detection, run `detect_signals_observed()` on the message. If cognitive signals are detected, update the StateStore:
   ```python
   from .signals import detect_signals_observed, SignalType
   from .state import StateStore

   # In _handle_message:
   signals = detect_signals_observed(text)
   for signal in signals:
       if signal.type == SignalType.FRUSTRATED and signal.confidence >= 0.7:
           state_store.set_burnout("YELLOW")  # Escalate cautiously
       elif signal.type == SignalType.DEPLETED and signal.confidence >= 0.7:
           state_store.set_energy("low")
   ```

2. **Add burst message buffering.** WhatsApp sends messages individually but users send in bursts. Buffer messages for 5 seconds before processing:
   ```python
   _message_buffer: dict[str, list[tuple[WhatsAppContact, IncomingMessage]]] = {}
   _buffer_tasks: dict[str, asyncio.Task] = {}

   async def _buffer_message(contact, message):
       key = message.from_
       if key not in _message_buffer:
           _message_buffer[key] = []
       _message_buffer[key].append((contact, message))

       # Cancel existing flush task, start new one (debounce)
       if key in _buffer_tasks:
           _buffer_tasks[key].cancel()
       _buffer_tasks[key] = asyncio.create_task(_flush_buffer(key, delay=5.0))

   async def _flush_buffer(key: str, delay: float):
       await asyncio.sleep(delay)
       messages = _message_buffer.pop(key, [])
       # Concatenate for single detector call (cheaper)
       combined_text = " ".join(m.text.body for _, m in messages if m.text)
       # Single API call for the burst
       ...
   ```

3. **Add message deduplication** at the webhook level. WhatsApp sometimes delivers the same webhook multiple times. Track message IDs:
   ```python
   _seen_message_ids: set[str] = set()  # In-memory, resets on restart (acceptable)
   _MAX_SEEN = 10000  # Cap memory usage

   # In _handle_message:
   if message.id in _seen_message_ids:
       _log.debug("Duplicate message skipped: %s", message.id)
       return
   _seen_message_ids.add(message.id)
   if len(_seen_message_ids) > _MAX_SEEN:
       # Evict oldest (convert to list, slice, reconvert -- simple and bounded)
       _seen_message_ids = set(list(_seen_message_ids)[-(_MAX_SEEN // 2):])
   ```

**TESTS TO WRITE:** Add to `tests/test_watcher.py`:
- `test_duplicate_message_id_skipped` -- same message.id sent twice, only processed once
- `test_burst_messages_combined` -- 3 rapid messages result in single detector call
- `test_cognitive_signal_updates_state` -- frustrated message updates burnout level
- `test_seen_ids_bounded` -- after MAX_SEEN messages, set stays bounded

**DONE_WHEN:** All new watcher tests pass. Duplicate messages are filtered. Burst messages are buffered. Cognitive signals from WhatsApp update state.

---

## Phase 2 Gate

```bash
cd otto_v4 && python -m pytest tests/ otto_agent/tests/ -v -m "not integration" --tb=short
# Verify: observed mode exists
python -c "from otto.signals import detect_signals_observed; print('OK')"
# Verify: false positives reduced
python -c "
from otto.signals import detect_signals
s = detect_signals('what about 3pm?')
assert not any(x.type.value == 'exploring' for x in s), 'False positive!'
print('False positive check: PASS')
"
```

---

## Phase 3: Production Pipeline

### Agent 3A: Daily Loop Builder

**Mission:** Implement the morning digest and evening capture -- the core daily interaction pattern.

**SCOPE:**
- `otto_v4/src/otto/digest.py` (NEW)
- `otto_v4/src/otto/scheduler.py` (modify)
- `otto_v4/src/otto/cli.py` (add `otto digest` command)
- `otto_v4/src/otto/nudge.py` (extract shared formatting)

**TASK LIST:**

1. **Create `digest.py` -- morning digest generator.**
   ```python
   """Morning digest for OTTO.

   Generates a summary of active commitments, due items, and suggested
   focus for the day. Constitutional-aware: adapts tone and content
   based on cognitive state.

   Template-only. No LLM calls. Deterministic.
   """
   ```

   Functions:
   - `generate_morning_digest(store, state, *, now=None) -> str`
     - Lists commitments due today
     - Lists overdue commitments (count only if > 3, to avoid overwhelm)
     - Suggests ONE focus item (the hardest/most overdue -- AlphaProof principle)
     - If state is ORANGE/RED: shortened digest, permission to skip
     - If state is depleted: "Nothing urgent. Take your time today."
   - `generate_evening_capture(store, state, *, now=None) -> str`
     - Summary of what was done/parked today
     - Follow-through rate for the day
     - Gentle close: "Good day. Rest well." / "Tough day. Tomorrow's clean."

2. **Wire into scheduler.** Add configurable digest times:
   ```python
   MORNING_DIGEST_HOUR = int(os.environ.get("OTTO_MORNING_HOUR", "9"))
   EVENING_CAPTURE_HOUR = int(os.environ.get("OTTO_EVENING_HOUR", "21"))
   ```

3. **Add `otto digest` CLI command:**
   ```
   otto digest          # Show morning digest now
   otto digest --evening  # Show evening capture now
   ```

4. **Constitutional gating on digest:** The digest itself goes through `should_suppress()`. If suppressed, the digest is still generated but marked `[SUPPRESSED -- you're in {state}. Digest saved, read when ready.]`

**TESTS TO WRITE:** `tests/test_digest.py`
- `test_morning_digest_with_due_items` -- shows due commitments
- `test_morning_digest_empty` -- graceful when nothing due
- `test_morning_digest_red_burnout` -- shortened, permission-granting
- `test_morning_digest_depleted` -- minimal, no pressure
- `test_evening_capture_with_completions` -- shows what was done
- `test_evening_capture_nothing_done` -- no judgment, suggests rest
- `test_digest_deterministic` -- same inputs = same output
- `test_digest_suppressed_in_red` -- marked as suppressed but still generated
- `test_hardest_item_surfaced` -- most overdue commitment shown as focus

**DONE_WHEN:** `otto digest` works. Morning and evening templates are constitutional-aware. All 9 tests pass.

---

### Agent 3B: WhatsApp Outbound Engineer

**Mission:** Complete the WhatsApp outbound transport so nudges can be sent back to users.

**SCOPE:**
- `otto_v4/src/otto/transport/whatsapp_transport.py` (already exists, needs completion)
- `otto_v4/src/otto/sender.py` (modify -- wire WhatsApp transport)
- `otto_v4/src/otto/cli.py` (modify -- `otto watch` uses WhatsApp transport)

**TASK LIST:**

1. **Complete `whatsapp_transport.py`.** The file exists but needs:
   - Retry logic with exponential backoff (3 attempts, 1s/2s/4s)
   - Rate limiting (WhatsApp allows 80 messages/second for business API, but we should self-limit to 1 message per user per minute to avoid being annoying)
   - Error classification: transient (retry) vs. permanent (log and skip)
   - Phone number formatting validation

2. **Wire into `sender.py`.** The `NudgeSender` should:
   - Check if the commitment has a `sender_phone` -- if yes, attempt WhatsApp delivery
   - Fall back to CLI transport if WhatsApp fails
   - Record delivery method in nudge metadata
   - Respect constitutional suppression (already implemented, verify)

3. **Add WhatsApp transport to `otto watch`.** When watcher is running and `WHATSAPP_PHONE_NUMBER_ID` + `WHATSAPP_ACCESS_TOKEN` are configured:
   - Nudges for WhatsApp-sourced commitments are sent back via WhatsApp
   - CLI-sourced commitments still use CLI transport

4. **Template WhatsApp messages.** WhatsApp messages should be shorter than CLI nudges. Add WhatsApp-specific templates to `nudge.py`:
   ```python
   _WA_OVERDUE_TEMPLATES = [
       "Hey -- did you handle: {commitment_text}? (for {who_to})",
       "Quick check on: {commitment_text}. Done / Still on it / Park it?",
   ]
   ```

**TESTS TO WRITE:** `tests/test_whatsapp_outbound.py`
- `test_send_success` -- mock HTTP, verify correct payload
- `test_retry_on_transient_error` -- 500 error retries, then succeeds
- `test_no_retry_on_permanent_error` -- 400 error does not retry
- `test_rate_limiting` -- second message within 60s is queued, not sent immediately
- `test_fallback_to_cli` -- WhatsApp failure falls back to CLI transport
- `test_sender_routes_by_source` -- WhatsApp-sourced commitment goes to WhatsApp transport

**DONE_WHEN:** Nudges can be sent via WhatsApp. Retry and rate limiting work. Fallback to CLI works. All 6 tests pass.

---

### Agent 3C: CLI Polish Agent

**Mission:** Add missing CLI commands and polish the user experience.

**SCOPE:**
- `otto_v4/src/otto/cli.py`
- `otto_v4/tests/test_cli.py`

**TASK LIST:**

1. **Add `otto encrypt` command:**
   ```
   otto encrypt       # Encrypt existing database in-place
   otto encrypt --check  # Show encryption status
   ```
   Uses the crypto module from Phase 0. Reads all commitments, encrypts sensitive fields, writes back. Idempotent (skips already-encrypted rows via `is_encrypted` column).

2. **Add `otto digest` command** (wired in Agent 3A).

3. **Add `otto doctor` command** -- system health check:
   ```
   otto doctor
   # Output:
   # Database: OK (142 commitments, 12 active)
   # Encryption: NOT CONFIGURED (run `otto encrypt` to enable)
   # WhatsApp: NOT CONFIGURED (set WHATSAPP_VERIFY_TOKEN)
   # Scheduler: OK (last run 2h ago)
   # Learning: 45 outcomes, 12 trails
   # State: energy=medium burnout=GREEN momentum=cold_start
   ```

4. **Improve `otto list` formatting.** Add color support via Click's `style()`:
   - Overdue commitments in yellow
   - RED burnout state shown as warning
   - Snoozed commitments in dim

5. **Add `otto export` command:**
   ```
   otto export > commitments.json  # JSON export (decrypted)
   otto export --format csv > commitments.csv
   ```

**TESTS TO WRITE:** Add to `tests/test_cli.py`:
- `test_doctor_reports_status` -- all health checks run
- `test_encrypt_command_encrypts_db` -- database rows become encrypted
- `test_export_json_format` -- valid JSON output
- `test_export_csv_format` -- valid CSV output
- `test_list_color_output` -- overdue items styled differently

**DONE_WHEN:** `otto doctor`, `otto encrypt`, `otto export` all work. All new CLI tests pass.

---

## Phase 3 Gate

```bash
cd otto_v4 && python -m pytest tests/ otto_agent/tests/ -v -m "not integration" --tb=short
# Verify new commands exist
otto digest --help
otto doctor --help
otto export --help
otto encrypt --help
```

---

## Phase 4: Integration & Learning

### Agent 4A: Calendar Integration Architect

**Mission:** Add Google Calendar integration for time-block suggestions.

**SCOPE:**
- `otto_v4/src/otto/calendar.py` (NEW)
- `otto_v4/src/otto/digest.py` (modify -- add calendar context)

**TASK LIST:**

1. **Create `calendar.py` -- Google Calendar read-only integration.**
   ```python
   """Google Calendar integration for OTTO.

   Read-only. Fetches today's events to:
   1. Suggest time blocks for commitment work
   2. Avoid nudging during meetings
   3. Provide context in morning digest

   Uses Google Calendar API via service account or OAuth.
   Gated by OTTO_GOOGLE_CALENDAR env var.
   """
   ```

   Functions:
   - `is_calendar_enabled() -> bool` -- checks env var
   - `get_today_events(*, now=None) -> list[CalendarEvent]`
   - `find_free_blocks(events, min_minutes=30) -> list[TimeBlock]`
   - `suggest_commitment_block(commitment, events) -> TimeBlock | None`

2. **Calendar-aware nudge suppression.** Don't nudge during meetings:
   ```python
   def is_in_meeting(*, now=None) -> bool:
       events = get_today_events(now=now)
       now = now or datetime.now(timezone.utc)
       return any(e.start <= now <= e.end for e in events)
   ```
   Wire into `constitutional.py` as an additional suppression check.

3. **Calendar context in morning digest.** When calendar is enabled:
   ```
   Today you have 3 meetings (10am-11am, 1pm-2pm, 4pm-5pm).
   Free blocks: 9-10am, 11am-1pm, 2-4pm.
   Suggested focus: "send the report to Sarah" during 11am-1pm block.
   ```

4. **Graceful degradation.** Calendar is entirely optional. All features work without it. If calendar API fails, log warning and continue without calendar context.

**TESTS TO WRITE:** `tests/test_calendar.py`
- `test_find_free_blocks_between_events` -- correct block detection
- `test_find_free_blocks_no_events` -- full day is free
- `test_is_in_meeting_true` -- currently in a meeting
- `test_is_in_meeting_false` -- not in a meeting
- `test_suggest_block_picks_longest` -- suggests longest free block
- `test_calendar_disabled_graceful` -- everything works when disabled
- `test_calendar_api_failure_graceful` -- API error logged, not propagated

**DONE_WHEN:** Calendar module exists with 7 passing tests. Digest incorporates calendar when available. All existing tests still pass.

---

### Agent 4B: Learning Pipeline Verifier

**Mission:** Verify and document the UCB1 learning pipeline end-to-end with the new 4-mode architecture.

**SCOPE:**
- `otto_v4/src/otto/simulate.py` (modify for 4 modes)
- `otto_v4/src/otto/learner.py` (verify correctness)
- `otto_v4/tests/test_simulate.py`
- `otto_v4/tests/test_learner.py`

**TASK LIST:**

1. **Update simulation to use 4 modes.** Verify convergence properties are maintained or improved.

2. **Add learning visibility to `otto metrics`.** Show:
   ```
   UCB1 Learning Status
   --------------------
   Mode        | Activations | Success Rate | UCB Adjustment
   executor    |          42 |        71.4% |        +0.085
   protector   |          18 |        66.7% |        +0.067
   restorer    |          12 |        50.0% |        -0.012
   decomposer  |          28 |        64.3% |        +0.057

   Plasticity: CLOSED (stable)
   Trail count: 34 (decay: 168h half-life)
   ```

3. **Add determinism regression test.** Run simulation with seed=42 for 200 cycles. Record exact final UCB adjustments. Hardcode these as expected values. If they ever change, determinism has broken:
   ```python
   def test_simulation_deterministic_regression():
       result = SimulationEngine(db_path).run(n_cycles=200, seed=42)
       assert result.ucb_adjustments_final == {
           "executor": pytest.approx(0.085, abs=0.001),
           ...
       }
   ```

4. **Document the learning pipeline** in a new `docs/learning.md`:
   - How UCB1 works in OTTO's context
   - What "success" and "ignored" mean for each mode
   - How plasticity amplifies crisis learning
   - How trail decay prevents stale patterns
   - Expected convergence behavior

**DONE_WHEN:** Simulation passes with 4 modes. Determinism regression test hardcoded. `otto metrics` shows learning status. `docs/learning.md` exists.

---

## Phase 4 Gate

```bash
cd otto_v4 && python -m pytest tests/ otto_agent/tests/ -v -m "not integration" --tb=short
# Verify simulation convergence
python -c "
from otto.simulate import SimulationEngine
import tempfile, os
with tempfile.TemporaryDirectory() as td:
    r = SimulationEngine(os.path.join(td, 'test.db')).run(200, seed=42)
    print(r.summary())
    assert r.cycles_completed == 200
    assert len(r.mode_activations) == 4, f'Expected 4 modes, got {len(r.mode_activations)}'
    print('PASS')
"
```

---

## Phase 5: Documentation & Release

### Agent 5A: Documentation Architect

**Mission:** Update all documentation to reflect the production-ready state.

**SCOPE:**
- `otto_v4/CLAUDE.md` (rewrite)
- `README.md` (root, rewrite)
- `otto_v4/README.md` (rewrite)
- `docs/learning.md` (verify from Phase 4)
- `docs/security.md` (NEW)
- `docs/architecture.md` (NEW)

**TASK LIST:**

1. **Rewrite CLAUDE.md** for v6.0:
   - Update code layout (4 modes, not 7; no OTTO_Agents)
   - Update test count
   - Add encryption documentation
   - Add calendar integration documentation
   - Update architecture diagram
   - Document daily loop (digest + evening capture)

2. **Rewrite root README.md:**
   - Clear value proposition
   - Quick start that actually works
   - Feature list reflecting reality
   - Link to docs/

3. **Create `docs/security.md`:**
   - Encryption architecture
   - Key management
   - WhatsApp webhook security
   - Data retention policy
   - What's encrypted vs. what's not (and why)

4. **Create `docs/architecture.md`:**
   - System diagram (ASCII art, constitutional)
   - Data flow: message → detect → store → schedule → nudge → gate → output
   - 4-mode routing explanation
   - Learning pipeline diagram
   - Transport layer diagram

5. **Version bump:** Update `pyproject.toml` version to `6.0.0`.

**DONE_WHEN:** All docs exist and are consistent with codebase. No references to 7 modes, OTTO_Agents, or pre-v6 architecture. Version is 6.0.0.

---

### Agent 5B: CI/CD Hardener

**Mission:** Ensure CI catches regressions and the release is clean.

**SCOPE:**
- `.github/workflows/tests.yml`
- `otto_v4/pyproject.toml`

**TASK LIST:**

1. **Update CI workflow:**
   ```yaml
   name: OTTO Tests
   on: [push, pull_request]
   jobs:
     test:
       runs-on: ubuntu-latest
       strategy:
         matrix:
           python-version: ["3.11", "3.12", "3.13"]
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v5
           with:
             python-version: ${{ matrix.python-version }}
         - run: cd otto_v4 && pip install -e ".[dev]"
         - run: cd otto_v4 && python -m pytest tests/ otto_agent/tests/ -v -m "not integration" --tb=short
         - run: cd otto_v4 && python -m pytest tests/test_determinism.py -v  # Determinism regression

     security:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - run: |
             # No default secrets in source
             ! grep -r "otto_verify" otto_v4/src/
             # No API keys
             ! grep -rE "sk-ant-[a-zA-Z0-9]" .
             echo "Security checks passed"
   ```

2. **Pin all dependencies** in `requirements.lock` (already exists, verify it's current).

3. **Add `[tool.coverage]` config** to `pyproject.toml`:
   ```toml
   [tool.coverage.run]
   source = ["otto"]
   omit = ["*/tests/*"]

   [tool.coverage.report]
   fail_under = 85
   ```

**DONE_WHEN:** CI runs on 3 Python versions. Security check job exists. Coverage threshold set at 85%.

---

## Phase 5 Gate (Final)

```bash
# Full test suite
cd otto_v4 && python -m pytest tests/ otto_agent/tests/ -v -m "not integration" --tb=short

# Coverage
cd otto_v4 && python -m pytest tests/ --cov=otto --cov-report=term-missing -m "not integration"

# Security
grep -r "otto_verify" otto_v4/src/ && echo "FAIL" || echo "PASS: no default tokens"
grep -rE "sk-ant-" . && echo "FAIL" || echo "PASS: no API keys"

# Doctor
cd otto_v4 && python -m otto.cli doctor

# Version
python -c "import otto; print(otto.__version__)"  # Should print 6.0.0
```

---

## Execution Order Summary

```
Phase 0: Security Hardening          [BLOCKS ALL]
  0A: SecOps Auditor                  (parallel)
  0B: Encryption Engineer             (parallel)
  0C: Package Surgeon                 (parallel)
  --- GATE ---

Phase 1: Architecture Surgery         [BLOCKS 2-5]
  1A: Determinism Auditor             (parallel)
  1B: Mode Consolidator               (parallel)
  1C: Connection Pooler               (parallel)
  --- GATE ---

Phase 2: Signal Intelligence          [BLOCKS 3-5]
  2A: Signal Refiner                  (parallel)
  2B: Watcher Hardener                (parallel, depends on 2A)
  --- GATE ---

Phase 3: Production Pipeline          [BLOCKS 4-5]
  3A: Daily Loop Builder              (parallel)
  3B: WhatsApp Outbound               (parallel)
  3C: CLI Polish                      (parallel, depends on 0B for encrypt)
  --- GATE ---

Phase 4: Integration & Learning       [BLOCKS 5]
  4A: Calendar Integration            (parallel)
  4B: Learning Pipeline Verifier      (parallel, depends on 1B)
  --- GATE ---

Phase 5: Documentation & Release      [FINAL]
  5A: Documentation Architect         (parallel)
  5B: CI/CD Hardener                  (parallel)
  --- SHIP ---
```

**Total: 6 phases, 14 agents, ~60 new tests, estimated 4-6 focused sessions.**

---

## Constitutional Reminder

Every agent in this blueprint must respect OTTO's constitutional principles:

1. **Safety First** -- Protector keeps its floor. Period.
2. **Don't Become Noise** -- Every new feature passes the Noise Test: Does it reduce noise? Does it add cognitive load? Would the user forget it's running?
3. **User Knows Best** -- Park is first-class. Rest is productive.
4. **Dignity Always** -- No clinical labels. No guilt. No "just."
5. **Privacy Is Sovereignty** -- All data local. Encryption available. No cloud sync.
6. **Ship Over Perfect** -- Each phase ships working code. No spec without implementation.
7. **Determinism** -- Same inputs = same outputs. Always.
