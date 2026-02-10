"""
WhatsApp watcher — listens for messages, detects commitments.

Runs a FastAPI server that receives WhatsApp Cloud API webhooks.
Incoming text messages go through the commitment detector.
Detected commitments get stored in SQLite.

Usage:
    python -m otto.watcher [--port 8000]

Environment Variables:
    WHATSAPP_VERIFY_TOKEN   - Webhook verification token (default: "otto_verify")
    WHATSAPP_APP_SECRET     - App secret for signature validation (optional)
    ANTHROPIC_API_KEY       - For commitment detection via Claude
"""

import asyncio
import hashlib
import hmac
import json
import os
import sys
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, Request, Response, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional

from .detector import detect_commitment
from .store import CommitmentStore


# --- Minimal WhatsApp schemas (copied from v0.7, stripped to essentials) ---

class TextContent(BaseModel):
    body: str

class WhatsAppContact(BaseModel):
    profile: dict = Field(default_factory=dict)
    wa_id: str

    @property
    def name(self) -> str:
        return self.profile.get("name", "Unknown")

class IncomingMessage(BaseModel):
    from_: str = Field(..., alias="from")
    id: str
    timestamp: str
    type: str = "text"
    text: Optional[TextContent] = None

    class Config:
        populate_by_name = True

    @property
    def message_time(self) -> datetime:
        return datetime.fromtimestamp(int(self.timestamp), tz=timezone.utc)

class WebhookValue(BaseModel):
    messaging_product: str = "whatsapp"
    metadata: dict = Field(default_factory=dict)
    contacts: list[WhatsAppContact] = Field(default_factory=list)
    messages: list[IncomingMessage] = Field(default_factory=list)

class WebhookChange(BaseModel):
    value: WebhookValue
    field: str = "messages"

class WebhookEntry(BaseModel):
    id: str
    changes: list[WebhookChange] = Field(default_factory=list)

class WebhookPayload(BaseModel):
    object: str = "whatsapp_business_account"
    entry: list[WebhookEntry] = Field(default_factory=list)


# --- Config ---

VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "otto_verify")
APP_SECRET = os.environ.get("WHATSAPP_APP_SECRET", "")
MAX_MESSAGE_AGE = timedelta(hours=1)  # Skip messages older than 1 hour


# --- App ---

app = FastAPI(title="OTTO Watcher")
store = CommitmentStore()


@app.get("/webhook/whatsapp")
async def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
):
    """WhatsApp webhook verification."""
    if hub_mode != "subscribe":
        raise HTTPException(status_code=400, detail="Invalid mode")
    if hub_verify_token != VERIFY_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")
    return Response(content=hub_challenge, media_type="text/plain")


@app.post("/webhook/whatsapp")
async def receive_webhook(request: Request):
    """Receive and process incoming WhatsApp messages."""
    body = await request.body()

    # Validate signature if app secret configured
    if APP_SECRET:
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not _verify_signature(body, signature):
            raise HTTPException(status_code=403, detail="Invalid signature")

    # Parse payload
    try:
        payload = WebhookPayload(**json.loads(body))
    except Exception as e:
        print(f"[watcher] Failed to parse payload: {e}", file=sys.stderr)
        raise HTTPException(status_code=400, detail="Invalid payload")

    # Process messages
    for entry in payload.entry:
        for change in entry.changes:
            contacts_map = {c.wa_id: c for c in change.value.contacts}
            for msg in change.value.messages:
                contact = contacts_map.get(msg.from_)
                if contact:
                    await _handle_message(contact, msg)

    return {"status": "ok"}


def _verify_signature(body: bytes, signature: str) -> bool:
    """Verify HMAC-SHA256 signature from WhatsApp."""
    if not signature.startswith("sha256="):
        return False
    expected = signature[7:]
    computed = hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, expected)


async def _handle_message(contact: WhatsAppContact, message: IncomingMessage):
    """Handle a single incoming message."""
    # Skip non-text messages
    if message.type != "text" or not message.text:
        return

    # Skip old messages (catch-up protection)
    age = datetime.now(timezone.utc) - message.message_time
    if age > MAX_MESSAGE_AGE:
        print(f"[watcher] Skipping old message ({age})", file=sys.stderr)
        return

    text = message.text.body
    chat_name = contact.name

    print(f"[watcher] Message from {chat_name}: {text[:80]}")

    # Detect commitment
    commitment = await detect_commitment(text, chat_name)

    if commitment:
        commitment.source_chat = f"WhatsApp/{chat_name}"
        store.add(commitment)
        print(f"  Commitment detected: {commitment.commitment_text}")
        print(f"  To: {commitment.who_to} | By: {commitment.deadline or 'no deadline'}")
    else:
        print(f"  No commitment detected.")


def main():
    """Start the watcher server."""
    import uvicorn

    port = int(os.environ.get("OTTO_WATCHER_PORT", "8000"))
    print(f"OTTO Watcher starting on port {port}")
    print(f"Webhook URL: http://localhost:{port}/webhook/whatsapp")
    print(f"Verify token: {VERIFY_TOKEN}")
    print(f"Signature validation: {'enabled' if APP_SECRET else 'disabled'}")
    print()
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    main()
