# OTTO OS Quickstart Guide

**Version 0.6.0**

Get OTTO OS running in 5 minutes.

---

## What Is OTTO OS?

OTTO OS is an operating system for **variable attention**. It tracks your cognitive state and adjusts its behavior:

| When you're... | OTTO quietly... |
|----------------|-----------------|
| Frustrated | Validates before problem-solving |
| Overwhelmed | Reduces options, breaks things down |
| Depleted | Offers easy wins, permits rest |
| In flow | Disappears completely |

---

## Install (1 minute)

```bash
# Clone and install
git clone https://github.com/your-org/otto-os.git
cd otto-os
pip install -e ".[dev]"

# Verify installation
otto --version
```

---

## First Run: Intake (10 minutes)

OTTO learns how you work through a brief scenario-based game:

```bash
otto-intake
```

The intake asks about:
- When you're naturally sharp (chronotype)
- How you prefer to work (deep focus vs. task switching)
- How you handle stress
- What helps when you're depleted

**No clinical language. No diagnostic framing.** Just scenarios and choices.

---

## Daily Usage

### Interactive Mode

```bash
otto
```

Start a conversation. OTTO will adapt to your state.

### Quick Status

```bash
otto status
```

```
┌─────────────────────────────────────────┐
│ OTTO STATUS                             │
│ Energy: medium | Burnout: GREEN         │
│ Momentum: building | Mode: focused      │
│ Integrations: 2 active                  │
└─────────────────────────────────────────┘
```

### TUI Dashboard

```bash
otto tui
```

Beautiful terminal dashboard showing your full state.

---

## The Seven Experts

OTTO routes to different modes based on your signals:

| Expert | When It Activates | What It Does |
|--------|-------------------|--------------|
| **Validator** | Frustration, ALL CAPS | Empathy first |
| **Scaffolder** | Overwhelm, stuck | Breaks things down |
| **Restorer** | Exhaustion, depleted | Easy wins, rest OK |
| **Refocuser** | Tangent, drift | Gentle redirect |
| **Celebrator** | Completion, milestone | Acknowledges win |
| **Socratic** | Exploring, "what if" | Guides discovery |
| **Direct** | Flow, focused | Stays out of way |

---

## Burnout Colors

| Color | Meaning | What OTTO Does |
|-------|---------|----------------|
| GREEN | You're good | Normal operation |
| YELLOW | Getting tired | "Quick break soon?" |
| ORANGE | Burning out | "What's blocking you?" |
| RED | Done for today | Full stop, recovery mode |

---

## Quick Commands

```bash
# Set your state manually
otto set -b YELLOW        # Mark as getting tired
otto set -e low           # Set energy to low

# Protection controls
otto protect --status     # See protection state
otto protect --override   # Acknowledge and continue

# Session management
otto session save         # Save current session
otto session restore      # Resume where you left off

# Knowledge
otto remember "Important thing"  # Store knowledge
otto recall "thing"              # Retrieve knowledge
```

---

## Add Integrations (Optional)

OTTO can read your calendar and tasks for context awareness:

```bash
# Calendar (ICS file)
otto integrations add calendar --file ~/calendar.ics

# Tasks (JSON file)
otto integrations add tasks --file ~/tasks.json

# Check status
otto integrations status
```

See [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) for details.

---

## Configuration

```bash
# View config
otto config list

# Change protection firmness (0.0 gentle, 1.0 firm)
otto config set protection.firmness 0.5

# Change theme
otto config set display.theme dark
```

Config file: `~/.otto/config/otto.yaml`

---

## Troubleshooting

### "Command not found: otto"

```bash
# Check pip install location
pip show otto-os

# Ensure ~/.local/bin is in PATH
export PATH="$HOME/.local/bin:$PATH"
```

### "State seems wrong"

```bash
# Reset to healthy state
otto set -b GREEN -e high

# Or clear session entirely
otto session clear
```

### "Want to start over"

```bash
# Wipe everything
otto wipe --confirm

# Re-run intake
otto-intake
```

---

## Next Steps

- **Full User Guide**: [USER_GUIDE.md](USER_GUIDE.md)
- **Integration Setup**: [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)
- **Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md)
- **Contributing**: [CONTRIBUTING.md](../CONTRIBUTING.md)

---

*OTTO OS v0.6.0 - Built for humans who think differently*
