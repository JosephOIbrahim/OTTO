# Testing Guide

OTTO OS maintains a comprehensive test suite with 3000+ tests and 92% coverage.

## Test Structure

```
tests/
├── unit/                    # Unit tests
│   ├── test_cognitive_engine.py
│   ├── test_state_manager.py
│   └── ...
├── integration/             # Integration tests
│   ├── test_mobile_integration.py
│   └── ...
├── e2e/                     # End-to-end tests
│   └── test_full_flow.py
├── determinism/             # Determinism verification
│   └── test_he2025_compliance.py
└── conftest.py              # Shared fixtures
```

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific file
pytest tests/test_websocket.py

# Run specific test
pytest tests/test_websocket.py::TestWebSocketHub::test_register_connection

# Run tests matching pattern
pytest -k "websocket"
```

### Coverage

```bash
# Run with coverage report
pytest --cov=src/otto --cov-report=term-missing

# Generate HTML coverage report
pytest --cov=src/otto --cov-report=html
open htmlcov/index.html

# Fail if coverage below threshold
pytest --cov=src/otto --cov-fail-under=90
```

### Parallel Execution

```bash
# Run tests in parallel (requires pytest-xdist)
pytest -n auto

# Run with specific number of workers
pytest -n 4
```

---

## Test Categories

### Markers

```python
import pytest

@pytest.mark.asyncio
async def test_async_operation():
    """Async test using pytest-asyncio."""
    result = await some_async_function()
    assert result is not None

@pytest.mark.slow
def test_slow_operation():
    """Test that takes a long time."""
    pass

@pytest.mark.determinism
def test_deterministic_output():
    """Verify deterministic behavior per [He2025]."""
    pass

@pytest.mark.integration
def test_component_integration():
    """Integration test across components."""
    pass
```

### Running by Marker

```bash
# Run async tests
pytest -m asyncio

# Skip slow tests
pytest -m "not slow"

# Run determinism tests only
pytest -m determinism

# Run integration tests
pytest -m integration
```

---

## Fixtures

### Common Fixtures

```python
# conftest.py

@pytest.fixture
def mobile_api():
    """Fresh MobileAPI instance."""
    reset_mobile_api()
    api = MobileAPI()
    yield api
    reset_mobile_api()

@pytest.fixture
def ws_hub():
    """Fresh WebSocketHub instance."""
    reset_websocket_hub()
    hub = WebSocketHub()
    yield hub
    reset_websocket_hub()

@pytest.fixture
def cognitive_state():
    """Sample cognitive state."""
    return {
        "active_mode": "focused",
        "burnout_level": "GREEN",
        "energy_level": "high",
        "momentum_phase": "rolling"
    }
```

### Async Fixtures

```python
@pytest.fixture
async def authenticated_client(mobile_api):
    """Client with authenticated device."""
    reg = await mobile_api.register_device("ios", "Test Device")
    await mobile_api.verify_device(reg["device_id"], reg["otp"], "test_user")
    return {"device_id": reg["device_id"], "user_id": "test_user"}
```

---

## Writing Tests

### Unit Test Example

```python
class TestWebSocketMessage:
    """Tests for WebSocketMessage."""

    def test_message_creation(self):
        """Test message creation with required fields."""
        msg = WebSocketMessage(
            type=MessageType.PING,
            data={"test": "value"},
        )

        assert msg.type == MessageType.PING
        assert msg.data == {"test": "value"}
        assert msg.id is not None
        assert msg.timestamp > 0

    def test_message_roundtrip(self):
        """Test message serialization and deserialization."""
        original = WebSocketMessage(
            type=MessageType.COMMAND,
            data={"command": "health"},
        )

        json_str = original.to_json()
        restored = WebSocketMessage.from_json(json_str)

        assert restored.type == original.type
        assert restored.data == original.data
```

### Integration Test Example

```python
class TestFullStackIntegration:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    async def test_mobile_to_websocket_to_push(
        self, mobile_api, ws_hub, push_manager
    ):
        """Test complete flow: Mobile API -> WebSocket -> Push."""
        # 1. Register device
        reg = await mobile_api.register_device("ios", "Test Device")
        await mobile_api.verify_device(reg["device_id"], reg["otp"], "user")

        # 2. Connect WebSocket
        messages = []
        conn = ws_hub.register("ws_conn", lambda m: messages.append(m))
        conn.subscribe(Channel.ALERTS)

        # 3. Register push
        push_manager.register_token("token", PushProvider.APNS, reg["device_id"], "user")

        # 4. Trigger alert
        monitor = StateChangeMonitor(ws_hub)
        await monitor.check_state({"burnout_level": "RED"})

        # 5. Verify
        alerts = [json.loads(m) for m in messages if "alert" in m]
        assert len(alerts) >= 1
```

### Determinism Test Example

```python
@pytest.mark.determinism
class TestHe2025Compliance:
    """Verify [He2025] determinism requirements."""

    def test_same_input_same_output(self):
        """Verify identical inputs produce identical outputs."""
        engine = CognitiveEngine()

        result1 = engine.process({"signal": "test"})
        result2 = engine.process({"signal": "test"})

        assert result1 == result2

    def test_evaluation_order_fixed(self):
        """Verify fixed evaluation order."""
        calls = []

        def track_call(name):
            calls.append(name)

        engine = CognitiveEngine()
        engine.process({"signal": "test"})

        # Order must be: detect -> cascade -> lock -> execute -> update
        assert calls == ["detect", "cascade", "lock", "execute", "update"]
```

---

## Mocking

### Mock External Services

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_push_notification_sent():
    """Test push notification is sent correctly."""
    with patch("otto.api.push.APNSProvider") as mock_apns:
        mock_apns.return_value.send = AsyncMock(return_value=True)

        manager = PushNotificationManager()
        result = await manager.send_burnout_warning(
            user_id="user123",
            level="YELLOW",
            message="Take a break"
        )

        assert result[0].status == DeliveryStatus.SENT
        mock_apns.return_value.send.assert_called_once()
```

### Mock WebSocket

```python
def test_websocket_connection():
    """Test WebSocket with mock callback."""
    messages = []

    def mock_send(message):
        messages.append(message)

    hub = WebSocketHub()
    hub.register("conn1", mock_send)

    # Welcome message should be sent
    assert len(messages) == 1
    assert "welcome" in messages[0]
```

---

## Performance Testing

### Benchmark Tests

```python
@pytest.mark.slow
def test_broadcast_performance(ws_hub):
    """Test broadcasting to many connections."""
    # Create 100 connections
    for i in range(100):
        conn = ws_hub.register(f"conn_{i}", lambda m: None)
        conn.subscribe(Channel.STATE)

    # Measure broadcast time
    import time
    start = time.time()
    sent = asyncio.run(ws_hub.broadcast_state_update({"test": "data"}))
    elapsed = time.time() - start

    assert sent == 100
    assert elapsed < 1.0  # Must complete within 1 second
```

---

## CI Integration

### GitHub Actions

Tests run automatically on:

- Every push to `master`
- Every pull request
- Nightly scheduled runs

### Local CI Simulation

```bash
# Run same checks as CI
pre-commit run --all-files
pytest --cov=src/otto --cov-fail-under=90
mypy src/
ruff check .
```

---

## Debugging Tests

### Print Debug Output

```bash
# Show print statements
pytest -s

# Show captured output on failure
pytest --capture=no

# Verbose with full diffs
pytest -vv
```

### Debug Specific Test

```bash
# Drop into debugger on failure
pytest --pdb

# Drop into debugger at start
pytest --pdb-first
```

---

## See Also

- [Contributing](contributing.md) - Contribution guidelines
- [API Reference](../API.md) - API documentation
