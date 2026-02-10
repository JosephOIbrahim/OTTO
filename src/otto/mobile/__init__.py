"""
OTTO OS Mobile Build Configuration
===================================

Platform-agnostic configuration for mobile builds.

This module provides:
- Mobile build detection
- Feature flags for platform capabilities
- Environment configuration
- Excluded module lists

Determinism:
- Fixed feature flag order
- Deterministic capability detection
- No runtime variation in configuration

Usage:
    from otto.mobile import is_mobile_build, get_capabilities

    if is_mobile_build():
        # Use mobile-specific code paths
        pass

    caps = get_capabilities()
    if caps.has_keyring:
        # Use keyring
        pass
"""

import os
from dataclasses import dataclass
from typing import List, Set


# =============================================================================
# Build Detection
# =============================================================================

def is_mobile_build() -> bool:
    """
    Detect if running as a mobile build.

    Detection order (first match wins):
    1. OTTO_MOBILE_BUILD environment variable (explicit true/false)
    2. OTTO_BUILD_TYPE environment variable
    3. Platform detection heuristics

    Fixed detection order, explicit values take precedence.
    """
    # Explicit environment variable (highest priority)
    mobile_env = os.environ.get("OTTO_MOBILE_BUILD", "").lower()
    if mobile_env in ("1", "true", "yes"):
        return True
    if mobile_env in ("0", "false", "no"):
        return False

    # Build type (only checked if OTTO_MOBILE_BUILD not set)
    build_type = os.environ.get("OTTO_BUILD_TYPE", "").lower()
    if build_type in ("mobile", "ios", "android"):
        return True

    # Platform heuristics (lowest priority)
    # Note: In actual mobile builds, this would check for Kivy/BeeWare/etc.
    # For now, we rely on explicit environment variables

    return False


def is_desktop_build() -> bool:
    """Check if running as desktop build."""
    return not is_mobile_build()


# =============================================================================
# Platform Capabilities
# =============================================================================

@dataclass
class PlatformCapabilities:
    """
    Platform capabilities for feature detection.

    Attributes:
        has_terminal: Can access terminal/console
        has_keyring: Has system keyring available
        has_filesystem: Has direct filesystem access
        has_network: Has network access
        has_rich: Has Rich library for TUI
        has_input: Can accept user input
        is_interactive: Supports interactive sessions
        is_sandboxed: Running in sandboxed environment
    """
    has_terminal: bool = True
    has_keyring: bool = True
    has_filesystem: bool = True
    has_network: bool = True
    has_rich: bool = True
    has_input: bool = True
    is_interactive: bool = True
    is_sandboxed: bool = False


def get_capabilities() -> PlatformCapabilities:
    """
    Detect platform capabilities.

    Fixed detection order, deterministic results.
    """
    if is_mobile_build():
        return PlatformCapabilities(
            has_terminal=False,
            has_keyring=False,  # Mobile uses different secure storage
            has_filesystem=True,  # Limited, sandboxed
            has_network=True,
            has_rich=False,  # No Rich on mobile
            has_input=True,  # Touch input
            is_interactive=True,
            is_sandboxed=True,
        )
    else:
        # Desktop capabilities
        return PlatformCapabilities(
            has_terminal=True,
            has_keyring=_check_keyring_available(),
            has_filesystem=True,
            has_network=True,
            has_rich=_check_rich_available(),
            has_input=True,
            is_interactive=_check_interactive(),
            is_sandboxed=False,
        )


def _check_keyring_available() -> bool:
    """Check if keyring is available."""
    try:
        import keyring
        return True
    except ImportError:
        return False


def _check_rich_available() -> bool:
    """Check if Rich is available."""
    try:
        import rich
        return True
    except ImportError:
        return False


def _check_interactive() -> bool:
    """Check if running interactively."""
    import sys
    return sys.stdin.isatty() if hasattr(sys.stdin, 'isatty') else False


# =============================================================================
# Excluded Modules
# =============================================================================

# Modules to exclude from mobile builds
MOBILE_EXCLUDED_MODULES: Set[str] = {
    # TUI modules (pure terminal)
    "otto.cli.tui",
    "otto.cli.tui_enhanced",
    "otto.tui.app",
    "otto.tui.widgets",

    # Terminal-specific
    "otto.cli.status",  # Use status_renderer instead

    # Tests for excluded modules
    "tests.test_tui",
    "tests.test_tui_enhanced",
}

# Modules that are mobile-only
MOBILE_ONLY_MODULES: Set[str] = {
    "otto.mobile",
}

# Dependencies to exclude from mobile
MOBILE_EXCLUDED_DEPENDENCIES: Set[str] = {
    "rich",
    "prompt_toolkit",
}


def get_excluded_modules() -> Set[str]:
    """Get set of modules to exclude from mobile builds."""
    if is_mobile_build():
        return MOBILE_EXCLUDED_MODULES
    return set()


def get_excluded_dependencies() -> Set[str]:
    """Get set of dependencies to exclude from mobile builds."""
    if is_mobile_build():
        return MOBILE_EXCLUDED_DEPENDENCIES
    return set()


# =============================================================================
# Environment Configuration
# =============================================================================

def configure_mobile_environment() -> None:
    """
    Configure environment for mobile builds.

    Sets appropriate defaults for mobile operation.

    Fixed configuration order.
    """
    if not is_mobile_build():
        return

    # Use memory input provider (no stdin)
    if "OTTO_INPUT_PROVIDER" not in os.environ:
        os.environ["OTTO_INPUT_PROVIDER"] = "memory"

    # Use JSON output format
    if "OTTO_OUTPUT_FORMAT" not in os.environ:
        os.environ["OTTO_OUTPUT_FORMAT"] = "json"

    # Disable keyring (use alternative secure storage)
    if "OTTO_KEYRING_DISABLED" not in os.environ:
        os.environ["OTTO_KEYRING_DISABLED"] = "true"


# =============================================================================
# Build Manifest
# =============================================================================

@dataclass
class BuildManifest:
    """
    Build manifest for mobile builds.

    Describes what's included/excluded from the build.
    """
    build_type: str
    excluded_modules: Set[str]
    excluded_dependencies: Set[str]
    capabilities: PlatformCapabilities

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "build_type": self.build_type,
            "excluded_modules": sorted(list(self.excluded_modules)),
            "excluded_dependencies": sorted(list(self.excluded_dependencies)),
            "capabilities": {
                "has_terminal": self.capabilities.has_terminal,
                "has_keyring": self.capabilities.has_keyring,
                "has_filesystem": self.capabilities.has_filesystem,
                "has_network": self.capabilities.has_network,
                "has_rich": self.capabilities.has_rich,
                "has_input": self.capabilities.has_input,
                "is_interactive": self.capabilities.is_interactive,
                "is_sandboxed": self.capabilities.is_sandboxed,
            },
        }


def get_build_manifest() -> BuildManifest:
    """
    Get the build manifest for current build type.

    Deterministic manifest generation.
    """
    if is_mobile_build():
        return BuildManifest(
            build_type="mobile",
            excluded_modules=MOBILE_EXCLUDED_MODULES,
            excluded_dependencies=MOBILE_EXCLUDED_DEPENDENCIES,
            capabilities=get_capabilities(),
        )
    else:
        return BuildManifest(
            build_type="desktop",
            excluded_modules=set(),
            excluded_dependencies=set(),
            capabilities=get_capabilities(),
        )


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "is_mobile_build",
    "is_desktop_build",
    "PlatformCapabilities",
    "get_capabilities",
    "get_excluded_modules",
    "get_excluded_dependencies",
    "configure_mobile_environment",
    "BuildManifest",
    "get_build_manifest",
    "MOBILE_EXCLUDED_MODULES",
    "MOBILE_EXCLUDED_DEPENDENCIES",
]
