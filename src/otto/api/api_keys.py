"""
API Key Management for OTTO Public REST API
============================================

Handles API key lifecycle:
- Generation with secure random bytes
- Storage in OS keyring (hash only, never plaintext)
- Validation with constant-time comparison
- Rotation and revocation

Key Format:
    otto_{env}_{key_id}_{random_32_chars}

Examples:
    otto_live_abc12345_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
    otto_test_xyz98765_q9r8s7t6u5v4w3x2y1z0a9b8c7d6e5f4

Security:
- Only SHA-256 hash stored, never plaintext
- Constant-time comparison to prevent timing attacks
- Key_id logged for auditing, never full key

Determinism:
- FIXED key format
- DETERMINISTIC: key_id → stored hash lookup
"""

import hashlib
import hmac
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

from .scopes import APIScope, parse_scopes

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Key format: otto_{env}_{key_id}_{random}
KEY_PATTERN = re.compile(
    r"^otto_(live|test)_([a-z0-9]{8})_([a-zA-Z0-9]{32})$"
)

# Storage key prefix in keyring
KEYRING_PREFIX = "api-key:"

# Default key storage location (for metadata, not the actual keys)
DEFAULT_KEYS_DIR = Path.home() / ".otto" / "api_keys"


# =============================================================================
# Exceptions
# =============================================================================

class APIKeyError(Exception):
    """Base exception for API key operations."""
    pass


class APIKeyNotFoundError(APIKeyError):
    """Raised when API key is not found."""
    pass


class APIKeyInvalidError(APIKeyError):
    """Raised when API key format is invalid."""
    pass


class APIKeyExpiredError(APIKeyError):
    """Raised when API key has expired."""
    pass


class APIKeyRevokedError(APIKeyError):
    """Raised when API key has been revoked."""
    pass


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class APIKey:
    """
    API key metadata (never stores the actual key).

    Attributes:
        key_id: Unique identifier (8 chars, alphanumeric)
        name: Human-readable name/description
        scopes: Set of permission scopes
        environment: 'live' or 'test'
        created_at: UTC timestamp when created
        expires_at: UTC timestamp when expires (None = never)
        revoked_at: UTC timestamp when revoked (None = active)
        last_used_at: UTC timestamp of last use
        use_count: Number of times key has been used
        rate_limit: Optional custom rate limit (requests/minute)
    """
    key_id: str
    name: str
    scopes: Set[APIScope]
    environment: str = "live"
    created_at: float = field(default_factory=lambda: time.time())
    expires_at: Optional[float] = None
    revoked_at: Optional[float] = None
    last_used_at: Optional[float] = None
    use_count: int = 0
    rate_limit: Optional[int] = None

    def is_active(self) -> bool:
        """Check if key is active (not expired, not revoked)."""
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and time.time() > self.expires_at:
            return False
        return True

    def is_expired(self) -> bool:
        """Check if key has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def is_revoked(self) -> bool:
        """Check if key has been revoked."""
        return self.revoked_at is not None

    def has_scope(self, scope: APIScope) -> bool:
        """Check if key has a specific scope."""
        from .scopes import has_scope
        return has_scope(self.scopes, scope)

    def to_dict(self) -> Dict:
        """Convert to dict (for storage/serialization)."""
        return {
            "key_id": self.key_id,
            "name": self.name,
            "scopes": [s.value for s in self.scopes],
            "environment": self.environment,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "revoked_at": self.revoked_at,
            "last_used_at": self.last_used_at,
            "use_count": self.use_count,
            "rate_limit": self.rate_limit,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "APIKey":
        """Create from dict."""
        scopes = {APIScope(s) for s in data.get("scopes", [])}
        return cls(
            key_id=data["key_id"],
            name=data.get("name", ""),
            scopes=scopes,
            environment=data.get("environment", "live"),
            created_at=data.get("created_at", time.time()),
            expires_at=data.get("expires_at"),
            revoked_at=data.get("revoked_at"),
            last_used_at=data.get("last_used_at"),
            use_count=data.get("use_count", 0),
            rate_limit=data.get("rate_limit"),
        )


@dataclass
class APIKeyValidationResult:
    """Result of API key validation."""
    valid: bool
    key: Optional[APIKey] = None
    error: Optional[str] = None
    error_code: Optional[str] = None


# =============================================================================
# Key Generation
# =============================================================================

def generate_key_id() -> str:
    """Generate a random 8-character key ID."""
    return os.urandom(4).hex()[:8]


def generate_key_secret() -> str:
    """Generate a random 32-character secret."""
    # Use base62 (alphanumeric) for URL safety
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(chars[b % 62] for b in os.urandom(32))


def generate_api_key(environment: str = "live") -> tuple[str, str]:
    """
    Generate a new API key.

    Args:
        environment: 'live' or 'test'

    Returns:
        Tuple of (full_key, key_id)
        The full_key should be shown to user ONCE and never stored
    """
    if environment not in ("live", "test"):
        raise ValueError(f"Invalid environment: {environment}")

    key_id = generate_key_id()
    secret = generate_key_secret()
    full_key = f"otto_{environment}_{key_id}_{secret}"

    return full_key, key_id


def hash_api_key(full_key: str) -> str:
    """
    Create SHA-256 hash of API key for storage.

    Args:
        full_key: The full API key string

    Returns:
        Hex-encoded SHA-256 hash
    """
    return hashlib.sha256(full_key.encode()).hexdigest()


def parse_api_key(full_key: str) -> tuple[str, str, str]:
    """
    Parse API key into components.

    Args:
        full_key: The full API key string

    Returns:
        Tuple of (environment, key_id, secret)

    Raises:
        APIKeyInvalidError: If key format is invalid
    """
    match = KEY_PATTERN.match(full_key)
    if not match:
        raise APIKeyInvalidError("Invalid API key format")

    return match.group(1), match.group(2), match.group(3)


def validate_key_format(full_key: str) -> bool:
    """Check if API key has valid format."""
    return KEY_PATTERN.match(full_key) is not None


# =============================================================================
# API Key Manager
# =============================================================================

class APIKeyManager:
    """
    Manages API key lifecycle.

    Keys are stored in two places:
    1. Metadata (key_id, name, scopes, etc.) in JSON file
    2. Key hash in OS keyring for secure validation

    The actual key is NEVER stored - only shown once on creation.
    """

    def __init__(
        self,
        keys_dir: Optional[Path] = None,
        use_keyring: bool = True
    ):
        """
        Initialize API key manager.

        Args:
            keys_dir: Directory for key metadata storage
            use_keyring: Whether to use OS keyring for hash storage
        """
        self.keys_dir = keys_dir or DEFAULT_KEYS_DIR
        self.use_keyring = use_keyring
        self._keys_cache: Dict[str, APIKey] = {}

        # Ensure directory exists
        self.keys_dir.mkdir(parents=True, exist_ok=True)

        # Load existing keys
        self._load_keys()

    def _load_keys(self) -> None:
        """Load key metadata from storage."""
        keys_file = self.keys_dir / "keys.json"
        if keys_file.exists():
            try:
                with open(keys_file) as f:
                    data = json.load(f)
                    for key_data in data.get("keys", []):
                        key = APIKey.from_dict(key_data)
                        self._keys_cache[key.key_id] = key
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load API keys: {e}")

    def _save_keys(self) -> None:
        """Save key metadata to storage."""
        keys_file = self.keys_dir / "keys.json"
        data = {
            "version": "1.0",
            "updated_at": time.time(),
            "keys": [k.to_dict() for k in self._keys_cache.values()],
        }
        try:
            with open(keys_file, "w") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save API keys: {e}")
            raise APIKeyError(f"Failed to save keys: {e}")

    def _store_key_hash(self, key_id: str, key_hash: str) -> None:
        """Store key hash in secure storage."""
        if self.use_keyring:
            try:
                from ..crypto.keyring_adapter import store_key
                # Store hash as bytes
                store_key(f"{KEYRING_PREFIX}{key_id}", key_hash.encode())
            except ImportError:
                # Fallback to file storage if keyring not available
                self._store_hash_to_file(key_id, key_hash)
            except Exception as e:
                logger.warning(f"Keyring storage failed, using file: {e}")
                self._store_hash_to_file(key_id, key_hash)
        else:
            self._store_hash_to_file(key_id, key_hash)

    def _store_hash_to_file(self, key_id: str, key_hash: str) -> None:
        """Store key hash in file (fallback)."""
        hash_file = self.keys_dir / f"{key_id}.hash"
        with open(hash_file, "w") as f:
            f.write(key_hash)

    def _retrieve_key_hash(self, key_id: str) -> Optional[str]:
        """Retrieve key hash from secure storage."""
        if self.use_keyring:
            try:
                from ..crypto.keyring_adapter import retrieve_key
                hash_bytes = retrieve_key(f"{KEYRING_PREFIX}{key_id}")
                return hash_bytes.decode()
            except ImportError:
                return self._retrieve_hash_from_file(key_id)
            except Exception:
                return self._retrieve_hash_from_file(key_id)
        else:
            return self._retrieve_hash_from_file(key_id)

    def _retrieve_hash_from_file(self, key_id: str) -> Optional[str]:
        """Retrieve key hash from file (fallback)."""
        hash_file = self.keys_dir / f"{key_id}.hash"
        if hash_file.exists():
            with open(hash_file) as f:
                return f.read().strip()
        return None

    def _delete_key_hash(self, key_id: str) -> None:
        """Delete key hash from storage."""
        if self.use_keyring:
            try:
                from ..crypto.keyring_adapter import delete_key
                delete_key(f"{KEYRING_PREFIX}{key_id}")
            except Exception:
                pass  # Ignore if not found

        # Also remove file if exists
        hash_file = self.keys_dir / f"{key_id}.hash"
        if hash_file.exists():
            hash_file.unlink()

    def create(
        self,
        name: str,
        scopes: Set[APIScope],
        environment: str = "live",
        expires_in_days: Optional[int] = None,
        rate_limit: Optional[int] = None,
    ) -> tuple[str, APIKey]:
        """
        Create a new API key.

        Args:
            name: Human-readable name/description
            scopes: Set of permission scopes
            environment: 'live' or 'test'
            expires_in_days: Days until expiration (None = never)
            rate_limit: Custom rate limit (requests/minute)

        Returns:
            Tuple of (full_key, key_metadata)
            full_key should be shown ONCE and never stored by server
        """
        # Generate key
        full_key, key_id = generate_api_key(environment)
        key_hash = hash_api_key(full_key)

        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = time.time() + (expires_in_days * 86400)

        # Create metadata
        key = APIKey(
            key_id=key_id,
            name=name,
            scopes=scopes,
            environment=environment,
            expires_at=expires_at,
            rate_limit=rate_limit,
        )

        # Store hash and metadata
        self._store_key_hash(key_id, key_hash)
        self._keys_cache[key_id] = key
        self._save_keys()

        logger.info(f"Created API key: {key_id} (name={name}, env={environment})")

        return full_key, key

    def validate(self, full_key: str) -> APIKeyValidationResult:
        """
        Validate an API key.

        Uses constant-time comparison to prevent timing attacks.

        Args:
            full_key: The full API key string

        Returns:
            Validation result with key metadata if valid
        """
        # Check format
        if not validate_key_format(full_key):
            return APIKeyValidationResult(
                valid=False,
                error="Invalid key format",
                error_code="INVALID_FORMAT",
            )

        # Parse key
        try:
            _, key_id, _ = parse_api_key(full_key)
        except APIKeyInvalidError as e:
            return APIKeyValidationResult(
                valid=False,
                error=str(e),
                error_code="INVALID_FORMAT",
            )

        # Get key metadata
        key = self._keys_cache.get(key_id)
        if not key:
            # Return generic error to not reveal key existence
            return APIKeyValidationResult(
                valid=False,
                error="Invalid API key",
                error_code="INVALID_KEY",
            )

        # Check if revoked
        if key.is_revoked():
            return APIKeyValidationResult(
                valid=False,
                key=key,
                error="API key has been revoked",
                error_code="KEY_REVOKED",
            )

        # Check if expired
        if key.is_expired():
            return APIKeyValidationResult(
                valid=False,
                key=key,
                error="API key has expired",
                error_code="KEY_EXPIRED",
            )

        # Retrieve stored hash
        stored_hash = self._retrieve_key_hash(key_id)
        if not stored_hash:
            return APIKeyValidationResult(
                valid=False,
                error="Invalid API key",
                error_code="INVALID_KEY",
            )

        # Constant-time comparison
        provided_hash = hash_api_key(full_key)
        if not hmac.compare_digest(stored_hash, provided_hash):
            return APIKeyValidationResult(
                valid=False,
                error="Invalid API key",
                error_code="INVALID_KEY",
            )

        # Valid - update usage stats
        key.last_used_at = time.time()
        key.use_count += 1
        self._save_keys()

        return APIKeyValidationResult(valid=True, key=key)

    def get(self, key_id: str) -> Optional[APIKey]:
        """Get key metadata by ID."""
        return self._keys_cache.get(key_id)

    def list(
        self,
        include_revoked: bool = False,
        include_expired: bool = False,
    ) -> List[APIKey]:
        """
        List all API keys.

        Args:
            include_revoked: Include revoked keys
            include_expired: Include expired keys

        Returns:
            List of APIKey metadata
        """
        keys = []
        for key in self._keys_cache.values():
            if not include_revoked and key.is_revoked():
                continue
            if not include_expired and key.is_expired():
                continue
            keys.append(key)
        return sorted(keys, key=lambda k: k.created_at, reverse=True)

    def revoke(self, key_id: str, reason: Optional[str] = None) -> bool:
        """
        Revoke an API key.

        Args:
            key_id: Key ID to revoke
            reason: Optional reason for revocation

        Returns:
            True if revoked, False if not found
        """
        key = self._keys_cache.get(key_id)
        if not key:
            return False

        key.revoked_at = time.time()
        self._save_keys()

        logger.info(f"Revoked API key: {key_id} (reason={reason})")
        return True

    def rotate(
        self,
        key_id: str,
        expires_in_days: Optional[int] = None,
    ) -> Optional[tuple[str, APIKey]]:
        """
        Rotate an API key (create new, revoke old).

        Args:
            key_id: Key ID to rotate
            expires_in_days: Days until new key expires

        Returns:
            Tuple of (new_full_key, new_key_metadata) or None if not found
        """
        old_key = self._keys_cache.get(key_id)
        if not old_key:
            return None

        # Create new key with same config
        full_key, new_key = self.create(
            name=f"{old_key.name} (rotated)",
            scopes=old_key.scopes,
            environment=old_key.environment,
            expires_in_days=expires_in_days,
            rate_limit=old_key.rate_limit,
        )

        # Revoke old key
        self.revoke(key_id, reason="Rotated")

        logger.info(f"Rotated API key: {key_id} -> {new_key.key_id}")
        return full_key, new_key

    def delete(self, key_id: str) -> bool:
        """
        Permanently delete an API key.

        Args:
            key_id: Key ID to delete

        Returns:
            True if deleted, False if not found
        """
        if key_id not in self._keys_cache:
            return False

        # Remove hash from storage
        self._delete_key_hash(key_id)

        # Remove from cache
        del self._keys_cache[key_id]
        self._save_keys()

        logger.info(f"Deleted API key: {key_id}")
        return True


# =============================================================================
# Global Manager Instance
# =============================================================================

_manager: Optional[APIKeyManager] = None


def get_manager() -> APIKeyManager:
    """Get or create global API key manager."""
    global _manager
    if _manager is None:
        _manager = APIKeyManager()
    return _manager


def reset_manager() -> None:
    """Reset global manager (for testing)."""
    global _manager
    _manager = None


__all__ = [
    # Exceptions
    "APIKeyError",
    "APIKeyNotFoundError",
    "APIKeyInvalidError",
    "APIKeyExpiredError",
    "APIKeyRevokedError",

    # Data classes
    "APIKey",
    "APIKeyValidationResult",

    # Functions
    "generate_api_key",
    "hash_api_key",
    "parse_api_key",
    "validate_key_format",

    # Manager
    "APIKeyManager",
    "get_manager",
    "reset_manager",
]
