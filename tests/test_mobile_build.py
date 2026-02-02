"""
Tests for Mobile Build Configuration

Tests the mobile build detection and configuration.
"""

import os
import pytest
from unittest.mock import patch

from otto.mobile import (
    is_mobile_build,
    is_desktop_build,
    PlatformCapabilities,
    get_capabilities,
    get_excluded_modules,
    get_excluded_dependencies,
    configure_mobile_environment,
    BuildManifest,
    get_build_manifest,
    MOBILE_EXCLUDED_MODULES,
    MOBILE_EXCLUDED_DEPENDENCIES,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def clean_env():
    """Clean mobile-related environment variables."""
    env_vars = [
        "OTTO_MOBILE_BUILD",
        "OTTO_BUILD_TYPE",
        "OTTO_INPUT_PROVIDER",
        "OTTO_OUTPUT_FORMAT",
        "OTTO_KEYRING_DISABLED",
    ]

    old_values = {}
    for var in env_vars:
        old_values[var] = os.environ.pop(var, None)

    yield

    # Restore
    for var, value in old_values.items():
        if value is not None:
            os.environ[var] = value
        elif var in os.environ:
            del os.environ[var]


# =============================================================================
# Build Detection Tests
# =============================================================================

class TestBuildDetection:
    """Tests for build type detection."""

    def test_is_mobile_build_default_false(self, clean_env):
        """Default is desktop (not mobile)."""
        assert is_mobile_build() is False
        assert is_desktop_build() is True

    def test_is_mobile_build_env_var(self, clean_env):
        """OTTO_MOBILE_BUILD enables mobile mode."""
        os.environ["OTTO_MOBILE_BUILD"] = "true"
        assert is_mobile_build() is True
        assert is_desktop_build() is False

    def test_is_mobile_build_env_var_values(self, clean_env):
        """Various truthy values work."""
        for value in ["1", "true", "yes", "True", "YES"]:
            os.environ["OTTO_MOBILE_BUILD"] = value
            assert is_mobile_build() is True

    def test_is_mobile_build_build_type(self, clean_env):
        """OTTO_BUILD_TYPE=mobile enables mobile mode."""
        os.environ["OTTO_BUILD_TYPE"] = "mobile"
        assert is_mobile_build() is True

    def test_is_mobile_build_ios(self, clean_env):
        """OTTO_BUILD_TYPE=ios enables mobile mode."""
        os.environ["OTTO_BUILD_TYPE"] = "ios"
        assert is_mobile_build() is True

    def test_is_mobile_build_android(self, clean_env):
        """OTTO_BUILD_TYPE=android enables mobile mode."""
        os.environ["OTTO_BUILD_TYPE"] = "android"
        assert is_mobile_build() is True

    def test_is_desktop_build_explicit(self, clean_env):
        """OTTO_BUILD_TYPE=desktop is not mobile."""
        os.environ["OTTO_BUILD_TYPE"] = "desktop"
        assert is_mobile_build() is False
        assert is_desktop_build() is True


# =============================================================================
# Platform Capabilities Tests
# =============================================================================

class TestPlatformCapabilities:
    """Tests for platform capability detection."""

    def test_capabilities_dataclass(self):
        """PlatformCapabilities has expected fields."""
        caps = PlatformCapabilities()

        assert hasattr(caps, 'has_terminal')
        assert hasattr(caps, 'has_keyring')
        assert hasattr(caps, 'has_filesystem')
        assert hasattr(caps, 'has_network')
        assert hasattr(caps, 'has_rich')
        assert hasattr(caps, 'has_input')
        assert hasattr(caps, 'is_interactive')
        assert hasattr(caps, 'is_sandboxed')

    def test_capabilities_default_desktop(self):
        """Default capabilities are desktop-oriented."""
        caps = PlatformCapabilities()

        assert caps.has_terminal is True
        assert caps.has_keyring is True
        assert caps.has_filesystem is True
        assert caps.is_sandboxed is False

    def test_get_capabilities_desktop(self, clean_env):
        """get_capabilities returns desktop capabilities by default."""
        caps = get_capabilities()

        assert caps.has_terminal is True
        assert caps.is_sandboxed is False

    def test_get_capabilities_mobile(self, clean_env):
        """get_capabilities returns mobile capabilities when mobile."""
        os.environ["OTTO_MOBILE_BUILD"] = "true"
        caps = get_capabilities()

        assert caps.has_terminal is False
        assert caps.has_keyring is False
        assert caps.has_rich is False
        assert caps.is_sandboxed is True


# =============================================================================
# Excluded Modules Tests
# =============================================================================

class TestExcludedModules:
    """Tests for excluded modules."""

    def test_mobile_excluded_modules_defined(self):
        """MOBILE_EXCLUDED_MODULES is defined and non-empty."""
        assert len(MOBILE_EXCLUDED_MODULES) > 0

    def test_mobile_excluded_dependencies_defined(self):
        """MOBILE_EXCLUDED_DEPENDENCIES is defined and non-empty."""
        assert len(MOBILE_EXCLUDED_DEPENDENCIES) > 0

    def test_tui_modules_excluded(self):
        """TUI modules are in excluded list."""
        assert "otto.cli.tui" in MOBILE_EXCLUDED_MODULES
        assert "otto.cli.tui_enhanced" in MOBILE_EXCLUDED_MODULES

    def test_rich_excluded(self):
        """Rich is in excluded dependencies."""
        assert "rich" in MOBILE_EXCLUDED_DEPENDENCIES

    def test_get_excluded_modules_desktop(self, clean_env):
        """Desktop build has no excluded modules."""
        excluded = get_excluded_modules()
        assert len(excluded) == 0

    def test_get_excluded_modules_mobile(self, clean_env):
        """Mobile build has excluded modules."""
        os.environ["OTTO_MOBILE_BUILD"] = "true"
        excluded = get_excluded_modules()

        assert "otto.cli.tui" in excluded
        assert "otto.cli.tui_enhanced" in excluded

    def test_get_excluded_dependencies_desktop(self, clean_env):
        """Desktop build has no excluded dependencies."""
        excluded = get_excluded_dependencies()
        assert len(excluded) == 0

    def test_get_excluded_dependencies_mobile(self, clean_env):
        """Mobile build has excluded dependencies."""
        os.environ["OTTO_MOBILE_BUILD"] = "true"
        excluded = get_excluded_dependencies()

        assert "rich" in excluded


# =============================================================================
# Environment Configuration Tests
# =============================================================================

class TestEnvironmentConfiguration:
    """Tests for environment configuration."""

    def test_configure_noop_on_desktop(self, clean_env):
        """configure_mobile_environment does nothing on desktop."""
        configure_mobile_environment()

        # Should not set any variables
        assert "OTTO_INPUT_PROVIDER" not in os.environ
        assert "OTTO_OUTPUT_FORMAT" not in os.environ

    def test_configure_sets_defaults_on_mobile(self, clean_env):
        """configure_mobile_environment sets defaults on mobile."""
        os.environ["OTTO_MOBILE_BUILD"] = "true"
        configure_mobile_environment()

        assert os.environ.get("OTTO_INPUT_PROVIDER") == "memory"
        assert os.environ.get("OTTO_OUTPUT_FORMAT") == "json"
        assert os.environ.get("OTTO_KEYRING_DISABLED") == "true"

    def test_configure_preserves_existing(self, clean_env):
        """configure_mobile_environment preserves existing values."""
        os.environ["OTTO_MOBILE_BUILD"] = "true"
        os.environ["OTTO_INPUT_PROVIDER"] = "async"
        os.environ["OTTO_OUTPUT_FORMAT"] = "plain"

        configure_mobile_environment()

        # Should not override existing values
        assert os.environ.get("OTTO_INPUT_PROVIDER") == "async"
        assert os.environ.get("OTTO_OUTPUT_FORMAT") == "plain"


# =============================================================================
# Build Manifest Tests
# =============================================================================

class TestBuildManifest:
    """Tests for build manifest."""

    def test_manifest_dataclass(self):
        """BuildManifest has expected fields."""
        caps = PlatformCapabilities()
        manifest = BuildManifest(
            build_type="test",
            excluded_modules=set(),
            excluded_dependencies=set(),
            capabilities=caps,
        )

        assert manifest.build_type == "test"
        assert manifest.capabilities is caps

    def test_manifest_to_dict(self):
        """BuildManifest serializes to dict."""
        caps = PlatformCapabilities(has_terminal=True)
        manifest = BuildManifest(
            build_type="test",
            excluded_modules={"mod1", "mod2"},
            excluded_dependencies={"dep1"},
            capabilities=caps,
        )

        data = manifest.to_dict()

        assert data["build_type"] == "test"
        assert "mod1" in data["excluded_modules"]
        assert "dep1" in data["excluded_dependencies"]
        assert data["capabilities"]["has_terminal"] is True

    def test_manifest_to_dict_sorted(self):
        """BuildManifest.to_dict sorts lists."""
        manifest = BuildManifest(
            build_type="test",
            excluded_modules={"z", "a", "m"},
            excluded_dependencies=set(),
            capabilities=PlatformCapabilities(),
        )

        data = manifest.to_dict()

        assert data["excluded_modules"] == ["a", "m", "z"]

    def test_get_build_manifest_desktop(self, clean_env):
        """get_build_manifest returns desktop manifest."""
        manifest = get_build_manifest()

        assert manifest.build_type == "desktop"
        assert len(manifest.excluded_modules) == 0
        assert manifest.capabilities.has_terminal is True

    def test_get_build_manifest_mobile(self, clean_env):
        """get_build_manifest returns mobile manifest."""
        os.environ["OTTO_MOBILE_BUILD"] = "true"
        manifest = get_build_manifest()

        assert manifest.build_type == "mobile"
        assert len(manifest.excluded_modules) > 0
        assert manifest.capabilities.has_terminal is False


# =============================================================================
# Determinism Tests
# =============================================================================

class TestDeterminism:
    """Tests for [He2025] determinism compliance."""

    def test_get_capabilities_deterministic(self, clean_env):
        """get_capabilities returns same result each time."""
        caps1 = get_capabilities()
        caps2 = get_capabilities()
        caps3 = get_capabilities()

        assert caps1 == caps2 == caps3

    def test_get_excluded_modules_deterministic(self, clean_env):
        """get_excluded_modules returns same result each time."""
        os.environ["OTTO_MOBILE_BUILD"] = "true"

        m1 = get_excluded_modules()
        m2 = get_excluded_modules()

        assert m1 == m2

    def test_build_manifest_deterministic(self, clean_env):
        """get_build_manifest returns same result each time."""
        import json

        manifest1 = get_build_manifest()
        manifest2 = get_build_manifest()

        # Compare serialized form
        assert json.dumps(manifest1.to_dict(), sort_keys=True) == \
               json.dumps(manifest2.to_dict(), sort_keys=True)

    def test_detection_order_fixed(self, clean_env):
        """Detection order is fixed (OTTO_MOBILE_BUILD takes precedence)."""
        # Set both, but OTTO_MOBILE_BUILD should win
        os.environ["OTTO_MOBILE_BUILD"] = "false"
        os.environ["OTTO_BUILD_TYPE"] = "mobile"

        # OTTO_MOBILE_BUILD=false means not mobile
        assert is_mobile_build() is False


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests."""

    def test_full_mobile_setup(self, clean_env):
        """Full mobile setup flow."""
        # Set mobile build
        os.environ["OTTO_MOBILE_BUILD"] = "true"

        # Check detection
        assert is_mobile_build() is True

        # Configure environment
        configure_mobile_environment()

        # Check configuration
        assert os.environ.get("OTTO_INPUT_PROVIDER") == "memory"
        assert os.environ.get("OTTO_OUTPUT_FORMAT") == "json"

        # Check capabilities
        caps = get_capabilities()
        assert caps.has_terminal is False
        assert caps.has_rich is False

        # Check excluded modules
        excluded = get_excluded_modules()
        assert "otto.cli.tui" in excluded

        # Check manifest
        manifest = get_build_manifest()
        assert manifest.build_type == "mobile"
