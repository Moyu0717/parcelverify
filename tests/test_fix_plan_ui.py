"""Actual widgets: a partner reply with an ambiguous time is refused without losing the draft."""
from tests.test_ui_refactor import app,open_main,widget,healthy,keyed,approve_as_supervisor
from db import get_connection

def test_partner_reply_requires_timezone_and_keeps_draft(app):
    cid=open_main(app);path=app.session_state.db_path
    widget(app.radio,'What proof do you need?').set_value('request_rescan').run()
    widget(app.text_area,'Message to the partner').set_value('Clarify the original package count conditions')
    app.button(key='send-request-'+cid).click().run();healthy(app)
    approve_as_supervisor(app);healthy(app)
    with get_connection(path) as conn:
        action=conn.execute('SELECT action_id FROM action_requests WHERE case_id=?',(cid,)).fetchone()[0]
    widget(app.text_input,'Package count').set_value('1')
    widget(app.text_area,'Message from the partner').set_value('Original count conditions are not yet independently confirmed.')
    widget(app.text_input,'Check time (ISO 8601)').set_value('2026-09-02T09:00:00')
    widget(app.button,'Send reply as partner').click().run()
    assert not app.exception and any('timezone' in error.value for error in app.error)
    assert widget(app.text_area,'Message from the partner').value.startswith('Original count')
    assert widget(app.text_input,'Check time (ISO 8601)').value=='2026-09-02T09:00:00'
    widget(app.text_input,'Check time (ISO 8601)').set_value('2026-09-02T09:00:00+08:00')
    widget(app.button,'Send reply as partner').click().run();healthy(app)
    with get_connection(path) as conn:
        assert conn.execute('SELECT status FROM action_requests WHERE action_id=?',(action,)).fetchone()[0]=='executed'
        assert conn.execute('SELECT COUNT(*) FROM task_submissions').fetchone()[0]==1
    assert keyed(app.button,'accept-')
