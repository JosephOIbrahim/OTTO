# OTTO OS Public REST API

**Version**: v1.0.0
**Release**: v0.7.0

A versioned REST API for third-party integrations with OTTO OS.

## Table of Contents

- [Quick Start](#quick-start)
- [Authentication](#authentication)
- [Endpoints](#endpoints)
- [Scopes & Permissions](#scopes--permissions)
- [Rate Limiting](#rate-limiting)
- [Error Handling](#error-handling)
- [Response Format](#response-format)
- [CLI Commands](#cli-commands)
- [OpenAPI Specification](#openapi-specification)
- [Determinism Compliance](#determinism-compliance)

---

## Quick Start

### 1. Create an API Key

```bash
otto api-key create --name "My Integration" --scopes "read:status,read:state"
```

Save the displayed key - it won't be shown again.

### 2. Make Your First Request

```bash
curl -H "Authorization: Bearer otto_live_abc123_..." \
     http://localhost:8080/api/v1/status
```

### 3. Check Available Endpoints

```bash
curl http://localhost:8080/api/v1/openapi.json
```

---

## Authentication

All protected endpoints require an API key passed as a Bearer token.

### Request Header

```
Authorization: Bearer otto_live_<key_id>_<secret>
```

### Key Format

```
otto_{environment}_{key_id}_{secret}

Examples:
  otto_live_abc12345_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
  otto_test_xyz98765_q9r8s7t6u5v4w3x2y1z0a9b8c7d6e5f4
```

### Environments

| Environment | Prefix | Use Case |
|-------------|--------|----------|
| `live` | `otto_live_` | Production integrations |
| `test` | `otto_test_` | Development and testing |

### Public Endpoints (No Auth Required)

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/health` | Health check |
| `GET /api/v1/openapi.json` | OpenAPI specification |

---

## Endpoints

### System Endpoints

#### Health Check
```
GET /api/v1/health
```
Returns server health status. No authentication required.

**Response:**
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "timestamp": 1706540400.123
  },
  "meta": {
    "version": "v1",
    "timestamp": 1706540400.123,
    "request_id": "req_abc123"
  }
}
```

#### Ping
```
GET /api/v1/ping
```
Simple connectivity test.

**Scope Required:** `read:status`

**Response:**
```json
{
  "success": true,
  "data": "pong",
  "meta": { ... }
}
```

#### Status
```
GET /api/v1/status
```
Returns OTTO OS status including version information.

**Scope Required:** `read:status`

#### Available Methods
```
GET /api/v1/methods
```
Lists all available JSON-RPC methods.

**Scope Required:** `read:status`

---

### State Endpoints

#### Get State
```
GET /api/v1/state
```
Returns current OTTO OS state.

**Scope Required:** `read:state` or `read:state:full`

**Note:** With `read:state`, sensitive fields (burnout_level, energy_level, etc.) are filtered. Use `read:state:full` for complete state.

**Sensitive Fields:**
- `burnout_level`
- `energy_level`
- `momentum_phase`
- `epistemic_tension`
- `convergence_attractor`
- `rapid_exchange_count`

#### Update State
```
PATCH /api/v1/state
```
Updates OTTO OS state.

**Scope Required:** `write:state`

**Request Body:**
```json
{
  "session_goal": "Complete API documentation",
  "active_mode": "focused"
}
```

---

### Session Endpoints

#### Start Session
```
POST /api/v1/sessions
```
Starts a new session.

**Scope Required:** `write:session`

#### End Current Session
```
DELETE /api/v1/sessions/current
```
Ends the current session.

**Scope Required:** `write:session`

---

### Agent Endpoints

#### List Agents
```
GET /api/v1/agents
```
Lists all running agents.

**Scope Required:** `read:agents`

#### Spawn Agent
```
POST /api/v1/agents
```
Spawns a new agent.

**Scope Required:** `write:agents`

**Request Body:**
```json
{
  "task": "Research topic X",
  "type": "researcher"
}
```

#### Abort Agent
```
DELETE /api/v1/agents/:id
```
Aborts a running agent.

**Scope Required:** `write:agents`

---

### Integration Endpoints

#### List Integrations
```
GET /api/v1/integrations
```
Lists configured integrations.

**Scope Required:** `read:integrations`

#### Sync Integrations
```
POST /api/v1/integrations/sync
```
Triggers integration sync.

**Scope Required:** `write:session`

#### Get Context
```
GET /api/v1/context
```
Returns current context from integrations.

**Scope Required:** `read:integrations`

---

### Protection Endpoints

#### Check Protection
```
POST /api/v1/protection/check
```
Checks if an action is allowed by protection rules.

**Scope Required:** `read:state`

**Request Body:**
```json
{
  "action": "spawn_agent",
  "context": { ... }
}
```

---

## Scopes & Permissions

### Available Scopes

| Scope | Description | Access Level |
|-------|-------------|--------------|
| `read:status` | Status, ping, methods | Read |
| `read:state` | State (filtered) | Read |
| `read:state:full` | State (all fields) | Read |
| `read:agents` | Agent list/status | Read |
| `read:integrations` | Integration status | Read |
| `write:state` | Update state | Write |
| `write:session` | Session lifecycle | Write |
| `write:agents` | Spawn/abort agents | Write |
| `admin` | All permissions | Admin |

### Scope Hierarchy

The `admin` scope includes all other scopes.

### Default Scopes

When creating a key without specifying scopes:
- `read:status`
- `read:state`

---

## Rate Limiting

Rate limits are applied per API key.

### Default Limits

| Endpoint Category | Requests/Minute |
|-------------------|-----------------|
| Health/Ping | 120 |
| Status/Methods | 60 |
| State (read) | 30 |
| State (write) | 10 |
| Agents (read) | 30 |
| Agents (write) | 5 |
| Sessions | 10 |
| Integrations | 30 |

### Rate Limit Headers

Responses include rate limit information:

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 55
X-RateLimit-Reset: 1706540460
```

### Exceeded Response

```json
{
  "success": false,
  "error": {
    "code": "RATE_LIMITED",
    "message": "Rate limit exceeded. Try again in 45 seconds."
  },
  "meta": {
    "rate_limit_remaining": 0,
    "rate_limit_reset": 1706540460
  }
}
```

---

## Error Handling

### Error Response Format

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable description"
  },
  "meta": {
    "version": "v1",
    "timestamp": 1706540400.123,
    "request_id": "req_abc123"
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INVALID_JSON` | 400 | Malformed JSON in request |
| `INVALID_REQUEST` | 400 | Invalid request structure |
| `INVALID_PARAMS` | 400 | Invalid parameters |
| `UNAUTHORIZED` | 401 | Missing or invalid API key |
| `FORBIDDEN` | 403 | Insufficient scope |
| `NOT_FOUND` | 404 | Endpoint or resource not found |
| `METHOD_NOT_ALLOWED` | 405 | HTTP method not allowed |
| `RATE_LIMITED` | 429 | Rate limit exceeded |
| `INTERNAL_ERROR` | 500 | Server error |
| `PROTECTION_BLOCKED` | 403 | Action blocked by protection |

---

## Response Format

### Success Response

```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "version": "v1",
    "timestamp": 1706540400.123,
    "request_id": "req_abc123",
    "rate_limit_remaining": 55,
    "rate_limit_reset": 1706540460
  }
}
```

### Meta Fields

| Field | Type | Description |
|-------|------|-------------|
| `version` | string | API version (always "v1") |
| `timestamp` | float | Unix timestamp |
| `request_id` | string | Unique request identifier |
| `rate_limit_remaining` | int | Requests remaining in window |
| `rate_limit_reset` | float | Unix timestamp when limit resets |

---

## CLI Commands

### Create API Key

```bash
otto api-key create [options]

Options:
  -n, --name NAME       Key name (default: "API Key")
  -s, --scopes SCOPES   Comma-separated scopes
  -e, --expires DAYS    Days until expiration
  -t, --test            Create test environment key
```

**Examples:**

```bash
# Create with default scopes
otto api-key create --name "Dashboard"

# Create with specific scopes
otto api-key create -n "Agent Controller" -s "read:agents,write:agents"

# Create test key with expiration
otto api-key create -t -e 30 -n "Testing"
```

### List API Keys

```bash
otto api-key list [options]

Options:
  -a, --all    Include revoked and expired keys
```

### Revoke API Key

```bash
otto api-key revoke --key-id KEY_ID [options]

Options:
  -r, --reason REASON   Reason for revocation
```

### Delete API Key

```bash
otto api-key delete --key-id KEY_ID --force
```

---

## OpenAPI Specification

The complete OpenAPI 3.0 specification is available at:

```
GET /api/v1/openapi.json
```

This can be imported into tools like:
- Swagger UI
- Postman
- Insomnia
- OpenAPI Generator

---

## Determinism Compliance

The API is designed "Defeating Nondeterminism in LLM Inference" principles.

### Guarantees

| Component | Guarantee |
|-----------|-----------|
| Route evaluation | Fixed order |
| Middleware chain | Fixed order (Auth → RateLimit → Scope → Filter) |
| Error code mapping | Fixed (deterministic HTTP status) |
| Response structure | Fixed envelope format |
| JSON serialization | Sorted keys |

### Expected Variance

These fields intentionally vary per-request:

| Field | Reason |
|-------|--------|
| `meta.timestamp` | Time of request |
| `meta.request_id` | Unique per request |
| `meta.rate_limit_remaining` | Decrements per request |
| `meta.rate_limit_reset` | Time-based |

### Batch Invariance

Same input produces same output regardless of:
- Concurrent load
- Sequential vs parallel requests
- Connection reuse vs new connections

---

## Security

### Key Storage

- API keys are stored as SHA-256 hashes in the OS keyring
- Full keys are never stored or logged
- Validation uses constant-time comparison (`hmac.compare_digest`)

### Audit Logging

All key lifecycle events are logged to `~/.otto/audit/api_audit.jsonl`:
- Key creation
- Key validation (success/failure)
- Key revocation
- Authentication failures
- Scope denials
- Rate limit exceeded

### Best Practices

1. **Never share API keys** - Each integration should have its own key
2. **Use minimal scopes** - Only request permissions you need
3. **Rotate keys regularly** - Create new keys and revoke old ones
4. **Use test keys for development** - Use `--test` flag for non-production
5. **Monitor audit logs** - Check for suspicious activity

---

## Examples

### Python (httpx)

```python
import httpx

api_key = "otto_live_abc123_..."
headers = {"Authorization": f"Bearer {api_key}"}

async with httpx.AsyncClient() as client:
    # Get status
    response = await client.get(
        "http://localhost:8080/api/v1/status",
        headers=headers
    )
    print(response.json())
```

### JavaScript (fetch)

```javascript
const apiKey = "otto_live_abc123_...";

const response = await fetch("http://localhost:8080/api/v1/status", {
  headers: {
    "Authorization": `Bearer ${apiKey}`
  }
});

const data = await response.json();
console.log(data);
```

### cURL

```bash
# Get status
curl -H "Authorization: Bearer otto_live_abc123_..." \
     http://localhost:8080/api/v1/status

# Update state
curl -X PATCH \
     -H "Authorization: Bearer otto_live_abc123_..." \
     -H "Content-Type: application/json" \
     -d '{"session_goal": "Complete task X"}' \
     http://localhost:8080/api/v1/state
```

---

## Changelog

### v1.0.0 (v0.7.0 Release)

- Initial public API release
- 18 REST endpoints
- API key authentication with scopes
- Rate limiting per key/endpoint
- Sensitive data filtering
- OpenAPI 3.0 specification
- CLI key management
- Audit logging
- Determinism
