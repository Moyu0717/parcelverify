"""
ParcelVerify — Data Layer Tests
Owner: Role A (Data Agent)

Tests for db.py and seed.py using isolated temp databases.
Never writes to the demo database (D-017).
"""

import os
import sys
import json
import sqlite3
import tempfile
import hashlib
from io import BytesIO

import pytest

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contracts import DBConfig
from db import init_db, get_connection, submit_event, upload_photo
from seed import seed_demo


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_db():
    """Create an isolated temp database for each test (D-017)."""
    dir_path, db_path = DBConfig.temp_db()
    init_db(db_path)
    yield db_path
    # Cleanup
    try:
        conn = sqlite3.connect(db_path)
        conn.close()
    except Exception:
        pass
    import shutil
    shutil.rmtree(dir_path, ignore_errors=True)


@pytest.fixture
def seeded_db():
    """Create a temp database and seed it with demo data."""
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


def _make_jpeg(width=100, height=100, color=(128, 128, 128)):
    """Create a small JPEG image as bytes."""
    from PIL import Image
    img = Image.new("RGB", (width, height), color)
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# init_db tests
# ---------------------------------------------------------------------------

class TestInitDb:
    def test_creates_tables(self, temp_db):
        """init_db should create all expected tables."""
        conn = get_connection(temp_db)
        try:
            tables = {
                row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            expected = {
                "partners", "contract_history", "shipments", "assignments",
                "events", "access_logs", "photos", "case_records",
                "evidence_tasks", "action_requests", "audit_log",
                "report_versions", "tool_executions",
            }
            assert expected.issubset(tables), f"Missing tables: {expected - tables}"
        finally:
            conn.close()

    def test_idempotent(self, temp_db):
        """init_db called twice should not error or destroy data."""
        # Seed some data
        seed_demo(temp_db, seed=42, reset=True)
        # Call init_db again
        init_db(temp_db)
        # Data should still be there
        conn = get_connection(temp_db)
        try:
            count = conn.execute("SELECT COUNT(*) FROM partners").fetchone()[0]
            assert count == 3
        finally:
            conn.close()

    def test_foreign_keys_enabled(self, temp_db):
        """Every connection must have foreign_keys pragma ON."""
        conn = get_connection(temp_db)
        try:
            result = conn.execute("PRAGMA foreign_keys").fetchone()
            assert result[0] == 1
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# submit_event tests
# ---------------------------------------------------------------------------

class TestSubmitEvent:
    def test_creates_event(self, seeded_db):
        """submit_event should create a new event."""
        result = submit_event(
            seeded_db, VALID_ACTOR, "PV-DEMO-001",
            "message_reported",
            {"message": "Test complaint", "channel": "sms"},
            "test_source",
            "2026-10-12T10:00:00Z",
        )
        assert result["is_new"] is True
        assert result["shipment_id"] == "PV-DEMO-001"
        assert result["event_type"] == "message_reported"
        assert result["received_at"]  # server-assigned

    def test_idempotent(self, seeded_db):
        """Duplicate submission returns the same event_id (D-016)."""
        result1 = submit_event(
            seeded_db, VALID_ACTOR, "PV-DEMO-001",
            "message_reported",
            {"message": "Test", "channel": "sms"},
            "test_source",
            "2026-10-12T10:00:00Z",
        )
        result2 = submit_event(
            seeded_db, VALID_ACTOR, "PV-DEMO-001",
            "message_reported",
            {"message": "Test", "channel": "sms"},
            "test_source",
            "2026-10-12T10:00:00Z",
        )
        assert result1["event_id"] == result2["event_id"]
        assert result1["is_new"] is True
        assert result2["is_new"] is False

    def test_unauthorized_actor_rejected(self, seeded_db):
        """Actor without assignment for the shipment is rejected (D-019)."""
        unauthorized = {
            "actor_id": "ACTOR-SL-01",
            "partner_id": "P-SAFELOG",
            "role": "partner_user",
            "session_id": "test-session-sf",
            "is_simulated": True,
        }
        with pytest.raises(Exception):
            submit_event(
                seeded_db, unauthorized, "PV-DEMO-001",
                "message_reported",
                {"message": "x", "channel": "sms"},
                "test_source",
                "2026-10-12T10:00:00Z",
            )

    def test_admin_bypasses_auth(self, seeded_db):
        """Admin role can submit events for any shipment."""
        result = submit_event(
            seeded_db, ADMIN_ACTOR, "PV-DEMO-001",
            "official_notice",
            {"notice": "Test notice"},
            "admin_source",
            "2026-10-12T11:00:00Z",
        )
        assert result["is_new"] is True


# ---------------------------------------------------------------------------
# upload_photo tests
# ---------------------------------------------------------------------------

class TestUploadPhoto:
    def test_uploads_photo(self, seeded_db):
        """upload_photo should store photo with SHA-256 and pHash."""
        # Get an event from seeded data
        conn = get_connection(seeded_db)
        try:
            event_id = conn.execute(
                "SELECT event_id FROM events WHERE shipment_id='PV-DEMO-001' "
                "AND event_type='handoff_submitted' LIMIT 1"
            ).fetchone()[0]
        finally:
            conn.close()

        file_bytes = _make_jpeg(200, 200, (255, 0, 0))
        result = upload_photo(
            seeded_db, VALID_ACTOR, event_id, file_bytes,
            claimed_capture_at="2026-10-12T02:15:00Z",
            manual_observation="Box appears intact",
        )
        assert result["is_new"] is True
        assert result["sha256"]
        assert result["phash"]
        assert os.path.exists(result["local_path"])

    def test_idempotent(self, seeded_db):
        """Same file for same event returns existing photo_id (D-016)."""
        conn = get_connection(seeded_db)
        try:
            event_id = conn.execute(
                "SELECT event_id FROM events WHERE shipment_id='PV-DEMO-001' "
                "AND event_type='pod_submitted' LIMIT 1"
            ).fetchone()[0]
        finally:
            conn.close()

        file_bytes = _make_jpeg(150, 150, (0, 255, 0))
        result1 = upload_photo(seeded_db, VALID_ACTOR, event_id, file_bytes)
        result2 = upload_photo(seeded_db, VALID_ACTOR, event_id, file_bytes)
        assert result1["photo_id"] == result2["photo_id"]
        assert result1["is_new"] is True
        assert result2["is_new"] is False

    def test_rejects_unauthorized(self, seeded_db):
        """Unauthorized actor cannot upload photo for another partner's event."""
        conn = get_connection(seeded_db)
        try:
            event_id = conn.execute(
                "SELECT event_id FROM events WHERE shipment_id='PV-DEMO-001' "
                "AND event_type='handoff_submitted' LIMIT 1"
            ).fetchone()[0]
        finally:
            conn.close()

        unauthorized = {
            "actor_id": "ACTOR-SL-01",
            "partner_id": "P-SAFELOG",
            "role": "partner_user",
            "session_id": "test-session-sf",
            "is_simulated": True,
        }
        file_bytes = _make_jpeg(100, 100)
        with pytest.raises(Exception):
            upload_photo(seeded_db, unauthorized, event_id, file_bytes)

    def test_rejects_oversized(self, seeded_db):
        """Photos over 10MB are rejected."""
        conn = get_connection(seeded_db)
        try:
            event_id = conn.execute(
                "SELECT event_id FROM events WHERE shipment_id='PV-DEMO-001' "
                "AND event_type='handoff_submitted' LIMIT 1"
            ).fetchone()[0]
        finally:
            conn.close()

        # 11MB of zeros (not a valid image, but size check comes first)
        big_bytes = b"\x00" * (11 * 1024 * 1024)
        with pytest.raises(ValueError, match="10MB"):
            upload_photo(seeded_db, VALID_ACTOR, event_id, big_bytes)


# ---------------------------------------------------------------------------
# seed_demo tests
# ---------------------------------------------------------------------------

class TestSeedDemo:
    def test_seeds_three_partners(self, seeded_db):
        """seed_demo creates exactly 3 partners."""
        conn = get_connection(seeded_db)
        try:
            partners = conn.execute(
                "SELECT partner_id FROM partners ORDER BY partner_id"
            ).fetchall()
            assert len(partners) == 3
            ids = [p[0] for p in partners]
            assert "P-QUICKRUN" in ids
            assert "P-SAFELOG" in ids
            assert "P-METROLINE" in ids
        finally:
            conn.close()

    def test_seeds_sixty_shipments(self, seeded_db):
        """seed_demo creates 60 shipments."""
        conn = get_connection(seeded_db)
        try:
            count = conn.execute("SELECT COUNT(*) FROM shipments").fetchone()[0]
            assert count == 60
        finally:
            conn.close()

    def test_pv_demo_001_scenario(self, seeded_db):
        """PV-DEMO-001 has expected 2000g, SEAL-07, and 1850g handoff."""
        conn = get_connection(seeded_db)
        try:
            ship = conn.execute(
                "SELECT expected_weight_g, expected_seal FROM shipments "
                "WHERE shipment_id='PV-DEMO-001'"
            ).fetchone()
            assert ship[0] == 2000.0
            assert ship[1] == "SEAL-07"

            # Handoff event should show 1850g
            handoff = conn.execute(
                "SELECT payload_json FROM events "
                "WHERE shipment_id='PV-DEMO-001' AND event_type='handoff_submitted'"
            ).fetchone()
            assert handoff is not None
            payload = json.loads(handoff[0])
            assert payload["weight_g"] == 1850.0
        finally:
            conn.close()

    def test_repackaging_approved_event_exists(self, seeded_db):
        """PV-SHIP-011 has a repackaging_approved event (D-005)."""
        conn = get_connection(seeded_db)
        try:
            event = conn.execute(
                "SELECT event_type, payload_json FROM events "
                "WHERE shipment_id='PV-SHIP-011' AND event_type='repackaging_approved'"
            ).fetchone()
            assert event is not None
            payload = json.loads(event[1])
            assert payload["approver_id"]
            assert payload["weight_diff_g"] == 150.0
        finally:
            conn.close()

    def test_contract_history_exists(self, seeded_db):
        """Contract history entries exist for all partners (D-019)."""
        conn = get_connection(seeded_db)
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM contract_history"
            ).fetchone()[0]
            assert count >= 4  # 3 initial + 1 QuickRun scope expansion
        finally:
            conn.close()

    def test_photo_reuse_scenario(self, seeded_db):
        """photo_001.jpg is reused across PV-DEMO-001 and PV-SHIP-010."""
        conn = get_connection(seeded_db)
        try:
            # Find photos with the same SHA-256 on different shipments
            rows = conn.execute(
                """SELECT p.sha256, COUNT(*) as cnt, GROUP_CONCAT(e.shipment_id) as ships
                   FROM photos p
                   JOIN events e ON p.event_id = e.event_id
                   GROUP BY p.sha256
                   HAVING cnt > 1"""
            ).fetchall()
            assert len(rows) > 0, "Expected at least one reused photo"
            reused = rows[0]
            shipments = reused[2].split(",")
            assert len(set(shipments)) >= 2
        finally:
            conn.close()

    def test_access_logs_have_authorized_and_denied(self, seeded_db):
        """Access logs include both authorized and denied entries."""
        conn = get_connection(seeded_db)
        try:
            outcomes = {
                row[0] for row in conn.execute(
                    "SELECT DISTINCT outcome FROM access_logs"
                ).fetchall()
            }
            assert "authorized" in outcomes
            assert "denied" in outcomes
        finally:
            conn.close()

    def test_reset_false_skips_existing(self, seeded_db):
        """reset=False does not duplicate data."""
        # Seeded DB already has data
        counts1 = seed_demo(seeded_db, seed=42, reset=False)
        counts2 = seed_demo(seeded_db, seed=42, reset=False)
        assert counts1 == counts2

    def test_reset_true_recreates(self, temp_db):
        """reset=True drops and recreates all data."""
        seed_demo(temp_db, seed=42, reset=True)
        conn = get_connection(temp_db)
        try:
            count1 = conn.execute("SELECT COUNT(*) FROM shipments").fetchone()[0]
        finally:
            conn.close()

        seed_demo(temp_db, seed=42, reset=True)
        conn = get_connection(temp_db)
        try:
            count2 = conn.execute("SELECT COUNT(*) FROM shipments").fetchone()[0]
        finally:
            conn.close()

        assert count1 == count2 == 60

    def test_reproducible_with_same_seed(self, temp_db):
        """Same seed produces identical data."""
        seed_demo(temp_db, seed=42, reset=True)
        conn1 = get_connection(temp_db)
        try:
            ships1 = conn1.execute(
                "SELECT shipment_id, expected_weight_g FROM shipments ORDER BY shipment_id"
            ).fetchall()
        finally:
            conn1.close()

        seed_demo(temp_db, seed=42, reset=True)
        conn2 = get_connection(temp_db)
        try:
            ships2 = conn2.execute(
                "SELECT shipment_id, expected_weight_g FROM shipments ORDER BY shipment_id"
            ).fetchall()
        finally:
            conn2.close()

        assert ships1 == ships2

    def test_returns_counts(self, seeded_db):
        """seed_demo returns a dict with expected count keys."""
        result = seed_demo(seeded_db, seed=42, reset=False)
        assert "partners" in result
        assert "shipments" in result
        assert "events" in result
        assert "photos" in result
        assert "access_logs" in result
        assert "contract_history" in result


# ---------------------------------------------------------------------------
# Foreign key enforcement
# ---------------------------------------------------------------------------

class TestForeignKeys:
    def test_cannot_insert_event_for_nonexistent_shipment(self, temp_db):
        """Inserting an event for a non-existent shipment should fail."""
        conn = get_connection(temp_db)
        try:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO events (event_id, shipment_id, partner_id, "
                    "actor_id, event_type, occurred_at, received_at, source, "
                    "payload_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("E-TEST", "NONEXISTENT", "P-QUICKRUN", "A1",
                     "test", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z",
                     "test", "{}"),
                )
        finally:
            conn.close()

    def test_cannot_insert_photo_for_nonexistent_event(self, temp_db):
        """Inserting a photo for a non-existent event should fail."""
        conn = get_connection(temp_db)
        try:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO photos (photo_id, event_id, local_path, sha256, "
                    "uploaded_at) VALUES (?, ?, ?, ?, ?)",
                    ("PH-TEST", "NONEXISTENT", "/tmp/test.jpg",
                     "abc123", "2026-01-01T00:00:00Z"),
                )
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# No test writes to demo DB (D-017)
# ---------------------------------------------------------------------------

class TestDatabaseIsolation:
    def test_no_test_writes_to_demo_db(self, temp_db, seeded_db):
        """Verify that test databases are not the demo database path."""
        assert temp_db != "data/parcelverify.db"
        assert seeded_db != "data/parcelverify.db"
        assert "pvtest_" in temp_db or "tmp" in temp_db.lower()
