"""
Substrate Protection Layer
==========================

Encrypts and signs cognitive substrate configuration to ensure only
authorized users can adjust the substrate.

Protection Levels:
- ENCRYPTED: Data is encrypted at rest (confidentiality)
- SIGNED: Data has integrity verification (authenticity)
- PROTECTED: Both encrypted AND signed (full protection)

Protected Assets:
┌─────────────────────────────────────────────────────────────────┐
│ Asset                     │ Level      │ Purpose               │
├─────────────────────────────────────────────────────────────────┤
│ Expert routing weights    │ PROTECTED  │ Prevent routing tamper│
│ Safety floors             │ SIGNED     │ Cannot weaken safety  │
│ BCM trails               │ ENCRYPTED  │ Personal calibration  │
│ Session state            │ ENCRYPTED  │ Cognitive privacy     │
│ Personal knowledge       │ ENCRYPTED  │ Personal facts        │
│ Constitutional values    │ SIGNED     │ Immutable core values │
└─────────────────────────────────────────────────────────────────┘

ThinkingMachines [He2025] Compliance:
- FIXED signature algorithm: HMAC-SHA256
- FIXED encryption: AES-256-GCM (via EncryptionManager)
- DETERMINISTIC verification
- BOUNDED operations

Usage:
    from otto.substrate.protection import SubstrateProtection

    # Setup (first time)
    protection = SubstrateProtection()
    recovery_key = protection.setup("my-secure-passphrase")
    print(f"Save this recovery key: {recovery_key}")

    # Unlock (each session)
    protection.unlock("my-secure-passphrase")

    # Read protected data
    routing_weights = protection.read_protected("routing/expert_weights.json")

    # Write protected data
    protection.write_protected("routing/expert_weights.json", new_weights)

    # Verify integrity
    if protection.verify_integrity("config/safety_floors.json"):
        print("Safety floors are authentic")
"""

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from ..encryption.encryption_manager import (
    EncryptionManager,
    EncryptionManagerError,
    NotSetupError,
    NotUnlockedError,
    InvalidPassphraseError,
    create_encryption_manager,
)
from ..crypto import (
    generate_salt,
    derive_key,
    KEY_SIZE,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Protection levels
class ProtectionLevel(Enum):
    """Level of protection for substrate assets."""
    NONE = "none"          # No protection (public)
    SIGNED = "signed"      # Integrity verification only
    ENCRYPTED = "encrypted"  # Confidentiality only
    PROTECTED = "protected"  # Both encrypted AND signed


# Asset protection mappings
SUBSTRATE_ASSETS = {
    # Routing configuration (critical for behavior)
    "routing/expert_weights.json": ProtectionLevel.PROTECTED,
    "routing/expert_priorities.json": ProtectionLevel.SIGNED,
    "routing/moe_config.json": ProtectionLevel.PROTECTED,

    # Safety configuration (critical, must not be weakened)
    "config/safety_floors.json": ProtectionLevel.SIGNED,
    "config/constitutional_values.json": ProtectionLevel.SIGNED,
    "config/burnout_thresholds.json": ProtectionLevel.SIGNED,

    # Calibration data (personal, sensitive)
    "calibration/bcm_trails.json": ProtectionLevel.PROTECTED,
    "calibration/learned_weights.json": ProtectionLevel.PROTECTED,
    "calibration/outcomes.json": ProtectionLevel.ENCRYPTED,
    "calibration/feedback_history.json": ProtectionLevel.ENCRYPTED,

    # Session state (privacy-sensitive)
    "sessions/": ProtectionLevel.ENCRYPTED,  # All files in directory
    "state/cognitive_state.json": ProtectionLevel.ENCRYPTED,
    "state/session_state.json": ProtectionLevel.ENCRYPTED,

    # Knowledge (personal facts)
    "knowledge/personal.usda": ProtectionLevel.ENCRYPTED,
    "knowledge/learned_facts.json": ProtectionLevel.ENCRYPTED,

    # Handoff documents (may contain sensitive context)
    "handoffs/": ProtectionLevel.ENCRYPTED,
}

# Signature file suffix
SIGNATURE_SUFFIX = ".sig"

# Signature version for format compatibility
SIGNATURE_VERSION = 1


# =============================================================================
# Exceptions
# =============================================================================

class SubstrateProtectionError(Exception):
    """Base exception for substrate protection."""
    pass


class IntegrityError(SubstrateProtectionError):
    """Raised when signature verification fails."""
    pass


class PermissionDeniedError(SubstrateProtectionError):
    """Raised when operation is not permitted."""
    pass


class AssetNotFoundError(SubstrateProtectionError):
    """Raised when protected asset doesn't exist."""
    pass


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class Signature:
    """
    Digital signature for substrate assets.

    Uses HMAC-SHA256 with a key derived from the master encryption key.
    """
    version: int
    asset_path: str
    content_hash: str  # SHA-256 of content
    signature: str     # HMAC-SHA256 of content_hash
    timestamp: int     # Unix timestamp

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "version": self.version,
            "asset_path": self.asset_path,
            "content_hash": self.content_hash,
            "signature": self.signature,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Signature":
        """Deserialize from dictionary."""
        return cls(
            version=data["version"],
            asset_path=data["asset_path"],
            content_hash=data["content_hash"],
            signature=data["signature"],
            timestamp=data["timestamp"],
        )

    def to_bytes(self) -> bytes:
        """Serialize to JSON bytes."""
        return json.dumps(self.to_dict(), indent=2).encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> "Signature":
        """Deserialize from JSON bytes."""
        return cls.from_dict(json.loads(data.decode("utf-8")))


@dataclass
class ProtectionStatus:
    """Current protection status."""
    is_setup: bool = False
    is_unlocked: bool = False
    protected_asset_count: int = 0
    signed_asset_count: int = 0
    integrity_valid: bool = True
    invalid_signatures: List[str] = field(default_factory=list)
    last_verification: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_setup": self.is_setup,
            "is_unlocked": self.is_unlocked,
            "protected_asset_count": self.protected_asset_count,
            "signed_asset_count": self.signed_asset_count,
            "integrity_valid": self.integrity_valid,
            "invalid_signatures": self.invalid_signatures,
            "last_verification": self.last_verification,
        }


# =============================================================================
# Substrate Protection
# =============================================================================

class SubstrateProtection:
    """
    Manages encryption and signing for cognitive substrate assets.

    Wraps EncryptionManager with substrate-specific logic for:
    - Asset classification (what needs protection)
    - Integrity verification (signature checking)
    - Access control (read/write permissions)
    """

    DEFAULT_DIR = Path.home() / ".otto"

    def __init__(self, otto_dir: Path = None):
        """
        Initialize substrate protection.

        Args:
            otto_dir: Base OTTO directory (default: ~/.otto)
        """
        self.otto_dir = otto_dir or self.DEFAULT_DIR
        self.substrate_dir = self.otto_dir / "substrate"
        self.substrate_dir.mkdir(parents=True, exist_ok=True)

        # Use existing encryption manager
        self._encryption = create_encryption_manager(self.otto_dir)

        # Signing key (derived from encryption key)
        self._signing_key: Optional[bytes] = None

    # =========================================================================
    # Setup
    # =========================================================================

    def is_setup(self) -> bool:
        """Check if protection has been configured."""
        return self._encryption.is_setup()

    def setup(
        self,
        passphrase: str,
        sign_existing: bool = True,
    ) -> str:
        """
        Set up substrate protection.

        Args:
            passphrase: Encryption passphrase (min 12 characters)
            sign_existing: Sign existing configuration files

        Returns:
            Recovery key (MUST be shown to user and saved)

        Raises:
            InvalidPassphraseError: If passphrase is too weak
        """
        # Setup encryption
        recovery_key = self._encryption.setup(passphrase)

        # Derive signing key from encryption key
        self._derive_signing_key()

        # Sign existing configuration files
        if sign_existing:
            self._sign_existing_assets()

        logger.info("Substrate protection setup complete")
        return recovery_key

    def _derive_signing_key(self) -> None:
        """Derive signing key from encryption key."""
        if not self._encryption.is_unlocked():
            return

        # Use the encryption key to derive a separate signing key
        # This is done via HKDF-like construction
        key_material = self._encryption._key
        if key_material:
            # HMAC-SHA256(key, "substrate-signing") as signing key
            self._signing_key = hmac.new(
                key_material,
                b"substrate-signing-v1",
                hashlib.sha256
            ).digest()

    def _sign_existing_assets(self) -> int:
        """Sign existing assets that require signatures. Returns count."""
        count = 0
        for asset_path, level in SUBSTRATE_ASSETS.items():
            if level in (ProtectionLevel.SIGNED, ProtectionLevel.PROTECTED):
                if asset_path.endswith('/'):
                    # Directory - sign all files
                    dir_path = self.substrate_dir / asset_path.rstrip('/')
                    if dir_path.exists():
                        for file_path in dir_path.glob("*"):
                            if file_path.is_file() and not file_path.suffix == SIGNATURE_SUFFIX:
                                try:
                                    self._sign_asset(file_path)
                                    count += 1
                                except Exception as e:
                                    logger.warning(f"Failed to sign {file_path}: {e}")
                else:
                    file_path = self.substrate_dir / asset_path
                    if file_path.exists():
                        try:
                            self._sign_asset(file_path)
                            count += 1
                        except Exception as e:
                            logger.warning(f"Failed to sign {file_path}: {e}")
        return count

    # =========================================================================
    # Unlock / Lock
    # =========================================================================

    def is_unlocked(self) -> bool:
        """Check if protection is unlocked."""
        return self._encryption.is_unlocked() and self._signing_key is not None

    def unlock(self, passphrase: str) -> bool:
        """
        Unlock substrate protection.

        Args:
            passphrase: Encryption passphrase

        Returns:
            True if unlock successful

        Raises:
            NotSetupError: If protection not configured
            InvalidPassphraseError: If passphrase is wrong
        """
        # Unlock encryption
        self._encryption.unlock(passphrase)

        # Derive signing key
        self._derive_signing_key()

        # Verify integrity of signed assets
        invalid = self._verify_all_signatures()
        if invalid:
            logger.warning(f"Integrity check failed for: {invalid}")

        logger.info("Substrate protection unlocked")
        return True

    def unlock_with_recovery_key(self, recovery_key: str) -> bool:
        """
        Unlock using recovery key.

        Args:
            recovery_key: Recovery key from setup

        Returns:
            True if unlock successful
        """
        self._encryption.unlock_with_recovery_key(recovery_key)
        self._derive_signing_key()

        logger.info("Substrate protection unlocked with recovery key")
        return True

    def lock(self) -> None:
        """Lock substrate protection."""
        self._encryption.lock()
        self._signing_key = None
        logger.info("Substrate protection locked")

    # =========================================================================
    # Read Operations
    # =========================================================================

    def read_protected(self, asset_path: str) -> bytes:
        """
        Read a protected asset.

        Args:
            asset_path: Relative path within substrate directory

        Returns:
            Decrypted content bytes

        Raises:
            NotUnlockedError: If protection is locked
            IntegrityError: If signature verification fails
            AssetNotFoundError: If asset doesn't exist
        """
        if not self.is_unlocked():
            raise NotUnlockedError("Substrate protection is locked")

        level = self._get_protection_level(asset_path)
        file_path = self.substrate_dir / asset_path

        # Check existence
        encrypted_path = file_path.with_suffix(file_path.suffix + ".enc")
        if encrypted_path.exists():
            file_path = encrypted_path
        elif not file_path.exists():
            raise AssetNotFoundError(f"Asset not found: {asset_path}")

        # Verify signature if required
        if level in (ProtectionLevel.SIGNED, ProtectionLevel.PROTECTED):
            if not self._verify_signature(file_path):
                raise IntegrityError(f"Signature verification failed: {asset_path}")

        # Decrypt if encrypted
        if level in (ProtectionLevel.ENCRYPTED, ProtectionLevel.PROTECTED):
            return self._encryption.read_encrypted(f"substrate/{asset_path}")
        else:
            return file_path.read_bytes()

    def read_protected_json(self, asset_path: str) -> Dict[str, Any]:
        """Read and parse protected JSON asset."""
        content = self.read_protected(asset_path)
        return json.loads(content.decode("utf-8"))

    def read_protected_string(self, asset_path: str, encoding: str = "utf-8") -> str:
        """Read protected asset as string."""
        return self.read_protected(asset_path).decode(encoding)

    # =========================================================================
    # Write Operations
    # =========================================================================

    def write_protected(
        self,
        asset_path: str,
        content: bytes,
        require_unlock: bool = True,
    ) -> Path:
        """
        Write a protected asset.

        Args:
            asset_path: Relative path within substrate directory
            content: Content bytes to write
            require_unlock: Require protection to be unlocked (default True)

        Returns:
            Path to written file

        Raises:
            NotUnlockedError: If protection is locked and require_unlock=True
            PermissionDeniedError: If asset is read-only
        """
        if require_unlock and not self.is_unlocked():
            raise NotUnlockedError("Substrate protection is locked")

        level = self._get_protection_level(asset_path)
        file_path = self.substrate_dir / asset_path
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write content
        if level in (ProtectionLevel.ENCRYPTED, ProtectionLevel.PROTECTED):
            # Encrypt and write
            result_path = self._encryption.write_encrypted(
                f"substrate/{asset_path}",
                content
            )
        else:
            # Write plaintext
            file_path.write_bytes(content)
            result_path = file_path

        # Sign if required
        if level in (ProtectionLevel.SIGNED, ProtectionLevel.PROTECTED):
            self._sign_asset(result_path)

        logger.debug(f"Wrote protected asset: {asset_path}")
        return result_path

    def write_protected_json(
        self,
        asset_path: str,
        data: Dict[str, Any],
        indent: int = 2,
    ) -> Path:
        """Write JSON data as protected asset."""
        content = json.dumps(data, indent=indent).encode("utf-8")
        return self.write_protected(asset_path, content)

    def write_protected_string(
        self,
        asset_path: str,
        content: str,
        encoding: str = "utf-8",
    ) -> Path:
        """Write string as protected asset."""
        return self.write_protected(asset_path, content.encode(encoding))

    # =========================================================================
    # Signing
    # =========================================================================

    def _sign_asset(self, file_path: Path) -> Path:
        """
        Sign an asset file.

        Args:
            file_path: Path to file to sign

        Returns:
            Path to signature file
        """
        if self._signing_key is None:
            raise NotUnlockedError("Cannot sign: protection is locked")

        # Read content
        content = file_path.read_bytes()

        # Compute content hash
        content_hash = hashlib.sha256(content).hexdigest()

        # Compute signature (HMAC-SHA256)
        signature = hmac.new(
            self._signing_key,
            content_hash.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        # Create signature object
        sig = Signature(
            version=SIGNATURE_VERSION,
            asset_path=str(file_path.relative_to(self.substrate_dir)),
            content_hash=content_hash,
            signature=signature,
            timestamp=int(time.time()),
        )

        # Write signature file
        sig_path = file_path.with_suffix(file_path.suffix + SIGNATURE_SUFFIX)
        sig_path.write_bytes(sig.to_bytes())

        return sig_path

    def _verify_signature(self, file_path: Path) -> bool:
        """
        Verify signature for an asset.

        Args:
            file_path: Path to file to verify

        Returns:
            True if signature is valid
        """
        if self._signing_key is None:
            return False

        # Find signature file
        sig_path = file_path.with_suffix(file_path.suffix + SIGNATURE_SUFFIX)
        if not sig_path.exists():
            logger.warning(f"No signature found for: {file_path}")
            return False

        try:
            # Read signature
            sig = Signature.from_bytes(sig_path.read_bytes())

            # Verify version
            if sig.version != SIGNATURE_VERSION:
                logger.warning(f"Unsupported signature version: {sig.version}")
                return False

            # Compute actual content hash
            content = file_path.read_bytes()
            actual_hash = hashlib.sha256(content).hexdigest()

            # Verify content hash matches
            if sig.content_hash != actual_hash:
                logger.warning(f"Content hash mismatch for: {file_path}")
                return False

            # Verify signature
            expected_sig = hmac.new(
                self._signing_key,
                sig.content_hash.encode("utf-8"),
                hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(sig.signature, expected_sig):
                logger.warning(f"Signature verification failed: {file_path}")
                return False

            return True

        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False

    def _verify_all_signatures(self) -> List[str]:
        """Verify all signed assets. Returns list of invalid paths."""
        invalid = []

        for asset_path, level in SUBSTRATE_ASSETS.items():
            if level not in (ProtectionLevel.SIGNED, ProtectionLevel.PROTECTED):
                continue

            if asset_path.endswith('/'):
                dir_path = self.substrate_dir / asset_path.rstrip('/')
                if dir_path.exists():
                    for file_path in dir_path.glob("*"):
                        if file_path.is_file() and not file_path.suffix == SIGNATURE_SUFFIX:
                            if not self._verify_signature(file_path):
                                invalid.append(str(file_path))
            else:
                file_path = self.substrate_dir / asset_path
                # Check for encrypted version
                encrypted_path = file_path.with_suffix(file_path.suffix + ".enc")
                if encrypted_path.exists():
                    file_path = encrypted_path

                if file_path.exists():
                    if not self._verify_signature(file_path):
                        invalid.append(asset_path)

        return invalid

    # =========================================================================
    # Utilities
    # =========================================================================

    def _get_protection_level(self, asset_path: str) -> ProtectionLevel:
        """Get protection level for an asset path."""
        # Check exact match
        if asset_path in SUBSTRATE_ASSETS:
            return SUBSTRATE_ASSETS[asset_path]

        # Check directory match
        for pattern, level in SUBSTRATE_ASSETS.items():
            if pattern.endswith('/'):
                if asset_path.startswith(pattern.rstrip('/')):
                    return level

        # Default to no protection
        return ProtectionLevel.NONE

    def verify_integrity(self, asset_path: str = None) -> bool:
        """
        Verify integrity of substrate assets.

        Args:
            asset_path: Specific asset to verify, or None for all

        Returns:
            True if all verified assets are valid
        """
        if not self.is_unlocked():
            return False

        if asset_path:
            file_path = self.substrate_dir / asset_path
            return self._verify_signature(file_path)
        else:
            invalid = self._verify_all_signatures()
            return len(invalid) == 0

    def get_status(self) -> ProtectionStatus:
        """Get current protection status."""
        invalid = self._verify_all_signatures() if self.is_unlocked() else []

        # Count protected assets
        protected_count = 0
        signed_count = 0
        for asset_path, level in SUBSTRATE_ASSETS.items():
            if level in (ProtectionLevel.ENCRYPTED, ProtectionLevel.PROTECTED):
                protected_count += 1
            if level in (ProtectionLevel.SIGNED, ProtectionLevel.PROTECTED):
                signed_count += 1

        return ProtectionStatus(
            is_setup=self.is_setup(),
            is_unlocked=self.is_unlocked(),
            protected_asset_count=protected_count,
            signed_asset_count=signed_count,
            integrity_valid=len(invalid) == 0,
            invalid_signatures=invalid,
            last_verification=int(time.time()) if self.is_unlocked() else None,
        )

    def change_passphrase(self, old_passphrase: str, new_passphrase: str) -> None:
        """
        Change the protection passphrase.

        Args:
            old_passphrase: Current passphrase
            new_passphrase: New passphrase
        """
        self._encryption.change_passphrase(old_passphrase, new_passphrase)
        self._derive_signing_key()

        # Re-sign all assets with new key
        self._sign_existing_assets()

        logger.info("Passphrase changed successfully")


# =============================================================================
# Factory Function
# =============================================================================

def create_substrate_protection(otto_dir: Path = None) -> SubstrateProtection:
    """Factory function to create SubstrateProtection."""
    return SubstrateProtection(otto_dir)


# =============================================================================
# Singleton Pattern
# =============================================================================

_default_protection: SubstrateProtection | None = None


def get_protection() -> SubstrateProtection:
    """
    Get or create the default SubstrateProtection instance (singleton).

    [He2025] Compliance:
    - Singleton ensures consistent state across all callers
    - Deterministic initialization order

    Returns:
        SubstrateProtection singleton instance
    """
    global _default_protection
    if _default_protection is None:
        _default_protection = create_substrate_protection()
    return _default_protection


def reset_protection() -> None:
    """
    Reset the protection singleton (for testing only).

    WARNING: This will lose all unlocked state.
    """
    global _default_protection
    _default_protection = None


__all__ = [
    "SubstrateProtection",
    "SubstrateProtectionError",
    "IntegrityError",
    "PermissionDeniedError",
    "AssetNotFoundError",
    "ProtectionLevel",
    "ProtectionStatus",
    "Signature",
    "SUBSTRATE_ASSETS",
    "create_substrate_protection",
    "get_protection",
    "reset_protection",
]
