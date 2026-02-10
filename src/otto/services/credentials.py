"""
Secure Credential Management
============================

Per spec: OTTO NEVER stores raw API keys.
All credentials flow through this module with:
- OS keyring as primary storage
- Encrypted file fallback
- Audit logging of all access
- Automatic expiration

Determinism:
- Fixed hashing algorithm (SHA-256)
- Deterministic key naming
- Sorted iteration for consistent behavior
- No random delays in access patterns

Reference: https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Final, List, Optional, Set

logger = logging.getLogger(__name__)


# === Constants (Fixed) ===

CREDENTIAL_SEED: Final[int] = 0xC7ED5EED
CREDENTIAL_HASH_ALGORITHM: Final[str] = "sha256"
CREDENTIAL_NAMESPACE: Final[str] = "otto.credentials"
DEFAULT_EXPIRY_DAYS: Final[int] = 90
CREDENTIAL_VERSION: Final[str] = "1.0.0"


class CredentialScope(str, Enum):
    """
    Credential access scope levels.

    Per spec: Scopes control what can access credentials.
    """

    SYSTEM = "system"      # Core OTTO system only
    SERVICE = "service"    # Specific MCP service
    AGENT = "agent"        # Agent operations (requires approval)
    USER = "user"          # User-initiated actions

    def requires_approval(self) -> bool:
        """Check if this scope requires explicit approval."""
        return self == CredentialScope.AGENT


class CredentialError(Exception):
    """Base exception for credential operations."""
    pass


class CredentialNotFoundError(CredentialError):
    """Raised when credential doesn't exist."""
    pass


class CredentialExpiredError(CredentialError):
    """Raised when credential has expired."""
    pass


class CredentialAccessDeniedError(CredentialError):
    """Raised when access to credential is denied."""
    pass


@dataclass
class Credential:
    """
    Secure credential container.

    Credentials are NEVER logged or serialized with their value visible.
    The value is only accessible through get_value() which requires scope.
    """

    service: str
    """Service this credential belongs to (e.g., 'google_calendar')."""

    key_name: str
    """Credential identifier (e.g., 'api_key', 'oauth_token')."""

    created_at: datetime = field(default_factory=datetime.now)
    """When credential was stored."""

    expires_at: Optional[datetime] = None
    """When credential expires (None = no expiry)."""

    scope: CredentialScope = CredentialScope.SERVICE
    """Access scope for this credential."""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Non-sensitive metadata (e.g., token type, scopes granted)."""

    # Internal - NEVER serialize or log
    _value: str = field(default="", repr=False, compare=False)

    # Checksum for integrity verification
    _checksum: str = field(default="", repr=False)

    def __post_init__(self):
        """Generate checksum for integrity."""
        if self._value and not self._checksum:
            self._checksum = self._compute_checksum()

    def _compute_checksum(self) -> str:
        """Compute deterministic checksum."""
        # Fixed algorithm, fixed field order
        data = f"{self.service}|{self.key_name}|{len(self._value)}|{self.scope.value}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def is_expired(self) -> bool:
        """Check if credential has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def verify_integrity(self) -> bool:
        """Verify credential hasn't been tampered with."""
        return self._checksum == self._compute_checksum()

    def get_value(self, requested_scope: CredentialScope) -> str:
        """
        Get credential value with scope check.

        Args:
            requested_scope: Scope of the requestor

        Returns:
            Credential value

        Raises:
            CredentialExpiredError: If credential has expired
            CredentialAccessDeniedError: If scope doesn't permit access
        """
        if self.is_expired():
            raise CredentialExpiredError(
                f"Credential {self.service}/{self.key_name} has expired"
            )

        # Check scope hierarchy
        scope_hierarchy = [
            CredentialScope.USER,
            CredentialScope.AGENT,
            CredentialScope.SERVICE,
            CredentialScope.SYSTEM,
        ]

        if scope_hierarchy.index(requested_scope) > scope_hierarchy.index(self.scope):
            raise CredentialAccessDeniedError(
                f"Scope {requested_scope.value} cannot access {self.scope.value} credential"
            )

        return self._value

    def to_dict(self) -> Dict[str, Any]:
        """Serialize without value (safe for logging)."""
        return {
            "service": self.service,
            "key_name": self.key_name,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "scope": self.scope.value,
            "metadata": self.metadata,
            "is_expired": self.is_expired(),
            "checksum": self._checksum,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], value: str = "") -> "Credential":
        """Deserialize credential (value must be provided separately)."""
        return cls(
            service=data["service"],
            key_name=data["key_name"],
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            scope=CredentialScope(data["scope"]),
            metadata=data.get("metadata", {}),
            _value=value,
            _checksum=data.get("checksum", ""),
        )


class CredentialManager:
    """
    Secure credential manager.

    Architecture per spec:
    - Primary: OS keyring (most secure)
    - Fallback: Encrypted file storage
    - All access is logged
    - Automatic credential rotation alerts

    Determinism:
    - Deterministic key naming
    - Fixed iteration order (sorted)
    - No timing-based decisions
    """

    def __init__(
        self,
        otto_dir: Optional[Path] = None,
        use_keyring: bool = True,
    ):
        """
        Initialize credential manager.

        Args:
            otto_dir: Base OTTO directory
            use_keyring: Whether to use OS keyring (recommended)
        """
        self.otto_dir = otto_dir or Path.home() / ".otto"
        self._credentials_dir = self.otto_dir / "credentials"
        self._credentials_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache (credentials indexed by service/key)
        self._cache: Dict[str, Credential] = {}

        # Keyring availability
        self._use_keyring = use_keyring and self._check_keyring_available()

        # Access tracking for audit
        self._access_log: List[Dict[str, Any]] = []

        # Load metadata index
        self._load_index()

    def _check_keyring_available(self) -> bool:
        """Check if OS keyring is available."""
        try:
            import keyring
            # Test write/read/delete cycle
            test_key = f"{CREDENTIAL_NAMESPACE}.test"
            keyring.set_password(test_key, "test", "test")
            keyring.delete_password(test_key, "test")
            return True
        except Exception as e:
            logger.warning(f"Keyring unavailable: {e}")
            return False

    def _get_key_id(self, service: str, key_name: str) -> str:
        """
        Generate deterministic key identifier.

        Fixed naming scheme for reproducibility.
        """
        return f"{CREDENTIAL_NAMESPACE}.{service}.{key_name}"

    def _load_index(self) -> None:
        """Load credential metadata index."""
        index_path = self._credentials_dir / "index.json"
        if index_path.exists():
            try:
                with open(index_path) as f:
                    index = json.load(f)

                # Sorted iteration
                for key in sorted(index.get("credentials", {}).keys()):
                    meta = index["credentials"][key]
                    # Don't load values, just metadata
                    cred = Credential.from_dict(meta, value="")
                    self._cache[key] = cred

            except Exception as e:
                logger.error(f"Failed to load credential index: {e}")

    def _save_index(self) -> None:
        """Save credential metadata index."""
        index_path = self._credentials_dir / "index.json"

        # Sorted keys
        index = {
            "version": CREDENTIAL_VERSION,
            "credentials": {
                k: self._cache[k].to_dict()
                for k in sorted(self._cache.keys())
            },
        }

        with open(index_path, 'w') as f:
            json.dump(index, f, indent=2)

    def _store_value(self, key_id: str, value: str) -> None:
        """Store credential value securely."""
        if self._use_keyring:
            import keyring
            keyring.set_password(CREDENTIAL_NAMESPACE, key_id, value)
        else:
            # Fallback: encrypted file storage
            # This should integrate with EncryptionManager
            from ..encryption import create_encryption_manager

            enc_manager = create_encryption_manager(self.otto_dir)
            if enc_manager.is_unlocked():
                enc_manager.write_encrypted_string(
                    f"credentials/{key_id}.enc",
                    value
                )
            else:
                raise CredentialError(
                    "Cannot store credential: encryption is locked and keyring unavailable"
                )

    def _retrieve_value(self, key_id: str) -> str:
        """Retrieve credential value from secure storage."""
        if self._use_keyring:
            import keyring
            value = keyring.get_password(CREDENTIAL_NAMESPACE, key_id)
            if value is None:
                raise CredentialNotFoundError(f"Credential not found: {key_id}")
            return value
        else:
            # Fallback: encrypted file storage
            from ..encryption import create_encryption_manager

            enc_manager = create_encryption_manager(self.otto_dir)
            if enc_manager.is_unlocked():
                try:
                    return enc_manager.read_encrypted_string(f"credentials/{key_id}.enc")
                except FileNotFoundError:
                    raise CredentialNotFoundError(f"Credential not found: {key_id}")
            else:
                raise CredentialError(
                    "Cannot retrieve credential: encryption is locked and keyring unavailable"
                )

    def _delete_value(self, key_id: str) -> None:
        """Delete credential value from secure storage."""
        if self._use_keyring:
            import keyring
            try:
                keyring.delete_password(CREDENTIAL_NAMESPACE, key_id)
            except keyring.errors.PasswordDeleteError:
                pass  # Already deleted
        else:
            # Delete encrypted file
            enc_path = self._credentials_dir / f"{key_id}.enc"
            if enc_path.exists():
                enc_path.unlink()

    def _log_access(
        self,
        action: str,
        service: str,
        key_name: str,
        scope: CredentialScope,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """Log credential access for audit."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "service": service,
            "key_name": key_name,
            "scope": scope.value,
            "success": success,
            "error": error,
        }
        self._access_log.append(entry)

        if success:
            logger.debug(f"Credential {action}: {service}/{key_name}")
        else:
            logger.warning(f"Credential {action} FAILED: {service}/{key_name} - {error}")

    # =========================================================================
    # Public API
    # =========================================================================

    def store(
        self,
        service: str,
        key_name: str,
        value: str,
        scope: CredentialScope = CredentialScope.SERVICE,
        expires_days: Optional[int] = DEFAULT_EXPIRY_DAYS,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Credential:
        """
        Store a credential securely.

        Args:
            service: Service identifier (e.g., 'google_calendar')
            key_name: Key identifier (e.g., 'api_key')
            value: The actual credential value
            scope: Access scope
            expires_days: Days until expiry (None = no expiry)
            metadata: Optional metadata

        Returns:
            Credential object (without value)
        """
        key_id = self._get_key_id(service, key_name)

        # Calculate expiry
        expires_at = None
        if expires_days is not None:
            expires_at = datetime.now() + timedelta(days=expires_days)

        # Create credential object
        credential = Credential(
            service=service,
            key_name=key_name,
            scope=scope,
            expires_at=expires_at,
            metadata=metadata or {},
            _value=value,
        )

        try:
            # Store value securely
            self._store_value(key_id, value)

            # Cache metadata (without value)
            cached = Credential.from_dict(credential.to_dict(), value="")
            self._cache[key_id] = cached

            # Save index
            self._save_index()

            self._log_access("store", service, key_name, scope, True)
            return cached

        except Exception as e:
            self._log_access("store", service, key_name, scope, False, str(e))
            raise CredentialError(f"Failed to store credential: {e}") from e

    def get(
        self,
        service: str,
        key_name: str,
        scope: CredentialScope = CredentialScope.SERVICE,
    ) -> Credential:
        """
        Retrieve a credential.

        Args:
            service: Service identifier
            key_name: Key identifier
            scope: Requestor's scope

        Returns:
            Credential object with value accessible via get_value()
        """
        key_id = self._get_key_id(service, key_name)

        # Check cache for metadata
        if key_id not in self._cache:
            self._log_access("get", service, key_name, scope, False, "not found")
            raise CredentialNotFoundError(
                f"Credential not found: {service}/{key_name}"
            )

        cached = self._cache[key_id]

        # Check expiry
        if cached.is_expired():
            self._log_access("get", service, key_name, scope, False, "expired")
            raise CredentialExpiredError(
                f"Credential expired: {service}/{key_name}"
            )

        try:
            # Retrieve value from secure storage
            value = self._retrieve_value(key_id)

            # Return credential with value
            credential = Credential.from_dict(cached.to_dict(), value=value)

            self._log_access("get", service, key_name, scope, True)
            return credential

        except CredentialError:
            raise
        except Exception as e:
            self._log_access("get", service, key_name, scope, False, str(e))
            raise CredentialError(f"Failed to retrieve credential: {e}") from e

    def delete(
        self,
        service: str,
        key_name: str,
        scope: CredentialScope = CredentialScope.SERVICE,
    ) -> bool:
        """
        Delete a credential.

        Args:
            service: Service identifier
            key_name: Key identifier
            scope: Requestor's scope

        Returns:
            True if deleted, False if not found
        """
        key_id = self._get_key_id(service, key_name)

        if key_id not in self._cache:
            self._log_access("delete", service, key_name, scope, False, "not found")
            return False

        try:
            # Delete from secure storage
            self._delete_value(key_id)

            # Remove from cache
            del self._cache[key_id]

            # Save index
            self._save_index()

            self._log_access("delete", service, key_name, scope, True)
            return True

        except Exception as e:
            self._log_access("delete", service, key_name, scope, False, str(e))
            raise CredentialError(f"Failed to delete credential: {e}") from e

    def exists(self, service: str, key_name: str) -> bool:
        """Check if credential exists (doesn't require scope)."""
        key_id = self._get_key_id(service, key_name)
        return key_id in self._cache

    def list_credentials(
        self,
        service: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List all credentials (metadata only, no values).

        Args:
            service: Filter by service (None = all)

        Returns:
            List of credential metadata dicts
        """
        # Sorted iteration
        result = []
        for key_id in sorted(self._cache.keys()):
            cred = self._cache[key_id]
            if service is None or cred.service == service:
                result.append(cred.to_dict())
        return result

    def get_expiring_soon(
        self,
        days: int = 7,
    ) -> List[Dict[str, Any]]:
        """
        Get credentials expiring within specified days.

        Args:
            days: Number of days to check

        Returns:
            List of expiring credential metadata
        """
        threshold = datetime.now() + timedelta(days=days)
        result = []

        for key_id in sorted(self._cache.keys()):
            cred = self._cache[key_id]
            if cred.expires_at and cred.expires_at <= threshold:
                result.append(cred.to_dict())

        return result

    def rotate(
        self,
        service: str,
        key_name: str,
        new_value: str,
        scope: CredentialScope = CredentialScope.SERVICE,
    ) -> Credential:
        """
        Rotate a credential (update value, extend expiry).

        Args:
            service: Service identifier
            key_name: Key identifier
            new_value: New credential value
            scope: Requestor's scope

        Returns:
            Updated credential object
        """
        key_id = self._get_key_id(service, key_name)

        if key_id not in self._cache:
            raise CredentialNotFoundError(
                f"Credential not found: {service}/{key_name}"
            )

        old = self._cache[key_id]

        # Store with new value and extended expiry
        return self.store(
            service=service,
            key_name=key_name,
            value=new_value,
            scope=old.scope,
            expires_days=DEFAULT_EXPIRY_DAYS,
            metadata=old.metadata,
        )

    def get_access_log(self) -> List[Dict[str, Any]]:
        """Get credential access log for audit."""
        return self._access_log.copy()

    def clear_access_log(self) -> int:
        """Clear access log, return count of entries cleared."""
        count = len(self._access_log)
        self._access_log = []
        return count


# === Module-level Singleton ===

_manager: Optional[CredentialManager] = None


def get_credential_manager(
    otto_dir: Optional[Path] = None,
) -> CredentialManager:
    """Get or create the credential manager singleton."""
    global _manager
    if _manager is None:
        _manager = CredentialManager(otto_dir=otto_dir)
    return _manager


__all__ = [
    "CredentialManager",
    "Credential",
    "CredentialScope",
    "CredentialError",
    "CredentialNotFoundError",
    "CredentialExpiredError",
    "CredentialAccessDeniedError",
    "get_credential_manager",
]
