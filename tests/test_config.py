"""
Tests for configuration module.

Tests:
- Default values
- Environment variable overrides
- Validation logic
- Path properties
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

from otto.config import (
    OrchestratorConfig,
    get_config,
    set_config,
    _get_env_int,
    _get_env_float,
    _get_env_bool,
    _get_env_path,
)


class TestEnvHelpers:
    """Test environment variable helper functions."""

    def test_get_env_int_default(self):
        """Should return default when env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            assert _get_env_int('NONEXISTENT_VAR', 42) == 42

    def test_get_env_int_valid(self):
        """Should parse valid integer from env."""
        with patch.dict(os.environ, {'TEST_INT': '100'}):
            assert _get_env_int('TEST_INT', 42) == 100

    def test_get_env_int_invalid(self):
        """Should return default for invalid integer."""
        with patch.dict(os.environ, {'TEST_INT': 'not_a_number'}):
            assert _get_env_int('TEST_INT', 42) == 42

    def test_get_env_float_default(self):
        """Should return default when env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            assert _get_env_float('NONEXISTENT_VAR', 3.14) == 3.14

    def test_get_env_float_valid(self):
        """Should parse valid float from env."""
        with patch.dict(os.environ, {'TEST_FLOAT': '2.718'}):
            assert _get_env_float('TEST_FLOAT', 3.14) == 2.718

    def test_get_env_float_invalid(self):
        """Should return default for invalid float."""
        with patch.dict(os.environ, {'TEST_FLOAT': 'not_a_float'}):
            assert _get_env_float('TEST_FLOAT', 3.14) == 3.14

    def test_get_env_bool_true_values(self):
        """Should recognize various truthy values."""
        for value in ['true', 'True', 'TRUE', '1', 'yes', 'Yes', 'on', 'ON']:
            with patch.dict(os.environ, {'TEST_BOOL': value}):
                assert _get_env_bool('TEST_BOOL', False) is True

    def test_get_env_bool_false_values(self):
        """Should treat non-truthy values as false."""
        for value in ['false', 'False', '0', 'no', 'off', 'anything']:
            with patch.dict(os.environ, {'TEST_BOOL': value}):
                assert _get_env_bool('TEST_BOOL', True) is False

    def test_get_env_bool_default(self):
        """Should return default when env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            assert _get_env_bool('NONEXISTENT_VAR', True) is True
            assert _get_env_bool('NONEXISTENT_VAR', False) is False

    def test_get_env_path(self):
        """Should parse path from env."""
        with patch.dict(os.environ, {'TEST_PATH': '/custom/path'}):
            result = _get_env_path('TEST_PATH', Path('/default'))
            assert result == Path('/custom/path')


class TestOrchestratorConfig:
    """Test OrchestratorConfig dataclass."""

    def test_default_values(self):
        """Should have sensible defaults."""
        # Don't clear=True as it removes HOME which breaks Path.home() on Windows
        config = OrchestratorConfig()

        assert config.agent_timeout == 30.0
        assert config.orchestration_timeout == 120.0
        assert config.max_retries == 3
        assert config.circuit_breaker_threshold == 5
        assert config.max_task_length == 10000
        assert config.log_level == 'INFO'
        assert config.log_format == 'text'

    def test_env_override_timeout(self):
        """Should override timeouts from env vars."""
        with patch.dict(os.environ, {
            'FO_AGENT_TIMEOUT': '60',
            'FO_ORCHESTRATION_TIMEOUT': '300'
        }):
            config = OrchestratorConfig()

            assert config.agent_timeout == 60.0
            assert config.orchestration_timeout == 300.0

    def test_env_override_feature_flags(self):
        """Should override feature flags from env vars."""
        with patch.dict(os.environ, {
            'FO_ENABLE_CIRCUIT_BREAKER': 'false',
            'FO_ENABLE_RATE_LIMIT': 'true'
        }):
            config = OrchestratorConfig()

            assert config.enable_circuit_breaker is False
            assert config.enable_rate_limit is True

    def test_path_properties(self):
        """Should construct paths correctly."""
        with patch.dict(os.environ, {'FO_WORKSPACE': '/test/workspace'}):
            config = OrchestratorConfig()

            assert config.workspace == Path('/test/workspace')
            # domains and frameworks are under config/ subdirectory
            assert config.domains_path == Path('/test/workspace/config/domains')
            assert config.frameworks_path == Path('/test/workspace/config/frameworks')
            # results_dir is under state/ subdirectory
            assert config.results_dir == Path('/test/workspace/state/results')

    def test_custom_domain_path(self):
        """Should allow custom domain path override."""
        with patch.dict(os.environ, {
            'FO_WORKSPACE': '/test/workspace',
            'FO_DOMAINS': '/custom/domains'
        }):
            config = OrchestratorConfig()

            assert config.domains_path == Path('/custom/domains')


class TestConfigValidation:
    """Test configuration validation."""

    def test_valid_config(self):
        """Should pass validation with defaults."""
        config = OrchestratorConfig()
        errors = config.validate()
        assert errors == []

    def test_invalid_agent_timeout(self):
        """Should catch negative agent timeout."""
        with patch.dict(os.environ, {'FO_AGENT_TIMEOUT': '-1'}):
            config = OrchestratorConfig()
            errors = config.validate()
            assert any('agent_timeout must be positive' in e for e in errors)

    def test_invalid_orchestration_timeout(self):
        """Should catch zero orchestration timeout."""
        with patch.dict(os.environ, {'FO_ORCHESTRATION_TIMEOUT': '0'}):
            config = OrchestratorConfig()
            errors = config.validate()
            assert any('orchestration_timeout must be positive' in e for e in errors)

    def test_agent_exceeds_orchestration_timeout(self):
        """Should warn when agent timeout exceeds orchestration timeout."""
        with patch.dict(os.environ, {
            'FO_AGENT_TIMEOUT': '200',
            'FO_ORCHESTRATION_TIMEOUT': '100'
        }):
            config = OrchestratorConfig()
            errors = config.validate()
            assert any('should not exceed' in e for e in errors)

    def test_invalid_log_level(self):
        """Should catch invalid log level."""
        with patch.dict(os.environ, {'FO_LOG_LEVEL': 'VERBOSE'}):
            config = OrchestratorConfig()
            errors = config.validate()
            assert any('log_level must be one of' in e for e in errors)

    def test_invalid_log_format(self):
        """Should catch invalid log format."""
        with patch.dict(os.environ, {'FO_LOG_FORMAT': 'xml'}):
            config = OrchestratorConfig()
            errors = config.validate()
            assert any("log_format must be 'text' or 'json'" in e for e in errors)


class TestConfigToDict:
    """Test configuration serialization."""

    def test_to_dict_contains_key_fields(self):
        """Should export key configuration fields."""
        config = OrchestratorConfig()
        data = config.to_dict()

        assert 'workspace' in data
        assert 'agent_timeout' in data
        assert 'orchestration_timeout' in data
        assert 'max_retries' in data
        assert 'enable_circuit_breaker' in data
        assert 'enable_bulkhead' in data

    def test_to_dict_paths_are_strings(self):
        """Should convert paths to strings."""
        config = OrchestratorConfig()
        data = config.to_dict()

        assert isinstance(data['workspace'], str)
        assert isinstance(data['domains_path'], str)


class TestGlobalConfig:
    """Test global configuration management."""

    def test_get_config_singleton(self):
        """Should return same instance on multiple calls."""
        set_config(None)  # Reset
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_set_config_override(self):
        """Should allow setting custom config."""
        custom = OrchestratorConfig()
        set_config(custom)
        assert get_config() is custom
