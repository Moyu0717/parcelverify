"""
ParcelVerify - Synthetic Data Seeder
Owner: Role A (Data Agent)

Generates reproducible synthetic data for the ParcelVerify prototype:
- 3 partners (P-QUICKRUN, P-SAFELOG, P-METROLINE)
- 60 shipments with 3-5 events each
- Access logs (authorized and unauthorized)
- Contract history entries per partner
- 12 fixture photos linked to events (+1 reused for photo-reuse scenario)
- PV-DEMO-001: weight discrepancy scenario (2000g -> 1850g, SEAL-07)
- PV-SHIP-011: repackaging_approved event (explained weight diff)
- Photo reuse: photo_001.jpg on PV-DEMO-001 and PV-SHIP-010
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from io import BytesIO

from db import get_connection, init_db

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

# Partner definitions
PARTNERS = [
    {
        "partner_id": "P-QUICKRUN",
        "name": "QuickRun Logistics",
        "status": "active",
        "contract_end": "2026-12-31T23:59:59Z",
        "service_area": "Klang Valley",
        "approved_scope": "standard_delivery,cod_collection",
        "vendor_evidence_id": "EV-QR-001",
    },
    {
        "partner_id": "P-SAFELOG",
        "name": "SafeLog Express",
        "status": "active",
        "contract_end": "2027-03-31T23:59:59Z",
        "service_area": "Penang",
        "approved_scope": "standard_delivery,temperature_controlled",
        "vendor_evidence_id": "EV-SL-001",
    },
    {
        "partner_id": "P-METROLINE",
        "name": "MetroLine Courier",
        "status": "active",
        "contract_end": "2026-11-30T23:59:59Z",
        "service_area": "Kuala Lumpur CBD",
        "approved_scope": "standard_delivery,high_value",
        "vendor_evidence_id": "EV-ML-001",
    },
]

# Actor IDs per partner
ACTORS = {
    "P-QUICKRUN": ["ACTOR-QR-01", "ACTOR-QR-02"],
    "P-SAFELOG": ["ACTOR-SL-01", "ACTOR-SL-02"],
    "P-METROLINE": ["ACTOR-ML-01", "ACTOR-ML-02"],
}

# Base date for timeline
BASE_DATE = datetime(2026, 9, 1, 8, 0, 0, tzinfo=timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _compute_phash(file_bytes: bytes) -> str | None:
    try:
        from PIL import Image
        import imagehash

        img = Image.open(BytesIO(file_bytes))
        return str(imagehash.phash(img))
    except Exception:
        return None


def _load_fixture(filename: str) -> bytes:
    path = os.path.join(FIXTURES_DIR, filename)
    with open(path, "rb") as f:
        return f.read()


def _get_counts(conn: sqlite3.Connection) -> dict:
    """Return current table counts."""
    tables = [
        "partners", "shipments", "events", "photos",
        "access_logs", "contract_history",
    ]
    counts = {}
    for t in tables:
        counts[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    return counts


def _generate_contract_snapshots() -> list[dict]:
    """Generate contract history entries for each partner."""
    history = []
    for p in PARTNERS:
        history.append(
            {
                "history_id": _uuid(),
                "partner_id": p["partner_id"],
                "contract_snapshot_json": json.dumps(
                    {
                        "name": p["name"],
                        "status": p["status"],
                        "contract_end": p["contract_end"],
                        "service_area": p["service_area"],
                        "approved_scope": p["approved_scope"],
                        "vendor_evidence_id": p["vendor_evidence_id"],
                    }
                ),
                "effective_from": "2026-01-01T00:00:00Z",
                "effective_until": None,
                "changed_by": "system",
                "changed_at": "2026-01-01T00:00:00Z",
            }
        )

    # P-QUICKRUN had a scope expansion on 2026-06-01
    qr = PARTNERS[0]
    history[0]["effective_until"] = "2026-06-01T00:00:00Z"
    history.append(
        {
            "history_id": _uuid(),
            "partner_id": qr["partner_id"],
            "contract_snapshot_json": json.dumps(
                {
                    "name": qr["name"],
                    "status": qr["status"],
                    "contract_end": qr["contract_end"],
                    "service_area": qr["service_area"],
                    "approved_scope": "standard_delivery,cod_collection,express_delivery",
                    "vendor_evidence_id": qr["vendor_evidence_id"],
                }
            ),
            "effective_from": "2026-06-01T00:00:00Z",
            "effective_until": None,
            "changed_by": "admin-001",
            "changed_at": "2026-06-01T00:00:00Z",
        }
    )

    return history


def _generate_shipments(rng: random.Random) -> list[dict]:
    """Generate 60 shipments distributed across 3 partners."""
    shipments = []

    # PV-DEMO-001: Special demo case (QuickRun, 2000g, SEAL-07)
    shipments.append(
        {
            "shipment_id": "PV-DEMO-001",
            "partner_id": "P-QUICKRUN",
            "expected_count": 1,
            "expected_weight_g": 2000.0,
            "expected_seal": "SEAL-07",
            "destination_lat": 3.1390,
            "destination_lon": 101.6869,
            "status": "delivered",
            "reference_event_id": None,
        }
    )

    # 19 QuickRun + 20 SafeLog + 20 MetroLine = 59 remaining
    partner_counts = {"P-QUICKRUN": 19, "P-SAFELOG": 20, "P-METROLINE": 20}
    ship_num = 2
    for pid in ["P-QUICKRUN", "P-SAFELOG", "P-METROLINE"]:
        for _ in range(partner_counts[pid]):
            ship_id = f"PV-SHIP-{ship_num:03d}"

            # PV-SHIP-011: repackaging scenario (specific weight/seal)
            if ship_id == "PV-SHIP-011":
                weight = 2000.0
                seal = "SEAL-019"
            else:
                weight = round(rng.uniform(500, 3000), 1)
                seal = f"SEAL-{rng.randint(100, 999)}"

            shipments.append(
                {
                    "shipment_id": ship_id,
                    "partner_id": pid,
                    "expected_count": rng.randint(1, 5),
                    "expected_weight_g": weight,
                    "expected_seal": seal,
                    "destination_lat": round(rng.uniform(2.5, 4.5), 4),
                    "destination_lon": round(rng.uniform(100.5, 103.5), 4),
                    "status": rng.choice(
                        ["delivered", "in_transit", "delivered", "delivered"]
                    ),
                    "reference_event_id": None,
                }
            )
            ship_num += 1

    return shipments


def _generate_assignments(shipments: list[dict]) -> list[dict]:
    """Generate one assignment per shipment."""
    assignments = []
    for ship in shipments:
        pid = ship["partner_id"]
        actor_id = ACTORS[pid][0]
        assignments.append(
            {
                "assignment_id": _uuid(),
                "shipment_id": ship["shipment_id"],
                "partner_id": pid,
                "actor_id": actor_id,
                "valid_from": _iso(BASE_DATE),
                "valid_until": None,
                "allowed_actions": json.dumps(
                    ["view", "submit_event", "upload_photo"]
                ),
            }
        )
    return assignments


def _generate_events(
    shipments: list[dict], rng: random.Random
) -> list[dict]:
    """Generate 3-5 events per shipment."""
    events = []
    received_at = _iso(datetime.now(timezone.utc))

    for i, ship in enumerate(shipments):
        pid = ship["partner_id"]
        actor_id = ACTORS[pid][0]
        ship_start = BASE_DATE + timedelta(
            days=i, hours=rng.randint(0, 12)
        )

        # 1. dispatch_confirmed
        events.append(
            {
                "event_id": _uuid(),
                "shipment_id": ship["shipment_id"],
                "partner_id": pid,
                "actor_id": actor_id,
                "event_type": "dispatch_confirmed",
                "occurred_at": _iso(ship_start),
                "received_at": received_at,
                "source": "dispatch_system",
                "payload": {
                    "count": ship["expected_count"],
                    "weight_g": ship["expected_weight_g"],
                    "seal_id": ship["expected_seal"],
                },
            }
        )

        # 2. handoff_submitted (1 day later)
        handoff_time = ship_start + timedelta(
            days=1, hours=rng.randint(0, 8)
        )

        # Determine handoff weight
        if ship["shipment_id"] == "PV-DEMO-001":
            handoff_weight = 1850.0  # Weight discrepancy (no explanation)
        elif ship["shipment_id"] == "PV-SHIP-011":
            handoff_weight = ship["expected_weight_g"] - 150.0  # Explained
        else:
            handoff_weight = round(
                ship["expected_weight_g"] + rng.uniform(-50, 50), 1
            )

        events.append(
            {
                "event_id": _uuid(),
                "shipment_id": ship["shipment_id"],
                "partner_id": pid,
                "actor_id": actor_id,
                "event_type": "handoff_submitted",
                "occurred_at": _iso(handoff_time),
                "received_at": received_at,
                "source": "handoff_app",
                "payload": {
                    "count": ship["expected_count"],
                    "weight_g": handoff_weight,
                    "seal_id": ship["expected_seal"],
                    "handoff_location": "Hub " + rng.choice(["A", "B", "C", "D"]),
                },
            }
        )

        # 3. pod_submitted (1-2 days after handoff)
        pod_time = handoff_time + timedelta(
            days=1, hours=rng.randint(0, 8)
        )
        events.append(
            {
                "event_id": _uuid(),
                "shipment_id": ship["shipment_id"],
                "partner_id": pid,
                "actor_id": actor_id,
                "event_type": "pod_submitted",
                "occurred_at": _iso(pod_time),
                "received_at": received_at,
                "source": "pod_system",
                "payload": {
                    "recipient_name": rng.choice(
                        ["John Tan", "Sarah Lee", "Mike Chen",
                         "Emma Wong", "David Lim"]
                    ),
                    "signature": True,
                    "delivery_location": "Residential",
                },
            }
        )

        # 4. Optional: recipient_authorization (~50%)
        if rng.random() < 0.5:
            auth_time = handoff_time - timedelta(
                hours=rng.randint(1, 6)
            )
            events.append(
                {
                    "event_id": _uuid(),
                    "shipment_id": ship["shipment_id"],
                    "partner_id": pid,
                    "actor_id": actor_id,
                    "event_type": "recipient_authorization",
                    "occurred_at": _iso(auth_time),
                    "received_at": received_at,
                    "source": "auth_portal",
                    "payload": {
                        "recipient_id": f"REC-{rng.randint(1000, 9999)}",
                        "authorization_method": "id_card",
                    },
                }
            )

        # 5. Optional: message_reported (~20%)
        if rng.random() < 0.2:
            msg_time = pod_time + timedelta(
                hours=rng.randint(1, 12)
            )
            events.append(
                {
                    "event_id": _uuid(),
                    "shipment_id": ship["shipment_id"],
                    "partner_id": pid,
                    "actor_id": actor_id,
                    "event_type": "message_reported",
                    "occurred_at": _iso(msg_time),
                    "received_at": received_at,
                    "source": "customer_support",
                    "payload": {
                        "message": rng.choice(
                            [
                                "Package arrived late",
                                "Seal appeared tampered",
                                "Package in good condition",
                                "Delivery driver was professional",
                            ]
                        ),
                        "channel": "sms",
                    },
                }
            )

    # Repackaging approved event for PV-SHIP-011 (D-005)
    for e in events:
        if (
            e["shipment_id"] == "PV-SHIP-011"
            and e["event_type"] == "handoff_submitted"
        ):
            repack_time = datetime.fromisoformat(
                e["occurred_at"]
            ) + timedelta(hours=2)
            measurements = []
            for offset, measured in enumerate((2000.0, 1850.0)):
                measurement_id = _uuid()
                measurements.append(measurement_id)
                events.append({
                    "event_id": measurement_id, "shipment_id": e["shipment_id"],
                    "partner_id": e["partner_id"], "actor_id": "APPROVER-001",
                    "event_type": "weight_measured", "occurred_at": _iso(repack_time + timedelta(minutes=offset)),
                    "received_at": received_at, "source": "calibrated_scale",
                    "payload": {"weight_g": measured, "handoff_event_id": e["event_id"]},
                })
            events.append(
                {
                    "event_id": _uuid(),
                    "shipment_id": "PV-SHIP-011",
                    "partner_id": "P-QUICKRUN",
                    "actor_id": "ACTOR-QR-02",
                    "event_type": "repackaging_approved",
                    "occurred_at": _iso(repack_time),
                    "received_at": received_at,
                    "source": "ops_portal",
                    "payload": {
                        "approver_id": "APPROVER-001",
                        "reason": "Repackaging for safety - damaged outer box",
                        "weight_diff_g": 150.0,
                        "new_packaging_weight_g": 150.0,
                        "handoff_event_id": e["event_id"],
                        "supporting_measurement_ids": measurements,
                    },
                }
            )
            break

    return events


def _generate_photos(events: list[dict]) -> list[dict]:
    """Generate photo records linked to events using fixture images."""
    photos = []

    # Map fixture files to events
    photo_map = [
        {"file": "photo_001.jpg", "shipment": "PV-DEMO-001", "event_type": "pod_submitted"},
        {"file": "photo_002.jpg", "shipment": "PV-DEMO-001", "event_type": "handoff_submitted"},
        {"file": "photo_003.jpg", "shipment": "PV-DEMO-001", "event_type": "handoff_submitted"},
        {"file": "photo_004.jpg", "shipment": "PV-DEMO-001", "event_type": "pod_submitted"},
        {"file": "photo_005.jpg", "shipment": "PV-SHIP-002", "event_type": "handoff_submitted"},
        {"file": "photo_006.jpg", "shipment": "PV-SHIP-003", "event_type": "handoff_submitted"},
        {"file": "photo_007.jpg", "shipment": "PV-SHIP-005", "event_type": "handoff_submitted"},
        {"file": "photo_008.jpg", "shipment": "PV-SHIP-008", "event_type": "pod_submitted"},
        {"file": "photo_009.jpg", "shipment": "PV-SHIP-012", "event_type": "handoff_submitted"},
        {"file": "photo_010.jpg", "shipment": "PV-SHIP-015", "event_type": "handoff_submitted"},
        {"file": "photo_011.jpg", "shipment": "PV-SHIP-020", "event_type": "handoff_submitted"},
        {"file": "photo_012.jpg", "shipment": "PV-SHIP-025", "event_type": "handoff_submitted"},
        # Photo reuse: same photo_001.jpg on a different shipment (PV-SHIP-010)
        {"file": "photo_001.jpg", "shipment": "PV-SHIP-010", "event_type": "handoff_submitted"},
    ]

    uploaded_at = _iso(datetime.now(timezone.utc))

    for pm in photo_map:
        matching = [
            e for e in events
            if e["shipment_id"] == pm["shipment"]
            and e["event_type"] == pm["event_type"]
        ]
        if not matching:
            continue

        event = matching[0]
        file_bytes = _load_fixture(pm["file"])
        sha = _sha256(file_bytes)
        phash = _compute_phash(file_bytes)
        fixture_path = os.path.join(FIXTURES_DIR, pm["file"])

        photos.append(
            {
                "photo_id": _uuid(),
                "event_id": event["event_id"],
                "local_path": fixture_path,
                "sha256": sha,
                "phash": phash,
                "uploaded_at": uploaded_at,
                "claimed_capture_at": event["occurred_at"],
                "capture_method": "upload",
                "manual_observation": "",
            }
        )

    return photos


def _generate_access_logs(
    shipments: list[dict], rng: random.Random
) -> list[dict]:
    """Generate access logs with both authorized and unauthorized queries."""
    logs = []

    # Authorized access: first 20 shipments
    for ship in shipments[:20]:
        pid = ship["partner_id"]
        actor_id = ACTORS[pid][0]
        log_time = BASE_DATE + timedelta(
            days=rng.randint(5, 35), hours=rng.randint(0, 23)
        )
        logs.append(
            {
                "log_id": _uuid(),
                "partner_id": pid,
                "actor_id": actor_id,
                "credential_id": f"CREDS-{actor_id}",
                "shipment_id": ship["shipment_id"],
                "occurred_at": _iso(log_time),
                "action": "query_shipment",
                "outcome": "authorized",
                "returned_fields": json.dumps(
                    ["shipment_id", "partner_id", "status", "expected_weight_g"]
                ),
                "batch_job_id": None,
            }
        )

    # Unauthorized: SafeLog actor queries QuickRun shipment
    logs.append(
        {
            "log_id": _uuid(),
            "partner_id": "P-SAFELOG",
            "actor_id": "ACTOR-SL-02",
            "credential_id": "CREDS-ACTOR-SL-02",
            "shipment_id": "PV-DEMO-001",
            "occurred_at": _iso(BASE_DATE + timedelta(days=20, hours=14)),
            "action": "query_shipment",
            "outcome": "denied",
            "returned_fields": json.dumps([]),
            "batch_job_id": None,
        }
    )

    # Unauthorized: MetroLine actor queries SafeLog shipment
    logs.append(
        {
            "log_id": _uuid(),
            "partner_id": "P-METROLINE",
            "actor_id": "ACTOR-ML-02",
            "credential_id": "CREDS-ACTOR-ML-02",
            "shipment_id": "PV-SHIP-021",
            "occurred_at": _iso(BASE_DATE + timedelta(days=25, hours=10)),
            "action": "query_shipment",
            "outcome": "denied",
            "returned_fields": json.dumps([]),
            "batch_job_id": None,
        }
    )

    # Batch job access
    logs.append(
        {
            "log_id": _uuid(),
            "partner_id": "P-QUICKRUN",
            "actor_id": "BATCH-QR-001",
            "credential_id": "CREDS-BATCH-QR-001",
            "shipment_id": "PV-DEMO-001",
            "occurred_at": _iso(BASE_DATE + timedelta(days=30, hours=2)),
            "action": "batch_query",
            "outcome": "authorized",
            "returned_fields": json.dumps(
                ["shipment_id", "status", "expected_weight_g"]
            ),
            "batch_job_id": "BATCH-2026-10-001",
        }
    )

    # Authorized access: shipments 20-40
    for ship in shipments[20:40]:
        pid = ship["partner_id"]
        actor_id = ACTORS[pid][0]
        log_time = BASE_DATE + timedelta(
            days=rng.randint(5, 35), hours=rng.randint(0, 23)
        )
        logs.append(
            {
                "log_id": _uuid(),
                "partner_id": pid,
                "actor_id": actor_id,
                "credential_id": f"CREDS-{actor_id}",
                "shipment_id": ship["shipment_id"],
                "occurred_at": _iso(log_time),
                "action": "query_shipment",
                "outcome": "authorized",
                "returned_fields": json.dumps(
                    ["shipment_id", "partner_id", "status"]
                ),
                "batch_job_id": None,
            }
        )

    return logs


def seed_demo(
    db_path: str = "data/parcelverify.db", seed: int = 42, reset: bool = False
) -> dict:
    """Generate reproducible synthetic data.

    Args:
        db_path: Path to SQLite database file.
        seed: Random seed for reproducibility.
        reset: If True, drops and recreates all tables before seeding.
               If False, inserts only if no data exists (skips existing).

    Returns:
        dict with counts: partners, shipments, events, photos,
              access_logs, contract_history
    """
    rng = random.Random(seed)

    if reset:
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            DROP TABLE IF EXISTS tool_executions;
            DROP TABLE IF EXISTS report_versions;
            DROP TABLE IF EXISTS investigation_runs;
            DROP TABLE IF EXISTS audit_log;
            DROP TABLE IF EXISTS action_requests;
            DROP TABLE IF EXISTS evidence_tasks;
            DROP TABLE IF EXISTS case_records;
            DROP TABLE IF EXISTS photos;
            DROP TABLE IF EXISTS access_logs;
            DROP TABLE IF EXISTS events;
            DROP TABLE IF EXISTS assignments;
            DROP TABLE IF EXISTS contract_history;
            DROP TABLE IF EXISTS shipments;
            DROP TABLE IF EXISTS partners;
            """
        )
        conn.close()

    # Ensure tables exist
    init_db(db_path)

    conn = get_connection(db_path)
    try:
        # Skip if data already exists (reset=False)
        if not reset:
            count = conn.execute(
                "SELECT COUNT(*) FROM partners"
            ).fetchone()[0]
            if count > 0:
                return _get_counts(conn)

        # Generate all data
        contract_history = _generate_contract_snapshots()
        shipments = _generate_shipments(rng)
        assignments = _generate_assignments(shipments)
        events = _generate_events(shipments, rng)
        photos = _generate_photos(events)
        access_logs = _generate_access_logs(shipments, rng)

        # 1. Insert partners
        for p in PARTNERS:
            conn.execute(
                """INSERT INTO partners (partner_id, name, status, contract_end,
                   service_area, approved_scope, vendor_evidence_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    p["partner_id"], p["name"], p["status"],
                    p["contract_end"], p["service_area"],
                    p["approved_scope"], p["vendor_evidence_id"],
                ),
            )

        # 2. Insert contract history
        for ch in contract_history:
            conn.execute(
                """INSERT INTO contract_history
                   (history_id, partner_id, contract_snapshot_json,
                    effective_from, effective_until, changed_by, changed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    ch["history_id"], ch["partner_id"],
                    ch["contract_snapshot_json"], ch["effective_from"],
                    ch["effective_until"], ch["changed_by"],
                    ch["changed_at"],
                ),
            )

        # 3. Insert shipments
        for s in shipments:
            conn.execute(
                """INSERT INTO shipments
                   (shipment_id, partner_id, expected_count, expected_weight_g,
                    expected_seal, destination_lat, destination_lon, status,
                    reference_event_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    s["shipment_id"], s["partner_id"], s["expected_count"],
                    s["expected_weight_g"], s["expected_seal"],
                    s["destination_lat"], s["destination_lon"],
                    s["status"], s["reference_event_id"],
                ),
            )

        # 4. Insert assignments
        for a in assignments:
            conn.execute(
                """INSERT INTO assignments
                   (assignment_id, shipment_id, partner_id, actor_id,
                    valid_from, valid_until, allowed_actions)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    a["assignment_id"], a["shipment_id"], a["partner_id"],
                    a["actor_id"], a["valid_from"], a["valid_until"],
                    a["allowed_actions"],
                ),
            )

        # 5. Insert events
        for e in events:
            conn.execute(
                """INSERT INTO events
                   (event_id, shipment_id, partner_id, actor_id, event_type,
                    occurred_at, received_at, source, payload_json, is_synthetic)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (
                    e["event_id"], e["shipment_id"], e["partner_id"],
                    e["actor_id"], e["event_type"], e["occurred_at"],
                    e["received_at"], e["source"],
                    json.dumps(e["payload"]),
                ),
            )

        # 6. Update reference_event_id for demo cases
        for ship_id, event_type in [
            ("PV-DEMO-001", "handoff_submitted"),
            ("PV-SHIP-011", "handoff_submitted"),
        ]:
            ref_event = [
                e for e in events
                if e["shipment_id"] == ship_id
                and e["event_type"] == event_type
            ]
            if ref_event:
                conn.execute(
                    "UPDATE shipments SET reference_event_id = ? "
                    "WHERE shipment_id = ?",
                    (ref_event[0]["event_id"], ship_id),
                )

        # 7. Insert photos
        for p in photos:
            conn.execute(
                """INSERT INTO photos
                   (photo_id, event_id, local_path, sha256, phash,
                    uploaded_at, claimed_capture_at, capture_method,
                    manual_observation)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    p["photo_id"], p["event_id"], p["local_path"],
                    p["sha256"], p["phash"], p["uploaded_at"],
                    p["claimed_capture_at"], p["capture_method"],
                    p["manual_observation"],
                ),
            )

        # 8. Insert access logs
        for al in access_logs:
            conn.execute(
                """INSERT INTO access_logs
                   (log_id, partner_id, actor_id, credential_id,
                    shipment_id, occurred_at, action, outcome,
                    returned_fields, batch_job_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    al["log_id"], al["partner_id"], al["actor_id"],
                    al["credential_id"], al["shipment_id"],
                    al["occurred_at"], al["action"], al["outcome"],
                    al["returned_fields"], al["batch_job_id"],
                ),
            )

        conn.commit()
        return _get_counts(conn)
    finally:
        conn.close()
