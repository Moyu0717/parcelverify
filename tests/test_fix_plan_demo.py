"""Both gate controls and contextual partner reporting, without a live provider."""
import json
import pytest
from db import init_db,get_connection
from seed import seed_demo
from services.access import query_shipment
from services.access_patterns import evaluate_access_patterns
from services.workflow import initialize_reviews,submit_handoff
from services.cases import list_cases,review_finding
from services.handoff import compare_handoff
from services.risk import summarize_permitted_shipments

ADMIN=dict(actor_id='ADMIN-001',role='admin',session_id='fix-plan')
PARTNER=dict(actor_id='ACTOR-QR-01',partner_id='P-QUICKRUN',role='partner_user',session_id='fix-plan')

@pytest.fixture
def demo(tmp_path):
    path=str(tmp_path/'demo.db');init_db(path);seed_demo(path);initialize_reviews(path,ADMIN)
    return path

def test_gate1_allowed_minimized_denied_logged(demo):
    allowed=query_shipment(demo,PARTNER,'PV-DEMO-001')
    assert allowed['authorized']
    assert not {'destination_lat','destination_lon','reference_event_id'} & allowed['fields'].keys()
    denied=query_shipment(demo,dict(PARTNER,actor_id='UNASSIGNED'),'PV-DEMO-001')
    assert not denied['authorized'] and denied['fields'] is None
    with get_connection(demo) as conn:
        row=conn.execute('SELECT outcome,returned_fields FROM access_logs WHERE log_id=?',(denied['log_id'],)).fetchone()
    assert row[0]=='denied' and json.loads(row[1])==[]

def test_controls_missing_evidence_and_summary_denominator(demo):
    cases=list_cases(demo,ADMIN)
    explained=next(c for c in cases if c['shipment_id']=='PV-SHIP-011')
    assert 'weight_diff' not in {f['category'] for f in explained['linked_findings']}
    assert evaluate_access_patterns(demo,'PV-SHIP-011')[0]['category']=='authorized_export'
    assert evaluate_access_patterns(demo,'PV-DEMO-001')[0]['category']=='access_anomaly'
    assert compare_handoff(demo,'PV-SHIP-021')['unknowns']
    population=['PV-DEMO-001','PV-SHIP-021']
    summary=summarize_permitted_shipments(demo,population)
    assert summary['total_shipments']==2 and summary['small_sample']
    assert summary['missing_evidence_shipments']>=1
    assert summary['complete_shipments']+summary['missing_evidence_shipments']==2
    assert summary['supported_findings']==0
    main=next(c for c in cases if c['shipment_id']=='PV-DEMO-001')
    f=next(f for f in main['linked_findings'] if f['category']=='weight_diff')
    review_finding(demo,f['finding_id'],ADMIN,'supported','Original readings support a discrepancy, not misconduct',f['evidence_ids'])
    revised=summarize_permitted_shipments(demo,population)
    assert revised['supported_findings']==1
    assert revised['open_findings']==summary['open_findings']-1
    assert revised['affected_shipments']==summary['affected_shipments']

@pytest.mark.parametrize('payload,stamp',[({'weight_g':float('nan')},'2026-10-01T00:00:00Z'),({'weight_g':-1},'2026-10-01T00:00:00Z'),({'count':1.5},'2026-10-01T00:00:00Z'),({},'2026-10-01T00:00:00')])
def test_bad_evidence_rejected_before_persistence(demo,payload,stamp):
    with get_connection(demo) as conn:before=conn.execute('SELECT COUNT(*) FROM events').fetchone()[0]
    with pytest.raises(ValueError):submit_handoff(demo,ADMIN,'PV-DEMO-001','handoff_submitted',payload,stamp)
    with get_connection(demo) as conn:assert conn.execute('SELECT COUNT(*) FROM events').fetchone()[0]==before
