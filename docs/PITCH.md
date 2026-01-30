# Otto: Cognitive-Aware AI Assistance

## The One-Liner

**Otto helps you finish projects by knowing when to do the work yourself, when to delegate to agents, and when to protect your flow.**

---

## The Problem

AI assistants are powerful, but they don't understand *you*.

They don't know when you're in the zone and shouldn't be interrupted. They don't know when you're exhausted and need simpler explanations. They don't know when spawning five parallel search agents will overwhelm you versus when it's exactly what you need.

Current AI tools treat every interaction the same way, regardless of:
- How tired you are
- Whether you're in deep focus or just exploring
- How many things you're already tracking
- Whether you're building momentum or crashing

The result? AI that interrupts your flow at the worst times, overwhelms you when you're already struggling, and fails to leverage its full power when you have the bandwidth for it.

---

## The Solution: Otto

Otto is a **cognitive-aware AI layer** that models your mental state and adapts assistance accordingly.

### Three Core Decisions

Every time you ask for help, Otto makes one of three decisions:

#### 1. WORK (Do It Yourself)
When the task is straightforward and you're focused, Otto gets out of the way. Direct action, minimal overhead. No unnecessary complexity.

> *"You're in flow, the task is simple. I'll just do it."*

#### 2. DELEGATE (Spawn Agents)
When the task would benefit from parallel work and you have the cognitive budget, Otto leverages agents. But only when you can handle tracking them.

> *"This is complex and parallelizable. You have bandwidth. I'll spawn 3 search agents to cover this faster."*

#### 3. PROTECT (Shield Your Flow)
When you're in peak focus, Otto queues results instead of interrupting. It batches notifications. It lets you finish what you're doing.

> *"You're in the zone. I'll queue these results for when you come up for air."*

---

## How It Works

### Cognitive State Tracking

Otto tracks five key dimensions of your cognitive state:

| Dimension | What It Means | How It's Used |
|-----------|---------------|---------------|
| **Energy** | Your current capacity | Low energy = simpler responses, fewer options |
| **Burnout** | Accumulated stress | High burnout = no agents, recovery suggestions |
| **Momentum** | Flow state progress | Peak momentum = protect from interruptions |
| **Mode** | Current mental mode | Exploring = follow tangents. Focused = stay on task |
| **Working Memory** | Items being tracked | Near limit = don't add more |

### Signal Detection

Otto detects signals in your messages:

- **Frustration signals**: CAPS, short responses, negative language → empathy first
- **Exploration signals**: "what if", tangent questions → follow the thread
- **Fatigue signals**: typos, minimal input, "tired" → simplify, suggest breaks
- **Focus signals**: clear requests, quick accepts → stay out of the way

### Energy Investment Model

Agents are **energy investments**. Every agent you spawn costs cognitive budget:
- Tracking its progress
- Understanding its results
- Integrating its work with yours

Otto only invests when the return is worth the cost.

---

## The Technology: USD Composition

Otto uses **Pixar's USD (Universal Scene Description)** composition semantics to resolve cognitive state. This is technically novel - no other system uses scene graph composition for cognitive modeling.

Why USD? Because USD already solves the problem of **multiple sources of opinion about the same thing**:

```
User's current state (Session) > Learned preferences (Calibration) > Mode settings (Variants) > Safety limits (Constitutional)
```

This is LIVRPS composition - the same priority system that resolves complex VFX scenes, now resolving cognitive state.

### Safety Floors

Some limits are constitutional - they can never be overridden:

- **Working memory limit**: 3 items max without external structure
- **Agent limit**: 3 concurrent agents maximum
- **Body check interval**: Reminder every 20 rapid exchanges

These aren't preferences. They're based on human cognitive science.

---

## Real Example: The Case Study

In a dogfooding session, Otto detected frustration at Exchange 13:

```
User: "WHY ISN'T THIS WORKING?! I've tried everything"
```

Otto's response:
> "I notice some frustration. Let's pause and make sure we're on the same page."

Result: User stepped back, found a typo in the config, solved the problem.

**Without Otto**: The user might have spiraled further, made hasty changes, introduced new bugs, or abandoned the task entirely.

---

## Who It's For

Otto is for anyone who:
- Works with AI assistants on complex projects
- Experiences variable energy and focus throughout the day
- Wants AI that adapts to them, not the other way around
- Values finishing projects over starting them

It's especially valuable for:
- Knowledge workers managing multiple parallel tasks
- Developers in long coding sessions
- Anyone who's ever been interrupted at the worst possible moment

---

## The Philosophy

### Finishing > Starting
Otto optimizes for project completion, not just task execution. It tracks momentum, protects flow, and knows when to push forward versus when to rest.

### Adaptation > Configuration
You don't configure Otto. It learns from your behavior, detects your signals, and adapts in real-time.

### Protection > Permission
Otto doesn't ask "should I interrupt you?" It knows when not to. Flow protection is proactive, not reactive.

### Energy Distribution > Raw Power
The goal isn't to do everything AI can do. It's to do the right things at the right times given your current capacity.

---

## Getting Started

Otto integrates as a Claude Code extension via hooks and skills:

```bash
# Calibrate at session start
/calibrate

# Check current cognitive state
/status

# Surface any pending tensions
/tension

# Recovery options when burned out
/recover
```

The system is always-on. No toggle. Because cognitive support shouldn't be opt-in - it should be default.

---

## Summary

Otto is cognitive-aware AI assistance.

It tracks your energy, protects your flow, and makes intelligent decisions about when to work directly, when to delegate to agents, and when to shield you from interruption.

The result: You finish more projects. With less burnout. And an AI that actually feels like it understands you.

**Otto helps you finish projects by knowing when to do the work yourself, when to delegate to agents, and when to protect your flow.**
