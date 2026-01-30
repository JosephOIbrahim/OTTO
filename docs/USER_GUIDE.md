# OTTO OS User Guide

**Version 0.6.0**

A complete guide to using OTTO OS, the operating system for variable attention.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Core Concepts](#core-concepts)
3. [CLI Commands](#cli-commands)
4. [The Seven Experts](#the-seven-experts)
5. [Protection System](#protection-system)
6. [Integrations](#integrations)
7. [Configuration](#configuration)
8. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Installation

```bash
# From source (recommended)
git clone https://github.com/your-org/otto-os.git
cd otto-os
pip install -e ".[dev]"
```

### First Run: Personality Intake

OTTO learns how you work through a brief scenario-based intake:

```bash
otto-intake
```

The intake takes about 10 minutes and covers:
- **Chronotype** - When you're naturally sharp vs. need protection
- **Work style** - Deep work, task switching, or burst patterns
- **Stress response** - How you handle overwhelm
- **Recovery preferences** - What helps when you're depleted

**No diagnostic language. No clinical framing.** Just scenarios and choices.

### Daily Use

```bash
# Start interactive session
otto

# Quick status check
otto status

# Launch TUI dashboard
otto tui
```

---

## Core Concepts

### Cognitive State

OTTO tracks several dimensions of your current state:

| Dimension | Values | What It Means |
|-----------|--------|---------------|
| **Energy** | high, medium, low, depleted | Your available cognitive capacity |
| **Burnout** | GREEN, YELLOW, ORANGE, RED | How close to overwhelm you are |
| **Momentum** | cold_start, building, rolling, peak, crashed | Session progress energy |
| **Mode** | focused, exploring, stuck, overwhelmed | Current working state |

### The Pipeline

Every interaction flows through OTTO's 5-phase pipeline:

```
DETECT → CASCADE → LOCK → EXECUTE → UPDATE
```

1. **DETECT** - Signals extracted from your input (emotional, energy, task)
2. **CASCADE** - Routes to the right expert based on signals
3. **LOCK** - Safety parameters locked before response
4. **EXECUTE** - Response generated with locked parameters
5. **UPDATE** - State updated for continuity

### LIVRPS Composition

Your personality is layered using USD composition semantics:

```
Session (highest priority)
    ↓
Calibration (learned patterns)
    ↓
Base Profile (from intake)
    ↓
System Defaults (lowest priority)
```

Higher layers override lower ones. OTTO learns your patterns over time.

---

## CLI Commands

### Session Commands

```bash
otto                    # Start interactive session
otto [message]          # Quick message, respond, exit
otto status             # Show current cognitive state
otto status --detailed  # Full state dump with all fields
otto status --json      # Machine-readable JSON output
```

### Intake Commands

```bash
otto-intake             # Run personality intake game
otto-intake --reset     # Reset profile and re-run intake
otto-intake --export    # Export profile as USD
```

### Configuration Commands

```bash
otto config                     # Open config in editor
otto config get [key]           # Get specific config value
otto config set [key] [value]   # Set config value
otto config list                # List all configuration
```

### Protection Commands

```bash
otto protect --status   # Show current protection state
otto protect --off      # Disable protection (session only)
otto protect --on       # Re-enable protection
otto protect --override # Acknowledge and continue despite warning
```

### State Management

```bash
otto set -b GREEN       # Set burnout level
otto set -b YELLOW      # Mark as getting tired
otto set -b ORANGE      # Mark as burning out
otto set -b RED         # Mark as done for today

otto set -e high        # Set energy to high
otto set -e medium      # Set energy to medium
otto set -e low         # Set energy to low
otto set -e depleted    # Set energy to depleted
```

### Session Persistence

```bash
otto session save       # Save current session state
otto session restore    # Restore last saved session
otto session clear      # Clear current session
otto session list       # List saved sessions
```

### Knowledge Commands

```bash
otto remember [text]    # Store knowledge for later
otto forget [query]     # Remove stored knowledge
otto recall [query]     # Search stored knowledge
```

### Integration Commands

```bash
otto integrations list              # List configured integrations
otto integrations add calendar      # Add calendar integration
otto integrations add tasks         # Add task integration
otto integrations status            # Show integration health
otto integrations sync              # Force sync all integrations
```

### Dashboard

```bash
otto tui                # Launch TUI dashboard
otto tui --theme dark   # Launch with dark theme
otto tui --theme light  # Launch with light theme
```

### Data Management

```bash
otto export             # Export all data (profile, knowledge, sessions)
otto export --format json  # Export as JSON
otto export --format usda  # Export as USD
otto wipe               # Delete all OTTO data (requires confirmation)
otto wipe --confirm     # Delete without prompt
```

---

## The Seven Experts

OTTO routes to different experts based on your detected state:

### Validator (Priority 1)

**Triggers**: Frustration, caps lock, negative language, distress signals

**Behavior**: Empathy first. Always validates feelings before problem-solving.

```
You: "THIS IS RIDICULOUS I CAN'T GET ANYTHING TO WORK"

OTTO: "That sounds really frustrating. It's not you -
       sometimes things just don't cooperate. Want to
       talk through what's happening?"
```

### Scaffolder (Priority 2)

**Triggers**: Overwhelm, stuck, "too much", decision paralysis

**Behavior**: Breaks things down. Reduces scope. Shows one step at a time.

```
You: "I have so many things to do I don't know where to start"

OTTO: "Let's narrow it down. What's the ONE thing that
       would feel like a win if you finished it today?"
```

### Restorer (Priority 3)

**Triggers**: Depletion, exhaustion, "tired", post-crash state

**Behavior**: Offers easy wins. Gives permission to stop. No pressure.

```
You: "I'm wiped out but I feel like I should keep going"

OTTO: "You've been at it for a while. It's okay to stop.
       Want to wrap up with something small, or just
       call it for today?"
```

### Refocuser (Priority 4)

**Triggers**: Tangent detected, topic drift, distraction patterns

**Behavior**: Gentle redirect without judgment.

```
You: [after long tangent about unrelated topic]

OTTO: "That's interesting! By the way, we were working
       on [original task]. Want to bookmark this idea
       and come back to it?"
```

### Celebrator (Priority 5)

**Triggers**: Task completion, milestone reached, success signals

**Behavior**: Acknowledges wins. Provides dopamine hit.

```
You: "Okay that's finally done"

OTTO: "Nice work! That was a solid piece of work.
       What's next, or want to ride this momentum?"
```

### Socratic (Priority 6)

**Triggers**: Exploration, "what if", curiosity, brainstorming

**Behavior**: Follows threads. Asks guiding questions. Enables discovery.

```
You: "What if we tried a completely different approach?"

OTTO: "I like where you're going. What would that
       look like? What's the core insight?"
```

### Direct (Priority 7)

**Triggers**: Flow state, focused work, quick requests

**Behavior**: Minimal friction. Gets out of the way.

```
You: "What's the syntax for X?"

OTTO: "[answer]"
```

---

## Protection System

### How Protection Works

OTTO monitors your state and offers protection when needed:

| Level | What Happens | Example Message |
|-------|--------------|-----------------|
| **GREEN** | Normal operation | (no message) |
| **YELLOW** | Soft suggestion | "Quick break soon?" |
| **ORANGE** | Firmer nudge | "You've been going a while. Blocker?" |
| **RED** | Full stop | "Let's pick this up tomorrow." |

### Protection Firmness

Your profile's `protection_firmness` (0.0-1.0) determines how OTTO protects:

- **0.0-0.3 (Gentle)**: Information only, never blocks
- **0.3-0.7 (Medium)**: Suggestions with soft confirmation
- **0.7-1.0 (Firm)**: Requires explicit override to continue

### Calibration Learning

OTTO learns from your overrides:

```
Pattern: You override evening protection frequently
Learning: OTTO adjusts peak_hours to include evenings

Pattern: You push through YELLOW warnings successfully
Learning: OTTO becomes slightly less protective

Pattern: You crash after ignoring ORANGE warnings
Learning: OTTO becomes slightly more protective
```

### Override Protocol

When protection activates:

```bash
# See what's happening
otto protect --status

# Acknowledge and continue
otto protect --override

# Or just take the break
# (OTTO will remember where you were)
```

---

## Integrations

### Available Integrations

| Integration | Type | What It Provides |
|-------------|------|------------------|
| **Calendar** | ICS/iCal files | Meeting awareness, deadline detection |
| **Tasks** | JSON file | Task load awareness, overdue detection |
| **Notes** | Coming soon | Knowledge context |

### Calendar Integration

OTTO reads calendar files (`.ics`) to understand your schedule:

```bash
# Add calendar from file
otto integrations add calendar --file ~/calendar.ics

# Add calendar from URL
otto integrations add calendar --url https://calendar.example.com/feed.ics
```

**What OTTO learns from your calendar:**
- Busy level (light, moderate, heavy)
- Upcoming meetings
- Approaching deadlines
- Focus time availability

### Task Integration

OTTO reads task files to understand your workload:

```bash
# Add task file
otto integrations add tasks --file ~/tasks.json
```

**Task file format:**
```json
{
  "tasks": [
    {
      "title": "Review PR",
      "due_date": "2026-01-30",
      "priority": "high",
      "completed": false
    }
  ]
}
```

**What OTTO learns from your tasks:**
- Load level (light, manageable, heavy, overloaded)
- Overdue count
- Priority distribution

### Context-Aware Decisions

When integrations are active, OTTO adjusts behavior:

```
Heavy calendar + overloaded tasks → Reduced cognitive budget
    → Simpler responses
    → Fewer agent spawns
    → More protective interventions
```

---

## Configuration

### Configuration File

OTTO's configuration lives at `~/.otto/config/otto.yaml`:

```yaml
# OTTO OS Configuration

# Protection settings
protection:
  firmness: 0.5           # 0.0 (gentle) to 1.0 (firm)
  allow_override: true    # Can user override protection?
  override_cooldown: 30   # Minutes between overrides

# Integration settings
integrations:
  calendar:
    enabled: true
    sync_interval: 300    # Seconds between syncs
  tasks:
    enabled: true
    sync_interval: 300

# Display settings
display:
  theme: auto             # auto, light, dark
  verbosity: standard     # minimal, brief, standard, verbose

# Session settings
session:
  auto_save: true
  save_interval: 60       # Seconds between auto-saves
```

### Environment Variables

```bash
OTTO_HOME=~/.otto         # OTTO data directory
OTTO_LOG_LEVEL=INFO       # Logging level
OTTO_NO_COLOR=1           # Disable colored output
OTTO_THEME=dark           # Force theme
```

---

## Troubleshooting

### "OTTO not responding"

```bash
# Check OTTO is installed
which otto

# Verify configuration
otto config list

# Check for errors
otto status --debug
```

### "State seems wrong"

```bash
# View current state
otto status --detailed

# Reset to healthy state
otto set -b GREEN -e high

# Clear session and start fresh
otto session clear
```

### "Integrations not syncing"

```bash
# Check integration status
otto integrations status

# Force sync
otto integrations sync

# View integration logs
otto integrations logs
```

### "Protection too aggressive/passive"

```bash
# Adjust firmness
otto config set protection.firmness 0.3  # More gentle
otto config set protection.firmness 0.7  # More firm

# Or re-run intake for new profile
otto-intake --reset
```

### "Want to start fresh"

```bash
# Reset everything
otto wipe --confirm

# Re-run intake
otto-intake

# Verify clean state
otto status
```

---

## Philosophy Recap

1. **Safety first** - Emotional safety before productivity
2. **Ship over perfect** - Working beats polished
3. **Protect momentum** - Don't break flow unnecessarily
4. **External memory** - Write it down
5. **Recover without guilt** - Rest is productive
6. **No labels** - Human states, not clinical categories

---

## Support

- **Issues**: https://github.com/your-org/otto-os/issues
- **Documentation**: https://github.com/your-org/otto-os/docs
- **BLUEPRINT**: See `BLUEPRINT.md` for technical specification

---

*OTTO OS - The first OS where variable attention is the native architecture.*
