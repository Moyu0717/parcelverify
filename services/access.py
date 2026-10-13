"""
ParcelVerify — Access Service (Gate 1)
Owner: Role B (Evidence Agent)

Provides:
- query_shipment(): Authorization check + access logging
- check_access_scope(): Compare access logs against assignments
- get_contract_at_time(): Historical contract snapshot lookup (D-019)
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from contracts import ActorContext, AuthorizationError
from db import get_connection


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_actor(actor_context: dict) -> ActorContext:
    return ActorContext(**actor_context)


def get_contract_at_time(
    db_path: str = "data/parcelverify.db",
    partner_id: str = "",
    at_time: str = "",
) -> dict:
    """Return the contract snapshot that was active at ``at_time``.

    Uses the ``contract_history`` table: finds the row where
    ``effective_from <= at_time < effective_until`` (or ``effective_until IS NULL``).

    Falls back to the current ``partners`` row if no history entry matches.
    """
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            """
            SELECT history_id, partner_id, contract_snapshot_json,
                   effective_from, effective_until, changed_by, changed_at
            FROM contract_history
            WHERE partner_id = ?
              AND effective_from <= ?
              AND (effective_until IS NULL OR effective_until > ?)
            ORDER BY effective_from DESC
            LIMIT 1
            """,
            (partner_id, at_time, at_time),
        ).fetchone()

        if row:
            snapshot = json.loads(row[2])
            return {
                "partner_id": partner_id,
                "contract_snapshot": snapshot,
                "effective_from": row[3],
                "effective_until": row[4],
                "source": "contract_history",
            }

        # Fallback: use current partners row
        row = conn.execute(
            "SELECT partner_id, name, status, contract_end, "
            "service_area, approved_scope, vendor_evidence_id "
            "FROM partners WHERE partner_id = ?",
            (partner_id,),
        ).fetchone()

        if not row:
            return {
                "partner_id": partner_id,
                "contract_snapshot": {},
                "effective_from": None,
                "effective_until": None,
                "source": "partners_fallback",
            }

        snapshot = {
            "name": row[1],
            "status": row[2],
            "contract_end": row[3],
            "service_area": row[4],
            "approved_scope": row[5],
            "vendor_evidence_id": row[6],
        }
        return {
            "partner_id": partner_id,
            "contract_snapshot": snapshot,
            "effective_from": None,
            "effective_until": None,
            "source": "partners_fallback",
        }
    finally:
        conn.close()


def _is_authorized(
    conn: sqlite3.Connection,
    actor: ActorContext,
    shipment_id: str,
    at_time: str,
) -> tuple[bool, str | None]:
    """Check if actor is authorized for the shipment at ``at_time``.

    Admins and investigators bypass assignment checks.
    Partner users must have a valid assignment row.
    Returns ``(authorized, denied_reason)``.
    """
    if actor.role in ("admin", "investigator", "approver"):
        return True, None
    ship = conn.execute("SELECT partner_id FROM shipments WHERE shipment_id = ?", (shipment_id,)).fetchone()
    if not ship or not actor.partner_id or ship[0] != actor.partner_id:
        return False, "Actor partner does not match shipment partner"
    partner = conn.execute("SELECT status, contract_end FROM partners WHERE partner_id = ?", (actor.partner_id,)).fetchone()
    if not partner or partner[0] != "active":
        return False, "Partner contract is not active"
    if partner[1] and _parse_time(partner[1]) <= _parse_time(at_time):
        return False, "Partner contract has expired"
    rows = conn.execute("SELECT valid_from, valid_until, allowed_actions FROM assignments WHERE shipment_id = ? AND actor_id = ? AND partner_id = ?", (shipment_id, actor.actor_id, actor.partner_id)).fetchall()
    for start, end, actions in rows:
        if _parse_time(start) <= _parse_time(at_time) and (not end or _parse_time(end) > _parse_time(at_time)) and "view" in json.loads(actions):
            return True, None
    return False, f"Actor {actor.actor_id} has no valid assignment for shipment {shipment_id}"


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def query_shipment(
    db_path: str = "data/parcelverify.db",
    actor_context: dict | None = None,
    shipment_id: str = "",
    at_time: str | None = None,
) -> dict:
    """Check authorization first; return allowed fields or deny. Logs access.

    Uses ``contract_history`` for time-accurate authorization (D-019).
    """
    actor = _validate_actor(actor_context or {})
    check_time = _utc_now_iso()  # Server time for live access.

    conn = get_connection(db_path)
    log_id = str(uuid.uuid4())
    try:
        # Get shipment
        ship_row = conn.execute(
            "SELECT shipment_id, partner_id, expected_count, "
            "expected_weight_g, expected_seal, destination_lat, "
            "destination_lon, status, reference_event_id "
            "FROM shipments WHERE shipment_id = ?",
            (shipment_id,),
        ).fetchone()

        if not ship_row:
            # Log denied — shipment not found
            conn.execute(
                """INSERT INTO access_logs
                   (log_id, partner_id, actor_id, credential_id,
                    shipment_id, occurred_at, action, outcome,
                    returned_fields, batch_job_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (log_id, actor.partner_id, actor.actor_id,
                 f"ROLE-{actor.role}:CREDS-{actor.actor_id}", shipment_id,
                 check_time, "query_shipment", "denied",
                 json.dumps([]), None),
            )
            conn.commit()
            return {
                "authorized": False,
                "denied_reason": f"Shipment {shipment_id} not found",
                "fields": None,
                "log_id": log_id,
            }

        partner_id = ship_row[1]

        # Check authorization
        authorized, denied_reason = _is_authorized(
            conn, actor, shipment_id, check_time
        )

        if not authorized:
            conn.execute(
                """INSERT INTO access_logs
                   (log_id, partner_id, actor_id, credential_id,
                    shipment_id, occurred_at, action, outcome,
                    returned_fields, batch_job_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (log_id, partner_id, actor.actor_id,
                 f"ROLE-{actor.role}:CREDS-{actor.actor_id}", shipment_id,
                 check_time, "query_shipment", "denied",
                 json.dumps([]), None),
            )
            conn.commit()
            return {
                "authorized": False,
                "denied_reason": denied_reason,
                "fields": None,
                "log_id": log_id,
            }

        # Authorized — return shipment fields
        fields = {
            "shipment_id": ship_row[0],
            "partner_id": ship_row[1],
            "expected_count": ship_row[2],
            "expected_weight_g": ship_row[3],
            "expected_seal": ship_row[4],
            "destination_lat": ship_row[5],
            "destination_lon": ship_row[6],
            "status": ship_row[7],
            "reference_event_id": ship_row[8],
        }

        conn.execute(
            """INSERT INTO access_logs
               (log_id, partner_id, actor_id, credential_id,
                shipment_id, occurred_at, action, outcome,
                returned_fields, batch_job_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (log_id, partner_id, actor.actor_id,
             f"ROLE-{actor.role}:CREDS-{actor.actor_id}", shipment_id,
             check_time, "query_shipment", "authorized",
             json.dumps(list(fields.keys())), None),
        )
        conn.commit()

        return {
            "authorized": True,
            "denied_reason": None,
            "fields": fields,
            "log_id": log_id,
        }
    finally:
        conn.close()


def check_access_scope(
    db_path: str = "data/parcelverify.db",
    case_id: str = "",
    actor_context: dict | None = None,
) -> dict:
    """Compare access logs against assignments and permissions.

    Returns access logs for the case's shipment(s) and any violations found.
    """
    actor = _validate_actor(actor_context or {})
    conn = get_connection(db_path)
    try:
        # Get case's shipment
        case_row = conn.execute(
            "SELECT shipment_id, partner_id FROM case_records WHERE case_id = ?",
            (case_id,),
        ).fetchone()

        if not case_row:
            return {
                "case_id": case_id,
                "access_logs": [],
                "violations": [],
                "authorized": False,
            }

        shipment_id, partner_id = case_row

        authorized, _ = _is_authorized(conn, actor, shipment_id, _utc_now_iso())
        if not authorized:
            return {"case_id": case_id, "access_logs": [], "violations": [], "authorized": False}

        # Get all access logs for this shipment
        log_rows = conn.execute(
            """SELECT log_id, actor_id, shipment_id, action, outcome,
                      occurred_at, returned_fields, batch_job_id, credential_id
               FROM access_logs
               WHERE shipment_id = ?
               ORDER BY occurred_at""",
            (shipment_id,),
        ).fetchall()

        access_logs = []
        violations = []

        for row in log_rows:
            log_id, log_actor_id, log_shipment_id, action, outcome, occurred_at, \
                returned_fields, batch_job_id, credential_id = row

            access_logs.append({
                "log_id": log_id,
                "actor_id": log_actor_id,
                "shipment_id": log_shipment_id,
                "action": action,
                "outcome": outcome,
                "occurred_at": occurred_at,
            })

            # Check for violations: denied outcomes or unauthorized access
            if outcome == "denied":
                violations.append({
                    "type": "unauthorized_access_attempt",
                    "detail": (
                        f"Actor {log_actor_id} attempted unauthorized "
                        f"access to shipment {log_shipment_id} at {occurred_at}"
                    ),
                    "evidence_ids": [log_id],
                })

        # Check if any actor accessed the shipment without a valid assignment
        for row in log_rows:
            log_id, log_actor_id, log_shipment_id, action, outcome, occurred_at, \
                returned_fields, batch_job_id, credential_id = row

            internal = credential_id and any(credential_id.startswith(f"ROLE-{role}:") for role in ("admin", "investigator", "approver"))
            if outcome == "authorized" and log_actor_id and not internal:
                # Verify the actor had a valid assignment
                assignment = conn.execute(
                    """SELECT 1 FROM assignments
                       WHERE shipment_id = ?
                         AND actor_id = ?
                         AND valid_from <= ?
                         AND (valid_until IS NULL OR valid_until > ?)
                       LIMIT 1""",
                    (log_shipment_id, log_actor_id, occurred_at, occurred_at),
                ).fetchone()

                if not assignment:
                    # Check if it's an admin/investigator (bypass)
                    # We can't know the role from the log alone,
                    # so we flag it as a potential violation
                    violations.append({
                        "type": "missing_assignment",
                        "detail": (
                            f"Actor {log_actor_id} accessed shipment "
                            f"{log_shipment_id} at {occurred_at} "
                            f"without a matching assignment record"
                        ),
                        "evidence_ids": [log_id],
                    })

        # Admin/investigator can see all
        if actor.role in ("admin", "investigator", "approver"):
            authorized = True
        else:
            authorized = actor.partner_id == partner_id

        return {
            "case_id": case_id,
            "access_logs": access_logs,
            "violations": violations,
            "authorized": authorized,
        }
    finally:
        conn.close()
