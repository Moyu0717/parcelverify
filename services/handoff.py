"""
ParcelVerify — Handoff Service (Gate 2)
Owner: Role B (Evidence Agent)

Provides:
- evaluate_handoff(): Rule results, contradictions, missing evidence
- compare_handoff(): Compare count/weight/seal/recipient across handoff events
- create_or_update_case(): Idempotent case creation (D-016)
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from contracts import (
    WEIGHT_DIFF_MIN_G,
    WEIGHT_DIFF_PCT,
    RULE_VERSION,
)
from db import get_connection


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compare_handoff(
    db_path: str = "data/parcelverify.db",
    shipment_id: str = "",
    event_id: str | None = None,
) -> dict:
    """Compare count/weight/seal/recipient across handoff events.

    Compares the expected values (from shipments table) against
    the actual values from the handoff_submitted event payload.
    """
    conn = get_connection(db_path)
    try:
        ship = conn.execute(
            "SELECT expected_count, expected_weight_g, expected_seal, "
            "destination_lat, destination_lon "
            "FROM shipments WHERE shipment_id = ?",
            (shipment_id,),
        ).fetchone()

        if not ship:
            return {
                "shipment_id": shipment_id,
                "count": {"expected": None, "actual": None, "match": None},
                "weight_g": {"expected": None, "actual": None, "diff": None, "match": None},
                "seal": {"expected": None, "actual": None, "match": None},
                "recipient": {"expected": None, "actual": None, "authorized": None},
                "unknowns": ["shipment_not_found"],
            }

        expected_count = ship[0]
        expected_weight = ship[1]
        expected_seal = ship[2]
        dest_lat = ship[3]
        dest_lon = ship[4]

        # Selected evidence is bounded by its actual event time. A POD without
        # measurements inherits the latest preceding measurement-bearing event.
        selected = None
        if event_id:
            selected = conn.execute("SELECT event_id, event_type, occurred_at, received_at, payload_json FROM events WHERE shipment_id = ? AND event_id = ?", (shipment_id, event_id)).fetchone()
        cutoff = selected[2] if selected else None
        selected_payload = json.loads(selected[4]) if selected else {}
        measurement_keys = ("count", "weight_g", "seal_id")
        if selected and any(key in selected_payload for key in measurement_keys):
            handoff = (selected[4], selected[0])
        elif event_id and not selected:
            handoff = None
        else:
            candidates = conn.execute("""SELECT payload_json, event_id FROM events WHERE shipment_id = ?
                AND event_type IN ('handoff_submitted', 'collection_submitted', 'collection_confirmed', 'collected',
                'collection', 'transit_submitted', 'transit_handoff', 'transit', 'pod_submitted')
                AND (? IS NULL OR julianday(occurred_at) <= julianday(?))
                ORDER BY julianday(occurred_at) DESC""", (shipment_id, cutoff, cutoff)).fetchall()
            handoff = next((row for row in candidates if any(key in json.loads(row[0]) for key in measurement_keys)), None)

        no_measurements = handoff is None
        if not handoff:
            handoff = ("{}", selected[0] if selected else None)

        payload = json.loads(handoff[0])
        actual_count = payload.get("count")
        actual_weight = payload.get("weight_g")
        actual_seal = payload.get("seal_id")
        handoff_location = payload.get("handoff_location")

        # Count comparison
        count_match = None
        if actual_count is not None and expected_count is not None:
            count_match = actual_count == expected_count

        # Weight comparison
        weight_diff = None
        weight_match = None
        if actual_weight is not None and expected_weight is not None:
            weight_diff = round(actual_weight - expected_weight, 2)
            threshold = max(WEIGHT_DIFF_MIN_G, abs(expected_weight) * WEIGHT_DIFF_PCT)
            weight_match = abs(weight_diff) <= threshold

        # Seal comparison
        seal_match = None
        if actual_seal is not None and expected_seal is not None:
            seal_match = actual_seal == expected_seal

        pod = conn.execute("""SELECT payload_json, occurred_at, event_id FROM events
            WHERE shipment_id = ? AND event_type = 'pod_submitted'
            AND (? IS NULL OR julianday(occurred_at) <= julianday(?))
            ORDER BY julianday(occurred_at) DESC LIMIT 1""", (shipment_id, cutoff, cutoff)).fetchone()
        recipient_name = None
        recipient_authorized = None
        expected_recipient = None
        recipient_refs = []
        pod_payload = json.loads(pod[0]) if pod else {}
        if pod:
            recipient_name = pod_payload.get("recipient_name")
            auth_event = conn.execute("""SELECT payload_json, event_id FROM events
                WHERE shipment_id = ? AND event_type = 'recipient_authorization'
                AND julianday(occurred_at) <= julianday(?)
                ORDER BY julianday(occurred_at) DESC LIMIT 1""", (shipment_id, pod[1])).fetchone()
            if auth_event:
                expected_recipient = json.loads(auth_event[0]).get("recipient_name")
                if expected_recipient and recipient_name:
                    recipient_authorized = expected_recipient == recipient_name
                    recipient_refs = [pod[2], auth_event[1]]
        gps_payload = pod_payload if pod else selected_payload or payload
        actual_lat = gps_payload.get("location_lat", gps_payload.get("latitude"))
        actual_lon = gps_payload.get("location_lon", gps_payload.get("longitude"))
        accuracy = gps_payload.get("gps_accuracy_m", gps_payload.get("accuracy_m"))
        gps_valid = _valid_gps(actual_lat, actual_lon) and (accuracy is None or isinstance(accuracy, (int, float)) and 0 <= accuracy <= 1000)
        destination_valid = _valid_gps(dest_lat, dest_lon)
        location_conflict = False
        # Destination comparison is meaningful only for delivery evidence.
        if pod and gps_valid and destination_valid:
            from math import radians, sin, cos, asin, sqrt
            dlat, dlon = radians(actual_lat - dest_lat), radians(actual_lon - dest_lon)
            distance_km = 12742 * asin(min(1, sqrt(sin(dlat / 2)**2 + cos(radians(dest_lat)) * cos(radians(actual_lat)) * sin(dlon / 2)**2)))
            location_conflict = distance_km > 50
        time_conflict = False
        if selected and selected[2] and selected[3]:
            from services.access import _parse_time
            try:
                time_conflict = (_parse_time(selected[2]) - _parse_time(selected[3])).total_seconds() > 300
            except ValueError:
                pass

        time_refs = [selected[0]] if selected else []
        if selected and selected[1] == "pod_submitted" and selected[2]:
            dispatch = conn.execute("SELECT event_id, occurred_at FROM events WHERE shipment_id = ? AND event_type = 'dispatch_confirmed' ORDER BY julianday(occurred_at) LIMIT 1", (shipment_id,)).fetchone()
            if dispatch and dispatch[1]:
                from services.access import _parse_time
                try:
                    if _parse_time(selected[2]) < _parse_time(dispatch[1]):
                        time_conflict = True
                        time_refs.append(dispatch[0])
                except ValueError:
                    pass

        unknowns: list[str] = ["no_handoff_event"] if no_measurements else []
        if actual_count is None:
            unknowns.append("actual_count")
        if actual_weight is None:
            unknowns.append("actual_weight")
        if actual_seal is None:
            unknowns.append("actual_seal")
        if recipient_name is None:
            unknowns.append("recipient_name")
        if not destination_valid:
            unknowns.append("destination_gps")
        if not gps_valid:
            unknowns.append("actual_gps")
        if recipient_authorized is None:
            unknowns.append("recipient_authorization")

        return {
            "shipment_id": shipment_id,
            "count": {
                "expected": expected_count,
                "actual": actual_count,
                "match": count_match,
            },
            "weight_g": {
                "expected": expected_weight,
                "actual": actual_weight,
                "diff": weight_diff,
                "match": weight_match,
            },
            "seal": {
                "expected": expected_seal,
                "actual": actual_seal,
                "match": seal_match,
            },
            "recipient": {
                "expected": expected_recipient,
                "actual": recipient_name,
                "authorized": recipient_authorized,
            },
            "measurement_event_id": handoff[1],
            "recipient_evidence_ids": recipient_refs,
            "location_conflict": location_conflict,
            "time_conflict": time_conflict,
            "time_evidence_ids": time_refs,
            "unknowns": unknowns,
        }
    finally:
        conn.close()


def evaluate_handoff(
    db_path: str = "data/parcelverify.db",
    shipment_id: str = "",
    event_id: str = "",
    actor_context: dict | None = None,
) -> dict:
    """Return rule results, contradictions, missing evidence, evidence IDs.

    Evaluates a handoff event for:
    - Weight discrepancy (D-006: threshold = max(100g, base*5%))
    - Seal mismatch (D-002: 25 pt category)
    - Count discrepancy
    - Photo reuse (checks for duplicate SHA-256)
    - Repackaging explanation (D-005)
    - Scale calibration explanation (D-007)
    """
    conn = get_connection(db_path)
    try:
        actor = None
        if actor_context is not None:
            from contracts import ActorContext, AuthorizationError
            from services.access import _is_authorized
            actor = ActorContext(**actor_context)
            if not _is_authorized(conn, actor, shipment_id, _utc_now_iso())[0]:
                raise AuthorizationError("Actor is not authorized for shipment evidence")
        # Call compare_handoff directly (it accepts db_path as first arg)
        cmp = compare_handoff(db_path, shipment_id, event_id or None)

        findings: list[dict] = []
        missing_evidence: list[str] = []
        evidence_refs: list[str] = [value for value in (event_id, cmp.get("measurement_event_id")) if value]
        blocking_issues: list[str] = []

        # Weight check (D-006)
        weight = cmp["weight_g"]
        if weight["match"] is False:
            # Check for repackaging_approved event (D-005)
            repack = conn.execute(
                """SELECT event_id, payload_json FROM events
                   WHERE shipment_id = ? AND event_type = 'repackaging_approved'
                   ORDER BY occurred_at DESC LIMIT 1""",
                (shipment_id,),
            ).fetchone()

            if repack:
                evidence_refs.append(repack[0])
            explanation = _supported_repackaging(conn, shipment_id, cmp.get("measurement_event_id", event_id), repack, weight)
            if explanation is not None:
                repack_diff, measurement_ids = explanation
                evidence_refs.extend(measurement_ids)
                remaining_diff = abs((weight["diff"] or 0) - repack_diff)
                if remaining_diff > max(WEIGHT_DIFF_MIN_G, abs(weight["expected"] or 0) * WEIGHT_DIFF_PCT):
                    findings.append({
                        "category": "weight_diff",
                        "description": (
                            f"Weight discrepancy of {weight['diff']}g. "
                            f"Repackaging explains {repack_diff}g but "
                            f"remaining {round(remaining_diff, 2)}g still exceeds threshold."
                        ),
                        "severity": "warning",
                        "evidence_ids": [event_id, repack[0]],
                    })
                    blocking_issues.append("weight_diff_exceeds_threshold_after_repackaging")
                evidence_refs.append(repack[0])
            else:
                # Check for scale_calibration event (D-007)
                scale = conn.execute(
                    """SELECT event_id FROM events
                       WHERE shipment_id = ? AND event_type = 'scale_calibration'
                       LIMIT 1""",
                    (shipment_id,),
                ).fetchone()
                if scale:
                    findings.append({
                        "category": "weight_diff",
                        "description": (
                            f"Weight discrepancy of {weight['diff']}g. "
                            f"Scale calibration event exists but is an "
                            f"unverified hypothesis without calibration records."
                        ),
                        "severity": "warning",
                        "evidence_ids": [event_id, scale[0]],
                    })
                else:
                    findings.append({
                        "category": "weight_diff",
                        "description": (
                            f"Weight discrepancy of {weight['diff']}g "
                            f"(expected {weight['expected']}g, "
                            f"actual {weight['actual']}g). "
                            f"No valid explanation provided."
                        ),
                        "severity": "warning",
                        "evidence_ids": [event_id],
                    })
                blocking_issues.append("weight_diff_no_explanation")

        # Seal check (D-002)
        seal = cmp["seal"]
        if seal["match"] is False:
            findings.append({
                "category": "seal_mismatch",
                "description": (
                    f"Seal ID mismatch: expected '{seal['expected']}', "
                    f"actual '{seal['actual']}'."
                ),
                "severity": "blocking",
                "evidence_ids": [event_id],
            })
            blocking_issues.append("seal_mismatch")

        # Count check (D-003)
        count = cmp["count"]
        if count["match"] is False:
            # Check for per-item scan
            scan = conn.execute(
                """SELECT 1 FROM events
                   WHERE shipment_id = ? AND event_type = 'approved_batch_job'
                   AND payload_json LIKE '%scan%'
                   LIMIT 1""",
                (shipment_id,),
            ).fetchone()
            if not scan:
                missing_evidence.append("per_item_scan")
            findings.append({
                "category": "count_discrepancy",
                "description": (
                    f"Count discrepancy: expected {count['expected']}, "
                    f"actual {count['actual']}. "
                    f"{'No per-item scan available.' if not scan else 'Scan confirmed.'}"
                ),
                "severity": "info",
                "evidence_ids": [event_id],
            })

        # Photo reuse check
        photos = conn.execute(
            """SELECT p.photo_id, p.sha256, p.event_id, e.shipment_id
               FROM photos p
               JOIN events e ON p.event_id = e.event_id
               WHERE e.shipment_id = ?""",
            (shipment_id,),
        ).fetchall()

        if photos:
            sha_set: dict[str, list] = {}
            for p in photos:
                sha = p[1]
                if sha not in sha_set:
                    sha_set[sha] = []
                sha_set[sha].append(p[0])

            for sha, pids in sha_set.items():
                if len(pids) > 1:
                    findings.append({
                        "category": "photo_reuse",
                        "description": (
                            f"Same photo (SHA-256: {sha[:16]}...) "
                            f"appears {len(pids)} times on this shipment."
                        ),
                        "severity": "blocking",
                        "evidence_ids": pids,
                    })
                    blocking_issues.append("photo_reuse_exact_match")
                    evidence_refs.extend(pids)

        # Cross-shipment photo reuse
        if photos:
            for p in photos:
                cross = conn.execute(
                    """SELECT p2.photo_id, e2.shipment_id
                       FROM photos p2
                       JOIN events e2 ON p2.event_id = e2.event_id
                       WHERE p2.sha256 = ? AND e2.shipment_id != ?
                       LIMIT 1""",
                    (p[1], shipment_id),
                ).fetchone()
                if cross:
                    from services.access import _is_authorized
                    visible = actor is None or _is_authorized(conn, actor, cross[1], _utc_now_iso())[0]
                    findings.append({
                        "category": "photo_reuse",
                        "description": (
                            f"Photo {p[0]} (SHA-256: {p[1][:16]}...) "
                            + (f"also appears on shipment {cross[1]}." if visible else "matches evidence outside your authorized scope.")
                        ),
                        "severity": "blocking",
                        "evidence_ids": [p[0], cross[0]] if visible else [p[0]],
                    })
                    blocking_issues.append("photo_reuse_cross_shipment")
                    evidence_refs.extend([p[0], cross[0]] if visible else [p[0]])

        if cmp["recipient"]["authorized"] is False:
            findings.append({"category": "id_conflict", "description": "POD recipient does not match the recorded authorized recipient.", "severity": "blocking", "evidence_ids": cmp.get("recipient_evidence_ids", [])})
            blocking_issues.append("recipient_mismatch")
            evidence_refs.extend(cmp.get("recipient_evidence_ids", []))
        for key, category, description in (("location_conflict", "location_conflict", "Delivery GPS is more than 50 km from the recorded destination."), ("time_conflict", "time_conflict", "Recorded event time conflicts with server receipt or the dispatch-to-delivery order.")):
            if cmp.get(key):
                findings.append({"category": category, "description": description, "severity": "warning", "evidence_ids": cmp.get("time_evidence_ids", [event_id]) if key == "time_conflict" else [event_id]})
                if key == "time_conflict":
                    evidence_refs.extend(cmp.get("time_evidence_ids", []))
        # Missing evidence
        for unknown in cmp["unknowns"]:
            if unknown in ("shipment_not_found", "no_handoff_event"):
                missing_evidence.append(unknown)
            elif unknown == "actual_count":
                missing_evidence.append("handoff_count")
            elif unknown == "actual_weight":
                missing_evidence.append("handoff_weight")
            elif unknown == "actual_seal":
                missing_evidence.append("handoff_seal")
            elif unknown == "recipient_name":
                missing_evidence.append("pod_recipient")
            elif unknown in ("destination_gps", "actual_gps", "recipient_authorization"):
                missing_evidence.append(unknown)

        # Determine result
        if not findings:
            result = "insufficient_evidence" if cmp["unknowns"] else "consistent"
        elif any(f["severity"] == "blocking" for f in findings):
            result = "needs_review"
        else:
            result = "needs_review"

        return {
            "shipment_id": shipment_id,
            "event_id": event_id,
            "result": result,
            "findings": findings,
            "missing_evidence": missing_evidence,
            "evidence_refs": list(set(evidence_refs)),
            "blocking_issues": blocking_issues,
        }
    finally:
        conn.close()


def create_or_update_case(
    db_path: str = "data/parcelverify.db",
    shipment_id: str = "",
    triggering_event_id: str = "",
    findings: list[dict] | None = None,
    rule_version: str = RULE_VERSION,
) -> dict:
    """Create case if not exists for shipment+triggering event; update if exists.

    Idempotent key: ``(shipment_id, triggering_event_id)``.
    Streamlit refresh does NOT duplicate cases (D-016).
    """
    findings = findings or []
    conn = get_connection(db_path)
    try:
        # Check for existing case
        existing = conn.execute(
            """SELECT case_id, status, priority_score FROM case_records
               WHERE shipment_id = ? AND triggering_event_id = ?""",
            (shipment_id, triggering_event_id),
        ).fetchone()

        # Get partner_id from shipment
        ship = conn.execute(
            "SELECT partner_id FROM shipments WHERE shipment_id = ?",
            (shipment_id,),
        ).fetchone()
        partner_id = ship[0] if ship else None

        # Calculate priority from findings
        from services.risk import calculate_priority
        priority_result = calculate_priority(db_path, findings)

        if existing:
            case_id, _, _ = existing
            conn.execute(
                """UPDATE case_records
                   SET findings_json = ?, rule_version = ?,
                       priority_score = ?, updated_at = ?
                   WHERE case_id = ?""",
                (json.dumps(findings), rule_version,
                 priority_result["total_score"], _utc_now_iso(), case_id),
            )
            conn.commit()
            return {
                "case_id": case_id,
                "status": "pending_review" if priority_result["review_queue"] else "review_completed",
                "is_new": False,
                "priority_score": priority_result["total_score"],
                "review_queue": priority_result["review_queue"],
            }

        case_id = str(uuid.uuid4())
        status = "pending_review" if priority_result["review_queue"] else "review_completed"

        conn.execute(
            """INSERT INTO case_records
               (case_id, partner_id, shipment_id, triggering_event_id,
                status, priority_score, rule_version, findings_json,
                report_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)""",
            (case_id, partner_id, shipment_id, triggering_event_id,
             status, priority_result["total_score"], rule_version,
             json.dumps(findings), _utc_now_iso(), _utc_now_iso()),
        )
        conn.commit()

        return {
            "case_id": case_id,
            "status": status,
            "is_new": True,
            "priority_score": priority_result["total_score"],
            "review_queue": priority_result["review_queue"],
        }
    finally:
        conn.close()


def _supported_repackaging(conn, shipment_id, event_id, repack, weight):
    """Only linked, approved measurements can explain a signed weight change."""
    if not repack:
        return None
    payload = json.loads(repack[1])
    if not payload.get("approver_id") or payload.get("handoff_event_id") != event_id:
        return None
    measurement_ids = payload.get("supporting_measurement_ids", [])
    if not isinstance(measurement_ids, list) or len(measurement_ids) < 2:
        return None
    measurements = []
    for measurement_id in measurement_ids:
        row = conn.execute("SELECT event_type, payload_json FROM events WHERE event_id = ? AND shipment_id = ?", (measurement_id, shipment_id)).fetchone()
        if not row or row[0] not in ("reweigh", "reweigh_submitted", "weight_measured"):
            return None
        value = json.loads(row[1]).get("weight_g")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            return None
        measurements.append(value)
    if abs(measurements[0] - weight["expected"]) > 0.01 or abs(measurements[-1] - weight["actual"]) > 0.01:
        return None
    delta = measurements[-1] - measurements[0]
    claimed = payload.get("weight_diff_g")
    if not isinstance(claimed, (int, float)) or abs(abs(delta) - abs(claimed)) > 0.01:
        return None
    return delta, measurement_ids


def _valid_gps(lat, lon):
    from math import isfinite
    return (isinstance(lat, (int, float)) and not isinstance(lat, bool)
            and isinstance(lon, (int, float)) and not isinstance(lon, bool)
            and isfinite(lat) and isfinite(lon) and -90 <= lat <= 90
            and -180 <= lon <= 180 and (lat, lon) != (0, 0))
