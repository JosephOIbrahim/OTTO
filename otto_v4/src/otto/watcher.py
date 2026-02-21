"""
WhatsApp watcher — listens for messages, detects commitments.

Runs a FastAPI server that receives WhatsApp Cloud API webhooks.
Incoming text messages go through the commitment detector.
Detected commitments get stored in SQLite.

Usage:
    python -m otto.watcher [--port 8000]

Environment Variables:
    WHATSAPP_VERIFY_TOKEN   - Webhook verification token (required for webhook verify)
    WHATSAPP_APP_SECRET     - App secret for signature validation (required in production)
    ANTHROPIC_API_KEY       - For commitment detection via Claude
    OTTO_ENV                - "development" (default) or "production"
"""

import asyncio
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone, timedelta

from .log import get_logger

_log = get_logger(__name__)

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

from .db import Database
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

    model_config = ConfigDict(populate_by_name=True)

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

VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
APP_SECRET = os.environ.get("WHATSAPP_APP_SECRET", "")
OTTO_ENV = os.environ.get("OTTO_ENV", "development")
MAX_MESSAGE_AGE = timedelta(hours=1)  # Skip messages older than 1 hour

# Rate limiting: max requests per IP within the sliding window
_RATE_LIMIT = int(os.environ.get("OTTO_RATE_LIMIT", "100"))  # per window
_RATE_WINDOW = int(os.environ.get("OTTO_RATE_WINDOW", "60"))  # seconds


# --- Rate limiter (SQLite-backed, survives restarts) ---


class RateLimiter:
    """SQLite-backed sliding window rate limiter.

    Persists request timestamps so rate limits survive process restarts.
    Prunes expired entries on each call to keep the table small.
    """

    def __init__(
        self,
        db_path: str = "",
        max_requests: int = 100,
        window_seconds: int = 60,
    ) -> None:
        import sqlite3
        self._max = max_requests
        self._window = window_seconds
        if db_path:
            self._conn = sqlite3.connect(db_path, check_same_thread=False)
        else:
            self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS rate_limits ("
            "ip TEXT NOT NULL, ts REAL NOT NULL)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rate_ip ON rate_limits(ip)"
        )
        self._conn.commit()

    def allow(self, client_ip: str) -> bool:
        """Return True if the request is allowed, False if rate limited."""
        now = time.time()
        cutoff = now - self._window

        # Prune expired entries for this IP
        self._conn.execute(
            "DELETE FROM rate_limits WHERE ip = ? AND ts < ?",
            (client_ip, cutoff),
        )

        # Count recent requests
        cur = self._conn.execute(
            "SELECT COUNT(*) FROM rate_limits WHERE ip = ? AND ts >= ?",
            (client_ip, cutoff),
        )
        count = cur.fetchone()[0]

        if count >= self._max:
            self._conn.commit()
            return False

        # Record this request
        self._conn.execute(
            "INSERT INTO rate_limits (ip, ts) VALUES (?, ?)",
            (client_ip, now),
        )
        self._conn.commit()
        return True


# Module-level instance (in-memory by default, overridable for testing)
_rate_limiter = RateLimiter(max_requests=_RATE_LIMIT, window_seconds=_RATE_WINDOW)


def _is_rate_limited(client_ip: str) -> bool:
    """Check if a client IP has exceeded the rate limit."""
    return not _rate_limiter.allow(client_ip)


# --- App ---

_START_TIME = time.monotonic()


@asynccontextmanager
async def _lifespan(application: FastAPI):
    """Startup/shutdown lifecycle handler."""
    if not VERIFY_TOKEN:
        _log.warning(
            "WHATSAPP_VERIFY_TOKEN is not set. Webhook verification disabled."
        )
    if not APP_SECRET:
        _log.warning(
            "WHATSAPP_APP_SECRET is not set. Webhook requests will NOT be "
            "validated. Set this env var in production."
        )
    yield


app = FastAPI(title="OTTO Watcher", lifespan=_lifespan)
_watcher_db = Database("~/.otto/commitments.db")
store = CommitmentStore(db=_watcher_db)


@app.get("/health")
async def health():
    """Health check for load balancers and monitoring."""
    return {
        "status": "ok",
        "version": "5.1.0",
        "uptime_seconds": round(time.monotonic() - _START_TIME, 1),
    }


@app.get("/webhook/whatsapp")
async def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
):
    """WhatsApp webhook verification."""
    if not VERIFY_TOKEN:
        raise HTTPException(status_code=503, detail="WHATSAPP_VERIFY_TOKEN not configured")
    if hub_mode != "subscribe":
        raise HTTPException(status_code=400, detail="Invalid mode")
    if hub_verify_token != VERIFY_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")
    return Response(content=hub_challenge, media_type="text/plain")


@app.post("/webhook/whatsapp")
async def receive_webhook(request: Request):
    """Receive and process incoming WhatsApp messages."""
    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if _is_rate_limited(client_ip):
        _log.warning("Rate limited: %s", client_ip)
        raise HTTPException(status_code=429, detail="Too many requests")

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
        _log.warning("Failed to parse payload: %s", e)
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
        _log.debug("Skipping old message (age=%s)", age)
        return

    text = message.text.body
    chat_name = contact.name

    _log.info("Message from %s: %s", chat_name, text[:80])

    # Detect commitment
    commitment = await detect_commitment(text, chat_name)

    if commitment:
        commitment.source_chat = f"WhatsApp/{chat_name}"
        commitment.sender_phone = message.from_
        store.add(commitment)
        _log.info("Commitment detected: %s", commitment.commitment_text)
        _log.info("  To: %s | By: %s", commitment.who_to, commitment.deadline or "no deadline")
    else:
        _log.debug("No commitment detected.")


def main():
    """Start the watcher server."""
    import uvicorn

    port = int(os.environ.get("OTTO_WATCHER_PORT", "8000"))
    _log.info("OTTO Watcher starting on port %d", port)
    _log.info("Webhook URL: http://localhost:%d/webhook/whatsapp", port)
    _log.info("Verify token: %s", "****" + VERIFY_TOKEN[-4:] if len(VERIFY_TOKEN) > 4 else "[not set]")
    _log.info("Signature validation: %s", "enabled" if APP_SECRET else "disabled")
    if OTTO_ENV == "production" and not APP_SECRET:
        _log.error("WHATSAPP_APP_SECRET is required in production. Set OTTO_ENV=development to bypass.")
        raise SystemExit(1)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    main()
