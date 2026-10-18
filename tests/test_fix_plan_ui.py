"""Actual widgets: clarification remains usable while approval is pending."""
from tests.test_ui_refactor import app,open_main,widget,healthy
from db import get_connection

def test_pending_approval_can_receive_requested_clarification(app):
    cid=open_main(app);path=app.session_state.db_path
    widget(app.text_area,'Reason for the request').set_value('Clarify the original measurement conditions')
    widget(app.button,'Send request for approval').click().run();healthy(app)
    with get_connection(path) as conn:
        action=conn.execute('SELECT action_id FROM action_requests WHERE case_id=?',(cid,)).fetchone()[0]
    widget(app.text_area,'What information is needed?').set_value('Describe the original weighing and packaging context')
    widget(app.button,'Record information request').click().run();healthy(app)
    assert widget(app.button,'Approve request')
    note=widget(app.text_area,'Evidence or explanation')
    note.set_value('Original measurement conditions are not yet independently confirmed.')
    when=widget(app.text_input,'Evidence event time (ISO 8601 with timezone offset)')
    when.set_value('2026-09-02T09:00:00')
    widget(app.button,'Submit evidence for review').click().run()
    assert not app.exception and any('timezone' in error.value for error in app.error)
    assert widget(app.text_area,'Evidence or explanation').value.startswith('Original measurement')
    assert widget(app.text_input,'Evidence event time (ISO 8601 with timezone offset)').value=='2026-09-02T09:00:00'
    widget(app.text_input,'Evidence event time (ISO 8601 with timezone offset)').set_value('2026-09-02T09:00:00+08:00')
    widget(app.button,'Submit evidence for review').click().run();healthy(app)
    with get_connection(path) as conn:
        assert conn.execute('SELECT status FROM action_requests WHERE action_id=?',(action,)).fetchone()[0]=='proposed'
        assert conn.execute('SELECT COUNT(*) FROM task_submissions').fetchone()[0]==1
