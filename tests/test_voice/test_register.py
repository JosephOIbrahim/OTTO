"""Tests for register detection."""
import pytest
from otto.voice.register import get_register, Register, detect_register


class TestCasualDetection:

    def test_bro(self):
        assert get_register("bro can u help") == Register.CASUAL

    def test_lol(self):
        assert get_register("lol this is broken") == Register.CASUAL

    def test_lowercase_short(self):
        assert get_register("yeah that works") == Register.CASUAL

    def test_informal_spelling(self):
        assert get_register("gonna try that thx") == Register.CASUAL

    def test_teen_question(self):
        """THE golden test case."""
        assert get_register("bro... is this a low key assistant?") == Register.CASUAL

    def test_multiple_casual_markers(self):
        assert get_register("yo dude lol") == Register.CASUAL


class TestTerseDetection:

    def test_single_word(self):
        assert get_register("next") == Register.TERSE

    def test_two_words(self):
        assert get_register("what next") == Register.TERSE

    def test_continue(self):
        assert get_register("continue") == Register.TERSE

    def test_ok(self):
        assert get_register("ok") == Register.TERSE


class TestFormalDetection:

    def test_please_assist(self):
        assert get_register("Could you please assist me with this task?") == Register.FORMAL

    def test_would_like(self):
        assert get_register("I would like to request your assistance.") == Register.FORMAL

    def test_regarding(self):
        assert get_register("Regarding the previous matter, I have a question.") == Register.FORMAL


class TestVentingDetection:

    def test_caps(self):
        assert get_register("WHY WONT THIS WORK") == Register.VENTING

    def test_exclamation(self):
        assert get_register("Nothing is working!!!") == Register.VENTING

    def test_profanity(self):
        assert get_register("fuck this is broken") == Register.VENTING

    def test_ugh(self):
        assert get_register("ugh I give up") == Register.VENTING

    def test_so_frustrated(self):
        assert get_register("I am so frustrated with this") == Register.VENTING


class TestNeutralDetection:

    def test_standard_question(self):
        assert get_register("Can you help me with this?") == Register.NEUTRAL

    def test_medium_length(self):
        assert get_register("I'm working on the authentication system.") == Register.NEUTRAL


class TestDeterminism:

    def test_same_input_same_output(self):
        """Register detection must be deterministic."""
        message = "bro can you help me with something"
        results = [get_register(message) for _ in range(100)]
        assert all(r == results[0] for r in results)

    def test_signals_deterministic(self):
        """Signals must be deterministic."""
        message = "yo lol what's up"
        results = [detect_register(message) for _ in range(100)]
        signals = [r[1].casual_markers for r in results]
        assert all(s == signals[0] for s in signals)

    def test_caps_ratio_deterministic(self):
        """Caps ratio calculation must be deterministic."""
        message = "HELP me WITH this"
        results = [detect_register(message)[1].caps_ratio for _ in range(100)]
        assert all(r == results[0] for r in results)
