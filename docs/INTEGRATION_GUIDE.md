# OTTO OS Integration Guide

**Version 0.6.0**

How to connect OTTO OS with external services for context awareness.

---

## Philosophy

OTTO integrations are **information sources, not control mechanisms**.

- OTTO **reads** from services to understand your context
- OTTO **rarely writes** to services (and only with explicit consent)
- External context **adjusts** behavior, it doesn't **control** it

---

## Available Integrations

| Integration | Status | Read | Write | Purpose |
|-------------|--------|------|-------|---------|
| **Calendar (ICS)** | Stable | Yes | No | Meeting awareness, deadline detection |
| **Tasks (JSON)** | Stable | Yes | No | Workload awareness, priority context |
| **Notes** | Coming | Yes | No | Knowledge context |
| **Cloud Sync** | Stable | Yes | Yes | Cross-device state sync |

---

## Calendar Integration

### ICS/iCal Files

OTTO reads standard iCalendar (`.ics`) files from Google Calendar, Outlook, Apple Calendar, or any CalDAV server.

#### Setup

```bash
# From local file
otto integrations add calendar --file ~/calendars/work.ics

# From URL (auto-sync)
otto integrations add calendar --url https://calendar.google.com/calendar/ical/...

# Verify
otto integrations status
```

#### Getting Your Calendar URL

**Google Calendar:**
1. Open Google Calendar → Settings → [Your Calendar]
2. Find "Secret address in iCal format"
3. Copy the URL

**Outlook/Microsoft 365:**
1. Open Outlook → Calendar → Share → Publish
2. Select "Can view all details"
3. Copy the ICS link

**Apple iCloud:**
1. Open Calendar → Share Calendar
2. Enable "Public Calendar"
3. Copy the URL

#### What OTTO Extracts

OTTO only extracts **metadata**, never event contents:

| Data | Example | How It's Used |
|------|---------|---------------|
| Event count | "8 events today" | Busy level detection |
| Total busy time | "5 hours of meetings" | Cognitive budget adjustment |
| Next event start | "Meeting in 30 min" | Focus window calculation |
| Deadline proximity | "Due in 4 hours" | Urgency signal |

#### Context Signals

From calendar data, OTTO derives:

```
busy_level: light | moderate | heavy
    light:    < 2 hours meetings
    moderate: 2-4 hours meetings
    heavy:    > 4 hours meetings

deadline_approaching: true | false
    true: Event with "deadline" or due within 24 hours

free_window_minutes: number
    Time until next event
```

---

## Task Integration

### JSON Task Files

OTTO reads task data from JSON files, compatible with exports from Todoist, Things, or custom systems.

#### Setup

```bash
# Add task file
otto integrations add tasks --file ~/tasks.json

# Verify
otto integrations status
```

#### Task File Format

```json
{
  "tasks": [
    {
      "id": "task-001",
      "title": "Review pull request",
      "due_date": "2026-01-30",
      "priority": "high",
      "completed": false,
      "labels": ["work", "code-review"]
    },
    {
      "id": "task-002",
      "title": "Weekly planning",
      "due_date": "2026-01-29",
      "priority": "medium",
      "completed": false
    }
  ]
}
```

#### Required Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | Yes | Task description |
| `completed` | boolean | Yes | Whether task is done |
| `due_date` | string | No | ISO date (YYYY-MM-DD) |
| `priority` | string | No | "high", "medium", "low" |

#### What OTTO Extracts

| Data | How It's Used |
|------|---------------|
| Total count | Load level calculation |
| Overdue count | Urgency signals |
| High priority count | Focus prioritization |
| Completion rate | Momentum assessment |

#### Context Signals

From task data, OTTO derives:

```
load_level: light | manageable | heavy | overloaded
    light:      <= 5 tasks
    manageable: 6-15 tasks
    heavy:      16-30 tasks
    overloaded: > 30 tasks

overdue_tasks: number
    Tasks past due_date

high_priority_tasks: number
    Tasks with priority="high"
```

---

## How Integrations Affect Behavior

### Cognitive Budget Adjustment

External context adjusts your cognitive budget:

```
Base budget from internal state:
    energy=high, burnout=GREEN → budget = 0.85

External adjustments applied:
    calendar=heavy   → budget -= 0.15
    tasks=overloaded → budget -= 0.20
    deadline_near    → budget -= 0.10

Final budget: 0.85 - 0.15 - 0.20 = 0.50
```

### Decision Impact

| External Load | Effect |
|---------------|--------|
| **Light** | Normal operation, slight budget boost |
| **Moderate** | Standard operation |
| **Heavy** | Reduced agent spawning, simpler responses |
| **Critical** | Protection mode, minimal complexity |

### Agent Capacity

Heavy external load reduces parallel agent capacity:

```
max_parallel_agents = 3 (default)

if calendar=heavy OR tasks=overloaded:
    max_parallel_agents = 2

Prevents overwhelming you with too much parallel activity.
```

---

## Integration Configuration

### Config File

Integration settings in `~/.otto/config/integrations.yaml`:

```yaml
calendar:
  enabled: true
  adapters:
    - type: ical
      path: ~/calendars/work.ics
      sync_interval: 300  # seconds
    - type: ical
      url: https://calendar.google.com/...
      sync_interval: 300

tasks:
  enabled: true
  adapters:
    - type: json
      path: ~/tasks.json
      sync_interval: 60

# Future: notes integration
notes:
  enabled: false
```

### Sync Intervals

| Integration | Default Interval | Recommended |
|-------------|------------------|-------------|
| Calendar | 5 minutes | 5-15 minutes |
| Tasks | 1 minute | 1-5 minutes |

Shorter intervals = more current data, higher resource usage.

---

## Integration Health

### Checking Status

```bash
otto integrations status
```

Output:
```
INTEGRATION STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Calendar (ical)
  Status:     healthy
  Last sync:  2 minutes ago
  Events:     8 today
  Busy level: moderate

Tasks (json)
  Status:     healthy
  Last sync:  30 seconds ago
  Total:      12 tasks
  Overdue:    2
  Load level: manageable
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Health States

| State | Meaning | Action |
|-------|---------|--------|
| `healthy` | Working normally | None needed |
| `stale` | Data older than 2x sync interval | Check file/URL |
| `error` | Sync failed | Check logs, verify access |
| `disabled` | Manually disabled | Enable if needed |

### Force Sync

```bash
# Sync all integrations
otto integrations sync

# Sync specific integration
otto integrations sync calendar
```

---

## Cloud Sync

### Overview

OTTO can sync your state across devices using encrypted cloud storage.

**Key principle**: End-to-end encryption. Your cloud provider never sees your data.

### Supported Backends

| Backend | Use Case |
|---------|----------|
| WebDAV | Nextcloud, ownCloud, any WebDAV server |
| S3 | AWS S3, MinIO, any S3-compatible storage |
| Local | Testing, manual backup |

### Setup (WebDAV)

```bash
otto sync setup webdav \
  --url https://nextcloud.example.com/remote.php/dav \
  --username your-user \
  --password your-password
```

### Setup (S3)

```bash
otto sync setup s3 \
  --bucket otto-sync \
  --region us-east-1 \
  --access-key AKIA... \
  --secret-key ...
```

### Encryption

All synced data is encrypted with AES-256-GCM before leaving your device.

```bash
# First time: creates encryption key
otto sync setup ... --create-key

# Subsequent devices: import existing key
otto sync setup ... --import-key <key-file>
```

**Keep your key safe.** Without it, synced data cannot be recovered.

### What Gets Synced

| Data | Synced | Notes |
|------|--------|-------|
| Profile | Yes | Your personality settings |
| Calibration | Yes | Learned patterns |
| Session state | Optional | Current session |
| Knowledge | Yes | Personal knowledge store |
| Logs | No | Stay local |

---

## Troubleshooting

### Calendar not updating

```bash
# Check file exists and is readable
ls -la ~/calendars/work.ics

# For URL, check accessibility
curl -I "https://calendar.google.com/..."

# View integration logs
otto integrations logs calendar
```

### Task file parse error

```bash
# Validate JSON
python -m json.tool ~/tasks.json

# Check required fields
cat ~/tasks.json | jq '.tasks[] | select(.title == null)'
```

### Sync conflicts

```bash
# View conflict status
otto sync status

# Force local → remote
otto sync push --force

# Force remote → local
otto sync pull --force
```

---

## Privacy

### What OTTO Reads

- **Calendar**: Event times, durations, titles (for deadline detection)
- **Tasks**: Titles, due dates, priorities, completion status
- **Notes**: (Coming) Search index only

### What OTTO Never Reads

- Email content
- Message content
- File contents (except configured task files)
- Browser history
- Location data

### Data Storage

All integration data cached locally at:
```
~/.otto/integrations/
├── calendar_cache.json
├── task_cache.json
└── sync_state.json
```

---

## Building Custom Integrations

### Adapter Interface

Create custom integrations by implementing the adapter interface:

```python
from otto.integration import IntegrationAdapter, CalendarContext

class MyCalendarAdapter(IntegrationAdapter):
    integration_type = "calendar"

    async def connect(self) -> None:
        # Initialize connection
        pass

    async def get_context(self) -> CalendarContext:
        # Return calendar context
        return CalendarContext(
            events_today=5,
            total_busy_minutes_today=180,
            busy_level="moderate"
        )

    async def disconnect(self) -> None:
        # Clean up
        pass
```

### Registering Adapters

```python
from otto.integration import IntegrationManager

manager = IntegrationManager()
manager.register_adapter(MyCalendarAdapter(config))
await manager.start()
```

---

*For more details, see the BLUEPRINT.md section on Integration Layer.*
