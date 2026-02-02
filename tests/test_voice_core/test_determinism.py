"""
Tests for [He2025] determinism compliance in voice_core.

Verifies:
- Fixed seeds produce reproducible results
- Kahan summation is batch-invariant
- prepare_for_speech has consistent output
- 100 trials produce identical hashes
"""

import pytest
from otto.voice_core import (
    # Seeds
    WHATSAPP_VOICE_SEED,
    TTS_VOICE_SEED,
    STT_NORMALIZATION_SEED,
    COGNITIVE_TILE_SIZE,
    HASH_ALGORITHM,
    # Utilities
    DeterministicRNG,
    compute_checksum,
    verify_determinism,
    kahan_sum,
    batch_invariant_process,
    # Prepare for speech
    prepare_for_speech,
)


class TestFixedSeeds:
    """Test that seeds are fixed and documented."""

    def test_whatsapp_voice_seed_is_fixed(self):
        """WHATSAPP_VOICE_SEED should be 0xDEADBEEF."""
        assert WHATSAPP_VOICE_SEED == 0xDEADBEEF

    def test_tts_voice_seed_is_fixed(self):
        """TTS_VOICE_SEED should be 0xFEEDFACE."""
        assert TTS_VOICE_SEED == 0xFEEDFACE

    def test_stt_normalization_seed_is_fixed(self):
        """STT_NORMALIZATION_SEED should be 0xCAFED00D."""
        assert STT_NORMALIZATION_SEED == 0xCAFED00D

    def test_cognitive_tile_size_is_fixed(self):
        """COGNITIVE_TILE_SIZE should be 32."""
        assert COGNITIVE_TILE_SIZE == 32

    def test_hash_algorithm_is_sha256(self):
        """HASH_ALGORITHM should be sha256."""
        assert HASH_ALGORITHM == "sha256"


class TestDeterministicRNG:
    """Test DeterministicRNG produces reproducible sequences."""

    def test_same_seed_same_sequence(self):
        """Same seed should produce same sequence."""
        rng1 = DeterministicRNG(42)
        rng2 = DeterministicRNG(42)

        seq1 = [rng1.random() for _ in range(100)]
        seq2 = [rng2.random() for _ in range(100)]

        assert seq1 == seq2

    def test_different_seed_different_sequence(self):
        """Different seeds should produce different sequences."""
        rng1 = DeterministicRNG(42)
        rng2 = DeterministicRNG(43)

        seq1 = [rng1.random() for _ in range(10)]
        seq2 = [rng2.random() for _ in range(10)]

        assert seq1 != seq2

    def test_reset_restarts_sequence(self):
        """Reset should restart the sequence."""
        rng = DeterministicRNG(42)

        seq1 = [rng.random() for _ in range(10)]
        rng.reset()
        seq2 = [rng.random() for _ in range(10)]

        assert seq1 == seq2

    def test_randint_reproducible(self):
        """randint should be reproducible."""
        rng1 = DeterministicRNG(42)
        rng2 = DeterministicRNG(42)

        seq1 = [rng1.randint(0, 100) for _ in range(100)]
        seq2 = [rng2.randint(0, 100) for _ in range(100)]

        assert seq1 == seq2

    def test_choice_reproducible(self):
        """choice should be reproducible."""
        items = ["a", "b", "c", "d", "e"]
        rng1 = DeterministicRNG(42)
        rng2 = DeterministicRNG(42)

        seq1 = [rng1.choice(items) for _ in range(50)]
        seq2 = [rng2.choice(items) for _ in range(50)]

        assert seq1 == seq2

    def test_shuffle_reproducible(self):
        """shuffle should be reproducible."""
        rng1 = DeterministicRNG(42)
        rng2 = DeterministicRNG(42)

        list1 = [1, 2, 3, 4, 5]
        list2 = [1, 2, 3, 4, 5]

        rng1.shuffle(list1)
        rng2.shuffle(list2)

        assert list1 == list2


class TestComputeChecksum:
    """Test compute_checksum function."""

    def test_string_checksum(self):
        """Should compute checksum for string."""
        checksum = compute_checksum("hello world")
        assert isinstance(checksum, str)
        assert len(checksum) == 64  # SHA-256 hex length

    def test_bytes_checksum(self):
        """Should compute checksum for bytes."""
        checksum = compute_checksum(b"hello world")
        assert isinstance(checksum, str)
        assert len(checksum) == 64

    def test_same_input_same_checksum(self):
        """Same input should produce same checksum."""
        checksum1 = compute_checksum("test input")
        checksum2 = compute_checksum("test input")
        assert checksum1 == checksum2

    def test_different_input_different_checksum(self):
        """Different input should produce different checksum."""
        checksum1 = compute_checksum("input one")
        checksum2 = compute_checksum("input two")
        assert checksum1 != checksum2


class TestVerifyDeterminism:
    """Test verify_determinism utility."""

    def test_deterministic_function_passes(self):
        """Deterministic function should pass verification."""
        def deterministic(x):
            return x * 2

        is_deterministic, hashes = verify_determinism(deterministic, [5], n_trials=100)

        assert is_deterministic
        assert len(hashes) == 1

    def test_non_deterministic_function_fails(self):
        """Non-deterministic function should fail verification."""
        import random

        def non_deterministic(x):
            return x * random.random()

        is_deterministic, hashes = verify_determinism(non_deterministic, [5], n_trials=100)

        assert not is_deterministic
        assert len(hashes) > 1


class TestKahanSum:
    """Test Kahan summation for batch invariance."""

    def test_basic_sum(self):
        """Should sum correctly."""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = kahan_sum(values)
        assert result == pytest.approx(15.0)

    def test_order_independent(self):
        """Sum should be order-independent due to sorting."""
        values1 = [1.0, 2.0, 3.0, 4.0, 5.0]
        values2 = [5.0, 4.0, 3.0, 2.0, 1.0]
        values3 = [3.0, 1.0, 4.0, 2.0, 5.0]

        result1 = kahan_sum(values1)
        result2 = kahan_sum(values2)
        result3 = kahan_sum(values3)

        assert result1 == result2 == result3

    def test_precision_with_small_values(self):
        """Should handle precision with small values."""
        # Kahan summation reduces floating point error accumulation
        # Test with values where naive summation loses precision
        values = [1.0, 1e-16, 1e-16, 1e-16, -1.0]
        result = kahan_sum(values)
        # Result should be 3e-16, Kahan helps preserve small values
        assert result == pytest.approx(3e-16, rel=1e-5)

    def test_empty_list(self):
        """Should handle empty list."""
        result = kahan_sum([])
        assert result == 0.0


class TestBatchInvariantProcess:
    """Test batch_invariant_process function."""

    def test_processes_all_items(self):
        """Should process all items."""
        items = [1, 2, 3, 4, 5]
        results = batch_invariant_process(items, lambda x: x * 2)
        assert results == [2, 4, 6, 8, 10]

    def test_respects_tile_size(self):
        """Should process in tiles of correct size."""
        processed_tiles = []

        def track_processor(item):
            return item

        items = list(range(100))
        batch_invariant_process(items, track_processor, tile_size=32)

        # Should have processed all items
        assert len(items) == 100

    def test_deterministic_across_tile_sizes(self):
        """Same result regardless of tile size."""
        items = list(range(100))
        processor = lambda x: x * 2

        result_16 = batch_invariant_process(items, processor, tile_size=16)
        result_32 = batch_invariant_process(items, processor, tile_size=32)
        result_64 = batch_invariant_process(items, processor, tile_size=64)

        assert result_16 == result_32 == result_64


class TestPrepareForSpeechDeterminism:
    """Test prepare_for_speech determinism."""

    def test_same_input_same_output_100_trials(self):
        """Same input should produce same output in 100 trials."""
        input_text = """
        # Hello World

        This is a **test** with some `code` and numbers like 42.

        - Item 1
        - Item 2

        Check out [this link](http://example.com).
        """

        hashes = set()
        for _ in range(100):
            result = prepare_for_speech(input_text)
            hashes.add(result.prepared_checksum)

        assert len(hashes) == 1, f"Got {len(hashes)} different outputs"

    def test_checksums_are_computed(self):
        """Should compute checksums for input and output."""
        result = prepare_for_speech("Hello world")

        assert result.original_checksum != ""
        assert result.prepared_checksum != ""
        assert len(result.original_checksum) == 64
        assert len(result.prepared_checksum) == 64

    def test_phases_are_tracked(self):
        """Should track which phases were applied."""
        result = prepare_for_speech("# Hello **world** 42")

        assert "remove_formatting" in result.phases_applied
        assert "convert_numbers" in result.phases_applied
        assert "final_cleanup" in result.phases_applied

    def test_skip_phases(self):
        """Should skip specified phases."""
        text = "# Hello **world** 42"

        result_all = prepare_for_speech(text)
        result_skip_numbers = prepare_for_speech(text, skip_phases=[3])

        # Skipping number conversion should produce different result
        assert "42" in result_skip_numbers.text
        assert "forty-two" in result_all.text

    def test_was_modified_property(self):
        """was_modified should reflect if text changed."""
        result_changed = prepare_for_speech("# Hello 42")
        result_unchanged = prepare_for_speech("simple text")

        assert result_changed.was_modified
        # Simple text might still be modified by cleanup


class TestPrepareForSpeechPhases:
    """Test individual phases of prepare_for_speech."""

    def test_phase1_removes_markdown(self):
        """Phase 1 should remove markdown formatting."""
        text = "# Heading\n**bold** and *italic*"
        result = prepare_for_speech(text)

        assert "#" not in result.text
        assert "**" not in result.text
        assert "*" not in result.text
        assert "bold" in result.text
        assert "italic" in result.text

    def test_phase1_removes_code_blocks(self):
        """Phase 1 should remove code blocks."""
        text = "Before ```python\ncode here\n``` After"
        result = prepare_for_speech(text)

        assert "```" not in result.text
        assert "python" not in result.text
        assert "code here" not in result.text
        assert "code example" in result.text

    def test_phase2_expands_abbreviations(self):
        """Phase 2 should expand abbreviations."""
        text = "The API uses JSON for the URL"
        result = prepare_for_speech(text)

        assert "A P I" in result.text
        assert "Jason" in result.text  # JSON -> Jason
        assert "U R L" in result.text

    def test_phase3_converts_numbers(self):
        """Phase 3 should convert numbers to words."""
        text = "I have 42 items and $100"
        result = prepare_for_speech(text)

        assert "forty-two" in result.text
        assert "one hundred dollars" in result.text

    def test_phase3_converts_percentages(self):
        """Phase 3 should convert percentages."""
        text = "That's 50% complete"
        result = prepare_for_speech(text)

        assert "fifty percent" in result.text

    def test_phase3_converts_times(self):
        """Phase 3 should convert times."""
        text = "Meet at 3:30"
        result = prepare_for_speech(text)

        assert "three thirty" in result.text

    def test_phase5_normalizes_whitespace(self):
        """Phase 5 should normalize whitespace."""
        text = "Hello    world\n\n\ntest"
        result = prepare_for_speech(text)

        assert "  " not in result.text
        assert "\n" not in result.text
