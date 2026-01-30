"""
API Response Envelope for OTTO Public REST API
===============================================

Provides standardized response format for all API endpoints.

Response Format:
    {
        "success": true,
        "data": { ... },
        "error": null,
        "meta": {
            "timestamp": 1706540400.123,
            "version": "v1",
            "request_id": "req_abc123"
        }
    }

ThinkingMachines [He2025] Compliance:
- FIXED response structure
- DETERMINISTIC: same input → same output format
"""

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


# =============================================================================
# Constants
# =============================================================================

API_VERSION = "v1"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class APIResponseMeta:
    """
    Response metadata.

    Attributes:
        timestamp: Unix timestamp of response
        version: API version string
        request_id: Unique request identifier for tracing
        rate_limit_remaining: Remaining requests in current window
        rate_limit_reset: Timestamp when rate limit resets
    """
    timestamp: float = field(default_factory=time.time)
    version: str = API_VERSION
    request_id: str = field(default_factory=lambda: f"req_{uuid.uuid4().hex[:12]}")
    rate_limit_remaining: Optional[int] = None
    rate_limit_reset: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict, excluding None values."""
        d = {
            "timestamp": self.timestamp,
            "version": self.version,
            "request_id": self.request_id,
        }
        if self.rate_limit_remaining is not None:
            d["rate_limit_remaining"] = self.rate_limit_remaining
        if self.rate_limit_reset is not None:
            d["rate_limit_reset"] = self.rate_limit_reset
        return d


@dataclass
class APIError:
    """
    API error details.

    Attributes:
        code: Machine-readable error code (e.g., "INVALID_PARAMS")
        message: Human-readable error message
        details: Additional error context
    """
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        d = {
            "code": self.code,
            "message": self.message,
        }
        if self.details:
            d["details"] = self.details
        return d


@dataclass
class APIResponse:
    """
    Standardized API response envelope.

    All REST API responses use this format for consistency.
    Either data is set (success) or error is set (failure), never both.

    Example success:
        {
            "success": true,
            "data": {"status": "ok"},
            "error": null,
            "meta": {"timestamp": 1706540400.123, ...}
        }

    Example error:
        {
            "success": false,
            "data": null,
            "error": {"code": "NOT_FOUND", "message": "Resource not found"},
            "meta": {"timestamp": 1706540400.123, ...}
        }
    """
    success: bool
    data: Any = None
    error: Optional[APIError] = None
    meta: APIResponseMeta = field(default_factory=APIResponseMeta)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error.to_dict() if self.error else None,
            "meta": self.meta.to_dict(),
        }

    def to_json(self, indent: Optional[int] = None) -> str:
        """
        Convert to JSON string.

        [He2025] Compliance: sort_keys=True ensures deterministic serialization.
        """
        return json.dumps(self.to_dict(), sort_keys=True, indent=indent)

    @classmethod
    def success_response(
        cls,
        data: Any,
        request_id: Optional[str] = None,
        rate_limit_remaining: Optional[int] = None,
        rate_limit_reset: Optional[float] = None,
    ) -> "APIResponse":
        """
        Create a success response.

        Args:
            data: Response payload
            request_id: Optional custom request ID
            rate_limit_remaining: Remaining rate limit quota
            rate_limit_reset: When rate limit resets

        Returns:
            APIResponse with success=True
        """
        meta = APIResponseMeta(
            rate_limit_remaining=rate_limit_remaining,
            rate_limit_reset=rate_limit_reset,
        )
        if request_id:
            meta.request_id = request_id

        return cls(success=True, data=data, meta=meta)

    @classmethod
    def error_response(
        cls,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> "APIResponse":
        """
        Create an error response.

        Args:
            code: Error code (e.g., "INVALID_PARAMS")
            message: Human-readable error message
            details: Additional error context
            request_id: Optional custom request ID

        Returns:
            APIResponse with success=False
        """
        meta = APIResponseMeta()
        if request_id:
            meta.request_id = request_id

        return cls(
            success=False,
            error=APIError(code=code, message=message, details=details),
            meta=meta,
        )


# =============================================================================
# Convenience Functions
# =============================================================================

def success(
    data: Any,
    request_id: Optional[str] = None,
    rate_limit_remaining: Optional[int] = None,
    rate_limit_reset: Optional[float] = None,
) -> APIResponse:
    """Create a success response."""
    return APIResponse.success_response(
        data=data,
        request_id=request_id,
        rate_limit_remaining=rate_limit_remaining,
        rate_limit_reset=rate_limit_reset,
    )


def error(
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> APIResponse:
    """Create an error response."""
    return APIResponse.error_response(
        code=code,
        message=message,
        details=details,
        request_id=request_id,
    )


# Common error responses
def not_found(
    resource: str = "Resource",
    request_id: Optional[str] = None,
) -> APIResponse:
    """Create a 404 Not Found response."""
    return error(
        code="NOT_FOUND",
        message=f"{resource} not found",
        request_id=request_id,
    )


def unauthorized(
    message: str = "Authentication required",
    request_id: Optional[str] = None,
) -> APIResponse:
    """Create a 401 Unauthorized response."""
    return error(
        code="UNAUTHORIZED",
        message=message,
        request_id=request_id,
    )


def forbidden(
    message: str = "Access denied",
    scope: Optional[str] = None,
    request_id: Optional[str] = None,
) -> APIResponse:
    """Create a 403 Forbidden response."""
    details = {"required_scope": scope} if scope else None
    return error(
        code="FORBIDDEN",
        message=message,
        details=details,
        request_id=request_id,
    )


def rate_limited(
    retry_after: float,
    request_id: Optional[str] = None,
) -> APIResponse:
    """Create a 429 Rate Limited response."""
    return error(
        code="RATE_LIMITED",
        message="Rate limit exceeded",
        details={"retry_after": retry_after},
        request_id=request_id,
    )


def invalid_params(
    message: str,
    field: Optional[str] = None,
    request_id: Optional[str] = None,
) -> APIResponse:
    """Create a 400 Invalid Parameters response."""
    details = {"field": field} if field else None
    return error(
        code="INVALID_PARAMS",
        message=message,
        details=details,
        request_id=request_id,
    )


def internal_error(
    message: str = "Internal server error",
    request_id: Optional[str] = None,
) -> APIResponse:
    """Create a 500 Internal Error response."""
    return error(
        code="INTERNAL_ERROR",
        message=message,
        request_id=request_id,
    )


__all__ = [
    # Version
    "API_VERSION",

    # Data classes
    "APIResponseMeta",
    "APIError",
    "APIResponse",

    # Convenience functions
    "success",
    "error",
    "not_found",
    "unauthorized",
    "forbidden",
    "rate_limited",
    "invalid_params",
    "internal_error",
]
