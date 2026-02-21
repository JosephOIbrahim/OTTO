"""Tests for the WhatsApp watcher webhook server."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from otto.watcher import app

# Fixed token for verification tests (the real default is now "" for security)
_TEST_VERIFY_TOKEN = "test_token_for_verification_tests"


@pytest.fixture()
def client():
    return TestClient(app)


# ------------------------------------------------------------------
# GET /webhook/whatsapp — verification
# ------------------------------------------------------------------


class TestHealthEndpoint:

    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], float)

    def test_health_version_is_string(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert isinstance(data["version"], str)
        assert "." in data["version"]


# ------------------------------------------------------------------
# GET /webhook/whatsapp -- verification
# ------------------------------------------------------------------


class TestWebhookVerification:

    def test_valid_verification(self, client):
        with patch("otto.watcher.VERIFY_TOKEN", _TEST_VERIFY_TOKEN):
            resp = client.get("/webhook/whatsapp", params={
                "hub.mode": "subscribe",
                "hub.verify_token": _TEST_VERIFY_TOKEN,
                "hub.challenge": "test_challenge_123",
            })
        assert resp.status_code == 200
        assert resp.text == "test_challenge_123"

    def test_wrong_mode_rejected(self, client):
        with patch("otto.watcher.VERIFY_TOKEN", _TEST_VERIFY_TOKEN):
            resp = client.get("/webhook/whatsapp", params={
                "hub.mode": "unsubscribe",
                "hub.verify_token": _TEST_VERIFY_TOKEN,
                "hub.challenge": "test",
            })
        assert resp.status_code == 400

    def test_wrong_token_rejected(self, client):
        with patch("otto.watcher.VERIFY_TOKEN", _TEST_VERIFY_TOKEN):
            resp = client.get("/webhook/whatsapp", params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong_token",
                "hub.challenge": "test",
            })
        assert resp.status_code == 403

    def test_missing_params_rejected(self, client):
        resp = client.get("/webhook/whatsapp")
        assert resp.status_code == 422


# ------------------------------------------------------------------
# POST /webhook/whatsapp — message processing
# ------------------------------------------------------------------


def _make_webhook_payload(text: str, sender: str = "1234567890", name: str = "Alice") -> dict:
    """Build a minimal WhatsApp Cloud API webhook payload."""
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "BIZ_ACCOUNT_ID",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "0000", "phone_number_id": "PID"},
                    "contacts": [{"profile": {"name": name}, "wa_id": sender}],
                    "messages": [{
                        "from": sender,
                        "id": "wamid.test123",
                        "timestamp": str(int(time.time())),
                        "type": "text",
                        "text": {"body": text},
                    }],
                },
                "field": "messages",
            }],
        }],
    }


class TestMessageProcessing:

    def test_text_message_calls_detector(self, client):
        payload = _make_webhook_payload("I'll send the deck by Friday")
        with patch("otto.watcher.detect_commitment", new_callable=AsyncMock, return_value=None) as mock_detect:
            resp = client.post("/webhook/whatsapp", json=payload)

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
        mock_detect.assert_called_once()
        args = mock_detect.call_args
        assert "deck" in args[0][0].lower() or "deck" in str(args).lower()

    def test_detected_commitment_stored(self, client, store):
        from otto.models import Commitment
        fake_commitment = Commitment(
            raw_message="I'll send the deck",
            commitment_text="send the deck",
            who_to="Bob",
        )

        payload = _make_webhook_payload("I'll send the deck by Friday", name="Bob")
        with (
            patch("otto.watcher.detect_commitment", new_callable=AsyncMock, return_value=fake_commitment),
            patch("otto.watcher.store", store),
        ):
            resp = client.post("/webhook/whatsapp", json=payload)

        assert resp.status_code == 200
        stored = store.get_active()
        assert len(stored) == 1
        assert stored[0].commitment_text == "send the deck"
        assert "WhatsApp" in stored[0].source_chat

    def test_no_commitment_nothing_stored(self, client, store):
        payload = _make_webhook_payload("Sounds good!")
        with (
            patch("otto.watcher.detect_commitment", new_callable=AsyncMock, return_value=None),
            patch("otto.watcher.store", store),
        ):
            resp = client.post("/webhook/whatsapp", json=payload)

        assert resp.status_code == 200
        assert len(store.get_active()) == 0

    def test_non_text_message_skipped(self, client):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "BIZ_ACCOUNT_ID",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {},
                        "contacts": [{"profile": {"name": "Alice"}, "wa_id": "123"}],
                        "messages": [{
                            "from": "123",
                            "id": "wamid.img1",
                            "timestamp": str(int(time.time())),
                            "type": "image",
                        }],
                    },
                    "field": "messages",
                }],
            }],
        }
        with patch("otto.watcher.detect_commitment", new_callable=AsyncMock) as mock_detect:
            resp = client.post("/webhook/whatsapp", json=payload)

        assert resp.status_code == 200
        mock_detect.assert_not_called()

    def test_old_message_skipped(self, client):
        payload = _make_webhook_payload("I'll do it")
        # Set timestamp to 2 hours ago
        old_ts = str(int(time.time()) - 7200)
        payload["entry"][0]["changes"][0]["value"]["messages"][0]["timestamp"] = old_ts

        with patch("otto.watcher.detect_commitment", new_callable=AsyncMock) as mock_detect:
            resp = client.post("/webhook/whatsapp", json=payload)

        assert resp.status_code == 200
        mock_detect.assert_not_called()

    def test_empty_entry_ok(self, client):
        payload = {"object": "whatsapp_business_account", "entry": []}
        resp = client.post("/webhook/whatsapp", json=payload)
        assert resp.status_code == 200

    def test_invalid_payload_rejected(self, client):
        resp = client.post("/webhook/whatsapp", content=b"not json at all",
                          headers={"content-type": "application/json"})
        assert resp.status_code == 400


# ------------------------------------------------------------------
# Signature validation
# ------------------------------------------------------------------


class TestSignatureValidation:

    def test_valid_signature_accepted(self, client):
        secret = "test_secret_123"
        payload = json.dumps(_make_webhook_payload("hello")).encode()
        sig = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

        with (
            patch("otto.watcher.APP_SECRET", secret),
            patch("otto.watcher.detect_commitment", new_callable=AsyncMock, return_value=None),
        ):
            resp = client.post(
                "/webhook/whatsapp",
                content=payload,
                headers={"content-type": "application/json", "X-Hub-Signature-256": sig},
            )

        assert resp.status_code == 200

    def test_invalid_signature_rejected(self, client):
        secret = "test_secret_123"
        payload = json.dumps(_make_webhook_payload("hello")).encode()

        with patch("otto.watcher.APP_SECRET", secret):
            resp = client.post(
                "/webhook/whatsapp",
                content=payload,
                headers={"content-type": "application/json", "X-Hub-Signature-256": "sha256=wrong"},
            )

        assert resp.status_code == 403

    def test_no_signature_when_secret_configured_rejected(self, client):
        secret = "test_secret_123"
        payload = json.dumps(_make_webhook_payload("hello")).encode()

        with patch("otto.watcher.APP_SECRET", secret):
            resp = client.post(
                "/webhook/whatsapp",
                content=payload,
                headers={"content-type": "application/json"},
            )

        assert resp.status_code == 403


# ------------------------------------------------------------------
# Rate limiting
# ------------------------------------------------------------------


class TestRateLimiting:
    def test_rate_limit_allows_normal_traffic(self, client):
        """Normal traffic under the limit should be accepted."""
        from otto.watcher import RateLimiter
        fresh = RateLimiter(max_requests=100, window_seconds=60)
        with patch("otto.watcher._rate_limiter", fresh):
            payload = _make_webhook_payload("hello")
            with patch("otto.watcher.detect_commitment", new_callable=AsyncMock, return_value=None):
                resp = client.post("/webhook/whatsapp", json=payload)
            assert resp.status_code == 200

    def test_rate_limit_blocks_excessive_traffic(self, client):
        """Traffic exceeding the limit should return 429."""
        from otto.watcher import RateLimiter
        tight = RateLimiter(max_requests=3, window_seconds=60)

        payload = _make_webhook_payload("hello")

        with (
            patch("otto.watcher._rate_limiter", tight),
            patch("otto.watcher.detect_commitment", new_callable=AsyncMock, return_value=None),
        ):
            for _ in range(3):
                resp = client.post("/webhook/whatsapp", json=payload)
                assert resp.status_code == 200

            # 4th request should be rate limited
            resp = client.post("/webhook/whatsapp", json=payload)
            assert resp.status_code == 429

    def test_rate_limiter_persistence(self, tmp_path):
        """Rate limit state persists across instances (same DB)."""
        from otto.watcher import RateLimiter
        db = str(tmp_path / "rate.db")
        limiter1 = RateLimiter(db_path=db, max_requests=3, window_seconds=60)
        assert limiter1.allow("1.2.3.4")
        assert limiter1.allow("1.2.3.4")
        assert limiter1.allow("1.2.3.4")
        assert not limiter1.allow("1.2.3.4")  # 4th blocked

        # New instance, same DB
        limiter2 = RateLimiter(db_path=db, max_requests=3, window_seconds=60)
        assert not limiter2.allow("1.2.3.4")  # Still blocked
