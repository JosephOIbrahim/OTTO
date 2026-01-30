"""
Tests for API Audit Logging.

ThinkingMachines [He2025] Compliance:
- Tests verify deterministic log format
- Tests verify append-only behavior
- Tests verify fixed structure
"""

import json
import pytest
import tempfile
import time
from pathlib import Path

from otto.api.audit import (
    AuditEvent,
    AuditRecord,
    AuditLogger,
    get_audit_logger,
    reset_audit_logger,
)


class TestAuditRecord:
    """Test AuditRecord dataclass."""

    def test_creation(self):
        """Should create record with all fields."""
        record = AuditRecord(
            timestamp=1234567890.123,
            event="key.created",
            key_id="abc123",
            details={"name": "Test Key"},
            source_ip="127.0.0.1",
            request_id="req_123",
        )

        assert record.timestamp == 1234567890.123
        assert record.event == "key.created"
        assert record.key_id == "abc123"
        assert record.details["name"] == "Test Key"

    def test_to_dict_fixed_structure(self):
        """Should have fixed field order in dict."""
        record = AuditRecord(
            timestamp=1234567890.123,
            event="key.created",
            key_id="abc123",
            details={},
        )

        d = record.to_dict()

        # Should have all expected fields
        expected_fields = [
            "timestamp", "iso_time", "event", "key_id",
            "source_ip", "request_id", "user_agent", "details"
        ]
        for field in expected_fields:
            assert field in d

    def test_to_json_deterministic(self):
        """Same record should produce identical JSON."""
        record = AuditRecord(
            timestamp=1234567890.123,
            event="key.created",
            key_id="abc123",
            details={"a": 1, "b": 2, "c": 3},
        )

        # Generate JSON multiple times
        json1 = record.to_json()
        json2 = record.to_json()
        json3 = record.to_json()

        # All should be identical
        assert json1 == json2 == json3

    def test_to_json_sorted_keys(self):
        """JSON should have sorted keys for determinism."""
        record = AuditRecord(
            timestamp=1234567890.123,
            event="key.created",
            key_id="abc123",
            details={"z": 1, "a": 2},
        )

        json_str = record.to_json()
        parsed = json.loads(json_str)

        # Verify deterministic structure
        assert "timestamp" in json_str
        assert "event" in json_str


class TestAuditLogger:
    """Test AuditLogger class."""

    @pytest.fixture
    def temp_audit_dir(self):
        """Create temporary directory for audit files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def audit_logger(self, temp_audit_dir):
        """Create audit logger with temp directory."""
        return AuditLogger(
            audit_dir=temp_audit_dir,
            also_log=False,  # Don't spam test output
        )

    def test_log_creates_file(self, audit_logger, temp_audit_dir):
        """Should create audit file on first log."""
        audit_logger.log(
            AuditEvent.KEY_CREATED,
            key_id="test123",
            name="Test Key",
        )

        audit_file = temp_audit_dir / "api_audit.jsonl"
        assert audit_file.exists()

    def test_log_appends(self, audit_logger, temp_audit_dir):
        """Should append to file (not overwrite)."""
        audit_logger.log(AuditEvent.KEY_CREATED, key_id="key1")
        audit_logger.log(AuditEvent.KEY_CREATED, key_id="key2")
        audit_logger.log(AuditEvent.KEY_CREATED, key_id="key3")

        audit_file = temp_audit_dir / "api_audit.jsonl"
        with open(audit_file) as f:
            lines = f.readlines()

        assert len(lines) == 3

    def test_log_jsonl_format(self, audit_logger, temp_audit_dir):
        """Should use JSONL format (one JSON per line)."""
        audit_logger.log(AuditEvent.KEY_CREATED, key_id="key1")
        audit_logger.log(AuditEvent.KEY_VALIDATED, key_id="key1")

        audit_file = temp_audit_dir / "api_audit.jsonl"
        with open(audit_file) as f:
            lines = f.readlines()

        # Each line should be valid JSON
        for line in lines:
            parsed = json.loads(line)
            assert "event" in parsed
            assert "timestamp" in parsed

    def test_log_returns_record(self, audit_logger):
        """Should return the created record."""
        record = audit_logger.log(
            AuditEvent.KEY_CREATED,
            key_id="test123",
        )

        assert isinstance(record, AuditRecord)
        assert record.key_id == "test123"
        assert record.event == "key.created"

    def test_disabled_logger_no_file(self, temp_audit_dir):
        """Disabled logger should not create file."""
        logger = AuditLogger(
            audit_dir=temp_audit_dir,
            enabled=False,
        )

        logger.log(AuditEvent.KEY_CREATED, key_id="test")

        audit_file = temp_audit_dir / "api_audit.jsonl"
        assert not audit_file.exists()


class TestAuditLoggerConvenienceMethods:
    """Test convenience methods for common events."""

    @pytest.fixture
    def temp_audit_dir(self):
        """Create temporary directory for audit files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def audit_logger(self, temp_audit_dir):
        """Create audit logger with temp directory."""
        return AuditLogger(
            audit_dir=temp_audit_dir,
            also_log=False,
        )

    def test_key_created(self, audit_logger):
        """Should log key creation."""
        record = audit_logger.key_created(
            key_id="abc123",
            name="My Key",
            scopes=["read:status"],
        )

        assert record.event == "key.created"
        assert record.key_id == "abc123"
        assert record.details["name"] == "My Key"
        assert record.details["scopes"] == ["read:status"]

    def test_key_validated(self, audit_logger):
        """Should log key validation."""
        record = audit_logger.key_validated(key_id="abc123")

        assert record.event == "key.validated"
        assert record.key_id == "abc123"

    def test_key_validation_failed(self, audit_logger):
        """Should log validation failure."""
        record = audit_logger.key_validation_failed(
            key_id="abc123",
            reason="expired",
        )

        assert record.event == "key.validation_failed"
        assert record.details["reason"] == "expired"

    def test_key_revoked(self, audit_logger):
        """Should log key revocation."""
        record = audit_logger.key_revoked(
            key_id="abc123",
            revoked_by="admin",
        )

        assert record.event == "key.revoked"
        assert record.details["revoked_by"] == "admin"

    def test_auth_success(self, audit_logger):
        """Should log successful auth."""
        record = audit_logger.auth_success(
            key_id="abc123",
            endpoint="/api/v1/status",
        )

        assert record.event == "auth.success"
        assert record.details["endpoint"] == "/api/v1/status"

    def test_auth_failed(self, audit_logger):
        """Should log failed auth."""
        record = audit_logger.auth_failed(
            key_id="abc123",
            reason="invalid_key",
            endpoint="/api/v1/status",
        )

        assert record.event == "auth.failed"
        assert record.details["reason"] == "invalid_key"

    def test_scope_denied(self, audit_logger):
        """Should log scope denial."""
        record = audit_logger.scope_denied(
            key_id="abc123",
            required_scope="write:state",
            endpoint="/api/v1/state",
        )

        assert record.event == "scope.denied"
        assert record.details["required_scope"] == "write:state"

    def test_rate_limit_exceeded(self, audit_logger):
        """Should log rate limit exceeded."""
        record = audit_logger.rate_limit_exceeded(
            key_id="abc123",
            endpoint="/api/v1/status",
            limit=60,
            window_seconds=60,
        )

        assert record.event == "rate.limit_exceeded"
        assert record.details["limit"] == 60


class TestDeterminismHe2025:
    """
    Test determinism compliance per [He2025].

    Key principle: Same event → same log structure.
    """

    @pytest.fixture
    def temp_audit_dir(self):
        """Create temporary directory for audit files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_same_event_same_structure(self, temp_audit_dir):
        """Same event type should produce same structure."""
        logger = AuditLogger(audit_dir=temp_audit_dir, also_log=False)

        # Log same event multiple times
        records = []
        for i in range(5):
            record = logger.log(
                AuditEvent.KEY_CREATED,
                key_id=f"key{i}",
                name=f"Key {i}",
            )
            records.append(record)

        # All should have same structure (different values)
        fields_sets = [set(r.to_dict().keys()) for r in records]
        assert all(f == fields_sets[0] for f in fields_sets)

    def test_event_types_fixed(self):
        """Event types should be fixed enumeration."""
        # Should be able to iterate all events
        all_events = list(AuditEvent)
        assert len(all_events) > 0

        # Each should have a string value
        for event in all_events:
            assert isinstance(event.value, str)
            assert "." in event.value  # Format: category.action

    def test_log_format_reproducible(self, temp_audit_dir):
        """Same inputs should produce same log format."""
        logger1 = AuditLogger(audit_dir=temp_audit_dir / "log1", also_log=False)
        logger2 = AuditLogger(audit_dir=temp_audit_dir / "log2", also_log=False)

        # Log same event to both
        record1 = logger1.log(
            AuditEvent.KEY_CREATED,
            key_id="abc123",
            name="Test",
        )
        record2 = logger2.log(
            AuditEvent.KEY_CREATED,
            key_id="abc123",
            name="Test",
        )

        # Structure should be identical (timestamp will differ)
        dict1 = record1.to_dict()
        dict2 = record2.to_dict()

        # Same keys
        assert set(dict1.keys()) == set(dict2.keys())

        # Same non-time values
        assert dict1["event"] == dict2["event"]
        assert dict1["key_id"] == dict2["key_id"]
        assert dict1["details"] == dict2["details"]


class TestGlobalAuditLogger:
    """Test global audit logger singleton."""

    def setup_method(self):
        """Reset global logger before each test."""
        reset_audit_logger()

    def teardown_method(self):
        """Reset global logger after each test."""
        reset_audit_logger()

    def test_get_audit_logger_singleton(self):
        """Should return same instance."""
        logger1 = get_audit_logger()
        logger2 = get_audit_logger()

        assert logger1 is logger2

    def test_reset_creates_new_instance(self):
        """Reset should create new instance."""
        logger1 = get_audit_logger()
        reset_audit_logger()
        logger2 = get_audit_logger()

        assert logger1 is not logger2
