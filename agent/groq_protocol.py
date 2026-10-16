"""Groq local-function protocol. No hosted tools or identity arguments."""
import json
from contracts import TOOL_WHITELIST

DESCRIPTIONS={
 'get_case_context':'Read linked, permitted shipment and account findings, recorded handoffs and context.',
 'get_vendor_context':'Read recorded partner contract context; optionally at a recorded ISO timestamp.',
 'get_shipment_timeline':'Read the current shipment timeline and photo record identifiers.',
 'compare_handoff':'Compare recorded shipment measurements; missing values remain unknown.',
 'find_photo_reuse':'Compare a retrieved photo identifier against permitted records.',
 'check_access_scope':'Read recorded requests and independent permission findings.',
 'get_partner_metrics':'Read aggregate partner evidence metrics.',
 'get_context_events':'Read recorded business explanations and contextual events, including approved work.',
}

def local_tools():
    tools=[]
    for name in TOOL_WHITELIST:
        properties={};required=[]
        if name=='find_photo_reuse':
            properties={'photo_id':{'type':'string','description':'An actual photo identifier from retrieved records.'}};required=['photo_id']
        elif name=='get_vendor_context':properties={'at_time':{'type':'string','description':'Optional ISO 8601 time from a source record.'}}
        tools.append({'type':'function','function':{'name':name,'description':DESCRIPTIONS.get(name,'Read permitted case records.'),
                      'parameters':{'type':'object','properties':properties,'required':required,'additionalProperties':False}}})
    return tools

def selection_messages(messages):
    """Adapt audited local selections to correctly paired native API messages."""
    if not messages:raise ValueError('Investigation messages are required')
    output=[];pending=None
    for index,message in enumerate(messages):
        if message['role']=='assistant':
            selected=json.loads(message['content'])
            call=selected['tool_call'];pending='local_'+str(index)
            output.append({'role':'assistant','content':None,'tool_calls':[{'id':pending,'type':'function',
                'function':{'name':call['tool'],'arguments':json.dumps(call['params'])}}]})
        elif pending and message['role']=='user':
            output.append({'role':'tool','tool_call_id':pending,'content':message['content']});pending=None
        else:output.append(dict(message))
    if pending:raise ValueError('A local tool selection has no recorded result')
    output[0]['content']+=' Use the declared local functions, one at a time. When enough evidence is retrieved, return exactly {"done":true} as JSON text. Do not write the report yet.'
    return output

def read_selection(message):
    calls=message.get('tool_calls') or []
    if calls:
        if len(calls)!=1 or calls[0].get('type')!='function':raise ValueError('Exactly one local function call is permitted')
        function=calls[0]['function'];name=function['name']
        if name not in TOOL_WHITELIST:raise ValueError('Unknown model-selected tool')
        params=json.loads(function['arguments'])
        if not isinstance(params,dict):raise ValueError('Tool arguments must be an object')
        return json.dumps({'tool_call':{'tool':name,'params':params}})
    value=json.loads(message.get('content') or '')
    if value!={'done':True}:raise ValueError('Expected a local function call or a done decision')
    return json.dumps(value)
