"""
Middleware for OTTO Public REST API
===================================

Provides middleware chain for request processing:
1. SecurityHeadersMiddleware - Add security headers (response wrapper)
2. AuthenticationMiddleware - API key validation
3. RateLimitMiddleware - Per-client rate limiting
4. ScopeValidationMiddleware - Permission checking
5. InputValidationMiddleware - Request body validation
6. SensitiveDataFilterMiddleware - Field filtering by scope

Middleware Pattern:
    Each middleware receives a request context, can modify it,
    and either passes to the next middleware or returns an error.

ThinkingMachines [He2025] Compliance:
- FIXED middleware order
- DETERMINISTIC: same request → same middleware decisions
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Awaitable

from ..rate_limit import RateLimiter, SlidingWindowLimiter, RateLimitExceeded
from ..http_server import HTTPRequest, HTTPResponse

from .api_keys import APIKeyManager, APIKeyValidationResult, get_manager
from .scopes import APIScope, filter_state_by_scope, has_scope, expand_scopes
from .response import APIResponse, unauthorized, forbidden, rate_limited, invalid_params
from .errors import (
    APIException,
    UnauthorizedError,
    ForbiddenError,
    RateLimitedError,
    BadRequestError,
)
from .schemas import get_schema_for_endpoint, ENDPOINT_SCHEMAS


logger = logging.getLogger(__name__)


# =============================================================================
# Request Context
# =============================================================================

@dataclass
class APIRequestContext:
    """
    Context passed through middleware chain.

    Carries both the original request and accumulated state.
    """
    # Original HTTP request
    request: HTTPRequest

    # Extracted from request
    path: str = ""
    method: str = "GET"
    body: Optional[Dict] = None
    query_params: Dict[str, str] = field(default_factory=dict)

    # Set by authentication middleware
    api_key: Optional[Any] = None  # APIKey when authenticated
    scopes: Set[APIScope] = field(default_factory=set)
    authenticated: bool = False

    # Set by rate limit middleware
    rate_limit_remaining: Optional[int] = None
    rate_limit_reset: Optional[float] = None

    # Request metadata
    request_id: str = ""
    timestamp: float = field(default_factory=time.time)

    # For response
    response_data: Any = None
    error: Optional[APIException] = None

    @classmethod
    def from_http_request(cls, request: HTTPRequest) -> "APIRequestContext":
        """Create context from HTTP request."""
        import json
        import uuid

        # Parse path and query string
        path = request.path
        query_params = {}
        if "?" in path:
            path, query_string = path.split("?", 1)
            for pair in query_string.split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    query_params[k] = v

        # Parse body if JSON
        body = None
        if request.body:
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    body = json.loads(request.body.decode())
                except (json.JSONDecodeError, UnicodeDecodeError):
                    body = None

        return cls(
            request=request,
            path=path,
            method=request.method.upper(),
            body=body,
            query_params=query_params,
            request_id=f"req_{uuid.uuid4().hex[:12]}",
        )


# =============================================================================
# Middleware Base
# =============================================================================

class Middleware(ABC):
    """
    Base class for API middleware.

    Middleware receives a context, can modify it, and either
    returns None to continue the chain or returns an HTTPResponse to stop.
    """

    @abstractmethod
    async def process(self, ctx: APIRequestContext) -> Optional[HTTPResponse]:
        """
        Process the request.

        Args:
            ctx: Request context (may be modified)

        Returns:
            None to continue chain, HTTPResponse to stop
        """
        pass


class MiddlewareChain:
    """
    Ordered chain of middleware.

    Middleware is executed in order. If any middleware returns
    a response, the chain stops and that response is returned.

    Middleware that implements wrap_response() will have their
    wrapper called on ALL responses (including those from handlers).
    """

    def __init__(self):
        self._middleware: List[Middleware] = []
        self._response_wrappers: List[Middleware] = []

    def add(self, middleware: Middleware) -> "MiddlewareChain":
        """Add middleware to chain."""
        self._middleware.append(middleware)

        # Track middleware that can wrap responses
        if hasattr(middleware, "wrap_response") and callable(middleware.wrap_response):
            self._response_wrappers.append(middleware)

        return self

    async def process(self, ctx: APIRequestContext) -> Optional[HTTPResponse]:
        """
        Process request through all middleware.

        Returns:
            HTTPResponse if any middleware stops the chain, else None
        """
        for mw in self._middleware:
            response = await mw.process(ctx)
            if response is not None:
                # Apply response wrappers to middleware-generated responses
                return self.wrap_response(response, ctx)
        return None

    def wrap_response(
        self,
        response: HTTPResponse,
        ctx: APIRequestContext,
    ) -> HTTPResponse:
        """
        Apply response wrappers to a response.

        Called automatically for middleware-generated responses,
        and should be called by the router for handler responses.

        Args:
            response: HTTP response to wrap
            ctx: Request context

        Returns:
            Wrapped HTTP response
        """
        for wrapper in self._response_wrappers:
            response = wrapper.wrap_response(response, ctx)
        return response


# =============================================================================
# Authentication Middleware
# =============================================================================

class AuthenticationMiddleware(Middleware):
    """
    Extracts and validates API key from request.

    API key can be provided via:
    - Authorization: Bearer otto_live_xxx... header
    - X-API-Key: otto_live_xxx... header
    - api_key query parameter (for WebSocket upgrade)

    On success: Sets ctx.api_key, ctx.scopes, ctx.authenticated
    On failure: Returns 401 Unauthorized response
    """

    # Paths that don't require authentication
    PUBLIC_PATHS = frozenset([
        "/api/v1/health",
        "/api/v1/openapi.json",
    ])

    def __init__(
        self,
        key_manager: Optional[APIKeyManager] = None,
        public_paths: Optional[Set[str]] = None,
    ):
        """
        Initialize authentication middleware.

        Args:
            key_manager: API key manager (uses global if not provided)
            public_paths: Additional paths that don't require auth
        """
        self._key_manager = key_manager
        self._public_paths = set(self.PUBLIC_PATHS)
        if public_paths:
            self._public_paths.update(public_paths)

    @property
    def key_manager(self) -> APIKeyManager:
        """Get key manager (global if not set)."""
        if self._key_manager is None:
            return get_manager()
        return self._key_manager

    def _extract_api_key(self, ctx: APIRequestContext) -> Optional[str]:
        """Extract API key from request."""
        # Check Authorization header
        auth_header = ctx.request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:].strip()

        # Check X-API-Key header
        api_key_header = ctx.request.headers.get("x-api-key", "")
        if api_key_header:
            return api_key_header.strip()

        # Check query parameter (for WebSocket upgrade)
        api_key_param = ctx.query_params.get("api_key", "")
        if api_key_param:
            return api_key_param

        return None

    async def process(self, ctx: APIRequestContext) -> Optional[HTTPResponse]:
        """Validate API key and set context."""
        # Check if path is public
        if ctx.path in self._public_paths:
            ctx.authenticated = False
            return None

        # Extract API key
        api_key = self._extract_api_key(ctx)
        if not api_key:
            return self._unauthorized_response(
                "Missing API key",
                ctx.request_id,
            )

        # Validate key
        result = self.key_manager.validate(api_key)
        if not result.valid:
            # Log key_id only, never the full key
            if result.key:
                logger.warning(
                    f"Invalid API key: {result.key.key_id} - {result.error_code}"
                )
            return self._unauthorized_response(
                result.error or "Invalid API key",
                ctx.request_id,
            )

        # Set context
        ctx.api_key = result.key
        ctx.scopes = expand_scopes(result.key.scopes)
        ctx.authenticated = True

        return None

    def _unauthorized_response(
        self,
        message: str,
        request_id: str,
    ) -> HTTPResponse:
        """Create 401 response."""
        import json
        response = unauthorized(message, request_id)
        return HTTPResponse(
            status=401,
            content_type="application/json",
            body=response.to_json(),
            headers={"WWW-Authenticate": "Bearer"},
        )


# =============================================================================
# Rate Limit Middleware
# =============================================================================

@dataclass
class EndpointRateLimit:
    """Rate limit configuration for an endpoint."""
    requests_per_minute: int
    burst_size: Optional[int] = None


class RateLimitMiddleware(Middleware):
    """
    Applies rate limiting per client per endpoint.

    Rate limits are tracked by (key_id, endpoint) pair.
    Uses sliding window algorithm for accuracy.

    On success: Sets ctx.rate_limit_remaining, ctx.rate_limit_reset
    On failure: Returns 429 Too Many Requests response
    """

    # Default rate limits per endpoint
    DEFAULT_LIMITS: Dict[str, EndpointRateLimit] = {
        "/api/v1/status": EndpointRateLimit(60, 10),
        "/api/v1/ping": EndpointRateLimit(120, 20),
        "/api/v1/methods": EndpointRateLimit(30, 5),
        "/api/v1/state": EndpointRateLimit(30, 5),
        "/api/v1/sessions": EndpointRateLimit(10, 3),
        "/api/v1/agents": EndpointRateLimit(30, 5),
        "/api/v1/integrations": EndpointRateLimit(30, 5),
        "/api/v1/protection/check": EndpointRateLimit(30, 5),
        "/api/v1/context": EndpointRateLimit(30, 5),
        "/api/v1/openapi.json": EndpointRateLimit(60, 10),
        "/api/v1/health": EndpointRateLimit(120, 20),
    }

    # Global default for unlisted endpoints
    GLOBAL_DEFAULT = EndpointRateLimit(30, 5)

    def __init__(
        self,
        endpoint_limits: Optional[Dict[str, EndpointRateLimit]] = None,
        global_default: Optional[EndpointRateLimit] = None,
    ):
        """
        Initialize rate limit middleware.

        Args:
            endpoint_limits: Custom limits per endpoint
            global_default: Default for unlisted endpoints
        """
        self._endpoint_limits = dict(self.DEFAULT_LIMITS)
        if endpoint_limits:
            self._endpoint_limits.update(endpoint_limits)

        self._global_default = global_default or self.GLOBAL_DEFAULT

        # Limiters keyed by (key_id, endpoint)
        self._limiters: Dict[str, SlidingWindowLimiter] = {}
        self._lock = asyncio.Lock()

    def _get_limiter_key(self, ctx: APIRequestContext) -> str:
        """Get unique key for rate limiter lookup."""
        key_id = ctx.api_key.key_id if ctx.api_key else "anonymous"
        # Normalize endpoint (remove path params)
        endpoint = self._normalize_endpoint(ctx.path)
        return f"{key_id}:{endpoint}"

    def _normalize_endpoint(self, path: str) -> str:
        """Normalize endpoint path for rate limit lookup."""
        # Replace path parameters (e.g., /agents/123 -> /agents/:id)
        parts = path.split("/")
        normalized = []
        for part in parts:
            # If it looks like an ID (alphanumeric, 8+ chars), replace
            if part and len(part) >= 8 and part.isalnum():
                normalized.append(":id")
            else:
                normalized.append(part)
        return "/".join(normalized)

    def _get_endpoint_limit(self, endpoint: str) -> EndpointRateLimit:
        """Get rate limit for endpoint."""
        # Check custom rate limit from API key
        # (Could be set in ctx.api_key.rate_limit)

        # Check endpoint-specific limit
        if endpoint in self._endpoint_limits:
            return self._endpoint_limits[endpoint]

        # Check pattern match (for parameterized endpoints)
        normalized = self._normalize_endpoint(endpoint)
        if normalized in self._endpoint_limits:
            return self._endpoint_limits[normalized]

        return self._global_default

    async def _get_or_create_limiter(
        self,
        limiter_key: str,
        endpoint: str,
    ) -> SlidingWindowLimiter:
        """Get or create rate limiter for key."""
        async with self._lock:
            if limiter_key not in self._limiters:
                limit = self._get_endpoint_limit(endpoint)
                self._limiters[limiter_key] = SlidingWindowLimiter(
                    rate=limit.requests_per_minute,
                    window_seconds=60.0,
                    block=False,  # Don't block, raise instead
                )
            return self._limiters[limiter_key]

    async def process(self, ctx: APIRequestContext) -> Optional[HTTPResponse]:
        """Apply rate limiting."""
        # Skip for health/openapi (already public, high limit)
        if ctx.path in ("/api/v1/health", "/api/v1/openapi.json"):
            return None

        limiter_key = self._get_limiter_key(ctx)
        limiter = await self._get_or_create_limiter(limiter_key, ctx.path)

        try:
            await limiter.acquire()

            # Set remaining info (approximate)
            limit = self._get_endpoint_limit(ctx.path)
            current_rate = limiter.get_current_rate()
            ctx.rate_limit_remaining = max(0, int(limit.requests_per_minute - current_rate * 60))
            ctx.rate_limit_reset = time.time() + 60

            return None

        except RateLimitExceeded as e:
            return self._rate_limited_response(
                e.retry_after,
                ctx.request_id,
            )

    def _rate_limited_response(
        self,
        retry_after: float,
        request_id: str,
    ) -> HTTPResponse:
        """Create 429 response."""
        import json
        response = rate_limited(retry_after, request_id)
        return HTTPResponse(
            status=429,
            content_type="application/json",
            body=response.to_json(),
            headers={"Retry-After": str(int(retry_after) + 1)},
        )


# =============================================================================
# Scope Validation Middleware
# =============================================================================

@dataclass
class EndpointScope:
    """Required scope for an endpoint."""
    scope: APIScope
    methods: Set[str] = field(default_factory=lambda: {"GET", "POST", "PATCH", "DELETE"})


class ScopeValidationMiddleware(Middleware):
    """
    Validates API key has required scope for endpoint.

    Each endpoint has a required scope. If the API key doesn't
    have that scope (directly or via hierarchy), access is denied.

    On success: Continues chain
    On failure: Returns 403 Forbidden response
    """

    # Required scopes per endpoint
    ENDPOINT_SCOPES: Dict[str, EndpointScope] = {
        "/api/v1/status": EndpointScope(APIScope.READ_STATUS, {"GET"}),
        "/api/v1/ping": EndpointScope(APIScope.READ_STATUS, {"GET"}),
        "/api/v1/methods": EndpointScope(APIScope.READ_STATUS, {"GET"}),
        "/api/v1/state": EndpointScope(APIScope.READ_STATE, {"GET"}),
        "/api/v1/state:PATCH": EndpointScope(APIScope.WRITE_STATE, {"PATCH"}),
        "/api/v1/sessions": EndpointScope(APIScope.WRITE_SESSION, {"POST"}),
        "/api/v1/sessions/current": EndpointScope(APIScope.WRITE_SESSION, {"DELETE"}),
        "/api/v1/agents": EndpointScope(APIScope.READ_AGENTS, {"GET"}),
        "/api/v1/agents:POST": EndpointScope(APIScope.WRITE_AGENTS, {"POST"}),
        "/api/v1/agents/:id": EndpointScope(APIScope.WRITE_AGENTS, {"DELETE"}),
        "/api/v1/integrations": EndpointScope(APIScope.READ_INTEGRATIONS, {"GET"}),
        "/api/v1/integrations/sync": EndpointScope(APIScope.WRITE_SESSION, {"POST"}),
        "/api/v1/protection/check": EndpointScope(APIScope.READ_STATE, {"POST"}),
        "/api/v1/context": EndpointScope(APIScope.READ_INTEGRATIONS, {"GET"}),
    }

    def __init__(
        self,
        endpoint_scopes: Optional[Dict[str, EndpointScope]] = None,
    ):
        """
        Initialize scope validation middleware.

        Args:
            endpoint_scopes: Custom scope requirements
        """
        self._endpoint_scopes = dict(self.ENDPOINT_SCOPES)
        if endpoint_scopes:
            self._endpoint_scopes.update(endpoint_scopes)

    def _get_required_scope(self, ctx: APIRequestContext) -> Optional[APIScope]:
        """Get required scope for request."""
        # Check method-specific scope first
        method_key = f"{ctx.path}:{ctx.method}"
        if method_key in self._endpoint_scopes:
            return self._endpoint_scopes[method_key].scope

        # Check general endpoint scope
        if ctx.path in self._endpoint_scopes:
            endpoint_scope = self._endpoint_scopes[ctx.path]
            if ctx.method in endpoint_scope.methods:
                return endpoint_scope.scope

        # Normalize path for parameterized endpoints
        normalized = self._normalize_path(ctx.path)
        if normalized in self._endpoint_scopes:
            return self._endpoint_scopes[normalized].scope

        # No scope required (public or unconfigured)
        return None

    def _normalize_path(self, path: str) -> str:
        """Normalize path for scope lookup."""
        # Replace IDs with :id
        parts = path.split("/")
        normalized = []
        for part in parts:
            if part and len(part) >= 8 and part.isalnum():
                normalized.append(":id")
            else:
                normalized.append(part)
        return "/".join(normalized)

    async def process(self, ctx: APIRequestContext) -> Optional[HTTPResponse]:
        """Validate scope for request."""
        # Skip if not authenticated (auth middleware handles)
        if not ctx.authenticated:
            return None

        required_scope = self._get_required_scope(ctx)
        if required_scope is None:
            return None

        # Check if API key has required scope
        if has_scope(ctx.scopes, required_scope):
            return None

        return self._forbidden_response(
            f"Insufficient scope. Required: {required_scope.value}",
            required_scope.value,
            ctx.request_id,
        )

    def _forbidden_response(
        self,
        message: str,
        required_scope: str,
        request_id: str,
    ) -> HTTPResponse:
        """Create 403 response."""
        import json
        response = forbidden(message, required_scope, request_id)
        return HTTPResponse(
            status=403,
            content_type="application/json",
            body=response.to_json(),
        )


# =============================================================================
# Input Validation Middleware
# =============================================================================

class InputValidationMiddleware(Middleware):
    """
    Validates request bodies against JSON schemas.

    [He2025] Compliance: FIXED schemas, DETERMINISTIC validation.

    Validates:
    - Request body structure matches schema
    - Required fields are present
    - Field types are correct
    - String lengths are within limits
    - Enum values are valid
    - No extra fields (additionalProperties: false)

    On success: Continues chain
    On failure: Returns 400 Bad Request with validation errors
    """

    def __init__(
        self,
        schemas: Optional[Dict[str, Dict[str, Any]]] = None,
        strict: bool = True,
    ):
        """
        Initialize input validation middleware.

        Args:
            schemas: Custom schema mappings (uses defaults if not provided)
            strict: If True, reject unknown fields. If False, allow them.
        """
        self._schemas = schemas or dict(ENDPOINT_SCHEMAS)
        self._strict = strict

    def _get_schema(self, method: str, path: str) -> Optional[Dict[str, Any]]:
        """Get schema for endpoint."""
        return get_schema_for_endpoint(method, path)

    def _validate(
        self,
        data: Any,
        schema: Dict[str, Any],
        path: str = "",
    ) -> List[str]:
        """
        Validate data against schema.

        Args:
            data: Data to validate
            schema: JSON schema
            path: Current path (for error messages)

        Returns:
            List of validation error messages
        """
        errors = []

        # Get expected type
        expected_type = schema.get("type")

        if expected_type == "object":
            errors.extend(self._validate_object(data, schema, path))
        elif expected_type == "array":
            errors.extend(self._validate_array(data, schema, path))
        elif expected_type == "string":
            errors.extend(self._validate_string(data, schema, path))
        elif expected_type == "integer":
            errors.extend(self._validate_integer(data, schema, path))
        elif expected_type == "number":
            errors.extend(self._validate_number(data, schema, path))
        elif expected_type == "boolean":
            errors.extend(self._validate_boolean(data, schema, path))

        return errors

    def _validate_object(
        self,
        data: Any,
        schema: Dict[str, Any],
        path: str,
    ) -> List[str]:
        """Validate object type."""
        errors = []

        if not isinstance(data, dict):
            errors.append(f"{path or 'body'}: expected object, got {type(data).__name__}")
            return errors

        properties = schema.get("properties", {})
        required = schema.get("required", [])
        additional = schema.get("additionalProperties", True)

        # Check required fields
        for field in required:
            if field not in data:
                field_path = f"{path}.{field}" if path else field
                errors.append(f"{field_path}: required field missing")

        # Check additional properties
        if additional is False and self._strict:
            allowed = set(properties.keys())
            for key in data.keys():
                if key not in allowed:
                    field_path = f"{path}.{key}" if path else key
                    errors.append(f"{field_path}: unknown field not allowed")

        # Validate each property
        for key, value in data.items():
            if key in properties:
                field_path = f"{path}.{key}" if path else key
                errors.extend(self._validate(value, properties[key], field_path))

        return errors

    def _validate_array(
        self,
        data: Any,
        schema: Dict[str, Any],
        path: str,
    ) -> List[str]:
        """Validate array type."""
        errors = []

        if not isinstance(data, list):
            errors.append(f"{path or 'body'}: expected array, got {type(data).__name__}")
            return errors

        # Check max items
        max_items = schema.get("maxItems")
        if max_items is not None and len(data) > max_items:
            errors.append(f"{path or 'body'}: array exceeds maximum {max_items} items")

        # Check min items
        min_items = schema.get("minItems")
        if min_items is not None and len(data) < min_items:
            errors.append(f"{path or 'body'}: array has fewer than minimum {min_items} items")

        # Validate items
        items_schema = schema.get("items")
        if items_schema:
            for i, item in enumerate(data):
                item_path = f"{path}[{i}]" if path else f"[{i}]"
                errors.extend(self._validate(item, items_schema, item_path))

        return errors

    def _validate_string(
        self,
        data: Any,
        schema: Dict[str, Any],
        path: str,
    ) -> List[str]:
        """Validate string type."""
        errors = []

        if not isinstance(data, str):
            errors.append(f"{path or 'body'}: expected string, got {type(data).__name__}")
            return errors

        # Check min length
        min_length = schema.get("minLength")
        if min_length is not None and len(data) < min_length:
            errors.append(f"{path or 'body'}: string shorter than minimum {min_length} characters")

        # Check max length
        max_length = schema.get("maxLength")
        if max_length is not None and len(data) > max_length:
            errors.append(f"{path or 'body'}: string exceeds maximum {max_length} characters")

        # Check enum
        enum_values = schema.get("enum")
        if enum_values is not None and data not in enum_values:
            errors.append(f"{path or 'body'}: value must be one of {enum_values}")

        # Check pattern
        pattern = schema.get("pattern")
        if pattern is not None:
            import re
            if not re.match(pattern, data):
                errors.append(f"{path or 'body'}: value does not match pattern '{pattern}'")

        return errors

    def _validate_integer(
        self,
        data: Any,
        schema: Dict[str, Any],
        path: str,
    ) -> List[str]:
        """Validate integer type."""
        errors = []

        if not isinstance(data, int) or isinstance(data, bool):
            errors.append(f"{path or 'body'}: expected integer, got {type(data).__name__}")
            return errors

        # Check minimum
        minimum = schema.get("minimum")
        if minimum is not None and data < minimum:
            errors.append(f"{path or 'body'}: value {data} is less than minimum {minimum}")

        # Check maximum
        maximum = schema.get("maximum")
        if maximum is not None and data > maximum:
            errors.append(f"{path or 'body'}: value {data} exceeds maximum {maximum}")

        return errors

    def _validate_number(
        self,
        data: Any,
        schema: Dict[str, Any],
        path: str,
    ) -> List[str]:
        """Validate number type."""
        errors = []

        if not isinstance(data, (int, float)) or isinstance(data, bool):
            errors.append(f"{path or 'body'}: expected number, got {type(data).__name__}")
            return errors

        # Check minimum
        minimum = schema.get("minimum")
        if minimum is not None and data < minimum:
            errors.append(f"{path or 'body'}: value {data} is less than minimum {minimum}")

        # Check maximum
        maximum = schema.get("maximum")
        if maximum is not None and data > maximum:
            errors.append(f"{path or 'body'}: value {data} exceeds maximum {maximum}")

        return errors

    def _validate_boolean(
        self,
        data: Any,
        schema: Dict[str, Any],
        path: str,
    ) -> List[str]:
        """Validate boolean type."""
        errors = []

        if not isinstance(data, bool):
            errors.append(f"{path or 'body'}: expected boolean, got {type(data).__name__}")

        return errors

    async def process(self, ctx: APIRequestContext) -> Optional[HTTPResponse]:
        """Validate request body against schema."""
        # Skip if no body to validate
        if ctx.body is None:
            # Check if body is required
            schema = self._get_schema(ctx.method, ctx.path)
            if schema and schema.get("required"):
                return self._invalid_params_response(
                    ["Request body is required"],
                    ctx.request_id,
                )
            return None

        # Get schema for endpoint
        schema = self._get_schema(ctx.method, ctx.path)
        if schema is None:
            # No schema defined, skip validation
            return None

        # Validate
        errors = self._validate(ctx.body, schema)
        if errors:
            return self._invalid_params_response(errors, ctx.request_id)

        return None

    def _invalid_params_response(
        self,
        errors: List[str],
        request_id: str,
    ) -> HTTPResponse:
        """Create 400 response for validation errors."""
        response = invalid_params(
            errors[0] if len(errors) == 1 else "Validation failed",
            {"validation_errors": errors},
            request_id,
        )
        return HTTPResponse(
            status=400,
            content_type="application/json",
            body=response.to_json(),
        )


# =============================================================================
# Security Headers Middleware
# =============================================================================

class SecurityHeadersMiddleware(Middleware):
    """
    Add security headers to all responses.

    [He2025] Compliance: FIXED headers, no runtime variation.

    Headers added:
    - X-Content-Type-Options: nosniff (prevent MIME sniffing)
    - X-Frame-Options: DENY (prevent clickjacking)
    - X-XSS-Protection: 1; mode=block (legacy XSS filter)
    - Referrer-Policy: strict-origin-when-cross-origin
    - Content-Security-Policy: default-src 'none' (strict CSP)
    - X-Request-Id: {request_id} (for tracing)
    """

    # Fixed security headers - [He2025] DETERMINISTIC
    HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Content-Security-Policy": "default-src 'none'",
    }

    @classmethod
    def add_headers(
        cls,
        response: HTTPResponse,
        request_id: str = "",
    ) -> HTTPResponse:
        """
        Add security headers to an HTTP response.

        This method can be called directly to add security headers
        to any response, including those created outside the middleware chain.

        Args:
            response: HTTP response to modify
            request_id: Request ID for tracing (optional)

        Returns:
            The same response with security headers added
        """
        for header, value in cls.HEADERS.items():
            if header not in response.headers:
                response.headers[header] = value

        # Add request ID for tracing
        if request_id and "X-Request-Id" not in response.headers:
            response.headers["X-Request-Id"] = request_id

        return response

    async def process(self, ctx: APIRequestContext) -> Optional[HTTPResponse]:
        """
        Process request - this middleware passes through.

        Security headers are applied to responses via wrap_response()
        which is called by MiddlewareChain after processing completes.

        This process() method exists for compatibility with the chain
        but always returns None to continue processing.
        """
        return None

    def wrap_response(
        self,
        response: HTTPResponse,
        ctx: APIRequestContext,
    ) -> HTTPResponse:
        """
        Wrap a response with security headers.

        Called by MiddlewareChain after all processing completes.
        """
        return self.add_headers(response, ctx.request_id)


# =============================================================================
# Replay Protection Middleware
# =============================================================================

class ReplayProtectionMiddleware(Middleware):
    """
    Protects against request replay attacks.

    [He2025] Compliance:
    - FIXED time window (no runtime variation)
    - DETERMINISTIC nonce validation
    - Bounded memory for nonce storage

    Validates:
    - X-Request-Timestamp header (within time window)
    - X-Request-Nonce header (unique, not seen before)

    Both headers are required for write operations (POST, PUT, PATCH, DELETE).
    GET requests are not protected (read-only, idempotent).
    """

    # [He2025] FIXED configuration - no runtime variation
    DEFAULT_TIME_WINDOW_SECONDS: int = 300  # 5 minutes
    DEFAULT_MAX_NONCES: int = 100000  # Max stored nonces
    DEFAULT_CLEANUP_THRESHOLD: float = 0.9  # Cleanup at 90% capacity

    # Methods requiring replay protection
    PROTECTED_METHODS: frozenset = frozenset(["POST", "PUT", "PATCH", "DELETE"])

    def __init__(
        self,
        time_window_seconds: Optional[int] = None,
        max_nonces: Optional[int] = None,
        protected_methods: Optional[Set[str]] = None,
    ):
        """
        Initialize replay protection middleware.

        [He2025] Compliance: Parameters are FIXED at initialization.

        Args:
            time_window_seconds: Max age of valid requests. Default: 300 (5 min).
            max_nonces: Maximum stored nonces before cleanup. Default: 100000.
            protected_methods: HTTP methods to protect. Default: POST, PUT, PATCH, DELETE.
        """
        self._time_window = (
            time_window_seconds
            if time_window_seconds is not None
            else self.DEFAULT_TIME_WINDOW_SECONDS
        )
        self._max_nonces = max_nonces or self.DEFAULT_MAX_NONCES
        self._protected_methods = frozenset(
            protected_methods or self.PROTECTED_METHODS
        )

        # Nonce storage: {nonce: expiry_timestamp}
        self._nonces: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    def _is_protected_method(self, method: str) -> bool:
        """Check if method requires replay protection."""
        return method.upper() in self._protected_methods

    def _validate_timestamp(self, timestamp_str: str) -> Tuple[bool, str]:
        """
        Validate request timestamp.

        Args:
            timestamp_str: Unix timestamp as string

        Returns:
            (is_valid, error_message)
        """
        try:
            timestamp = float(timestamp_str)
        except (ValueError, TypeError):
            return False, "Invalid timestamp format"

        current_time = time.time()
        age = current_time - timestamp

        # Check if timestamp is in the future (clock skew tolerance: 60s)
        if age < -60:
            return False, "Timestamp is in the future"

        # Check if timestamp is too old
        if age > self._time_window:
            return False, f"Request expired (max age: {self._time_window}s)"

        return True, ""

    def _validate_nonce_format(self, nonce: str) -> Tuple[bool, str]:
        """
        Validate nonce format.

        Args:
            nonce: Request nonce

        Returns:
            (is_valid, error_message)
        """
        if not nonce:
            return False, "Nonce is required"

        # Nonce must be reasonable length
        if len(nonce) < 8:
            return False, "Nonce too short (min 8 characters)"

        if len(nonce) > 128:
            return False, "Nonce too long (max 128 characters)"

        # Alphanumeric plus common safe characters
        import re
        if not re.match(r'^[a-zA-Z0-9_\-]+$', nonce):
            return False, "Nonce contains invalid characters"

        return True, ""

    async def _check_and_store_nonce(
        self,
        nonce: str,
        expiry: float,
    ) -> Tuple[bool, str]:
        """
        Check if nonce is unique and store it.

        Thread-safe nonce checking and storage.

        Args:
            nonce: Request nonce
            expiry: When this nonce expires

        Returns:
            (is_unique, error_message)
        """
        async with self._lock:
            # Cleanup expired nonces if at capacity
            if len(self._nonces) >= self._max_nonces * self.DEFAULT_CLEANUP_THRESHOLD:
                await self._cleanup_expired_nonces()

            # Check if nonce already used
            if nonce in self._nonces:
                return False, "Nonce already used (possible replay attack)"

            # Store nonce with expiry
            self._nonces[nonce] = expiry
            return True, ""

    async def _cleanup_expired_nonces(self) -> int:
        """
        Remove expired nonces from storage.

        Returns:
            Number of nonces removed
        """
        current_time = time.time()
        expired = [
            nonce for nonce, expiry in self._nonces.items()
            if expiry < current_time
        ]

        for nonce in expired:
            del self._nonces[nonce]

        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired nonces")

        return len(expired)

    async def process(self, ctx: APIRequestContext) -> Optional[HTTPResponse]:
        """
        Validate request against replay attacks.

        Checks:
        1. Method is protected (POST, PUT, PATCH, DELETE)
        2. Timestamp header present and valid
        3. Nonce header present, valid, and unique
        """
        # Skip unprotected methods
        if not self._is_protected_method(ctx.method):
            return None

        # Get timestamp header
        timestamp_str = ctx.request.headers.get("x-request-timestamp", "")
        if not timestamp_str:
            return self._replay_error_response(
                "Missing X-Request-Timestamp header",
                ctx.request_id,
            )

        # Validate timestamp
        valid, error = self._validate_timestamp(timestamp_str)
        if not valid:
            return self._replay_error_response(error, ctx.request_id)

        # Get nonce header
        nonce = ctx.request.headers.get("x-request-nonce", "")
        if not nonce:
            return self._replay_error_response(
                "Missing X-Request-Nonce header",
                ctx.request_id,
            )

        # Validate nonce format
        valid, error = self._validate_nonce_format(nonce)
        if not valid:
            return self._replay_error_response(error, ctx.request_id)

        # Check and store nonce
        expiry = time.time() + self._time_window
        unique, error = await self._check_and_store_nonce(nonce, expiry)
        if not unique:
            logger.warning(
                f"Replay attack detected: nonce={nonce[:8]}... "
                f"request_id={ctx.request_id}"
            )
            return self._replay_error_response(error, ctx.request_id)

        return None

    def _replay_error_response(
        self,
        message: str,
        request_id: str,
    ) -> HTTPResponse:
        """Create 400 response for replay protection errors."""
        import json
        from .response import error

        response = error(
            code="REPLAY_PROTECTION_FAILED",
            message=message,
            request_id=request_id,
        )
        return HTTPResponse(
            status=400,
            content_type="application/json",
            body=response.to_json(),
        )

    def get_stats(self) -> Dict[str, Any]:
        """
        Get replay protection statistics.

        Returns:
            Dict with nonce storage stats
        """
        return {
            "stored_nonces": len(self._nonces),
            "max_nonces": self._max_nonces,
            "time_window_seconds": self._time_window,
            "utilization_percent": (len(self._nonces) / self._max_nonces) * 100,
        }


# =============================================================================
# CORS Middleware
# =============================================================================

class CORSMiddleware(Middleware):
    """
    Cross-Origin Resource Sharing (CORS) middleware.

    [He2025] Compliance: FIXED allowed origins, methods, and headers.
    No runtime variation in CORS policy.

    Handles:
    - Preflight OPTIONS requests
    - CORS headers on all responses
    - Origin validation

    Headers added:
    - Access-Control-Allow-Origin
    - Access-Control-Allow-Methods
    - Access-Control-Allow-Headers
    - Access-Control-Allow-Credentials
    - Access-Control-Max-Age
    - Access-Control-Expose-Headers
    """

    # [He2025] FIXED CORS configuration - no runtime variation
    DEFAULT_ALLOWED_METHODS: frozenset = frozenset([
        "GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"
    ])

    DEFAULT_ALLOWED_HEADERS: frozenset = frozenset([
        "Authorization",
        "Content-Type",
        "X-API-Key",
        "X-Request-Id",
        "Accept",
        "Accept-Language",
        "Content-Language",
    ])

    DEFAULT_EXPOSE_HEADERS: frozenset = frozenset([
        "X-Request-Id",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "Retry-After",
    ])

    # [He2025] FIXED max-age for preflight caching (24 hours)
    DEFAULT_MAX_AGE: int = 86400

    def __init__(
        self,
        allowed_origins: Optional[Set[str]] = None,
        allowed_methods: Optional[Set[str]] = None,
        allowed_headers: Optional[Set[str]] = None,
        expose_headers: Optional[Set[str]] = None,
        allow_credentials: bool = False,
        max_age: Optional[int] = None,
    ):
        """
        Initialize CORS middleware.

        [He2025] Compliance: All parameters are FIXED at initialization.
        No runtime changes to CORS policy.

        Args:
            allowed_origins: Set of allowed origins. Use {"*"} for any origin.
                            Default: empty (no CORS). Must be explicitly set.
            allowed_methods: Allowed HTTP methods. Default: standard REST methods.
            allowed_headers: Allowed request headers. Default: standard API headers.
            expose_headers: Headers exposed to client. Default: rate limit headers.
            allow_credentials: Allow credentials (cookies, auth). Default: False.
            max_age: Preflight cache duration in seconds. Default: 86400 (24h).
        """
        # FIXED at init - [He2025] determinism
        self._allowed_origins: frozenset = frozenset(allowed_origins or set())
        self._allowed_methods: frozenset = frozenset(
            allowed_methods or self.DEFAULT_ALLOWED_METHODS
        )
        self._allowed_headers: frozenset = frozenset(
            allowed_headers or self.DEFAULT_ALLOWED_HEADERS
        )
        self._expose_headers: frozenset = frozenset(
            expose_headers or self.DEFAULT_EXPOSE_HEADERS
        )
        self._allow_credentials: bool = allow_credentials
        self._max_age: int = max_age if max_age is not None else self.DEFAULT_MAX_AGE

        # Pre-compute header values for determinism
        self._methods_str: str = ", ".join(sorted(self._allowed_methods))
        self._headers_str: str = ", ".join(sorted(self._allowed_headers))
        self._expose_str: str = ", ".join(sorted(self._expose_headers))

    def _is_origin_allowed(self, origin: str) -> bool:
        """Check if origin is allowed."""
        if not origin:
            return False
        if "*" in self._allowed_origins:
            return True
        return origin in self._allowed_origins

    def _get_allowed_origin(self, request_origin: str) -> Optional[str]:
        """
        Get the allowed origin for CORS response.

        Returns:
            The allowed origin or None if not allowed
        """
        if not self._allowed_origins:
            return None

        if "*" in self._allowed_origins:
            # If credentials allowed, must echo back origin, not *
            if self._allow_credentials and request_origin:
                return request_origin
            return "*"

        if request_origin in self._allowed_origins:
            return request_origin

        return None

    def _build_cors_headers(self, origin: str) -> Dict[str, str]:
        """
        Build CORS response headers.

        [He2025] DETERMINISTIC: Same origin → same headers.
        """
        allowed_origin = self._get_allowed_origin(origin)
        if not allowed_origin:
            return {}

        headers = {
            "Access-Control-Allow-Origin": allowed_origin,
            "Access-Control-Allow-Methods": self._methods_str,
            "Access-Control-Allow-Headers": self._headers_str,
            "Access-Control-Max-Age": str(self._max_age),
        }

        if self._expose_headers:
            headers["Access-Control-Expose-Headers"] = self._expose_str

        if self._allow_credentials:
            headers["Access-Control-Allow-Credentials"] = "true"

        # Vary header for caching correctness
        headers["Vary"] = "Origin"

        return headers

    def _handle_preflight(self, ctx: APIRequestContext) -> HTTPResponse:
        """
        Handle CORS preflight OPTIONS request.

        Returns 204 No Content with CORS headers if allowed,
        or 403 Forbidden if origin not allowed.
        """
        origin = ctx.request.headers.get("origin", "")
        cors_headers = self._build_cors_headers(origin)

        if not cors_headers:
            # Origin not allowed
            return HTTPResponse(
                status=403,
                content_type="text/plain",
                body="CORS origin not allowed",
                headers={"Vary": "Origin"},
            )

        return HTTPResponse(
            status=204,
            content_type="text/plain",
            body="",
            headers=cors_headers,
        )

    async def process(self, ctx: APIRequestContext) -> Optional[HTTPResponse]:
        """
        Process CORS for request.

        - OPTIONS preflight: Return 204 with CORS headers
        - Other requests: Continue chain, headers added via wrap_response()
        """
        # Handle preflight
        if ctx.method == "OPTIONS":
            return self._handle_preflight(ctx)

        # Other requests continue - CORS headers added in wrap_response
        return None

    def wrap_response(
        self,
        response: HTTPResponse,
        ctx: APIRequestContext,
    ) -> HTTPResponse:
        """
        Add CORS headers to response.

        Called by MiddlewareChain after all processing completes.
        """
        origin = ctx.request.headers.get("origin", "")
        if not origin:
            return response

        cors_headers = self._build_cors_headers(origin)
        for header, value in cors_headers.items():
            if header not in response.headers:
                response.headers[header] = value

        return response


# =============================================================================
# Sensitive Data Filter Middleware
# =============================================================================

class SensitiveDataFilterMiddleware(Middleware):
    """
    Filters sensitive fields from state responses.

    If API key doesn't have READ_STATE_FULL scope, sensitive
    fields are removed from state data in the response.

    This middleware runs AFTER the handler, filtering the response.
    """

    async def process(self, ctx: APIRequestContext) -> Optional[HTTPResponse]:
        """
        Filter sensitive data from response.

        Note: This should be called after the handler sets ctx.response_data.
        """
        # Only filter state responses
        if not ctx.path.startswith("/api/v1/state"):
            return None

        # Only filter if we have response data
        if ctx.response_data is None or not isinstance(ctx.response_data, dict):
            return None

        # Check if full state access
        if APIScope.READ_STATE_FULL in ctx.scopes:
            return None

        # Filter sensitive fields
        ctx.response_data = filter_state_by_scope(ctx.response_data, ctx.scopes)
        return None


# =============================================================================
# Middleware Factory
# =============================================================================

def create_api_middleware(
    key_manager: Optional[APIKeyManager] = None,
    public_paths: Optional[Set[str]] = None,
    endpoint_limits: Optional[Dict[str, EndpointRateLimit]] = None,
    endpoint_scopes: Optional[Dict[str, EndpointScope]] = None,
    include_security_headers: bool = True,
    include_input_validation: bool = True,
    validation_strict: bool = True,
    cors_origins: Optional[Set[str]] = None,
    cors_credentials: bool = False,
    include_replay_protection: bool = False,
    replay_time_window: Optional[int] = None,
) -> MiddlewareChain:
    """
    Create the standard API middleware chain.

    Order is FIXED (per ThinkingMachines [He2025]):
    1. CORS - Handle preflight and add CORS headers (wrapper)
    2. Security Headers - Add security headers to ALL responses (wrapper)
    3. Authentication - Who is this?
    4. Rate Limiting - Are they allowed this many requests?
    5. Replay Protection - Is this a replay attack? (optional)
    6. Scope Validation - Do they have permission?
    7. Input Validation - Is the request body valid?

    Note: CORS and SecurityHeaders are response wrappers - added first
    so wrap_response() is called last (on all responses).

    Args:
        key_manager: Custom API key manager
        public_paths: Additional public paths
        endpoint_limits: Custom rate limits
        endpoint_scopes: Custom scope requirements
        include_security_headers: Whether to add security headers (default True)
        include_input_validation: Whether to validate request bodies (default True)
        validation_strict: If True, reject unknown fields (default True)
        cors_origins: Set of allowed CORS origins. None = no CORS. {"*"} = any origin.
        cors_credentials: Whether to allow credentials with CORS (default False)
        include_replay_protection: Whether to enable replay protection (default False)
        replay_time_window: Replay protection time window in seconds (default 300)

    Returns:
        Configured middleware chain
    """
    chain = MiddlewareChain()

    # CORS wrapper - added first for preflight handling
    if cors_origins is not None:
        chain.add(CORSMiddleware(
            allowed_origins=cors_origins,
            allow_credentials=cors_credentials,
        ))

    # Security headers wrapper - added so it wraps all responses
    if include_security_headers:
        chain.add(SecurityHeadersMiddleware())

    # Request processing middleware
    chain.add(AuthenticationMiddleware(key_manager, public_paths))
    chain.add(RateLimitMiddleware(endpoint_limits))

    # Replay protection - after rate limiting to avoid DoS via nonce storage
    if include_replay_protection:
        chain.add(ReplayProtectionMiddleware(
            time_window_seconds=replay_time_window,
        ))

    chain.add(ScopeValidationMiddleware(endpoint_scopes))

    # Input validation - after auth/scope so unauthorized requests fail fast
    if include_input_validation:
        chain.add(InputValidationMiddleware(strict=validation_strict))

    return chain


__all__ = [
    # Context
    "APIRequestContext",

    # Base classes
    "Middleware",
    "MiddlewareChain",

    # Middleware implementations
    "SecurityHeadersMiddleware",
    "CORSMiddleware",
    "ReplayProtectionMiddleware",
    "AuthenticationMiddleware",
    "RateLimitMiddleware",
    "ScopeValidationMiddleware",
    "InputValidationMiddleware",
    "SensitiveDataFilterMiddleware",

    # Configuration
    "EndpointRateLimit",
    "EndpointScope",

    # Factory
    "create_api_middleware",
]
