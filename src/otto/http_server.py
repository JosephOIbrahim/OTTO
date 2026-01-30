"""
HTTP server for Framework Orchestrator operational endpoints.

Provides:
- /health - Full health check with component status
- /ready - Readiness probe for load balancers
- /metrics - Prometheus-compatible metrics export
- /live - Liveness probe (always returns 200 if server is running)

Usage:
    from http_server import start_server, stop_server

    # Start server (non-blocking)
    server = await start_server(port=8080)

    # Start HTTPS server with TLS
    from otto.api.tls import TLSConfig, create_development_tls
    tls_config = create_development_tls()
    server = await start_server(port=8443, tls_config=tls_config)

    # Stop server gracefully
    await stop_server(server)

Or run directly:
    python -m http_server --port 8080
"""

import asyncio
import json
import logging
import ssl
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .api.tls import TLSConfig

logger = logging.getLogger(__name__)


@dataclass
class HTTPRequest:
    """Parsed HTTP request."""
    method: str
    path: str
    headers: Dict[str, str]
    body: bytes


@dataclass
class HTTPResponse:
    """HTTP response to send."""
    status: int
    content_type: str
    body: str
    headers: Dict[str, str] = None

    def __post_init__(self):
        if self.headers is None:
            self.headers = {}

    def to_bytes(self) -> bytes:
        """Convert response to HTTP bytes."""
        status_text = HTTPStatus(self.status).phrase
        headers = {
            'Content-Type': self.content_type,
            'Content-Length': str(len(self.body.encode())),
            **self.headers
        }
        header_lines = '\r\n'.join(f'{k}: {v}' for k, v in headers.items())
        return f'HTTP/1.1 {self.status} {status_text}\r\n{header_lines}\r\n\r\n{self.body}'.encode()


class OperationalHTTPServer:
    """
    Minimal async HTTP server for operational endpoints.

    Does not use external dependencies - pure asyncio for minimal footprint.

    Production Safety [He2025]:
    - Request size limits to prevent DoS
    - Timeout on request reads
    - Content-Length validation
    """

    # Production safety limits [He2025]
    MAX_REQUEST_SIZE = 1_000_000  # 1MB max request body
    MAX_HEADER_SIZE = 8192  # 8KB max headers
    REQUEST_TIMEOUT = 30.0  # 30 seconds timeout

    def __init__(
        self,
        host: str = '0.0.0.0',
        port: int = 8080,
        health_checker: Optional[Any] = None,
        metrics: Optional[Any] = None,
        decision_engine: Optional[Any] = None,
        rest_router: Optional[Any] = None,
        tls_config: Optional["TLSConfig"] = None,
    ):
        """
        Initialize HTTP server.

        Args:
            host: Host to bind to
            port: Port to listen on
            health_checker: HealthChecker instance for /health endpoint
            metrics: OrchestratorMetrics instance for /metrics endpoint
            decision_engine: DecisionEngine instance for /decisions endpoint (v4.3.0)
            rest_router: RESTRouter instance for /api/v1/* endpoints
            tls_config: TLS configuration for HTTPS (optional)
        """
        self.host = host
        self.port = port
        self.health_checker = health_checker
        self.metrics = metrics
        self.decision_engine = decision_engine
        self.rest_router = rest_router
        self.tls_config = tls_config
        self._server: Optional[asyncio.Server] = None
        self._running = False
        self._ssl_context: Optional[ssl.SSLContext] = None
        self._tls_enabled = False

        # Route table
        self._routes: Dict[str, Callable[[HTTPRequest], HTTPResponse]] = {
            '/health': self._handle_health,
            '/ready': self._handle_ready,
            '/live': self._handle_live,
            '/metrics': self._handle_metrics,
            '/decisions': self._handle_decisions,  # v4.3.0
            '/api/state': self._handle_api_state,  # v4.3.0 - Dashboard API
        }

    async def start(self) -> None:
        """Start the HTTP server (HTTP or HTTPS based on TLS config)."""
        # Create SSL context if TLS configured
        if self.tls_config and self.tls_config.is_configured():
            self._ssl_context = self.tls_config.create_ssl_context()
            self._tls_enabled = True
            logger.info(f"TLS enabled with min version: {self.tls_config.min_version.name}")

        self._server = await asyncio.start_server(
            self._handle_connection,
            self.host,
            self.port,
            ssl=self._ssl_context,
        )
        self._running = True
        protocol = "HTTPS" if self._tls_enabled else "HTTP"
        logger.info(f"{protocol} server started on {self.host}:{self.port}")

    async def start_https(self, tls_config: "TLSConfig") -> None:
        """
        Start the server with HTTPS.

        Args:
            tls_config: TLS configuration with certificate

        Raises:
            ValueError: If TLS config is not properly configured
        """
        if not tls_config.is_configured():
            raise ValueError("TLS configuration requires certificate and key files")

        errors = tls_config.validate()
        if errors:
            raise ValueError(f"Invalid TLS configuration: {', '.join(errors)}")

        self.tls_config = tls_config
        await self.start()

    @property
    def is_tls_enabled(self) -> bool:
        """Check if TLS is enabled."""
        return self._tls_enabled

    def get_tls_info(self) -> Optional[Dict[str, Any]]:
        """
        Get TLS configuration information.

        Returns:
            Dict with TLS info or None if TLS not enabled
        """
        if not self._tls_enabled or not self.tls_config:
            return None

        return {
            "enabled": True,
            "min_version": self.tls_config.min_version.name,
            "verify_client": self.tls_config.verify_client,
            "cert_file": str(self.tls_config.cert_file) if self.tls_config.cert_file else None,
        }

    async def stop(self) -> None:
        """Stop the HTTP server gracefully."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._running = False
            logger.info("HTTP server stopped")

    async def serve_forever(self) -> None:
        """Run server until cancelled."""
        if self._server:
            async with self._server:
                await self._server.serve_forever()

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ) -> None:
        """Handle incoming HTTP connection."""
        try:
            # Read request
            request_line = await reader.readline()
            if not request_line:
                return

            # Parse request line
            parts = request_line.decode().strip().split(' ')
            if len(parts) < 2:
                return

            method, path = parts[0], parts[1]

            # Read headers
            headers = {}
            while True:
                line = await reader.readline()
                if line == b'\r\n' or not line:
                    break
                if b':' in line:
                    key, value = line.decode().strip().split(':', 1)
                    headers[key.strip().lower()] = value.strip()

            # Read body if present with size validation [He2025]
            body = b''
            if 'content-length' in headers:
                try:
                    content_length = int(headers['content-length'])
                except ValueError:
                    logger.warning(f"Invalid Content-Length header: {headers['content-length']}")
                    return

                # Validate content length bounds
                if content_length < 0 or content_length > self.MAX_REQUEST_SIZE:
                    logger.warning(f"Content-Length out of bounds: {content_length}")
                    error_response = HTTPResponse(
                        status=413,
                        content_type='application/json',
                        body=json.dumps({'error': 'Request too large', 'max_size': self.MAX_REQUEST_SIZE})
                    )
                    writer.write(error_response.to_bytes())
                    await writer.drain()
                    return

                # Read with timeout
                try:
                    body = await asyncio.wait_for(
                        reader.readexactly(content_length),
                        timeout=self.REQUEST_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    logger.warning("Request body read timed out")
                    return
                except asyncio.IncompleteReadError:
                    logger.warning("Incomplete request body")
                    return

            request = HTTPRequest(
                method=method,
                path=path.split('?')[0],  # Strip query string
                headers=headers,
                body=body
            )

            # Route request (now async to support REST API)
            response = await self._route_request(request)

            # Send response
            writer.write(response.to_bytes())
            await writer.drain()

        except Exception as e:
            logger.error(f"Error handling HTTP request: {e}")
            error_response = HTTPResponse(
                status=500,
                content_type='application/json',
                body=json.dumps({'error': 'Internal server error'})
            )
            writer.write(error_response.to_bytes())
            await writer.drain()

        finally:
            writer.close()
            await writer.wait_closed()

    async def _route_request(self, request: HTTPRequest) -> HTTPResponse:
        """Route request to appropriate handler."""
        # Check for REST API v1 routes first
        if request.path.startswith('/api/v1/') and self.rest_router:
            return await self.rest_router.handle_request(request)

        handler = self._routes.get(request.path)

        if handler:
            return handler(request)

        # 404 for unknown routes
        return HTTPResponse(
            status=404,
            content_type='application/json',
            body=json.dumps({
                'error': 'Not found',
                'path': request.path,
                'available_endpoints': list(self._routes.keys()) + ['/api/v1/*']
            })
        )

    def _handle_health(self, request: HTTPRequest) -> HTTPResponse:
        """
        Handle /health endpoint.

        Returns detailed health status of all components.
        Includes TLS status if HTTPS is enabled.
        """
        if self.health_checker:
            report = self.health_checker.check_health()
            status = 200 if report.is_ready else 503
            health_data = report.to_dict()

            # Add TLS info if enabled
            tls_info = self.get_tls_info()
            if tls_info:
                health_data['tls'] = tls_info

            return HTTPResponse(
                status=status,
                content_type='application/json',
                body=json.dumps(health_data, indent=2)
            )

        # No health checker configured - return basic status
        basic_health = {
            'status': 'healthy',
            'message': 'Health checker not configured'
        }

        # Add TLS info if enabled
        tls_info = self.get_tls_info()
        if tls_info:
            basic_health['tls'] = tls_info

        return HTTPResponse(
            status=200,
            content_type='application/json',
            body=json.dumps(basic_health)
        )

    def _handle_ready(self, request: HTTPRequest) -> HTTPResponse:
        """
        Handle /ready endpoint.

        Kubernetes readiness probe - returns 200 if ready to accept traffic.
        """
        if self.health_checker:
            is_ready = self.health_checker.get_ready_status()
            if is_ready:
                return HTTPResponse(
                    status=200,
                    content_type='text/plain',
                    body='ready'
                )
            return HTTPResponse(
                status=503,
                content_type='text/plain',
                body='not ready'
            )

        return HTTPResponse(
            status=200,
            content_type='text/plain',
            body='ready'
        )

    def _handle_live(self, request: HTTPRequest) -> HTTPResponse:
        """
        Handle /live endpoint.

        Kubernetes liveness probe - if server can respond, it's alive.
        """
        return HTTPResponse(
            status=200,
            content_type='text/plain',
            body='alive'
        )

    def _handle_metrics(self, request: HTTPRequest) -> HTTPResponse:
        """
        Handle /metrics endpoint.

        Returns Prometheus-compatible metrics export.
        """
        if self.metrics:
            prometheus_text = self.metrics.export_prometheus()
            return HTTPResponse(
                status=200,
                content_type='text/plain; version=0.0.4; charset=utf-8',
                body=prometheus_text
            )

        return HTTPResponse(
            status=200,
            content_type='text/plain; version=0.0.4; charset=utf-8',
            body='# No metrics configured\n'
        )

    def _handle_decisions(self, request: HTTPRequest) -> HTTPResponse:
        """
        Handle /decisions endpoint (v4.3.0).

        Returns current decision engine state including:
        - Current mode (work/delegate/protect)
        - Cognitive budget
        - Active agents
        - Queued results
        - Flow protection status
        """
        if self.decision_engine:
            coordinator = self.decision_engine.coordinator
            status = coordinator.get_status()

            # Get recent decisions from history
            recent_decisions = []
            for plan in self.decision_engine.execution_history[-5:]:
                recent_decisions.append({
                    'mode': plan.decision.mode.value,
                    'rationale': plan.decision.rationale,
                    'checksum': plan.checksum,
                    'flow_protected': plan.flow_protection_enabled
                })

            response_data = {
                'version': '4.3.0',
                'status': {
                    'cognitive_budget': status['cognitive_budget'],
                    'can_spawn_agents': status['can_spawn'],
                    'flow_protection_active': status['flow_protection'],
                    'active_agents': status['active_agents'],
                    'queued_results': status['queued_results'],
                    'decisions_made': status['decisions_made']
                },
                'agents': status['agents'],
                'recent_decisions': recent_decisions,
                'routing': {
                    'method': 'table-driven',
                    'deterministic': True,
                    'modes': ['work', 'delegate', 'protect']
                }
            }

            return HTTPResponse(
                status=200,
                content_type='application/json',
                body=json.dumps(response_data, indent=2)
            )

        return HTTPResponse(
            status=200,
            content_type='application/json',
            body=json.dumps({
                'version': '4.3.0',
                'status': 'Decision engine not configured',
                'routing': {
                    'method': 'table-driven',
                    'deterministic': True,
                    'modes': ['work', 'delegate', 'protect']
                }
            })
        )

    def _handle_api_state(self, request: HTTPRequest) -> HTTPResponse:
        """
        Handle /api/state endpoint (v4.3.0).

        Human-friendly dashboard API - returns cognitive state in
        artist-relatable terms, not engineer jargon.

        ThinkingMachines [He2025] compliant:
        - Fixed state mappings (pre-computed)
        - Deterministic response structure
        - No runtime variance
        """
        # CORS headers for dashboard frontend
        cors_headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        }

        # Handle preflight
        if request.method == 'OPTIONS':
            return HTTPResponse(
                status=204,
                content_type='text/plain',
                body='',
                headers=cors_headers
            )

        # Build state response
        state_data = {
            # Burnout: GREEN/YELLOW/ORANGE/RED
            'burnout_level': 'GREEN',
            # Decision mode: work/delegate/protect
            'decision_mode': 'work',
            # Momentum: cold_start/building/rolling/peak/crashed
            'momentum_phase': 'rolling',
            # Energy: high/medium/low/depleted
            'energy_level': 'medium',
            # Working memory slots used (0-3)
            'working_memory_used': 1,
            # Body check needed (after 20 rapid exchanges)
            'body_check_needed': False,
            # Session stats
            'tasks_completed': 0,
            'session_minutes': 0,
        }

        # Get real state from decision engine if available
        if self.decision_engine:
            try:
                coordinator = self.decision_engine.coordinator
                status = coordinator.get_status()
                context = status.get('context', {})

                state_data.update({
                    'burnout_level': context.get('burnout_level', 'GREEN'),
                    'decision_mode': status.get('last_mode', 'work'),
                    'momentum_phase': context.get('momentum_phase', 'rolling'),
                    'energy_level': context.get('energy_level', 'medium'),
                    'working_memory_used': context.get('working_memory_used', 1),
                    'body_check_needed': context.get('body_check_needed', False),
                    'tasks_completed': status.get('decisions_made', 0),
                })
            except Exception as e:
                logger.warning(f"Error fetching decision engine state: {e}")

        # Try to get state from cognitive state file
        state_file = Path.home() / ".orchestra" / "state" / "cognitive_state.json"
        if state_file.exists():
            try:
                with open(state_file) as f:
                    saved_state = json.load(f)
                    state_data.update({
                        'burnout_level': saved_state.get('burnout_level', state_data['burnout_level']),
                        'momentum_phase': saved_state.get('momentum_phase', state_data['momentum_phase']),
                        'energy_level': saved_state.get('energy_level', state_data['energy_level']),
                    })
            except Exception:
                pass  # Use defaults

        return HTTPResponse(
            status=200,
            content_type='application/json',
            body=json.dumps(state_data, indent=2),
            headers=cors_headers
        )

    def add_route(
        self,
        path: str,
        handler: Callable[[HTTPRequest], HTTPResponse]
    ) -> None:
        """Add a custom route handler."""
        self._routes[path] = handler


async def start_server(
    port: int = 8080,
    host: str = '0.0.0.0',
    health_checker: Optional[Any] = None,
    metrics: Optional[Any] = None,
    decision_engine: Optional[Any] = None,
    rest_router: Optional[Any] = None,
    tls_config: Optional["TLSConfig"] = None,
) -> OperationalHTTPServer:
    """
    Start the operational HTTP server.

    Args:
        port: Port to listen on
        host: Host to bind to
        health_checker: Optional HealthChecker instance
        metrics: Optional OrchestratorMetrics instance
        decision_engine: Optional DecisionEngine instance (v4.3.0)
        rest_router: Optional RESTRouter for /api/v1/* endpoints
        tls_config: Optional TLS configuration for HTTPS

    Returns:
        Running OperationalHTTPServer instance
    """
    server = OperationalHTTPServer(
        host=host,
        port=port,
        health_checker=health_checker,
        metrics=metrics,
        decision_engine=decision_engine,
        rest_router=rest_router,
        tls_config=tls_config,
    )
    await server.start()
    return server


async def start_https_server(
    port: int = 8443,
    host: str = '0.0.0.0',
    tls_config: "TLSConfig" = None,
    health_checker: Optional[Any] = None,
    metrics: Optional[Any] = None,
    decision_engine: Optional[Any] = None,
    rest_router: Optional[Any] = None,
) -> OperationalHTTPServer:
    """
    Start the operational HTTPS server.

    Convenience function that ensures TLS is enabled.

    Args:
        port: Port to listen on (default 8443 for HTTPS)
        host: Host to bind to
        tls_config: TLS configuration (required)
        health_checker: Optional HealthChecker instance
        metrics: Optional OrchestratorMetrics instance
        decision_engine: Optional DecisionEngine instance
        rest_router: Optional RESTRouter for /api/v1/* endpoints

    Returns:
        Running OperationalHTTPServer instance with TLS

    Raises:
        ValueError: If tls_config is not provided or invalid
    """
    if tls_config is None:
        raise ValueError("tls_config is required for HTTPS server")

    return await start_server(
        port=port,
        host=host,
        health_checker=health_checker,
        metrics=metrics,
        decision_engine=decision_engine,
        rest_router=rest_router,
        tls_config=tls_config,
    )


async def stop_server(server: OperationalHTTPServer) -> None:
    """Stop the HTTP server gracefully."""
    await server.stop()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Framework Orchestrator HTTP Server')
    parser.add_argument('--port', type=int, default=8080, help='Port to listen on')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to bind to')
    args = parser.parse_args()

    async def main():
        server = await start_server(port=args.port, host=args.host)
        print(f"Server running on http://{args.host}:{args.port}")
        print("Endpoints: /health, /ready, /live, /metrics")
        print("Press Ctrl+C to stop")
        try:
            await server.serve_forever()
        except KeyboardInterrupt:
            await stop_server(server)

    asyncio.run(main())
