"""
REST Router for OTTO Public REST API
====================================

Maps REST endpoints to JSON-RPC methods.

Route Mappings:
    GET  /api/v1/status            → otto.status
    GET  /api/v1/ping              → otto.ping
    GET  /api/v1/methods           → otto.methods
    GET  /api/v1/state             → otto.state.get
    PATCH /api/v1/state            → otto.state.update
    POST /api/v1/protection/check  → otto.protect.check
    POST /api/v1/sessions          → otto.session.start
    DELETE /api/v1/sessions/current → otto.session.end
    GET  /api/v1/agents            → otto.agent.list
    POST /api/v1/agents            → otto.agent.spawn
    DELETE /api/v1/agents/:id      → otto.agent.abort
    GET  /api/v1/integrations      → otto.integration.list
    POST /api/v1/integrations/sync → otto.integration.sync
    GET  /api/v1/context           → otto.context.get
    GET  /api/v1/health            → (health check)
    GET  /api/v1/openapi.json      → (OpenAPI spec)

Determinism:
- FIXED route mappings
- DETERMINISTIC: path + method → JSON-RPC method
"""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Pattern, Set, Tuple, Union

from ..http_server import HTTPRequest, HTTPResponse
from ..protocol.layer1_jsonrpc import JSONRPCHandler, JSONRPCError

from .middleware import (
    APIRequestContext,
    MiddlewareChain,
    create_api_middleware,
    SensitiveDataFilterMiddleware,
)
from .response import APIResponse, success, internal_error
from .errors import (
    APIException,
    NotFoundError,
    MethodNotAllowedError,
    BadRequestError,
    jsonrpc_error_to_api,
)
from .scopes import APIScope


logger = logging.getLogger(__name__)


# =============================================================================
# Route Definition
# =============================================================================

@dataclass
class Route:
    """
    REST route definition.

    Maps HTTP method + path pattern to JSON-RPC method.
    """
    method: str                   # HTTP method: GET, POST, PATCH, DELETE
    path_pattern: str             # Path with params: /api/v1/agents/:id
    jsonrpc_method: str           # JSON-RPC method: otto.agent.abort
    required_scope: APIScope      # Required permission scope
    rate_limit: int = 30          # Requests per minute

    # Computed
    _regex: Optional[Pattern] = field(default=None, repr=False)
    _param_names: List[str] = field(default_factory=list, repr=False)

    def __post_init__(self):
        """Compile path pattern to regex."""
        pattern = self.path_pattern
        param_names = []

        # Extract parameter names and build regex
        # :id becomes (?P<id>[^/]+)
        param_pattern = re.compile(r":(\w+)")
        for match in param_pattern.finditer(pattern):
            param_names.append(match.group(1))

        regex_pattern = param_pattern.sub(r"(?P<\1>[^/]+)", pattern)
        regex_pattern = f"^{regex_pattern}$"

        self._regex = re.compile(regex_pattern)
        self._param_names = param_names

    def match(self, path: str) -> Optional[Dict[str, str]]:
        """
        Match path against pattern.

        Returns:
            Dict of path parameters if match, None otherwise
        """
        match = self._regex.match(path)
        if match:
            return match.groupdict()
        return None


# =============================================================================
# Route Registry
# =============================================================================

# Standard REST routes mapped to JSON-RPC methods
ROUTES: List[Route] = [
    # Status endpoints
    Route("GET", "/api/v1/status", "otto.status", APIScope.READ_STATUS, 60),
    Route("GET", "/api/v1/ping", "otto.ping", APIScope.READ_STATUS, 120),
    Route("GET", "/api/v1/methods", "otto.methods", APIScope.READ_STATUS, 30),

    # State endpoints
    Route("GET", "/api/v1/state", "otto.state.get", APIScope.READ_STATE, 30),
    Route("PATCH", "/api/v1/state", "otto.state.update", APIScope.WRITE_STATE, 10),

    # Protection
    Route("POST", "/api/v1/protection/check", "otto.protect.check", APIScope.READ_STATE, 30),

    # Sessions
    Route("POST", "/api/v1/sessions", "otto.session.start", APIScope.WRITE_SESSION, 10),
    Route("DELETE", "/api/v1/sessions/current", "otto.session.end", APIScope.WRITE_SESSION, 10),

    # Agents
    Route("GET", "/api/v1/agents", "otto.agent.list", APIScope.READ_AGENTS, 30),
    Route("POST", "/api/v1/agents", "otto.agent.spawn", APIScope.WRITE_AGENTS, 5),
    Route("DELETE", "/api/v1/agents/:id", "otto.agent.abort", APIScope.WRITE_AGENTS, 10),

    # Integrations
    Route("GET", "/api/v1/integrations", "otto.integration.list", APIScope.READ_INTEGRATIONS, 30),
    Route("POST", "/api/v1/integrations/sync", "otto.integration.sync", APIScope.WRITE_SESSION, 5),
    Route("GET", "/api/v1/context", "otto.context.get", APIScope.READ_INTEGRATIONS, 30),
]


# =============================================================================
# REST Router
# =============================================================================

class RESTRouter:
    """
    Routes REST requests to JSON-RPC handlers.

    Handles:
    - Path matching with parameters
    - Method validation
    - Parameter extraction from path, query, body
    - JSON-RPC invocation
    - Response formatting
    """

    API_PREFIX = "/api/v1"

    def __init__(
        self,
        jsonrpc_handler: Optional[JSONRPCHandler] = None,
        routes: Optional[List[Route]] = None,
        middleware: Optional[MiddlewareChain] = None,
    ):
        """
        Initialize REST router.

        Args:
            jsonrpc_handler: JSON-RPC handler for method execution
            routes: Custom route definitions (uses ROUTES if not provided)
            middleware: Middleware chain (creates default if not provided)
        """
        self._jsonrpc_handler = jsonrpc_handler or JSONRPCHandler()
        self._routes = routes or list(ROUTES)
        self._middleware = middleware or create_api_middleware()

        # Build lookup tables
        self._routes_by_path: Dict[str, List[Route]] = {}
        for route in self._routes:
            key = route.path_pattern
            if key not in self._routes_by_path:
                self._routes_by_path[key] = []
            self._routes_by_path[key].append(route)

    def add_route(self, route: Route) -> None:
        """Add a custom route."""
        self._routes.append(route)
        key = route.path_pattern
        if key not in self._routes_by_path:
            self._routes_by_path[key] = []
        self._routes_by_path[key].append(route)

    def _find_route(self, method: str, path: str) -> Tuple[Optional[Route], Dict[str, str]]:
        """
        Find matching route for request.

        Returns:
            Tuple of (route, path_params) or (None, {})
        """
        for route in self._routes:
            params = route.match(path)
            if params is not None:
                if route.method == method:
                    return route, params
        return None, {}

    def _get_allowed_methods(self, path: str) -> List[str]:
        """Get allowed HTTP methods for a path."""
        methods = set()
        for route in self._routes:
            if route.match(path) is not None:
                methods.add(route.method)
        return sorted(methods)

    async def handle_request(self, request: HTTPRequest) -> HTTPResponse:
        """
        Handle an HTTP request.

        Args:
            request: Incoming HTTP request

        Returns:
            HTTP response
        """
        # Create request context
        ctx = APIRequestContext.from_http_request(request)
        response: Optional[HTTPResponse] = None

        try:
            # Handle special endpoints first
            if ctx.path == f"{self.API_PREFIX}/health":
                response = self._handle_health(ctx)

            elif ctx.path == f"{self.API_PREFIX}/openapi.json":
                response = await self._handle_openapi(ctx)

            # Handle OPTIONS for CORS preflight
            elif ctx.method == "OPTIONS":
                response = self._handle_options(ctx)

            else:
                # Run middleware chain
                middleware_response = await self._middleware.process(ctx)
                if middleware_response is not None:
                    # Middleware already wraps its responses
                    return middleware_response

                # Find matching route
                route, path_params = self._find_route(ctx.method, ctx.path)

                if route is None:
                    # Check if path exists with different method
                    allowed = self._get_allowed_methods(ctx.path)
                    if allowed:
                        response = self._method_not_allowed_response(ctx.method, allowed, ctx.request_id)
                    else:
                        response = self._not_found_response(ctx.path, ctx.request_id)
                else:
                    # Execute JSON-RPC method
                    result = await self._execute_route(route, ctx, path_params)

                    # Apply post-processing (sensitive data filter)
                    ctx.response_data = result
                    filter_mw = SensitiveDataFilterMiddleware()
                    await filter_mw.process(ctx)

                    # Format response
                    response = self._success_response(ctx.response_data, ctx)

        except APIException as e:
            response = self._error_response(e, ctx.request_id)

        except Exception as e:
            logger.exception(f"Error handling request: {ctx.path}")
            response = self._error_response(
                APIException(500, "INTERNAL_ERROR", str(e)),
                ctx.request_id,
            )

        # Wrap response with security headers (middleware chain handles this)
        if response is not None:
            response = self._middleware.wrap_response(response, ctx)

        return response

    async def _execute_route(
        self,
        route: Route,
        ctx: APIRequestContext,
        path_params: Dict[str, str],
    ) -> Any:
        """
        Execute JSON-RPC method for route.

        Args:
            route: Matched route
            ctx: Request context
            path_params: Extracted path parameters

        Returns:
            JSON-RPC method result
        """
        # Build params from path, query, and body
        params = {}

        # Add path params (e.g., :id → agent_id)
        if "id" in path_params:
            # Map 'id' to appropriate param name based on route
            if "agent" in route.jsonrpc_method:
                params["agent_id"] = path_params["id"]
            else:
                params["id"] = path_params["id"]

        # Add query params
        params.update(ctx.query_params)

        # Add body params (for POST/PATCH)
        if ctx.body and isinstance(ctx.body, dict):
            params.update(ctx.body)

        # Build JSON-RPC request
        jsonrpc_request = {
            "jsonrpc": "2.0",
            "method": route.jsonrpc_method,
            "params": params,
            "id": ctx.request_id,
        }

        # Execute
        try:
            response = await self._jsonrpc_handler.handle_request(jsonrpc_request)

            if response is None:
                return None

            # Check for error
            if "error" in response and response["error"] is not None:
                error = response["error"]
                raise jsonrpc_error_to_api(
                    error.get("code", -32603),
                    error.get("message", "Unknown error"),
                    error.get("data"),
                )

            return response.get("result")

        except JSONRPCError as e:
            raise jsonrpc_error_to_api(e.code, e.message, e.data)

    def _handle_health(self, ctx: APIRequestContext) -> HTTPResponse:
        """Handle /api/v1/health endpoint."""
        data = {
            "status": "healthy",
            "timestamp": time.time(),
            "version": "v1",
        }
        return self._success_response(data, ctx)

    async def _handle_openapi(self, ctx: APIRequestContext) -> HTTPResponse:
        """Handle /api/v1/openapi.json endpoint."""
        # Import here to avoid circular dependency
        try:
            from .openapi import generate_openapi_spec
            spec = generate_openapi_spec(self._routes)
        except ImportError:
            spec = {"error": "OpenAPI spec not available"}

        # Deterministic: sort_keys=True for deterministic serialization
        return HTTPResponse(
            status=200,
            content_type="application/json",
            body=json.dumps(spec, sort_keys=True, indent=2),
            headers=self._cors_headers(),
        )

    def _handle_options(self, ctx: APIRequestContext) -> HTTPResponse:
        """Handle OPTIONS request for CORS preflight."""
        allowed = self._get_allowed_methods(ctx.path)
        return HTTPResponse(
            status=204,
            content_type="text/plain",
            body="",
            headers={
                **self._cors_headers(),
                "Allow": ", ".join(allowed + ["OPTIONS"]),
            },
        )

    def _success_response(
        self,
        data: Any,
        ctx: APIRequestContext,
    ) -> HTTPResponse:
        """Create success HTTP response."""
        response = success(
            data=data,
            request_id=ctx.request_id,
            rate_limit_remaining=ctx.rate_limit_remaining,
            rate_limit_reset=ctx.rate_limit_reset,
        )
        return HTTPResponse(
            status=200,
            content_type="application/json",
            body=response.to_json(),
            headers=self._cors_headers(),
        )

    def _error_response(
        self,
        error: APIException,
        request_id: str,
    ) -> HTTPResponse:
        """Create error HTTP response."""
        from .response import error as error_response
        response = error_response(
            code=error.error_code,
            message=error.message,
            details=error.details,
            request_id=request_id,
        )
        headers = self._cors_headers()

        # Add specific headers for certain errors
        if error.status_code == 401:
            headers["WWW-Authenticate"] = "Bearer"
        elif error.status_code == 429 and hasattr(error, "retry_after"):
            headers["Retry-After"] = str(int(error.retry_after) + 1)

        return HTTPResponse(
            status=error.status_code,
            content_type="application/json",
            body=response.to_json(),
            headers=headers,
        )

    def _not_found_response(self, path: str, request_id: str) -> HTTPResponse:
        """Create 404 response."""
        return self._error_response(
            NotFoundError(f"Endpoint not found: {path}"),
            request_id,
        )

    def _method_not_allowed_response(
        self,
        method: str,
        allowed: List[str],
        request_id: str,
    ) -> HTTPResponse:
        """Create 405 response."""
        error = MethodNotAllowedError(method, allowed)
        response = self._error_response(error, request_id)
        response.headers["Allow"] = ", ".join(allowed)
        return response

    def _cors_headers(self) -> Dict[str, str]:
        """Get CORS headers for responses."""
        return {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-API-Key",
            "Access-Control-Max-Age": "86400",
        }


# =============================================================================
# Factory Functions
# =============================================================================

def create_rest_router(
    jsonrpc_handler: Optional[JSONRPCHandler] = None,
    custom_routes: Optional[List[Route]] = None,
) -> RESTRouter:
    """
    Create a configured REST router.

    Args:
        jsonrpc_handler: JSON-RPC handler (creates default if not provided)
        custom_routes: Additional custom routes

    Returns:
        Configured RESTRouter
    """
    routes = list(ROUTES)
    if custom_routes:
        routes.extend(custom_routes)

    return RESTRouter(
        jsonrpc_handler=jsonrpc_handler,
        routes=routes,
    )


__all__ = [
    "Route",
    "ROUTES",
    "RESTRouter",
    "create_rest_router",
]
