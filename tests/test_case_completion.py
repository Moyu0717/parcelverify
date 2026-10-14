"""Consequential linkage, task, closure, scope and approval regressions."""
import json
from datetime import datetime,timezone
import pytest
from db import init_db,get_connection
from seed import seed_demo
from services.workflow import initialize_reviews
from services.review import ensure_access_cases
from services.cases import ensure_case_links,get_case_context,list_cases,review_finding,close_case
from services.followups import submit_task_response,review_task_response
from services.actions import propose_action,review_action,execute_action,revise_request
from services.case_export import export_case
from services.access_patterns import evaluate_access_patterns

ADMIN={'actor_id':'ADMIN-001','role':'admin','session_id':'completion'}
PARTNER={'actor_id':'ACTOR-QR-01','partner_id':'P-QUICKRUN','role':'partner_user','session_id':'completion'}
STRANGER={'actor_id':'ACTOR-SL-01','partner_id':'P-SAFELOG','role':'partner_user','session_id':'completion'}

@pytest.fixture
def demo(tmp_path):
    path=str(tmp_path/'demo.db');init_db(path);seed_demo(path);initialize_reviews(path,ADMIN);ensure_access_cases(path,ADMIN);ensure_case_links(path,ADMIN)
    cases=list_cases(path,ADMIN)
    return path,next(c for c in cases if c['shipment_id']=='PV-DEMO-001')['case_id']

def request(path,cid):
    action=propose_action(path,cid,'request_reweigh',ADMIN,reason='Check the unexplained weight difference')
    review_action(path,action['action_id'],'approve',ADMIN,'Review evidence and obtain a fresh measurement')
    result=execute_action(path,action['action_id'],ADMIN)
    return action['action_id'],result['after']['evidence_task_id']

def test_linkage_clean_background_and_idempotence(demo):
    path,cid=demo;ctx=get_case_context(path,cid,ADMIN)
    assert set(ctx['shipment_ids'])=={'PV-DEMO-001','PV-SHIP-010'}
    assert {'weight_diff','photo_reuse','access_anomaly'}<={f['category'] for f in ctx['findings']}
    before=[f['finding_id'] for f in ctx['findings']];ensure_case_links(path,ADMIN)
    assert before==[f['finding_id'] for f in get_case_context(path,cid,ADMIN)['findings']]
    assert len(list_cases(path,ADMIN))==3
    assert evaluate_access_patterns(path,'PV-SHIP-011')[0]['category']=='authorized_export'
    assert evaluate_access_patterns(path,'PV-DEMO-001')[0]['category']=='access_anomaly'

def test_task_response_review_and_supported_closure(demo):
    path,cid=demo;aid,tid=request(path,cid)
    assert execute_action(path,aid,ADMIN)['status']=='already_executed'
    timestamp=datetime.now(timezone.utc).isoformat();payload={'weight_g':2000,'count':1,'seal_id':'SEAL-07','notes':'Reweighed on a checked scale after investigation'}
    submission=submit_task_response(path,tid,PARTNER,payload,timestamp,submission_key='response-1')
    assert not submit_task_response(path,tid,PARTNER,payload,timestamp,submission_key='response-1')['is_new']
    case=next(c for c in list_cases(path,ADMIN) if c['case_id']==cid);assert case['work_bucket']=='needs_review'
    with pytest.raises(ValueError):close_case(path,cid,ADMIN,'verified_resolved','The submitted response needs human review',[submission['event_id']])
    review_task_response(path,submission['submission_id'],ADMIN,'accept','The supplied measurement is documented and usable')
    ctx=get_case_context(path,cid,ADMIN)
    for f in ctx['findings']:
        review_finding(path,f['finding_id'],ADMIN,'resolved','Reviewed the original signal and supporting response',f['evidence_ids'] or [submission['event_id']])
    assert close_case(path,cid,ADMIN,'verified_resolved','All required findings and the response were reviewed',[submission['event_id']])['is_new']
    export=export_case(path,cid,ADMIN)
    assert export['decisions'][-1]['outcome']=='verified_resolved'
    assert export['submissions'][0]['review_status']=='accepted'

def test_admin_closure_is_not_verification_and_late_evidence_reopens(demo):
    path,cid=demo;_,tid=request(path,cid)
    closed=close_case(path,cid,ADMIN,'closed_unresolved','Stop this investigation with the evidence gaps recorded')
    assert closed['outcome']=='closed_unresolved'
    with get_connection(path) as conn:
        row=conn.execute('SELECT status,resolution_json FROM evidence_tasks WHERE task_id=?',(tid,)).fetchone()
        assert row[0]=='cancelled' and json.loads(row[1])['evidence_verified'] is False
    submit_task_response(path,tid,PARTNER,{'weight_g':2000},datetime.now(timezone.utc).isoformat(),submission_key='late-response')
    assert next(c for c in list_cases(path,ADMIN) if c['case_id']==cid)['display_status']=='Needs review'

def test_permissions_and_retry_do_not_leak(demo):
    path,cid=demo;_,tid=request(path,cid)
    with pytest.raises(Exception):get_case_context(path,cid,STRANGER)
    with pytest.raises(Exception):export_case(path,cid,STRANGER)
    with pytest.raises(Exception):submit_task_response(path,tid,STRANGER,{'weight_g':2000},datetime.now(timezone.utc).isoformat(),submission_key='foreign')
    with pytest.raises(Exception):review_finding(path,get_case_context(path,cid,ADMIN)['findings'][0]['finding_id'],PARTNER,'resolved','Unsupported external review',[])
    with get_connection(path) as conn:conn.execute("UPDATE assignments SET valid_until='2020-01-01T00:00:00+00:00' WHERE actor_id='ACTOR-QR-01'")
    with pytest.raises(Exception):get_case_context(path,cid,PARTNER)

def test_revision_invalidates_approval(demo):
    path,cid=demo
    action=propose_action(path,cid,'request_reweigh',ADMIN,reason='Obtain a new scale measurement')
    review_action(path,action['action_id'],'approve',ADMIN,'Reviewed the original measurement request')
    revised=revise_request(path,action['action_id'],ADMIN,'Use a calibrated scale and attach its reading',request_id='revision-1')
    assert execute_action(path,action['action_id'],ADMIN)['status']=='not_approved'
    assert execute_action(path,revised['action_id'],ADMIN)['status']=='not_approved'

def test_failed_submission_audit_rolls_back(demo,monkeypatch):
    import services.followups as follow
    path,cid=demo;_,tid=request(path,cid)
    with get_connection(path) as conn:before=conn.execute('SELECT COUNT(*) FROM events').fetchone()[0]
    def fail(*a,**k):raise RuntimeError('Injected audit failure')
    monkeypatch.setattr(follow,'append_audit',fail)
    with pytest.raises(RuntimeError):submit_task_response(path,tid,PARTNER,{'weight_g':2000},datetime.now(timezone.utc).isoformat(),submission_key='rollback')
    with get_connection(path) as conn:
        assert conn.execute('SELECT COUNT(*) FROM events').fetchone()[0]==before
        assert conn.execute('SELECT status FROM evidence_tasks WHERE task_id=?',(tid,)).fetchone()[0]=='open'

def test_approval_is_bound_to_exact_request(demo):
    path,cid=demo
    action=propose_action(path,cid,'request_reweigh',ADMIN,reason='Original authorized weight check')
    review_action(path,action['action_id'],'approve',ADMIN,'Approve this exact measurement request')
    with get_connection(path) as conn:conn.execute("UPDATE action_requests SET reason='A different request after approval' WHERE action_id=?",(action['action_id'],))
    with pytest.raises(Exception,match='approval'):execute_action(path,action['action_id'],ADMIN)

def test_incomplete_case_cannot_be_verified_from_an_explanation_alone(demo):
    path,_=demo
    case=next(c for c in list_cases(path,ADMIN) if c['shipment_id']=='PV-SHIP-021')
    for f in get_case_context(path,case['case_id'],ADMIN)['findings']:
        review_finding(path,f['finding_id'],ADMIN,'supported','The missing fact is recorded but is not a new measurement',f['evidence_ids'])
    with pytest.raises(ValueError):close_case(path,case['case_id'],ADMIN,'verified_resolved','A narrative should not verify missing measurements',[get_case_context(path,case['case_id'],ADMIN)['findings'][0]['evidence_ids'][0]])
