"""
HSM/PKCS#11 Interface
=====================

Hardware Security Module interface for OTTO OS.

Provides abstraction over hardware security modules:
- Key generation in secure hardware
- Signing without key exposure
- Key never leaves the HSM
- Mock implementation for development

[He2025] Compliance:
- FIXED key slot assignments
- FIXED algorithm selection
- Deterministic interface (same operations → same behavior)

Supported HSMs:
- SoftHSM2 (software HSM for development)
- YubiHSM (hardware)
- AWS CloudHSM (via PKCS#11)
- Any PKCS#11-compliant HSM

Usage:
    from otto.security.hsm import HSMInterface, get_hsm

    hsm = get_hsm()  # Auto-detects or uses mock

    # Generate key in HSM
    key_info = hsm.generate_key(
        label="otto-signing-key",
        key_type=HSMKeyType.EC_P256,
    )

    # Sign data (key never leaves HSM)
    signature = hsm.sign(key_info.key_id, b"data to sign")

    # Verify signature
    valid = hsm.verify(key_info.key_id, b"data to sign", signature)
"""

import hashlib
import secrets
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Constants (FIXED - [He2025] Compliant)
# =============================================================================

# Default PKCS#11 library paths by platform
PKCS11_LIBRARY_PATHS = {
    'linux': [
        '/usr/lib/softhsm/libsofthsm2.so',
        '/usr/lib/x86_64-linux-gnu/softhsm/libsofthsm2.so',
        '/usr/local/lib/softhsm/libsofthsm2.so',
    ],
    'darwin': [
        '/usr/local/lib/softhsm/libsofthsm2.so',
        '/opt/homebrew/lib/softhsm/libsofthsm2.so',
    ],
    'win32': [
        'C:\\SoftHSM2\\lib\\softhsm2.dll',
        'C:\\Program Files\\SoftHSM2\\lib\\softhsm2-x64.dll',
    ],
}

# Fixed slot assignments
DEFAULT_SLOT = 0
SIGNING_SLOT = 0
ENCRYPTION_SLOT = 0


# =============================================================================
# Enums
# =============================================================================

class HSMKeyType(Enum):
    """Types of keys that can be generated in HSM."""
    # Asymmetric
    RSA_2048 = "rsa_2048"
    RSA_4096 = "rsa_4096"
    EC_P256 = "ec_p256"
    EC_P384 = "ec_p384"
    ED25519 = "ed25519"

    # Symmetric
    AES_128 = "aes_128"
    AES_256 = "aes_256"


class HSMOperation(Enum):
    """Operations supported by HSM."""
    SIGN = "sign"
    VERIFY = "verify"
    ENCRYPT = "encrypt"
    DECRYPT = "decrypt"
    WRAP = "wrap"
    UNWRAP = "unwrap"
    DERIVE = "derive"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class HSMConfig:
    """HSM configuration."""
    library_path: Optional[str] = None
    slot: int = DEFAULT_SLOT
    pin: str = ""
    label: str = "OTTO"
    use_mock: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'library_path': self.library_path,
            'slot': self.slot,
            'label': self.label,
            'use_mock': self.use_mock,
            # PIN intentionally omitted for security
        }


@dataclass
class HSMSlotInfo:
    """Information about an HSM slot."""
    slot_id: int
    label: str
    manufacturer: str
    model: str
    serial: str
    flags: int = 0
    has_token: bool = False
    token_label: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'slot_id': self.slot_id,
            'label': self.label,
            'manufacturer': self.manufacturer,
            'model': self.model,
            'serial': self.serial,
            'has_token': self.has_token,
            'token_label': self.token_label,
        }


@dataclass
class HSMKeyInfo:
    """Information about a key in the HSM."""
    key_id: str
    label: str
    key_type: HSMKeyType
    created_at: float
    slot: int = DEFAULT_SLOT
    extractable: bool = False
    operations: List[HSMOperation] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'key_id': self.key_id,
            'label': self.label,
            'key_type': self.key_type.value,
            'created_at': self.created_at,
            'slot': self.slot,
            'extractable': self.extractable,
            'operations': [op.value for op in self.operations],
            'metadata': self.metadata,
        }


# =============================================================================
# Exceptions
# =============================================================================

class HSMException(Exception):
    """Base exception for HSM operations."""
    pass


class HSMNotAvailable(HSMException):
    """HSM is not available."""
    pass


class HSMKeyNotFound(HSMException):
    """Key not found in HSM."""
    pass


class HSMOperationFailed(HSMException):
    """HSM operation failed."""
    pass


# =============================================================================
# HSM Interface
# =============================================================================

class HSMInterface(ABC):
    """
    Abstract interface for Hardware Security Modules.

    All key operations happen inside the HSM - keys never leave the device.
    """

    @abstractmethod
    def is_available(self) -> bool:
        """Check if HSM is available and connected."""
        pass

    @abstractmethod
    def get_slots(self) -> List[HSMSlotInfo]:
        """Get information about available slots."""
        pass

    @abstractmethod
    def get_keys(self, slot: int = DEFAULT_SLOT) -> List[HSMKeyInfo]:
        """List keys in a slot."""
        pass

    @abstractmethod
    def generate_key(
        self,
        label: str,
        key_type: HSMKeyType,
        slot: int = DEFAULT_SLOT,
        extractable: bool = False,
    ) -> HSMKeyInfo:
        """
        Generate a new key in the HSM.

        Args:
            label: Human-readable key label
            key_type: Type of key to generate
            slot: HSM slot to use
            extractable: Whether key can be exported (usually False)

        Returns:
            Information about the generated key
        """
        pass

    @abstractmethod
    def delete_key(self, key_id: str) -> bool:
        """Delete a key from the HSM."""
        pass

    @abstractmethod
    def sign(self, key_id: str, data: bytes) -> bytes:
        """
        Sign data using a key in the HSM.

        Args:
            key_id: ID of the signing key
            data: Data to sign

        Returns:
            Signature bytes
        """
        pass

    @abstractmethod
    def verify(self, key_id: str, data: bytes, signature: bytes) -> bool:
        """
        Verify a signature using a key in the HSM.

        Args:
            key_id: ID of the verification key
            data: Original data
            signature: Signature to verify

        Returns:
            True if signature is valid
        """
        pass

    @abstractmethod
    def encrypt(self, key_id: str, plaintext: bytes) -> bytes:
        """
        Encrypt data using a key in the HSM.

        Args:
            key_id: ID of the encryption key
            plaintext: Data to encrypt

        Returns:
            Ciphertext bytes
        """
        pass

    @abstractmethod
    def decrypt(self, key_id: str, ciphertext: bytes) -> bytes:
        """
        Decrypt data using a key in the HSM.

        Args:
            key_id: ID of the decryption key
            ciphertext: Data to decrypt

        Returns:
            Plaintext bytes
        """
        pass

    @abstractmethod
    def get_public_key(self, key_id: str) -> bytes:
        """
        Get the public key component (for asymmetric keys).

        Args:
            key_id: ID of the key

        Returns:
            Public key bytes (DER encoded)
        """
        pass


# =============================================================================
# Mock HSM Implementation
# =============================================================================

class MockHSM(HSMInterface):
    """
    Mock HSM for development and testing.

    Provides the same interface as a real HSM but stores keys in memory.
    NOT SECURE - only for development/testing.
    """

    def __init__(self, config: Optional[HSMConfig] = None):
        self._config = config or HSMConfig(use_mock=True)
        self._keys: Dict[str, Dict[str, Any]] = {}
        self._available = True

    def is_available(self) -> bool:
        return self._available

    def get_slots(self) -> List[HSMSlotInfo]:
        return [
            HSMSlotInfo(
                slot_id=0,
                label="Mock Slot 0",
                manufacturer="OTTO Mock HSM",
                model="MockHSM v1",
                serial="MOCK001",
                has_token=True,
                token_label="OTTO",
            )
        ]

    def get_keys(self, slot: int = DEFAULT_SLOT) -> List[HSMKeyInfo]:
        return [
            HSMKeyInfo(
                key_id=key_id,
                label=data['label'],
                key_type=data['key_type'],
                created_at=data['created_at'],
                slot=slot,
                extractable=data.get('extractable', False),
                operations=data.get('operations', []),
            )
            for key_id, data in self._keys.items()
            if data.get('slot', DEFAULT_SLOT) == slot
        ]

    def generate_key(
        self,
        label: str,
        key_type: HSMKeyType,
        slot: int = DEFAULT_SLOT,
        extractable: bool = False,
    ) -> HSMKeyInfo:
        # Generate key ID
        key_id = hashlib.sha256(
            f"{label}-{time.time()}-{secrets.token_hex(8)}".encode()
        ).hexdigest()[:16]

        # Determine supported operations based on key type
        if key_type in (HSMKeyType.RSA_2048, HSMKeyType.RSA_4096):
            operations = [
                HSMOperation.SIGN, HSMOperation.VERIFY,
                HSMOperation.ENCRYPT, HSMOperation.DECRYPT,
                HSMOperation.WRAP, HSMOperation.UNWRAP,
            ]
            # Generate mock RSA key material
            private_key = secrets.token_bytes(256)
            public_key = secrets.token_bytes(256)

        elif key_type in (HSMKeyType.EC_P256, HSMKeyType.EC_P384, HSMKeyType.ED25519):
            operations = [HSMOperation.SIGN, HSMOperation.VERIFY, HSMOperation.DERIVE]
            # Generate mock EC key material
            private_key = secrets.token_bytes(32)
            public_key = secrets.token_bytes(64)

        else:  # Symmetric
            operations = [HSMOperation.ENCRYPT, HSMOperation.DECRYPT]
            # Generate mock symmetric key
            key_size = 32 if key_type == HSMKeyType.AES_256 else 16
            private_key = secrets.token_bytes(key_size)
            public_key = b""

        self._keys[key_id] = {
            'label': label,
            'key_type': key_type,
            'created_at': time.time(),
            'slot': slot,
            'extractable': extractable,
            'operations': operations,
            'private_key': private_key,
            'public_key': public_key,
        }

        logger.info(f"MockHSM: Generated {key_type.value} key: {key_id}")

        return HSMKeyInfo(
            key_id=key_id,
            label=label,
            key_type=key_type,
            created_at=self._keys[key_id]['created_at'],
            slot=slot,
            extractable=extractable,
            operations=operations,
        )

    def delete_key(self, key_id: str) -> bool:
        if key_id in self._keys:
            del self._keys[key_id]
            logger.info(f"MockHSM: Deleted key: {key_id}")
            return True
        return False

    def sign(self, key_id: str, data: bytes) -> bytes:
        if key_id not in self._keys:
            raise HSMKeyNotFound(f"Key not found: {key_id}")

        key_data = self._keys[key_id]
        if HSMOperation.SIGN not in key_data['operations']:
            raise HSMOperationFailed("Key does not support signing")

        # Mock signature: HMAC-SHA256 with private key
        import hmac
        signature = hmac.new(
            key_data['private_key'],
            data,
            hashlib.sha256,
        ).digest()

        return signature

    def verify(self, key_id: str, data: bytes, signature: bytes) -> bool:
        if key_id not in self._keys:
            raise HSMKeyNotFound(f"Key not found: {key_id}")

        key_data = self._keys[key_id]
        if HSMOperation.VERIFY not in key_data['operations']:
            raise HSMOperationFailed("Key does not support verification")

        # Mock verify: Recompute signature and compare
        import hmac
        expected = hmac.new(
            key_data['private_key'],
            data,
            hashlib.sha256,
        ).digest()

        return hmac.compare_digest(signature, expected)

    def encrypt(self, key_id: str, plaintext: bytes) -> bytes:
        if key_id not in self._keys:
            raise HSMKeyNotFound(f"Key not found: {key_id}")

        key_data = self._keys[key_id]
        if HSMOperation.ENCRYPT not in key_data['operations']:
            raise HSMOperationFailed("Key does not support encryption")

        # Mock encryption: XOR with key (NOT SECURE - mock only)
        key = key_data['private_key']
        ciphertext = bytes(p ^ key[i % len(key)] for i, p in enumerate(plaintext))
        return ciphertext

    def decrypt(self, key_id: str, ciphertext: bytes) -> bytes:
        # XOR decryption is same as encryption
        return self.encrypt(key_id, ciphertext)

    def get_public_key(self, key_id: str) -> bytes:
        if key_id not in self._keys:
            raise HSMKeyNotFound(f"Key not found: {key_id}")

        key_data = self._keys[key_id]
        return key_data['public_key']


# =============================================================================
# PKCS#11 HSM Implementation
# =============================================================================

class PKCS11HSM(HSMInterface):
    """
    Real HSM implementation using PKCS#11.

    Requires python-pkcs11 library and a PKCS#11-compatible HSM.
    """

    def __init__(self, config: HSMConfig):
        self._config = config
        self._lib = None
        self._session = None
        self._available = False

        # Try to initialize
        self._initialize()

    def _initialize(self) -> None:
        """Initialize PKCS#11 library."""
        try:
            import pkcs11
            from pkcs11 import Mechanism, KeyType

            if not self._config.library_path:
                raise HSMNotAvailable("No PKCS#11 library path configured")

            lib_path = Path(self._config.library_path)
            if not lib_path.exists():
                raise HSMNotAvailable(f"PKCS#11 library not found: {lib_path}")

            self._lib = pkcs11.lib(str(lib_path))
            self._available = True
            logger.info(f"PKCS#11 HSM initialized: {lib_path}")

        except ImportError:
            logger.warning("python-pkcs11 not installed")
            self._available = False
        except Exception as e:
            logger.warning(f"Failed to initialize PKCS#11: {e}")
            self._available = False

    def is_available(self) -> bool:
        return self._available and self._lib is not None

    def _get_token(self, slot: int = DEFAULT_SLOT):
        """Get token for slot."""
        if not self._lib:
            raise HSMNotAvailable("HSM not initialized")

        slots = self._lib.get_slots(token_present=True)
        if slot >= len(slots):
            raise HSMException(f"Slot {slot} not found")

        return slots[slot].get_token()

    def _open_session(self, slot: int = DEFAULT_SLOT):
        """Open session with PIN."""
        token = self._get_token(slot)
        session = token.open(rw=True, user_pin=self._config.pin)
        return session

    def get_slots(self) -> List[HSMSlotInfo]:
        if not self._lib:
            return []

        result = []
        for slot in self._lib.get_slots():
            info = HSMSlotInfo(
                slot_id=slot.slot_id,
                label=slot.slot_description,
                manufacturer=slot.manufacturer_id,
                model="PKCS#11",
                serial="",
                has_token=slot.flags & 0x01 != 0,  # CKF_TOKEN_PRESENT
            )
            try:
                token = slot.get_token()
                info.token_label = token.label
                info.serial = token.serial
            except Exception:
                pass
            result.append(info)

        return result

    def get_keys(self, slot: int = DEFAULT_SLOT) -> List[HSMKeyInfo]:
        if not self.is_available():
            return []

        try:
            with self._open_session(slot) as session:
                keys = []
                for obj in session.get_objects():
                    if hasattr(obj, 'label'):
                        key_info = HSMKeyInfo(
                            key_id=str(obj.id) if hasattr(obj, 'id') else str(hash(obj)),
                            label=obj.label,
                            key_type=HSMKeyType.EC_P256,  # Simplified
                            created_at=time.time(),
                            slot=slot,
                        )
                        keys.append(key_info)
                return keys
        except Exception as e:
            logger.error(f"Failed to list keys: {e}")
            return []

    def generate_key(
        self,
        label: str,
        key_type: HSMKeyType,
        slot: int = DEFAULT_SLOT,
        extractable: bool = False,
    ) -> HSMKeyInfo:
        if not self.is_available():
            raise HSMNotAvailable("HSM not available")

        import pkcs11
        from pkcs11 import Mechanism, KeyType as PKCS11KeyType

        try:
            with self._open_session(slot) as session:
                # Map key type
                if key_type == HSMKeyType.AES_256:
                    key = session.generate_key(
                        PKCS11KeyType.AES,
                        256,
                        label=label,
                        extractable=extractable,
                    )
                elif key_type == HSMKeyType.EC_P256:
                    pub, priv = session.generate_keypair(
                        PKCS11KeyType.EC,
                        256,
                        label=label,
                        store=True,
                    )
                else:
                    raise HSMOperationFailed(f"Unsupported key type: {key_type}")

                key_id = hashlib.sha256(
                    f"{label}-{time.time()}".encode()
                ).hexdigest()[:16]

                return HSMKeyInfo(
                    key_id=key_id,
                    label=label,
                    key_type=key_type,
                    created_at=time.time(),
                    slot=slot,
                    extractable=extractable,
                )

        except Exception as e:
            raise HSMOperationFailed(f"Key generation failed: {e}")

    def delete_key(self, key_id: str) -> bool:
        # Would implement key deletion via PKCS#11
        logger.warning("PKCS#11 key deletion not implemented")
        return False

    def sign(self, key_id: str, data: bytes) -> bytes:
        if not self.is_available():
            raise HSMNotAvailable("HSM not available")

        import pkcs11
        from pkcs11 import Mechanism

        try:
            with self._open_session() as session:
                # Find key by label (key_id used as label lookup)
                for key in session.get_objects({pkcs11.Attribute.LABEL: key_id}):
                    return key.sign(data, mechanism=Mechanism.ECDSA_SHA256)

                raise HSMKeyNotFound(f"Key not found: {key_id}")

        except HSMKeyNotFound:
            raise
        except Exception as e:
            raise HSMOperationFailed(f"Sign failed: {e}")

    def verify(self, key_id: str, data: bytes, signature: bytes) -> bool:
        if not self.is_available():
            raise HSMNotAvailable("HSM not available")

        try:
            with self._open_session() as session:
                import pkcs11
                from pkcs11 import Mechanism

                for key in session.get_objects({pkcs11.Attribute.LABEL: key_id}):
                    try:
                        key.verify(data, signature, mechanism=Mechanism.ECDSA_SHA256)
                        return True
                    except Exception:
                        return False

                raise HSMKeyNotFound(f"Key not found: {key_id}")

        except HSMKeyNotFound:
            raise
        except Exception as e:
            raise HSMOperationFailed(f"Verify failed: {e}")

    def encrypt(self, key_id: str, plaintext: bytes) -> bytes:
        if not self.is_available():
            raise HSMNotAvailable("HSM not available")

        # Would implement PKCS#11 encryption
        raise NotImplementedError("PKCS#11 encryption not yet implemented")

    def decrypt(self, key_id: str, ciphertext: bytes) -> bytes:
        if not self.is_available():
            raise HSMNotAvailable("HSM not available")

        # Would implement PKCS#11 decryption
        raise NotImplementedError("PKCS#11 decryption not yet implemented")

    def get_public_key(self, key_id: str) -> bytes:
        if not self.is_available():
            raise HSMNotAvailable("HSM not available")

        # Would implement public key extraction
        raise NotImplementedError("PKCS#11 public key extraction not yet implemented")


# =============================================================================
# Factory Functions
# =============================================================================

_hsm_instance: Optional[HSMInterface] = None


def create_hsm(config: Optional[HSMConfig] = None) -> HSMInterface:
    """
    Create an HSM instance.

    Args:
        config: HSM configuration. If None, attempts auto-detection.

    Returns:
        HSMInterface implementation
    """
    if config is None:
        config = HSMConfig()

    if config.use_mock:
        logger.info("Using MockHSM")
        return MockHSM(config)

    # Try to find PKCS#11 library
    if config.library_path:
        hsm = PKCS11HSM(config)
        if hsm.is_available():
            return hsm

    # Auto-detect PKCS#11 library
    import sys
    platform = sys.platform

    for path in PKCS11_LIBRARY_PATHS.get(platform, []):
        if Path(path).exists():
            config.library_path = path
            hsm = PKCS11HSM(config)
            if hsm.is_available():
                logger.info(f"Auto-detected PKCS#11 HSM: {path}")
                return hsm

    # Fall back to mock
    logger.warning("No HSM available, using MockHSM")
    return MockHSM(config)


def get_hsm() -> HSMInterface:
    """Get the global HSM instance."""
    global _hsm_instance
    if _hsm_instance is None:
        _hsm_instance = create_hsm()
    return _hsm_instance


def is_hsm_available() -> bool:
    """Check if a real HSM is available."""
    hsm = get_hsm()
    return hsm.is_available() and not isinstance(hsm, MockHSM)
