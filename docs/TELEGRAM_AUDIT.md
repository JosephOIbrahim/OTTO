# Telegram Module Audit

**Generated:** 2026-02-02
**Branch:** feature/telegram-bot
**Stream:** A (Highest Priority)

---

## Files Found

| File | Lines | Purpose |
|------|-------|---------|
| `src/otto/telegram/__init__.py` | ~20 | Module exports |
| `src/otto/telegram/bot.py` | 350 | Telegram bot runner (python-telegram-bot) |
| `src/otto/telegram/adapter.py` | 770 | Adapter to CognitiveOrchestrator |

## Current Capabilities

### Bot (`bot.py`)
- Full working bot using python-telegram-bot>=20.0
- Commands: `/start`, `/help`, `/status`, `/reset`, `/calibrate`
- Message handler for natural language
- Session storage path configurable
- [He2025] Compliant: Fixed handler registration order
- Supports both polling and webhook modes

### Adapter (`adapter.py`)
- `TelegramSession`: Session state per user (2-hour timeout)
- `TelegramMessage`: Normalized message structure
- `TelegramResponse`: Response with expert/anchor metadata
- Connects to `CognitiveOrchestrator`
- Expert-specific responses (Validator, Scaffolder, Restorer, Socratic, Direct)
- Session persistence to JSON
- [He2025] Compliant: Sorted iteration, deterministic state transitions

## Missing Pieces

### 1. Memory Integration (CRITICAL)
The adapter does NOT currently use `get_memory()`:

```python
# MISSING in adapter.py:
from ..memory import get_memory, Episode, Outcome

# Should be added to process_message():
memory = get_memory()
memory.record_episode(...)
memory.deposit_trail(...)
```

### 2. Trail-Based Trust
The adapter doesn't check trail strength for auto-approval:

```python
# MISSING:
trail = memory.follow_trail(f"action:{action_type}")
if trail.strength > AUTO_APPROVE_THRESHOLD:
    # Auto-approve based on learned trust
```

### 3. MCP Service Routing
The adapter routes through CognitiveOrchestrator but doesn't:
- Connect directly to MCP services (calendar, tasks, email)
- Record service invocations as episodes
- Track service success/failure in trails

### 4. Approval Flow
Missing inline button approval flow:
- InlineKeyboardButton for approve/deny
- Pending approval tracking
- Callback query handling

## Integration Points

| Component | Status | Notes |
|-----------|--------|-------|
| `surfaces/base.py` | ❌ Not Used | Should inherit BaseSurface |
| `memory.get_memory()` | ❌ Not Used | CRITICAL - need to wire |
| CognitiveOrchestrator | ✅ Connected | Routes messages |
| MCP Services | ❌ Not Connected | Need direct service routing |
| Approval Service | ❌ Not Connected | Need trail-based approval |

## Recommended Changes

### Phase A.1: Wire Memory (2-3 hours)
1. Import `get_memory()` in adapter
2. Record episodes for all messages
3. Deposit trails on successful interactions
4. Follow trails for trust decisions

### Phase A.2: Connect Approval Flow (2-3 hours)
1. Add inline buttons for approval
2. Connect to ApprovalService
3. Query trails before auto-approve
4. Deposit trails on approval outcomes

### Phase A.3: MCP Service Routing (3-4 hours)
1. Add ServiceRouter class
2. Parse intents to service calls
3. Route to calendar/tasks/email MCP
4. Record service results in memory

---

## Architecture After Changes

```
TelegramAdapter
    │
    ├── get_memory() ─────────────────────┐
    │   ├── record_episode() ◄────────────┤
    │   ├── deposit_trail() ◄─────────────┤
    │   └── follow_trail() ◄──────────────┤
    │                                      │
    ├── CognitiveOrchestrator ────────────┤
    │   └── process_message()             │
    │                                      │
    └── ServiceRouter (NEW) ──────────────┤
        ├── CalendarMCP                   │
        ├── TasksMCP                      │
        └── EmailMCP                      │
                                          │
                                          ▼
                                    OTTOMemory
                                   (Central Hub)
```

---

*Audit completed: 2026-02-02*
