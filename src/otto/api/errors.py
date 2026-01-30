"""
Error Mapping for OTTO Public REST API
======================================

Maps JSON-RPC error codes to HTTP status codes and API error codes.

JSON-RPC Error Codes (standard):
    -32700  PARSE_ERROR       → 400 INVALID_JSON
    -32600  INVALID_REQUEST   → 400 INVALID_REQUEST
    -32601  METHOD_NOT_FOUND  → 404 NOT_FOUND
    -32602  INVALID_PARAMS    → 400 INVALID_PARAMS
    -32603  INTERNAL_ERROR    → 500 INTERNAL_ERROR

Custom OTTO Error Codes:
    -32001  PROTECTION_BLOCKED → 403 PROTECTION_BLOCKED
    -32002  STATE_ERROR        → 400 STATE_ERROR
    -32003  AGENT_ERROR        → 400 AGENT_ERROR
    -32004  INTEGRATION_ERROR  → 400 INTEGRATION_ERROR

REST-only Error Codes:
    N/A     UNAUTHORIZED       → 401 (missing/invalid API key)
    N/A     RATE_LIMITED       → 429 (rate limit exceeded)
    N/A     FORBIDDEN          → 403 (insufficient scope)

ThinkingMachines [He2025] Compliance:
- FIXED error code mappings
- DETERMINISTIC: JSON-RPC code → (HTTP status, API code)
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from ..protocol.layer1_jsonrpc import (
    PARSE_ERROR,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    INVALID_PARAMS,
    INTERNAL_ERROR,
    PROTECTION_BLOCKED,
    STATE_ERROR,
    AGENT_ERROR,
    INTEGRATION_ERROR,
)


# =============================================================================
# API Error Codes (for REST responses)
# =============================================================================

class APIErrorCode:
    """
    API error codes for REST responses.

    These are machine-readable codes returned in the error envelope.
    """
    # From JSON-RPC
    INVALID_JSON = "INVALID_JSON"
    INVALID_REQUEST = "INVALID_REQUEST"
    NOT_FOUND = "NOT_FOUND"
    INVALID_PARAMS = "INVALID_PARAMS"
    INTERNAL_ERROR = "INTERNAL_ERROR"

    # OTTO custom (from JSON-RPC)
    PROTECTION_BLOCKED = "PROTECTION_BLOCKED"
    STATE_ERROR = "STATE_ERROR"
    AGENT_ERROR = "AGENT_ERROR"
    INTEGRATION_ERROR = "INTEGRATION_ERROR"

    # REST-only
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    RATE_LIMITED = "RATE_LIMITED"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"


# =============================================================================
# Error Mapping Table (FIXED)
# =============================================================================

# JSON-RPC error code → (HTTP status, API error code)
JSONRPC_TO_HTTP: Dict[int, Tuple[int, str]] = {
    PARSE_ERROR: (400, APIErrorCode.INVALID_JSON),
    INVALID_REQUEST: (400, APIErrorCode.INVALID_REQUEST),
    METHOD_NOT_FOUND: (404, APIErrorCode.NOT_FOUND),
    INVALID_PARAMS: (400, APIErrorCode.INVALID_PARAMS),
    INTERNAL_ERROR: (500, APIErrorCode.INTERNAL_ERROR),
    PROTECTION_BLOCKED: (403, APIErrorCode.PROTECTION_BLOCKED),
    STATE_ERROR: (400, APIErrorCode.STATE_ERROR),
    AGENT_ERROR: (400, APIErrorCode.AGENT_ERROR),
    INTEGRATION_ERROR: (400, APIErrorCode.INTEGRATION_ERROR),
}


# API error code → default HTTP status
API_CODE_TO_HTTP: Dict[str, int] = {
    APIErrorCode.INVALID_JSON: 400,
    APIErrorCode.INVALID_REQUEST: 400,
    APIErrorCode.NOT_FOUND: 404,
    APIErrorCode.INVALID_PARAMS: 400,
    APIErrorCode.INTERNAL_ERROR: 500,
    APIErrorCode.PROTECTION_BLOCKED: 403,
    APIErrorCode.STATE_ERROR: 400,
    APIErrorCode.AGENT_ERROR: 400,
    APIErrorCode.INTEGRATION_ERROR: 400,
    APIErrorCode.UNAUTHORIZED: 401,
    APIErrorCode.FORBIDDEN: 403,
    APIErrorCode.RATE_LIMITED: 429,
    APIErrorCode.METHOD_NOT_ALLOWED: 405,
}


# =============================================================================
# API Exception Classes
# =============================================================================

class APIException(Exception):
    """
    Base exception for REST API errors.

    Attributes:
        status_code: HTTP status code
        error_code: Machine-readable error code
        message: Human-readable error message
        details: Additional error context
    """

    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.details = details

    def to_dict(self) -> Dict[str, Any]:
        """Convert to error dict for response."""
        d = {
            "code": self.error_code,
            "message": self.message,
        }
        if self.details:
            d["details"] = self.details
        return d


class BadRequestError(APIException):
    """400 Bad Request."""

    def __init__(
        self,
        message: str = "Bad request",
        error_code: str = APIErrorCode.INVALID_REQUEST,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(400, error_code, message, details)


class UnauthorizedError(APIException):
    """401 Unauthorized."""

    def __init__(
        self,
        message: str = "Authentication required",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(401, APIErrorCode.UNAUTHORIZED, message, details)


class ForbiddenError(APIException):
    """403 Forbidden."""

    def __init__(
        self,
        message: str = "Access denied",
        error_code: str = APIErrorCode.FORBIDDEN,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(403, error_code, message, details)


class NotFoundError(APIException):
    """404 Not Found."""

    def __init__(
        self,
        message: str = "Resource not found",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(404, APIErrorCode.NOT_FOUND, message, details)


class MethodNotAllowedError(APIException):
    """405 Method Not Allowed."""

    def __init__(
        self,
        method: str,
        allowed: list[str],
    ):
        super().__init__(
            405,
            APIErrorCode.METHOD_NOT_ALLOWED,
            f"Method {method} not allowed",
            {"allowed_methods": allowed},
        )


class RateLimitedError(APIException):
    """429 Too Many Requests."""

    def __init__(
        self,
        retry_after: float,
        message: str = "Rate limit exceeded",
    ):
        super().__init__(
            429,
            APIErrorCode.RATE_LIMITED,
            message,
            {"retry_after": retry_after},
        )
        self.retry_after = retry_after


class InternalServerError(APIException):
    """500 Internal Server Error."""

    def __init__(
        self,
        message: str = "Internal server error",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(500, APIErrorCode.INTERNAL_ERROR, message, details)


# =============================================================================
# Error Conversion Functions
# =============================================================================

def jsonrpc_error_to_api(
    jsonrpc_code: int,
    message: str,
    data: Any = None,
) -> APIException:
    """
    Convert JSON-RPC error to API exception.

    Args:
        jsonrpc_code: JSON-RPC error code
        message: Error message
        data: Additional error data

    Returns:
        Corresponding APIException
    """
    http_status, api_code = JSONRPC_TO_HTTP.get(
        jsonrpc_code,
        (500, APIErrorCode.INTERNAL_ERROR)
    )

    details = None
    if data:
        details = {"data": data} if not isinstance(data, dict) else data

    return APIException(
        status_code=http_status,
        error_code=api_code,
        message=message,
        details=details,
    )


def api_code_to_http_status(api_code: str) -> int:
    """
    Get HTTP status code for an API error code.

    Args:
        api_code: API error code string

    Returns:
        HTTP status code (defaults to 500 if unknown)
    """
    return API_CODE_TO_HTTP.get(api_code, 500)


@dataclass
class ErrorMapping:
    """
    Complete error mapping entry.

    Attributes:
        jsonrpc_code: JSON-RPC error code (if from JSON-RPC)
        http_status: HTTP status code
        api_code: REST API error code
        default_message: Default error message
    """
    jsonrpc_code: Optional[int]
    http_status: int
    api_code: str
    default_message: str


# Complete error mapping table
ERROR_MAPPINGS = [
    ErrorMapping(PARSE_ERROR, 400, APIErrorCode.INVALID_JSON, "Invalid JSON"),
    ErrorMapping(INVALID_REQUEST, 400, APIErrorCode.INVALID_REQUEST, "Invalid request"),
    ErrorMapping(METHOD_NOT_FOUND, 404, APIErrorCode.NOT_FOUND, "Method not found"),
    ErrorMapping(INVALID_PARAMS, 400, APIErrorCode.INVALID_PARAMS, "Invalid parameters"),
    ErrorMapping(INTERNAL_ERROR, 500, APIErrorCode.INTERNAL_ERROR, "Internal error"),
    ErrorMapping(PROTECTION_BLOCKED, 403, APIErrorCode.PROTECTION_BLOCKED, "Protected by burnout engine"),
    ErrorMapping(STATE_ERROR, 400, APIErrorCode.STATE_ERROR, "State error"),
    ErrorMapping(AGENT_ERROR, 400, APIErrorCode.AGENT_ERROR, "Agent error"),
    ErrorMapping(INTEGRATION_ERROR, 400, APIErrorCode.INTEGRATION_ERROR, "Integration error"),
    ErrorMapping(None, 401, APIErrorCode.UNAUTHORIZED, "Authentication required"),
    ErrorMapping(None, 403, APIErrorCode.FORBIDDEN, "Access denied"),
    ErrorMapping(None, 429, APIErrorCode.RATE_LIMITED, "Rate limit exceeded"),
    ErrorMapping(None, 405, APIErrorCode.METHOD_NOT_ALLOWED, "Method not allowed"),
]


__all__ = [
    # Error codes
    "APIErrorCode",

    # Mappings
    "JSONRPC_TO_HTTP",
    "API_CODE_TO_HTTP",
    "ERROR_MAPPINGS",

    # Exceptions
    "APIException",
    "BadRequestError",
    "UnauthorizedError",
    "ForbiddenError",
    "NotFoundError",
    "MethodNotAllowedError",
    "RateLimitedError",
    "InternalServerError",

    # Functions
    "jsonrpc_error_to_api",
    "api_code_to_http_status",
]
