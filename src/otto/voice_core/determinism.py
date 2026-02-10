"""
[He2025]-inspired batch-invariance for Voice Processing.

Fixed seeds and deterministic constants ensuring reproducible voice processing.

Reference: https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/

Key principles:
1. Fixed seeds for all randomness
2. Fixed tile sizes for batching
3. Consistent ordering of operations
4. No dynamic algorithm switching
"""

from typing import Final
import hashlib
import random


# === Fixed Seeds (per [He2025]: "Control every source of randomness") ===

WHATSAPP_VOICE_SEED: Final[int] = 0xDEADBEEF
"""Seed for WhatsApp voice processing pipeline."""

TTS_VOICE_SEED: Final[int] = 0xFEEDFACE
"""Seed for text-to-speech operations."""

STT_NORMALIZATION_SEED: Final[int] = 0xCAFED00D
"""Seed for speech-to-text text normalization."""

COGNITIVE_TILE_SIZE: Final[int] = 32
"""Fixed tile size for batch-invariant processing."""

HASH_ALGORITHM: Final[str] = "sha256"
"""Fixed hash algorithm for checksums."""


# === Text Expansion Constants (deterministic ordering) ===

ABBREVIATION_EXPANSIONS: Final[dict[str, str]] = {
    # Common abbreviations - sorted for deterministic iteration
    "API": "A P I",
    "CEO": "C E O",
    "ADHD": "A D H D",
    "AI": "A I",
    "CPU": "C P U",
    "GPU": "G P U",
    "HTML": "H T M L",
    "HTTP": "H T T P",
    "ID": "I D",
    "JSON": "Jason",
    "LLM": "L L M",
    "ML": "M L",
    "NLP": "N L P",
    "OK": "okay",
    "OTTO": "Otto",
    "PDF": "P D F",
    "RAM": "ram",
    "SDK": "S D K",
    "SQL": "sequel",
    "TTS": "T T S",
    "UI": "U I",
    "URL": "U R L",
    "USD": "U S D",
    "USB": "U S B",
    "VFX": "V F X",
    "vs": "versus",
    "w/": "with",
    "w/o": "without",
    "e.g.": "for example",
    "i.e.": "that is",
    "etc.": "et cetera",
}

# Number words for speakable conversion
NUMBER_WORDS: Final[dict[int, str]] = {
    0: "zero", 1: "one", 2: "two", 3: "three", 4: "four",
    5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine",
    10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen",
    14: "fourteen", 15: "fifteen", 16: "sixteen", 17: "seventeen",
    18: "eighteen", 19: "nineteen", 20: "twenty",
}

TENS_WORDS: Final[dict[int, str]] = {
    2: "twenty", 3: "thirty", 4: "forty", 5: "fifty",
    6: "sixty", 7: "seventy", 8: "eighty", 9: "ninety",
}


class DeterministicRNG:
    """
    Seeded random number generator for reproducible operations.

    Per [He2025]: "Control every source of randomness with explicit seeds."
    """

    def __init__(self, seed: int = WHATSAPP_VOICE_SEED):
        """Initialize with explicit seed."""
        self._rng = random.Random(seed)
        self._seed = seed

    @property
    def seed(self) -> int:
        """Return the seed used for this RNG."""
        return self._seed

    def random(self) -> float:
        """Return random float in [0.0, 1.0)."""
        return self._rng.random()

    def randint(self, a: int, b: int) -> int:
        """Return random integer N such that a <= N <= b."""
        return self._rng.randint(a, b)

    def choice(self, seq: list) -> any:
        """Return random element from non-empty sequence."""
        return self._rng.choice(seq)

    def shuffle(self, seq: list) -> None:
        """Shuffle list in place deterministically."""
        self._rng.shuffle(seq)

    def reset(self) -> None:
        """Reset RNG to initial state."""
        self._rng = random.Random(self._seed)


def compute_checksum(data: bytes | str) -> str:
    """
    Compute deterministic checksum for data.

    Args:
        data: Bytes or string to hash

    Returns:
        Hex-encoded hash string
    """
    if isinstance(data, str):
        data = data.encode('utf-8')
    return hashlib.new(HASH_ALGORITHM, data).hexdigest()


def verify_determinism(func: callable, inputs: list, n_trials: int = 100) -> tuple[bool, set[str]]:
    """
    Verify a function produces deterministic output.

    Per [He2025]: Run N trials, all outputs must be identical.

    Args:
        func: Function to test
        inputs: List of input arguments
        n_trials: Number of trials to run

    Returns:
        Tuple of (is_deterministic, set of output hashes)
    """
    hashes = set()
    for _ in range(n_trials):
        result = func(*inputs)
        result_hash = compute_checksum(str(result))
        hashes.add(result_hash)

    return len(hashes) == 1, hashes


def kahan_sum(values: list[float]) -> float:
    """
    Kahan summation for batch-invariant floating point accumulation.

    Per [He2025]: Use compensated summation to avoid order-dependent
    floating point errors.

    Args:
        values: List of floats to sum

    Returns:
        Sum with reduced floating point error
    """
    values = sorted(values)  # Deterministic order
    total = 0.0
    compensation = 0.0

    for value in values:
        y = value - compensation
        t = total + y
        compensation = (t - total) - y
        total = t

    return total


def batch_invariant_process(items: list, processor: callable, tile_size: int = COGNITIVE_TILE_SIZE) -> list:
    """
    Process items in fixed-size tiles for batch invariance.

    Per [He2025]: "Fixed tile sizes ensure reproducible reduction order."

    Args:
        items: Items to process
        processor: Function to apply to each item
        tile_size: Fixed tile size (default: COGNITIVE_TILE_SIZE)

    Returns:
        Processed items in deterministic order
    """
    results = []
    for i in range(0, len(items), tile_size):
        tile = items[i:i + tile_size]
        tile_results = [processor(item) for item in tile]
        results.extend(tile_results)
    return results
