"""Commitment detector — calls Claude to identify promises in messages."""

from __future__ import annotations

import json
import os
import sys

import anthropic

from .models import Commitment

_SYSTEM_PROMPT = """\
You are a commitment detector. Given a WhatsApp message, determine if the sender is making a commitment — a promise to do something for someone.

Examples of commitments:
- "I'll send that over Monday"
- "Let me get back to you on that"
- "I'll take care of it"
- "Will do, by end of week"
- "I need to follow up with Sarah about the contract"

Examples of NOT commitments:
- "That sounds good"
- "Thanks!"
- "I think we should consider..."
- "Maybe next week"

If a commitment is found, respond with JSON:
{
    "found": true,
    "commitment_text": "what was promised",
    "who_to": "recipient name or 'unknown'",
    "deadline": "ISO date if mentioned, null if not",
    "deadline_source": "explicit" or "inferred" or "none",
    "confidence": 0.0-1.0
}

If no commitment, respond with:
{"found": false}

Respond ONLY with JSON. No explanation."""

_CONFIDENCE_THRESHOLD = float(os.environ.get("OTTO_CONFIDENCE_THRESHOLD", "0.7"))


async def detect_commitment(message: str, chat_name: str) -> Commitment | None:
    """Detect if a message contains a commitment. Returns Commitment or None."""
    try:
        client = anthropic.AsyncAnthropic()
        response = await client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=256,
            system=_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": f"Chat: {chat_name}\nMessage: {message}"}
            ],
        )
    except Exception as e:
        print(f"OTTO detector API error: {e}", file=sys.stderr)
        return None

    raw_text = response.content[0].text
    print(f"OTTO detector raw: {raw_text}", file=sys.stderr)

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        print(f"OTTO detector JSON parse failed: {raw_text}", file=sys.stderr)
        return None

    if not data.get("found"):
        return None

    if data.get("confidence", 0) < _CONFIDENCE_THRESHOLD:
        return None

    return Commitment(
        raw_message=message,
        commitment_text=data["commitment_text"],
        who_to=data.get("who_to", "unknown"),
        source_chat=chat_name,
        deadline_source=data.get("deadline_source", "none"),
    )
