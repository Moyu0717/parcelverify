import json
from ui.evidence_map import build_nodes

def event(eid,kind,weight=None,time='2026-10-01T10:00:00+08:00',**fields):
    if weight is not None:fields['weight_g']=weight
    return dict(event_id=eid,event_type=kind,occurred_at=time,received_at=time,source='test',payload_json=json.dumps(fields))

def test_stage_values_are_not_inherited_from_later_measurements():
    nodes=build_nodes([event('later','handoff_submitted',800,time='2026-10-01T11:00:00+08:00'),event('first','dispatch_confirmed',1000),event('pod','pod_submitted',time='2026-10-01T12:00:00+08:00')],{'weight_g':1000})
    assert [n['id'] for n in nodes]==['first','later','pod']
    assert nodes[0]['status']=='Missing fields'
    assert nodes[1]['status']=='Difference'
    assert 'Weight: not recorded' in nodes[2]['facts']
    assert not any('0.800' in f for f in nodes[2]['facts'])

def test_missing_handoff_is_explicit_even_with_new_weighing():
    nodes=build_nodes([event('reweigh','weight_measured',1000)],{'weight_g':1000})
    assert nodes[-1]['id']=='missing-handoff'
    assert nodes[-1]['missing'] is True
    assert nodes[0]['status']=='Recorded'

def test_tolerance_and_zero_values():
    nodes=build_nodes([event('within','handoff_submitted',950,count=0,seal_id='S')],{'weight_g':1000,'count':0,'seal_id':'S'})
    assert nodes[0]['status']=='Recorded'
    assert 'Packages: 0' in nodes[0]['facts']

def test_account_events_do_not_become_physical_handoff_nodes():
    nodes=build_nodes([event('account','approved_batch_job'),event('handoff','handoff_submitted',1000)],{'weight_g':1000})
    assert [n['id'] for n in nodes]==['handoff']
