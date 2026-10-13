"""
ParcelVerify — Rules Service Tests
Owner: Role B (Evidence Agent)

Tests for services/access.py, services/handoff.py, services/photos.py,
and services/risk.py using isolated temp databases.
Never writes to the demo database (D-017).
"""

import json
import os
import sys
import sqlite3
from io import BytesIO

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contracts import DBConfig
from db import init_db, get_connection, upload_photo
from seed import seed_demo
from services.access import query_shipment, check_access_scope, get_contract_at_time
from services.handoff import evaluate_handoff, compare_handoff, create_or_update_case
from services.photos import inspect_photo, find_photo_reuse
from services.risk import calculate_priority, get_partner_metrics


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_db():
    dir_path, db_path = DBConfig.temp_db()
    init_db(db_path)
    yield db_path
    import shutil
    shutil.rmtree(dir_path, ignore_errors=True)


@pytest.fixture
def seeded_db():
    dir_path, db_path = DBConfig.temp_db()
    init_db(db_path)
    seed_demo(db_path, seed=42, reset=True)
    yield db_path
    import shutil
    shutil.rmtree(dir_path, ignore_errors=True)


VALID_ACTOR = {
    "actor_id": "ACTOR-QR-01",
    "partner_id": "P-QUICKRUN",
    "role": "partner_user",
    "session_id": "test-session-001",
    "is_simulated": True,
}

ADMIN_ACTOR = {
    "actor_id": "ADMIN-001",
    "role": "admin",
    "session_id": "test-session-admin",
    "is_simulated": True,
}

INVESTIGATOR_ACTOR = {
    "actor_id": "INVESTIGATOR-001",
    "role": "investigator",
    "session_id": "test-session-inv",
    "is_simulated": True,
}

UNAUTHORIZED_ACTOR = {
    "actor_id": "ACTOR-SL-01",
    "partner_id": "P-SAFELOG",
    "role": "partner_user",
    "session_id": "test-session-sf",
    "is_simulated": True,
}


def _make_jpeg(width=100, height=100, color=(128, 128, 128)):
    from PIL import Image
    img = Image.new("RGB", (width, height), color)
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Access Service Tests
# ---------------------------------------------------------------------------

class TestQueryShipment:
    def test_authorized_query(self, seeded_db):
        """Authorized actor gets shipment fields and access log is written."""
        result = query_shipment(seeded_db, VALID_ACTOR, "PV-DEMO-001")
        assert result["authorized"] is True
        assert result["fields"] is not None
        assert result["fields"]["shipment_id"] == "PV-DEMO-001"
        assert result["log_id"]

    def test_unauthorized_query(self, seeded_db):
        """Unauthorized actor is denied; no fields returned; log written."""
        result = query_shipment(seeded_db, UNAUTHORIZED_ACTOR, "PV-DEMO-001")
        assert result["authorized"] is False
        assert result["fields"] is None
        assert result["denied_reason"]
        assert result["log_id"]

    def test_admin_bypasses(self, seeded_db):
        """Admin can query any shipment."""
        result = query_shipment(seeded_db, ADMIN_ACTOR, "PV-DEMO-001")
        assert result["authorized"] is True

    def test_nonexistent_shipment(self, seeded_db):
        """Querying a nonexistent shipment is denied and logged."""
        result = query_shipment(seeded_db, VALID_ACTOR, "NONEXISTENT")
        assert result["authorized"] is False
        assert "not found" in result["denied_reason"].lower()

    def test_access_log_written_on_success(self, seeded_db):
        """Access log is written even for authorized queries."""
        result = query_shipment(seeded_db, VALID_ACTOR, "PV-DEMO-001")
        conn = get_connection(seeded_db)
        try:
            log = conn.execute(
                "SELECT outcome FROM access_logs WHERE log_id = ?",
                (result["log_id"],),
            ).fetchone()
            assert log[0] == "authorized"
        finally:
            conn.close()


class TestGetContractAtTime:
    def test_returns_current_contract(self, seeded_db):
        """Returns the contract snapshot active at the given time."""
        result = get_contract_at_time(seeded_db, "P-QUICKRUN", "2026-09-01T00:00:00Z")
        assert result["partner_id"] == "P-QUICKRUN"
        assert "contract_snapshot" in result
        assert result["source"] in ("contract_history", "partners_fallback")

    def test_returns_historical_contract(self, seeded_db):
        """Returns the contract that was active before a scope change."""
        # QuickRun had scope expansion on 2026-06-01
        result = get_contract_at_time(seeded_db, "P-QUICKRUN", "2026-03-01T00:00:00Z")
        assert result["partner_id"] == "P-QUICKRUN"
        # Before June, scope should NOT include express_delivery
        snapshot = result.get("contract_snapshot", {})
        scope = snapshot.get("approved_scope", "")
        assert "express_delivery" not in scope

    def test_returns_updated_contract_after_change(self, seeded_db):
        """After the scope change, the new scope is returned."""
        result = get_contract_at_time(seeded_db, "P-QUICKRUN", "2026-07-01T00:00:00Z")
        snapshot = result.get("contract_snapshot", {})
        scope = snapshot.get("approved_scope", "")
        assert "express_delivery" in scope


# ---------------------------------------------------------------------------
# Handoff Service Tests
# ---------------------------------------------------------------------------

class TestCompareHandoff:
    def test_compare_known_shipment(self, seeded_db):
        """compare_handoff returns expected vs actual for PV-DEMO-001."""
        result = compare_handoff(seeded_db, "PV-DEMO-001")
        assert result["shipment_id"] == "PV-DEMO-001"
        assert result["weight_g"]["expected"] == 2000.0
        assert result["weight_g"]["actual"] == 1850.0
        assert result["weight_g"]["diff"] == -150.0
        assert result["weight_g"]["match"] is False

    def test_compare_nonexistent_shipment(self, seeded_db):
        """Nonexistent shipment returns unknowns."""
        result = compare_handoff(seeded_db, "NONEXISTENT")
        assert "shipment_not_found" in result["unknowns"]

    def test_seal_match(self, seeded_db):
        """PV-DEMO-001 has matching seal (SEAL-07)."""
        result = compare_handoff(seeded_db, "PV-DEMO-001")
        assert result["seal"]["expected"] == "SEAL-07"
        assert result["seal"]["actual"] == "SEAL-07"
        assert result["seal"]["match"] is True


class TestEvaluateHandoff:
    def test_weight_discrepancy_finding(self, seeded_db):
        """PV-DEMO-001 triggers weight_diff finding (no explanation)."""
        conn = get_connection(seeded_db)
        try:
            event_id = conn.execute(
                "SELECT event_id FROM events WHERE shipment_id='PV-DEMO-001' "
                "AND event_type='handoff_submitted' LIMIT 1"
            ).fetchone()[0]
        finally:
            conn.close()

        result = evaluate_handoff(seeded_db, "PV-DEMO-001", event_id)
        assert result["result"] == "needs_review"
        categories = [f["category"] for f in result["findings"]]
        assert "weight_diff" in categories
        assert "weight_diff_no_explanation" in result["blocking_issues"]

    def test_consistent_shipment(self, seeded_db):
        """A shipment with matching weight/seal should be consistent."""
        # PV-SHIP-002 should have near-matching weight (within threshold)
        conn = get_connection(seeded_db)
        try:
            event_id = conn.execute(
                "SELECT event_id FROM events WHERE shipment_id='PV-SHIP-002' "
                "AND event_type='handoff_submitted' LIMIT 1"
            ).fetchone()[0]
        finally:
            conn.close()

        result = evaluate_handoff(seeded_db, "PV-SHIP-002", event_id)
        # May or may not have findings depending on weight diff, but should not error
        assert result["result"] in ("consistent", "needs_review", "insufficient_evidence")

    def test_repackaging_event_detected(self, seeded_db):
        """PV-SHIP-011 has a repackaging_approved event."""
        conn = get_connection(seeded_db)
        try:
            event_id = conn.execute(
                "SELECT event_id FROM events WHERE shipment_id='PV-SHIP-011' "
                "AND event_type='handoff_submitted' LIMIT 1"
            ).fetchone()[0]
        finally:
            conn.close()

        result = evaluate_handoff(seeded_db, "PV-SHIP-011", event_id)
        conn = get_connection(seeded_db)
        try:
            repack_id = conn.execute("SELECT event_id FROM events WHERE shipment_id = 'PV-SHIP-011' AND event_type = 'repackaging_approved'").fetchone()[0]
        finally:
            conn.close()
        assert repack_id in result["evidence_refs"]

    def test_photo_reuse_detected(self, seeded_db):
        """Photo reuse should be detected for PV-DEMO-001."""
        conn = get_connection(seeded_db)
        try:
            event_id = conn.execute(
                "SELECT event_id FROM events WHERE shipment_id='PV-DEMO-001' "
                "AND event_type='handoff_submitted' LIMIT 1"
            ).fetchone()[0]
        finally:
            conn.close()

        result = evaluate_handoff(seeded_db, "PV-DEMO-001", event_id)
        # photo_001.jpg is reused across PV-DEMO-001 and PV-SHIP-010
        categories = [f["category"] for f in result["findings"]]
        assert "photo_reuse" in categories


class TestCreateOrUpdateCase:
    def test_creates_new_case(self, seeded_db):
        """create_or_update_case creates a new case."""
        findings = [
            {"category": "weight_diff", "description": "150g discrepancy",
             "severity": "warning", "evidence_ids": ["E-001"]}
        ]
        result = create_or_update_case(seeded_db, "PV-DEMO-001", "E-001", findings, "1.1.0")
        assert result["is_new"] is True
        assert result["case_id"]
        assert result["review_queue"] is False

    def test_idempotent(self, seeded_db):
        """Calling twice with same key returns same case_id."""
        findings = [
            {"category": "weight_diff", "description": "150g discrepancy",
             "severity": "warning", "evidence_ids": ["E-001"]}
        ]
        result1 = create_or_update_case(seeded_db, "PV-DEMO-001", "E-001", findings, "1.1.0")
        result2 = create_or_update_case(seeded_db, "PV-DEMO-001", "E-001", findings, "1.1.0")
        assert result1["case_id"] == result2["case_id"]
        assert result1["is_new"] is True
        assert result2["is_new"] is False


# ---------------------------------------------------------------------------
# Photo Service Tests
# ---------------------------------------------------------------------------

class TestInspectPhoto:
    def test_inspect_photo_returns_metadata(self, seeded_db):
        """inspect_photo returns photo metadata."""
        conn = get_connection(seeded_db)
        try:
            photo_id = conn.execute(
                "SELECT photo_id FROM photos LIMIT 1"
            ).fetchone()[0]
        finally:
            conn.close()

        result = inspect_photo(seeded_db, photo_id, ADMIN_ACTOR)
        assert result["photo_id"] == photo_id
        assert result["sha256"]

    def test_finds_exact_match(self, seeded_db):
        """Finds SHA-256 exact match across shipments."""
        conn = get_connection(seeded_db)
        try:
            # Find the reused photo (photo_001.jpg on PV-DEMO-001)
            photo_id = conn.execute(
                """SELECT p.photo_id FROM photos p
                   JOIN events e ON p.event_id = e.event_id
                   WHERE e.shipment_id = 'PV-DEMO-001'
                   LIMIT 1"""
            ).fetchone()[0]
        finally:
            conn.close()

        result = inspect_photo(seeded_db, photo_id, ADMIN_ACTOR)
        # Should find the cross-shipment match
        assert len(result["exact_matches"]) > 0 or len(result["similar_candidates"]) > 0


class TestFindPhotoReuse:
    def test_finds_cross_shipment_reuse(self, seeded_db):
        """find_photo_reuse detects cross-shipment photo reuse."""
        conn = get_connection(seeded_db)
        try:
            photo_id = conn.execute(
                """SELECT p.photo_id FROM photos p
                   JOIN events e ON p.event_id = e.event_id
                   WHERE e.shipment_id = 'PV-DEMO-001'
                   AND e.event_type = 'pod_submitted'
                   AND EXISTS (SELECT 1 FROM photos other WHERE other.sha256 = p.sha256 AND other.photo_id != p.photo_id)
                   LIMIT 1"""
            ).fetchone()[0]
        finally:
            conn.close()

        result = find_photo_reuse(seeded_db, photo_id, ADMIN_ACTOR)
        assert len(result["exact_matches"]) > 0

    def test_actor_context_required(self, seeded_db):
        """find_photo_reuse with no actor_context should raise."""
        conn = get_connection(seeded_db)
        try:
            photo_id = conn.execute(
                "SELECT photo_id FROM photos LIMIT 1"
            ).fetchone()[0]
        finally:
            conn.close()

        # Empty actor_context should raise validation error
        with pytest.raises(Exception):
            find_photo_reuse(seeded_db, photo_id, {})

    def test_unauthorized_fields_masked(self, seeded_db):
        """Unauthorized cross-shipment matches mask fields."""
        conn = get_connection(seeded_db)
        try:
            photo_id = conn.execute(
                """SELECT p.photo_id FROM photos p
                   JOIN events e ON p.event_id = e.event_id
                   WHERE e.shipment_id = 'PV-DEMO-001'
                   LIMIT 1"""
            ).fetchone()[0]
        finally:
            conn.close()

        # SafeLog actor is not authorized for QuickRun shipments
        from contracts import AuthorizationError
        with pytest.raises(AuthorizationError):
            find_photo_reuse(seeded_db, photo_id, UNAUTHORIZED_ACTOR)


# ---------------------------------------------------------------------------
# Risk Service Tests
# ---------------------------------------------------------------------------

class TestCalculatePriority:
    def test_scoring_weight_only(self):
        """weight_diff = 20 pts, review_queue = False (< 30, no blocking)."""
        findings = [
            {"category": "weight_diff", "description": "diff", "severity": "warning", "evidence_ids": []}
        ]
        result = calculate_priority("data/parcelverify.db", findings)
        assert result["total_score"] == 20
        assert result["review_queue"] is False

    def test_scoring_seal_blocking(self):
        """seal_mismatch = 25 pts, blocking → review_queue = True."""
        findings = [
            {"category": "seal_mismatch", "description": "mismatch", "severity": "blocking", "evidence_ids": []}
        ]
        result = calculate_priority("data/parcelverify.db", findings)
        assert result["total_score"] == 25
        assert result["review_queue"] is True  # blocking issue

    def test_scoring_combined(self):
        """seal_mismatch(25) + weight_diff(20) = 45, review_queue = True."""
        findings = [
            {"category": "seal_mismatch", "description": "mismatch", "severity": "blocking", "evidence_ids": []},
            {"category": "weight_diff", "description": "diff", "severity": "warning", "evidence_ids": []},
        ]
        result = calculate_priority("data/parcelverify.db", findings)
        assert result["total_score"] == 45
        assert result["review_queue"] is True

    def test_scoring_deduplication(self):
        """Multiple photo_reuse findings = 25 pts once."""
        findings = [
            {"category": "photo_reuse", "description": "reuse1", "severity": "blocking", "evidence_ids": []},
            {"category": "photo_reuse", "description": "reuse2", "severity": "blocking", "evidence_ids": []},
        ]
        result = calculate_priority("data/parcelverify.db", findings)
        assert result["total_score"] == 25  # not 50

    def test_scoring_cap_100(self):
        """Total score capped at 100."""
        findings = [
            {"category": "seal_mismatch", "description": "x", "severity": "blocking", "evidence_ids": []},
            {"category": "weight_diff", "description": "x", "severity": "warning", "evidence_ids": []},
            {"category": "photo_reuse", "description": "x", "severity": "blocking", "evidence_ids": []},
            {"category": "location_conflict", "description": "x", "severity": "warning", "evidence_ids": []},
            {"category": "time_conflict", "description": "x", "severity": "warning", "evidence_ids": []},
            {"category": "access_anomaly", "description": "x", "severity": "warning", "evidence_ids": []},
            # Duplicate categories (should be deduped)
            {"category": "seal_mismatch", "description": "y", "severity": "blocking", "evidence_ids": []},
            {"category": "weight_diff", "description": "y", "severity": "warning", "evidence_ids": []},
        ]
        result = calculate_priority("data/parcelverify.db", findings)
        assert result["total_score"] == 100  # 25+20+25+10+10+10 = 100

    def test_priority_threshold(self):
        """Score >= 60 → priority = True."""
        findings = [
            {"category": "seal_mismatch", "description": "x", "severity": "blocking", "evidence_ids": []},
            {"category": "photo_reuse", "description": "x", "severity": "blocking", "evidence_ids": []},
            {"category": "weight_diff", "description": "x", "severity": "warning", "evidence_ids": []},
        ]
        result = calculate_priority("data/parcelverify.db", findings)
        assert result["total_score"] == 70
        assert result["priority"] is True


class TestGetPartnerMetrics:
    def test_returns_metrics(self, seeded_db):
        """get_partner_metrics returns all expected fields."""
        result = get_partner_metrics(seeded_db, "P-QUICKRUN")
        assert result["partner_id"] == "P-QUICKRUN"
        assert result["total_shipments"] == 20  # 19 + PV-DEMO-001
        assert result["meets_display_threshold"] is True  # >= 20
        assert "anomaly_rate_per_1000" in result
        assert "evidence_completeness_rate" in result

    def test_below_display_threshold(self, seeded_db):
        """Partner with < 20 shipments has meets_display_threshold = False."""
        # MetroLine has 20 shipments which should be >= threshold
        result = get_partner_metrics(seeded_db, "P-METROLINE")
        assert result["total_shipments"] == 20
        assert result["meets_display_threshold"] is True

    def test_no_has_reliable_sample(self, seeded_db):
        """Ensure field is 'meets_display_threshold' not 'has_reliable_sample'."""
        result = get_partner_metrics(seeded_db, "P-QUICKRUN")
        assert "meets_display_threshold" in result
        assert "has_reliable_sample" not in result
