"""Acceptance tests for integrated persistence, scope and isolated sessions."""
import json
from pathlib import Path
from datetime import datetime, timezone

import pytest
from streamlit.testing.v1 import AppTest

import workspace
from db import get_connection, init_db, submit_event, upload_photo
from seed import seed_demo
from services.actions import propose_action, review_action, execute_action
from services.workflow import initialize_reviews, submit_handoff, process_evidence
from services.risk import get_partner_metrics

ADMIN = {"actor_id": "ADMIN-001", "role": "admin", "session_id": "acceptance"}

@pytest.fixture
def database(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    seed_demo(path)
    return path

def test_seed_main_case_score_and_explanation(database):
    initialize_reviews(database, ADMIN)
    with get_connection(database) as conn:
        main = conn.execute("SELECT priority_score, findings_json FROM case_records WHERE shipment_id='PV-DEMO-001'").fetchone()
        assert main[0] == 45
        assert {f["category"] for f in json.loads(main[1])} == {"weight_diff", "photo_reuse"}
        explained = conn.execute("SELECT findings_json FROM case_records WHERE shipment_id='PV-SHIP-011'").fetchall()
        assert all("weight_diff" not in {f["category"] for f in json.loads(row[0])} for row in explained)

def test_workflow_persists_and_duplicate_submission_no_duplicate_case(database):
    occurred = datetime.now(timezone.utc).isoformat()
    payload = {"count": 98, "weight_g": 1850, "seal_id": "SEAL-07"}
    first = submit_handoff(database, ADMIN, "PV-DEMO-001", "handoff_submitted", payload, occurred)
    second = submit_handoff(database, ADMIN, "PV-DEMO-001", "handoff_submitted", payload, occurred)
    assert first["event"]["event_id"] == second["event"]["event_id"]
    assert first["case"]["case_id"] == second["case"]["case_id"]
    init_db(database)
    with get_connection(database) as conn:
        assert conn.execute("SELECT COUNT(*) FROM case_records WHERE triggering_event_id=?", (first["event"]["event_id"],)).fetchone()[0] == 1
    action = propose_action(database, first["case"]["case_id"], "request_reweigh", ADMIN)
    review_action(database, action["action_id"], "approve", ADMIN)
    assert execute_action(database, action["action_id"], ADMIN)["status"] == "executed"
    assert execute_action(database, action["action_id"], ADMIN)["status"] == "already_executed"
    with get_connection(database) as conn:
        assert conn.execute("SELECT COUNT(*) FROM evidence_tasks WHERE case_id=? AND task_type='reweigh' AND status='open'", (first["case"]["case_id"],)).fetchone()[0] == 1
        conn.execute("UPDATE case_records SET status='review_completed' WHERE case_id=?", (first["case"]["case_id"],))
    assert get_partner_metrics(database, "P-QUICKRUN")["open_cases"] >= 1

def test_duplicate_evidence_cannot_bypass_authorization(database):
    with get_connection(database) as conn:
        event = conn.execute("SELECT event_id, event_type, payload_json, source, occurred_at FROM events WHERE shipment_id='PV-DEMO-001' LIMIT 1").fetchone()
    stranger = {"actor_id": "ACTOR-SL-01", "partner_id": "P-SAFELOG", "role": "partner_user", "session_id": "test"}
    with pytest.raises(Exception, match="partner|authorized|assignment"):
        submit_event(database, stranger, "PV-DEMO-001", event[1], json.loads(event[2]), event[3], event[4])

def test_separate_workspaces_resume_and_persist(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "DATA_ROOT", tmp_path)
    one, path_one = workspace.open_workspace()
    two, path_two = workspace.open_workspace()
    assert one != two and path_one != path_two
    with get_connection(path_one) as conn:
        conn.execute("UPDATE shipments SET status='held' WHERE shipment_id='PV-DEMO-001'")
    assert workspace.open_workspace(one)[1] == path_one
    with get_connection(path_one) as conn:
        assert conn.execute("SELECT status FROM shipments WHERE shipment_id='PV-DEMO-001'").fetchone()[0] == "held"
    with get_connection(path_two) as conn:
        assert conn.execute("SELECT status FROM shipments WHERE shipment_id='PV-DEMO-001'").fetchone()[0] != "held"
    with pytest.raises(ValueError):
        workspace.open_workspace("../../foreign")

def test_all_live_pages_and_partner_scope(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "DATA_ROOT", tmp_path)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30).run()
    assert not app.exception
    assert not app.sidebar.radio
    for page in ('Issues', 'Partners', 'Home'):
        app.button(key='nav-'+page).click().run()
        assert not app.exception
        assert not app.error
    app.button(key='desktop-Settings').click().run()
    app.selectbox(key='role_widget').set_value('partner_user').run()
    assert app.session_state.actor_context['role'] == 'partner_user'
    app.button(key='nav-Issues').click().run()
    assert not app.exception
    assert app.session_state.actor_role == 'partner_user'
    from contracts import ActorContext
    from services.access import _is_authorized
    from services.review import list_review_cases
    path, actor = app.session_state.db_path, app.session_state.actor_context
    cohort = list_review_cases(path, actor)
    assert cohort
    with get_connection(path) as conn:
        assert all(c['partner_id'] == 'P-QUICKRUN' and _is_authorized(conn, ActorContext(**actor), c['shipment_id'], datetime.now(timezone.utc).isoformat())[0] for c in cohort)
    app.button(key='nav-Partners').click().run()
    assert not app.exception
    assert app.session_state.actor_context['role'] == 'partner_user'
    assert [button.key for button in app.button if (button.key or '').startswith('partner-')] == ['partner-P-QUICKRUN']
    app.button(key='desktop-Settings').click().run()
    assert app.selectbox(key='role_widget').value == 'partner_user'
