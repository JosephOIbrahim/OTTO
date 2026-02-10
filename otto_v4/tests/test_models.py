"""Tests for Commitment data model."""

from datetime import datetime, timezone

from otto.models import Commitment


def test_instantiation_defaults():
    c = Commitment(
        raw_message="I'll send it Monday",
        commitment_text="send it Monday",
        who_to="Alice",
        source_chat="Work Chat",
    )
    assert c.who_from == "me"
    assert c.status == "active"
    assert c.direction == "outbound"
    assert c.deadline is None
    assert c.deadline_source == "none"
    assert c.follow_up_count == 0
    assert len(c.id) == 36  # uuid4 format


def test_instantiation_all_fields():
    now = datetime.now(timezone.utc)
    c = Commitment(
        id="test-id",
        raw_message="I'll send the deck by Friday",
        commitment_text="send the deck",
        who_to="Bob",
        who_from="me",
        deadline=now,
        deadline_source="explicit",
        status="active",
        created_at=now,
        updated_at=now,
        follow_up_count=2,
        source_chat="Project Chat",
        direction="outbound",
    )
    assert c.id == "test-id"
    assert c.deadline == now
    assert c.follow_up_count == 2


def test_to_dict_from_dict_roundtrip():
    now = datetime.now(timezone.utc)
    original = Commitment(
        id="rt-id",
        raw_message="Will follow up with Sandra",
        commitment_text="follow up with Sandra",
        who_to="Sandra",
        who_from="me",
        deadline=now,
        deadline_source="inferred",
        status="active",
        created_at=now,
        updated_at=now,
        follow_up_count=1,
        source_chat="Friends",
        direction="outbound",
    )
    d = original.to_dict()
    restored = Commitment.from_dict(d)

    assert restored.id == original.id
    assert restored.raw_message == original.raw_message
    assert restored.commitment_text == original.commitment_text
    assert restored.who_to == original.who_to
    assert restored.who_from == original.who_from
    assert restored.deadline == original.deadline
    assert restored.deadline_source == original.deadline_source
    assert restored.status == original.status
    assert restored.created_at == original.created_at
    assert restored.updated_at == original.updated_at
    assert restored.follow_up_count == original.follow_up_count
    assert restored.source_chat == original.source_chat
    assert restored.direction == original.direction


def test_roundtrip_no_deadline():
    c = Commitment(
        raw_message="I'll handle it",
        commitment_text="handle it",
        who_to="unknown",
        source_chat="Random",
    )
    d = c.to_dict()
    assert d["deadline"] is None
    restored = Commitment.from_dict(d)
    assert restored.deadline is None
    assert restored.deadline_source == "none"
