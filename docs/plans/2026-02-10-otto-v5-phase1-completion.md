# OTTO v5.0 Phase 1 Completion Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Complete Phase 1 (the first phase that changes user-visible behavior) and fix the entry point conflict so `otto` works from any terminal.

**Architecture:** Phase 1.1 (constitutional wiring) and 1.3 (scheduler) are already done. This plan covers 1.2 (snooze + notes), the entry point fix, agent CLI entry point, and an updated inventory with new numbers.

**Tech Stack:** Python 3.11+, Click, SQLite, anthropic SDK

---

## Current State

- **Source**: 12 files, 1,679 lines in `src/otto/`
- **Agent**: 3 files, 722 lines in `otto_agent/`
- **Tests**: 215 test functions, 211 pass (4 integration deselected), 95% coverage
- **Commits**: 76 on master
- **Phase 1.1**: DONE (constitutional wired to CLI nudge)
- **Phase 1.3**: DONE (scheduler with `--schedule` flag)
- **Phase 1.2**: NOT DONE (snooze + notes)
- **Entry point**: BROKEN (`otto-os` 0.6.0 shadows `otto` command)

---

### Task 1: Add `snoozed_until` column to schema

**Files:**
- Modify: `otto_v4/src/otto/models.py`
- Modify: `otto_v4/src/otto/store.py`

**Step 1: Write the failing test**

```python
# tests/test_store.py — add to existing file

class TestSnooze:
    def test_snooze_commitment(self, store, sample):
        store.add(sample)
        snooze_until = datetime.now(timezone.utc) + timedelta(hours=4)
        store.snooze(sample.id, snooze_until)
        c = store.get(sample.id)
        assert c.snoozed_until is not None
        assert c.snoozed_until == snooze_until

    def test_snoozed_excluded_from_due(self, store):
        """Snoozed commitments don't appear in get_due()."""
        past = datetime.now(timezone.utc) - timedelta(days=2)
        future = datetime.now(timezone.utc) + timedelta(hours=4)
        c = Commitment(
            raw_message="test", commitment_text="test",
            who_to="X", deadline=past, deadline_source="manual",
            created_at=past, updated_at=past,
        )
        store.add(c)
        store.snooze(c.id, future)
        assert store.get_due() == []

    def test_expired_snooze_appears_in_due(self, store):
        """Snooze that has expired should appear in get_due()."""
        past = datetime.now(timezone.utc) - timedelta(days=2)
        expired = datetime.now(timezone.utc) - timedelta(hours=1)
        c = Commitment(
            raw_message="test", commitment_text="test",
            who_to="X", deadline=past, deadline_source="manual",
            created_at=past, updated_at=past,
        )
        store.add(c)
        store.snooze(c.id, expired)
        assert len(store.get_due()) == 1

    def test_unsnooze(self, store, sample):
        store.add(sample)
        future = datetime.now(timezone.utc) + timedelta(hours=4)
        store.snooze(sample.id, future)
        store.unsnooze(sample.id)
        c = store.get(sample.id)
        assert c.snoozed_until is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_store.py::TestSnooze -v`
Expected: FAIL with AttributeError (no `snoozed_until` field)

**Step 3: Add `snoozed_until` to Commitment model**

In `models.py`, add field:
```python
snoozed_until: datetime | None = None
```

Add to `to_dict()` and `from_dict()`.

**Step 4: Add `snoozed_until` column to schema and store methods**

In `store.py`:
- Add `snoozed_until TEXT` column to `_SCHEMA` (with ALTER TABLE fallback for existing DBs)
- Add `store.snooze(id, until)` method
- Add `store.unsnooze(id)` method
- Modify `get_due()` to exclude snoozed commitments (WHERE snoozed_until IS NULL OR snoozed_until <= ?)
- Modify `get_stale()` same way
- Update `_row_to_commitment()` for new column position

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_store.py -v`
Expected: All store tests pass including new snooze tests

**Step 6: Commit**

```bash
git add src/otto/models.py src/otto/store.py tests/test_store.py
git commit -m "feat: add snooze support to commitment store"
```

---

### Task 2: Add `notes` column to schema

**Files:**
- Modify: `otto_v4/src/otto/models.py`
- Modify: `otto_v4/src/otto/store.py`

**Step 1: Write the failing test**

```python
# tests/test_store.py

class TestNotes:
    def test_add_note(self, store, sample):
        store.add(sample)
        store.add_note(sample.id, "Working on it, 50% done")
        c = store.get(sample.id)
        assert c.notes == "Working on it, 50% done"

    def test_append_note(self, store, sample):
        store.add(sample)
        store.add_note(sample.id, "Started")
        store.add_note(sample.id, "50% done")
        c = store.get(sample.id)
        assert "Started" in c.notes
        assert "50% done" in c.notes

    def test_default_notes_empty(self, store, sample):
        store.add(sample)
        c = store.get(sample.id)
        assert c.notes == ""
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_store.py::TestNotes -v`
Expected: FAIL

**Step 3: Add `notes` field and store methods**

In `models.py`: add `notes: str = ""`
In `store.py`:
- Add `notes TEXT NOT NULL DEFAULT ''` column
- Add `store.add_note(id, text)` — appends with newline separator
- Update `_row_to_commitment()` for new column

**Step 4: Run tests**

Run: `pytest tests/test_store.py -v`
Expected: All pass

**Step 5: Commit**

```bash
git add src/otto/models.py src/otto/store.py tests/test_store.py
git commit -m "feat: add notes field to commitment store"
```

---

### Task 3: Add `otto snooze` CLI command

**Files:**
- Modify: `otto_v4/src/otto/cli.py`
- Modify: `otto_v4/tests/test_cli.py`

**Step 1: Write the failing test**

```python
# tests/test_cli.py

class TestSnooze:
    def test_snooze_commitment(self, runner, tmp_both, seeded_both):
        result = runner.invoke(main, ["snooze", "1", "4h"])
        assert result.exit_code == 0
        assert "Snoozed" in result.output

    def test_snooze_invalid_id(self, runner, tmp_both):
        result = runner.invoke(main, ["snooze", "99", "4h"])
        assert "No commitment" in result.output

    def test_snooze_bad_duration(self, runner, tmp_both, seeded_both):
        result = runner.invoke(main, ["snooze", "1", "xyz"])
        assert "Invalid duration" in result.output
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py::TestSnooze -v`
Expected: FAIL (no snooze command)

**Step 3: Implement `otto snooze <id> <duration>`**

In `cli.py`:
```python
@main.command()
@click.argument("commitment_id", type=int)
@click.argument("duration", type=str)
def snooze(commitment_id: int, duration: str) -> None:
    """Snooze a commitment for a duration (e.g. 4h, 2d, 30m)."""
    # Parse duration: Nh = hours, Nd = days, Nm = minutes
    # Calculate snoozed_until
    # Call store.snooze(uuid, snoozed_until)
```

Duration parsing: `(\d+)(m|h|d)` -> minutes/hours/days from now.

**Step 4: Run tests**

Run: `pytest tests/test_cli.py -v`
Expected: All pass

**Step 5: Commit**

```bash
git add src/otto/cli.py tests/test_cli.py
git commit -m "feat: add otto snooze command"
```

---

### Task 4: Add `otto wip` CLI command

**Files:**
- Modify: `otto_v4/src/otto/cli.py`
- Modify: `otto_v4/tests/test_cli.py`

**Step 1: Write the failing test**

```python
# tests/test_cli.py

class TestWip:
    def test_wip_adds_note(self, runner, tmp_both, seeded_both):
        result = runner.invoke(main, ["wip", "1", "50% done"])
        assert result.exit_code == 0
        assert "Noted" in result.output

    def test_wip_invalid_id(self, runner, tmp_both):
        result = runner.invoke(main, ["wip", "99", "note"])
        assert "No commitment" in result.output
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py::TestWip -v`
Expected: FAIL

**Step 3: Implement `otto wip <id> "note"`**

```python
@main.command()
@click.argument("commitment_id", type=int)
@click.argument("note", type=str)
def wip(commitment_id: int, note: str) -> None:
    """Add a work-in-progress note to a commitment."""
```

**Step 4: Run tests**

Run: `pytest tests/test_cli.py -v`
Expected: All pass

**Step 5: Commit**

```bash
git add src/otto/cli.py tests/test_cli.py
git commit -m "feat: add otto wip command for progress notes"
```

---

### Task 5: Add snooze + wip tools to the agent

**Files:**
- Modify: `otto_v4/otto_agent/otto_tools.py`
- Modify: `otto_v4/otto_agent/tests/test_tools.py`

**Step 1: Write the failing test**

```python
# otto_agent/tests/test_tools.py

class TestSnoozeCommitment:
    def test_snooze(self, store, sample_commitment):
        store.add(sample_commitment)
        result = json.loads(
            execute_tool("otto_snooze_commitment", {"short_id": 1, "duration": "4h"})
        )
        assert result["snoozed"] is True

class TestWipNote:
    def test_wip(self, store, sample_commitment):
        store.add(sample_commitment)
        result = json.loads(
            execute_tool("otto_add_wip_note", {"short_id": 1, "note": "50% done"})
        )
        assert result["noted"] is True
```

**Step 2: Run test to verify it fails**

Run: `pytest otto_agent/tests/test_tools.py -v`
Expected: FAIL

**Step 3: Add 2 new tool definitions + handlers**

Add `otto_snooze_commitment` and `otto_add_wip_note` to `TOOL_DEFINITIONS` and `execute_tool()`.

**Step 4: Run tests**

Run: `pytest otto_agent/tests/ -v`
Expected: All pass

**Step 5: Update tool count test**

Update `test_tool_count` from 8 to 10.

**Step 6: Commit**

```bash
git add otto_agent/otto_tools.py otto_agent/tests/test_tools.py
git commit -m "feat: add snooze and wip tools to agent"
```

---

### Task 6: Fix entry point conflict

**Files:**
- Modify: `otto_v4/pyproject.toml`

**Step 1: Uninstall the old otto-os 0.6.0 package**

```bash
pip uninstall otto-os -y
pip uninstall otto-mcp -y   # depends on otto-os
```

**Step 2: Verify otto command is gone**

```bash
where otto
# Should fail or not exist
```

**Step 3: Install otto v4 in editable mode**

```bash
cd C:\Users\User\OTTO_OS\otto_v4
pip install -e ".[dev]"
```

**Step 4: Add agent entry point to pyproject.toml**

```toml
[project.scripts]
otto = "otto.cli:main"
otto-agent = "otto_agent.otto_agent:main"
```

**Step 5: Reinstall and verify**

```bash
pip install -e ".[dev]"
otto list
otto-agent "What commitments do I have?"
```

**Step 6: Commit**

```bash
git add pyproject.toml
git commit -m "fix: add otto-agent entry point, document otto-os removal"
```

---

### Task 7: Update inventory document

**Files:**
- Create: `docs/plans/2026-02-10-otto-v5-phase1-inventory.md`

**Step 1: Gather actual numbers**

Run: `pytest tests/ otto_agent/tests/ -v -m "not integration" --cov=src/otto --cov=otto_agent`

Count source files, lines, test functions.

**Step 2: Write updated inventory**

Document:
- Source files: 12 core + 3 agent = 15
- Source lines: ~1,700 core + ~720 agent = ~2,420
- Test files: 10 core + 3 agent = 13
- Test functions: updated count
- CLI commands: 11 (list, add, done, park, nudge, stats, energy, watch, nuke, snooze, wip)
- Agent tools: 10
- Coverage: updated %
- Phase status: Phase 1 COMPLETE (all 3 sub-phases done)
- Revised scores with justification

**Step 3: Commit**

```bash
git add docs/plans/2026-02-10-otto-v5-phase1-inventory.md
git commit -m "docs: Phase 1 completion inventory"
```

---

### Task 8: Run full test suite and verify

**Step 1: Run all tests with coverage**

```bash
cd C:\Users\User\OTTO_OS\otto_v4
python -m pytest tests/ otto_agent/tests/ -v -m "not integration" --cov=src/otto --cov=otto_agent --cov-report=term-missing
```

Expected: All pass, coverage >= 90%.

**Step 2: Verify CLI commands work**

```bash
otto list
otto energy
otto snooze --help
otto wip --help
otto nudge
otto-agent --help
```

---

## Quality Gate

Phase 1 is complete when:

- [ ] Constitutional layer is live in CLI nudge (DONE)
- [ ] Scheduler runs automatic checks (DONE)
- [ ] Snooze delays nudges for a duration
- [ ] WIP adds progress notes to commitments
- [ ] Snoozed commitments excluded from get_due() and get_stale()
- [ ] Agent has snooze + wip tools (10 total)
- [ ] `otto` command works from terminal (entry point fixed)
- [ ] `otto-agent` command works from terminal
- [ ] All tests pass, coverage >= 90%
- [ ] Inventory document updated with Phase 1 numbers

## Expected Final Numbers

- ~15 source files, ~2,500 lines
- ~13 test files, ~230 test functions
- 11 CLI commands, 10 agent tools
- Coverage >= 92%
- Phase 1: COMPLETE (3/3 sub-phases)
