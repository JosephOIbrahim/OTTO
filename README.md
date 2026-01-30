# OTTO OS

<p align="center">
  <strong>An Operating System for Variable Attention</strong>
</p>

<p align="center">
  <em>The first OS where neurodivergence is the native architecture.</em>
</p>

---

Most productivity tools assume human attention is linear and infinite.

OTTO OS assumes what neuroscience already knows: attention fluctuates, crashes, surges, and drifts—and that variation is **feature, not failure**.

---

## What Is This?

OTTO OS is a personal computing layer built on a proprietary cognitive substrate (USD-based). A conductor-like interface called OTTO detects your cognitive state—focused, scattered, exhausted, curious—and orchestrates specialist AI modes to match it.

| When you're... | OTTO quietly... |
|----------------|-----------------|
| Overwhelmed | Reduces options to three |
| Distressed | Validates before problem-solving |
| Lost | Preserves context across sessions |
| Depleted | Offers rest before burnout arrives |
| In flow | Disappears completely |

## The Stealth Accommodation

OTTO OS was designed from the inside by neurodivergent engineers, but it **never labels the user**.

There are no "ADHD modes." No "productivity timers." No diagnostic language.

Just a system that quietly:
- Limits choices when decision fatigue is detected
- Offers rest before burnout arrives
- Remembers where you left off without making you feel broken

Like curb cuts designed for wheelchairs but used by everyone with strollers and luggage, OTTO's neurodivergent-native architecture benefits **all humans** who have off-days, crash cycles, or non-linear work patterns.

## Privacy-First, Dignity-First

Your cognitive profile lives **locally**—not in a medical database, not on a cloud server, not anywhere you haven't explicitly chosen.

OTTO speaks in human states:
- *"You seem tired"* — not "executive dysfunction detected"
- *"Let's slow down"* — not "burnout risk: HIGH"
- *"Want to continue tomorrow?"* — not "session limit exceeded"

**OTTO is the first operating system that treats variable attention as a hardware feature to be orchestrated, not a pathology to be corrected.**

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              OTTO OS                                         │
│                    "Variable Attention as Native Architecture"               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  COMMUNICATION LAYERS                                                        │
│  ────────────────────                                                        │
│  Layer 2: Human Render    │ Natural language, dignity-first                 │
│  Layer 1: OTTO Core       │ JSON-RPC, structured, inspectable               │
│  Layer 0: Agent Kernel    │ Binary protocol, machine-speed                  │
│                                                                              │
│  COGNITIVE SUBSTRATE (USD-Based)                                             │
│  ───────────────────────────────                                             │
│  • 5-phase deterministic pipeline                                            │
│    DETECT → CASCADE → LOCK → EXECUTE → UPDATE                               │
│  • 7 specialist modes (see below)                                           │
│  • USD personality profiles with LIVRPS composition                         │
│  • Adaptive protection that learns your patterns                            │
│                                                                              │
│  STATE PERSISTENCE                                                           │
│  ─────────────────                                                           │
│  ~/.otto/profile.usda     │ Your personality (from intake)                  │
│  ~/.otto/calibration/     │ Learned patterns over time                      │
│  ~/.otto/sessions/        │ Context continuity                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## The Seven Modes

OTTO automatically routes to the mode that matches your state:

| Mode | When Active | What It Does |
|------|-------------|--------------|
| **Validator** | You're upset | Empathy first. Always. |
| **Scaffolder** | You're stuck | Breaks things down. Reduces scope. |
| **Restorer** | You're depleted | Easy wins. Permission to stop. |
| **Refocuser** | You've drifted | Gentle redirect. No judgment. |
| **Celebrator** | You've finished | Acknowledges the win. |
| **Socratic** | You're curious | Follows your threads. |
| **Direct** | You're in flow | Stays out of the way. |

**No mode is better than another.** They're all just different responses to different human states.

---

## Getting Started

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

The intake is a brief experience that helps OTTO understand how you work—without diagnostic language, without clinical framing. Just scenarios and choices.

**Documentation:**
- [Quickstart Guide](docs/QUICKSTART.md) - Get running in 5 minutes
- [User Guide](docs/USER_GUIDE.md) - Complete usage documentation
- [Integration Guide](docs/INTEGRATION_GUIDE.md) - Connect calendar, tasks, and more
- [Architecture](docs/ARCHITECTURE.md) - Technical deep-dive

---

## Technical Foundation

OTTO OS is built on the foundations of [Orchestra](https://github.com/JosephOIbrahim/Orchestra), a cognitive orchestration system with 917 tests and production-hardened architecture. We've refactored it from a developer-focused tool into a general-purpose personal OS.

### Key Properties

- **Deterministic routing**: Same signals → same behavior, every time
- **Safety gating**: Your state overrides your requests (depleted → minimal depth)
- **Session continuity**: Pick up where you left off, always
- **USD composition**: Personality layers compose via LIVRPS priority
- **Adaptive protection**: OTTO learns when you ignore nudges and adjusts

### Communication Layers

```
Agent ↔ Agent:  Binary protocol (MessagePack/Protobuf) — fastest
Agent ↔ Core:   JSON-RPC — structured, debuggable
Core ↔ Human:   Natural language — rendered only when needed
```

---

## Philosophy

1. **Safety first** — Emotional safety before productivity
2. **Ship over perfect** — Working beats polished
3. **Protect momentum** — Don't break flow unnecessarily
4. **External memory** — Write it down, don't hold it in your head
5. **Recover without guilt** — Rest is productive
6. **No labels** — Human states, not clinical categories

---

## The Future of Computing

We're not building an app.

We're building the first OS where **neurodivergence is the native architecture**, and neurotypical users simply experience it as:

*"Finally, a computer that gets me."*

---

## License

MIT

## Contributing

OTTO OS welcomes contributors who understand that variable attention is not a bug to be fixed.

---

<p align="center">
  <em>"The goal isn't to make you more productive. The goal is to make computing work with your brain, not against it."</em>
</p>
