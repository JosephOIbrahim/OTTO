# OTTO OS

<p align="center">
  <strong>An Operating System for Variable Attention</strong>
</p>

<p align="center">
  <a href="#installation"><img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python 3.10+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License"></a>
  <a href="https://github.com/JosephOIbrahim/otto-os/releases"><img src="https://img.shields.io/badge/version-0.7.0-orange.svg" alt="Version 0.7.0"></a>
  <a href="#security"><img src="https://img.shields.io/badge/encryption-AES--256--GCM-purple.svg" alt="AES-256-GCM"></a>
</p>

<p align="center">
  <em>The first OS where neurodivergence is the native architecture.</em>
</p>

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Platform Integrations](#platform-integrations)
- [CLI Reference](#cli-reference)
- [Architecture](#architecture)
- [Security](#security)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

---

## Overview

Most productivity tools assume human attention is linear and infinite.

OTTO OS assumes what neuroscience already knows: attention fluctuates, crashes, surges, and drifts—and that variation is **feature, not failure**.

| When you're... | OTTO quietly... |
|----------------|-----------------|
| Overwhelmed | Reduces options to three |
| Distressed | Validates before problem-solving |
| Lost | Preserves context across sessions |
| Depleted | Offers rest before burnout arrives |
| In flow | Disappears completely |

### The Stealth Accommodation

OTTO OS was designed from the inside by neurodivergent engineers, but it **never labels the user**.

There are no "ADHD modes." No "productivity timers." No diagnostic language.

Just a system that quietly:
- Limits choices when decision fatigue is detected
- Offers rest before burnout arrives
- Remembers where you left off without making you feel broken

Like curb cuts designed for wheelchairs but used by everyone with strollers and luggage, OTTO's neurodivergent-native architecture benefits **all humans** who have off-days, crash cycles, or non-linear work patterns.

### Privacy-First, Dignity-First

Your cognitive profile lives **locally**—not in a medical database, not on a cloud server, not anywhere you haven't explicitly chosen.

OTTO speaks in human states:
- *"You seem tired"* — not "executive dysfunction detected"
- *"Let's slow down"* — not "burnout risk: HIGH"
- *"Want to continue tomorrow?"* — not "session limit exceeded"

---

## Features

### Cognitive Safety Layer
- **7 Specialist Modes**: Validator, Scaffolder, Restorer, Refocuser, Celebrator, Socratic, Direct
- **Burnout Detection**: GREEN → YELLOW → ORANGE → RED with automatic intervention
- **Momentum Tracking**: cold_start → building → rolling → peak → crashed
- **Safety Gating**: Your state overrides your requests (depleted → minimal depth)

### Deterministic Routing ([He2025] Compliant)
- **5-Phase NEXUS Pipeline**: DETECT → CASCADE → LOCK → EXECUTE → UPDATE
- **Fixed Evaluation Order**: Same signals → same behavior, every time
- **Batch-Invariant Processing**: COGNITIVE_TILE_SIZE=32, Kahan summation

### Multi-Platform Support
- **CLI**: Primary interface with TUI dashboard
- **WhatsApp**: Voice and text messaging (2B+ users)
- **Discord**: Bot integration for communities
- **Telegram**: Bot integration for personal use
- **Web Dashboard**: PWA with offline support

### Security (v0.7.0)
- **Encryption at Rest**: AES-256-GCM for all cognitive data
- **Argon2id Key Derivation**: Memory-hard password hashing
- **Secure Key Storage**: OS keyring integration
- **Post-Quantum Ready**: X25519 with optional ML-KEM hybrid

### Voice Integration
- **Speech-to-Text**: OpenAI Whisper with deterministic normalization
- **Text-to-Speech**: OpenAI TTS with 6 voice options
- **5-Phase Speech Pipeline**: Format removal → Abbreviation expansion → Number conversion → Speech markers → Cleanup

---

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# First run: Personality intake (10 min)
otto-intake

# Daily use
otto

# Status check
otto status

# TUI Dashboard
otto tui
```

---

## Installation

### Requirements
- Python 3.10 or higher
- 50MB disk space (plus ~500MB for optional voice models)
- Windows, macOS, or Linux

### Standard Installation

```bash
# Clone the repository
git clone https://github.com/JosephOIbrahim/otto-os.git
cd otto-os

# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or: .venv\Scripts\activate  # Windows

# Install with development dependencies
pip install -e ".[dev]"

# Verify installation
otto status
```

### Optional Dependencies

```bash
# TUI dashboard (Textual-based)
pip install -e ".[tui]"

# Post-quantum cryptography (requires liboqs system library)
pip install -e ".[frontier]"

# All optional dependencies
pip install -e ".[dev,tui]"
```

### Platform-Specific Notes

**Windows:**
```powershell
# Ensure long path support is enabled
git config --system core.longpaths true
```

**macOS:**
```bash
# If using Homebrew Python
brew install python@3.11
```

**Linux:**
```bash
# Install keyring dependencies (for secure credential storage)
sudo apt-get install libsecret-1-0 gnome-keyring  # Debian/Ubuntu
sudo dnf install libsecret gnome-keyring          # Fedora
```

---

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | For voice | OpenAI API key (Whisper STT, TTS) |
| `ANTHROPIC_API_KEY` | For LLM | Anthropic API key (Claude responses) |
| `WHATSAPP_TOKEN` | For WhatsApp | WhatsApp Cloud API access token |
| `WHATSAPP_PHONE_NUMBER_ID` | For WhatsApp | WhatsApp Business phone number ID |
| `WHATSAPP_VERIFY_TOKEN` | For WhatsApp | Webhook verification token |
| `DISCORD_BOT_TOKEN` | For Discord | Discord bot token |
| `TELEGRAM_BOT_TOKEN` | For Telegram | Telegram bot token |

### Encryption Setup

```bash
# Initialize encryption (first time only)
otto encryption setup

# Unlock at start of session
otto encryption unlock

# Migrate existing data to encrypted storage
otto encryption migrate

# Check encryption status
otto encryption status
```

### State Files

OTTO stores state in `~/.otto/`:

```
~/.otto/
├── profile.usda          # Your personality profile
├── calibration/          # Learned patterns over time
├── sessions/             # Session context and history
├── trails.db.enc         # Encrypted cognitive trails
└── .keys/                # Encryption keys (protected)
```

---

## Platform Integrations

### WhatsApp Voice

Enable 2 billion users to interact with OTTO via voice messages.

```bash
# Start WhatsApp voice server
python -m otto.whatsapp.server --port 8000
```

**Or mount to existing FastAPI app:**

```python
from otto.whatsapp import get_whatsapp_router

app.include_router(get_whatsapp_router(), prefix="/webhook")
```

**Target Metrics:**
- Latency: <10 seconds end-to-end
- Cost: ~$0.22/user/day (20 voice interactions)

### Discord

```python
from otto.discord import create_discord_adapter

adapter = create_discord_adapter()
await adapter.start()
```

### Telegram

```python
from otto.telegram import create_telegram_adapter

adapter = create_telegram_adapter()
await adapter.start()
```

### Web Dashboard

```bash
# Start dashboard server
cd deploy/dashboard
python server.py --port 8080
```

Open `http://localhost:8080` in your browser.

---

## CLI Reference

### Core Commands

| Command | Description |
|---------|-------------|
| `otto` | Start interactive OTTO session |
| `otto status` | Show current cognitive state |
| `otto tui` | Launch TUI dashboard |
| `otto-intake` | Run personality intake questionnaire |

### Encryption Commands

| Command | Description |
|---------|-------------|
| `otto encryption setup` | Initialize encryption with passphrase |
| `otto encryption unlock` | Unlock encrypted storage |
| `otto encryption lock` | Lock encrypted storage |
| `otto encryption status` | Show encryption status |
| `otto encryption migrate` | Migrate plaintext data to encrypted |
| `otto encryption rotate` | Rotate encryption keys |

### Development Commands

| Command | Description |
|---------|-------------|
| `otto debug` | Show debug information |
| `otto calibrate` | Run calibration sequence |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              OTTO OS v0.7.0                                 │
│                    "Variable Attention as Native Architecture"              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  COMMUNICATION LAYERS                                                       │
│  ────────────────────                                                       │
│  Layer 2: Human Render    │ Natural language, dignity-first                │
│  Layer 1: OTTO Core       │ JSON-RPC, structured, inspectable              │
│  Layer 0: Agent Kernel    │ Binary protocol, machine-speed                 │
│                                                                             │
│  COGNITIVE SUBSTRATE (USD-Based)                                            │
│  ───────────────────────────────                                            │
│  • 5-phase deterministic pipeline (NEXUS)                                   │
│    DETECT → CASCADE → LOCK → EXECUTE → UPDATE                              │
│  • 7 specialist modes with fixed priority routing                          │
│  • USD personality profiles with LIVRPS composition                        │
│  • Trail-based learning with batch-invariant updates                       │
│                                                                             │
│  PLATFORM ADAPTERS                                                          │
│  ─────────────────                                                          │
│  WhatsApp │ Discord │ Telegram │ CLI │ Web Dashboard │ MCP                 │
│                                                                             │
│  SECURITY LAYER                                                             │
│  ──────────────                                                             │
│  • AES-256-GCM encryption at rest                                          │
│  • Argon2id key derivation (64MB memory, 3 iterations)                     │
│  • OS keyring integration for secure key storage                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### The Seven Modes

| Mode | Trigger | Response |
|------|---------|----------|
| **Validator** | frustrated, RED, caps | Empathy first. Always. |
| **Scaffolder** | overwhelmed, stuck | Breaks things down. Reduces scope. |
| **Restorer** | depleted, ORANGE | Easy wins. Permission to stop. |
| **Refocuser** | distracted, tangent_over | Gentle redirect. No judgment. |
| **Celebrator** | task_complete | Acknowledges the win. |
| **Socratic** | exploring, "what if" | Follows your threads. |
| **Direct** | focused, flow | Stays out of the way. |

### NEXUS Pipeline

```
Phase 0:  RETRIEVE   → Knowledge fast path (O(1) retrieval)
Phase 0b: CLASSIFY   → LEARN | ACCESS | HYBRID mode selection
Phase 0c: GROUND     → Oracle query if ACCESS mode
Phase 1:  DETECT     → PRISM signal extraction
Phase 2:  CASCADE    → Expert routing with safety gates
Phase 3:  LOCK       → Parameter locking (MAX3 bounds)
Phase 4:  EXECUTE    → Response generation
Phase 5:  UPDATE     → Convergence tracking
[Post]:   FLUSH      → Batch apply trail updates
```

---

## Security

### Encryption at Rest (v0.7.0)

All cognitive data is encrypted using AES-256-GCM:

- **trails.db** → `trails.db.enc`
- **Discord sessions** → encrypted JSON
- **Telegram sessions** → encrypted JSON

### Key Derivation

```
Passphrase → Argon2id(64MB, 3 iterations, 4 parallelism) → 256-bit key
```

### Threat Model

| Threat | Mitigation |
|--------|------------|
| Disk theft | AES-256-GCM encryption |
| Memory dump | Argon2id memory hardness |
| Brute force | Rate limiting, high iteration count |
| Key exposure | OS keyring storage |

### Security Commands

```bash
# Check security status
otto encryption status

# Rotate encryption keys
otto encryption rotate

# Emergency lock
otto encryption lock
```

---

## Development

### Project Structure

```
otto-os/
├── src/otto/                 # Main source code
│   ├── cognitive_orchestrator.py  # NEXUS pipeline
│   ├── prism_detector.py     # Signal detection
│   ├── expert_router.py      # Mode routing
│   ├── voice_core/           # STT/TTS pipeline
│   ├── whatsapp/             # WhatsApp integration
│   ├── discord/              # Discord integration
│   ├── telegram/             # Telegram integration
│   ├── encryption/           # Security layer
│   └── trails/               # Cognitive trails
├── tests/                    # Test suite
├── deploy/                   # Deployment configs
└── packages/                 # MCP packages
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/otto --cov-report=html

# Run specific test file
pytest tests/test_cognitive_orchestrator.py -v

# Run determinism tests only
pytest -m determinism
```

### Code Style

```bash
# Format code
black src/ tests/

# Check types
mypy src/otto

# Lint
ruff check src/ tests/
```

### Building Documentation

```bash
cd docs
make html
```

---

## Troubleshooting

### Common Issues

**"liboqs not found" warning:**
```
This is expected if you haven't installed post-quantum cryptography.
OTTO falls back to classical X25519 encryption, which is still secure.
To install: pip install liboqs-python (requires liboqs system library)
```

**"USD Python bindings not available":**
```
This is expected. OTTO uses a mock USD implementation by default.
For full USD support, install: pip install usd-core
```

**Encryption unlock fails:**
```bash
# Reset encryption state (WARNING: loses encrypted data)
rm -rf ~/.otto/.keys ~/.otto/*.enc

# Re-run setup
otto encryption setup
```

**WhatsApp webhook not receiving messages:**
```
1. Verify WHATSAPP_TOKEN and WHATSAPP_PHONE_NUMBER_ID are set
2. Ensure webhook URL is publicly accessible (use ngrok for local dev)
3. Check webhook verification token matches WHATSAPP_VERIFY_TOKEN
```

### Debug Mode

```bash
# Enable verbose logging
OTTO_LOG_LEVEL=DEBUG otto status

# Show routing decisions
otto debug --show-routing
```

### Getting Help

- [GitHub Issues](https://github.com/JosephOIbrahim/otto-os/issues)
- [Documentation](docs/)

---

## Contributing

OTTO OS welcomes contributors who understand that variable attention is not a bug to be fixed.

### Development Setup

```bash
# Clone and install
git clone https://github.com/JosephOIbrahim/otto-os.git
cd otto-os
pip install -e ".[dev]"

# Run tests to verify setup
pytest
```

### Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`pytest`)
5. Commit with conventional commits (`feat:`, `fix:`, `docs:`, etc.)
6. Push and create a Pull Request

### Code of Conduct

- **Dignity-first**: No pathologizing language
- **Privacy-respecting**: No telemetry without consent
- **Inclusive**: Designed for variable attention patterns

---

## Philosophy

1. **Safety first** — Emotional safety before productivity
2. **Ship over perfect** — Working beats polished
3. **Protect momentum** — Don't break flow unnecessarily
4. **External memory** — Write it down, don't hold it in your head
5. **Recover without guilt** — Rest is productive
6. **No labels** — Human states, not clinical categories

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Acknowledgments

### Technical Foundation

OTTO OS is built on the foundations of [Orchestra](https://github.com/JosephOIbrahim/Orchestra), a cognitive orchestration system with 1,494 tests and production-hardened architecture.

### Universal Scene Description (USD)

OTTO's cognitive substrate uses concepts inspired by Pixar's Universal Scene Description.

```
Copyright (c) 2016-2024 Pixar.
Licensed under the Apache License, Version 2.0.
https://github.com/PixarAnimationStudios/USD
```

### Deterministic LLM Inference

OTTO implements application-level determinism principles from:

```bibtex
@article{he2025defeating,
  title={Defeating Non-determinism in LLM Inference},
  author={He, Horace},
  journal={Thinking Machines Lab},
  year={2025},
  month={September},
  url={https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/}
}
```

See [THINKINGMACHINES_COMPLIANCE.md](THINKINGMACHINES_COMPLIANCE.md) for implementation details.

---

<p align="center">
  <em>"The goal isn't to make you more productive. The goal is to make computing work with your brain, not against it."</em>
</p>

<p align="center">
  <a href="https://github.com/JosephOIbrahim/otto-os">GitHub</a> •
  <a href="https://github.com/JosephOIbrahim/otto-os/issues">Issues</a> •
  <a href="docs/">Documentation</a>
</p>
