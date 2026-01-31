"""
OTTO Dashboard Server
=====================

Serves the PWA dashboard and proxies API requests.

Usage:
    python server.py [--port 8080] [--host 0.0.0.0]
"""

import argparse
import asyncio
import json
import logging
import mimetypes
import os
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('otto.dashboard')

# Dashboard directory
DASHBOARD_DIR = Path(__file__).parent


class DashboardServer:
    """
    Simple async HTTP server for the dashboard.

    Serves:
    - Static files (HTML, CSS, JS, images)
    - API endpoints (proxied to OTTO API)
    - Service worker
    - PWA manifest
    """

    def __init__(self, host: str = '0.0.0.0', port: int = 8080):
        self.host = host
        self.port = port
        self._mobile_api = None

    @property
    def mobile_api(self):
        """Lazy load mobile API."""
        if self._mobile_api is None:
            try:
                from otto.api.mobile import get_mobile_api
                self._mobile_api = get_mobile_api()
            except ImportError:
                logger.warning("Mobile API not available")
        return self._mobile_api

    async def handle_request(self, reader, writer):
        """Handle incoming HTTP request."""
        try:
            # Read request line
            request_line = await reader.readline()
            if not request_line:
                return

            request_line = request_line.decode('utf-8').strip()
            method, path, _ = request_line.split(' ', 2)

            # Read headers
            headers = {}
            while True:
                header_line = await reader.readline()
                if header_line == b'\r\n':
                    break
                if b':' in header_line:
                    key, value = header_line.decode('utf-8').strip().split(':', 1)
                    headers[key.lower()] = value.strip()

            # Read body if present
            body = None
            content_length = headers.get('content-length')
            if content_length:
                body = await reader.read(int(content_length))

            # Route request
            if path.startswith('/api/'):
                response = await self.handle_api(method, path, headers, body)
            else:
                response = self.handle_static(method, path)

            # Send response
            writer.write(response)
            await writer.drain()

        except Exception as e:
            logger.exception(f"Request error: {e}")
            error_response = self.error_response(500, str(e))
            writer.write(error_response)
            await writer.drain()

        finally:
            writer.close()
            await writer.wait_closed()

    def handle_static(self, method: str, path: str) -> bytes:
        """Serve static files."""
        if method not in ('GET', 'HEAD'):
            return self.error_response(405, 'Method Not Allowed')

        # Normalize path
        if path == '/':
            path = '/index.html'

        # Security: prevent directory traversal
        if '..' in path:
            return self.error_response(403, 'Forbidden')

        # Resolve file path
        file_path = DASHBOARD_DIR / path.lstrip('/')

        if not file_path.exists():
            # SPA fallback: serve index.html for navigation
            if not path.startswith('/static/') and not path.startswith('/api/'):
                file_path = DASHBOARD_DIR / 'index.html'
            else:
                return self.error_response(404, 'Not Found')

        if file_path.is_dir():
            file_path = file_path / 'index.html'

        if not file_path.exists():
            return self.error_response(404, 'Not Found')

        # Read file
        try:
            content = file_path.read_bytes()
        except Exception as e:
            logger.error(f"Failed to read {file_path}: {e}")
            return self.error_response(500, 'Internal Server Error')

        # Determine content type
        content_type, _ = mimetypes.guess_type(str(file_path))
        if content_type is None:
            content_type = 'application/octet-stream'

        # Build response
        headers = [
            f'Content-Type: {content_type}',
            f'Content-Length: {len(content)}',
            'Cache-Control: public, max-age=3600',
        ]

        # Add service worker scope header
        if path == '/sw.js':
            headers.append('Service-Worker-Allowed: /')

        return self.build_response(200, 'OK', headers, content if method == 'GET' else b'')

    async def handle_api(
        self,
        method: str,
        path: str,
        headers: dict,
        body: Optional[bytes],
    ) -> bytes:
        """Handle API requests."""
        # Parse path
        path_parts = path.split('/')
        if len(path_parts) < 4:
            return self.json_response(404, {'error': 'Not Found'})

        # Parse body
        data = {}
        if body:
            try:
                data = json.loads(body.decode('utf-8'))
            except json.JSONDecodeError:
                pass

        try:
            # Route to appropriate handler
            if '/mobile/' in path:
                result = await self.handle_mobile_api(method, path, data)
            elif '/security/' in path:
                result = await self.handle_security_api(method, path, data)
            elif '/commands/' in path:
                result = await self.handle_command_api(method, path, data)
            else:
                result = {'error': 'Unknown endpoint'}

            return self.json_response(200, result)

        except Exception as e:
            logger.exception(f"API error: {e}")
            return self.json_response(500, {'error': str(e)})

    async def handle_mobile_api(self, method: str, path: str, data: dict) -> dict:
        """Handle mobile API endpoints."""
        if not self.mobile_api:
            return {'error': 'Mobile API not available'}

        if path.endswith('/register'):
            return await self.mobile_api.register_device(
                device_type=data.get('device_type', 'web'),
                device_name=data.get('device_name', 'Browser'),
                os_version=data.get('os_version'),
                app_version=data.get('app_version'),
            )

        elif path.endswith('/verify'):
            return await self.mobile_api.verify_device(
                device_id=data.get('device_id', ''),
                otp=data.get('otp', ''),
                user_id=data.get('user_id', 'anonymous'),
            )

        elif path.endswith('/refresh'):
            return await self.mobile_api.refresh_token(
                refresh_token=data.get('refresh_token', ''),
            )

        elif path.endswith('/sync'):
            device_id = data.get('device_id', 'web')
            return await self.mobile_api.get_sync_state(device_id)

        elif '/push/register' in path:
            return await self.mobile_api.register_push(
                device_id=data.get('device_id', ''),
                push_token=data.get('push_token', ''),
                provider=data.get('provider', 'web'),
            )

        elif '/push/unregister' in path:
            return await self.mobile_api.unregister_push(
                device_id=data.get('device_id', ''),
            )

        return {'error': 'Unknown mobile endpoint'}

    async def handle_security_api(self, method: str, path: str, data: dict) -> dict:
        """Handle security API endpoints."""
        if not self.mobile_api:
            return {'error': 'API not available'}

        if path.endswith('/posture'):
            return await self.mobile_api.get_security_posture()

        elif path.endswith('/crypto'):
            return await self.mobile_api.get_crypto_capabilities()

        return {'error': 'Unknown security endpoint'}

    async def handle_command_api(self, method: str, path: str, data: dict) -> dict:
        """Handle command execution."""
        if not self.mobile_api:
            return {'error': 'API not available'}

        # Extract command from path: /api/v1/commands/health -> health
        path_parts = path.rstrip('/').split('/')
        command = path_parts[-1] if path_parts else ''

        if not command:
            return {'error': 'No command specified'}

        return await self.mobile_api.execute_command(
            command=command,
            args=data,
        )

    def build_response(
        self,
        status: int,
        status_text: str,
        headers: list,
        body: bytes,
    ) -> bytes:
        """Build HTTP response."""
        response = f'HTTP/1.1 {status} {status_text}\r\n'
        for header in headers:
            response += f'{header}\r\n'
        response += '\r\n'
        return response.encode('utf-8') + body

    def error_response(self, status: int, message: str) -> bytes:
        """Build error response."""
        body = f'<html><body><h1>{status} {message}</h1></body></html>'
        body_bytes = body.encode('utf-8')
        headers = [
            'Content-Type: text/html',
            f'Content-Length: {len(body_bytes)}',
        ]
        return self.build_response(status, message, headers, body_bytes)

    def json_response(self, status: int, data: dict) -> bytes:
        """Build JSON response."""
        body = json.dumps(data, sort_keys=True)
        body_bytes = body.encode('utf-8')
        headers = [
            'Content-Type: application/json',
            f'Content-Length: {len(body_bytes)}',
            'Access-Control-Allow-Origin: *',
            'Access-Control-Allow-Methods: GET, POST, OPTIONS',
            'Access-Control-Allow-Headers: Content-Type, Authorization',
        ]
        return self.build_response(status, 'OK', headers, body_bytes)

    async def start(self):
        """Start the server."""
        server = await asyncio.start_server(
            self.handle_request,
            self.host,
            self.port,
        )

        addr = server.sockets[0].getsockname()
        logger.info(f'Dashboard server running on http://{addr[0]}:{addr[1]}')
        logger.info(f'Open in browser: http://localhost:{self.port}')

        async with server:
            await server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description='OTTO Dashboard Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8080, help='Port to listen on')
    args = parser.parse_args()

    server = DashboardServer(host=args.host, port=args.port)

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info('Server stopped')


if __name__ == '__main__':
    main()
