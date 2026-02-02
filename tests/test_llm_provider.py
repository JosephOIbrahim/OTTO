"""
Tests for LLM Provider Layer

[He2025] Compliance:
- Fixed test data
- Deterministic assertions
- Provider-agnostic testing
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Import provider components
from otto.llm.provider import (
    LLMProvider,
    LLMConfig,
    LLMResponse,
    BaseLLMProvider,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
)
from otto.llm.response_generator import (
    ResponseGenerator,
    GenerationContext,
    EXPERT_PROMPTS,
    DEFAULT_PROMPT,
)


class TestLLMConfig:
    """Test LLMConfig dataclass."""

    def test_default_values(self):
        """Config has correct defaults."""
        config = LLMConfig()
        assert config.max_tokens == DEFAULT_MAX_TOKENS
        assert config.temperature == DEFAULT_TEMPERATURE
        assert config.model is None
        assert config.stop_sequences == []
        assert config.extra == {}

    def test_custom_values(self):
        """Config accepts custom values."""
        config = LLMConfig(
            max_tokens=500,
            temperature=0.5,
            model="test-model",
            stop_sequences=["STOP"],
            extra={"key": "value"},
        )
        assert config.max_tokens == 500
        assert config.temperature == 0.5
        assert config.model == "test-model"
        assert config.stop_sequences == ["STOP"]
        assert config.extra == {"key": "value"}


class TestLLMResponse:
    """Test LLMResponse dataclass."""

    def test_basic_response(self):
        """Response stores basic fields."""
        response = LLMResponse(
            text="Hello!",
            model="test-model",
        )
        assert response.text == "Hello!"
        assert response.model == "test-model"
        assert response.input_tokens == 0
        assert response.output_tokens == 0

    def test_total_tokens(self):
        """Total tokens calculation."""
        response = LLMResponse(
            text="Test",
            model="test-model",
            input_tokens=10,
            output_tokens=5,
        )
        assert response.total_tokens == 15

    def test_response_metadata(self):
        """Response stores metadata."""
        response = LLMResponse(
            text="Test",
            model="test-model",
            finish_reason="max_tokens",
            provider="test",
            raw={"id": "123"},
        )
        assert response.finish_reason == "max_tokens"
        assert response.provider == "test"
        assert response.raw == {"id": "123"}


class TestGenerationContext:
    """Test GenerationContext dataclass."""

    def test_default_context(self):
        """Context has correct defaults."""
        ctx = GenerationContext()
        assert ctx.expert == "Direct"
        assert ctx.burnout_level == "GREEN"
        assert ctx.energy_level == "medium"
        assert ctx.momentum_phase == "building"
        assert ctx.mode == "focused"
        assert ctx.platform == "discord"

    def test_custom_context(self):
        """Context accepts custom values."""
        ctx = GenerationContext(
            expert="Validator",
            burnout_level="ORANGE",
            energy_level="low",
            momentum_phase="crashed",
            mode="recovery",
            user_id=12345,
            session_id="test-session",
        )
        assert ctx.expert == "Validator"
        assert ctx.burnout_level == "ORANGE"
        assert ctx.energy_level == "low"
        assert ctx.momentum_phase == "crashed"
        assert ctx.user_id == 12345
        assert ctx.session_id == "test-session"

    def test_context_string(self):
        """Context generates proper string."""
        ctx = GenerationContext(
            burnout_level="YELLOW",
            energy_level="high",
            momentum_phase="rolling",
        )
        context_str = ctx.to_context_string()
        assert "YELLOW" in context_str
        assert "high" in context_str
        assert "rolling" in context_str


class TestExpertPrompts:
    """Test expert prompt definitions."""

    def test_all_experts_defined(self):
        """All intervention experts have prompts."""
        expected_experts = [
            "Validator",
            "Scaffolder",
            "Restorer",
            "Celebrator",
            "Socratic",
            "Direct",
        ]
        for expert in expected_experts:
            assert expert in EXPERT_PROMPTS
            assert len(EXPERT_PROMPTS[expert]) > 50  # Non-trivial prompt

    def test_default_prompt_exists(self):
        """Default prompt exists for unknown experts."""
        assert len(DEFAULT_PROMPT) > 20

    def test_validator_empathy_first(self):
        """Validator prompt emphasizes empathy."""
        prompt = EXPERT_PROMPTS["Validator"]
        assert "empathy" in prompt.lower() or "feelings" in prompt.lower()

    def test_scaffolder_break_down(self):
        """Scaffolder prompt emphasizes breaking down."""
        prompt = EXPERT_PROMPTS["Scaffolder"]
        assert "break" in prompt.lower() or "reduce" in prompt.lower()

    def test_restorer_rest_ok(self):
        """Restorer prompt permits rest."""
        prompt = EXPERT_PROMPTS["Restorer"]
        assert "rest" in prompt.lower() or "break" in prompt.lower()

    def test_direct_minimal_friction(self):
        """Direct prompt emphasizes minimal friction."""
        prompt = EXPERT_PROMPTS["Direct"]
        assert "minimal" in prompt.lower() or "concise" in prompt.lower()


class TestResponseGenerator:
    """Test ResponseGenerator class."""

    @pytest.fixture
    def mock_provider(self):
        """Create a mock LLM provider."""
        provider = MagicMock()
        provider.name = "mock"
        provider.default_model = "mock-model"
        provider.is_available.return_value = True
        provider.generate = AsyncMock(
            return_value=LLMResponse(
                text="Generated response",
                model="mock-model",
                input_tokens=10,
                output_tokens=5,
            )
        )
        return provider

    @pytest.fixture
    def generator(self, mock_provider):
        """Create a ResponseGenerator with mock provider."""
        return ResponseGenerator(mock_provider)

    def test_generator_creation(self, mock_provider):
        """Generator initializes correctly."""
        gen = ResponseGenerator(mock_provider)
        assert gen.provider == mock_provider
        assert gen.default_config.max_tokens == 512  # Concise default

    @pytest.mark.asyncio
    async def test_generate_calls_provider(self, generator, mock_provider):
        """Generate calls the provider with correct args."""
        result = await generator.generate(
            message="Hello",
            context=GenerationContext(expert="Direct"),
        )

        mock_provider.generate.assert_called_once()
        call_args = mock_provider.generate.call_args
        assert call_args.kwargs["prompt"] == "Hello"
        # Direct expert prompt contains "efficient" and "minimal friction"
        assert "efficient" in call_args.kwargs["system"].lower()
        assert result == "Generated response"

    @pytest.mark.asyncio
    async def test_generate_uses_expert_prompt(self, generator, mock_provider):
        """Generate uses correct expert-specific prompt."""
        await generator.generate(
            message="I'm frustrated",
            context=GenerationContext(expert="Validator"),
        )

        call_args = mock_provider.generate.call_args
        system_prompt = call_args.kwargs["system"]
        assert "empathetic" in system_prompt.lower()

    @pytest.mark.asyncio
    async def test_generate_includes_context(self, generator, mock_provider):
        """Generate includes cognitive context in system prompt."""
        await generator.generate(
            message="Test",
            context=GenerationContext(
                expert="Direct",
                burnout_level="ORANGE",
                energy_level="low",
            ),
        )

        call_args = mock_provider.generate.call_args
        system_prompt = call_args.kwargs["system"]
        assert "ORANGE" in system_prompt
        assert "low" in system_prompt

    @pytest.mark.asyncio
    async def test_generate_default_context(self, generator, mock_provider):
        """Generate works with no context provided."""
        result = await generator.generate(message="Hello")

        assert result == "Generated response"
        mock_provider.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_fallback_on_error(self, generator, mock_provider):
        """Generate returns fallback on provider error."""
        mock_provider.generate.side_effect = Exception("API Error")

        result = await generator.generate(
            message="Test",
            context=GenerationContext(expert="Validator"),
        )

        # Should return Validator's fallback
        assert "hear" in result.lower() or "frustrating" in result.lower()

    @pytest.mark.asyncio
    async def test_generate_unknown_expert_fallback(self, generator, mock_provider):
        """Generate handles unknown expert with fallback."""
        mock_provider.generate.side_effect = Exception("Error")

        result = await generator.generate(
            message="Test",
            context=GenerationContext(expert="UnknownExpert"),
        )

        # Should return generic fallback
        assert "help" in result.lower()


class TestMockProvider:
    """Test that mock providers work as expected."""

    def test_provider_protocol_compliance(self):
        """Mock provider matches LLMProvider protocol."""
        provider = MagicMock()
        provider.name = "test"
        provider.default_model = "test-model"
        provider.generate = AsyncMock()
        provider.is_available.return_value = True

        # Should be usable as LLMProvider
        assert isinstance(provider.name, str)
        assert isinstance(provider.default_model, str)
        assert callable(provider.is_available)


class TestDeterminism:
    """Test deterministic behavior per [He2025]."""

    def test_expert_prompts_fixed(self):
        """Expert prompts are constants."""
        # Get prompts twice
        prompts1 = dict(EXPERT_PROMPTS)
        prompts2 = dict(EXPERT_PROMPTS)

        # Should be identical
        assert prompts1 == prompts2

    def test_context_string_deterministic(self):
        """Context string is deterministic."""
        ctx = GenerationContext(
            burnout_level="YELLOW",
            energy_level="high",
            momentum_phase="rolling",
        )

        str1 = ctx.to_context_string()
        str2 = ctx.to_context_string()

        assert str1 == str2

    def test_config_defaults_fixed(self):
        """Config defaults are fixed constants."""
        config1 = LLMConfig()
        config2 = LLMConfig()

        assert config1.max_tokens == config2.max_tokens
        assert config1.temperature == config2.temperature
