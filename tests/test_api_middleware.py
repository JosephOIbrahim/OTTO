"""
Tests for OTTO Public REST API - Phase 2 Middleware
====================================================

Tests for:
- AuthenticationMiddleware
- RateLimitMiddleware
- ScopeValidationMiddleware
- SensitiveDataFilterMiddleware
- MiddlewareChain
"""

import pytest
import asyncio
import time
from unittest.mock import MagicMock, patch

from otto.http_server import HTTPRequest, HTTPResponse
from otto.api.scopes import APIScope, SENSITIVE_FIELDS
from otto.api.api_keys import APIKey, APIKeyManager
from otto.api.middleware import (
    APIRequestContext,
    Middleware,
    MiddlewareChain,
    AuthenticationMiddleware,
    RateLimitMiddleware,
    ScopeValidationMiddleware,
    SensitiveDataFilterMiddleware,
    EndpointRateLimit,
    EndpointScope,
    create_api_middleware,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def http_request():
    """Create a basic HTTP request."""
    return HTTPRequest(
        method="GET",
        path="/api/v1/status",
        headers={"content-type": "application/json"},
        body=b"",
    )


@pytest.fixture
def http_request_with_auth(tmp_path):
    """Create HTTP request with valid API key."""
    # Create manager and key
    manager = APIKeyManager(keys_dir=tmp_path, use_keyring=False)
    full_key, key = manager.create(
        name="Test Key",
        scopes={APIScope.READ_STATUS, APIScope.READ_STATE},
    )

    return HTTPRequest(
        method="GET",
        path="/api/v1/status",
        headers={
            "content-type": "application/json",
            "authorization": f"Bearer {full_key}",
        },
        body=b"",
    ), manager, full_key


@pytest.fixture
def api_context(http_request):
    """Create an API request context."""
    return APIRequestContext.from_http_request(http_request)


# =============================================================================
# APIRequestContext Tests
# =============================================================================

class TestAPIRequestContext:
    """Tests for request context creation."""

    def test_from_http_request_basic(self, http_request):
        """Should parse basic HTTP request."""
        ctx = APIRequestContext.from_http_request(http_request)
        assert ctx.path == "/api/v1/status"
        assert ctx.method == "GET"
        assert ctx.request_id.startswith("req_")

    def test_from_http_request_with_query(self):
        """Should parse query parameters."""
        request = HTTPRequest(
            method="GET",
            path="/api/v1/status?foo=bar&baz=qux",
            headers={},
            body=b"",
        )
        ctx = APIRequestContext.from_http_request(request)
        assert ctx.path == "/api/v1/status"
        assert ctx.query_params == {"foo": "bar", "baz": "qux"}

    def test_from_http_request_with_body(self):
        """Should parse JSON body."""
        request = HTTPRequest(
            method="POST",
            path="/api/v1/state",
            headers={"content-type": "application/json"},
            body=b'{"burnout_level": "GREEN"}',
        )
        ctx = APIRequestContext.from_http_request(request)
        assert ctx.body == {"burnout_level": "GREEN"}

    def test_from_http_request_invalid_json(self):
        """Should handle invalid JSON gracefully."""
        request = HTTPRequest(
            method="POST",
            path="/api/v1/state",
            headers={"content-type": "application/json"},
            body=b"not json",
        )
        ctx = APIRequestContext.from_http_request(request)
        assert ctx.body is None

    def test_timestamp_is_set(self, http_request):
        """Should set timestamp."""
        ctx = APIRequestContext.from_http_request(http_request)
        assert ctx.timestamp > 0
        assert time.time() - ctx.timestamp < 1.0


# =============================================================================
# MiddlewareChain Tests
# =============================================================================

class TestMiddlewareChain:
    """Tests for middleware chain."""

    @pytest.mark.asyncio
    async def test_empty_chain(self, api_context):
        """Empty chain should return None."""
        chain = MiddlewareChain()
        result = await chain.process(api_context)
        assert result is None

    @pytest.mark.asyncio
    async def test_single_middleware_pass(self, api_context):
        """Single passing middleware should return None."""
        class PassMiddleware(Middleware):
            async def process(self, ctx):
                ctx.authenticated = True  # Modify context
                return None

        chain = MiddlewareChain().add(PassMiddleware())
        result = await chain.process(api_context)
        assert result is None
        assert api_context.authenticated is True

    @pytest.mark.asyncio
    async def test_single_middleware_stop(self, api_context):
        """Single stopping middleware should return response."""
        class StopMiddleware(Middleware):
            async def process(self, ctx):
                return HTTPResponse(401, "application/json", '{"error": "no"}')

        chain = MiddlewareChain().add(StopMiddleware())
        result = await chain.process(api_context)
        assert result is not None
        assert result.status == 401

    @pytest.mark.asyncio
    async def test_chain_stops_on_first_response(self, api_context):
        """Chain should stop on first middleware that returns response."""
        call_order = []

        class FirstMiddleware(Middleware):
            async def process(self, ctx):
                call_order.append("first")
                return None

        class StopMiddleware(Middleware):
            async def process(self, ctx):
                call_order.append("stop")
                return HTTPResponse(401, "application/json", "{}")

        class NeverCalledMiddleware(Middleware):
            async def process(self, ctx):
                call_order.append("never")
                return None

        chain = (
            MiddlewareChain()
            .add(FirstMiddleware())
            .add(StopMiddleware())
            .add(NeverCalledMiddleware())
        )
        result = await chain.process(api_context)

        assert result.status == 401
        assert call_order == ["first", "stop"]


# =============================================================================
# AuthenticationMiddleware Tests
# =============================================================================

class TestAuthenticationMiddleware:
    """Tests for authentication middleware."""

    @pytest.mark.asyncio
    async def test_public_path_no_auth_required(self, http_request):
        """Public paths should not require authentication."""
        request = HTTPRequest(
            method="GET",
            path="/api/v1/health",
            headers={},
            body=b"",
        )
        ctx = APIRequestContext.from_http_request(request)
        mw = AuthenticationMiddleware()

        result = await mw.process(ctx)
        assert result is None
        assert ctx.authenticated is False

    @pytest.mark.asyncio
    async def test_missing_api_key(self, api_context):
        """Missing API key should return 401."""
        mw = AuthenticationMiddleware()
        result = await mw.process(api_context)

        assert result is not None
        assert result.status == 401
        assert "WWW-Authenticate" in result.headers

    @pytest.mark.asyncio
    async def test_valid_bearer_token(self, tmp_path):
        """Valid Bearer token should authenticate."""
        manager = APIKeyManager(keys_dir=tmp_path, use_keyring=False)
        full_key, key = manager.create(
            name="Test Key",
            scopes={APIScope.READ_STATUS},
        )

        request = HTTPRequest(
            method="GET",
            path="/api/v1/status",
            headers={"authorization": f"Bearer {full_key}"},
            body=b"",
        )
        ctx = APIRequestContext.from_http_request(request)
        mw = AuthenticationMiddleware(key_manager=manager)

        result = await mw.process(ctx)
        assert result is None
        assert ctx.authenticated is True
        assert ctx.api_key is not None
        assert APIScope.READ_STATUS in ctx.scopes

    @pytest.mark.asyncio
    async def test_valid_x_api_key_header(self, tmp_path):
        """X-API-Key header should work."""
        manager = APIKeyManager(keys_dir=tmp_path, use_keyring=False)
        full_key, key = manager.create(
            name="Test Key",
            scopes={APIScope.READ_STATUS},
        )

        request = HTTPRequest(
            method="GET",
            path="/api/v1/status",
            headers={"x-api-key": full_key},
            body=b"",
        )
        ctx = APIRequestContext.from_http_request(request)
        mw = AuthenticationMiddleware(key_manager=manager)

        result = await mw.process(ctx)
        assert result is None
        assert ctx.authenticated is True

    @pytest.mark.asyncio
    async def test_valid_query_param(self, tmp_path):
        """api_key query param should work (for WebSocket)."""
        manager = APIKeyManager(keys_dir=tmp_path, use_keyring=False)
        full_key, key = manager.create(
            name="Test Key",
            scopes={APIScope.READ_STATUS},
        )

        request = HTTPRequest(
            method="GET",
            path=f"/api/v1/status?api_key={full_key}",
            headers={},
            body=b"",
        )
        ctx = APIRequestContext.from_http_request(request)
        mw = AuthenticationMiddleware(key_manager=manager)

        result = await mw.process(ctx)
        assert result is None
        assert ctx.authenticated is True

    @pytest.mark.asyncio
    async def test_invalid_api_key(self, tmp_path):
        """Invalid API key should return 401."""
        manager = APIKeyManager(keys_dir=tmp_path, use_keyring=False)

        request = HTTPRequest(
            method="GET",
            path="/api/v1/status",
            headers={"authorization": "Bearer otto_live_invalid1_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"},
            body=b"",
        )
        ctx = APIRequestContext.from_http_request(request)
        mw = AuthenticationMiddleware(key_manager=manager)

        result = await mw.process(ctx)
        assert result is not None
        assert result.status == 401

    @pytest.mark.asyncio
    async def test_revoked_api_key(self, tmp_path):
        """Revoked API key should return 401."""
        manager = APIKeyManager(keys_dir=tmp_path, use_keyring=False)
        full_key, key = manager.create(
            name="Test Key",
            scopes={APIScope.READ_STATUS},
        )
        manager.revoke(key.key_id)

        request = HTTPRequest(
            method="GET",
            path="/api/v1/status",
            headers={"authorization": f"Bearer {full_key}"},
            body=b"",
        )
        ctx = APIRequestContext.from_http_request(request)
        mw = AuthenticationMiddleware(key_manager=manager)

        result = await mw.process(ctx)
        assert result is not None
        assert result.status == 401

    @pytest.mark.asyncio
    async def test_custom_public_paths(self, api_context):
        """Custom public paths should not require auth."""
        mw = AuthenticationMiddleware(
            public_paths={"/api/v1/status", "/custom/public"}
        )
        result = await mw.process(api_context)
        assert result is None


# =============================================================================
# RateLimitMiddleware Tests
# =============================================================================

class TestRateLimitMiddleware:
    """Tests for rate limiting middleware."""

    @pytest.mark.asyncio
    async def test_first_request_passes(self, api_context):
        """First request should always pass."""
        mw = RateLimitMiddleware()
        result = await mw.process(api_context)
        assert result is None
        assert api_context.rate_limit_remaining is not None

    @pytest.mark.asyncio
    async def test_health_endpoint_not_limited(self):
        """Health endpoint should not be rate limited."""
        request = HTTPRequest(
            method="GET",
            path="/api/v1/health",
            headers={},
            body=b"",
        )
        ctx = APIRequestContext.from_http_request(request)
        mw = RateLimitMiddleware()

        result = await mw.process(ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self):
        """Should return 429 when rate limit exceeded."""
        # Create a very low limit
        mw = RateLimitMiddleware(
            endpoint_limits={"/api/v1/test": EndpointRateLimit(1, 1)}
        )

        request = HTTPRequest(
            method="GET",
            path="/api/v1/test",
            headers={},
            body=b"",
        )

        # First request should pass
        ctx1 = APIRequestContext.from_http_request(request)
        ctx1.api_key = MagicMock()
        ctx1.api_key.key_id = "test_key"
        result1 = await mw.process(ctx1)
        assert result1 is None

        # Second request should be rate limited
        ctx2 = APIRequestContext.from_http_request(request)
        ctx2.api_key = MagicMock()
        ctx2.api_key.key_id = "test_key"
        result2 = await mw.process(ctx2)
        assert result2 is not None
        assert result2.status == 429
        assert "Retry-After" in result2.headers

    @pytest.mark.asyncio
    async def test_different_keys_separate_limits(self):
        """Different API keys should have separate limits."""
        mw = RateLimitMiddleware(
            endpoint_limits={"/api/v1/test": EndpointRateLimit(1, 1)}
        )

        request = HTTPRequest(
            method="GET",
            path="/api/v1/test",
            headers={},
            body=b"",
        )

        # Key 1 - first request passes
        ctx1 = APIRequestContext.from_http_request(request)
        ctx1.api_key = MagicMock()
        ctx1.api_key.key_id = "key1"
        result1 = await mw.process(ctx1)
        assert result1 is None

        # Key 2 - first request passes (different limit bucket)
        ctx2 = APIRequestContext.from_http_request(request)
        ctx2.api_key = MagicMock()
        ctx2.api_key.key_id = "key2"
        result2 = await mw.process(ctx2)
        assert result2 is None

    @pytest.mark.asyncio
    async def test_custom_endpoint_limits(self):
        """Custom endpoint limits should be applied."""
        mw = RateLimitMiddleware(
            endpoint_limits={"/api/v1/custom": EndpointRateLimit(1000, 100)}
        )
        limit = mw._get_endpoint_limit("/api/v1/custom")
        assert limit.requests_per_minute == 1000

    @pytest.mark.asyncio
    async def test_default_limit_for_unknown_endpoint(self):
        """Unknown endpoints should use global default."""
        mw = RateLimitMiddleware()
        limit = mw._get_endpoint_limit("/api/v1/unknown")
        assert limit == mw.GLOBAL_DEFAULT


# =============================================================================
# ScopeValidationMiddleware Tests
# =============================================================================

class TestScopeValidationMiddleware:
    """Tests for scope validation middleware."""

    @pytest.mark.asyncio
    async def test_unauthenticated_passes(self, api_context):
        """Unauthenticated requests should pass (auth middleware handles)."""
        api_context.authenticated = False
        mw = ScopeValidationMiddleware()
        result = await mw.process(api_context)
        assert result is None

    @pytest.mark.asyncio
    async def test_sufficient_scope_passes(self, api_context):
        """Request with sufficient scope should pass."""
        api_context.authenticated = True
        api_context.scopes = {APIScope.READ_STATUS}
        mw = ScopeValidationMiddleware()
        result = await mw.process(api_context)
        assert result is None

    @pytest.mark.asyncio
    async def test_insufficient_scope_rejected(self):
        """Request without required scope should be rejected."""
        request = HTTPRequest(
            method="PATCH",
            path="/api/v1/state",
            headers={},
            body=b"",
        )
        ctx = APIRequestContext.from_http_request(request)
        ctx.authenticated = True
        ctx.scopes = {APIScope.READ_STATE}  # Missing WRITE_STATE

        mw = ScopeValidationMiddleware()
        result = await mw.process(ctx)
        assert result is not None
        assert result.status == 403

    @pytest.mark.asyncio
    async def test_admin_scope_grants_all(self):
        """ADMIN scope should grant access to everything."""
        request = HTTPRequest(
            method="PATCH",
            path="/api/v1/state",
            headers={},
            body=b"",
        )
        ctx = APIRequestContext.from_http_request(request)
        ctx.authenticated = True
        ctx.scopes = {APIScope.ADMIN, APIScope.WRITE_STATE}  # ADMIN expanded

        mw = ScopeValidationMiddleware()
        result = await mw.process(ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_unconfigured_endpoint_passes(self):
        """Unconfigured endpoints should pass."""
        request = HTTPRequest(
            method="GET",
            path="/api/v1/unknown",
            headers={},
            body=b"",
        )
        ctx = APIRequestContext.from_http_request(request)
        ctx.authenticated = True
        ctx.scopes = set()

        mw = ScopeValidationMiddleware()
        result = await mw.process(ctx)
        assert result is None


# =============================================================================
# SensitiveDataFilterMiddleware Tests
# =============================================================================

class TestSensitiveDataFilterMiddleware:
    """Tests for sensitive data filtering."""

    @pytest.mark.asyncio
    async def test_non_state_endpoint_not_filtered(self):
        """Non-state endpoints should not be filtered."""
        request = HTTPRequest(
            method="GET",
            path="/api/v1/status",
            headers={},
            body=b"",
        )
        ctx = APIRequestContext.from_http_request(request)
        ctx.response_data = {"burnout_level": "GREEN", "status": "ok"}
        ctx.scopes = {APIScope.READ_STATE}

        mw = SensitiveDataFilterMiddleware()
        result = await mw.process(ctx)
        assert result is None
        assert "burnout_level" in ctx.response_data

    @pytest.mark.asyncio
    async def test_state_endpoint_filtered_without_full(self):
        """State endpoint should filter sensitive fields."""
        request = HTTPRequest(
            method="GET",
            path="/api/v1/state",
            headers={},
            body=b"",
        )
        ctx = APIRequestContext.from_http_request(request)
        ctx.response_data = {
            "burnout_level": "GREEN",
            "energy_level": "high",
            "session_goal": "Test",
        }
        ctx.scopes = {APIScope.READ_STATE}

        mw = SensitiveDataFilterMiddleware()
        result = await mw.process(ctx)
        assert result is None
        assert "burnout_level" not in ctx.response_data
        assert "energy_level" not in ctx.response_data
        assert "session_goal" in ctx.response_data

    @pytest.mark.asyncio
    async def test_state_endpoint_not_filtered_with_full(self):
        """State endpoint should not filter with READ_STATE_FULL."""
        request = HTTPRequest(
            method="GET",
            path="/api/v1/state",
            headers={},
            body=b"",
        )
        ctx = APIRequestContext.from_http_request(request)
        ctx.response_data = {
            "burnout_level": "GREEN",
            "energy_level": "high",
            "session_goal": "Test",
        }
        ctx.scopes = {APIScope.READ_STATE_FULL}

        mw = SensitiveDataFilterMiddleware()
        result = await mw.process(ctx)
        assert result is None
        assert "burnout_level" in ctx.response_data
        assert "energy_level" in ctx.response_data


# =============================================================================
# Integration Tests
# =============================================================================

class TestMiddlewareIntegration:
    """Integration tests for full middleware chain."""

    @pytest.mark.asyncio
    async def test_full_chain_valid_request(self, tmp_path):
        """Valid request should pass through full chain."""
        manager = APIKeyManager(keys_dir=tmp_path, use_keyring=False)
        full_key, key = manager.create(
            name="Test Key",
            scopes={APIScope.READ_STATUS, APIScope.READ_STATE},
        )

        request = HTTPRequest(
            method="GET",
            path="/api/v1/status",
            headers={"authorization": f"Bearer {full_key}"},
            body=b"",
        )
        ctx = APIRequestContext.from_http_request(request)

        chain = create_api_middleware(key_manager=manager)
        result = await chain.process(ctx)

        assert result is None
        assert ctx.authenticated is True
        assert ctx.api_key is not None

    @pytest.mark.asyncio
    async def test_full_chain_unauthorized(self, tmp_path):
        """Unauthorized request should be stopped by auth middleware."""
        manager = APIKeyManager(keys_dir=tmp_path, use_keyring=False)

        request = HTTPRequest(
            method="GET",
            path="/api/v1/status",
            headers={},  # No auth
            body=b"",
        )
        ctx = APIRequestContext.from_http_request(request)

        chain = create_api_middleware(key_manager=manager)
        result = await chain.process(ctx)

        assert result is not None
        assert result.status == 401

    @pytest.mark.asyncio
    async def test_full_chain_forbidden(self, tmp_path):
        """Request with insufficient scope should be stopped."""
        manager = APIKeyManager(keys_dir=tmp_path, use_keyring=False)
        full_key, key = manager.create(
            name="Test Key",
            scopes={APIScope.READ_STATUS},  # No WRITE_STATE
        )

        request = HTTPRequest(
            method="PATCH",
            path="/api/v1/state",
            headers={"authorization": f"Bearer {full_key}"},
            body=b"{}",
        )
        ctx = APIRequestContext.from_http_request(request)

        chain = create_api_middleware(key_manager=manager)
        result = await chain.process(ctx)

        assert result is not None
        assert result.status == 403

    @pytest.mark.asyncio
    async def test_public_endpoint_no_auth(self, tmp_path):
        """Public endpoint should work without auth."""
        manager = APIKeyManager(keys_dir=tmp_path, use_keyring=False)

        request = HTTPRequest(
            method="GET",
            path="/api/v1/health",
            headers={},
            body=b"",
        )
        ctx = APIRequestContext.from_http_request(request)

        chain = create_api_middleware(key_manager=manager)
        result = await chain.process(ctx)

        assert result is None
        assert ctx.authenticated is False


class TestCreateAPIMiddleware:
    """Tests for middleware factory function."""

    def test_creates_chain_with_five_middleware(self):
        """Factory should create chain with 5 middleware (security + auth + rate + scope + validation)."""
        chain = create_api_middleware()
        assert len(chain._middleware) == 5

    def test_custom_public_paths(self):
        """Should pass custom public paths to auth middleware."""
        chain = create_api_middleware(
            public_paths={"/custom/public"}
        )
        # Auth middleware is now at index 1 (after SecurityHeadersMiddleware)
        auth_mw = chain._middleware[1]
        assert "/custom/public" in auth_mw._public_paths

    def test_custom_endpoint_limits(self):
        """Should pass custom limits to rate limit middleware."""
        chain = create_api_middleware(
            endpoint_limits={"/api/v1/custom": EndpointRateLimit(1000, 100)}
        )
        # Rate limit middleware is now at index 2 (after Security and Auth)
        rate_mw = chain._middleware[2]
        assert "/api/v1/custom" in rate_mw._endpoint_limits
