"""
Tests for SecurityHeadersMiddleware

Tests security header injection into all API responses.

Determinism: Verifies FIXED headers, no runtime variation.
"""

import pytest
import asyncio
from typing import Dict, Set

from otto.api import (
    SecurityHeadersMiddleware,
    APIRequestContext,
    MiddlewareChain,
    AuthenticationMiddleware,
    RateLimitMiddleware,
    ScopeValidationMiddleware,
    create_api_middleware,
    APIKeyManager,
    APIScope,
)
from otto.http_server import HTTPRequest, HTTPResponse


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_request() -> HTTPRequest:
    """Create a mock HTTP request."""
    return HTTPRequest(
        method="GET",
        path="/api/v1/status",
        headers={"content-type": "application/json"},
        body=b"",
    )


@pytest.fixture
def mock_response() -> HTTPResponse:
    """Create a mock HTTP response."""
    return HTTPResponse(
        status=200,
        content_type="application/json",
        body='{"success": true}',
        headers={},
    )


@pytest.fixture
def request_context(mock_request: HTTPRequest) -> APIRequestContext:
    """Create request context from mock request."""
    return APIRequestContext.from_http_request(mock_request)


@pytest.fixture
def security_middleware() -> SecurityHeadersMiddleware:
    """Create security headers middleware."""
    return SecurityHeadersMiddleware()


@pytest.fixture
def key_manager(tmp_path) -> APIKeyManager:
    """Create an API key manager with a test key."""
    manager = APIKeyManager(keys_dir=tmp_path, use_keyring=False)
    return manager


# =============================================================================
# Test: Header Values (FIXED)
# =============================================================================

class TestSecurityHeaderValues:
    """Test that security headers have correct fixed values."""

    def test_headers_are_fixed(self):
        """Security headers must be FIXED (no runtime variation)."""
        expected = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": "default-src 'none'",
        }

        assert SecurityHeadersMiddleware.HEADERS == expected

    def test_header_count(self):
        """Verify expected number of security headers."""
        assert len(SecurityHeadersMiddleware.HEADERS) == 5

    def test_x_content_type_options(self):
        """X-Content-Type-Options prevents MIME type sniffing."""
        assert SecurityHeadersMiddleware.HEADERS["X-Content-Type-Options"] == "nosniff"

    def test_x_frame_options(self):
        """X-Frame-Options prevents clickjacking."""
        assert SecurityHeadersMiddleware.HEADERS["X-Frame-Options"] == "DENY"

    def test_x_xss_protection(self):
        """X-XSS-Protection enables legacy XSS filter."""
        assert SecurityHeadersMiddleware.HEADERS["X-XSS-Protection"] == "1; mode=block"

    def test_referrer_policy(self):
        """Referrer-Policy controls referrer header behavior."""
        expected = "strict-origin-when-cross-origin"
        assert SecurityHeadersMiddleware.HEADERS["Referrer-Policy"] == expected

    def test_content_security_policy(self):
        """Content-Security-Policy restricts resource loading."""
        assert SecurityHeadersMiddleware.HEADERS["Content-Security-Policy"] == "default-src 'none'"


# =============================================================================
# Test: add_headers() Class Method
# =============================================================================

class TestAddHeadersMethod:
    """Test the add_headers() class method."""

    def test_adds_all_security_headers(self, mock_response: HTTPResponse):
        """All security headers should be added to response."""
        result = SecurityHeadersMiddleware.add_headers(mock_response)

        for header, value in SecurityHeadersMiddleware.HEADERS.items():
            assert header in result.headers
            assert result.headers[header] == value

    def test_adds_request_id(self, mock_response: HTTPResponse):
        """Request ID should be added when provided."""
        request_id = "req_test123456"
        result = SecurityHeadersMiddleware.add_headers(mock_response, request_id)

        assert "X-Request-Id" in result.headers
        assert result.headers["X-Request-Id"] == request_id

    def test_no_request_id_when_empty(self, mock_response: HTTPResponse):
        """Request ID should not be added when empty."""
        result = SecurityHeadersMiddleware.add_headers(mock_response, "")

        assert "X-Request-Id" not in result.headers

    def test_preserves_existing_headers(self, mock_response: HTTPResponse):
        """Existing headers should be preserved."""
        mock_response.headers["Custom-Header"] = "custom-value"

        result = SecurityHeadersMiddleware.add_headers(mock_response)

        assert result.headers["Custom-Header"] == "custom-value"

    def test_does_not_override_existing_security_headers(self):
        """Should not override security headers already set."""
        response = HTTPResponse(
            status=200,
            content_type="application/json",
            body="{}",
            headers={"X-Frame-Options": "SAMEORIGIN"},  # Custom value
        )

        result = SecurityHeadersMiddleware.add_headers(response)

        # Should keep existing value, not override
        assert result.headers["X-Frame-Options"] == "SAMEORIGIN"

    def test_returns_same_response_object(self, mock_response: HTTPResponse):
        """Should modify and return the same response object."""
        result = SecurityHeadersMiddleware.add_headers(mock_response)

        assert result is mock_response

    def test_does_not_override_existing_request_id(self, mock_response: HTTPResponse):
        """Should not override X-Request-Id if already set."""
        mock_response.headers["X-Request-Id"] = "existing_id"

        result = SecurityHeadersMiddleware.add_headers(mock_response, "new_id")

        assert result.headers["X-Request-Id"] == "existing_id"


# =============================================================================
# Test: Middleware process() Method
# =============================================================================

class TestMiddlewareProcess:
    """Test the process() method behavior."""

    @pytest.mark.asyncio
    async def test_process_returns_none(
        self,
        security_middleware: SecurityHeadersMiddleware,
        request_context: APIRequestContext,
    ):
        """process() should always return None to continue chain."""
        result = await security_middleware.process(request_context)

        assert result is None

    @pytest.mark.asyncio
    async def test_process_does_not_modify_context(
        self,
        security_middleware: SecurityHeadersMiddleware,
        request_context: APIRequestContext,
    ):
        """process() should not modify the request context."""
        original_path = request_context.path
        original_method = request_context.method

        await security_middleware.process(request_context)

        assert request_context.path == original_path
        assert request_context.method == original_method


# =============================================================================
# Test: wrap_response() Method
# =============================================================================

class TestWrapResponse:
    """Test the wrap_response() method."""

    def test_wrap_response_adds_headers(
        self,
        security_middleware: SecurityHeadersMiddleware,
        mock_response: HTTPResponse,
        request_context: APIRequestContext,
    ):
        """wrap_response() should add all security headers."""
        result = security_middleware.wrap_response(mock_response, request_context)

        for header in SecurityHeadersMiddleware.HEADERS:
            assert header in result.headers

    def test_wrap_response_adds_request_id_from_context(
        self,
        security_middleware: SecurityHeadersMiddleware,
        mock_response: HTTPResponse,
        request_context: APIRequestContext,
    ):
        """wrap_response() should add X-Request-Id from context."""
        result = security_middleware.wrap_response(mock_response, request_context)

        assert "X-Request-Id" in result.headers
        assert result.headers["X-Request-Id"] == request_context.request_id


# =============================================================================
# Test: MiddlewareChain Integration
# =============================================================================

class TestMiddlewareChainIntegration:
    """Test SecurityHeadersMiddleware integration with MiddlewareChain."""

    def test_chain_tracks_response_wrappers(self, security_middleware: SecurityHeadersMiddleware):
        """MiddlewareChain should track middleware with wrap_response()."""
        chain = MiddlewareChain()
        chain.add(security_middleware)

        assert security_middleware in chain._response_wrappers

    def test_chain_wrap_response_applies_security_headers(
        self,
        security_middleware: SecurityHeadersMiddleware,
        mock_response: HTTPResponse,
        request_context: APIRequestContext,
    ):
        """Chain's wrap_response() should apply security headers."""
        chain = MiddlewareChain()
        chain.add(security_middleware)

        result = chain.wrap_response(mock_response, request_context)

        for header in SecurityHeadersMiddleware.HEADERS:
            assert header in result.headers

    @pytest.mark.asyncio
    async def test_chain_wraps_middleware_responses(
        self,
        key_manager: APIKeyManager,
    ):
        """Middleware-generated responses should have security headers."""
        # Create chain with security headers and auth (will reject without key)
        chain = create_api_middleware(key_manager=key_manager)

        # Create request without API key (will be rejected by auth)
        request = HTTPRequest(
            method="GET",
            path="/api/v1/status",  # Not a public path
            headers={},
            body=b"",
        )
        ctx = APIRequestContext.from_http_request(request)

        # Process will return 401 response
        response = await chain.process(ctx)

        # Should have security headers on the 401 response
        assert response is not None
        assert response.status == 401
        for header in SecurityHeadersMiddleware.HEADERS:
            assert header in response.headers, f"Missing header: {header}"


# =============================================================================
# Test: create_api_middleware() Factory
# =============================================================================

class TestCreateApiMiddleware:
    """Test the middleware factory function."""

    def test_includes_security_headers_by_default(self, key_manager: APIKeyManager):
        """Security headers middleware should be included by default."""
        chain = create_api_middleware(key_manager=key_manager)

        # Check that SecurityHeadersMiddleware is in the chain
        has_security_middleware = any(
            isinstance(mw, SecurityHeadersMiddleware)
            for mw in chain._middleware
        )
        assert has_security_middleware

    def test_can_disable_security_headers(self, key_manager: APIKeyManager):
        """Security headers can be disabled via parameter."""
        chain = create_api_middleware(
            key_manager=key_manager,
            include_security_headers=False,
        )

        # Check that SecurityHeadersMiddleware is NOT in the chain
        has_security_middleware = any(
            isinstance(mw, SecurityHeadersMiddleware)
            for mw in chain._middleware
        )
        assert not has_security_middleware

    def test_security_middleware_is_first(self, key_manager: APIKeyManager):
        """Security headers middleware should be first in chain."""
        chain = create_api_middleware(key_manager=key_manager)

        # First middleware should be SecurityHeadersMiddleware
        assert isinstance(chain._middleware[0], SecurityHeadersMiddleware)


# =============================================================================
# Test: Determinism
# =============================================================================

class TestDeterminism:
    """Test Determinism."""

    def test_headers_are_deterministic(self):
        """Headers should be identical across multiple instantiations."""
        mw1 = SecurityHeadersMiddleware()
        mw2 = SecurityHeadersMiddleware()

        assert mw1.HEADERS == mw2.HEADERS

    def test_add_headers_is_deterministic(self, mock_response: HTTPResponse):
        """add_headers() should produce identical results."""
        # Create two copies of the same response
        response1 = HTTPResponse(
            status=200,
            content_type="application/json",
            body="{}",
            headers={},
        )
        response2 = HTTPResponse(
            status=200,
            content_type="application/json",
            body="{}",
            headers={},
        )

        SecurityHeadersMiddleware.add_headers(response1, "req_123")
        SecurityHeadersMiddleware.add_headers(response2, "req_123")

        # Headers should be identical
        assert response1.headers == response2.headers

    @pytest.mark.asyncio
    async def test_process_is_deterministic(self, request_context: APIRequestContext):
        """process() should return identical results."""
        mw1 = SecurityHeadersMiddleware()
        mw2 = SecurityHeadersMiddleware()

        result1 = await mw1.process(request_context)
        result2 = await mw2.process(request_context)

        assert result1 == result2 == None


# =============================================================================
# Test: Response Status Codes
# =============================================================================

class TestResponseStatusCodes:
    """Test security headers are added for all response status codes."""

    @pytest.mark.parametrize("status_code", [
        200,  # OK
        201,  # Created
        204,  # No Content
        400,  # Bad Request
        401,  # Unauthorized
        403,  # Forbidden
        404,  # Not Found
        405,  # Method Not Allowed
        429,  # Too Many Requests
        500,  # Internal Server Error
    ])
    def test_headers_added_for_status_code(self, status_code: int):
        """Security headers should be added regardless of status code."""
        response = HTTPResponse(
            status=status_code,
            content_type="application/json",
            body="{}",
            headers={},
        )

        result = SecurityHeadersMiddleware.add_headers(response, "req_test")

        for header in SecurityHeadersMiddleware.HEADERS:
            assert header in result.headers, f"Missing {header} for status {status_code}"


# =============================================================================
# Test: Content Types
# =============================================================================

class TestContentTypes:
    """Test security headers work with different content types."""

    @pytest.mark.parametrize("content_type", [
        "application/json",
        "text/plain",
        "text/html",
        "application/xml",
    ])
    def test_headers_added_for_content_type(self, content_type: str):
        """Security headers should be added regardless of content type."""
        response = HTTPResponse(
            status=200,
            content_type=content_type,
            body="test",
            headers={},
        )

        result = SecurityHeadersMiddleware.add_headers(response)

        for header in SecurityHeadersMiddleware.HEADERS:
            assert header in result.headers


# =============================================================================
# Test: Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_response_body(self):
        """Should work with empty response body."""
        response = HTTPResponse(
            status=204,
            content_type="",
            body="",
            headers={},
        )

        result = SecurityHeadersMiddleware.add_headers(response)

        assert len(result.headers) >= len(SecurityHeadersMiddleware.HEADERS)

    def test_none_headers_dict(self):
        """Should handle response with None-like headers gracefully."""
        response = HTTPResponse(
            status=200,
            content_type="application/json",
            body="{}",
            headers={},  # Empty dict, not None
        )

        # Should not raise
        result = SecurityHeadersMiddleware.add_headers(response)
        assert result is not None

    def test_special_characters_in_request_id(self):
        """Should handle special characters in request ID."""
        response = HTTPResponse(
            status=200,
            content_type="application/json",
            body="{}",
            headers={},
        )

        # Request ID with various characters
        request_id = "req_abc-123_xyz"
        result = SecurityHeadersMiddleware.add_headers(response, request_id)

        assert result.headers["X-Request-Id"] == request_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
