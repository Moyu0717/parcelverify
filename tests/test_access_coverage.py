"""S05: access-pattern detection is not limited to two hard-coded shipments and runs even when cases exist."""
import json
from datetime import datetime, timedelta, timezone
from db import get_connection
from services.workflow import initialize_reviews
from tests.test_workflow import database, ADMIN


def _add_burst(conn, shipment_id, partner, actor, n=12):
    start = datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc)
    conn.execute("INSERT INTO events(event_id,shipment_id,partner_id,actor_id,event_type,occurred_at,received_at,source,payload_json) VALUES (?,?,?,?,'workload_context',?,?,'test',?)",
                 ('EV-WL-'+shipment_id, shipment_id, partner, actor, start.isoformat(), start.isoformat(), json.dumps({'actor_id': actor, 'batch_job_id': 'JOB-T', 'normal_downloads_per_15_minutes': 3})))
    cols = [r[1] for r in conn.execute('PRAGMA table_info(access_logs)')]
    for i in range(n):
        row = {'log_id': f'LOG-T-{shipment_id}-{i}', 'actor_id': actor, 'shipment_id': shipment_id, 'action': 'download', 'outcome': 'allowed',
               'occurred_at': (start + timedelta(seconds=30 * i)).isoformat(), 'batch_job_id': 'JOB-T', 'returned_fields': '[]'}
        keys = [k for k in row if k in cols]
        extra = {c: '' for c in cols if c not in row and c not in ('log_id',)}
        conn.execute('INSERT INTO access_logs(' + ','.join(keys) + ') VALUES (' + ','.join('?' * len(keys)) + ')', [row[k] for k in keys])


def test_detection_covers_any_shipment_with_a_baseline_and_runs_after_cases_exist(database):
    initialize_reviews(database, ADMIN)  # first run creates the seed cases
    with get_connection(database) as conn:
        other = conn.execute("SELECT shipment_id, partner_id FROM shipments WHERE shipment_id NOT IN ('PV-DEMO-001','PV-SHIP-011') LIMIT 1").fetchone()
        actor = conn.execute('SELECT actor_id FROM assignments WHERE shipment_id=?', (other[0],)).fetchone()
        _add_burst(conn, other[0], other[1], actor[0] if actor else 'ACTOR-QR-01')
    initialize_reviews(database, ADMIN)  # cases already exist: must not return early
    with get_connection(database) as conn:
        assert conn.execute("SELECT COUNT(*) FROM case_records WHERE triggering_event_id=?", ('access:workload:' + other[0],)).fetchone()[0] == 1
    initialize_reviews(database, ADMIN)  # idempotent
    with get_connection(database) as conn:
        assert conn.execute("SELECT COUNT(*) FROM case_records WHERE triggering_event_id=?", ('access:workload:' + other[0],)).fetchone()[0] == 1
