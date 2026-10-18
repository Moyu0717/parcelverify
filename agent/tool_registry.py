"""Canonical read-only tool names, schemas and argument validation.

Identity, shipment scope and authority are never model arguments.
"""
from copy import deepcopy
from datetime import datetime

TOOL_REGISTRY={
 'get_case_context':('Read permitted linked findings, handoffs and recorded business context.',{}),
 'get_vendor_context':('Read recorded partner contract context.',{'at_time':{'type':'string','description':'Optional timezone-aware ISO 8601 source timestamp.'}}),
 'get_shipment_timeline':('Read the case shipment timeline and photo identifiers.',{}),
 'compare_handoff':('Compare recorded shipment measurements; absent values remain unknown.',{}),
 'find_photo_reuse':('Compare one retrieved photo identifier against permitted records.',{'photo_id':{'type':'string','description':'An actual photo identifier retrieved from this case.'}}),
 'check_access_scope':('Read independent permission findings and recorded requests.',{}),
 'get_context_events':('Read recorded explanations including approved packaging and batch work.',{}),
 'get_partner_metrics':('Read contextual partner evidence metrics.',{}),
}

def validate_tool_arguments(name,params):
    if not isinstance(name,str) or name not in TOOL_REGISTRY:raise ValueError('Unknown model-selected tool')
    if not isinstance(params,dict):raise ValueError('Tool arguments must be an object')
    allowed=TOOL_REGISTRY[name][1]
    if set(params)-set(allowed):raise ValueError('Unexpected tool parameters; scope is server controlled')
    if name=='find_photo_reuse' and not params.get('photo_id'):raise ValueError('photo_id is required')
    for key,value in params.items():
        if not isinstance(value,str) or not value.strip() or len(value)>160:raise ValueError('Invalid tool argument: '+key)
        if key=='at_time':
            stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
            if stamp.tzinfo is None or stamp.utcoffset() is None:raise ValueError('at_time requires a timezone offset')
    return params

def tool_definitions():
    return [{'type':'function','function':{'name':name,'description':description,'parameters':{
        'type':'object','properties':deepcopy(properties),'required':['photo_id'] if name=='find_photo_reuse' else [],'additionalProperties':False}}}
        for name,(description,properties) in TOOL_REGISTRY.items()]
