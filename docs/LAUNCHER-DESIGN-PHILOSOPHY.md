# ComfyUI Zen Launcher - Design Philosophy

## Principles Applied

### Greg Brockman (OpenAI)
> "Make the default path the right path."

- **Auto-launch**: No decisions required for 95% of use cases
- **Remember state**: Last mode saved automatically
- **Clean slate**: Kills existing processes silently

### John Maeda (Laws of Simplicity)

| Law | Application |
|-----|-------------|
| **REDUCE** | 5 options → 3 visible (4th hidden) |
| **ORGANIZE** | Primary action = do nothing |
| **TIME** | 2-second countdown, not 10 |
| **TRUST** | Just works, no confirmation |

---

## Before vs After

### BEFORE (Decision Paralysis)
```
╔════════════════════════════════════════════════════════════╗
║  LAUNCH MODES                                              ║
├────────────────────────────────────────────────────────────┤
│    [1]  STABLE        Balanced, recommended                │
│    [2]  DETERMINISTIC Reproducible inference (batch=1)     │
│    [3]  FAST          Maximum performance                  │
│    [4]  ORCHESTRATOR  Launch 7-Agent system                │
│    [5]  BOTH          ComfyUI + Ottotor               │
└────────────────────────────────────────────────────────────┘

   Select mode (auto-selects STABLE in 10s):
```

**Problems:**
- 5 choices = cognitive overload
- Technical jargon ("DETERMINISTIC")
- 10 seconds of waiting anxiety
- ASCII boxes = visual noise
- Equal visual weight on all options

### AFTER (Zero Friction)
```
  ComfyUI

  [O] Options   (starting in 2s)
```

**Improvements:**
- 1 action (wait or press O)
- 2 seconds, not 10
- Plain English
- Visual silence
- Power hidden

---

## ADHD Optimization

| ADHD Challenge | Solution |
|----------------|----------|
| Decision paralysis | Default = do nothing |
| Time pressure | Short countdown (2s) |
| Working memory | Remembers last choice |
| Visual overwhelm | Minimal text |
| Context switching | One clear action |

---

## File Locations

| File | Purpose |
|------|---------|
| `comfyui_zen.bat` | Zen launcher (default) |
| `launch_comfyui_framework.bat` | Full options (power users) |
| `%USERPROFILE%\.comfyui_mode` | Saved mode preference |

---

## Usage

**Normal use:**
1. Double-click shortcut
2. Wait 2 seconds (or press Enter)
3. ComfyUI launches

**Change mode:**
1. Double-click shortcut
2. Press `O` within 2 seconds
3. Select mode (1-4)
4. Choice is remembered

---

*"Simplicity is about subtracting the obvious and adding the meaningful."*
— John Maeda
