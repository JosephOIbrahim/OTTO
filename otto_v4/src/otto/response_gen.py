"""Optional LLM-powered response rephrasing for OTTO modes.

Gated by the OTTO_LLM_RESPONSES environment variable.  When disabled
(the default), template text passes through unchanged.  When enabled,
OTTO uses Claude to rephrase template output into more natural language
while preserving intent and constitutional tone.

Deterministic routing is NEVER affected.  This module operates at the
presentation layer only -- the "intentional variation" layer in the
determinism table.

Usage:
    from otto.response_gen import maybe_rephrase
    text = await maybe_rephrase(response.text, mode="protector", action="validate")
"""

from __future__ import annotations

import os

import anthropic

from .log import get_logger
from .model_config import RESPONSE_GEN_MODEL, TEMPERATURE

_log = get_logger(__name__)


def is_llm_enabled() -> bool:
    """Check whether LLM response generation is enabled."""
    return os.environ.get("OTTO_LLM_RESPONSES", "").lower() in (
        "true", "1", "yes",
    )


# System prompt constraining the rephraser to OTTO's constitutional voice
_REPHRASE_SYSTEM = """\
You are rephrasing a message from OTTO, a cognitive commitment engine.

Rules:
- Keep the same meaning and intent
- Use warm, direct language (not chirpy)
- Never use "just" or "simply"
- Never guilt-trip or judge
- Never add clinical language or labels
- Keep it brief (1-3 sentences max)
- Output ONLY the rephrased text, nothing else
"""


async def maybe_rephrase(
    text: str,
    *,
    mode: str = "",
    action: str = "",
) -> str:
    """Optionally rephrase template text using Claude.

    Parameters
    ----------
    text:
        The template text from a mode's execute() output.
    mode:
        Which mode produced this text (for context).
    action:
        The action metadata (for context).

    Returns
    -------
    str
        The original text if LLM is disabled, or a rephrased version.
        On any error, falls back to the original text.
    """
    if not is_llm_enabled() or not text.strip():
        return text

    try:
        client = anthropic.AsyncAnthropic()
        response = await client.messages.create(
            model=RESPONSE_GEN_MODEL,
            max_tokens=200,
            temperature=TEMPERATURE,
            system=[
                {
                    "type": "text",
                    "text": _REPHRASE_SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{
                "role": "user",
                "content": f"Rephrase this OTTO {mode} message ({action}):\n\n{text}",
            }],
        )
        rephrased = response.content[0].text.strip()
        _log.debug("LLM rephrase: %r -> %r", text[:60], rephrased[:60])
        return rephrased

    except Exception as exc:
        _log.warning("LLM rephrase failed, using template: %s", exc)
        return text
