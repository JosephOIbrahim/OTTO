"""
Voice identity configuration for OTTO.

Manages voice characteristics and persona consistency.

Per spec: OTTO sounds like a calm friend on the phone—someone who's been there.
NOT like Siri (corporate), Alexa (assistant-y), or a therapist (clinical).
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Final, Optional

from .tts import TTSVoice, TTSModel, VOICE_CHARACTERISTICS


# === Voice Character Constants ===

# Phrases that sound awkward when spoken aloud
# These get removed before TTS synthesis
FORBIDDEN_SPOKEN_PHRASES: Final[list[str]] = [
    "Does that make sense?",
    "Let me know if you have questions",
    "I hope this helps",
    "Is there anything else?",
    "I understand you're feeling",
    "I'm here to help",
    "Feel free to ask",
    "Don't hesitate to",
    "As an AI",
    "As a language model",
    "As your AI assistant",
    "As your assistant",
    "I cannot",
    "I'm unable to",
    "I'd be happy to help",
    "I'd be delighted to",
]

# Maximum limits for spoken responses (keeps voice responses digestible)
MAX_SPOKEN_WORDS: Final[int] = 60      # ~30 seconds of speech
MAX_SPOKEN_SENTENCES: Final[int] = 4   # Breathing room between ideas

# Threshold for switching from voice to text response
VOICE_RESPONSE_MAX_LENGTH: Final[int] = 500  # Characters


class VoiceTone(str, Enum):
    """Voice tone presets."""

    PROFESSIONAL = "professional"  # Business-like, clear
    FRIENDLY = "friendly"          # Warm, approachable
    CALM = "calm"                  # Soothing, gentle
    ENERGETIC = "energetic"        # Upbeat, enthusiastic
    NEUTRAL = "neutral"            # Balanced, informative


class SpeakingStyle(str, Enum):
    """Speaking style presets."""

    CONVERSATIONAL = "conversational"  # Natural, casual
    FORMAL = "formal"                  # Structured, precise
    INSTRUCTIONAL = "instructional"    # Clear, step-by-step
    SUPPORTIVE = "supportive"          # Encouraging, patient


@dataclass
class VoiceIdentity:
    """
    Voice identity configuration for OTTO.

    Defines how OTTO sounds and speaks.
    """

    name: str = "OTTO"
    """Voice assistant name."""

    voice: TTSVoice = field(default_factory=TTSVoice.default)
    """TTS voice selection."""

    model: TTSModel = field(default_factory=TTSModel.default)
    """TTS model selection."""

    tone: VoiceTone = VoiceTone.FRIENDLY
    """Default tone."""

    style: SpeakingStyle = SpeakingStyle.CONVERSATIONAL
    """Default speaking style."""

    speed: float = 1.0
    """Speech speed (0.25-4.0)."""

    language: str = "en"
    """Primary language."""

    pronouns: str = "they/them"
    """OTTO's pronouns."""

    def get_greeting(self) -> str:
        """Return appropriate greeting based on tone."""
        greetings = {
            VoiceTone.PROFESSIONAL: f"Hello, this is {self.name}.",
            VoiceTone.FRIENDLY: f"Hey there! It's {self.name}.",
            VoiceTone.CALM: f"Hi, {self.name} here.",
            VoiceTone.ENERGETIC: f"Hi! {self.name} at your service!",
            VoiceTone.NEUTRAL: f"Hello, {self.name} speaking.",
        }
        return greetings.get(self.tone, f"Hello, this is {self.name}.")

    def get_farewell(self) -> str:
        """Return appropriate farewell based on tone."""
        farewells = {
            VoiceTone.PROFESSIONAL: "Thank you. Have a productive day.",
            VoiceTone.FRIENDLY: "Take care! Chat soon!",
            VoiceTone.CALM: "Take care of yourself.",
            VoiceTone.ENERGETIC: "Awesome! Talk to you later!",
            VoiceTone.NEUTRAL: "Goodbye.",
        }
        return farewells.get(self.tone, "Goodbye.")

    def get_acknowledgment(self) -> str:
        """Return appropriate acknowledgment based on tone."""
        acknowledgments = {
            VoiceTone.PROFESSIONAL: "Understood.",
            VoiceTone.FRIENDLY: "Got it!",
            VoiceTone.CALM: "I understand.",
            VoiceTone.ENERGETIC: "Awesome, I'm on it!",
            VoiceTone.NEUTRAL: "Acknowledged.",
        }
        return acknowledgments.get(self.tone, "Understood.")

    def get_error_response(self) -> str:
        """Return appropriate error response based on tone."""
        errors = {
            VoiceTone.PROFESSIONAL: "I apologize, but I encountered an issue.",
            VoiceTone.FRIENDLY: "Oops, something went a bit sideways.",
            VoiceTone.CALM: "I ran into a small problem.",
            VoiceTone.ENERGETIC: "Whoa, hit a snag there!",
            VoiceTone.NEUTRAL: "An error occurred.",
        }
        return errors.get(self.tone, "An error occurred.")

    def get_thinking_response(self) -> str:
        """Return appropriate thinking indicator based on tone."""
        thinking = {
            VoiceTone.PROFESSIONAL: "Let me process that.",
            VoiceTone.FRIENDLY: "Hmm, let me think about that.",
            VoiceTone.CALM: "Give me a moment.",
            VoiceTone.ENERGETIC: "Oh, interesting! Let me figure this out!",
            VoiceTone.NEUTRAL: "Processing.",
        }
        return thinking.get(self.tone, "Processing.")


# Default OTTO voice identity
DEFAULT_IDENTITY = VoiceIdentity(
    name="OTTO",
    voice=TTSVoice.NOVA,      # Friendly, approachable
    model=TTSModel.TTS_1,     # Balance quality/latency
    tone=VoiceTone.FRIENDLY,
    style=SpeakingStyle.CONVERSATIONAL,
    speed=1.0,
    language="en",
)


# Context-aware identity adjustments
def adjust_for_context(
    identity: VoiceIdentity,
    context: str,
) -> VoiceIdentity:
    """
    Adjust voice identity based on conversation context.

    Args:
        identity: Base identity
        context: Context keyword (e.g., "error", "success", "support")

    Returns:
        Adjusted identity (new instance)
    """
    adjustments = {
        "error": {
            "tone": VoiceTone.CALM,
            "speed": 0.95,  # Slightly slower for clarity
        },
        "success": {
            "tone": VoiceTone.ENERGETIC,
            "speed": 1.05,  # Slightly faster, upbeat
        },
        "support": {
            "tone": VoiceTone.CALM,
            "style": SpeakingStyle.SUPPORTIVE,
            "speed": 0.9,  # Slower, more patient
        },
        "instruction": {
            "tone": VoiceTone.NEUTRAL,
            "style": SpeakingStyle.INSTRUCTIONAL,
            "speed": 0.95,  # Slightly slower for comprehension
        },
        "urgent": {
            "tone": VoiceTone.PROFESSIONAL,
            "speed": 1.1,  # Faster delivery
        },
    }

    context_adjustments = adjustments.get(context, {})
    if not context_adjustments:
        return identity

    # Create new identity with adjustments
    return VoiceIdentity(
        name=identity.name,
        voice=identity.voice,
        model=identity.model,
        tone=context_adjustments.get("tone", identity.tone),
        style=context_adjustments.get("style", identity.style),
        speed=context_adjustments.get("speed", identity.speed),
        language=identity.language,
        pronouns=identity.pronouns,
    )


def voice_for_emotion(emotion: str) -> TTSVoice:
    """
    Select appropriate voice for emotional context.

    Args:
        emotion: Emotional context (happy, sad, excited, etc.)

    Returns:
        Appropriate TTSVoice
    """
    emotion_voices = {
        "happy": TTSVoice.NOVA,
        "excited": TTSVoice.NOVA,
        "sad": TTSVoice.SHIMMER,
        "calm": TTSVoice.SHIMMER,
        "serious": TTSVoice.ONYX,
        "professional": TTSVoice.ONYX,
        "warm": TTSVoice.ECHO,
        "friendly": TTSVoice.ECHO,
        "neutral": TTSVoice.ALLOY,
        "storytelling": TTSVoice.FABLE,
    }
    return emotion_voices.get(emotion.lower(), TTSVoice.NOVA)


# === Voice Character Enforcement ===

def remove_forbidden_phrases(text: str) -> str:
    """
    Remove phrases that sound awkward when spoken aloud.

    Per spec: These clinical/robotic phrases break OTTO's
    "calm friend on the phone" voice character.

    Args:
        text: Input text that may contain forbidden phrases

    Returns:
        Text with forbidden phrases removed
    """
    # Normalize smart/curly quotes to straight quotes for consistent matching
    result = text.replace("'", "'").replace("'", "'").replace(""", '"').replace(""", '"')

    # Normalize whitespace BEFORE matching (handles line breaks in phrases)
    result = re.sub(r"\s+", " ", result)

    for phrase in FORBIDDEN_SPOKEN_PHRASES:
        # Case-insensitive removal
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        result = pattern.sub("", result)

    # Clean up resulting whitespace after removals
    result = re.sub(r"\s+", " ", result)
    result = re.sub(r"\s+([.,!?;:])", r"\1", result)
    return result.strip()


def limit_for_speech(
    text: str,
    max_words: int = MAX_SPOKEN_WORDS,
    max_sentences: int = MAX_SPOKEN_SENTENCES,
) -> str:
    """
    Limit text length for digestible voice responses.

    Keeps voice responses under ~30 seconds by limiting
    word count and sentence count.

    Args:
        text: Input text to limit
        max_words: Maximum word count (default: 60)
        max_sentences: Maximum sentence count (default: 4)

    Returns:
        Text limited to specified constraints
    """
    # Split into sentences (preserving sentence-ending punctuation)
    sentence_pattern = re.compile(r"(?<=[.!?])\s+")
    sentences = sentence_pattern.split(text)

    # Limit sentence count
    sentences = sentences[:max_sentences]

    # Join and limit word count
    result = " ".join(sentences)
    words = result.split()
    if len(words) > max_words:
        words = words[:max_words]
        result = " ".join(words)
        # Add ellipsis if truncated mid-sentence
        if not result.rstrip().endswith((".", "!", "?")):
            result = result.rstrip() + "..."

    return result.strip()


def should_respond_with_voice(
    user_sent_voice: bool,
    user_preference: Optional[str] = None,
    response_length: int = 0,
) -> bool:
    """
    Determine if OTTO should respond with voice or text.

    Decision logic (per spec):
    1. User preference always wins if specified
    2. Voice input → voice output (mirror)
    3. Long responses → text (too much to listen to)

    Args:
        user_sent_voice: True if user sent a voice message
        user_preference: "voice", "text", or None (auto)
        response_length: Length of response in characters

    Returns:
        True if should respond with voice, False for text
    """
    # User preference always wins
    if user_preference == "voice":
        return True
    if user_preference == "text":
        return False

    # Auto mode: mirror user's input format
    if not user_sent_voice:
        return False

    # Voice input, but check response length
    # Long responses are better as text
    if response_length > VOICE_RESPONSE_MAX_LENGTH:
        return False

    return True


def prepare_text_for_voice(text: str) -> str:
    """
    Prepare text for voice synthesis by applying all voice character rules.

    Combines forbidden phrase removal and length limiting.
    Use this before passing text to TTS.

    Args:
        text: Raw response text

    Returns:
        Text ready for TTS synthesis
    """
    # Remove forbidden phrases first
    text = remove_forbidden_phrases(text)
    # Then limit length
    text = limit_for_speech(text)
    return text
