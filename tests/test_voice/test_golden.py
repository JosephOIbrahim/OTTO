"""
Golden tests for voice system.

These are the acceptance tests. If these pass, voice is working.
"""
import pytest
from otto.voice import (
    get_register,
    detect_register,
    get_inference_params,
    adapt_response,
    get_voice_prompt,
    Register,
)


class TestTeenScenario:
    """
    THE acceptance test.

    User: "bro... is this a low key assistant?"
    OTTO should NOT respond like a robot.
    """

    def test_register_detection(self):
        """Should detect casual."""
        register = get_register("bro... is this a low key assistant?")
        assert register == Register.CASUAL

    def test_inference_params(self):
        """Should have appropriate temperature."""
        register = get_register("bro... is this a low key assistant?")
        params = get_inference_params("focused", register)

        # Not too robotic
        assert params.temperature >= 0.3
        # Not too chaotic
        assert params.temperature <= 0.7
        # Keep it short
        assert params.max_tokens <= 300

    def test_voice_prompt(self):
        """Should include casual instructions."""
        register = get_register("bro... is this a low key assistant?")
        prompt = get_voice_prompt(register)

        assert "casual" in prompt.lower()

    def test_robot_response_rejected(self):
        """Robot responses should be cleaned up."""
        robot_responses = [
            "I am OTTO, a cognitive support system designed to help you.",
            "As an AI assistant, I'm here to help with your tasks.",
            "Great question! I'm designed to provide cognitive support.",
        ]

        for robot in robot_responses:
            adapted = adapt_response(robot, Register.CASUAL)

            assert "I am OTTO" not in adapted
            assert "As an AI" not in adapted
            assert "cognitive support system" not in adapted
            assert "designed to" not in adapted
            assert "Great question" not in adapted


class TestFrustratedUser:
    """
    User: "NOTHING IS WORKING"
    OTTO should be supportive, not match chaos.
    """

    def test_register_detection(self):
        register = get_register("NOTHING IS WORKING")
        assert register == Register.VENTING

    def test_inference_params(self):
        params = get_inference_params("frustrated", Register.VENTING)

        # Steady, not chaotic
        assert params.temperature <= 0.5
        # Short
        assert params.max_tokens <= 200


class TestFlowState:
    """
    User: "next"
    OTTO should be minimal.
    """

    def test_register_detection(self):
        register = get_register("next")
        assert register == Register.TERSE

    def test_inference_params(self):
        params = get_inference_params("hyperfocused", Register.TERSE)

        # Minimal
        assert params.temperature <= 0.3
        assert params.max_tokens <= 150

    def test_response_truncation(self):
        verbose = "Here's the next step. You'll want to check the config. Then restart. After that, verify the logs."
        adapted = adapt_response(verbose, Register.TERSE)

        # Should be just first sentence
        assert adapted.count('.') <= 1


class TestExpertParamsIntegration:
    """Test that experts properly constrain inference params."""

    def test_validator_has_low_temp(self):
        params = get_inference_params("frustrated", Register.NEUTRAL, "Validator")
        assert params.temperature <= 0.4
        assert params.max_tokens <= 200

    def test_socratic_has_higher_temp(self):
        params = get_inference_params("exploring", Register.NEUTRAL, "Socratic")
        assert params.temperature >= 0.6

    def test_direct_is_minimal(self):
        params = get_inference_params("focused", Register.TERSE, "Direct")
        assert params.temperature <= 0.3
        assert params.max_tokens <= 150


class TestFullPipeline:
    """End-to-end integration test."""

    def test_casual_pipeline(self):
        message = "yo can u help me with this thing"

        # Detect
        register, signals = detect_register(message)
        assert register == Register.CASUAL
        assert signals.casual_markers >= 2

        # Params
        params = get_inference_params("focused", register, "Direct")
        assert 0.1 <= params.temperature <= 0.5

        # Prompt
        prompt = get_voice_prompt(register, "Direct")
        assert "casual" in prompt.lower()

        # Adapt
        response = "I'd be happy to help you with that! Let me explain."
        adapted = adapt_response(response, register)
        assert "happy to help" not in adapted

    def test_formal_pipeline(self):
        message = "Could you please assist me with implementing the authentication module?"

        register, signals = detect_register(message)
        assert register == Register.FORMAL

        params = get_inference_params("focused", register)
        # Formal is slightly cooler
        assert params.temperature <= 0.5

        prompt = get_voice_prompt(register)
        assert "formal" in prompt.lower() or "professional" in prompt.lower()


class TestDeterminism:
    """Voice system must be deterministic."""

    def test_full_pipeline_deterministic(self):
        message = "bro can you help me"

        results = []
        for _ in range(100):
            register, signals = detect_register(message)
            params = get_inference_params("focused", register)
            prompt = get_voice_prompt(register)

            results.append((
                register.value,
                signals.casual_markers,
                params.temperature,
                len(prompt),
            ))

        # All results should be identical
        assert all(r == results[0] for r in results)

    def test_adapter_deterministic_across_registers(self):
        response = "I understand you're frustrated. Here's what to do."

        for register in Register:
            results = [adapt_response(response, register) for _ in range(50)]
            assert all(r == results[0] for r in results), f"Non-deterministic for {register}"
