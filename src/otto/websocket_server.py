"""
WebSocket server for real-time dashboard state updates.

Provides:
- /ws/state - Real-time cognitive state broadcast
- Heartbeat/keepalive for connection monitoring
- Graceful reconnection support

ThinkingMachines [He2025] compliant:
- Deterministic state serialization
- Fixed update intervals
- Pre-computed state mappings

Usage:
    from websocket_server import WebSocketServer

    server = WebSocketServer(port=8081)
    await server.start()
"""

import asyncio
import json
import hashlib
import struct
import base64
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Set, Optional, Dict, Any, List

logger = logging.getLogger(__name__)


@dataclass
class CognitiveState:
    """
    Current cognitive state for dashboard display.

    ThinkingMachines [He2025]: Fixed structure, deterministic serialization.
    Full Orchestra substrate controls - 5-Phase NEXUS Pipeline.

    Phases:
    1. DETECT  - PRISM signal extraction
    2. CASCADE - Constitutional/safety gates + Cognitive Safety MoE expert routing
    3. LOCK    - Parameter locking with MAX3 bounds
    4. EXECUTE - Work/delegate/protect execution
    5. UPDATE  - RC^+xi convergence tracking
    """
    # === EXISTING FIELDS ===
    burnout_level: str = "GREEN"
    decision_mode: str = "work"
    momentum_phase: str = "rolling"
    energy_level: str = "high"
    working_memory_used: int = 2
    tangent_budget: int = 5
    altitude: str = "30000ft"
    paradigm: str = "Cortex"
    body_check_needed: bool = False
    current_task: Optional[str] = None
    tasks_completed: int = 0
    session_minutes: int = 0

    # === PHASE 1: DETECT - PRISM Signals ===
    signals_emotional: Optional[str] = None  # 'frustrated', 'overwhelmed', 'stuck'
    signals_mode: Optional[str] = None  # 'exploring', 'focused', 'teaching'
    signals_domain: Optional[List[str]] = None  # ['usd', 'houdini'], ['react', 'next']
    signals_task: Optional[str] = None  # 'implement', 'debug', 'plan', 'vision'
    current_phase: str = "detect"  # detect|cascade|lock|execute|update

    # === PHASE 2: CASCADE - Expert Routing ===
    constitutional_pass: bool = True
    safety_gate_pass: bool = True
    safety_redirect: Optional[str] = None  # 'validator', 'scaffolder', 'restorer'
    selected_expert: str = "direct"  # validator|scaffolder|restorer|refocuser|celebrator|socratic|direct
    expert_trigger: Optional[str] = None  # The signal that triggered expert selection

    # === PHASE 3: LOCK - Parameter Locking ===
    lock_status: str = "unlocked"  # unlocked|locking|locked
    reflection_iteration: int = 0  # MAX3: 0-3
    locked_expert: str = "direct"
    locked_paradigm: str = "Cortex"
    locked_altitude: str = "30000ft"
    locked_think_depth: str = "standard"  # minimal|standard|deep|ultradeep
    lock_checksum: Optional[str] = None  # 6-char deterministic checksum

    # === PHASE 5: UPDATE - RC^+xi Convergence ===
    epistemic_tension: float = 0.0  # xi_n: 0.0 - 1.0
    epsilon: float = 0.1  # Convergence threshold
    attractor_basin: str = "focused"  # focused|exploring|recovery|teaching
    stable_exchanges: int = 0  # 0-3 (converged at 3)
    converged: bool = False
    feedback_active: bool = True  # Loop indicator

    # Valid values for validation
    VALID_VALUES: Dict[str, list] = None

    def __post_init__(self):
        # Define valid values for each field
        self.VALID_VALUES = {
            'burnout_level': ['GREEN', 'YELLOW', 'ORANGE', 'RED'],
            'decision_mode': ['work', 'delegate', 'protect'],
            'momentum_phase': ['cold_start', 'building', 'rolling', 'peak', 'crashed'],
            'energy_level': ['high', 'medium', 'low', 'depleted'],
            'altitude': ['30000ft', '15000ft', '5000ft', 'Ground'],
            'paradigm': ['Cortex', 'Mycelium'],
            'current_phase': ['detect', 'cascade', 'lock', 'execute', 'update'],
            'selected_expert': ['validator', 'scaffolder', 'restorer', 'refocuser', 'celebrator', 'socratic', 'direct'],
            'lock_status': ['unlocked', 'locking', 'locked'],
            'locked_think_depth': ['minimal', 'standard', 'deep', 'ultradeep'],
            'attractor_basin': ['focused', 'exploring', 'recovery', 'teaching']
        }

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop('VALID_VALUES', None)  # Don't serialize validation rules
        return d

    def checksum(self) -> str:
        """Deterministic checksum for state verification."""
        data = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.md5(data.encode()).hexdigest()[:8]

    def validate_field(self, field: str, value: Any) -> bool:
        """Validate a field value against allowed values."""
        if field in self.VALID_VALUES:
            return value in self.VALID_VALUES[field]
        return hasattr(self, field)


class WebSocketServer:
    """
    Minimal WebSocket server for dashboard real-time updates.

    Implements RFC 6455 WebSocket protocol (basic handshake + text frames).
    No external dependencies - pure asyncio.
    """

    GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8081,
        update_interval: float = 1.0
    ):
        self.host = host
        self.port = port
        self.update_interval = update_interval
        self._server: Optional[asyncio.Server] = None
        self._clients: Set[asyncio.StreamWriter] = set()
        self._running = False
        self._state = CognitiveState()
        self._broadcast_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the WebSocket server."""
        self._server = await asyncio.start_server(
            self._handle_connection,
            self.host,
            self.port
        )
        self._running = True
        self._broadcast_task = asyncio.create_task(self._broadcast_loop())
        logger.info(f"WebSocket server started on ws://{self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop the WebSocket server gracefully."""
        self._running = False
        if self._broadcast_task:
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass

        # Close all client connections
        for writer in list(self._clients):
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
        self._clients.clear()

        if self._server:
            self._server.close()
            await self._server.wait_closed()
        logger.info("WebSocket server stopped")

    async def serve_forever(self) -> None:
        """Run server until cancelled."""
        if self._server:
            async with self._server:
                await self._server.serve_forever()

    def update_state(self, **kwargs) -> None:
        """
        Update cognitive state.

        Args:
            **kwargs: State fields to update
        """
        for key, value in kwargs.items():
            if hasattr(self._state, key):
                setattr(self._state, key, value)

    def get_state(self) -> CognitiveState:
        """Get current cognitive state."""
        return self._state

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ) -> None:
        """Handle incoming WebSocket connection."""
        try:
            # Read HTTP upgrade request
            request_line = await reader.readline()
            if not request_line:
                return

            # Parse request
            parts = request_line.decode().strip().split(' ')
            if len(parts) < 2:
                return

            path = parts[1]

            # Read headers
            headers = {}
            while True:
                line = await reader.readline()
                if line == b'\r\n' or not line:
                    break
                if b':' in line:
                    key, value = line.decode().strip().split(':', 1)
                    headers[key.strip().lower()] = value.strip()

            # Verify WebSocket upgrade request
            if headers.get('upgrade', '').lower() != 'websocket':
                writer.write(b'HTTP/1.1 400 Bad Request\r\n\r\n')
                await writer.drain()
                return

            # Get WebSocket key
            ws_key = headers.get('sec-websocket-key', '')
            if not ws_key:
                writer.write(b'HTTP/1.1 400 Bad Request\r\n\r\n')
                await writer.drain()
                return

            # Calculate accept key
            accept_key = self._calculate_accept_key(ws_key)

            # Send upgrade response
            response = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept_key}\r\n"
                "\r\n"
            )
            writer.write(response.encode())
            await writer.drain()

            # Add to clients
            self._clients.add(writer)
            logger.info(f"WebSocket client connected: {path}")

            # Send initial state
            await self._send_state(writer)

            # Keep connection alive, handle incoming frames
            while self._running:
                try:
                    # Read frame with timeout
                    data = await asyncio.wait_for(reader.read(2), timeout=30.0)
                    if not data:
                        break

                    # Parse frame header
                    opcode = data[0] & 0x0f
                    masked = (data[1] & 0x80) != 0
                    payload_len = data[1] & 0x7f

                    # Handle extended payload length
                    if payload_len == 126:
                        ext = await reader.read(2)
                        payload_len = struct.unpack('>H', ext)[0]
                    elif payload_len == 127:
                        ext = await reader.read(8)
                        payload_len = struct.unpack('>Q', ext)[0]

                    # Read mask key if present
                    mask_key = None
                    if masked:
                        mask_key = await reader.read(4)

                    # Read payload
                    payload = b''
                    if payload_len > 0:
                        payload = await reader.read(payload_len)
                        if masked and mask_key:
                            payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

                    if opcode == 0x8:  # Close frame
                        break
                    elif opcode == 0x9:  # Ping
                        await self._send_frame(writer, 0x0a, b'')
                    elif opcode == 0x0a:  # Pong
                        pass
                    elif opcode == 0x1:  # Text frame - handle commands
                        await self._handle_command(payload.decode('utf-8'), writer)

                except asyncio.TimeoutError:
                    # Send ping to keep alive
                    try:
                        await self._send_frame(writer, 0x9, b'')
                    except Exception:
                        break
                except Exception as e:
                    logger.error(f"Frame handling error: {e}")
                    break

        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            self._clients.discard(writer)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            logger.info("WebSocket client disconnected")

    def _calculate_accept_key(self, key: str) -> str:
        """Calculate WebSocket accept key per RFC 6455."""
        import hashlib
        combined = key + self.GUID
        sha1 = hashlib.sha1(combined.encode()).digest()
        return base64.b64encode(sha1).decode()

    async def _send_frame(self, writer: asyncio.StreamWriter, opcode: int, data: bytes) -> None:
        """Send WebSocket frame."""
        length = len(data)

        # Build frame header
        frame = bytes([0x80 | opcode])  # FIN + opcode

        if length < 126:
            frame += bytes([length])
        elif length < 65536:
            frame += bytes([126]) + struct.pack('>H', length)
        else:
            frame += bytes([127]) + struct.pack('>Q', length)

        frame += data
        writer.write(frame)
        await writer.drain()

    async def _send_state(self, writer: asyncio.StreamWriter) -> None:
        """Send current state to a client."""
        try:
            data = json.dumps(self._state.to_dict(), sort_keys=True).encode()
            await self._send_frame(writer, 0x1, data)  # Text frame
        except Exception as e:
            logger.error(f"Error sending state: {e}")
            self._clients.discard(writer)

    async def _handle_command(self, message: str, writer: asyncio.StreamWriter) -> None:
        """
        Handle incoming command from dashboard.

        Command format:
        {
            "type": "override",
            "field": "decision_mode",
            "value": "protect"
        }
        """
        try:
            cmd = json.loads(message)
            cmd_type = cmd.get('type')

            if cmd_type == 'override':
                field = cmd.get('field')
                value = cmd.get('value')

                if field and value and self._state.validate_field(field, value):
                    setattr(self._state, field, value)
                    self._save_state_to_file()
                    logger.info(f"Override applied: {field} = {value}")

                    # Broadcast updated state to all clients immediately
                    for client in list(self._clients):
                        await self._send_state(client)
                else:
                    logger.warning(f"Invalid override: {field} = {value}")

        except json.JSONDecodeError:
            logger.warning(f"Invalid command JSON: {message}")
        except Exception as e:
            logger.error(f"Command handling error: {e}")

    # Shared state location (must match CognitiveStateManager)
    STATE_DIR = Path.home() / ".orchestra" / "state"
    STATE_FILE = STATE_DIR / "cognitive_state.json"

    def _save_state_to_file(self) -> None:
        """Save cognitive state to file for persistence."""
        self.STATE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.STATE_FILE, 'w') as f:
                json.dump(self._state.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Error saving state: {e}")

    async def _broadcast_loop(self) -> None:
        """Broadcast state updates to all connected clients."""
        while self._running:
            await asyncio.sleep(self.update_interval)

            # Load state from file if available
            self._load_state_from_file()

            # Broadcast to all clients
            for writer in list(self._clients):
                await self._send_state(writer)

    def _load_state_from_file(self) -> None:
        """Load cognitive state from file."""
        if self.STATE_FILE.exists():
            try:
                with open(self.STATE_FILE) as f:
                    data = json.load(f)
                    # === EXISTING FIELDS ===
                    self._state.burnout_level = data.get('burnout_level', self._state.burnout_level)
                    self._state.decision_mode = data.get('decision_mode', self._state.decision_mode)
                    self._state.momentum_phase = data.get('momentum_phase', self._state.momentum_phase)
                    self._state.energy_level = data.get('energy_level', self._state.energy_level)
                    self._state.working_memory_used = data.get('working_memory_used', self._state.working_memory_used)
                    self._state.tangent_budget = data.get('tangent_budget', self._state.tangent_budget)
                    self._state.altitude = data.get('altitude', self._state.altitude)
                    self._state.paradigm = data.get('paradigm', self._state.paradigm)
                    self._state.current_task = data.get('current_task', self._state.current_task)

                    # === PHASE 1: DETECT - PRISM Signals ===
                    self._state.signals_emotional = data.get('signals_emotional', self._state.signals_emotional)
                    self._state.signals_mode = data.get('signals_mode', self._state.signals_mode)
                    self._state.signals_domain = data.get('signals_domain', self._state.signals_domain)
                    self._state.signals_task = data.get('signals_task', self._state.signals_task)
                    self._state.current_phase = data.get('current_phase', self._state.current_phase)

                    # === PHASE 2: CASCADE - Expert Routing ===
                    self._state.constitutional_pass = data.get('constitutional_pass', self._state.constitutional_pass)
                    self._state.safety_gate_pass = data.get('safety_gate_pass', self._state.safety_gate_pass)
                    self._state.safety_redirect = data.get('safety_redirect', self._state.safety_redirect)
                    self._state.selected_expert = data.get('selected_expert', self._state.selected_expert)
                    self._state.expert_trigger = data.get('expert_trigger', self._state.expert_trigger)

                    # === PHASE 3: LOCK - Parameter Locking ===
                    self._state.lock_status = data.get('lock_status', self._state.lock_status)
                    self._state.reflection_iteration = data.get('reflection_iteration', self._state.reflection_iteration)
                    self._state.locked_expert = data.get('locked_expert', self._state.locked_expert)
                    self._state.locked_paradigm = data.get('locked_paradigm', self._state.locked_paradigm)
                    self._state.locked_altitude = data.get('locked_altitude', self._state.locked_altitude)
                    self._state.locked_think_depth = data.get('locked_think_depth', self._state.locked_think_depth)
                    self._state.lock_checksum = data.get('lock_checksum', self._state.lock_checksum)

                    # === PHASE 5: UPDATE - RC^+xi Convergence ===
                    self._state.epistemic_tension = data.get('epistemic_tension', self._state.epistemic_tension)
                    self._state.epsilon = data.get('epsilon', self._state.epsilon)
                    self._state.attractor_basin = data.get('attractor_basin', self._state.attractor_basin)
                    self._state.stable_exchanges = data.get('stable_exchanges', self._state.stable_exchanges)
                    self._state.converged = data.get('converged', self._state.converged)
                    self._state.feedback_active = data.get('feedback_active', self._state.feedback_active)
            except Exception:
                pass


async def start_websocket_server(
    port: int = 8081,
    host: str = "0.0.0.0"
) -> WebSocketServer:
    """
    Start the WebSocket server.

    Args:
        port: Port to listen on
        host: Host to bind to

    Returns:
        Running WebSocketServer instance
    """
    server = WebSocketServer(host=host, port=port)
    await server.start()
    return server


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Orchestra WebSocket Server')
    parser.add_argument('--port', type=int, default=8081, help='Port to listen on')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to bind to')
    args = parser.parse_args()

    async def main():
        server = await start_websocket_server(port=args.port, host=args.host)
        print(f"WebSocket server running on ws://{args.host}:{args.port}")
        print("Endpoints: /ws/state")
        print("Press Ctrl+C to stop")
        try:
            await server.serve_forever()
        except KeyboardInterrupt:
            await server.stop()

    asyncio.run(main())
