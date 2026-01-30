"""
Tests for OTTO Public REST API - Phase 1 Foundation
====================================================

Tests for:
- API Scopes (scopes.py)
- API Keys (api_keys.py)
- Response Envelope (response.py)
- Error Mapping (errors.py)
"""

import json
import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

from otto.api.scopes import (
    APIScope,
    SENSITIVE_FIELDS,
    expand_scopes,
    has_scope,
    can_access_field,
    filter_state_by_scope,
    parse_scope,
    parse_scopes,
)
from otto.api.api_keys import (
    APIKey,
    APIKeyManager,
    APIKeyValidationResult,
    APIKeyError,
    APIKeyInvalidError,
    generate_api_key,
    hash_api_key,
    parse_api_key,
    validate_key_format,
)
from otto.api.response import (
    API_VERSION,
    APIResponse,
    APIResponseMeta,
    APIError,
    success,
    error,
    not_found,
    unauthorized,
    forbidden,
    rate_limited,
    invalid_params,
    internal_error,
)
from otto.api.errors import (
    APIErrorCode,
    APIException,
    BadRequestError,
    UnauthorizedError,
    ForbiddenError,
    NotFoundError,
    MethodNotAllowedError,
    RateLimitedError,
    InternalServerError,
    jsonrpc_error_to_api,
    api_code_to_http_status,
    JSONRPC_TO_HTTP,
)


# =============================================================================
# Scope Tests
# =============================================================================

class TestAPIScope:
    """Tests for APIScope enum."""

    def test_scope_values(self):
        """Scope values should be consistent strings."""
        assert APIScope.READ_STATUS.value == "read:status"
        assert APIScope.READ_STATE.value == "read:state"
        assert APIScope.READ_STATE_FULL.value == "read:state:full"
        assert APIScope.WRITE_STATE.value == "write:state"
        assert APIScope.ADMIN.value == "admin"

    def test_all_scopes_have_values(self):
        """All scopes should have non-empty string values."""
        for scope in APIScope:
            assert isinstance(scope.value, str)
            assert len(scope.value) > 0


class TestScopeExpansion:
    """Tests for scope hierarchy expansion."""

    def test_expand_admin_includes_all(self):
        """ADMIN scope should expand to include all other scopes."""
        expanded = expand_scopes({APIScope.ADMIN})
        assert APIScope.READ_STATUS in expanded
        assert APIScope.READ_STATE in expanded
        assert APIScope.READ_STATE_FULL in expanded
        assert APIScope.WRITE_STATE in expanded
        assert APIScope.WRITE_SESSION in expanded
        assert APIScope.WRITE_AGENTS in expanded
        assert APIScope.READ_AGENTS in expanded
        assert APIScope.READ_INTEGRATIONS in expanded

    def test_expand_read_state_full_includes_read_state(self):
        """READ_STATE_FULL should include READ_STATE."""
        expanded = expand_scopes({APIScope.READ_STATE_FULL})
        assert APIScope.READ_STATE in expanded
        assert APIScope.READ_STATE_FULL in expanded

    def test_expand_basic_scope_unchanged(self):
        """Basic scope without hierarchy stays unchanged."""
        expanded = expand_scopes({APIScope.READ_STATUS})
        assert expanded == {APIScope.READ_STATUS}

    def test_expand_empty_set(self):
        """Empty set expansion returns empty set."""
        expanded = expand_scopes(set())
        assert expanded == set()


class TestHasScope:
    """Tests for scope checking."""

    def test_has_scope_direct(self):
        """Direct scope match should work."""
        assert has_scope({APIScope.READ_STATUS}, APIScope.READ_STATUS)

    def test_has_scope_via_admin(self):
        """Admin should grant any scope."""
        assert has_scope({APIScope.ADMIN}, APIScope.READ_STATUS)
        assert has_scope({APIScope.ADMIN}, APIScope.WRITE_AGENTS)

    def test_has_scope_via_hierarchy(self):
        """READ_STATE_FULL grants READ_STATE."""
        assert has_scope({APIScope.READ_STATE_FULL}, APIScope.READ_STATE)

    def test_has_scope_missing(self):
        """Missing scope should return False."""
        assert not has_scope({APIScope.READ_STATUS}, APIScope.WRITE_STATE)

    def test_has_scope_empty(self):
        """Empty scopes should never match."""
        assert not has_scope(set(), APIScope.READ_STATUS)


class TestSensitiveFields:
    """Tests for sensitive field filtering."""

    def test_sensitive_fields_defined(self):
        """Sensitive fields should be defined."""
        assert "burnout_level" in SENSITIVE_FIELDS
        assert "energy_level" in SENSITIVE_FIELDS
        assert "momentum_phase" in SENSITIVE_FIELDS

    def test_can_access_field_sensitive_with_full(self):
        """READ_STATE_FULL can access sensitive fields."""
        assert can_access_field({APIScope.READ_STATE_FULL}, "burnout_level")
        assert can_access_field({APIScope.READ_STATE_FULL}, "energy_level")

    def test_can_access_field_sensitive_without_full(self):
        """READ_STATE cannot access sensitive fields."""
        assert not can_access_field({APIScope.READ_STATE}, "burnout_level")
        assert not can_access_field({APIScope.READ_STATE}, "energy_level")

    def test_can_access_field_non_sensitive(self):
        """READ_STATE can access non-sensitive fields."""
        assert can_access_field({APIScope.READ_STATE}, "session_goal")
        assert can_access_field({APIScope.READ_STATE}, "current_task")

    def test_filter_state_with_full(self):
        """READ_STATE_FULL returns all fields."""
        state = {
            "burnout_level": "GREEN",
            "energy_level": "high",
            "session_goal": "Test",
        }
        filtered = filter_state_by_scope(state, {APIScope.READ_STATE_FULL})
        assert filtered == state

    def test_filter_state_without_full(self):
        """READ_STATE filters sensitive fields."""
        state = {
            "burnout_level": "GREEN",
            "energy_level": "high",
            "session_goal": "Test",
        }
        filtered = filter_state_by_scope(state, {APIScope.READ_STATE})
        assert "burnout_level" not in filtered
        assert "energy_level" not in filtered
        assert "session_goal" in filtered


class TestScopeParsing:
    """Tests for scope string parsing."""

    def test_parse_scope_valid(self):
        """Valid scope string should parse."""
        assert parse_scope("read:status") == APIScope.READ_STATUS
        assert parse_scope("admin") == APIScope.ADMIN

    def test_parse_scope_invalid(self):
        """Invalid scope string should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown scope"):
            parse_scope("invalid:scope")

    def test_parse_scopes_list(self):
        """List of scope strings should parse."""
        scopes = parse_scopes(["read:status", "write:state"])
        assert APIScope.READ_STATUS in scopes
        assert APIScope.WRITE_STATE in scopes


# =============================================================================
# API Key Tests
# =============================================================================

class TestAPIKeyGeneration:
    """Tests for API key generation."""

    def test_generate_key_format(self):
        """Generated key should match format."""
        key, key_id = generate_api_key("live")
        assert key.startswith("otto_live_")
        assert len(key_id) == 8
        assert key_id in key

    def test_generate_key_test_env(self):
        """Test environment key should have 'test' marker."""
        key, key_id = generate_api_key("test")
        assert key.startswith("otto_test_")

    def test_generate_key_invalid_env(self):
        """Invalid environment should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid environment"):
            generate_api_key("invalid")

    def test_generate_key_unique(self):
        """Each generated key should be unique."""
        keys = [generate_api_key("live")[0] for _ in range(100)]
        assert len(set(keys)) == 100

    def test_validate_key_format_valid(self):
        """Valid key format should validate."""
        key, _ = generate_api_key("live")
        assert validate_key_format(key)

    def test_validate_key_format_invalid(self):
        """Invalid key formats should not validate."""
        assert not validate_key_format("")
        assert not validate_key_format("invalid")
        assert not validate_key_format("otto_invalid_key")
        assert not validate_key_format("otto_live_short_x")

    def test_parse_api_key_components(self):
        """Key should parse into correct components."""
        key, key_id = generate_api_key("live")
        env, parsed_id, secret = parse_api_key(key)
        assert env == "live"
        assert parsed_id == key_id
        assert len(secret) == 32

    def test_parse_api_key_invalid(self):
        """Invalid key should raise APIKeyInvalidError."""
        with pytest.raises(APIKeyInvalidError):
            parse_api_key("invalid_key")


class TestAPIKeyHashing:
    """Tests for API key hashing."""

    def test_hash_key_consistent(self):
        """Same key should produce same hash."""
        key, _ = generate_api_key("live")
        hash1 = hash_api_key(key)
        hash2 = hash_api_key(key)
        assert hash1 == hash2

    def test_hash_key_different(self):
        """Different keys should produce different hashes."""
        key1, _ = generate_api_key("live")
        key2, _ = generate_api_key("live")
        assert hash_api_key(key1) != hash_api_key(key2)

    def test_hash_key_length(self):
        """Hash should be SHA-256 hex (64 chars)."""
        key, _ = generate_api_key("live")
        hash_value = hash_api_key(key)
        assert len(hash_value) == 64


class TestAPIKeyDataclass:
    """Tests for APIKey dataclass."""

    def test_key_creation(self):
        """APIKey should be created with defaults."""
        key = APIKey(
            key_id="abc12345",
            name="Test Key",
            scopes={APIScope.READ_STATUS},
        )
        assert key.key_id == "abc12345"
        assert key.name == "Test Key"
        assert key.environment == "live"
        assert key.is_active()

    def test_key_is_active_not_revoked(self):
        """Active key should report is_active=True."""
        key = APIKey(
            key_id="abc12345",
            name="Test Key",
            scopes={APIScope.READ_STATUS},
        )
        assert key.is_active()
        assert not key.is_revoked()
        assert not key.is_expired()

    def test_key_revoked(self):
        """Revoked key should report is_active=False."""
        key = APIKey(
            key_id="abc12345",
            name="Test Key",
            scopes={APIScope.READ_STATUS},
            revoked_at=time.time(),
        )
        assert not key.is_active()
        assert key.is_revoked()

    def test_key_expired(self):
        """Expired key should report is_active=False."""
        key = APIKey(
            key_id="abc12345",
            name="Test Key",
            scopes={APIScope.READ_STATUS},
            expires_at=time.time() - 3600,  # 1 hour ago
        )
        assert not key.is_active()
        assert key.is_expired()

    def test_key_has_scope(self):
        """Key should correctly report scope membership."""
        key = APIKey(
            key_id="abc12345",
            name="Test Key",
            scopes={APIScope.READ_STATUS, APIScope.ADMIN},
        )
        assert key.has_scope(APIScope.READ_STATUS)
        assert key.has_scope(APIScope.ADMIN)
        # ADMIN implies WRITE_STATE
        assert key.has_scope(APIScope.WRITE_STATE)

    def test_key_to_dict(self):
        """Key should serialize to dict."""
        key = APIKey(
            key_id="abc12345",
            name="Test Key",
            scopes={APIScope.READ_STATUS},
        )
        d = key.to_dict()
        assert d["key_id"] == "abc12345"
        assert d["name"] == "Test Key"
        assert "read:status" in d["scopes"]

    def test_key_from_dict(self):
        """Key should deserialize from dict."""
        d = {
            "key_id": "abc12345",
            "name": "Test Key",
            "scopes": ["read:status"],
            "environment": "test",
        }
        key = APIKey.from_dict(d)
        assert key.key_id == "abc12345"
        assert key.environment == "test"
        assert APIScope.READ_STATUS in key.scopes


class TestAPIKeyManager:
    """Tests for APIKeyManager."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a manager with temporary storage."""
        return APIKeyManager(keys_dir=tmp_path, use_keyring=False)

    def test_create_key(self, manager):
        """Manager should create keys."""
        full_key, key = manager.create(
            name="Test Key",
            scopes={APIScope.READ_STATUS},
        )
        assert validate_key_format(full_key)
        assert key.name == "Test Key"
        assert APIScope.READ_STATUS in key.scopes

    def test_create_key_with_expiry(self, manager):
        """Manager should create keys with expiry."""
        _, key = manager.create(
            name="Expiring Key",
            scopes={APIScope.READ_STATUS},
            expires_in_days=30,
        )
        assert key.expires_at is not None
        # Should be ~30 days in the future
        assert key.expires_at > time.time()
        assert key.expires_at < time.time() + 31 * 86400

    def test_validate_key_valid(self, manager):
        """Manager should validate correct keys."""
        full_key, _ = manager.create(
            name="Test Key",
            scopes={APIScope.READ_STATUS},
        )
        result = manager.validate(full_key)
        assert result.valid
        assert result.key is not None
        assert result.key.name == "Test Key"

    def test_validate_key_invalid_format(self, manager):
        """Manager should reject invalid format."""
        result = manager.validate("invalid_key")
        assert not result.valid
        assert result.error_code == "INVALID_FORMAT"

    def test_validate_key_not_found(self, manager):
        """Manager should reject unknown keys."""
        result = manager.validate("otto_live_unknown1_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6")
        assert not result.valid
        assert result.error_code == "INVALID_KEY"

    def test_validate_key_revoked(self, manager):
        """Manager should reject revoked keys."""
        full_key, key = manager.create(
            name="Test Key",
            scopes={APIScope.READ_STATUS},
        )
        manager.revoke(key.key_id)
        result = manager.validate(full_key)
        assert not result.valid
        assert result.error_code == "KEY_REVOKED"

    def test_list_keys(self, manager):
        """Manager should list keys."""
        manager.create(name="Key 1", scopes={APIScope.READ_STATUS})
        manager.create(name="Key 2", scopes={APIScope.WRITE_STATE})
        keys = manager.list()
        assert len(keys) == 2

    def test_list_keys_exclude_revoked(self, manager):
        """Manager should exclude revoked keys by default."""
        _, key1 = manager.create(name="Key 1", scopes={APIScope.READ_STATUS})
        manager.create(name="Key 2", scopes={APIScope.WRITE_STATE})
        manager.revoke(key1.key_id)

        keys = manager.list()
        assert len(keys) == 1
        assert keys[0].name == "Key 2"

        # Include revoked
        keys = manager.list(include_revoked=True)
        assert len(keys) == 2

    def test_revoke_key(self, manager):
        """Manager should revoke keys."""
        _, key = manager.create(
            name="Test Key",
            scopes={APIScope.READ_STATUS},
        )
        result = manager.revoke(key.key_id)
        assert result
        assert manager.get(key.key_id).is_revoked()

    def test_rotate_key(self, manager):
        """Manager should rotate keys."""
        full_key1, key1 = manager.create(
            name="Test Key",
            scopes={APIScope.READ_STATUS},
        )
        result = manager.rotate(key1.key_id)
        assert result is not None

        full_key2, key2 = result
        assert full_key2 != full_key1
        assert "rotated" in key2.name
        assert manager.get(key1.key_id).is_revoked()

    def test_delete_key(self, manager):
        """Manager should delete keys."""
        _, key = manager.create(
            name="Test Key",
            scopes={APIScope.READ_STATUS},
        )
        result = manager.delete(key.key_id)
        assert result
        assert manager.get(key.key_id) is None

    def test_usage_tracking(self, manager):
        """Manager should track key usage."""
        full_key, key = manager.create(
            name="Test Key",
            scopes={APIScope.READ_STATUS},
        )
        assert key.use_count == 0
        assert key.last_used_at is None

        manager.validate(full_key)
        updated_key = manager.get(key.key_id)
        assert updated_key.use_count == 1
        assert updated_key.last_used_at is not None


# =============================================================================
# Response Tests
# =============================================================================

class TestAPIResponse:
    """Tests for API response envelope."""

    def test_success_response(self):
        """Success response should have correct structure."""
        response = success(data={"status": "ok"})
        d = response.to_dict()
        assert d["success"] is True
        assert d["data"]["status"] == "ok"
        assert d["error"] is None
        assert "timestamp" in d["meta"]
        assert d["meta"]["version"] == API_VERSION

    def test_error_response(self):
        """Error response should have correct structure."""
        response = error(code="NOT_FOUND", message="Resource not found")
        d = response.to_dict()
        assert d["success"] is False
        assert d["data"] is None
        assert d["error"]["code"] == "NOT_FOUND"
        assert d["error"]["message"] == "Resource not found"

    def test_response_to_json(self):
        """Response should serialize to valid JSON."""
        response = success(data={"status": "ok"})
        json_str = response.to_json()
        parsed = json.loads(json_str)
        assert parsed["success"] is True

    def test_response_with_rate_limit(self):
        """Response should include rate limit info."""
        response = success(
            data={"status": "ok"},
            rate_limit_remaining=50,
            rate_limit_reset=time.time() + 60,
        )
        d = response.to_dict()
        assert d["meta"]["rate_limit_remaining"] == 50

    def test_request_id_unique(self):
        """Each response should have unique request ID."""
        r1 = success(data={})
        r2 = success(data={})
        assert r1.meta.request_id != r2.meta.request_id

    def test_request_id_custom(self):
        """Custom request ID should be used."""
        response = success(data={}, request_id="custom_123")
        assert response.meta.request_id == "custom_123"


class TestConvenienceResponses:
    """Tests for convenience response functions."""

    def test_not_found(self):
        """not_found should create 404-style response."""
        response = not_found("User")
        d = response.to_dict()
        assert d["success"] is False
        assert d["error"]["code"] == "NOT_FOUND"
        assert "User" in d["error"]["message"]

    def test_unauthorized(self):
        """unauthorized should create 401-style response."""
        response = unauthorized()
        d = response.to_dict()
        assert d["error"]["code"] == "UNAUTHORIZED"

    def test_forbidden(self):
        """forbidden should create 403-style response."""
        response = forbidden("Insufficient scope", scope="write:state")
        d = response.to_dict()
        assert d["error"]["code"] == "FORBIDDEN"
        assert d["error"]["details"]["required_scope"] == "write:state"

    def test_rate_limited(self):
        """rate_limited should include retry_after."""
        response = rate_limited(retry_after=30.5)
        d = response.to_dict()
        assert d["error"]["code"] == "RATE_LIMITED"
        assert d["error"]["details"]["retry_after"] == 30.5

    def test_invalid_params(self):
        """invalid_params should create 400-style response."""
        response = invalid_params("Missing field 'name'", field="name")
        d = response.to_dict()
        assert d["error"]["code"] == "INVALID_PARAMS"
        assert d["error"]["details"]["field"] == "name"

    def test_internal_error(self):
        """internal_error should create 500-style response."""
        response = internal_error()
        d = response.to_dict()
        assert d["error"]["code"] == "INTERNAL_ERROR"


# =============================================================================
# Error Mapping Tests
# =============================================================================

class TestErrorMapping:
    """Tests for JSON-RPC to HTTP error mapping."""

    def test_parse_error_mapping(self):
        """PARSE_ERROR should map to 400."""
        from otto.protocol.layer1_jsonrpc import PARSE_ERROR
        http_status, api_code = JSONRPC_TO_HTTP[PARSE_ERROR]
        assert http_status == 400
        assert api_code == APIErrorCode.INVALID_JSON

    def test_method_not_found_mapping(self):
        """METHOD_NOT_FOUND should map to 404."""
        from otto.protocol.layer1_jsonrpc import METHOD_NOT_FOUND
        http_status, api_code = JSONRPC_TO_HTTP[METHOD_NOT_FOUND]
        assert http_status == 404
        assert api_code == APIErrorCode.NOT_FOUND

    def test_protection_blocked_mapping(self):
        """PROTECTION_BLOCKED should map to 403."""
        from otto.protocol.layer1_jsonrpc import PROTECTION_BLOCKED
        http_status, api_code = JSONRPC_TO_HTTP[PROTECTION_BLOCKED]
        assert http_status == 403
        assert api_code == APIErrorCode.PROTECTION_BLOCKED

    def test_internal_error_mapping(self):
        """INTERNAL_ERROR should map to 500."""
        from otto.protocol.layer1_jsonrpc import INTERNAL_ERROR
        http_status, api_code = JSONRPC_TO_HTTP[INTERNAL_ERROR]
        assert http_status == 500
        assert api_code == APIErrorCode.INTERNAL_ERROR


class TestAPIExceptions:
    """Tests for API exception classes."""

    def test_bad_request_error(self):
        """BadRequestError should have 400 status."""
        e = BadRequestError("Invalid input")
        assert e.status_code == 400
        assert e.message == "Invalid input"

    def test_unauthorized_error(self):
        """UnauthorizedError should have 401 status."""
        e = UnauthorizedError()
        assert e.status_code == 401
        assert e.error_code == APIErrorCode.UNAUTHORIZED

    def test_forbidden_error(self):
        """ForbiddenError should have 403 status."""
        e = ForbiddenError("No access")
        assert e.status_code == 403

    def test_not_found_error(self):
        """NotFoundError should have 404 status."""
        e = NotFoundError()
        assert e.status_code == 404

    def test_method_not_allowed_error(self):
        """MethodNotAllowedError should include allowed methods."""
        e = MethodNotAllowedError("DELETE", ["GET", "POST"])
        assert e.status_code == 405
        assert e.details["allowed_methods"] == ["GET", "POST"]

    def test_rate_limited_error(self):
        """RateLimitedError should include retry_after."""
        e = RateLimitedError(retry_after=60.0)
        assert e.status_code == 429
        assert e.retry_after == 60.0
        assert e.details["retry_after"] == 60.0

    def test_internal_server_error(self):
        """InternalServerError should have 500 status."""
        e = InternalServerError()
        assert e.status_code == 500

    def test_exception_to_dict(self):
        """Exception should serialize to dict."""
        e = BadRequestError("Invalid", details={"field": "name"})
        d = e.to_dict()
        assert d["code"] == APIErrorCode.INVALID_REQUEST
        assert d["message"] == "Invalid"
        assert d["details"]["field"] == "name"


class TestJSONRPCConversion:
    """Tests for JSON-RPC to API error conversion."""

    def test_convert_parse_error(self):
        """Should convert PARSE_ERROR to BadRequest."""
        from otto.protocol.layer1_jsonrpc import PARSE_ERROR
        e = jsonrpc_error_to_api(PARSE_ERROR, "Invalid JSON")
        assert e.status_code == 400
        assert e.error_code == APIErrorCode.INVALID_JSON

    def test_convert_method_not_found(self):
        """Should convert METHOD_NOT_FOUND to NotFound."""
        from otto.protocol.layer1_jsonrpc import METHOD_NOT_FOUND
        e = jsonrpc_error_to_api(METHOD_NOT_FOUND, "Method not found")
        assert e.status_code == 404
        assert e.error_code == APIErrorCode.NOT_FOUND

    def test_convert_unknown_code(self):
        """Unknown code should map to InternalError."""
        e = jsonrpc_error_to_api(-99999, "Unknown error")
        assert e.status_code == 500
        assert e.error_code == APIErrorCode.INTERNAL_ERROR

    def test_convert_with_data(self):
        """Should include error data in details."""
        from otto.protocol.layer1_jsonrpc import INVALID_PARAMS
        e = jsonrpc_error_to_api(
            INVALID_PARAMS,
            "Missing param",
            data={"param": "name"},
        )
        assert e.details["param"] == "name"

    def test_api_code_to_http_status(self):
        """Should map API codes to HTTP status."""
        assert api_code_to_http_status(APIErrorCode.UNAUTHORIZED) == 401
        assert api_code_to_http_status(APIErrorCode.RATE_LIMITED) == 429
        assert api_code_to_http_status("unknown") == 500


# =============================================================================
# Integration Tests
# =============================================================================

class TestKeyManagerPersistence:
    """Tests for key manager persistence."""

    def test_keys_persist_across_instances(self, tmp_path):
        """Keys should persist when manager is recreated."""
        # Create first manager and add a key
        manager1 = APIKeyManager(keys_dir=tmp_path, use_keyring=False)
        full_key, key = manager1.create(
            name="Persistent Key",
            scopes={APIScope.READ_STATUS},
        )

        # Create second manager and verify key exists
        manager2 = APIKeyManager(keys_dir=tmp_path, use_keyring=False)
        result = manager2.validate(full_key)
        assert result.valid
        assert result.key.name == "Persistent Key"

    def test_revoked_state_persists(self, tmp_path):
        """Revoked state should persist."""
        manager1 = APIKeyManager(keys_dir=tmp_path, use_keyring=False)
        full_key, key = manager1.create(
            name="To Revoke",
            scopes={APIScope.READ_STATUS},
        )
        manager1.revoke(key.key_id)

        manager2 = APIKeyManager(keys_dir=tmp_path, use_keyring=False)
        result = manager2.validate(full_key)
        assert not result.valid
        assert result.error_code == "KEY_REVOKED"
