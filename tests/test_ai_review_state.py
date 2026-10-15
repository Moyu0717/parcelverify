"""Shared AI states and safe HTTP diagnostics. All model requests are mocked."""
import json
from datetime import datetime,timezone,timedelta
import httpx
import pytest
from agent.diagnostics import provider_metadata
from agent.runner import investigate_case,recover_abandoned_runs
from services.ai_state import derive_ai_state,case_ai_state
from db import get_connection
from tests.test_agent import seeded_db,ADMIN_ACTOR,_create_case_for_investigation,ScriptedProvider,valid_report

CONFIG={'enabled':True,'configured':True,'model':'openai/gpt-oss-20b'}

def test_configuration_is_not_a_provider_validation():
    state=derive_ai_state(CONFIG)
    assert state['state']=='not_started' and state['can_run']
    assert state['provider_outcome']=='Unvalidated' and 'unavailable' not in state['message']
    assert not derive_ai_state(dict(CONFIG,configured=False))['can_run']
    assert not derive_ai_state(dict(CONFIG,enabled=False))['can_run']

@pytest.mark.parametrize('status',['authentication_failed','model_unavailable','rate_limited','usage_limited','timeout','invalid_output','interrupted','ai_not_running','error'])
def test_failure_is_retryable_but_never_a_completed_review(status):
    state=derive_ai_state(CONFIG,{'run_id':'run-1','status':status,'error':'safe'})
    assert state['state']!='completed' and state['can_run']
    assert state['reference']=='run-1' and state['action']=='Retry AI review'

def test_retry_after_and_running_prevent_requests():
    retry=(datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat()
    state=derive_ai_state(CONFIG,{'status':'rate_limited','diagnostics_json':json.dumps({'retry_at':retry,'http_status':429})})
    assert not state['can_run'] and state['retry_at']==retry
    assert not derive_ai_state(CONFIG,{'status':'running'})['can_run']
    assert derive_ai_state(CONFIG,{'status':'completed'})['state']=='invalid_output'

def test_error_diagnostics_keep_reason_without_provider_payload(monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY','gsk_super_secret')
    response=httpx.Response(400,headers={'x-request-id':'req_safe123','Authorization':'Bearer gsk_super_secret'},json={
        'error':{'type':'invalid_request_error','code':'json_validate_failed',
                 'message':"Failed to generate JSON. Please adjust your prompt. See 'failed_generation' for more details.",
                 'failed_generation':'private evidence gsk_super_secret'}})
    metadata=provider_metadata(response)
    assert metadata['provider_code']=='json_validate_failed'
    assert metadata['provider_type']=='invalid_request_error'
    assert 'Failed to generate JSON' in metadata['provider_message']
    assert metadata['provider_request_id']=='req_safe123'
    assert 'private evidence' not in str(metadata) and 'gsk_super_secret' not in str(metadata)
    reflected=httpx.Response(400,json={'error':{'message':"messages contain patient Alice secret shipment PV-001 token gsk_super_secret",'type':'private secret'}})
    assert 'Alice' not in str(provider_metadata(reflected))
    assert 'gsk_super_secret' not in str(provider_metadata(reflected))
    assert 'private secret' not in str(provider_metadata(reflected))

def test_http_failure_persists_stage_and_does_not_save_report(seeded_db):
    cid=_create_case_for_investigation(seeded_db)['case_id']
    request=httpx.Request('POST','https://api.groq.com/openai/v1/chat/completions')
    response=httpx.Response(400,request=request,json={'error':{'type':'invalid_request_error','code':'json_validate_failed','message':'Failed to generate JSON.','failed_generation':'private'}})
    p=ScriptedProvider([httpx.HTTPStatusError('private body',request=request,response=response)])
    result=investigate_case(seeded_db,cid,ADMIN_ACTOR,provider=p,request_id='failed-click')
    assert result['status']=='invalid_output' and result['report'] is None
    assert len(p.calls)==1 and not result['tool_calls']
    with get_connection(seeded_db) as conn:
        saved=conn.execute('SELECT diagnostics_json FROM investigation_runs WHERE run_id=?',(result['run_id'],)).fetchone()[0]
        assert json.loads(saved)['stage']=='tool_selection_request'
        assert json.loads(saved)['http_status']==400
        assert conn.execute('SELECT COUNT(*) FROM report_versions').fetchone()[0]==0
    assert 'private' not in str(result)

def test_completed_report_retained_after_failed_deliberate_retry(seeded_db,monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY','private-test-value')
    cid=_create_case_for_investigation(seeded_db)['case_id']
    first=investigate_case(seeded_db,cid,ADMIN_ACTOR,provider=ScriptedProvider([{'done':True},valid_report()]),request_id='first')
    assert first['status']=='completed'
    before=case_ai_state(seeded_db,cid,ADMIN_ACTOR)
    assert before['state']=='completed' and before['report']
    with get_connection(seeded_db) as conn:
        conn.execute("UPDATE events SET source='new evidence' WHERE shipment_id='PV-DEMO-001'")
    assert case_ai_state(seeded_db,cid,ADMIN_ACTOR)['state']=='outdated'
    failed=investigate_case(seeded_db,cid,ADMIN_ACTOR,provider=ScriptedProvider([httpx.ReadTimeout('timeout')]),request_id='retry')
    state=case_ai_state(seeded_db,cid,ADMIN_ACTOR)
    assert failed['status']=='timeout' and state['state']=='timeout'
    assert state['previous_report'] and state['report'] and state['report_outdated']

def test_abandoned_run_recovers_without_deleting_history(seeded_db):
    cid=_create_case_for_investigation(seeded_db)['case_id']
    old=(datetime.now(timezone.utc)-timedelta(minutes=10)).isoformat()
    with get_connection(seeded_db) as conn:
        conn.execute("INSERT INTO investigation_runs(run_id,case_id,actor_id,status,started_at) VALUES ('stopped',?,?,'running',?)",(cid,ADMIN_ACTOR['actor_id'],old))
        conn.execute("UPDATE case_records SET status='under_investigation' WHERE case_id=?",(cid,))
    recover_abandoned_runs(seeded_db,cid)
    with get_connection(seeded_db) as conn:
        assert conn.execute("SELECT status FROM investigation_runs WHERE run_id='stopped'").fetchone()[0]=='interrupted'
        assert conn.execute('SELECT status FROM case_records WHERE case_id=?',(cid,)).fetchone()[0]=='pending_review'
