"""
ParcelVerify — Actions & Audit Service Tests
Owner: Role D (Application Agent)

Tests for services/actions.py and services/audit.py using isolated temp databases.
Never writes to the demo database (D-017).
"""

import json
import os
import sys
import sqlite3

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contracts import DBConfig, AuditError, AuthorizationError, IdempotencyError
from db import init_db, get_connection
from seed import seed_demo
from services.actions import propose_action, review_action, execute_action, create_evidence_task
from services.audit import append_audit, export_audit
from services.handoff import create_or_update_case


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


INVESTIGATOR = {
    "actor_id": "INVESTIGATOR-001",
    "role": "investigator",
    "session_id": "test-inv",
    "is_simulated": True,
}

APPROVER = {
    "actor_id": "APPROVER-001",
    "role": "approver",
    "session_id": "test-approver",
    "is_simulated": True,
}

ADMIN = {
    "actor_id": "ADMIN-001",
    "role": "admin",
    "session_id": "test-admin",
    "is_simulated": True,
}

PARTNER_USER = {
    "actor_id": "ACTOR-QR-01",
    "partner_id": "P-QUICKRUN",
    "role": "partner_user",
    "session_id": "test-partner",
    "is_simulated": True,
}


def _create_case(db_path, shipment_id="PV-DEMO-001", event_id="E-TEST-001"):
    """Helper to create a case for testing."""
    findings = [
        {"category": "weight_diff", "description": "150g discrepancy",
         "severity": "warning", "evidence_ids": [event_id]}
    ]
    return create_or_update_case(db_path, shipment_id, event_id, findings, "1.1.0")


# ---------------------------------------------------------------------------
# Propose Action Tests
# ---------------------------------------------------------------------------

class TestProposeAction:
    def test_creates_proposed_action(self, seeded_db):
        """propose_action creates a pending request."""
        case = _create_case(seeded_db)
        result = propose_action(seeded_db, case["case_id"], "request_reweigh", INVESTIGATOR)
        assert result["action_id"]
        assert result["status"] == "proposed"

    def test_partner_user_cannot_propose(self, seeded_db):
        """Only investigators and admins can propose actions."""
        case = _create_case(seeded_db)
        with pytest.raises(AuthorizationError):
            propose_action(seeded_db, case["case_id"], "request_reweigh", PARTNER_USER)

    def test_nonexistent_case_raises(self, seeded_db):
        """Proposing for a nonexistent case raises ValueError."""
        with pytest.raises(ValueError):
            propose_action(seeded_db, "NONEXISTENT", "request_reweigh", INVESTIGATOR)


# ---------------------------------------------------------------------------
# Review Action Tests
# ---------------------------------------------------------------------------

class TestReviewAction:
    def test_approve_action(self, seeded_db):
        """Approver can approve a proposed action."""
        case = _create_case(seeded_db)
        action = propose_action(seeded_db, case["case_id"], "request_reweigh", INVESTIGATOR)
        result = review_action(seeded_db, action["action_id"], "approve", APPROVER)
        assert result["status"] == "approved"
        assert result["approved_by"] == "APPROVER-001"

    def test_reject_action(self, seeded_db):
        """Approver can reject a proposed action."""
        case = _create_case(seeded_db)
        action = propose_action(seeded_db, case["case_id"], "request_reweigh", INVESTIGATOR)
        result = review_action(seeded_db, action["action_id"], "reject", APPROVER)
        assert result["status"] == "rejected"

    def test_rejected_is_terminal(self, seeded_db):
        """Cannot execute a rejected action (D-019)."""
        case = _create_case(seeded_db)
        action = propose_action(seeded_db, case["case_id"], "request_reweigh", INVESTIGATOR)
        review_action(seeded_db, action["action_id"], "reject", APPROVER)
        result = execute_action(seeded_db, action["action_id"], ADMIN)
        assert result["status"] == "not_approved"

    def test_cannot_reject_already_rejected(self, seeded_db):
        """Cannot review an action that is already rejected (D-019)."""
        case = _create_case(seeded_db)
        action = propose_action(seeded_db, case["case_id"], "request_reweigh", INVESTIGATOR)
        review_action(seeded_db, action["action_id"], "reject", APPROVER)
        with pytest.raises(IdempotencyError):
            review_action(seeded_db, action["action_id"], "approve", APPROVER)

    def test_partner_user_cannot_review(self, seeded_db):
        """Partner users cannot review actions."""
        case = _create_case(seeded_db)
        action = propose_action(seeded_db, case["case_id"], "request_reweigh", INVESTIGATOR)
        with pytest.raises(AuthorizationError):
            review_action(seeded_db, action["action_id"], "approve", PARTNER_USER)


# ---------------------------------------------------------------------------
# Execute Action Tests
# ---------------------------------------------------------------------------

class TestExecuteAction:
    def test_execute_approved(self, seeded_db):
        """Execute an approved action successfully."""
        case = _create_case(seeded_db)
        action = propose_action(seeded_db, case["case_id"], "request_reweigh", INVESTIGATOR)
        review_action(seeded_db, action["action_id"], "approve", APPROVER)
        result = execute_action(seeded_db, action["action_id"], ADMIN)
        assert result["status"] == "executed"
        assert result["before"] is not None
        assert result["after"] is not None

    def test_execute_already_executed(self, seeded_db):
        """Executing twice returns already_executed (D-019 pre-check 5)."""
        case = _create_case(seeded_db)
        action = propose_action(seeded_db, case["case_id"], "request_reweigh", INVESTIGATOR)
        review_action(seeded_db, action["action_id"], "approve", APPROVER)
        execute_action(seeded_db, action["action_id"], ADMIN)
        result = execute_action(seeded_db, action["action_id"], ADMIN)
        assert result["status"] == "already_executed"

    def test_execute_proposed_fails(self, seeded_db):
        """Executing a proposed (not approved) action returns not_approved."""
        case = _create_case(seeded_db)
        action = propose_action(seeded_db, case["case_id"], "request_reweigh", INVESTIGATOR)
        result = execute_action(seeded_db, action["action_id"], ADMIN)
        assert result["status"] == "not_approved"

    def test_execute_rejected_fails(self, seeded_db):
        """Executing a rejected action returns not_approved."""
        case = _create_case(seeded_db)
        action = propose_action(seeded_db, case["case_id"], "request_reweigh", INVESTIGATOR)
        review_action(seeded_db, action["action_id"], "reject", APPROVER)
        result = execute_action(seeded_db, action["action_id"], ADMIN)
        assert result["status"] == "not_approved"

    def test_audit_record_written_on_execute(self, seeded_db):
        """Executing an action writes an audit record in the same transaction."""
        case = _create_case(seeded_db)
        action = propose_action(seeded_db, case["case_id"], "request_reweigh", INVESTIGATOR)
        review_action(seeded_db, action["action_id"], "approve", APPROVER)
        execute_action(seeded_db, action["action_id"], ADMIN)

        conn = get_connection(seeded_db)
        try:
            audit = conn.execute(
                "SELECT operation FROM audit_log WHERE case_id = ? AND operation = 'action_executed'",
                (case["case_id"],),
            ).fetchone()
            assert audit is not None
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Create Evidence Task Tests
# ---------------------------------------------------------------------------

class TestCreateEvidenceTask:
    def test_creates_task(self, seeded_db):
        """create_evidence_task creates a new open task."""
        case = _create_case(seeded_db)
        result = create_evidence_task(seeded_db, case["case_id"], "reweigh", INVESTIGATOR, "Need reweigh")
        assert result["is_new"] is True
        assert result["status"] == "open"
        assert result["task_type"] == "reweigh"

    def test_idempotent(self, seeded_db):
        """One open task per (case_id, task_type) — duplicate returns existing."""
        case = _create_case(seeded_db)
        result1 = create_evidence_task(seeded_db, case["case_id"], "reweigh", INVESTIGATOR, "Need reweigh")
        result2 = create_evidence_task(seeded_db, case["case_id"], "reweigh", INVESTIGATOR, "Need reweigh")
        assert result1["task_id"] == result2["task_id"]
        assert result1["is_new"] is True
        assert result2["is_new"] is False

    def test_different_task_types_allowed(self, seeded_db):
        """Different task types can coexist."""
        case = _create_case(seeded_db)
        r1 = create_evidence_task(seeded_db, case["case_id"], "reweigh", INVESTIGATOR, "rew")
        r2 = create_evidence_task(seeded_db, case["case_id"], "rephoto", INVESTIGATOR, "rep")
        assert r1["task_id"] != r2["task_id"]


# ---------------------------------------------------------------------------
# Audit Service Tests
# ---------------------------------------------------------------------------

class TestAppendAudit:
    def test_append_standalone(self, seeded_db):
        """append_audit writes a record when called standalone."""
        result = append_audit(seeded_db, "ADMIN-001", None, "test_operation", {"key": "value"})
        assert result is True

        conn = get_connection(seeded_db)
        try:
            row = conn.execute(
                "SELECT operation FROM audit_log WHERE actor_id = ? AND operation = ?",
                ("ADMIN-001", "test_operation"),
            ).fetchone()
            assert row is not None
        finally:
            conn.close()

    def test_append_within_transaction(self, seeded_db):
        """append_audit with tx writes within the same transaction."""
        conn = get_connection(seeded_db)
        try:
            append_audit(seeded_db, "ADMIN-001", None, "tx_test", {"x": 1}, tx=conn)
            conn.commit()
        finally:
            conn.close()

        conn = get_connection(seeded_db)
        try:
            row = conn.execute(
                "SELECT operation FROM audit_log WHERE operation = 'tx_test'",
            ).fetchone()
            assert row is not None
        finally:
            conn.close()


class TestExportAudit:
    def test_export_all_as_admin(self, seeded_db):
        """Admin can export full audit trail."""
        append_audit(seeded_db, "ADMIN-001", None, "test_export", {"a": 1})
        result = export_audit(seeded_db, None, ADMIN)
        assert result["format"] == "json"
        assert len(result["events"]) > 0

    def test_export_case_as_admin(self, seeded_db):
        """Admin can export audit for a specific case."""
        case = _create_case(seeded_db)
        append_audit(seeded_db, "ADMIN-001", case["case_id"], "case_test", {"b": 2})
        result = export_audit(seeded_db, case["case_id"], ADMIN)
        assert len(result["events"]) > 0
        assert all(e["case_id"] == case["case_id"] for e in result["events"])

    def test_non_admin_cannot_export_all(self, seeded_db):
        """Non-admin cannot export full audit trail."""
        with pytest.raises(AuthorizationError):
            export_audit(seeded_db, None, PARTNER_USER)
