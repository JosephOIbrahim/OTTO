# OTTO

OTTO watches your WhatsApp messages.
When you make a commitment ("I'll send that Monday"), OTTO remembers.
When you haven't followed through, OTTO asks — without judgment.

## Quick Start

```bash
cd otto_v4
pip install -e ".[dev]"
otto list
otto watch
```

## Commands

```
otto list                 Show active commitments
otto list --all           Show all including done/parked
otto list --due           Show only overdue
otto done <id>            Mark commitment as done
otto park <id>            Park a commitment (guilt-free)
otto add "text"           Manually add a commitment
otto nudge                Run follow-up check now
otto stats                Counts and follow-through stats
otto nuke                 Delete ALL data. Fresh start.
```
