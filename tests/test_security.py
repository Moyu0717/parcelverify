"""Security regressions; all data is seeded into pytest temporary directories."""
import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from contracts import AuthorizationError, AuditError
from db import init_db, get_connection
from seed import seed_demo
from services.access import query_shipment
from services.photos import find_photo_reuse
from services.actions import propose_action, review_action, execute_action
from services.audit import export_audit
from services.handoff import create_or_update_case, evaluate_handoff
from services.risk import calculate_priority, get_partner_metrics

PARTNER = dict(actor_id="ACTOR-QR-01", partner_id="P-QUICKRUN", role="partner_user", session_id="test")
ADMIN = dict(actor_id="ADMIN-001", role="admin", session_id="test")
APPROVER = dict(actor_id="arbitrary-approved-identity", role="approver", session_id="test")

@pytest.fixture
def database(tmp_path):
    path = str(tmp_path / "security.db")
    init_db(path)
    seed_demo(path, seed=42, reset=True)
    return path

def sql(path, statement, parameters=()):
    conn = get_connection(path)
    try:
        result = conn.execute(statement, parameters).fetchall()
        conn.commit()
        return result
    finally:
        conn.close()

def approved(path):
    case = create_or_update_case(path, "PV-DEMO-001", "test-trigger", [])
    action = propose_action(path, case["case_id"], "request_reweigh", ADMIN)
    review_action(path, action["action_id"], "approve", APPROVER)
    return case["case_id"], action["action_id"]

def test_past_timestamp_cannot_restore_live_access(database):
    sql(database, "UPDATE assignments SET valid_until = '2026-10-01T00:00:00Z'")
    assert not query_shipment(database, PARTNER, "PV-DEMO-001", "2026-09-01T00:00:00Z")["authorized"]

def test_other_actor_cannot_share_partner_assignment(database):
    actor = dict(PARTNER, actor_id="unassigned")
    assert not query_shipment(database, actor, "PV-DEMO-001")["authorized"]

def test_expired_contract_denies_read_and_photo(database):
    sql(database, "UPDATE partners SET contract_end = '2020-01-01T00:00:00Z' WHERE partner_id = 'P-QUICKRUN'")
    assert not query_shipment(database, PARTNER, "PV-DEMO-001")["authorized"]
    photo = sql(database, "SELECT p.photo_id FROM photos p JOIN events e ON e.event_id = p.event_id WHERE e.shipment_id = 'PV-DEMO-001'")[0][0]
    with pytest.raises(AuthorizationError):
        find_photo_reuse(database, photo, PARTNER)

def test_approver_internal_read_and_export_requires_context(database):
    assert query_shipment(database, APPROVER, "PV-DEMO-001")["authorized"]
    with pytest.raises(AuthorizationError):
        export_audit(database)

def test_execution_requires_current_role(database):
    _, action = approved(database)
    with pytest.raises(AuthorizationError):
        execute_action(database, action, PARTNER)
    assert sql(database, "SELECT status FROM action_requests WHERE action_id = ?", (action,))[0][0] == "approved"

def test_execution_expiry_uses_instant(database):
    _, action = approved(database)
    sql(database, "UPDATE action_requests SET expires_at = '2020-01-01T00:00:00+08:00' WHERE action_id = ?", (action,))
    assert execute_action(database, action, ADMIN)["status"] == "expired"

def test_audit_failure_rolls_back_business_change(database, monkeypatch):
    case, action = approved(database)
    before = sql(database, "SELECT status FROM case_records WHERE case_id = ?", (case,))[0][0]
    def fail(*args, **kwargs):
        raise AuditError("injected failure")
    monkeypatch.setattr("services.actions.append_audit", fail)
    assert execute_action(database, action, ADMIN)["status"] == "failed"
    assert sql(database, "SELECT status FROM case_records WHERE case_id = ?", (case,))[0][0] == before
    assert not sql(database, "SELECT 1 FROM audit_log WHERE operation = 'action_executed'")

def test_concurrent_execution_is_once(database):
    _, action = approved(database)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: execute_action(database, action, ADMIN)["status"], range(2)))
    assert sorted(results) == ["already_executed", "executed"]
    assert len(sql(database, "SELECT 1 FROM audit_log WHERE operation = 'action_executed'")) == 1

def test_missing_handoff_does_not_manufacture_score(database):
    sql(database, "DELETE FROM photos WHERE event_id IN (SELECT event_id FROM events WHERE shipment_id = 'PV-SHIP-002')")
    sql(database, "DELETE FROM events WHERE shipment_id = 'PV-SHIP-002'")
    result = evaluate_handoff(database, "PV-SHIP-002")
    assert result["result"] == "insufficient_evidence"
    assert calculate_priority(database, result["findings"])["total_score"] == 0

def test_metrics_union_unique_affected_shipments(database):
    sql(database, "DELETE FROM case_records")
    sql(database, "DELETE FROM access_logs")
    create_or_update_case(database, "PV-DEMO-001", "metric-trigger", [dict(category="weight_diff", description="diff", severity="warning")])
    query_shipment(database, dict(PARTNER, actor_id="no-access"), "PV-SHIP-002")
    metrics = get_partner_metrics(database, "P-QUICKRUN")
    assert metrics["anomaly_count"] == 2
    assert metrics["sample_size"] == 20
    assert metrics["anomaly_rate_per_1000"] == 100


def test_repackaging_measurements_explain_only_weight(database):
    handoff = sql(database, "SELECT event_id FROM events WHERE shipment_id = 'PV-DEMO-001' AND event_type = 'handoff_submitted'")[0][0]
    for name, weight in (("measure-before", 2000), ("measure-after", 1850)):
        sql(database, "INSERT INTO events (event_id, shipment_id, event_type, occurred_at, received_at, source, payload_json) VALUES (?, 'PV-DEMO-001', 'reweigh_submitted', ?, '2026-10-12T00:00:00Z', ?, ?)", (name, "2026-10-12T00:00:00Z", name, json.dumps(dict(weight_g=weight))))
    payload = dict(approver_id="APPROVER-001", handoff_event_id=handoff, weight_diff_g=150, supporting_measurement_ids=["measure-before", "measure-after"])
    sql(database, "INSERT INTO events (event_id, shipment_id, event_type, occurred_at, received_at, source, payload_json) VALUES ('supported-repack', 'PV-DEMO-001', 'repackaging_approved', '2026-10-12T00:00:00Z', '2026-10-12T00:00:00Z', 'test', ?)", (json.dumps(payload),))
    result = evaluate_handoff(database, "PV-DEMO-001", handoff)
    categories = {f["category"] for f in result["findings"]}
    assert "weight_diff" not in categories
    assert "photo_reuse" in categories
    assert "measure-after" in result["evidence_refs"]
    payload["handoff_event_id"] = "unrelated"
    sql(database, "UPDATE events SET payload_json = ? WHERE event_id = 'supported-repack'", (json.dumps(payload),))
    assert "weight_diff" in {f["category"] for f in evaluate_handoff(database, "PV-DEMO-001", handoff)["findings"]}


def test_internal_read_is_not_assignment_violation(database):
    from services.access import check_access_scope
    case = create_or_update_case(database, "PV-SHIP-002", "internal-read", [])
    query_shipment(database, APPROVER, "PV-SHIP-002")
    result = check_access_scope(database, case["case_id"], APPROVER)
    assert result["authorized"]
    assert not any(v["type"] == "missing_assignment" and "arbitrary-approved-identity" in v["detail"] for v in result["violations"])


def add_event(path, event_id, event_type, payload, occurred="2026-10-10T12:00:00Z", shipment="PV-DEMO-001"):
    sql(path, "INSERT INTO events (event_id, shipment_id, event_type, occurred_at, received_at, source, payload_json) VALUES (?, ?, ?, ?, '2026-10-12T12:00:00Z', ?, ?)", (event_id, shipment, event_type, occurred, event_id, json.dumps(payload)))

def test_scoped_handoff_photo_findings_hide_unassigned_ids(database):
    sql(database, "DELETE FROM assignments WHERE shipment_id = 'PV-SHIP-010'")
    foreign_photos = [row[0] for row in sql(database, "SELECT p.photo_id FROM photos p JOIN events e ON p.event_id=e.event_id WHERE e.shipment_id = 'PV-SHIP-010'")]
    handoff = sql(database, "SELECT event_id FROM events WHERE shipment_id='PV-DEMO-001' AND event_type='handoff_submitted'")[0][0]
    result = evaluate_handoff(database, "PV-DEMO-001", handoff, PARTNER)
    encoded = json.dumps(result)
    assert "PV-SHIP-010" not in encoded
    assert not any(photo in encoded for photo in foreign_photos)
    assert any(f["category"] == "photo_reuse" for f in result["findings"])
    with pytest.raises(AuthorizationError):
        evaluate_handoff(database, "PV-SHIP-010", actor_context=PARTNER)

def test_collection_measurement_is_compared(database):
    add_event(database, "collection-rule", "collection_submitted", dict(weight_g=1800, count=100, seal_id="SEAL-07"))
    result = evaluate_handoff(database, "PV-DEMO-001", "collection-rule")
    assert any(f["category"] == "weight_diff" for f in result["findings"])
    assert "handoff_weight" not in result["missing_evidence"]

def test_pod_inherits_preceding_handoff_and_exact_recipient(database):
    from services.handoff import compare_handoff
    add_event(database, "auth-name", "recipient_authorization", dict(recipient_name="Alice"), "2026-10-10T11:00:00Z")
    add_event(database, "pod-name", "pod_submitted", dict(recipient_name="Bob", location_lat=None, location_lon=None), "2026-10-10T13:00:00Z")
    comparison = compare_handoff(database, "PV-DEMO-001", "pod-name")
    assert comparison["weight_g"]["actual"] == 1850
    assert comparison["recipient"]["authorized"] is False
    result = evaluate_handoff(database, "PV-DEMO-001", "pod-name")
    assert any(f["category"] == "id_conflict" for f in result["findings"])
    assert "actual_gps" in result["missing_evidence"]
    add_event(database, "future-auth", "recipient_authorization", dict(recipient_name="Bob"), "2026-10-11T13:00:00Z")
    assert compare_handoff(database, "PV-DEMO-001", "pod-name")["recipient"]["authorized"] is False

def test_missing_recipient_authorization_is_unknown(database):
    from services.handoff import compare_handoff
    sql(database, "DELETE FROM events WHERE shipment_id='PV-DEMO-001' AND event_type='recipient_authorization'")
    add_event(database, "pod-no-auth", "pod_submitted", dict(recipient_name="Bob"))
    comparison = compare_handoff(database, "PV-DEMO-001", "pod-no-auth")
    assert comparison["recipient"]["authorized"] is None
    assert not any(f["category"] == "id_conflict" for f in evaluate_handoff(database, "PV-DEMO-001", "pod-no-auth")["findings"])

def test_valid_gross_gps_and_clock_conflicts(database):
    add_event(database, "pod-far", "pod_submitted", dict(recipient_name="Bob", location_lat=50.0, location_lon=10.0), "2026-10-15T13:00:00Z")
    categories = {f["category"] for f in evaluate_handoff(database, "PV-DEMO-001", "pod-far")["findings"]}
    assert {"location_conflict", "time_conflict"} <= categories
    sql(database, "UPDATE events SET payload_json = ? WHERE event_id='pod-far'", (json.dumps(dict(recipient_name="Bob", location_lat=50.0, location_lon=10.0, gps_accuracy_m=5000)),))
    result = evaluate_handoff(database, "PV-DEMO-001", "pod-far")
    assert "actual_gps" in result["missing_evidence"]
    assert not any(f["category"] == "location_conflict" for f in result["findings"])


def test_pod_before_dispatch_is_time_conflict(database):
    add_event(database, "pod-too-early", "pod_submitted", dict(recipient_name="Bob"), "2026-08-01T12:00:00Z")
    result = evaluate_handoff(database, "PV-DEMO-001", "pod-too-early")
    assert any(f["category"] == "time_conflict" for f in result["findings"])
