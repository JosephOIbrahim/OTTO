<p align="center">
  <img src="logo.png" alt="OTTO OS" width="200">
</p>

<h1 align="center">OTTO OS</h1>

<p align="center">
  <strong>The Cognitive Operating System for Variable Attention</strong>
</p>

<p align="center">
  <a href="#quick-start"><img src="https://img.shields.io/badge/status-production%20ready-brightgreen.svg" alt="Production Ready"></a>
  <a href="#"><img src="https://img.shields.io/badge/tests-4,392%20passing-success.svg" alt="4,392 Tests"></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python 3.10+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License"></a>
  <a href="#"><img src="https://img.shields.io/badge/version-0.7.0-orange.svg" alt="Version 0.7.0"></a>
</p>

<p align="center">
  <a href="#security"><img src="https://img.shields.io/badge/encryption-AES--256--GCM-purple.svg" alt="AES-256-GCM"></a>
  <a href="#"><img src="https://img.shields.io/badge/%5BHe2025%5D-inspired-blueviolet.svg" alt="Inspired by [He2025]"></a>
  <a href="#platform-support"><img src="https://img.shields.io/badge/platforms-Discord%20%7C%20WhatsApp%20%7C%20Telegram%20%7C%20CLI-informational.svg" alt="Multi-Platform"></a>
</p>

<p align="center">
  <em>Where neurodivergence is the native architecture, not an afterthought.</em>
</p>

---

## Why OTTO?

Most AI assistants assume human attention is linear and infinite. **OTTO knows better.**

```
You: "My name is Joe"
OTTO: "Nice to meet you, Joe."

[... hours later ...]

You: "What's my name?"
OTTO: "Joe."
```

**OTTO remembers.** Across sessions. Across platforms. Without cloud surveillance.

---

## Production Metrics

| Metric | Value |
|--------|-------|
| **Test Coverage** | 4,392 tests across 157 files |
| **Platforms** | Discord, WhatsApp, Telegram, CLI, Web |
| **Response Latency** | <800ms (cognitive pipeline) |
| **Memory Persistence** | SQLite-backed trail storage |
| **Encryption** | AES-256-GCM at rest |
| **Determinism** | [He2025]-inspired determinism, batch-invariant |

---

## Quick Start

```bash
# Clone
git clone https://github.com/JosephOIbrahim/otto-os.git
cd otto-os

# Install
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Add your API keys to .env

# Run Discord Bot
python -m otto.discord.bot

# Or run CLI
otto
```

**That's it.** OTTO is running.

---

## What Makes OTTO Different

### 1. Cognitive Safety Layer

OTTO detects your state and adapts automatically:

| Your State | OTTO's Response |
|------------|-----------------|
| Overwhelmed | Reduces options to 3 choices |
| Frustrated | Validates feelings before problem-solving |
| In flow | Disappears completely |
| Depleted | Suggests rest without guilt-tripping |
| Lost | Remembers where you left off |

### 2. Seven Expert Modes

```
Validator   → "That sounds frustrating."
Scaffolder  → "Let's break this into smaller steps."
Restorer    → "Permission granted to stop."
Refocuser   → "Back to what we were doing..."
Celebrator  → "You did it!"
Socratic    → "What if we tried..."
Direct      → [stays out of the way]
```

### 3. Persistent Memory

Every conversation is stored locally and retrieved for context:

```
Episode → TrailStore (SQLite) → Query → Claude API
    ↑                                      ↓
    └──────── Conversation Loop ───────────┘
```

### 4. Dignity-First Language

OTTO never says:
- "Executive dysfunction detected"
- "Burnout risk: HIGH"
- "Session limit exceeded"

OTTO says:
- "You seem tired"
- "Let's slow down"
- "Want to continue tomorrow?"

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           OTTO OS v0.7.0                                    │
│                     Production-Ready Cognitive OS                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     PLATFORM ADAPTERS                                │    │
│  │  Discord │ WhatsApp │ Telegram │ CLI │ Web Dashboard │ MCP          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    COGNITIVE ORCHESTRATOR                            │    │
│  │                                                                      │    │
│  │   DETECT → CASCADE → LOCK → EXECUTE → UPDATE                        │    │
│  │     │         │        │        │         │                         │    │
│  │   PRISM    Safety    MAX3    Claude    Trail                        │    │
│  │  Signals   Gates    Bounds    API     Update                        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      MEMORY BACKBONE                                 │    │
│  │                                                                      │    │
│  │   OTTOMemory ─── TrailStore ─── SQLite ─── Encryption               │    │
│  │       │              │             │            │                    │    │
│  │    Episodes      Deposits      trails.db   AES-256-GCM              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Platform Support

### Discord Bot

```python
# Automatically handles:
# - Message history retrieval
# - Session persistence
# - Multi-user isolation
# - Cognitive state tracking

python -m otto.discord.bot
```

**Features:**
- Slash commands (`/otto`, `/status`, `/services`)
- Mention-based interaction (`@OTTO help me`)
- Per-user conversation memory
- Burnout detection and intervention

### WhatsApp Voice

```bash
python -m otto.whatsapp.server --port 8000
```

**Features:**
- Voice message transcription (Whisper)
- Text-to-speech responses (OpenAI TTS)
- <10 second latency target
- ~$0.22/user/day (20 interactions)

### Telegram

```python
from otto.telegram import create_telegram_adapter

adapter = create_telegram_adapter()
await adapter.start()
```

**Features:**
- MCP service integration (calendar, tasks, email)
- Inline button approvals
- Adaptive response pacing

### CLI

```bash
otto          # Interactive session
otto status   # Show cognitive state
otto tui      # TUI dashboard
```

---

## Security

### Encryption at Rest

All cognitive data is encrypted using AES-256-GCM:

```
trails.db        → trails.db.enc
sessions.json    → encrypted JSON
user profiles    → encrypted storage
```

### Key Derivation

```
Passphrase → Argon2id(64MB, 3 iterations, 4 parallelism) → 256-bit key
```

### Setup

```bash
otto encryption setup    # Initialize encryption
otto encryption unlock   # Unlock at session start
otto encryption status   # Check status
```

---

## Configuration

### Environment Variables

```bash
# Required for LLM
ANTHROPIC_API_KEY=sk-ant-...

# Platform-specific
DISCORD_BOT_TOKEN=...
WHATSAPP_TOKEN=...
TELEGRAM_BOT_TOKEN=...

# Optional (voice features)
OPENAI_API_KEY=sk-...
```

### State Storage

```
~/.otto/
├── profile.usda          # Personality profile
├── calibration/          # Learned patterns
├── sessions/             # Session history
├── trails.db             # Cognitive trails (SQLite)
└── .keys/                # Encryption keys
```

---

## Development

### Running Tests

```bash
# All 4,392 tests
pytest

# With coverage
pytest --cov=src/otto --cov-report=html

# Determinism tests only
pytest -m determinism

# Specific module
pytest tests/test_discord/ -v
```

### Project Structure

```
otto-os/
├── src/otto/
│   ├── cognitive_orchestrator.py   # NEXUS pipeline
│   ├── prism_detector.py           # Signal detection
│   ├── expert_router.py            # Mode routing
│   ├── memory/                     # Memory backbone
│   │   └── interface.py            # OTTOMemory singleton
│   ├── discord/                    # Discord adapter
│   │   ├── adapter.py              # Message processing
│   │   └── bot.py                  # Bot runner
│   ├── whatsapp/                   # WhatsApp integration
│   ├── telegram/                   # Telegram integration
│   ├── llm/                        # LLM providers
│   │   ├── provider.py             # Base protocol
│   │   ├── claude_provider.py      # Anthropic Claude
│   │   └── response_generator.py   # Context-aware generation
│   ├── trails/                     # SQLite trail storage
│   └── encryption/                 # Security layer
├── tests/                          # 4,392 tests
├── docs/                           # Documentation
└── deploy/                         # Deployment configs
```

---

## Determinism (Inspired by [He2025])

OTTO applies [He2025] principles at the application layer, not at GPU kernel level:

| Principle | Implementation |
|-----------|----------------|
| Fixed evaluation order | 5-phase NEXUS pipeline |
| Batch-invariant | COGNITIVE_TILE_SIZE=32 |
| Deterministic routing | First-match-wins semantics |
| Reproducible checksums | `[EXEC:6bb68d\|direct\|Cortex\|30000ft\|standard]` |

**Same inputs → Same routing → Same behavior**

---

## Philosophy

```
1. Safety first        → Emotional safety before productivity
2. Ship over perfect   → Working beats polished
3. Protect momentum    → Don't break flow unnecessarily
4. External memory     → Write it down, don't hold it in your head
5. Recover without guilt → Rest is productive
6. No labels           → Human states, not clinical categories
```

---

## The Stealth Accommodation

OTTO was designed from the inside by neurodivergent engineers.

But there are no "ADHD modes." No "productivity timers." No diagnostic language.

Just a system that quietly:
- Limits choices when decision fatigue is detected
- Offers rest before burnout arrives
- Remembers where you left off

Like curb cuts designed for wheelchairs but used by everyone with strollers and luggage, OTTO's architecture benefits **all humans** with variable attention.

---

## Contributing

```bash
git clone https://github.com/JosephOIbrahim/otto-os.git
cd otto-os
pip install -e ".[dev]"
pytest  # Verify setup
```

**Code of Conduct:**
- Dignity-first (no pathologizing language)
- Privacy-respecting (no telemetry without consent)
- Inclusive (designed for variable attention)

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Acknowledgments

- **[Orchestra](https://github.com/JosephOIbrahim/Orchestra)** — Cognitive orchestration foundation
- **[Pixar USD](https://graphics.pixar.com/usd/)** — Composition semantics inspiration
- **[[He2025]](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/)** — Determinism principles

---

<p align="center">
  <strong>"The goal isn't to make you more productive.<br>The goal is to make computing work with your brain, not against it."</strong>
</p>

<p align="center">
  <a href="https://github.com/JosephOIbrahim/otto-os">GitHub</a> •
  <a href="https://github.com/JosephOIbrahim/otto-os/issues">Issues</a> •
  <a href="docs/">Documentation</a>
</p>

<p align="center">
  <sub>Built with care for minds that work differently.</sub>
</p>
