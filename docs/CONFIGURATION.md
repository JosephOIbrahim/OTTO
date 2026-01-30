# Configuration

## Overview

Framework Ottotor uses a layered configuration system with JSON files stored in `~/.framework-ottotor/`.

## Configuration Locations

```
~/.framework-ottotor/
├── principles.json           # Constitutional constraints (SPECIALIZES layer)
└── domains/                  # Domain-specific configurations
    ├── webdev.json
    ├── ai_conductor.json
    ├── ai_research.json
    └── general.json
```

## Principles Configuration

The `principles.json` file defines the SPECIALIZES layer - constitutional constraints that are **never compressed and never overridden**.

### Structure

```json
{
  "_meta": {
    "name": "Cognitive Principles Layer",
    "version": "1.0",
    "authority": "highest_immutable"
  },
  "constitutional": {
    "principles": [...]
  },
  "identity": {...},
  "constraints": {...},
  "recovery_protocol": {...},
  "livrps_memory_priority": {...},
  "memory_modes": {...}
}
```

### Constitutional Principles

Each principle has:
- `id`: Unique identifier
- `statement`: Human-readable description
- `triggers`: Keywords that activate this principle
- `action`: What to do when triggered

**Example**:
```json
{
  "id": "safety_first",
  "statement": "Safety first: Emotional safety before productivity",
  "triggers": ["frustration", "overwhelmed", "stressed", "caps", "negative"],
  "action": "Pause task execution, acknowledge state, offer support"
}
```

### Default Principles

1. **safety_first** - Emotional safety before productivity
2. **ship_over_perfect** - Working beats polished
3. **protect_momentum** - Don't break flow unnecessarily
4. **external_over_internal** - Write it down
5. **recover_without_guilt** - Rest is productive
6. **one_at_a_time** - Complete before switching
7. **user_knows_best** - Their signal trumps guesses

### Constraints

```json
{
  "never_compress": [
    "principles_layer",
    "active_goal",
    "user_explicit_preferences",
    "safety_state"
  ],
  "never_override": [
    "constitutional_principles",
    "user_explicit_request",
    "safety_constraints"
  ],
  "never_skip": [
    "safety_check",
    "determinism_enforcement",
    "principle_consultation_on_error"
  ]
}
```

### Memory Modes

```json
{
  "focused_recall": {
    "search_depth": "deep",
    "search_breadth": "narrow",
    "use_when": ["debugging", "specific_question", "implementation"]
  },
  "exploratory_recall": {
    "search_depth": "shallow",
    "search_breadth": "wide",
    "use_when": ["brainstorming", "what_if", "research"]
  },
  "recovery_recall": {
    "search_depth": "principles_only",
    "search_breadth": "minimal",
    "use_when": ["burnout", "overwhelmed", "error_state"]
  }
}
```

## Domain Configuration

Each domain is a JSON file in `~/.framework-ottotor/domains/`.

### Structure

```json
{
  "name": "Domain Name",
  "description": "What this domain covers",
  "version": "1.0",
  "specialists": {
    "specialist_name": {
      "keywords": ["trigger", "words"],
      "tools": ["Tool1", "Tool2"],
      "analysis_focus": ["focus1", "focus2"]
    }
  },
  "routing_keywords": ["domain", "level", "triggers"],
  "prism_perspectives": ["causal", "optimization", "risk"]
}
```

### Specialist Definition

| Field | Description |
|-------|-------------|
| `keywords` | Trigger words that route to this specialist |
| `tools` | Tools this specialist knows about |
| `analysis_focus` | What to analyze for this specialty |

### Routing Keywords

Top-level keywords that route to this domain. These are checked before specialist keywords.

### PRISM Perspectives

Which of the 6 PRISM perspectives apply to this domain:
- `causal` - What causes what?
- `optimization` - Where are bottlenecks?
- `hierarchical` - What's the structure?
- `temporal` - What's the sequence?
- `risk` - What could go wrong?
- `opportunity` - What's possible?

## Creating a New Domain

1. Create `~/.framework-ottotor/domains/your_domain.json`:

```json
{
  "name": "Your Domain",
  "description": "Description of your domain",
  "version": "1.0",
  "specialists": {
    "specialist_one": {
      "keywords": ["keyword1", "keyword2"],
      "tools": ["Tool A", "Tool B"],
      "analysis_focus": ["metric1", "metric2"]
    },
    "specialist_two": {
      "keywords": ["keyword3", "keyword4"],
      "tools": ["Tool C"],
      "analysis_focus": ["metric3"]
    }
  },
  "routing_keywords": ["your", "domain", "keywords"],
  "prism_perspectives": ["causal", "optimization"]
}
```

2. Restart the ottotor - domains are loaded on initialization.

## Example Domains

### WebDev Domain

```json
{
  "name": "WebDev",
  "specialists": {
    "frontend": {
      "keywords": ["react", "next", "component", "ui"],
      "analysis_focus": ["bundle_size", "render_performance"]
    },
    "backend": {
      "keywords": ["api", "server", "database"],
      "analysis_focus": ["response_time", "security"]
    }
  },
  "routing_keywords": ["react", "next", "api", "web"]
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FRAMEWORK_ORCHESTRATOR_HOME` | `~/.framework-ottotor` | Config directory |
| `FRAMEWORK_ORCHESTRATOR_WORKSPACE` | `./ottotor_workspace` | Working directory |

## Workspace Structure

Runtime state is stored in the workspace:

```
ottotor_workspace/
├── tasks/           # Input task definitions
├── results/         # Agent outputs with checksums
└── checkpoints/     # Recovery points
```

## Validation

### Principles Validation

- All principles must have `id`, `statement`, `triggers`, `action`
- Triggers must be non-empty arrays
- No duplicate principle IDs

### Domain Validation

- Must have `name` and `specialists`
- Each specialist must have `keywords` (non-empty)
- `routing_keywords` should not be empty (except for fallback domains)

## Best Practices

1. **Keep principles minimal** - Only add principles that actually guide behavior
2. **Use specific keywords** - Avoid overly broad triggers
3. **Test routing** - Verify tasks route to expected specialists
4. **Version your configs** - Include `version` field for tracking changes
5. **Use fallback domain** - `general.json` catches unmatched tasks
