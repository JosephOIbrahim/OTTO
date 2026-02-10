# OTTO OS API - Immediate Next Steps

**Status**: Ready for implementation
**Priority**: Start with P0 items

---

## Quick Reference: What to Build Next

### P0 - Do This Week (Security Critical)

```
┌─────────────────────────────────────────────────────────────┐
│ 1. SecurityHeadersMiddleware                                │
│    File: src/otto/api/middleware.py                         │
│    Effort: 2-4 hours                                        │
│    Tests: ~10                                               │
├─────────────────────────────────────────────────────────────┤
│ 2. InputValidationMiddleware                                │
│    File: src/otto/api/middleware.py                         │
│    Effort: 4-6 hours                                        │
│    Tests: ~20                                               │
├─────────────────────────────────────────────────────────────┤
│ 3. TLS Configuration                                        │
│    File: src/otto/api/tls.py (new)                          │
│    Effort: 4-6 hours                                        │
│    Tests: ~15                                               │
└─────────────────────────────────────────────────────────────┘
```

### P1 - Do Next Week (Observability + AI)

```
┌─────────────────────────────────────────────────────────────┐
│ 4. PrometheusMetrics                                        │
│    File: src/otto/api/metrics.py (new)                      │
│    Effort: 4-6 hours                                        │
│    Tests: ~20                                               │
├─────────────────────────────────────────────────────────────┤
│ 5. OpenAPI AI Extensions                                    │
│    File: src/otto/api/openapi.py                            │
│    Effort: 2-4 hours                                        │
│    Tests: ~5                                                │
├─────────────────────────────────────────────────────────────┤
│ 6. IdempotencyMiddleware                                    │
│    File: src/otto/api/middleware.py                         │
│    Effort: 4-6 hours                                        │
│    Tests: ~20                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Sketches

### 1. Security Headers (Copy-Paste Ready)

```python
# Add to src/otto/api/middleware.py

class SecurityHeadersMiddleware(Middleware):
    """
    Add security headers to all responses.

    Determinism: FIXED headers, no runtime variation.
    """
    HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Content-Security-Policy": "default-src 'none'",
    }

    async def process(
        self,
        ctx: APIRequestContext,
        next: Callable,
    ) -> Optional[HTTPResponse]:
        response = await next(ctx)

        if response:
            # Add security headers
            for header, value in self.HEADERS.items():
                if header not in response.headers:
                    response.headers[header] = value

            # Add request ID for tracing
            response.headers["X-Request-Id"] = ctx.request_id

        return response
```

### 2. Input Validation Schema Example

```python
# Add to src/otto/api/schemas.py (new file)

STATE_UPDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "session_goal": {"type": "string", "maxLength": 500},
        "active_mode": {
            "type": "string",
            "enum": ["focused", "exploring", "teaching", "recovery"]
        },
    },
    "additionalProperties": False,
}

AGENT_SPAWN_SCHEMA = {
    "type": "object",
    "required": ["task"],
    "properties": {
        "task": {"type": "string", "minLength": 1, "maxLength": 1000},
        "type": {"type": "string", "enum": ["researcher", "coder", "reviewer"]},
        "priority": {"type": "integer", "minimum": 1, "maximum": 10},
    },
    "additionalProperties": False,
}
```

### 3. Prometheus Metrics Skeleton

```python
# src/otto/api/metrics.py (new file)

"""
Prometheus metrics for OTTO API.

Determinism: FIXED metric names, DETERMINISTIC labels.
"""

from prometheus_client import Counter, Histogram, Gauge, generate_latest

# Counters
REQUESTS_TOTAL = Counter(
    'otto_api_requests_total',
    'Total API requests',
    ['method', 'path', 'status']
)

AUTH_FAILURES = Counter(
    'otto_api_auth_failures_total',
    'Authentication failures',
    ['reason']
)

RATE_LIMIT_HITS = Counter(
    'otto_api_rate_limit_hits_total',
    'Rate limit hits',
    ['path']
)

# Histograms
REQUEST_DURATION = Histogram(
    'otto_api_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'path'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)

# Gauges
ACTIVE_KEYS = Gauge(
    'otto_api_keys_active',
    'Number of active API keys'
)


class MetricsMiddleware(Middleware):
    """Record metrics for each request."""

    async def process(self, ctx, next):
        import time
        start = time.perf_counter()

        response = await next(ctx)

        duration = time.perf_counter() - start
        status = response.status if response else 500
        path = self._normalize_path(ctx.path)

        REQUESTS_TOTAL.labels(ctx.method, path, status).inc()
        REQUEST_DURATION.labels(ctx.method, path).observe(duration)

        return response

    def _normalize_path(self, path: str) -> str:
        """Normalize path for metrics (replace IDs with :id)."""
        import re
        return re.sub(r'/[a-f0-9]{8,}', '/:id', path)
```

### 4. OpenAPI AI Extensions

```python
# Add to src/otto/api/openapi.py

def _add_ai_extensions(spec: dict) -> dict:
    """
    Add AI tool use extensions to OpenAPI spec.

    These extensions help AI agents understand how to use the API effectively.
    """
    ai_extensions = {
        "/api/v1/status": {
            "x-ai-tool-use": {
                "safe_for_polling": True,
                "recommended_interval_seconds": 30,
                "idempotent": True,
                "use_cases": [
                    "Check OTTO OS health",
                    "Monitor cognitive state",
                    "Verify before operations"
                ]
            }
        },
        "/api/v1/agents": {
            "x-ai-tool-use": {
                "safe_for_polling": True,
                "idempotent": True,  # GET only
                "use_cases": [
                    "List running agents",
                    "Monitor agent progress",
                    "Check agent availability"
                ]
            }
        },
        # ... more endpoints
    }

    for path, extensions in ai_extensions.items():
        if path in spec.get("paths", {}):
            for method in spec["paths"][path]:
                if method != "parameters":
                    spec["paths"][path][method].update(extensions)

    return spec
```

### 5. Idempotency Key Handler

```python
# Add to src/otto/api/middleware.py

class IdempotencyMiddleware(Middleware):
    """
    Handle idempotency keys for safe retries.

    Determinism: DETERMINISTIC key matching, FIXED TTL.

    Usage:
        Client sends: X-Idempotency-Key: <uuid>
        Server returns cached response for repeated requests.
    """
    TTL_SECONDS = 86400  # 24 hours
    HEADER_NAME = "X-Idempotency-Key"
    REPLAY_HEADER = "X-Idempotency-Replayed"

    def __init__(self):
        # In-memory cache (use Redis for production HA)
        self._cache: Dict[str, Tuple[float, HTTPResponse]] = {}

    async def process(self, ctx, next):
        key = ctx.request.headers.get(self.HEADER_NAME)

        if not key:
            return await next(ctx)

        # Check cache
        if key in self._cache:
            timestamp, cached_response = self._cache[key]
            if time.time() - timestamp < self.TTL_SECONDS:
                cached_response.headers[self.REPLAY_HEADER] = "true"
                return cached_response
            else:
                del self._cache[key]

        # Process request
        response = await next(ctx)

        # Cache response for non-GET requests
        if response and ctx.method != "GET":
            self._cache[key] = (time.time(), response)
            response.headers[self.HEADER_NAME] = key

        return response
```

---

## Updated Middleware Chain Order

```python
# After all additions, the chain becomes:

def create_api_middleware(...) -> MiddlewareChain:
    """
    Order is FIXED (per [He2025]):
    1. Metrics - Record timing (must be first)
    2. Security Headers - Add security headers
    3. Idempotency - Check/cache responses
    4. Authentication - Who is this?
    5. Rate Limiting - Are they allowed this many requests?
    6. Scope Validation - Do they have permission?
    7. Input Validation - Is the request valid?
    """
    return (
        MiddlewareChain()
        .add(MetricsMiddleware())
        .add(SecurityHeadersMiddleware())
        .add(IdempotencyMiddleware())
        .add(AuthenticationMiddleware(key_manager, public_paths))
        .add(RateLimitMiddleware(endpoint_limits))
        .add(ScopeValidationMiddleware(endpoint_scopes))
        .add(InputValidationMiddleware())
    )
```

---

## Test Commands

```bash
# After implementing each component:

# Security headers
pytest tests/test_api_security_headers.py -v

# Input validation
pytest tests/test_api_input_validation.py -v

# Metrics
pytest tests/test_api_metrics.py -v

# Idempotency
pytest tests/test_api_idempotency.py -v

# Full API suite
pytest tests/test_api*.py -v

# Full project
pytest tests/ -v
```

---

## Checklist

### This Week (P0)
- [ ] Implement SecurityHeadersMiddleware
- [ ] Write security header tests
- [ ] Implement InputValidationMiddleware
- [ ] Write input validation tests
- [ ] Create TLS configuration module
- [ ] Write TLS tests
- [ ] Update middleware chain order

### Next Week (P1)
- [ ] Implement MetricsMiddleware
- [ ] Add /metrics endpoint
- [ ] Write metrics tests
- [ ] Add AI extensions to OpenAPI
- [ ] Implement IdempotencyMiddleware
- [ ] Write idempotency tests

### Verification
- [ ] All new tests pass
- [ ] All existing 2350 tests still pass
- [ ] Determinism maintained
- [ ] Documentation updated

---

## Questions to Answer Before Starting

1. **TLS**: Self-signed certs for dev, or integrate with Let's Encrypt?
2. **Metrics**: Prometheus endpoint public or protected?
3. **Idempotency Cache**: In-memory or Redis for HA?
4. **Rate Limit Tiers**: When to implement AI-specific tiers?
