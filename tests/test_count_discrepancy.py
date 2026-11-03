"""S06 (conservative): a package-count difference always needs review; text mentioning 'scan' is not proof."""
import json
from datetime import datetime, timezone
from db import get_connection
from services.handoff import evaluate_handoff
from services.risk import calculate_priority
from services.workflow import submit_handoff
from tests.test_workflow import database, ADMIN


def _submit(database, count):
    occurred = datetime.now(timezone.utc).isoformat()
    return submit_handoff(database, ADMIN, 'PV-DEMO-001', 'handoff_submitted', {'count': count, 'weight_g': 2000, 'seal_id': 'SEAL-07'}, occurred)


def test_count_difference_is_blocking_and_scan_status_unknown(database):
    event_id = _submit(database, 3)['event']['event_id']
    result = evaluate_handoff(database, 'PV-DEMO-001', event_id, ADMIN)
    finding = next(f for f in result['findings'] if f['category'] == 'count_discrepancy')
    assert finding['severity'] == 'blocking' and 'unknown' in finding['description']
    assert 'per_item_scan' in result['missing_evidence']
    score = calculate_priority(database, result['findings'])
    assert score['review_queue'] is True


def test_free_text_mentioning_scan_is_not_proof(database):
    with get_connection(database) as conn:
        conn.execute("INSERT INTO events(event_id,shipment_id,partner_id,actor_id,event_type,occurred_at,received_at,source,payload_json) VALUES ('EV-SCAN-TEXT','PV-DEMO-001','P-QUICKRUN','ACTOR-QR-01','approved_batch_job',?,?,'test',?)",
                     (datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat(), json.dumps({'note': 'no scan available'})))
    event_id = _submit(database, 3)['event']['event_id']
    result = evaluate_handoff(database, 'PV-DEMO-001', event_id, ADMIN)
    finding = next(f for f in result['findings'] if f['category'] == 'count_discrepancy')
    assert finding['severity'] == 'blocking' and 'Scan confirmed' not in finding['description']
    assert 'per_item_scan' in result['missing_evidence']


def test_count_score_is_counted_once_and_capped():
    findings = [{'category': 'count_discrepancy', 'severity': 'blocking', 'description': 'a'}] * 2
    result = calculate_priority('unused', findings)
    assert result['total_score'] == 20 and result['items'][1]['deduplicated'] is True
