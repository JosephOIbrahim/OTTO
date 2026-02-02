"""
Voice Adapter for OTTO.

Post-processes LLM responses to:
- Strip corporate/robot speak
- Match user's register
- Enforce voice principles

[He2025] ThinkingMachines Compliance:
- Pattern lists are sorted for deterministic iteration
- Transformations applied in fixed order
- Same inputs always produce same outputs
"""
import re
from typing import Optional

from .register import Register


# === Forbidden Phrases (sorted for determinism) ===

FORBIDDEN_STARTERS = sorted([
    r"^Absolutely[!.,]?\s*",
    r"^As an AI,?\s*",
    r"^As a language model,?\s*",
    r"^Certainly[!.,]?\s*",
    r"^Great question[!.,]?\s*",
    r"^I am (an AI|designed|here to|OTTO)[^.]*[.,]?\s*",  # Match to end of phrase
    r"^I can help you with that[.,]?\s*",
    r"^I understand[.,]?\s*",
    r"^I'd be happy to\s*",
    r"^Of course[!.,]?\s*",
    r"^Sure[!.,]?\s*",
    r"^That's a great\s+\w+[!.,]?\s*",
])

FORBIDDEN_ANYWHERE = sorted([
    r"I understand (that |how )?you",
    r"I('m| am) here to help",
    r"Let me help you with",
    r"I('d| would) be happy to",
    r"feel free to",
    r"don't hesitate to",
    r"happy to assist",
    r"As an AI",
    r"As a language model",
    r"cognitive support system",
    r"designed to help",
    r"designed to assist",
    r"designed to provide",
])

# === Rewrite Rules (fixed order) ===

REWRITE_I_STARTS = [
    (r"^I think ", ""),
    (r"^I believe ", ""),
    (r"^I can see (that )?", "Looks like "),
    (r"^I notice(d)? (that )?", ""),
    (r"^I would suggest ", "Try "),
    (r"^I recommend ", ""),
    (r"^I'll ", ""),
    (r"^I'd ", ""),
    (r"^I've ", ""),
]


class VoiceAdapter:
    """
    Adapts LLM responses to match user's voice.

    [He2025] Deterministic transformation pipeline:
    1. Strip forbidden phrases
    2. Fix "I" starts
    3. Apply register transformations
    4. Handle emoji
    5. Clean up
    """

    def __init__(self):
        self.register = Register.NEUTRAL
        self.user_uses_emoji = False

    def set_context(
        self,
        register: Register,
        user_uses_emoji: bool = False,
    ) -> None:
        """Set context for voice adaptation."""
        self.register = register
        self.user_uses_emoji = user_uses_emoji

    def adapt(self, response: str) -> str:
        """
        Adapt response to match voice profile.

        [He2025] Fixed transformation order for determinism.
        """
        result = response

        # Step 1: Strip forbidden
        result = self._strip_forbidden(result)

        # Step 2: Fix "I" starts
        result = self._fix_i_start(result)

        # Step 3: Register transforms
        if self.register == Register.CASUAL:
            result = self._make_casual(result)
        elif self.register == Register.FORMAL:
            result = self._make_formal(result)
        elif self.register == Register.TERSE:
            result = self._make_terse(result)
        elif self.register == Register.VENTING:
            result = self._make_supportive(result)

        # Step 4: Emoji
        if not self.user_uses_emoji:
            result = self._strip_emoji(result)

        # Step 5: Clean up
        result = self._cleanup(result)

        return result

    def _strip_forbidden(self, text: str) -> str:
        """Remove forbidden phrases (sorted iteration for determinism)."""
        # Starters
        for pattern in FORBIDDEN_STARTERS:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # Anywhere
        for pattern in FORBIDDEN_ANYWHERE:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        return text

    def _fix_i_start(self, text: str) -> str:
        """Don't start with 'I'."""
        stripped = text.strip()

        if not (stripped.startswith("I ") or stripped.startswith("I'")):
            return stripped

        for pattern, replacement in REWRITE_I_STARTS:
            if re.match(pattern, stripped, re.IGNORECASE):
                result = re.sub(pattern, replacement, stripped, count=1, flags=re.IGNORECASE)
                # Capitalize first letter
                if result and result[0].islower():
                    result = result[0].upper() + result[1:]
                return result

        return stripped

    def _make_casual(self, text: str) -> str:
        """Make response casual with contractions."""
        contractions = [
            (r"\bI am\b", "I'm"),
            (r"\bYou are\b", "You're"),
            (r"\bIt is\b", "It's"),
            (r"\bThat is\b", "That's"),
            (r"\bDo not\b", "Don't"),
            (r"\bCannot\b", "Can't"),
            (r"\bWill not\b", "Won't"),
            (r"\bLet us\b", "Let's"),
            (r"\bgoing to\b", "gonna"),
            (r"\bwant to\b", "wanna"),
            (r"\bkind of\b", "kinda"),
        ]

        for pattern, replacement in contractions:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        return text

    def _make_formal(self, text: str) -> str:
        """Make response formal by expanding contractions."""
        expansions = [
            (r"\bI'm\b", "I am"),
            (r"\bYou're\b", "You are"),
            (r"\bIt's\b", "It is"),
            (r"\bThat's\b", "That is"),
            (r"\bDon't\b", "Do not"),
            (r"\bCan't\b", "Cannot"),
            (r"\bWon't\b", "Will not"),
            (r"\bLet's\b", "Let us"),
        ]

        for pattern, replacement in expansions:
            text = re.sub(pattern, replacement, text)

        return text

    def _make_terse(self, text: str) -> str:
        """Make response minimal - first sentence only."""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        if sentences:
            return sentences[0]
        return text

    def _make_supportive(self, text: str) -> str:
        """Make response supportive (for venting users) - max 2 sentences."""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        if len(sentences) > 2:
            return ' '.join(sentences[:2])
        return text

    def _strip_emoji(self, text: str) -> str:
        """Remove emoji."""
        emoji_pattern = re.compile(
            "["
            "\U0001F300-\U0001F9FF"
            "\U0001FA00-\U0001FAFF"
            "\U00002702-\U000027B0"
            "]+",
            flags=re.UNICODE
        )
        return emoji_pattern.sub("", text)

    def _cleanup(self, text: str) -> str:
        """Final cleanup."""
        # Multiple spaces
        text = re.sub(r'\s+', ' ', text)
        # Space before punctuation
        text = re.sub(r'\s+([.!?,])', r'\1', text)
        # Multiple newlines
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()


def adapt_response(
    response: str,
    register: Register,
    user_uses_emoji: bool = False,
) -> str:
    """Convenience function for one-off adaptation."""
    adapter = VoiceAdapter()
    adapter.set_context(register, user_uses_emoji)
    return adapter.adapt(response)


__all__ = [
    'VoiceAdapter',
    'adapt_response',
    'FORBIDDEN_STARTERS',
    'FORBIDDEN_ANYWHERE',
]
