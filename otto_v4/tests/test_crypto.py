"""Tests for field-level encryption module."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from otto.crypto import decrypt_field, encrypt_field, load_or_create_key
from otto.models import Commitment
from otto.store import CommitmentStore


class TestCryptoRoundtrip:

    def test_roundtrip_encryption(self):
        """Encrypt then decrypt returns original plaintext."""
        key = os.urandom(32)
        plaintext = "send the report to Sarah by Friday"
        encrypted = encrypt_field(plaintext, key)
        decrypted = decrypt_field(encrypted, key)
        assert decrypted == plaintext

    def test_different_nonces(self):
        """Same plaintext + key produces different ciphertext each time."""
        key = os.urandom(32)
        plaintext = "same message"
        ct1 = encrypt_field(plaintext, key)
        ct2 = encrypt_field(plaintext, key)
        assert ct1 != ct2  # Different nonces

    def test_wrong_key_fails(self):
        """Decrypt with wrong key raises an error."""
        key1 = os.urandom(32)
        key2 = os.urandom(32)
        encrypted = encrypt_field("secret", key1)
        with pytest.raises(Exception):  # cryptography raises InvalidTag
            decrypt_field(encrypted, key2)

    def test_empty_string_roundtrip(self):
        """Empty string encrypts to empty string."""
        key = os.urandom(32)
        assert encrypt_field("", key) == ""
        assert decrypt_field("", key) == ""

    def test_unicode_roundtrip(self):
        """Unicode text survives encrypt/decrypt cycle."""
        key = os.urandom(32)
        plaintext = "meeting with cafe schedule"
        encrypted = encrypt_field(plaintext, key)
        assert decrypt_field(encrypted, key) == plaintext

    def test_none_like_empty(self):
        """None-ish values handled gracefully."""
        key = os.urandom(32)
        assert encrypt_field("", key) == ""
        assert decrypt_field("", key) == ""


class TestKeyFile:

    def test_key_file_creation(self, tmp_path):
        """Creates key file when it doesn't exist."""
        key_path = str(tmp_path / "test.key")
        key = load_or_create_key(key_path)
        assert len(key) == 32
        assert Path(key_path).exists()

    def test_key_file_reuse(self, tmp_path):
        """Loading twice returns the same key."""
        key_path = str(tmp_path / "test.key")
        key1 = load_or_create_key(key_path)
        key2 = load_or_create_key(key_path)
        assert key1 == key2

    def test_key_file_in_subdirectory(self, tmp_path):
        """Creates parent directories if needed."""
        key_path = str(tmp_path / "sub" / "dir" / "test.key")
        key = load_or_create_key(key_path)
        assert len(key) == 32
        assert Path(key_path).exists()


class TestStoreEncryption:

    def test_store_encrypted_roundtrip(self, tmp_path):
        """Store with encryption key: add then get returns original data."""
        key = os.urandom(32)
        db_path = str(tmp_path / "enc.db")
        s = CommitmentStore(db_path=db_path, encryption_key=key)

        c = Commitment(
            raw_message="I'll send the report",
            commitment_text="send the report",
            who_to="Sarah",
            source_chat="test",
        )
        cid = s.add(c, dedup=False)

        result = s.get(cid)
        assert result is not None
        assert result.raw_message == "I'll send the report"
        assert result.commitment_text == "send the report"
        assert result.who_to == "Sarah"
        assert result.source_chat == "test"

    def test_store_unencrypted_backward_compat(self, tmp_path):
        """Store works without encryption key (existing behavior)."""
        db_path = str(tmp_path / "plain.db")
        s = CommitmentStore(db_path=db_path)

        c = Commitment(
            raw_message="I'll do it",
            commitment_text="do it",
            who_to="Bob",
            source_chat="cli",
        )
        cid = s.add(c, dedup=False)

        result = s.get(cid)
        assert result is not None
        assert result.commitment_text == "do it"

    def test_encrypted_fields_not_plaintext_in_db(self, tmp_path):
        """Raw SQL SELECT shows encrypted data, not plaintext."""
        key = os.urandom(32)
        db_path = str(tmp_path / "enc2.db")
        s = CommitmentStore(db_path=db_path, encryption_key=key)

        c = Commitment(
            raw_message="secret message here",
            commitment_text="secret commitment",
            who_to="SecretPerson",
            source_chat="secret_chat",
            sender_phone="+15551234567",
        )
        cid = s.add(c, dedup=False)

        # Read raw from SQLite
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT raw_message, commitment_text, who_to, source_chat, sender_phone "
            "FROM commitments WHERE id = ?",
            (cid,),
        ).fetchone()
        conn.close()

        assert row[0] != "secret message here"
        assert row[1] != "secret commitment"
        assert row[2] != "SecretPerson"
        assert row[3] != "secret_chat"
        assert row[4] != "+15551234567"

    def test_encrypted_sender_phone_none(self, tmp_path):
        """Encryption handles None sender_phone correctly."""
        key = os.urandom(32)
        db_path = str(tmp_path / "enc3.db")
        s = CommitmentStore(db_path=db_path, encryption_key=key)

        c = Commitment(
            raw_message="test msg",
            commitment_text="do thing",
            who_to="Someone",
            source_chat="cli",
            sender_phone=None,
        )
        cid = s.add(c, dedup=False)

        result = s.get(cid)
        assert result is not None
        assert result.sender_phone is None or result.sender_phone == ""

    def test_get_active_with_encryption(self, tmp_path):
        """get_active returns decrypted commitments."""
        key = os.urandom(32)
        db_path = str(tmp_path / "enc4.db")
        s = CommitmentStore(db_path=db_path, encryption_key=key)

        c = Commitment(
            raw_message="active test",
            commitment_text="stay active",
            who_to="Alice",
            source_chat="test",
        )
        s.add(c, dedup=False)

        active = s.get_active()
        assert len(active) == 1
        assert active[0].commitment_text == "stay active"
        assert active[0].who_to == "Alice"

    def test_is_encrypted_column_set(self, tmp_path):
        """is_encrypted column is 1 when encryption is active."""
        key = os.urandom(32)
        db_path = str(tmp_path / "enc5.db")
        s = CommitmentStore(db_path=db_path, encryption_key=key)

        c = Commitment(
            raw_message="check flag",
            commitment_text="flag test",
            who_to="Bob",
            source_chat="test",
        )
        cid = s.add(c, dedup=False)

        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT is_encrypted FROM commitments WHERE id = ?", (cid,)
        ).fetchone()
        conn.close()
        assert row[0] == 1

    def test_unencrypted_is_encrypted_column_zero(self, tmp_path):
        """is_encrypted column is 0 when no encryption key."""
        db_path = str(tmp_path / "plain2.db")
        s = CommitmentStore(db_path=db_path)

        c = Commitment(
            raw_message="plain",
            commitment_text="plain text",
            who_to="Eve",
            source_chat="test",
        )
        cid = s.add(c, dedup=False)

        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT is_encrypted FROM commitments WHERE id = ?", (cid,)
        ).fetchone()
        conn.close()
        assert row[0] == 0
