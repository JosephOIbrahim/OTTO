# OTTO

OTTO watches your WhatsApp messages.
When you make a commitment ("I'll send that Monday"), OTTO remembers.
When you haven't followed through, OTTO asks — without judgment.

## Quick Start

```bash
cd otto_v4
pip install -e ".[dev]"
otto list
```

## Commands

```
otto list                 Show active commitments
otto list --all           Show all including done/parked
otto list --due           Show only overdue
otto add "text"           Manually add a commitment
otto done <id>            Mark commitment as done
otto park <id>            Park a commitment (guilt-free)
otto nudge                Run follow-up check now
otto stats                Counts and follow-through stats
otto watch                Start WhatsApp webhook server
otto nuke                 Delete ALL data. Fresh start.
```

## How It Works

```
MESSAGE IN --> DETECT --> STORE --> WAIT --> FOLLOW UP --> UPDATE
 (WhatsApp)  (Claude)  (SQLite)  (cron)   (template)   (count++)
```

- **Input:** WhatsApp Cloud API webhooks via FastAPI
- **Detection:** Claude Sonnet extracts commitments from messages
- **Storage:** SQLite (`~/.otto/commitments.db`), no ORM
- **Follow-up:** Template-based nudges, zero LLM cost, 24h cooldown
- **Interface:** Click CLI

## Tests

```bash
cd otto_v4
python -m pytest tests/ -v -m "not integration"   # 92 tests
python -m pytest tests/ -v                         # includes real API tests
```

## License

MIT
