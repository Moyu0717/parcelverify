"""3D-originated requests retain a validated, immutable source association."""
import json
import pytest
from tests.test_actions import seeded_db, _create_case, INVESTIGATOR
from services.actions import propose_action
from contracts import AuthorizationError, IdempotencyError
from db import get_connection

def test_source_link_persists_and_retry_cannot_switch_record(seeded_db):
    with get_connection(seeded_db) as conn:
        events=[r[0] for r in conn.execute("SELECT event_id FROM events WHERE shipment_id='PV-DEMO-001' LIMIT 2")]
    case=_create_case(seeded_db,event_id=events[0])
    args=dict(db_path=seeded_db,case_id=case['case_id'],action_type='request_reweigh',actor_context=INVESTIGATOR,reason='Check the selected measurement',request_id='scene-request',source_event_id=events[0])
    first=propose_action(**args)
    assert not propose_action(**args)['is_new']
    with get_connection(seeded_db) as conn:
        audit=[json.loads(r[0]) for r in conn.execute("SELECT details_json FROM audit_log WHERE operation='action_proposed'")]
    assert next(a for a in audit if a['action_id']==first['action_id'])['source_event_id']==events[0]
    with pytest.raises(IdempotencyError):propose_action(**dict(args,source_event_id=events[1]))

def test_selected_source_cannot_belong_to_another_shipment(seeded_db):
    case=_create_case(seeded_db)
    with get_connection(seeded_db) as conn:
        other=conn.execute("SELECT event_id FROM events WHERE shipment_id!='PV-DEMO-001' LIMIT 1").fetchone()[0]
        before=conn.execute('SELECT COUNT(*) FROM action_requests').fetchone()[0]
    with pytest.raises(AuthorizationError):
        propose_action(seeded_db,case['case_id'],'request_reweigh',INVESTIGATOR,source_event_id=other)
    with get_connection(seeded_db) as conn:
        assert conn.execute('SELECT COUNT(*) FROM action_requests').fetchone()[0]==before

def test_scene_tracks_persisted_request_task_and_response(seeded_db,monkeypatch):
    from ui.evidence_map import scene_data,operational_nodes
    from services.actions import review_action,execute_action
    from services.followups import submit_task_response,review_task_response
    from tests.test_actions import ADMIN
    from datetime import datetime,timezone
    with get_connection(seeded_db) as conn:
        eid=conn.execute("SELECT event_id FROM events WHERE shipment_id='PV-DEMO-001' AND event_type='handoff_submitted'").fetchone()[0]
    created=_create_case(seeded_db,event_id=eid)
    case=dict(case_id=created['case_id'],shipment_id='PV-DEMO-001',work_bucket='needs_review')
    def rows(sql,args=()):
        with get_connection(seeded_db) as conn:
            conn.row_factory=__import__('sqlite3').Row
            return [dict(r) for r in conn.execute(sql,args)]
    monkeypatch.setattr('ui.live.context',lambda:(seeded_db,ADMIN))
    monkeypatch.setattr('ui.live.rows',rows)
    def nodes():return operational_nodes(case,scene_data(case))
    action=propose_action(seeded_db,case['case_id'],'request_reweigh',ADMIN,reason='Recheck this recorded measurement',source_event_id=eid)
    assert next(n for n in nodes() if n['id']==eid)['workflow']=='Awaiting approval'
    review_action(seeded_db,action['action_id'],'approve',{'actor_id':'APPROVER-001','role':'approver','session_id':'separate-approver'},'Reviewed the evidence for this test')
    assert next(n for n in nodes() if n['id']==eid)['workflow']=='Approved · apply next'
    execute_action(seeded_db,action['action_id'],ADMIN)
    task=next(n for n in nodes() if n['kind']=='task')
    assert task['status']=='Awaiting response'
    response=submit_task_response(seeded_db,task['task_id'],ADMIN,{'weight_g':2000,'notes':'Fresh weight from the partner scale'},datetime.now(timezone.utc).isoformat(),submission_key='scene-response')
    assert next(n for n in nodes() if n['id']==eid)['workflow']=='Response needs review'
    review_task_response(seeded_db,response['submission_id'],ADMIN,'accept','Checked the source and the newly recorded measurement')
    assert next(n for n in nodes() if n['id']==eid)['workflow']=='Response reviewed'
    assert next(n for n in nodes() if n['id']==response['event_id'])['workflow']=='Response accepted'
    assert next(n for n in nodes() if n['id']==eid)['status']=='Difference'
