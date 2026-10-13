"""
ParcelVerify — Agent Tests (Mock Model)
Owner: Role C (Investigation Agent)

Tests for agent/tools.py and agent/runner.py using mock model.
Track B (Mock Model Tests) — NOT conflated with real model tests.

Uses isolated temp databases. Never writes to the demo database (D-017).
"""

import json
import os
import sys
import sqlite3
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contracts import DBConfig, TOOL_WHITELIST
from db import init_db, get_connection
from seed import seed_demo
from services.handoff import create_or_update_case
from agent.tools import dispatch_tool
from agent.runner import investigate_case


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


def _create_case_for_investigation(db_path, shipment_id="PV-DEMO-001"):
    """Create a case for testing investigation."""
    conn = get_connection(db_path)
    try:
        event_id = conn.execute(
            "SELECT event_id FROM events WHERE shipment_id = ? "
            "AND event_type = 'handoff_submitted' LIMIT 1",
            (shipment_id,),
        ).fetchone()[0]
    finally:
        conn.close()

    findings = [
        {"category": "weight_diff", "description": "150g discrepancy",
         "severity": "warning", "evidence_ids": [event_id]},
        {"category": "photo_reuse", "description": "Photo reused",
         "severity": "blocking", "evidence_ids": []},
    ]
    return create_or_update_case(db_path, shipment_id, event_id, findings, "1.1.0")


# ---------------------------------------------------------------------------
# Tool Dispatch Tests
# ---------------------------------------------------------------------------

class TestDispatchTool:
    def test_rejects_unknown_tool(self, seeded_db):
        """dispatch_tool rejects tools not in whitelist."""
        case = _create_case_for_investigation(seeded_db)
        result = dispatch_tool(
            seeded_db, "hack_database", {},
            {"case_id": case["case_id"]}, ADMIN_ACTOR
        )
        assert "Error" in result["result_summary"]
        assert result["result"]["error"].startswith("unknown_tool")

    def test_get_vendor_context(self, seeded_db):
        """get_vendor_context returns contract info."""
        case = _create_case_for_investigation(seeded_db)
        result = dispatch_tool(
            seeded_db, "get_vendor_context", {},
            {"case_id": case["case_id"]}, ADMIN_ACTOR
        )
        assert result["tool"] == "get_vendor_context"
        assert "contract" in result["result"] or "partner_id" in result["result"]

    def test_get_shipment_timeline(self, seeded_db):
        """get_shipment_timeline returns ordered events."""
        case = _create_case_for_investigation(seeded_db)
        result = dispatch_tool(
            seeded_db, "get_shipment_timeline", {},
            {"case_id": case["case_id"]}, ADMIN_ACTOR
        )
        assert "events" in result["result"]
        assert len(result["result"]["events"]) > 0

    def test_compare_handoff(self, seeded_db):
        """compare_handoff returns weight/seal/count comparison."""
        case = _create_case_for_investigation(seeded_db)
        result = dispatch_tool(
            seeded_db, "compare_handoff", {},
            {"case_id": case["case_id"]}, ADMIN_ACTOR
        )
        assert "count" in result["result"]
        assert "weight_g" in result["result"]
        assert "seal" in result["result"]

    def test_check_access_scope(self, seeded_db):
        """check_access_scope returns access logs and violations."""
        case = _create_case_for_investigation(seeded_db)
        result = dispatch_tool(
            seeded_db, "check_access_scope", {},
            {"case_id": case["case_id"]}, ADMIN_ACTOR
        )
        assert "access_logs" in result["result"]

    def test_get_context_events(self, seeded_db):
        """get_context_events returns calibration/repackaging events."""
        case = _create_case_for_investigation(seeded_db, "PV-SHIP-011")
        result = dispatch_tool(
            seeded_db, "get_context_events", {},
            {"case_id": case["case_id"]}, ADMIN_ACTOR
        )
        assert "context_events" in result["result"]

    def test_get_partner_metrics(self, seeded_db):
        """get_partner_metrics returns volume and anomaly rate."""
        case = _create_case_for_investigation(seeded_db)
        result = dispatch_tool(
            seeded_db, "get_partner_metrics", {},
            {"case_id": case["case_id"]}, ADMIN_ACTOR
        )
        assert result["result"]["partner_id"] == "P-QUICKRUN"
        assert "total_shipments" in result["result"]

    def test_evidence_ids_collected(self, seeded_db):
        """Tool results include evidence_ids from events."""
        case = _create_case_for_investigation(seeded_db)
        result = dispatch_tool(
            seeded_db, "get_shipment_timeline", {},
            {"case_id": case["case_id"]}, ADMIN_ACTOR
        )
        assert len(result["evidence_ids"]) > 0

    def test_missing_case_id(self, seeded_db):
        """Missing case_id in case_context returns error."""
        result = dispatch_tool(
            seeded_db, "get_vendor_context", {},
            {}, ADMIN_ACTOR
        )
        assert "Error" in result["result_summary"]


# ---------------------------------------------------------------------------
# Runner Tests (Mock Model)
# ---------------------------------------------------------------------------

class ScriptedProvider:
    model_name = "mock-model"

    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def generate(self, messages, timeout, final=False):
        self.calls.append(final)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return json.dumps(response)


def valid_report():
    return {"verdict":"insufficient_evidence", "summary":"Additional verification is required.",
            "facts":[], "alternative_explanations":["Measurement error is possible"],
            "missing_evidence":["Verified reweigh"], "recommended_action":"request_reweigh",
            "requires_approval":True, "limitations":"Text records only"}


class TestInvestigateCase:
    def test_nonexistent_case(self, seeded_db):
        assert investigate_case(seeded_db,"missing",ADMIN_ACTOR)["status"] == "error"

    def test_model_unavailable_preserves_status_and_run(self, seeded_db):
        import httpx
        case = _create_case_for_investigation(seeded_db)
        provider = ScriptedProvider([httpx.ConnectError("offline")])
        result = investigate_case(seeded_db,case["case_id"],ADMIN_ACTOR,provider=provider)
        assert result["status"] == "ai_not_running"
        assert result["report"] is None
        with get_connection(seeded_db) as conn:
            assert conn.execute("SELECT status FROM case_records WHERE case_id=?",(case["case_id"],)).fetchone()[0] == case["status"]
            run = conn.execute("SELECT status,error FROM investigation_runs").fetchone()
            assert run[0] == "ai_not_running" and run[1]

    def test_separate_report_phase_and_trace(self, seeded_db):
        case = _create_case_for_investigation(seeded_db)
        provider = ScriptedProvider([{"tool_call":{"tool":"get_shipment_timeline","params":{}}},{"done":True},valid_report()])
        result = investigate_case(seeded_db,case["case_id"],ADMIN_ACTOR,provider=provider)
        assert result["status"] == "completed"
        assert provider.calls == [False,False,True]
        assert result["report_version"] == 1
        with get_connection(seeded_db) as conn:
            row = conn.execute("SELECT run_id,report_id FROM tool_executions").fetchone()
            assert row[0] and row[1]
            assert conn.execute("SELECT status FROM investigation_runs").fetchone()[0] == "completed"

    def test_four_round_limit(self, seeded_db):
        case = _create_case_for_investigation(seeded_db)
        call = {"tool_call":{"tool":"get_partner_metrics","params":{}}}
        provider = ScriptedProvider([call]*4+[valid_report()])
        result = investigate_case(seeded_db,case["case_id"],ADMIN_ACTOR,provider=provider)
        assert result["status"] == "completed"
        assert len(result["tool_calls"]) == 4
        assert provider.calls == [False]*4+[True]
