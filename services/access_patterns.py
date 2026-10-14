"""Explicit demo workload rule; approved export exceptions apply only to that rule."""
import json
from services.access import _parse_time
from db import get_connection

def evaluate_access_patterns(db_path,shipment_id):
    with get_connection(db_path) as conn:
        rows=conn.execute("SELECT log_id,actor_id,occurred_at,batch_job_id,returned_fields,outcome FROM access_logs WHERE shipment_id=? AND action='download' ORDER BY occurred_at",(shipment_id,)).fetchall()
        contexts=[(r[0],json.loads(r[1])) for r in conn.execute("SELECT event_id,payload_json FROM events WHERE shipment_id=? AND event_type='workload_context'",(shipment_id,))]
        approvals=[(r[0],json.loads(r[1])) for r in conn.execute("SELECT event_id,payload_json FROM events WHERE shipment_id=? AND event_type='authorized_export'",(shipment_id,))]
        findings=[]
        for ctx_id,ctx in contexts:
            window=[r for r in rows if r[1]==ctx['actor_id'] and r[3]==ctx['batch_job_id']]
            if len(window)<=ctx['normal_downloads_per_15_minutes']:continue
            if (_parse_time(window[-1][2])-_parse_time(window[0][2])).total_seconds()>900:continue
            approval=next((eid for eid,p in approvals if p.get('approved_by') and p.get('actor_id')==ctx['actor_id'] and p.get('batch_job_id')==ctx['batch_job_id'] and shipment_id in p.get('shipment_ids',[]) and len(window)<=p.get('max_downloads',0) and all(r[5]=='authorized' and _parse_time(p['valid_from'])<=_parse_time(r[2])<_parse_time(p['valid_until']) and set(json.loads(r[4]))<=set(p.get('allowed_fields',[])) for r in window)),None)
            findings.append(dict(category='authorized_export' if approval else 'access_anomaly',severity='info' if approval else 'blocking',description='Recorded export matches its approved scope and active period.' if approval else f'{len(window)} downloads in 15 minutes exceed the recorded workload of {ctx["normal_downloads_per_15_minutes"]}. Intent is unknown.',evidence_ids=[ctx_id,*[r[0] for r in window],*([approval] if approval else [])]))
        return findings
