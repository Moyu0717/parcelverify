"""Review workflow acceptance through real Streamlit widgets; no AI requests."""
from pathlib import Path
import json
import pytest
from streamlit.testing.v1 import AppTest
import workspace
from db import get_connection
from services.cases import list_cases as list_review_cases


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, 'DATA_ROOT', tmp_path)
    monkeypatch.setenv('AI_PROVIDER', 'groq')
    monkeypatch.delenv('GROQ_API_KEY', raising=False)
    def forbidden(*args, **kwargs):
        raise AssertionError('UI acceptance must not call AI')
    monkeypatch.setattr('ui.workspace_ui.investigate_case', forbidden)
    monkeypatch.setattr('ui.live.investigate_case', forbidden)
    test = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=30).run()
    assert not test.exception
    assert not test.error
    return test


def widget(collection, label):
    return next(item for item in collection if item.label == label)


def healthy(app):
    assert not app.exception
    assert not app.error, [item.value for item in app.error]


def open_main(app):
    app.button(key='nav-Cases').click().run()
    app.text_input(key='case_query').set_value('PV-DEMO-001')
    widget(app.button, 'Find shipment').click().run()
    healthy(app)
    assert app.title[0].value == 'Check a weight difference'
    return app.session_state.selected_case_id


def test_open_back_filter_and_honest_ai_state(app):
    app.button(key='counter-needs_review').click().run()
    assert app.session_state.primary_destination == 'Home'
    assert app.session_state.home_bucket == 'needs_review'
    first = next(button for button in app.button if (button.key or '').startswith('open-'))
    selected = first.key.removeprefix('open-')
    first.click().run()
    healthy(app)
    assert app.session_state.selected_case_id == selected
    assert any('AI review' in item.value for item in app.info)
    assert not any(item.value == '**What we found**' for item in app.markdown)
    widget(app.button, 'Back to cases').click().run()
    app.selectbox(key='status_widget').set_value('All').run()
    app.selectbox(key='issue_widget').set_value('Data access').run()
    healthy(app)
    cohort = list_review_cases(app.session_state.db_path, app.session_state.actor_context)
    expected = {c['case_id'] for c in cohort if c.get('contains_access')}
    shown = {button.key.removeprefix('open-') for button in app.button if (button.key or '').startswith('open-')}
    assert shown and shown <= expected
    app.text_input(key='case_query').set_value('reference-that-does-not-exist').run()
    assert not [button for button in app.button if (button.key or '').startswith('open-')]
    assert any('No issues match' in item.value for item in app.info)


def test_request_approve_apply_and_manual_close(app):
    case_id = open_main(app)
    widget(app.text_area, 'Reason for the request').set_value('Verify the unexplained weight difference')
    widget(app.button, 'Send request for approval').click().run()
    healthy(app)
    path = app.session_state.db_path
    with get_connection(path) as conn:
        action = conn.execute('SELECT action_id,status FROM action_requests WHERE case_id=?', (case_id,)).fetchone()
        assert action[1] == 'proposed'
        assert conn.execute("SELECT COUNT(*) FROM evidence_tasks WHERE case_id=? AND task_type='reweigh'", (case_id,)).fetchone()[0] == 0
    assert widget(app.button, 'Approve request').disabled
    app.checkbox(key='confirm-' + action[0]).check().run()
    widget(app.button, 'Approve request').click().run()
    healthy(app)
    with get_connection(path) as conn:
        assert conn.execute('SELECT status FROM action_requests WHERE action_id=?', (action[0],)).fetchone()[0] == 'approved'
    widget(app.button, 'Apply approved step').click().run()
    healthy(app)
    with get_connection(path) as conn:
        assert conn.execute('SELECT status FROM action_requests WHERE action_id=?', (action[0],)).fetchone()[0] == 'executed'
        assert conn.execute("SELECT COUNT(*) FROM evidence_tasks WHERE case_id=? AND task_type='reweigh' AND status='open'", (case_id,)).fetchone()[0] == 1
    widget(app.button, 'Close case').click().run()
    assert any('Confirm the closure outcome' in item.value for item in app.error)
    with get_connection(path) as conn:
        assert conn.execute('SELECT status FROM case_records WHERE case_id=?', (case_id,)).fetchone()[0] != 'closed'
    widget(app.selectbox, 'Closure outcome').set_value('closed_unresolved')
    widget(app.text_area, 'Closure reason').set_value('Manual disposition after reviewing the supplied records')
    widget(app.checkbox, 'I reviewed the linked findings and the stated closure outcome.').check()
    widget(app.button, 'Close case').click().run()
    healthy(app)
    with get_connection(path) as conn:
        assert conn.execute('SELECT status FROM case_records WHERE case_id=?', (case_id,)).fetchone()[0] == 'closed'
        resolutions = conn.execute('SELECT resolution_json FROM evidence_tasks WHERE case_id=?', (case_id,)).fetchall()
        assert all(json.loads(row[0])['evidence_verified'] is False for row in resolutions)
    assert any('Case closed' in item.value for item in app.success)


def test_evidence_validation_keeps_draft_and_converts_kg(app):
    open_main(app)
    path = app.session_state.db_path
    with get_connection(path) as conn:
        original = conn.execute('SELECT COUNT(*) FROM events').fetchone()[0]
    widget(app.text_input, 'Quantity (packages)').set_value('not a count')
    widget(app.text_input, 'Weight (kg)').set_value('1.85')
    widget(app.button, 'Save evidence').click().run()
    assert not app.exception
    assert any('Quantity must be a whole number' in item.value for item in app.error)
    assert widget(app.text_input, 'Weight (kg)').value == '1.85'
    widget(app.button, 'Back to cases').click().run()
    open_main(app)
    assert widget(app.text_input, 'Weight (kg)').value == '1.85'
    assert widget(app.text_input, 'Quantity (packages)').value == 'not a count'
    with get_connection(path) as conn:
        assert conn.execute('SELECT COUNT(*) FROM events').fetchone()[0] == original
    widget(app.text_input, 'Quantity (packages)').set_value('98')
    widget(app.text_input, 'Seal reference').set_value('SEAL-07')
    widget(app.text_area, 'Supporting note').set_value('Manual test evidence')
    widget(app.button, 'Save evidence').click().run()
    healthy(app)
    with get_connection(path) as conn:
        payload = json.loads(conn.execute("SELECT payload_json FROM events WHERE shipment_id='PV-DEMO-001' AND source='manual_evidence'").fetchone()[0])
        assert payload['weight_g'] == 1850
        assert payload['count'] == 98
        assert conn.execute('SELECT COUNT(*) FROM events').fetchone()[0] == original + 1


def test_shipment_without_issue_lookup_does_not_create_case(app):
    path=app.session_state.db_path
    with get_connection(path) as conn:
        conn.execute("INSERT INTO shipments(shipment_id,partner_id,expected_count,expected_weight_g,expected_seal,status) VALUES('PV-NORMAL-001','P-QUICKRUN',1,2000,'SEAL-TEST','dispatched')")
        before=conn.execute('SELECT COUNT(*) FROM case_records').fetchone()[0]
    app.button(key='nav-Cases').click().run()
    app.text_input(key='case_query').set_value('PV-NORMAL-001')
    widget(app.button,'Find shipment').click().run()
    healthy(app)
    assert app.session_state.selected_shipment_id=='PV-NORMAL-001'
    assert app.title[0].value=='PV-NORMAL-001'
    with get_connection(path) as conn:
        assert conn.execute('SELECT COUNT(*) FROM case_records').fetchone()[0]==before


def test_access_review_close_and_matching_counter(app):
    app.button(key='nav-Cases').click().run()
    app.selectbox(key='issue_widget').set_value('Data access').run()
    button=next(b for b in app.button if (b.key or '').startswith('open-'))
    case_id=button.key.removeprefix('open-')
    button.click().run()
    assert app.session_state.selected_case_id
    widget(app.selectbox,'Closure outcome').set_value('closed_unresolved')
    widget(app.text_area,'Closure reason').set_value('Reviewed the denied access and recorded assignment context')
    widget(app.checkbox,'I reviewed the linked findings and the stated closure outcome.').check()
    widget(app.button,'Close case').click().run()
    healthy(app)
    app.button(key='nav-Home').click().run()
    app.button(key='counter-resolved').click().run()
    shown={b.key.removeprefix('open-') for b in app.button if (b.key or '').startswith('open-')}
    assert shown=={case_id}
    assert app.session_state.primary_destination=='Home'


def test_cancel_preserves_draft_and_supervisor_can_record_missing_information(app):
    case_id=open_main(app)
    widget(app.text_area,'Reason for the request').set_value('Keep this request draft while checking the photos').run()
    widget(app.button,'Cancel request').click().run()
    assert not [b for b in app.button if b.label=='Send request for approval']
    widget(app.button,'Prepare a request').click().run()
    assert widget(app.text_area,'Reason for the request').value=='Keep this request draft while checking the photos'
    widget(app.button,'Send request for approval').click().run()
    widget(app.text_area,'What information is needed?').set_value('Provide the original measurement and supporting photo')
    widget(app.button,'Record information request').click().run()
    healthy(app)
    with get_connection(app.session_state.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM evidence_tasks WHERE case_id=? AND task_type='supplementary_statement'",(case_id,)).fetchone()[0]==1
        assert conn.execute('SELECT status FROM action_requests WHERE case_id=?',(case_id,)).fetchone()[0]=='proposed'


def test_home_status_and_search_filter_the_local_queue(app):
    cohort=list_review_cases(app.session_state.db_path,app.session_state.actor_context)
    for bucket in ('needs_review','awaiting_approval','waiting_evidence','resolved'):
        app.button(key='counter-'+bucket).click().run()
        healthy(app)
        assert app.session_state.primary_destination=='Home'
        expected={c['case_id'] for c in cohort if c['work_bucket']==bucket}
        shown={b.key.removeprefix('open-') for b in app.button if (b.key or '').startswith('open-')}
        assert shown==set(sorted(expected,key=lambda cid:next(c['priority_score'] or 0 for c in cohort if c['case_id']==cid),reverse=True)[:8])
    app.button(key='counter-needs_review').click().run()
    app.text_input(key='home_query').set_value('no-such-record').run()
    assert not [b for b in app.button if (b.key or '').startswith('open-')]
    assert app.session_state.primary_destination=='Home'
