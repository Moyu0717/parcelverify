"""Stage-local evidence presentation and submission validation; isolated synthetic data."""
import json

import pytest

from contracts import DBConfig
from db import init_db, get_connection
from seed import seed_demo
from services.handoff import compare_handoff, evidence_fields, validate_evidence_fields


def test_hub_location_does_not_inherit_delivery_destination():
    directory, path = DBConfig.temp_db()
    try:
        init_db(path)
        seed_demo(path)
        result = compare_handoff(path, "PV-DEMO-001")
        with get_connection(path) as conn:
            event = conn.execute("SELECT event_type,payload_json FROM events WHERE event_id=?", (result["measurement_event_id"],)).fetchone()
        assert result["location"]["actual"] == json.loads(event[1]).get("handoff_location")
        assert result["location"]["expected"] is None
        assert result["location"]["match"] is None
        assert result["location"]["custodian"] is None
    finally:
        import shutil
        shutil.rmtree(directory)


def test_stage_expectation_and_existing_delivery_receiver():
    facts = evidence_fields({"event_type": "pod_submitted", "payload_json": {
        "handoff_location": " Hub B ", "expected_handoff_location": "hub b",
        "recipient_name": "Synthetic receiver", "sender_name": "Synthetic sender"}})
    assert facts["match"] is True
    assert facts["receiver"] == "Synthetic receiver"
    assert facts["sender"] == "Synthetic sender"
    assert facts["custodian"] is None
    assert evidence_fields({})["status"] == "Missing recorded location"
    assert evidence_fields({"payload_json": {"handoff_location": "Hub B"}})["status"] == "Recorded — not verified"


@pytest.mark.parametrize("payload", [{"weight_g": -1}, {"weight_g": float("nan")},
    {"weight_g": float("inf")}, {"weight_g": "1850"}, {"count": -1},
    {"count": 1.5}, {"count": True}])
def test_invalid_measurements_rejected(payload):
    with pytest.raises(ValueError):
        validate_evidence_fields(payload, "2026-09-04T12:00:00+08:00")


@pytest.mark.parametrize("timestamp", ["nonsense", "2026-09-04T12:00:00", "2026-02-30T12:00:00Z", None])
def test_invalid_or_ambiguous_event_times_rejected(timestamp):
    with pytest.raises(ValueError):
        validate_evidence_fields({}, timestamp)


def test_missing_measurements_and_future_source_times_remain_recordable():
    validate_evidence_fields({}, "2099-01-01T00:00:00+08:00")
    validate_evidence_fields({"weight_g": 0, "count": 0}, "2026-09-04T04:00:00Z")
