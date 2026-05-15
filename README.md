# OTTO

OTTO watches your WhatsApp messages.
When you make a commitment ("I'll send that Monday"), OTTO remembers.
When you haven't followed through, OTTO asks — without judgment.

**"Manage the noise without falling into it."**

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
otto metrics              Mode learning + plasticity visibility
otto watch                Start WhatsApp webhook server
otto nuke                 Delete ALL data. Fresh start.
```

## Architecture

### Core loop

```mermaid
flowchart LR
    M[Message In<br/>WhatsApp]:::light --> D[Detect<br/>Opus 4.7]:::dark
    D --> S[Store<br/>SQLite WAL]:::light
    S --> SC[Schedule<br/>background thread]:::dark
    SC --> N[Nudge<br/>SHA256 template]:::light
    N --> CG{{Constitutional<br/>Gate}}:::dark
    CG -->|allow| O[Output<br/>CLI / WhatsApp]:::light
    CG -.->|suppress| Q[silence]:::light

    classDef dark fill:#1e293b,stroke:#1e293b,color:#fde68a
    classDef light fill:#fde68a,stroke:#1e293b,color:#1e293b
```

The **constitutional layer sits above all output.** Any nudge or action can be suppressed based on cognitive state — that is the product differentiator. OTTO can decide *not* to remind you.

### Mode routing (NEXUS, 5-phase deterministic)

```mermaid
flowchart TB
    SIG[PRISM Signals<br/>14 types, 9 pattern banks]:::dark --> R{{NEXUS Router<br/>ACTIVATE -> WEIGHT -> BOUND -> SELECT -> EXECUTE}}:::light
    R --> EX[Executor<br/>commitment tracking]:::dark
    R --> PR[Protector<br/>10% safety floor]:::dark
    R --> RS[Restorer<br/>5% floor — rest/explore]:::dark
    R --> DC[Decomposer<br/>5% floor — breakdown]:::dark
    EX --> OUT[Mode Output]:::light
    PR --> OUT
    RS --> OUT
    DC --> OUT
    OUT --> CGM{{Constitutional Gate}}:::dark
    CGM --> USR[User]:::light
    USR -.->|outcome trail| LRN[UCB1 Learner<br/>+ plasticity]:::dark
    LRN -.->|adjust weights| R

    classDef dark fill:#1e293b,stroke:#1e293b,color:#fde68a
    classDef light fill:#fde68a,stroke:#1e293b,color:#1e293b
```

Same signals + same state = same routing. No randomness in control flow. UCB1 learning is contextual but **deterministic given the trail history** — application-level determinism per Patent P1.

### LLM integration (Tier 1 — Opus 4.7 upgrade)

```mermaid
flowchart LR
    CFG[src/otto/model_config.py<br/>env-overridable<br/>TEMPERATURE = 0.0]:::dark

    CFG --> OP[Opus 4.7<br/>DETECTOR_MODEL]:::light
    CFG --> SN[Sonnet 4.6<br/>AGENT_MODEL]:::light
    CFG --> HK[Haiku 4.5<br/>RESPONSE_GEN_MODEL]:::light

    OP --> DET[detector.py<br/>commitment extraction<br/>prompt-cached system]:::dark
    SN --> AG[otto_agent loop<br/>tool-use orchestration<br/>prompt-cached system + tools]:::dark
    HK --> RG[response_gen.py<br/>optional rephrase<br/>gated by OTTO_LLM_RESPONSES]:::dark

    classDef dark fill:#1e293b,stroke:#1e293b,color:#fde68a
    classDef light fill:#fde68a,stroke:#1e293b,color:#1e293b
```

Every model surface is one env var away from rollback:

```powershell
$env:OTTO_DETECTOR_MODEL = "claude-sonnet-4-5-20250929"   # rollback example
```

## How It Works

- **Input:** WhatsApp Cloud API webhooks via FastAPI (`watcher.py`)
- **Detection:** Claude Opus 4.7 extracts commitments — nuance on "I'll try" vs "I will" drives confidence and nudge timing
- **Storage:** SQLite WAL (`~/.otto/commitments.db`), shared connection pool (`db.py`), Fernet-encrypted sensitive fields (`crypto.py`)
- **Follow-up:** Deterministic SHA256 template selection, 24h cooldown, zero LLM cost on the hot path
- **Routing:** PRISM signals (regex banks) -> NEXUS 5-phase router -> 4 modes -> Constitutional Gate
- **Learning:** UCB1 mode-weight learning with plasticity amplification during crisis (`learner.py`)
- **Agent:** Same logic, different surface — tool-use loop with 10 MCP tools, pre-tool-use constitutional hooks
- **Interface:** Click CLI + optional WhatsApp Cloud API outbound

## Constitutional Principles (Immutable)

1. **Safety First** — Protector has a 10% floor and can suppress any output
2. **Don't Become Noise** — backs off when nudges aren't leading to completions
3. **User Knows Best** — "Park it" is a first-class action, not failure
4. **Rest Is Productive** — can grant permission to stop
5. **One At A Time** — when overwhelmed, reduce to ONE choice
6. **Dignity Always** — no clinical labels, no "ADHD mode"
7. **Privacy Is Sovereignty** — all data local, no cloud sync

## Tests

```bash
cd otto_v4
python -m pytest tests/ -v -m "not integration"           # 589 core tests
python -m pytest otto_agent/tests/ -v                     # 56 agent tests
python -m pytest tests/ otto_agent/tests/ -v              # 645 total (needs ANTHROPIC_API_KEY for integration)
```

## License

MIT
