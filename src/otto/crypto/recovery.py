"""
Recovery Key Generation
=======================

Generate and validate recovery keys for password-less decryption.

ThinkingMachines [He2025] Compliance:
- FIXED entropy: 256 bits
- FIXED format: 24 words (BIP39-compatible word count)
- DETERMINISTIC validation

Security Properties:
- 256-bit entropy provides 128-bit security level
- Human-readable word format for safe storage
- Checksum for typo detection

Usage:
    from otto.crypto import generate_recovery_key, validate_recovery_key

    # Generate recovery key (display once to user)
    recovery = generate_recovery_key()
    print("Save this recovery key:", recovery.words_string)

    # Later, validate and use
    if validate_recovery_key(user_input):
        key_bytes = recovery_key_to_bytes(user_input)
"""

import os
import hashlib
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# =============================================================================
# Constants (FIXED - ThinkingMachines compliant)
# =============================================================================

# Entropy size: 256 bits = 32 bytes
ENTROPY_SIZE = 32

# Word count: 24 words (256 bits + 8 checksum bits)
WORD_COUNT = 24

# Each word encodes 11 bits, 24 words = 264 bits (256 entropy + 8 checksum)
BITS_PER_WORD = 11

# BIP39-like word list (subset for OTTO - 2048 words)
# Using first 2048 words of standardized list
# Full list would be imported from a file in production
WORDLIST = [
    "abandon", "ability", "able", "about", "above", "absent", "absorb", "abstract",
    "absurd", "abuse", "access", "accident", "account", "accuse", "achieve", "acid",
    "acoustic", "acquire", "across", "act", "action", "actor", "actress", "actual",
    "adapt", "add", "addict", "address", "adjust", "admit", "adult", "advance",
    "advice", "aerobic", "affair", "afford", "afraid", "again", "age", "agent",
    "agree", "ahead", "aim", "air", "airport", "aisle", "alarm", "album",
    "alcohol", "alert", "alien", "all", "alley", "allow", "almost", "alone",
    "alpha", "already", "also", "alter", "always", "amateur", "amazing", "among",
    "amount", "amused", "analyst", "anchor", "ancient", "anger", "angle", "angry",
    "animal", "ankle", "announce", "annual", "another", "answer", "antenna", "antique",
    "anxiety", "any", "apart", "apology", "appear", "apple", "approve", "april",
    "arch", "arctic", "area", "arena", "argue", "arm", "armed", "armor",
    "army", "around", "arrange", "arrest", "arrive", "arrow", "art", "artefact",
    "artist", "artwork", "ask", "aspect", "assault", "asset", "assist", "assume",
    "asthma", "athlete", "atom", "attack", "attend", "attitude", "attract", "auction",
    "audit", "august", "aunt", "author", "auto", "autumn", "average", "avocado",
    "avoid", "awake", "aware", "away", "awesome", "awful", "awkward", "axis",
    # ... (truncated for brevity - full 2048 words in production)
    # Adding more common words to reach minimum for demonstration
    "baby", "bachelor", "bacon", "badge", "bag", "balance", "balcony", "ball",
    "bamboo", "banana", "banner", "bar", "barely", "bargain", "barrel", "base",
    "basic", "basket", "battle", "beach", "bean", "beauty", "because", "become",
    "beef", "before", "begin", "behave", "behind", "believe", "below", "belt",
    "bench", "benefit", "best", "betray", "better", "between", "beyond", "bicycle",
    "bid", "bike", "bind", "biology", "bird", "birth", "bitter", "black",
    "blade", "blame", "blanket", "blast", "bleak", "bless", "blind", "blood",
    "blossom", "blouse", "blue", "blur", "blush", "board", "boat", "body",
    "boil", "bomb", "bone", "bonus", "book", "boost", "border", "boring",
    "borrow", "boss", "bottom", "bounce", "box", "boy", "bracket", "brain",
    "brand", "brass", "brave", "bread", "breeze", "brick", "bridge", "brief",
    "bright", "bring", "brisk", "broccoli", "broken", "bronze", "broom", "brother",
    "brown", "brush", "bubble", "buddy", "budget", "buffalo", "build", "bulb",
    "bulk", "bullet", "bundle", "bunker", "burden", "burger", "burst", "bus",
    "business", "busy", "butter", "buyer", "buzz", "cabbage", "cabin", "cable",
    "cactus", "cage", "cake", "call", "calm", "camera", "camp", "can",
    "canal", "cancel", "candy", "cannon", "canoe", "canvas", "canyon", "capable",
    "capital", "captain", "car", "carbon", "card", "cargo", "carpet", "carry",
    "cart", "case", "cash", "casino", "castle", "casual", "cat", "catalog",
    "catch", "category", "cattle", "caught", "cause", "caution", "cave", "ceiling",
]

# Extend wordlist to 2048 entries (for demonstration)
while len(WORDLIST) < 2048:
    WORDLIST.append(f"word{len(WORDLIST)}")

WORDLIST_SIZE = len(WORDLIST)  # Should be 2048


# =============================================================================
# Exceptions
# =============================================================================

class RecoveryKeyError(Exception):
    """Raised when recovery key operations fail."""
    pass


class InvalidRecoveryKey(RecoveryKeyError):
    """Raised when recovery key validation fails."""
    pass


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class RecoveryKey:
    """
    Recovery key container.

    Attributes:
        words: List of 24 recovery words
        entropy: Original entropy bytes
        checksum: Checksum byte
    """
    words: list[str]
    entropy: bytes
    checksum: int

    @property
    def words_string(self) -> str:
        """Get words as space-separated string."""
        return " ".join(self.words)

    @property
    def words_grouped(self) -> str:
        """Get words grouped by 6 for display."""
        lines = []
        for i in range(0, len(self.words), 6):
            group = self.words[i:i+6]
            numbered = [f"{i+j+1}. {w}" for j, w in enumerate(group)]
            lines.append("  ".join(numbered))
        return "\n".join(lines)

    def to_bytes(self) -> bytes:
        """Convert recovery key back to entropy bytes."""
        return self.entropy


# =============================================================================
# Core Functions
# =============================================================================

def generate_recovery_key() -> RecoveryKey:
    """
    Generate a new recovery key.

    Returns:
        RecoveryKey with 24 words

    ThinkingMachines Compliance:
    - FIXED entropy: 256 bits
    - FIXED word count: 24
    - DETERMINISTIC encoding
    """
    # Generate entropy
    entropy = os.urandom(ENTROPY_SIZE)

    # Calculate checksum (first byte of SHA-256)
    checksum_full = hashlib.sha256(entropy).digest()
    checksum_byte = checksum_full[0]

    # Convert to words
    words = _entropy_to_words(entropy, checksum_byte)

    logger.info("Recovery key generated")

    return RecoveryKey(
        words=words,
        entropy=entropy,
        checksum=checksum_byte,
    )


def validate_recovery_key(words_input: str) -> bool:
    """
    Validate recovery key format and checksum.

    Args:
        words_input: Space-separated recovery words

    Returns:
        True if valid

    ThinkingMachines: DETERMINISTIC validation.
    """
    try:
        words = _parse_words(words_input)

        if len(words) != WORD_COUNT:
            return False

        # Check all words are in wordlist
        for word in words:
            if word.lower() not in WORDLIST:
                return False

        # Reconstruct entropy and verify checksum
        entropy, checksum = _words_to_entropy(words)

        expected_checksum = hashlib.sha256(entropy).digest()[0]

        return checksum == expected_checksum

    except Exception:
        return False


def recovery_key_to_bytes(words_input: str) -> bytes:
    """
    Convert recovery key words to entropy bytes.

    Args:
        words_input: Space-separated recovery words

    Returns:
        32-byte entropy

    Raises:
        InvalidRecoveryKey: If validation fails
    """
    if not validate_recovery_key(words_input):
        raise InvalidRecoveryKey("Invalid recovery key")

    words = _parse_words(words_input)
    entropy, _ = _words_to_entropy(words)

    return entropy


def recovery_key_from_entropy(entropy: bytes) -> RecoveryKey:
    """
    Create recovery key from existing entropy.

    Useful for deterministic key recovery from seed.

    Args:
        entropy: 32-byte entropy

    Returns:
        RecoveryKey

    Raises:
        RecoveryKeyError: If entropy size invalid
    """
    if len(entropy) != ENTROPY_SIZE:
        raise RecoveryKeyError(f"Entropy must be {ENTROPY_SIZE} bytes")

    checksum_byte = hashlib.sha256(entropy).digest()[0]
    words = _entropy_to_words(entropy, checksum_byte)

    return RecoveryKey(
        words=words,
        entropy=entropy,
        checksum=checksum_byte,
    )


# =============================================================================
# Internal Helpers
# =============================================================================

def _parse_words(words_input: str) -> list[str]:
    """Parse and normalize word input."""
    # Handle various separators
    words_input = words_input.lower().strip()
    words_input = words_input.replace(",", " ").replace("\n", " ")

    # Split and filter empty
    words = [w.strip() for w in words_input.split() if w.strip()]

    return words


def _entropy_to_words(entropy: bytes, checksum: int) -> list[str]:
    """
    Convert entropy bytes to words.

    Encoding:
    1. Concatenate entropy (256 bits) + checksum (8 bits) = 264 bits
    2. Split into 24 groups of 11 bits
    3. Each 11-bit value indexes into 2048-word list
    """
    # Convert entropy to integer
    entropy_int = int.from_bytes(entropy, "big")

    # Shift left 8 bits and add checksum
    combined = (entropy_int << 8) | checksum

    # Extract 24 words (11 bits each)
    words = []
    for i in range(WORD_COUNT):
        # Extract 11 bits from position
        shift = (WORD_COUNT - 1 - i) * BITS_PER_WORD
        index = (combined >> shift) & 0x7FF  # 0x7FF = 2047 (11 bits)
        words.append(WORDLIST[index])

    return words


def _words_to_entropy(words: list[str]) -> tuple[bytes, int]:
    """
    Convert words back to entropy.

    Returns:
        Tuple of (entropy_bytes, checksum_byte)
    """
    # Convert words to indices
    combined = 0
    for word in words:
        index = WORDLIST.index(word.lower())
        combined = (combined << BITS_PER_WORD) | index

    # Extract checksum (last 8 bits)
    checksum = combined & 0xFF

    # Extract entropy (remaining 256 bits)
    entropy_int = combined >> 8
    entropy = entropy_int.to_bytes(ENTROPY_SIZE, "big")

    return entropy, checksum


def format_recovery_key_for_display(recovery_key: RecoveryKey) -> str:
    """
    Format recovery key for user display.

    Args:
        recovery_key: RecoveryKey to format

    Returns:
        Formatted string for display
    """
    return f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                           RECOVERY KEY                                        ║
║                                                                               ║
║  SAVE THIS KEY! You will need it if you forget your password.                ║
║  Store it safely - anyone with this key can decrypt your data.               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
{_format_words_box(recovery_key.words)}║                                                                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""


def _format_words_box(words: list[str]) -> str:
    """Format words in a box for display."""
    lines = []
    for i in range(0, len(words), 4):
        group = words[i:i+4]
        formatted = "  ".join(f"{i+j+1:2}. {w:<12}" for j, w in enumerate(group))
        lines.append(f"║  {formatted:<75}║\n")
    return "".join(lines)


__all__ = [
    "RecoveryKey",
    "RecoveryKeyError",
    "InvalidRecoveryKey",
    "generate_recovery_key",
    "validate_recovery_key",
    "recovery_key_to_bytes",
    "recovery_key_from_entropy",
    "format_recovery_key_for_display",
    "WORD_COUNT",
    "ENTROPY_SIZE",
]
