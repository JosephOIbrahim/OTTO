"""Security tests for the WhatsApp watcher."""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from otto.watcher import app


@pytest.fixture()
def client():
    return TestClient(app)


class TestSecurityHardening:

    def test_missing_verify_token_returns_503(self, client):
        """Webhook verify returns 503 when WHATSAPP_VERIFY_TOKEN not configured."""
        with patch("otto.watcher.VERIFY_TOKEN", ""):
            resp = client.get("/webhook/whatsapp", params={
                "hub.mode": "subscribe",
                "hub.verify_token": "",
                "hub.challenge": "test_challenge",
            })
        assert resp.status_code == 503

    def test_production_requires_app_secret(self):
        """main() exits when OTTO_ENV=production and no APP_SECRET."""
        with (
            patch("otto.watcher.OTTO_ENV", "production"),
            patch("otto.watcher.APP_SECRET", ""),
        ):
            with pytest.raises(SystemExit):
                from otto.watcher import main
                main()

    def test_verify_token_not_logged_in_full(self, caplog):
        """Full verify token should never appear in logs."""
        test_token = "super_secret_token_12345"
        with (
            patch("otto.watcher.VERIFY_TOKEN", test_token),
            patch("otto.watcher.OTTO_ENV", "development"),
            patch("otto.watcher.APP_SECRET", ""),
            patch("uvicorn.run"),  # Don't actually start the server
            caplog.at_level(logging.INFO),
        ):
            from otto.watcher import main
            main()

        # The full token should NOT appear in any log message
        for record in caplog.records:
            assert test_token not in record.getMessage(), (
                f"Full token leaked in log: {record.getMessage()}"
            )
