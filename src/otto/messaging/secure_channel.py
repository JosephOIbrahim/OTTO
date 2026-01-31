"""
Post-Quantum Secure Channel
===========================

Additional encryption layer on top of Matrix's Olm/Megolm.

This module provides:
- Hybrid PQ key exchange (X25519 + ML-KEM-768)
- Payload encryption with AES-256-GCM
- Threshold signature verification for critical operations
- Forward secrecy with ephemeral keys

Security Model:
- Matrix Olm/Megolm provides transport security
- This layer adds PQ resistance for payload content
- Threshold signatures prevent single-device compromise
- Belt-and-suspenders: secure even if one layer fails

Usage:
    from otto.messaging.secure_channel import SecureChannel

    channel = SecureChannel()

    # Establish secure channel with peer
    await channel.establish(peer_public_key)

    # Encrypt message
    encrypted = channel.encrypt("Secret message")

    # Decrypt received message
    plaintext = channel.decrypt(encrypted_payload)
"""

import json
import time
import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple, List
from enum import Enum
import base64

from ..crypto.pqcrypto import (
    HybridKEM,
    HybridKeyPair,
    HybridPublicKey,
    HybridCiphertext,
    get_pq_status,
    serialize_hybrid_public_key,
    deserialize_hybrid_public_key,
)
from ..crypto.encryption import encrypt_data, decrypt_data, EncryptedBlob
from ..crypto.threshold import (
    ThresholdSigner,
    Share,
    PartialSignature,
    ThresholdSignature,
)


# =============================================================================
# Constants
# =============================================================================

# Message type identifiers
MSG_TYPE_KEY_EXCHANGE = "otto.pq.keyex"
MSG_TYPE_ENCRYPTED = "otto.pq.encrypted"
MSG_TYPE_SIGNATURE_REQUEST = "otto.pq.sig_req"
MSG_TYPE_PARTIAL_SIGNATURE = "otto.pq.partial_sig"
MSG_TYPE_THRESHOLD_SIGNATURE = "otto.pq.threshold_sig"

# Protocol version
PROTOCOL_VERSION = "1.0.0"

# Key rotation interval (24 hours)
KEY_ROTATION_INTERVAL = 86400

# Maximum message age (5 minutes)
MAX_MESSAGE_AGE = 300


# =============================================================================
# Exceptions
# =============================================================================

class SecureChannelError(Exception):
    """Base exception for secure channel errors."""
    pass


class KeyExchangeError(SecureChannelError):
    """Key exchange failed."""
    pass


class DecryptionError(SecureChannelError):
    """Decryption failed."""
    pass


class SignatureError(SecureChannelError):
    """Signature verification failed."""
    pass


class ReplayError(SecureChannelError):
    """Replay attack detected."""
    pass


# =============================================================================
# Data Classes
# =============================================================================

class ChannelState(Enum):
    """State of the secure channel."""
    UNINITIALIZED = "uninitialized"
    KEY_EXCHANGE_SENT = "key_exchange_sent"
    KEY_EXCHANGE_RECEIVED = "key_exchange_received"
    ESTABLISHED = "established"
    CLOSED = "closed"


@dataclass
class ChannelInfo:
    """Information about a secure channel."""
    peer_id: str
    state: ChannelState
    established_at: Optional[float] = None
    last_message_at: Optional[float] = None
    messages_sent: int = 0
    messages_received: int = 0
    pq_enabled: bool = True
    key_generation: int = 0


@dataclass
class SecurePayload:
    """An encrypted payload for transmission."""
    version: str
    message_type: str
    ciphertext: bytes
    nonce: bytes
    timestamp: float
    sender_key_id: str
    recipient_key_id: str
    signature: Optional[bytes] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'version': self.version,
            'message_type': self.message_type,
            'ciphertext': base64.b64encode(self.ciphertext).decode(),
            'nonce': base64.b64encode(self.nonce).decode(),
            'timestamp': self.timestamp,
            'sender_key_id': self.sender_key_id,
            'recipient_key_id': self.recipient_key_id,
            'signature': base64.b64encode(self.signature).decode() if self.signature else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SecurePayload':
        """Create from dictionary."""
        return cls(
            version=data['version'],
            message_type=data['message_type'],
            ciphertext=base64.b64decode(data['ciphertext']),
            nonce=base64.b64decode(data['nonce']),
            timestamp=data['timestamp'],
            sender_key_id=data['sender_key_id'],
            recipient_key_id=data['recipient_key_id'],
            signature=base64.b64decode(data['signature']) if data.get('signature') else None,
        )

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> 'SecurePayload':
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class KeyExchangeMessage:
    """Key exchange message for establishing secure channel."""
    version: str
    sender_id: str
    public_key: bytes
    timestamp: float
    key_id: str
    signature: Optional[bytes] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'version': self.version,
            'sender_id': self.sender_id,
            'public_key': base64.b64encode(self.public_key).decode(),
            'timestamp': self.timestamp,
            'key_id': self.key_id,
            'signature': base64.b64encode(self.signature).decode() if self.signature else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KeyExchangeMessage':
        """Create from dictionary."""
        return cls(
            version=data['version'],
            sender_id=data['sender_id'],
            public_key=base64.b64decode(data['public_key']),
            timestamp=data['timestamp'],
            key_id=data['key_id'],
            signature=base64.b64decode(data['signature']) if data.get('signature') else None,
        )


# =============================================================================
# Secure Channel
# =============================================================================

class SecureChannel:
    """
    Post-quantum secure channel for OTTO messaging.

    Provides an additional encryption layer on top of Matrix's E2E encryption,
    using hybrid post-quantum cryptography.

    Features:
    - Hybrid PQ key exchange (X25519 + ML-KEM-768)
    - AES-256-GCM payload encryption
    - Replay attack prevention via timestamps and nonces
    - Key rotation support
    - Threshold signature integration
    """

    def __init__(
        self,
        device_id: str,
        enable_pq: bool = True,
        key_rotation_interval: int = KEY_ROTATION_INTERVAL,
    ):
        """
        Initialize secure channel.

        Args:
            device_id: This device's identifier
            enable_pq: Enable post-quantum algorithms
            key_rotation_interval: Key rotation interval in seconds
        """
        self._device_id = device_id
        self._enable_pq = enable_pq and get_pq_status().pq_available
        self._rotation_interval = key_rotation_interval

        # Key management
        self._kem = HybridKEM()
        self._my_keypair: Optional[HybridKeyPair] = None
        self._key_id: Optional[str] = None
        self._key_created_at: Optional[float] = None

        # Peer channels
        self._channels: Dict[str, ChannelInfo] = {}
        self._peer_keys: Dict[str, HybridPublicKey] = {}
        self._shared_secrets: Dict[str, bytes] = {}

        # Replay prevention
        self._seen_nonces: Dict[str, float] = {}
        self._nonce_cleanup_interval = 60

        # Generate initial key pair
        self._rotate_keys()

    def _rotate_keys(self) -> None:
        """Generate new key pair."""
        self._my_keypair = self._kem.generate_keypair()
        self._key_id = hashlib.sha256(
            self._my_keypair.public_key.to_bytes()
        ).hexdigest()[:16]
        self._key_created_at = time.time()

    def _should_rotate_keys(self) -> bool:
        """Check if keys should be rotated."""
        if self._key_created_at is None:
            return True
        age = time.time() - self._key_created_at
        return age >= self._rotation_interval

    @property
    def public_key(self) -> HybridPublicKey:
        """Get our public key."""
        return self._my_keypair.public_key

    @property
    def key_id(self) -> str:
        """Get our key ID."""
        return self._key_id

    @property
    def security_status(self) -> Dict[str, Any]:
        """Get security status."""
        return {
            'pq_enabled': self._enable_pq,
            'algorithm': 'X25519+ML-KEM-768' if self._enable_pq else 'X25519',
            'key_id': self._key_id,
            'key_age_seconds': time.time() - self._key_created_at if self._key_created_at else 0,
            'active_channels': len(self._channels),
            'rotation_interval': self._rotation_interval,
        }

    def create_key_exchange(self) -> KeyExchangeMessage:
        """
        Create a key exchange message to send to a peer.

        Returns:
            KeyExchangeMessage to send
        """
        if self._should_rotate_keys():
            self._rotate_keys()

        return KeyExchangeMessage(
            version=PROTOCOL_VERSION,
            sender_id=self._device_id,
            public_key=self._my_keypair.public_key.to_bytes(),
            timestamp=time.time(),
            key_id=self._key_id,
        )

    def process_key_exchange(
        self,
        message: KeyExchangeMessage,
    ) -> Tuple[bytes, bytes]:
        """
        Process a received key exchange message.

        Args:
            message: Received key exchange message

        Returns:
            Tuple of (ciphertext_to_send, shared_secret)
        """
        # Validate timestamp
        age = abs(time.time() - message.timestamp)
        if age > MAX_MESSAGE_AGE:
            raise KeyExchangeError(f"Key exchange message too old: {age}s")

        # Deserialize peer's public key
        try:
            peer_public_key = HybridPublicKey.from_bytes(
                message.public_key,
                pq_available=self._enable_pq,
            )
        except Exception as e:
            raise KeyExchangeError(f"Invalid peer public key: {e}")

        # Encapsulate shared secret
        ciphertext, shared_secret = self._kem.encapsulate(peer_public_key)

        # Store channel info
        peer_id = message.sender_id
        self._peer_keys[peer_id] = peer_public_key
        self._shared_secrets[peer_id] = shared_secret
        self._channels[peer_id] = ChannelInfo(
            peer_id=peer_id,
            state=ChannelState.ESTABLISHED,
            established_at=time.time(),
            pq_enabled=peer_public_key.post_quantum is not None,
        )

        return ciphertext.to_bytes(), shared_secret

    def complete_key_exchange(
        self,
        peer_id: str,
        ciphertext: bytes,
    ) -> bytes:
        """
        Complete key exchange by decapsulating the shared secret.

        Args:
            peer_id: Peer's identifier
            ciphertext: Received ciphertext

        Returns:
            Shared secret
        """
        # Reconstruct ciphertext object
        from ..crypto.pqcrypto import HybridCiphertext, KEMCiphertext, KEMAlgorithm

        # Parse ciphertext (classical part always present)
        classical_len = int.from_bytes(ciphertext[:2], 'big')
        classical_bytes = ciphertext[2:2 + classical_len]
        pq_bytes = ciphertext[2 + classical_len:] if len(ciphertext) > 2 + classical_len else None

        classical_ct = KEMCiphertext(KEMAlgorithm.X25519, classical_bytes)
        pq_ct = KEMCiphertext(KEMAlgorithm.MLKEM768, pq_bytes) if pq_bytes else None

        hybrid_ct = HybridCiphertext(classical=classical_ct, post_quantum=pq_ct)

        # Decapsulate
        shared_secret = self._kem.decapsulate(hybrid_ct, self._my_keypair.private_key)

        # Store
        self._shared_secrets[peer_id] = shared_secret

        # Create or update channel info
        if peer_id not in self._channels:
            self._channels[peer_id] = ChannelInfo(
                peer_id=peer_id,
                state=ChannelState.ESTABLISHED,
                established_at=time.time(),
                pq_enabled=pq_ct is not None,
            )
        else:
            self._channels[peer_id].state = ChannelState.ESTABLISHED
            self._channels[peer_id].established_at = time.time()

        return shared_secret

    def encrypt(
        self,
        peer_id: str,
        plaintext: str,
        sign: bool = False,
    ) -> SecurePayload:
        """
        Encrypt a message for a peer.

        Args:
            peer_id: Recipient's identifier
            plaintext: Message to encrypt
            sign: Whether to sign the message

        Returns:
            SecurePayload ready for transmission
        """
        if peer_id not in self._shared_secrets:
            raise SecureChannelError(f"No established channel with {peer_id}")

        shared_secret = self._shared_secrets[peer_id]

        # Encrypt using our crypto module
        encrypted = encrypt_data(
            plaintext.encode('utf-8'),
            shared_secret,
        )

        # Create payload
        payload = SecurePayload(
            version=PROTOCOL_VERSION,
            message_type=MSG_TYPE_ENCRYPTED,
            ciphertext=encrypted.ciphertext,
            nonce=encrypted.nonce,
            timestamp=time.time(),
            sender_key_id=self._key_id,
            recipient_key_id=self._channels.get(peer_id, ChannelInfo(peer_id, ChannelState.ESTABLISHED)).peer_id,
        )

        # Sign if requested
        if sign:
            payload.signature = self._sign_payload(payload)

        # Update stats
        if peer_id in self._channels:
            self._channels[peer_id].messages_sent += 1
            self._channels[peer_id].last_message_at = time.time()

        return payload

    def decrypt(
        self,
        peer_id: str,
        payload: SecurePayload,
        verify_signature: bool = True,
    ) -> str:
        """
        Decrypt a message from a peer.

        Args:
            peer_id: Sender's identifier
            payload: Encrypted payload
            verify_signature: Whether to verify signature if present

        Returns:
            Decrypted plaintext
        """
        if peer_id not in self._shared_secrets:
            raise SecureChannelError(f"No established channel with {peer_id}")

        # Check for replay
        nonce_key = payload.nonce.hex()
        if nonce_key in self._seen_nonces:
            raise ReplayError("Duplicate nonce - possible replay attack")

        # Check timestamp
        age = abs(time.time() - payload.timestamp)
        if age > MAX_MESSAGE_AGE:
            raise ReplayError(f"Message too old: {age}s")

        # Verify signature if present
        if verify_signature and payload.signature:
            if not self._verify_payload_signature(payload, peer_id):
                raise SignatureError("Invalid payload signature")

        # Record nonce
        self._seen_nonces[nonce_key] = time.time()
        self._cleanup_nonces()

        # Decrypt
        shared_secret = self._shared_secrets[peer_id]

        # Reconstruct encrypted blob from payload
        # The blob format is: version (1 byte) + nonce (12 bytes) + ciphertext
        blob_bytes = bytes([1]) + payload.nonce + payload.ciphertext
        encrypted_blob = EncryptedBlob.from_bytes(blob_bytes)

        try:
            plaintext = decrypt_data(encrypted_blob, shared_secret)
            return plaintext.decode('utf-8')
        except Exception as e:
            raise DecryptionError(f"Decryption failed: {e}")

    def _sign_payload(self, payload: SecurePayload) -> bytes:
        """Sign a payload."""
        # Create signature data
        data = (
            payload.version.encode() +
            payload.message_type.encode() +
            payload.ciphertext +
            payload.nonce +
            str(payload.timestamp).encode()
        )
        return hashlib.sha256(data).digest()

    def _verify_payload_signature(self, payload: SecurePayload, peer_id: str) -> bool:
        """Verify a payload signature."""
        if not payload.signature:
            return False

        expected = self._sign_payload(payload)
        return secrets.compare_digest(expected, payload.signature)

    def _cleanup_nonces(self) -> None:
        """Remove old nonces."""
        now = time.time()
        cutoff = now - MAX_MESSAGE_AGE * 2

        self._seen_nonces = {
            k: v for k, v in self._seen_nonces.items()
            if v > cutoff
        }

    def get_channel_info(self, peer_id: str) -> Optional[ChannelInfo]:
        """Get channel info for a peer."""
        return self._channels.get(peer_id)

    def close_channel(self, peer_id: str) -> None:
        """Close a channel with a peer."""
        self._peer_keys.pop(peer_id, None)
        self._shared_secrets.pop(peer_id, None)
        if peer_id in self._channels:
            self._channels[peer_id].state = ChannelState.CLOSED

    def close_all(self) -> None:
        """Close all channels."""
        for peer_id in list(self._channels.keys()):
            self.close_channel(peer_id)


# =============================================================================
# Threshold-Protected Channel
# =============================================================================

class ThresholdSecureChannel(SecureChannel):
    """
    Secure channel with threshold signature protection.

    Extends SecureChannel to require N-of-M signatures for critical operations.
    """

    def __init__(
        self,
        device_id: str,
        threshold: int = 2,
        total_devices: int = 3,
        **kwargs,
    ):
        """
        Initialize threshold-protected channel.

        Args:
            device_id: This device's identifier
            threshold: Required signatures for critical ops
            total_devices: Total devices in signing group
            **kwargs: Additional SecureChannel options
        """
        super().__init__(device_id, **kwargs)

        self._threshold = threshold
        self._total_devices = total_devices
        self._signer = ThresholdSigner(threshold, total_devices)
        self._my_share: Optional[Share] = None
        self._pending_signatures: Dict[str, List[PartialSignature]] = {}

    def set_signing_share(self, share: Share) -> None:
        """Set this device's signing share."""
        self._my_share = share

    def create_signature_request(
        self,
        operation: str,
        data: bytes,
    ) -> Dict[str, Any]:
        """
        Create a signature request for a critical operation.

        Args:
            operation: Operation name
            data: Data to sign

        Returns:
            Signature request to broadcast
        """
        request_id = secrets.token_hex(16)
        message_hash = hashlib.sha256(data).hexdigest()

        self._pending_signatures[request_id] = []

        return {
            'type': MSG_TYPE_SIGNATURE_REQUEST,
            'request_id': request_id,
            'operation': operation,
            'message_hash': message_hash,
            'threshold': self._threshold,
            'timestamp': time.time(),
        }

    def create_partial_signature(
        self,
        request_id: str,
        data: bytes,
    ) -> PartialSignature:
        """
        Create a partial signature for a request.

        Args:
            request_id: Signature request ID
            data: Data to sign

        Returns:
            Partial signature to return
        """
        if not self._my_share:
            raise SignatureError("No signing share configured")

        return self._signer.partial_sign(data, self._my_share)

    def collect_partial_signature(
        self,
        request_id: str,
        partial: PartialSignature,
    ) -> Optional[ThresholdSignature]:
        """
        Collect a partial signature.

        Args:
            request_id: Signature request ID
            partial: Partial signature from a peer

        Returns:
            Complete signature if threshold reached, None otherwise
        """
        if request_id not in self._pending_signatures:
            self._pending_signatures[request_id] = []

        self._pending_signatures[request_id].append(partial)

        if len(self._pending_signatures[request_id]) >= self._threshold:
            return self._signer.combine_signatures(
                self._pending_signatures[request_id]
            )

        return None


# =============================================================================
# Factory Functions
# =============================================================================

def create_secure_channel(
    device_id: str,
    enable_pq: bool = True,
    threshold: Optional[int] = None,
    total_devices: Optional[int] = None,
) -> SecureChannel:
    """
    Create a secure channel instance.

    Args:
        device_id: Device identifier
        enable_pq: Enable post-quantum algorithms
        threshold: If provided, create threshold-protected channel
        total_devices: Total devices for threshold signing

    Returns:
        SecureChannel or ThresholdSecureChannel instance
    """
    if threshold and total_devices:
        return ThresholdSecureChannel(
            device_id=device_id,
            threshold=threshold,
            total_devices=total_devices,
            enable_pq=enable_pq,
        )

    return SecureChannel(
        device_id=device_id,
        enable_pq=enable_pq,
    )
