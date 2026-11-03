"""Guided review workflow through real Streamlit widgets; no AI requests."""
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


def keyed(collection, prefix):
    return next(item for item in collection if (item.key or '').startswith(prefix))


def healthy(app):
    assert not app.exception
    assert not app.error, [item.value for item in app.error]


def approve_as_supervisor(app, note='Weight is outside tolerance; a fresh measurement is needed'):
    """Separation of duties: the proposer cannot approve, so switch to Supervisor, approve with a reason, switch back."""
    if [b for b in app.button if b.key=='switch-approver']:
        app.button(key='switch-approver').click().run()
    keyed(app.text_area,'approval-note-').set_value(note).run()
    keyed(app.button,'approve-send-').click().run()
    if [b for b in app.button if b.key=='switch-admin']:
        app.button(key='switch-admin').click().run()
    return app


def open_main(app):
    app.button(key='nav-Cases').click().run()
    app.text_input(key='case_query').set_value('PV-DEMO-001')
    widget(app.button, 'Find shipment').click().run()
    healthy(app)
    assert app.title[0].value == 'Check a weight difference'
    return app.session_state.selected_case_id


def finish(app, case_id, outcome, reason, confirm=True):
    app.radio(key='outcome-' + case_id).set_value(outcome).run()
    app.text_area(key='finish-reason-' + case_id + '-' + outcome).set_value(reason)
    if confirm:
        app.checkbox(key='finish-confirm-' + case_id).check()
    app.button(key='finish-' + case_id).click().run()


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
    app.button(key='back-to-cases').click().run()
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


def test_guided_flow_request_approve_reply_accept_and_verify(app):
    case_id = open_main(app)
    path = app.session_state.db_path
    widget(app.text_area, 'Message to the partner').set_value('Please reweigh the parcel on a calibrated scale')
    app.button(key='send-request-' + case_id).click().run()
    healthy(app)
    with get_connection(path) as conn:
        action_id, status = conn.execute('SELECT action_id,status FROM action_requests WHERE case_id=?', (case_id,)).fetchone()
        assert status == 'proposed'
        assert conn.execute("SELECT COUNT(*) FROM evidence_tasks WHERE case_id=? AND task_type='reweigh'", (case_id,)).fetchone()[0] == 0
        source = [json.loads(r[0]).get('source_event_id') for r in conn.execute("SELECT details_json FROM audit_log WHERE operation='action_proposed'")]
        handoff = conn.execute("SELECT event_id FROM events WHERE shipment_id='PV-DEMO-001' AND event_type='handoff_submitted'").fetchone()[0]
    assert handoff in source, 'the request targets the highlighted 3D stop'
    approve_as_supervisor(app)
    healthy(app)
    with get_connection(path) as conn:
        assert conn.execute('SELECT status FROM action_requests WHERE action_id=?', (action_id,)).fetchone()[0] == 'executed'
        assert conn.execute("SELECT COUNT(*) FROM evidence_tasks WHERE case_id=? AND task_type='reweigh' AND status='open'", (case_id,)).fetchone()[0] == 1
    widget(app.text_input, 'New weight (kg)').set_value('2.0')
    widget(app.text_area, 'Message from the partner').set_value('Reweighed on the calibrated hub scale')
    widget(app.button, 'Send reply as partner').click().run()
    healthy(app)
    keyed(app.button, 'accept-').click().run()
    healthy(app)
    assert app.radio(key='outcome-' + case_id).value == 'verified_resolved'
    finish(app, case_id, 'verified_resolved', 'Fresh calibrated weight matches the dispatch record')
    healthy(app)
    with get_connection(path) as conn:
        assert conn.execute('SELECT status FROM case_records WHERE case_id=?', (case_id,)).fetchone()[0] == 'closed'
        assert conn.execute('SELECT outcome FROM case_decisions WHERE case_id=?', (case_id,)).fetchone()[0] == 'verified_resolved'
    assert any('Case closed' in item.value for item in app.success)


def test_waiting_case_can_still_be_closed_unresolved_with_confirmation(app):
    case_id = open_main(app)
    path = app.session_state.db_path
    app.button(key='send-request-' + case_id).click().run()
    approve_as_supervisor(app)
    healthy(app)
    finish(app, case_id, 'closed_unresolved', 'Manual disposition after reviewing the supplied records', confirm=False)
    assert any('Tick' in item.value for item in app.error)
    with get_connection(path) as conn:
        assert conn.execute('SELECT status FROM case_records WHERE case_id=?', (case_id,)).fetchone()[0] != 'closed'
    finish(app, case_id, 'closed_unresolved', 'Manual disposition after reviewing the supplied records')
    healthy(app)
    with get_connection(path) as conn:
        assert conn.execute('SELECT status FROM case_records WHERE case_id=?', (case_id,)).fetchone()[0] == 'closed'
        resolutions = conn.execute('SELECT resolution_json FROM evidence_tasks WHERE case_id=?', (case_id,)).fetchall()
        assert resolutions and all(json.loads(row[0])['evidence_verified'] is False for row in resolutions)
    assert any('Case closed' in item.value for item in app.success)


def test_verified_outcome_is_refused_while_a_task_is_open(app):
    case_id = open_main(app)
    app.button(key='send-request-' + case_id).click().run()
    approve_as_supervisor(app)
    finish(app, case_id, 'verified_resolved', 'Trying to verify before the partner replied')
    assert any('partner task is still open' in item.value for item in app.error)
    with get_connection(app.session_state.db_path) as conn:
        assert conn.execute('SELECT status FROM case_records WHERE case_id=?', (case_id,)).fetchone()[0] != 'closed'
        assert conn.execute('SELECT COUNT(*) FROM finding_reviews').fetchone()[0] == 0


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
    app.button(key='back-to-cases').click().run()
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
    app.radio(key='choice-'+case_id).set_value('Finish the case').run()
    finish(app,case_id,'closed_unresolved','Reviewed the denied access and recorded assignment context')
    healthy(app)
    app.button(key='nav-Home').click().run()
    app.button(key='counter-resolved').click().run()
    shown={b.key.removeprefix('open-') for b in app.button if (b.key or '').startswith('open-')}
    assert shown=={case_id}
    assert app.session_state.primary_destination=='Home'


def test_investigator_draft_survives_navigation_and_role_switch_unblocks_approval(app):
    app.session_state.actor_role='investigator'
    case_id=open_main(app)
    widget(app.text_area,'Message to the partner').set_value('Keep this request draft while checking the photos').run()
    app.button(key='back-to-cases').click().run()
    open_main(app)
    assert widget(app.text_area,'Message to the partner').value=='Keep this request draft while checking the photos'
    app.button(key='send-request-'+case_id).click().run()
    healthy(app)
    assert not [b for b in app.button if (b.key or '').startswith('approve-send-')]
    app.button(key='switch-approver').click().run()
    healthy(app)
    assert app.session_state.actor_context['role']=='approver'
    assert keyed(app.button,'approve-send-').disabled, 'a decision reason is required before approving'
    keyed(app.text_area,'approval-note-').set_value('Reviewed the evidence; a fresh weight is needed').run()
    keyed(app.button,'approve-send-').click().run()
    healthy(app)
    with get_connection(app.session_state.db_path) as conn:
        assert conn.execute('SELECT status FROM action_requests WHERE case_id=?',(case_id,)).fetchone()[0]=='executed'


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
