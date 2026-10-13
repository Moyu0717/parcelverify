"""
ParcelVerify — Audit Service
Owner: Role D (Application Agent)

Provides:
- append_audit(): Append audit event (transactional — D-015)
- export_audit(): Export audit trail as JSON (authorization enforced)
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from contracts import ActorContext, AuditError, AuthorizationError
from db import get_connection


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_actor(actor_context: dict | None) -> ActorContext | None:
    if actor_context is None:
        return None
    return ActorContext(**actor_context)


def append_audit(
    db_path: str = "data/parcelverify.db",
    actor_id: str = "",
    case_id: str | None = None,
    operation: str = "",
    details: dict | None = None,
    tx: sqlite3.Connection | None = None,
) -> bool:
    """Append audit event.

    If ``tx`` (a ``sqlite3.Connection``) is provided: writes within that
    transaction. If the audit write fails, the transaction rolls back —
    the business state change does NOT persist (D-015).

    If no ``tx``: opens its own connection, raises ``AuditError`` on failure.

    Returns ``True`` on success.
    """
    details = details or {}
    audit_id = str(uuid.uuid4())
    occurred_at = _utc_now_iso()
    details_json = json.dumps(details, default=str)

    if tx is not None:
        try:
            tx.execute(
                """INSERT INTO audit_log
                   (audit_id, occurred_at, actor_id, case_id, operation, details_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (audit_id, occurred_at, actor_id, case_id, operation, details_json),
            )
            return True
        except Exception as e:
            raise AuditError(f"Audit write failed within transaction: {e}")

    # Standalone connection
    conn = get_connection(db_path)
    try:
        conn.execute(
            """INSERT INTO audit_log
               (audit_id, occurred_at, actor_id, case_id, operation, details_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (audit_id, occurred_at, actor_id, case_id, operation, details_json),
        )
        conn.commit()
        return True
    except Exception as e:
        raise AuditError(f"Audit write failed: {e}")
    finally:
        conn.close()


def export_audit(
    db_path: str = "data/parcelverify.db",
    case_id: str | None = None,
    actor_context: dict | None = None,
) -> dict:
    """Export audit trail as JSON.

    Authorization enforced on ``case_id`` — cannot export audit for
    unauthorized cases (D-014).
    """
    actor = _validate_actor(actor_context)
    if actor is None:
        raise AuthorizationError("Audit export requires actor context")

    conn = get_connection(db_path)
    try:
        if case_id is None:
            # Export all — requires admin actor_context
            if actor and actor.role != "admin":
                raise AuthorizationError(
                    "Only admin can export full audit trail"
                )
            rows = conn.execute(
                """SELECT audit_id, occurred_at, actor_id, case_id,
                          operation, details_json
                   FROM audit_log ORDER BY occurred_at"""
            ).fetchall()
        else:
            # Check authorization for this case
            if actor and actor.role not in ("admin", "investigator", "approver"):
                from services.access import _is_authorized
                case = conn.execute("SELECT shipment_id FROM case_records WHERE case_id = ?", (case_id,)).fetchone()
                if not case or not _is_authorized(conn, actor, case[0], _utc_now_iso())[0]:
                    raise AuthorizationError(f"Actor is not authorized for case {case_id}")

            rows = conn.execute(
                """SELECT audit_id, occurred_at, actor_id, case_id,
                          operation, details_json
                   FROM audit_log
                   WHERE case_id = ?
                   ORDER BY occurred_at""",
                (case_id,),
            ).fetchall()

        events = []
        for row in rows:
            events.append({
                "audit_id": row[0],
                "occurred_at": row[1],
                "actor_id": row[2],
                "case_id": row[3],
                "operation": row[4],
                "details": json.loads(row[5]) if row[5] else {},
            })

        return {"events": events, "format": "json"}
    finally:
        conn.close()
