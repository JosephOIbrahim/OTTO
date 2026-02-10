# Otto Trails MCP

MCP server for the OTTO OS Pheromone Trail system.

## Overview

Trails are distributed signals that enable emergent learning:
- **QUALITY**: Code health signals (he2025_compliant, violations)
- **CONTEXT**: Relationships (depends_on, used_by)
- **DECISION**: Historical choices (why X over Y)
- **PATTERN**: Learned successful approaches
- **WORK**: Activity signals (currently_editing, recently_touched)

## Installation

```bash
pip install otto-trails-mcp
```

Or from source:

```bash
cd packages/otto-trails-mcp
pip install -e .
```

## Usage

### Run the Server

```bash
otto-trails-mcp
```

### Configure in Claude Desktop

```json
{
    "mcpServers": {
        "otto-trails": {
            "command": "otto-trails-mcp"
        }
    }
}
```

## Tools

| Tool | Description |
|------|-------------|
| `otto_read_trails` | Read all trails for a file path |
| `otto_deposit_trail` | Create or reinforce a trail |
| `otto_reinforce_trail` | Strengthen an existing trail |
| `otto_query_trails` | Flexible trail search |
| `otto_get_related` | Follow CONTEXT trails to find related files |
| `otto_decay_trails` | Run decay and prune dead trails |

## Determinism [He2025]

- All queries return results in deterministic order
- Trail operations are atomic via SQLite transactions
- Same inputs produce same outputs
