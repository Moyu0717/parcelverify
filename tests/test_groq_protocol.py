"""Native Groq local-function protocol regression; no provider network calls."""
import json
import httpx
import pytest
from agent.runner import ModelProvider,investigate_case
from agent.groq_protocol import local_tools,read_selection,selection_messages
from contracts import TOOL_WHITELIST
from tests.test_agent import seeded_db,ADMIN_ACTOR,_create_case_for_investigation,valid_report

def test_only_read_only_allowlisted_functions_are_declared():
    tools=local_tools()
    assert {tool['function']['name'] for tool in tools}==set(TOOL_WHITELIST)
    for tool in tools:
        assert tool['type']=='function'
        params=tool['function']['parameters']
        assert params['additionalProperties'] is False
        assert not set(params['properties']) & {'actor_id','case_id','shipment_id','partner_id','role'}

@pytest.mark.parametrize('calls',[
 [{'type':'function','function':{'name':'browser_search','arguments':'{}'}}],
 [{'type':'function','function':{'name':'get_case_context','arguments':'{}'}}]*2,
 [{'type':'function','function':{'name':'get_case_context','arguments':'[]'}}],
])
def test_unknown_parallel_and_non_object_calls_fail_closed(calls):
    with pytest.raises(ValueError):read_selection({'tool_calls':calls})

def test_native_request_tool_result_and_final_schema_are_separate(seeded_db,monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY','private-test-value')
    cid=_create_case_for_investigation(seeded_db)['case_id']
    requests=[]
    def handler(request):
        payload=json.loads(request.content);requests.append(payload)
        if len(requests)==1:
            assert payload['tool_choice']=='auto' and payload['parallel_tool_calls'] is False
            assert 'response_format' not in payload
            message={'content':None,'tool_calls':[{'id':'call_provider','type':'function','function':{'name':'get_case_context','arguments':'{}'}}]}
        elif len(requests)==2:
            assert payload['messages'][-1]['role']=='tool'
            previous=payload['messages'][-2]['tool_calls'][0]
            assert payload['messages'][-1]['tool_call_id']==previous['id']
            assert previous['function']['name']=='get_case_context'
            message={'content':'{"done":true}'}
        else:
            assert 'tools' not in payload and 'tool_choice' not in payload
            assert payload['response_format']['type']=='json_schema'
            assert payload['response_format']['json_schema']['strict'] is True
            refs=json.loads(payload['messages'][-1]['content'].split('Valid IDs: ')[1])
            report=valid_report();report['facts']=[{'text':'A source finding requires review.','evidence_ids':[refs[0]]}]
            message={'content':json.dumps(report)}
        return httpx.Response(200,json={'choices':[{'message':message,'finish_reason':'tool_calls' if len(requests)==1 else 'stop'}]})
    client_type=httpx.Client
    monkeypatch.setattr('agent.runner.httpx.Client',lambda **kwargs:client_type(transport=httpx.MockTransport(handler)))
    result=investigate_case(seeded_db,cid,ADMIN_ACTOR,provider=ModelProvider(),request_id='native-regression')
    assert result['status']=='completed' and result['report']['facts']
    assert len(result['tool_calls'])==1 and len(requests)==3
    assert 'private-test-value' not in str(requests) and 'private-test-value' not in str(result)

def test_unpaired_selection_is_rejected_before_transport():
    with pytest.raises(ValueError,match='no recorded result'):
        selection_messages([{'role':'system','content':'Read records'}, {'role':'assistant','content':'{"tool_call":{"tool":"get_case_context","params":{}}}'}])
