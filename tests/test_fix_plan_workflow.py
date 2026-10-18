"""Human decision and request-more regressions on isolated synthetic data."""
from datetime import datetime, timezone
import pytest
from contracts import AuthorizationError, IdempotencyError
from db import init_db, get_connection
from seed import seed_demo
from services.workflow import initialize_reviews
from services.actions import propose_action, review_action, execute_action
from services.cases import get_case_context, list_cases, review_finding, close_case
from services.followups import submit_task_response, review_task_response
from services.case_export import export_case

INV = dict(actor_id='INV-001', role='investigator', session_id='fix-plan')
SUP = dict(actor_id='SUP-001', role='approver', session_id='fix-plan')
PARTNER = dict(actor_id='ACTOR-QR-01', partner_id='P-QUICKRUN', role='partner_user', session_id='fix-plan')

@pytest.fixture
def demo(tmp_path):
    path=str(tmp_path/'workflow.db')
    init_db(path); seed_demo(path); initialize_reviews(path, INV)
    cid=next(c['case_id'] for c in list_cases(path,INV) if c['shipment_id']=='PV-DEMO-001')
    return path,cid

def test_rejection_pending_and_role_restrictions(demo):
    path,cid=demo
    action=propose_action(path,cid,'request_reweigh',INV,reason='Obtain a fresh scale reading')['action_id']
    assert execute_action(path,action,SUP)['status']=='not_approved'
    for actor in (INV,PARTNER):
        with pytest.raises(AuthorizationError):review_action(path,action,'approve',actor)
        with pytest.raises(AuthorizationError):execute_action(path,action,actor)
    review_action(path,action,'reject',SUP,'Existing request needs a more precise measurement method')
    assert execute_action(path,action,SUP)['status']=='not_approved'
    with pytest.raises(IdempotencyError):review_action(path,action,'approve',SUP)
    with get_connection(path) as conn:
        assert not conn.execute('SELECT 1 FROM evidence_tasks WHERE case_id=? AND task_type=?',(cid,'reweigh')).fetchone()
        audit=conn.execute("SELECT actor_id,details_json FROM audit_log WHERE case_id=? AND operation='action_rejected'",(cid,)).fetchone()
        assert audit and audit[0]==SUP['actor_id'] and 'precise measurement method' in audit[1]

def test_request_more_preserves_other_findings_and_audit(demo):
    path,cid=demo
    action=propose_action(path,cid,'request_reweigh',INV,reason='Fresh weighing cannot explain the earlier loss alone')['action_id']
    review_action(path,action,'approve',SUP,'Fresh measurement requested with original records retained')
    task=execute_action(path,action,SUP)['after']['evidence_task_id']
    assert execute_action(path,action,SUP)['status']=='already_executed'
    stamp=datetime.now(timezone.utc).isoformat()
    response=submit_task_response(path,task,PARTNER,{'weight_g':2000,'notes':'Fresh scale reading only'},stamp,submission_key='first')
    with pytest.raises(AuthorizationError):review_task_response(path,response['submission_id'],PARTNER,'accept','Partner cannot verify its own response')
    review_task_response(path,response['submission_id'],SUP,'request_more','Attach the scale identity and original weighing context')
    assert not review_task_response(path,response['submission_id'],SUP,'request_more','Attach the scale identity and original weighing context')['is_new']
    with get_connection(path) as conn:assert conn.execute('SELECT status FROM evidence_tasks WHERE task_id=?',(task,)).fetchone()[0]=='open'
    second=submit_task_response(path,task,PARTNER,{'weight_g':1900,'notes':'Scale S1 correction; earlier packaging remains unexplained'},stamp,submission_key='second')
    assert not submit_task_response(path,task,PARTNER,{'weight_g':1900,'notes':'Scale S1 correction; earlier packaging remains unexplained'},stamp,submission_key='second')['is_new']
    review_task_response(path,second['submission_id'],SUP,'accept','New measurement can be used; historical causation remains unknown')
    from services.handoff import compare_handoff
    assert compare_handoff(path,'PV-DEMO-001')['weight_g']['actual']==1900
    ctx=get_case_context(path,cid,INV)
    weight=next(f for f in ctx['findings'] if f['category']=='weight_diff')
    review_finding(path,weight['finding_id'],INV,'unresolved','Fresh measurement does not prove the historical discrepancy harmless',[second['event_id']])
    assert all(f['state']=='unreviewed' for f in get_case_context(path,cid,INV)['findings'] if f['category']=='photo_reuse')
    with pytest.raises(ValueError):close_case(path,cid,SUP,'verified_resolved','Unrelated findings are still outstanding',[second['event_id']])
    close_case(path,cid,SUP,'closed_unresolved','Historical discrepancy and photo reuse remain explicitly unresolved')
    exported=export_case(path,cid,SUP)
    operations=[r['operation'] for r in exported['activity']]
    assert operations.count('action_executed')==1
    assert operations.count('evidence_submitted')==2
    assert operations.count('evidence_reviewed')==2
    assert exported['decisions'][-1]['outcome']=='closed_unresolved'
    assert all(r['actor_id'] and r['occurred_at'] for r in exported['activity'])
