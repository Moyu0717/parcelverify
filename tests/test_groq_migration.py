"""Mocked Groq transport and persistent usage/idempotency; no live API calls."""
import json
import threading
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest
from agent.runner import ModelProvider, investigate_case
from agent.configuration import load_server_configuration, provider_settings
from agent.usage import reserve_request, UsageLimit
from db import get_connection
from tests.test_agent import seeded_db,ADMIN_ACTOR,_create_case_for_investigation,ScriptedProvider,valid_report

@pytest.fixture(autouse=True)
def isolation(monkeypatch,tmp_path):
    monkeypatch.setenv('PV_DATA_DIR',str(tmp_path/'guard'))
    monkeypatch.setenv('AI_PROVIDER','groq')
    monkeypatch.delenv('GROQ_API_KEY',raising=False)

def http_error(code):
    return httpx.HTTPStatusError('not exposed',request=httpx.Request('POST','https://api.groq.com'),response=httpx.Response(code))

@pytest.mark.parametrize('code,status',[(429,'rate_limited'),(401,'authentication_failed'),(403,'authentication_failed'),(404,'model_unavailable')])
def test_http_failure_has_no_retry_or_fallback(seeded_db,code,status):
    cid=_create_case_for_investigation(seeded_db)['case_id'];p=ScriptedProvider([http_error(code)])
    r=investigate_case(seeded_db,cid,ADMIN_ACTOR,provider=p)
    assert r['status']==status and r['report'] is None and len(p.calls)==1

def test_missing_key_cannot_activate_legacy_provider(monkeypatch,seeded_db):
    monkeypatch.setenv('PV_AI_PROVIDER','gemini');monkeypatch.setenv('GEMINI_API_KEY','old-private-test-value')
    monkeypatch.setenv('PV_AI_BASE_URL','https://paid.invalid')
    cid=_create_case_for_investigation(seeded_db)['case_id']
    r=investigate_case(seeded_db,cid,ADMIN_ACTOR)
    assert r['status']=='missing_configuration' and r['request_count']==0
    assert 'old-private-test-value' not in str(r)
    monkeypatch.setenv('AI_PROVIDER','openai')
    assert investigate_case(seeded_db,cid,ADMIN_ACTOR)['status']=='config_disabled'

def test_secrets_precedence_and_other_keys_ignored(monkeypatch):
    monkeypatch.setenv('GROQ_MODEL','environment-model')
    load_server_configuration({'GROQ_MODEL':'secret-model','PV_AI_PROVIDER':'gemini'})
    assert provider_settings()['model']=='secret-model' and provider_settings()['provider']=='groq'

def test_hosted_agent_model_cannot_enable_browser_or_code_tools(monkeypatch):
    monkeypatch.setenv('GROQ_MODEL','groq/compound')
    with pytest.raises(ValueError,match='hosted agent systems are disabled'):ModelProvider()

def test_groq_transport_is_fixed_bounded_and_no_hosted_tools(monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY','private-test-value');monkeypatch.setenv('PV_AI_BASE_URL','https://paid.invalid')
    seen=[]
    def handler(req):seen.append(req);return httpx.Response(200,json={'choices':[{'message':{'content':'{}'},'finish_reason':'stop'}]})
    client=httpx.Client(transport=httpx.MockTransport(handler))
    kwargs=[]
    def factory(**options):kwargs.append(options);return client
    monkeypatch.setattr('agent.runner.httpx.Client',factory)
    ModelProvider().generate([],100,True)
    assert str(seen[0].url)=='https://api.groq.com/openai/v1/chat/completions'
    payload=json.loads(seen[0].content)
    assert payload['max_completion_tokens']==1024 and payload['response_format']['json_schema']['strict']
    assert 'tools' not in payload and 'private-test-value' not in seen[0].content.decode()
    assert kwargs[0]['timeout']==20 and kwargs[0]['trust_env'] is False

def test_one_transient_retry_and_six_request_ceiling(seeded_db):
    cid=_create_case_for_investigation(seeded_db)['case_id']
    call={'tool_call':{'tool':'get_partner_metrics','params':{}}}
    p=ScriptedProvider([http_error(503),call,call,call,call,valid_report()])
    r=investigate_case(seeded_db,cid,ADMIN_ACTOR,provider=p)
    assert r['status']=='completed' and r['request_count']==6 and len(r['tool_calls'])==4
    p=ScriptedProvider([http_error(503)]*2)
    r=investigate_case(seeded_db,cid,ADMIN_ACTOR,provider=p)
    assert r['status']=='error' and len(p.calls)==2 and r['report'] is None

def test_completed_submission_reused_and_new_evidence_requires_new_id(seeded_db):
    cid=_create_case_for_investigation(seeded_db)['case_id']
    p=ScriptedProvider([{'tool_call':{'tool':'get_shipment_timeline','params':{}}},{'done':True},valid_report()])
    first=investigate_case(seeded_db,cid,ADMIN_ACTOR,provider=p,request_id='click-1')
    assert first['status']=='completed'
    again=investigate_case(seeded_db,cid,ADMIN_ACTOR,provider=p,request_id='click-1')
    assert again['deduplicated'] and again['status']=='completed' and len(p.calls)==3
    with get_connection(seeded_db) as c:c.execute("UPDATE events SET source='new confirmed source' WHERE shipment_id='PV-DEMO-001'")
    r=investigate_case(seeded_db,cid,ADMIN_ACTOR,provider=p,request_id='click-1')
    assert r['status']=='error' and 'changed' in r['error'] and len(p.calls)==3
    fresh=ScriptedProvider([{'done':True},valid_report()])
    assert investigate_case(seeded_db,cid,ADMIN_ACTOR,provider=fresh,request_id='click-2')['status']=='completed'

def test_inflight_double_submission_does_not_call_twice(seeded_db):
    cid=_create_case_for_investigation(seeded_db)['case_id'];entered=threading.Event();release=threading.Event()
    class Blocking(ScriptedProvider):
        def generate(self,*a,**kw):entered.set();release.wait(5);return super().generate(*a,**kw)
    p=Blocking([{'done':True},valid_report()])
    with ThreadPoolExecutor(2) as pool:
        first=pool.submit(investigate_case,seeded_db,cid,ADMIN_ACTOR,provider=p,request_id='double')
        assert entered.wait(5)
        second=investigate_case(seeded_db,cid,ADMIN_ACTOR,provider=p,request_id='double')
        assert second['status']=='running' and second['deduplicated']
        release.set();assert first.result()['status']=='completed'
    assert len(p.calls)==2

def test_shared_ledger_is_atomic_and_survives_new_connections(monkeypatch):
    monkeypatch.setenv('GROQ_GLOBAL_DAILY','1')
    def reserve():
        try:reserve_request(100);return True
        except UsageLimit:return False
    with ThreadPoolExecutor(4) as pool:assert sum(pool.map(lambda _:reserve(),range(4)))==1
    assert not reserve()

def test_malformed_and_timeout_never_save_conclusion(seeded_db):
    cid=_create_case_for_investigation(seeded_db)['case_id']
    class Bad:
        model_name='mock'
        def generate(self,*a,**k):return 'not JSON'
    r=investigate_case(seeded_db,cid,ADMIN_ACTOR,provider=Bad())
    assert r['status']=='invalid_output' and r['report'] is None
    r=investigate_case(seeded_db,cid,ADMIN_ACTOR,provider=ScriptedProvider([httpx.ReadTimeout('timeout')]))
    assert r['status']=='timeout' and r['request_count']==1

def test_featured_linked_case_compact_tool_has_real_citations(seeded_db):
    from services.workflow import initialize_reviews
    from services.cases import ensure_case_links,list_cases
    from agent.runner import _tool_message
    from agent.tools import dispatch_tool
    initialize_reviews(seeded_db,ADMIN_ACTOR);ensure_case_links(seeded_db,ADMIN_ACTOR)
    cid=next(c for c in list_cases(seeded_db,ADMIN_ACTOR) if c['shipment_id']=='PV-DEMO-001')['case_id']
    output=dispatch_tool(seeded_db,'get_case_context',{}, {'case_id':cid},ADMIN_ACTOR)
    encoded,refs=_tool_message(output)
    compact=json.loads(encoded)
    assert len(compact['shipments'])==2 and compact['findings'] and refs
    assert len(encoded)<10000
    report=valid_report();report['facts']=[{'text':'A recorded finding requires review.','evidence_ids':[next(iter(refs))]}]
    p=ScriptedProvider([{'tool_call':{'tool':'get_case_context','params':{}}},{'done':True},report])
    assert investigate_case(seeded_db,cid,ADMIN_ACTOR,provider=p)['status']=='completed'
