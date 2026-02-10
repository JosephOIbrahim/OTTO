# OTTO OS Public REST API - Production & Frontier AI Readiness Roadmap

**Created**: 2026-01-29
**Status**: Strategic Planning Document
**Audience**: Technical Leadership, DevOps, Security

---

## Executive Summary

The Public REST API v1.0.0 is feature-complete with 2350 passing tests and Determinism. This document outlines the path to:

1. **Production Readiness** - Deployment, security hardening, observability
2. **Frontier AI Readiness** - Optimizations for AI agent interaction patterns

---

## Current State Assessment

### Completed ✅

| Component | Status | Evidence |
|-----------|--------|----------|
| Core API (18 endpoints) | Complete | `rest_router.py` |
| Authentication (API keys) | Complete | `api_keys.py`, `middleware.py` |
| Authorization (scopes) | Complete | `scopes.py` |
| Rate limiting | Complete | `middleware.py` |
| Audit logging | Complete | `audit.py` |
| determinism | Verified | `API_HE2025_CONSISTENCY_REPORT.md` |
| OpenAPI spec | Auto-generated | `openapi.py` |
| CLI commands | Complete | `cli/main.py` |
| Test coverage | 261+ API tests | 9 test files |
| Documentation | Complete | `docs/API.md` |

### Gaps for Production 🔶

| Category | Gap | Priority |
|----------|-----|----------|
| Infrastructure | No containerization | HIGH |
| Security | No TLS enforcement | HIGH |
| Observability | No metrics export | HIGH |
| Operations | No CI/CD pipeline | MEDIUM |
| Performance | No load testing | MEDIUM |
| Reliability | No HA configuration | MEDIUM |

### Gaps for Frontier AI 🔷

| Category | Gap | Priority |
|----------|-----|----------|
| Tool Use | OpenAPI not optimized for AI | HIGH |
| Idempotency | No idempotency keys | MEDIUM |
| Batch Operations | No bulk endpoints | MEDIUM |
| Streaming | No webhook/SSE support | LOW |
| AI-specific Rate Limits | Single tier only | LOW |

---

## Phase 1: Production Security Hardening (Critical)

### 1.1 TLS/HTTPS Enforcement

**Current**: HTTP only
**Required**: TLS 1.3 with certificate management

```python
# Proposed: src/otto/api/tls.py
class TLSConfig:
    """
    TLS configuration for production.

    Determinism: FIXED cipher suites, no runtime negotiation variance.
    """
    MIN_VERSION = ssl.TLSVersion.TLSv1_3
    CIPHERS = [
        "TLS_AES_256_GCM_SHA384",
        "TLS_CHACHA20_POLY1305_SHA256",
        "TLS_AES_128_GCM_SHA256",
    ]
```

**Implementation Steps**:
1. Add `ssl` context to `asyncio.start_server()`
2. Create certificate management module
3. Add TLS configuration to CLI
4. Update health checks for HTTPS
5. Add HSTS headers

**Tests Required**: ~15 tests

### 1.2 Security Headers

**Required Headers**:
```
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Content-Security-Policy: default-src 'none'
X-Request-Id: {request_id}
```

**Implementation**: Add `SecurityHeadersMiddleware` to chain

**Tests Required**: ~10 tests

### 1.3 Input Validation Hardening

**Current**: Basic validation
**Required**: Strict schema validation

```python
# Proposed additions to middleware.py
class InputValidationMiddleware(Middleware):
    """
    Validate request bodies against JSON schemas.

    FIXED schemas, deterministic validation.
    """
    SCHEMAS: Dict[str, dict] = {
        "/api/v1/state": STATE_UPDATE_SCHEMA,
        "/api/v1/agents": AGENT_SPAWN_SCHEMA,
        # ...
    }
```

**Tests Required**: ~20 tests

### 1.4 API Key Rotation Automation

**Current**: Manual rotation via CLI
**Required**: Automated rotation with grace period

```python
# Proposed: src/otto/api/rotation.py
class KeyRotationManager:
    """
    Automatic API key rotation.

    Features:
    - Grace period for old keys (configurable, default 24h)
    - Notification hooks for key expiry
    - Audit trail for rotations
    """
    GRACE_PERIOD_HOURS = 24
    EXPIRY_WARNING_DAYS = 7
```

**Tests Required**: ~15 tests

---

## Phase 2: Observability & Operations

### 2.1 Metrics Export (Prometheus)

**Required Metrics**:
```
# Counters
otto_api_requests_total{method, path, status}
otto_api_auth_failures_total{reason}
otto_api_rate_limit_hits_total{key_id, path}

# Histograms
otto_api_request_duration_seconds{method, path}
otto_api_response_size_bytes{method, path}

# Gauges
otto_api_active_connections
otto_api_keys_active
otto_api_keys_expired
```

**Implementation**:
```python
# Proposed: src/otto/api/metrics.py
from prometheus_client import Counter, Histogram, Gauge

class APIMetrics:
    """
    Prometheus metrics for API observability.

    Determinism: FIXED metric names, DETERMINISTIC labels.
    """
    requests = Counter('otto_api_requests_total', 'Total requests',
                       ['method', 'path', 'status'])
    duration = Histogram('otto_api_request_duration_seconds', 'Request duration',
                        ['method', 'path'])
```

**Tests Required**: ~20 tests

### 2.2 Structured Logging

**Current**: Basic Python logging
**Required**: JSON structured logs for aggregation

```python
# Proposed log format
{
    "timestamp": "2026-01-29T18:00:00.000Z",
    "level": "INFO",
    "logger": "otto.api",
    "request_id": "req_abc123",
    "key_id": "abc12345",
    "method": "GET",
    "path": "/api/v1/status",
    "status": 200,
    "duration_ms": 12.5,
    "message": "Request completed"
}
```

**Implementation**: Add `StructuredLogger` class, update all log calls

**Tests Required**: ~10 tests

### 2.3 Health Check Enhancement

**Current**: Basic `/health` endpoint
**Required**: Deep health checks with dependencies

```python
# Proposed: Enhanced health response
{
    "status": "healthy",
    "version": "1.0.0",
    "checks": {
        "keyring": {"status": "ok", "latency_ms": 2},
        "state_manager": {"status": "ok", "latency_ms": 5},
        "jsonrpc_handler": {"status": "ok", "latency_ms": 1}
    },
    "uptime_seconds": 3600,
    "request_count": 12500
}
```

**Tests Required**: ~10 tests

### 2.4 CI/CD Pipeline

**Required Pipeline Stages**:
```yaml
# .github/workflows/api-release.yml
stages:
  - lint        # ruff, mypy
  - test        # pytest with coverage
  - security    # bandit, safety
  - build       # Docker image
  - deploy-staging
  - smoke-test
  - deploy-production
```

**Tests Required**: Pipeline tests (separate from unit tests)

---

## Phase 3: Reliability & Performance

### 3.1 Connection Pool Management

**Current**: New connection per request
**Required**: Configurable connection pooling

```python
# Proposed: src/otto/api/pool.py
class ConnectionPool:
    """
    Connection pool for HTTP server.

    Determinism: FIXED pool sizes, DETERMINISTIC connection selection.
    """
    MAX_CONNECTIONS = 1000
    MAX_KEEPALIVE = 100
    KEEPALIVE_TIMEOUT = 30
```

**Tests Required**: ~15 tests

### 3.2 Response Caching

**Cacheable Endpoints**:
- `GET /api/v1/openapi.json` - Long TTL (1 hour)
- `GET /api/v1/methods` - Medium TTL (5 minutes)
- `GET /api/v1/status` - Short TTL (10 seconds)

**Implementation**:
```python
# Proposed: src/otto/api/cache.py
class ResponseCache:
    """
    Response caching with TTL.

    Determinism: DETERMINISTIC cache keys, FIXED TTLs.
    """
    @staticmethod
    def cache_key(method: str, path: str, key_id: str) -> str:
        return f"{method}:{path}:{key_id}"
```

**Tests Required**: ~15 tests

### 3.3 Load Testing & Benchmarks

**Required Benchmarks**:
```
Target: 10,000 requests/second at p99 < 50ms

Scenarios:
1. Sustained load (10 min at 5,000 rps)
2. Burst load (1,000 concurrent connections)
3. Mixed workload (80% read, 20% write)
4. Rate limit saturation
5. Authentication storm (invalid keys)
```

**Tools**: `locust`, `wrk`, `vegeta`

**Tests Required**: Benchmark scripts (not unit tests)

### 3.4 High Availability Configuration

**Requirements**:
- Multiple server instances behind load balancer
- Shared state for rate limiting (Redis)
- Session affinity not required (stateless)
- Health-based routing

**Implementation**:
```yaml
# docker-compose.ha.yml
services:
  otto-api-1:
    image: otto-os/api:latest
    environment:
      - REDIS_URL=redis://redis:6379
  otto-api-2:
    image: otto-os/api:latest
    environment:
      - REDIS_URL=redis://redis:6379
  redis:
    image: redis:alpine
  nginx:
    image: nginx:alpine
    # Load balancer config
```

---

## Phase 4: Frontier AI Readiness

### 4.1 OpenAPI Optimization for AI Tool Use

**Current**: Standard OpenAPI 3.0 spec
**Required**: AI-optimized descriptions and examples

```yaml
# Enhanced OpenAPI for AI consumption
paths:
  /api/v1/state:
    get:
      summary: "Get current OTTO OS cognitive state"
      description: |
        Returns the current state of OTTO OS including:
        - Active mode (focused, exploring, teaching, recovery)
        - Energy and burnout levels
        - Current session goal

        AI USAGE NOTE: This endpoint is idempotent and safe for frequent polling.
        Recommended polling interval: 30 seconds minimum.
      x-ai-tool-use:
        recommended_for:
          - "Monitoring OTTO OS state"
          - "Checking before spawning agents"
          - "Health verification"
        not_recommended_for:
          - "High-frequency polling (use webhooks instead)"
```

**Implementation**: Add `x-ai-tool-use` extensions to OpenAPI spec

**Tests Required**: Schema validation tests

### 4.2 Idempotency Keys

**Purpose**: Allow AI agents to safely retry requests

```python
# Proposed header
X-Idempotency-Key: <client-generated-uuid>

# Response includes
X-Idempotency-Key: <echoed-uuid>
X-Idempotency-Replayed: true  # If this was a replay
```

**Implementation**:
```python
# Proposed: src/otto/api/idempotency.py
class IdempotencyMiddleware(Middleware):
    """
    Idempotency key handling for safe retries.

    Determinism: DETERMINISTIC key matching, FIXED TTL.
    """
    TTL_SECONDS = 86400  # 24 hours

    async def process(self, ctx, next):
        key = ctx.request.headers.get("X-Idempotency-Key")
        if key:
            cached = await self.cache.get(key)
            if cached:
                ctx.response_headers["X-Idempotency-Replayed"] = "true"
                return cached
```

**Tests Required**: ~20 tests

### 4.3 Batch Operations

**New Endpoints**:
```
POST /api/v1/batch
Content-Type: application/json

{
    "requests": [
        {"method": "GET", "path": "/api/v1/status"},
        {"method": "GET", "path": "/api/v1/agents"},
        {"method": "POST", "path": "/api/v1/agents", "body": {...}}
    ]
}
```

**Response**:
```json
{
    "responses": [
        {"status": 200, "data": {...}},
        {"status": 200, "data": {...}},
        {"status": 201, "data": {...}}
    ],
    "meta": {
        "batch_size": 3,
        "success_count": 3,
        "error_count": 0
    }
}
```

**Implementation**: Add `BatchRequestHandler` to router

**Tests Required**: ~25 tests

### 4.4 Webhook Support

**Purpose**: Push notifications for AI agents instead of polling

```python
# Proposed: src/otto/api/webhooks.py
class WebhookManager:
    """
    Webhook delivery for real-time AI agent notifications.

    Events:
    - state.changed
    - agent.spawned
    - agent.completed
    - agent.failed
    - session.started
    - session.ended
    - protection.triggered
    """
```

**New Endpoints**:
```
POST /api/v1/webhooks
GET /api/v1/webhooks
DELETE /api/v1/webhooks/:id
```

**Tests Required**: ~30 tests

### 4.5 AI-Specific Rate Limit Tiers

**Proposed Tiers**:

| Tier | Requests/min | Use Case |
|------|--------------|----------|
| `standard` | 60 | Human users |
| `ai_agent` | 300 | Single AI agent |
| `ai_orchestrator` | 1000 | Multi-agent orchestration |
| `enterprise` | 5000 | Enterprise AI deployments |

**Implementation**:
```python
# Proposed scope
class APIScope(Enum):
    # ... existing scopes ...
    TIER_AI_AGENT = "tier:ai_agent"
    TIER_AI_ORCHESTRATOR = "tier:ai_orchestrator"
```

**Tests Required**: ~15 tests

### 4.6 Semantic Error Messages

**Current**: HTTP status + generic message
**Required**: AI-parseable error context

```json
{
    "success": false,
    "error": {
        "code": "RATE_LIMITED",
        "message": "Rate limit exceeded",
        "ai_context": {
            "retry_after_seconds": 45,
            "limit": 60,
            "window_seconds": 60,
            "suggestion": "Implement exponential backoff or upgrade to ai_agent tier"
        }
    }
}
```

**Tests Required**: ~10 tests

---

## Implementation Priority Matrix

| Phase | Item | Effort | Impact | Priority |
|-------|------|--------|--------|----------|
| 1 | TLS Enforcement | Medium | Critical | P0 |
| 1 | Security Headers | Low | High | P0 |
| 1 | Input Validation | Medium | High | P0 |
| 2 | Metrics Export | Medium | High | P1 |
| 2 | Structured Logging | Low | Medium | P1 |
| 2 | CI/CD Pipeline | High | High | P1 |
| 3 | Connection Pooling | Medium | Medium | P2 |
| 3 | Response Caching | Medium | Medium | P2 |
| 3 | Load Testing | Medium | High | P2 |
| 4 | OpenAPI AI Extensions | Low | High | P1 |
| 4 | Idempotency Keys | Medium | High | P1 |
| 4 | Batch Operations | High | High | P2 |
| 4 | Webhooks | High | Medium | P3 |
| 4 | AI Rate Tiers | Low | Medium | P3 |

---

## Recommended Implementation Order

### Sprint 1 (Week 1-2): Security Critical
1. TLS enforcement
2. Security headers middleware
3. Input validation schemas

### Sprint 2 (Week 3-4): Observability
1. Prometheus metrics
2. Structured logging
3. Enhanced health checks

### Sprint 3 (Week 5-6): AI Readiness - Core
1. OpenAPI AI extensions
2. Idempotency keys
3. Semantic error messages

### Sprint 4 (Week 7-8): Performance
1. Connection pooling
2. Response caching
3. Load testing

### Sprint 5 (Week 9-10): AI Readiness - Advanced
1. Batch operations
2. AI-specific rate tiers

### Sprint 6 (Week 11-12): Enterprise
1. Webhooks
2. HA configuration
3. CI/CD pipeline

---

## Test Count Projections

| Phase | New Tests | Cumulative |
|-------|-----------|------------|
| Current | 261 | 261 |
| Phase 1 | 60 | 321 |
| Phase 2 | 50 | 371 |
| Phase 3 | 45 | 416 |
| Phase 4 | 115 | 531 |

**Target**: 530+ API tests for production + frontier AI readiness

---

## Success Criteria

### Production Ready
- [ ] TLS 1.3 enforced
- [ ] All security headers present
- [ ] Prometheus metrics exposed
- [ ] Structured JSON logging
- [ ] CI/CD pipeline operational
- [ ] Load tested to 10k rps
- [ ] HA deployment documented

### Frontier AI Ready
- [ ] OpenAPI spec AI-optimized
- [ ] Idempotency keys supported
- [ ] Batch operations available
- [ ] AI rate tiers configurable
- [ ] Semantic errors with AI context
- [ ] Webhook delivery operational

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking API changes | Low | High | Semantic versioning, deprecation policy |
| Performance regression | Medium | High | Load testing in CI, benchmarks |
| Security vulnerability | Low | Critical | Security scanning, dependency updates |
| AI misuse (rate abuse) | Medium | Medium | AI-specific rate limits, monitoring |
| Keyring unavailable | Low | High | Fallback to encrypted file storage |

---

## Conclusion

The OTTO OS Public REST API has a solid foundation. The path to production and frontier AI readiness requires:

1. **Immediate** (P0): Security hardening - TLS, headers, validation
2. **Short-term** (P1): Observability and AI-optimized OpenAPI
3. **Medium-term** (P2): Performance optimization and batch operations
4. **Long-term** (P3): Webhooks and enterprise features

Estimated timeline: 12 weeks for full production + frontier AI readiness.
