"""Field-level AES-256-GCM encryption for sensitive commitment data.

Key derivation: random 32-byte key, hex-encoded in key file.
Key storage: ~/.otto/otto.key (chmod 600 on Unix, best-effort on Windows).
If no key exists, generate one automatically on first use.

Encrypted fields: raw_message, commitment_text, who_to, source_chat, sender_phone
Unencrypted fields: id, status, deadline, follow_up_count, timestamps (needed for queries)
"""

from __future__ import annotations

import base64
import os
import stat
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Fields that get encrypted at rest.  Everything else stays plaintext
# so SQLite can still filter/sort on status, deadline, timestamps, etc.
ENCRYPTED_FIELDS = frozenset(
    {"raw_message", "commitment_text", "who_to", "source_chat", "sender_phone"}
)


def load_or_create_key(key_path: str = "~/.otto/otto.key") -> bytes:
    """Load encryption key from file, or create one if it doesn't exist.

    Returns the raw 32-byte key.
    """
    expanded = Path(os.path.expanduser(key_path))
    if expanded.exists():
        hex_key = expanded.read_text(encoding="utf-8").strip()
        return bytes.fromhex(hex_key)

    # Generate new key
    key = AESGCM.generate_key(bit_length=256)
    expanded.parent.mkdir(parents=True, exist_ok=True)
    expanded.write_text(key.hex(), encoding="utf-8")

    # Best-effort permission restriction
    try:
        expanded.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600
    except OSError:
        pass  # Windows may not support Unix permissions

    return key


def encrypt_field(plaintext: str, key: bytes) -> str:
    """Encrypt a string field using AES-256-GCM.

    Returns base64-encoded: nonce (12 bytes) || ciphertext || tag (16 bytes).
    Each call produces different output (random nonce) -- this is correct.
    """
    if not plaintext:
        return ""
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_field(token: str, key: bytes) -> str:
    """Decrypt a base64-encoded AES-256-GCM token back to plaintext string."""
    if not token:
        return ""
    raw = base64.b64decode(token)
    nonce = raw[:12]
    ciphertext = raw[12:]
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")
