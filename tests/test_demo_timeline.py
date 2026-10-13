"""Completed synthetic activity must predate the documented demo date."""
import random
from datetime import datetime, timezone

from seed import _generate_access_logs, _generate_events, _generate_shipments


def test_completed_demo_events_and_access_are_not_future_dated():
    rng = random.Random(42)
    shipments = _generate_shipments(rng)
    events = _generate_events(shipments, rng)
    logs = _generate_access_logs(shipments, rng)
    demo_date = datetime(2026, 10, 13, tzinfo=timezone.utc)
    for record in events + logs:
        assert datetime.fromisoformat(record['occurred_at']) < demo_date
    for shipment in shipments:
        timeline = {e['event_type']: datetime.fromisoformat(e['occurred_at'])
                    for e in events if e['shipment_id'] == shipment['shipment_id']}
        assert timeline['dispatch_confirmed'] < timeline['handoff_submitted'] < timeline['pod_submitted']
