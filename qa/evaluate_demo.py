"""Synthetic finding/case denominators, never a fabricated human-time comparison."""
import json
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from db import init_db,get_connection
from seed import seed_demo
from services.workflow import initialize_reviews
from services.review import ensure_access_cases
from services.cases import ensure_case_links,list_cases
from services.access_patterns import evaluate_access_patterns
from services.handoff import compare_handoff

def main():
    actor={'actor_id':'ADMIN-001','role':'admin','session_id':'evaluation'}
    with tempfile.TemporaryDirectory(prefix='pv-eval-') as folder:
        db=str(Path(folder)/'eval.db');init_db(db);seed_demo(db);initialize_reviews(db,actor);ensure_access_cases(db,actor);ensure_case_links(db,actor)
        cases=list_cases(db,actor)
        gt={'PV-DEMO-001':{'weight_diff','photo_reuse','access_anomaly'},'PV-SHIP-011':{'authorized_export'},'PV-SHIP-021':{'missing_evidence'}}
        findings={c['shipment_id']:{f['category'] for f in c['linked_findings']} for c in cases}
        with get_connection(db) as conn:total=conn.execute('SELECT COUNT(*) FROM shipments').fetchone()[0]
        with get_connection(db) as conn:shipment_ids=[r[0] for r in conn.execute('SELECT shipment_id FROM shipments')]
        complete=sum(not compare_handoff(db,sid)['unknowns'] for sid in shipment_ids)
        expected_flags={'PV-DEMO-001','PV-SHIP-010','PV-SHIP-021'}
        detected_flags={sid for c in cases if c['shipment_id']!='PV-SHIP-011' for sid in c['shipment_ids']}
        result={'dataset':'synthetic September 2026; rules only','total_shipments':total,'featured_cases':len(gt),'observed_cases':len(cases),'clean_background_shipments':total-len(expected_flags|set(gt)),'findings':{k:sorted(v) for k,v in findings.items()},'missed_required_categories':sum(len(categories-findings.get(sid,set())) for sid,categories in gt.items()),'false_alert_shipments':sorted(detected_flags-expected_flags),'missed_flagged_shipments':sorted(expected_flags-detected_flags),'supported_export':evaluate_access_patterns(db,'PV-SHIP-011'),'evidence_completeness':{'complete_required_fields':complete,'shipment_denominator':total,'note':'Field presence is not verified quality; illustrative images do not prove contents'},'human_review_time':'Pending actual timed human sessions','ai_assisted_evaluation':'Blocked until real provider credentials are configured'}
    dest=Path('qa/artifacts/demo-evaluation.json');dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))

if __name__=='__main__':main()
