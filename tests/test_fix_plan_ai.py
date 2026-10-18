"""Reproduce second-request Groq rejection and verify bounded correction offline."""
import json
import httpx
import pytest
from agent.runner import ModelProvider,investigate_case
from agent.tool_registry import TOOL_REGISTRY,validate_tool_arguments
from tests.test_agent import seeded_db,ADMIN_ACTOR,_create_case_for_investigation,valid_report
from db import get_connection

@pytest.mark.parametrize('recover',[True,False])
def test_second_request_unregistered_function_correction_is_bounded(seeded_db,monkeypatch,recover):
    monkeypatch.setenv('GROQ_API_KEY','private-test-key')
    cid=_create_case_for_investigation(seeded_db)['case_id'];seen=[]
    def response(message,finish='stop'):
        return httpx.Response(200,json={'choices':[{'finish_reason':finish,'message':message}]})
    def call(name,identifier):
        return {'content':None,'tool_calls':[{'id':identifier,'type':'function','function':{'name':name,'arguments':'{}'}}]}
    def handler(request):
        data=json.loads(request.content);seen.append(data);index=len(seen)
        if index==1:return response(call('get_case_context','call_actual_original'),'tool_calls')
        if index in (2,3):
            assert {t['function']['name'] for t in data['tools']}==set(TOOL_REGISTRY)
            assert data['messages'][-2]['tool_calls'][0]['id']=='call_actual_original'
            assert data['messages'][-1]['tool_call_id']=='call_actual_original'
            assert data['messages'][-1]['name']=='get_case_context'
            if index==2 or not recover:
                return httpx.Response(400,json={'error':{'code':'tool_use_failed','type':'invalid_request_error',
                    'message':"Failed to call a function. Attempted function 'get_vendor_contract' was not in request.tools.",
                    'failed_generation':'private evidence and private-test-key'}})
            assert 'previous request was rejected' in data['messages'][0]['content']
            return response(call('get_context_events','call_actual_second'),'tool_calls')
        if index==4:
            assert data['messages'][-1]['tool_call_id']=='call_actual_second'
            return response({'content':'{"done":true}'})
        assert index==5 and 'tools' not in data
        refs=json.loads(data['messages'][-1]['content'].split('Valid IDs: ')[1])
        report=valid_report();report['facts']=[{'text':'Recorded measurements need review.','evidence_ids':[refs[0]]}]
        return response({'content':json.dumps(report)})
    client_type=httpx.Client
    monkeypatch.setattr('agent.runner.httpx.Client',lambda **kwargs:client_type(transport=httpx.MockTransport(handler)))
    result=investigate_case(seeded_db,cid,ADMIN_ACTOR,provider=ModelProvider(),request_id='second-round-error')
    assert result['diagnostics']['retry_count']==1
    assert result['diagnostics']['request_history'][1]['provider_code']=='tool_use_failed'
    assert 'private evidence' not in str(result) and 'private-test-key' not in str(result)
    assert result['request_count']==(5 if recover else 3)
    assert len(result['tool_calls'])==(2 if recover else 1)
    with get_connection(seeded_db) as conn:
        assert conn.execute('SELECT COUNT(*) FROM report_versions').fetchone()[0]==(1 if recover else 0)
    assert result['status']==('completed' if recover else 'invalid_output')

@pytest.mark.parametrize('name,arguments',[
 ('functions.compare_handoff',{}),('compare_handoff',{'shipment_id':'other'}),
 ('find_photo_reuse',{}),('get_vendor_context',{'at_time':'2026-01-01T01:00:00'}),
 ('get_vendor_context',{'at_time':False}),('get_case_context',[]),
])
def test_canonical_registry_rejects_unknown_or_scope_arguments(name,arguments):
    with pytest.raises(ValueError):validate_tool_arguments(name,arguments)

def test_truncated_selection_is_not_retried_or_reported_as_success(seeded_db,monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY','private-test-key')
    cid=_create_case_for_investigation(seeded_db)['case_id'];requests=[]
    def handler(request):
        requests.append(request)
        return httpx.Response(200,json={'choices':[{'finish_reason':'length','message':{'content':'{"unfinished":'}}]})
    client_type=httpx.Client
    monkeypatch.setattr('agent.runner.httpx.Client',lambda **kwargs:client_type(transport=httpx.MockTransport(handler)))
    result=investigate_case(seeded_db,cid,ADMIN_ACTOR,provider=ModelProvider())
    assert result['status']!='completed' and result['report'] is None and not result['tool_calls']
    assert len(requests)==1 and result['diagnostics']['finish_reason']=='length'
    with get_connection(seeded_db) as conn:
        assert not conn.execute('SELECT 1 FROM report_versions').fetchone()
