"""
ParcelVerify — Actions Service
Owner: Role D (Application Agent)

Provides:
- propose_action(): Create a pending approval request (does not execute)
- review_action(): Validate approval authority; record decision (rejected is terminal — D-019)
- execute_action(): 5 pre-checks, transactional, rollback on failure (D-019)
- create_evidence_task(): Idempotent supplementary evidence request (D-016)
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from contracts import (
    ActorContext,
    ActionStatus,
    ActionType,
    AuditError,
    AuthorizationError,
    CaseStatus,
    EvidenceTaskType,
    IdempotencyError,
)
from db import get_connection
from services.audit import append_audit
from services.access import _parse_time


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_actor(actor_context: dict) -> ActorContext:
    return ActorContext(**actor_context)


def propose_action(
    db_path: str = "data/parcelverify.db",
    case_id: str = "",
    action_type: str = "",
    actor_context: dict | None = None,
    **kwargs,
) -> dict:
    """Create a pending approval request. Does not execute.

    Optional ``request_id`` retries the same intent without duplicating it.
    Returns action_id, persisted status, and is_new.
    """
    actor = _validate_actor(actor_context or {})
    conn = get_connection(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        # Verify case exists
        case = conn.execute(
            "SELECT case_id, status, partner_id, shipment_id FROM case_records WHERE case_id = ?",
            (case_id,),
        ).fetchone()
        if not case:
            raise ValueError(f"Case {case_id} not found")

        # Only investigators and admins can propose actions
        if actor.role not in ("investigator", "admin"):
            raise AuthorizationError(
                f"Actor {actor.actor_id} (role={actor.role}) cannot propose actions"
            )

        ActionType(action_type)
        request_id = kwargs.get("request_id")
        if request_id is not None and (not isinstance(request_id, str) or not request_id.strip()):
            raise ValueError("request_id must be a nonempty string")
        action_id = request_id if request_id is not None else str(uuid.uuid4())
        target_id = kwargs.get("target_id", case[3] or "")  # shipment_id
        expires_at = kwargs.get("expires_at")
        reason = kwargs.get("reason", "")

        if request_id is not None:
            existing = conn.execute(
                "SELECT case_id,action_type,target_id,requested_by,reason,status FROM action_requests WHERE action_id=?",
                (request_id,),
            ).fetchone()
            if existing:
                if existing[:5] != (case_id, action_type, target_id, actor.actor_id, reason):
                    raise IdempotencyError("request_id is already used for a different action intent")
                return {"action_id": action_id, "status": existing[5], "is_new": False}

        conn.execute(
            """INSERT INTO action_requests
               (action_id, case_id, action_type, target_id, status,
                requested_by, approved_by, approved_at, executed_at,
                expires_at, reason, before_json, after_json)
               VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, NULL, NULL)""",
            (action_id, case_id, action_type, target_id,
             ActionStatus.PROPOSED.value, actor.actor_id,
             expires_at, reason),
        )
        conn.commit()

        return {"action_id": action_id, "status": ActionStatus.PROPOSED.value, "is_new": True}
    finally:
        conn.close()


def review_action(
    db_path: str = "data/parcelverify.db",
    action_id: str = "",
    decision: str = "",
    actor_context: dict | None = None,
    reason: str = "",
) -> dict:
    """Validate approval authority; record decision.

    ``decision``: "approve" or "reject".
    ``rejected`` is terminal — cannot transition to executed or back to approved (D-019).
    """
    actor = _validate_actor(actor_context or {})

    if decision not in ("approve", "reject"):
        raise ValueError(f"Invalid decision: {decision}. Must be 'approve' or 'reject'")

    conn = get_connection(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        action = conn.execute(
            "SELECT action_id, case_id, status, action_type, target_id "
            "FROM action_requests WHERE action_id = ?",
            (action_id,),
        ).fetchone()

        if not action:
            raise ValueError(f"Action {action_id} not found")

        _, case_id, status, action_type, target_id = action

        # Only approvers and admins can review
        if actor.role not in ("approver", "admin"):
            raise AuthorizationError(
                f"Actor {actor.actor_id} (role={actor.role}) cannot review actions"
            )

        # Must be in proposed status
        if status != ActionStatus.PROPOSED.value:
            raise IdempotencyError(
                f"Action {action_id} is in status '{status}', not 'proposed'. "
                f"Cannot review."
            )

        new_status = ActionStatus.APPROVED.value if decision == "approve" else ActionStatus.REJECTED.value

        conn.execute(
            """UPDATE action_requests
               SET status = ?, approved_by = ?, approved_at = ?
               WHERE action_id = ?""",
            (new_status, actor.actor_id, _utc_now_iso(), action_id),
        )

        # Audit the review
        append_audit(
            db_path, actor.actor_id, case_id,
            f"action_{decision}d",
            {"action_id": action_id, "action_type": action_type, "reason": reason},
            tx=conn,
        )

        conn.commit()

        return {
            "action_id": action_id,
            "status": new_status,
            "approved_by": actor.actor_id,
            "approved_at": _utc_now_iso(),
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute_action(
    db_path: str = "data/parcelverify.db",
    action_id: str = "",
    actor_context: dict | None = None,
) -> dict:
    """Pre-checks: status=approved, not expired, approver authority,
    case state, idempotency.

    Transactional: business state change + audit in same transaction.
    Rollback on failure → status=failed, no partial state (D-019).
    """
    actor = _validate_actor(actor_context or {})
    if actor.role not in ("approver", "admin"):
        raise AuthorizationError("Only a current approver or admin may execute actions")
    conn = get_connection(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        action = conn.execute(
            """SELECT action_id, case_id, status, action_type, target_id,
                      approved_by, approved_at, expires_at, reason
               FROM action_requests WHERE action_id = ?""",
            (action_id,),
        ).fetchone()

        if not action:
            raise ValueError(f"Action {action_id} not found")

        _, case_id, status, action_type, target_id, \
            approved_by, approved_at, expires_at, reason = action

        now = _utc_now_iso()

        # Pre-check 5: Idempotency — if already executed, return already_executed
        if status == ActionStatus.EXECUTED.value:
            return {
                "action_id": action_id,
                "status": "already_executed",
                "before": None,
                "after": None,
                "error": None,
            }

        # Pre-check 1: Action status must be approved
        if status == ActionStatus.REJECTED.value:
            return {
                "action_id": action_id,
                "status": "not_approved",
                "before": None,
                "after": None,
                "error": "Action is rejected (terminal). Cannot execute.",
            }
        if status == ActionStatus.PROPOSED.value:
            return {
                "action_id": action_id,
                "status": "not_approved",
                "before": None,
                "after": None,
                "error": "Action is still proposed. Must be approved first.",
            }

        # Pre-check 2: Action must not be expired
        if expires_at and _parse_time(expires_at) <= _parse_time(now):
            return {
                "action_id": action_id,
                "status": "expired",
                "before": None,
                "after": None,
                "error": f"Action expired at {expires_at}",
            }

        approval = conn.execute("SELECT details_json FROM audit_log WHERE case_id = ? AND actor_id = ? AND operation = 'action_approved'", (case_id, approved_by)).fetchall()
        if not approved_by or not any(json.loads(row[0]).get("action_id") == action_id for row in approval):
            raise AuthorizationError("Action has no verified approval record")
        if status not in (ActionStatus.APPROVED.value, ActionStatus.FAILED.value):
            raise AuthorizationError("Action is not approved")

        # Pre-check 4: Case must still be in a state that allows this action
        case = conn.execute(
            "SELECT status FROM case_records WHERE case_id = ?",
            (case_id,),
        ).fetchone()
        if not case:
            return {
                "action_id": action_id,
                "status": "failed",
                "before": None,
                "after": None,
                "error": f"Case {case_id} not found",
            }
        case_status = case[0]
        if case_status in (CaseStatus.CLOSED.value, CaseStatus.ACTION_EXECUTED.value):
            return {
                "action_id": action_id,
                "status": "failed",
                "before": None,
                "after": None,
                "error": f"Case is in terminal state '{case_status}'",
            }

        # Capture before state
        before = {
            "case_status": case_status,
            "target_id": target_id,
            "action_type": action_type,
        }

        try:
            new_case_status = CaseStatus.ACTION_EXECUTED.value
            task_types = {
                ActionType.REQUEST_REWEIGH.value: EvidenceTaskType.REWEIGH.value,
                ActionType.REQUEST_REPHOTO.value: EvidenceTaskType.REPHOTO.value,
                ActionType.REQUEST_RESCAN.value: EvidenceTaskType.RESCAN.value,
            }
            task_id = None
            if action_type in task_types:
                task_type = task_types[action_type]
                conn.execute(
                    """INSERT OR IGNORE INTO evidence_tasks
                       (task_id, case_id, task_type, description, status, created_by, created_at)
                       VALUES (?, ?, ?, ?, 'open', ?, ?)""",
                    (str(uuid.uuid4()), case_id, task_type, reason, actor.actor_id, now),
                )
                task_id = conn.execute(
                    "SELECT task_id FROM evidence_tasks WHERE case_id = ? AND task_type = ? AND status = 'open'",
                    (case_id, task_type),
                ).fetchone()[0]
            shipment_status = None
            if action_type in (ActionType.HOLD_HANDOFF.value, ActionType.HOLD_POD.value):
                shipment = conn.execute("SELECT status FROM shipments WHERE shipment_id = ?", (target_id,)).fetchone()
                if not shipment:
                    raise ValueError(f"Target shipment {target_id} not found")
                before["shipment_status"] = shipment[0]
                shipment_status = f"simulated_{action_type}"
                conn.execute("UPDATE shipments SET status = ? WHERE shipment_id = ?", (shipment_status, target_id))

            conn.execute(
                "UPDATE case_records SET status = ?, updated_at = ? WHERE case_id = ?",
                (new_case_status, now, case_id),
            )

            after = {
                "case_status": new_case_status,
                "target_id": target_id,
                "action_type": action_type,
            }

            if task_id is not None:
                after["evidence_task_id"] = task_id
                after["evidence_task_type"] = task_types[action_type]
            if shipment_status is not None:
                after["shipment_status"] = shipment_status

            # Update action status
            conn.execute(
                """UPDATE action_requests
                   SET status = ?, executed_at = ?, before_json = ?, after_json = ?
                   WHERE action_id = ?""",
                (ActionStatus.EXECUTED.value, now,
                 json.dumps(before), json.dumps(after), action_id),
            )

            # Audit the execution (same transaction)
            append_audit(
                db_path, actor.actor_id, case_id,
                "action_executed",
                {
                    "action_id": action_id,
                    "action_type": action_type,
                    "target_id": target_id,
                    "before": before,
                    "after": after,
                },
                tx=conn,
            )

            conn.commit()

            return {
                "action_id": action_id,
                "status": ActionStatus.EXECUTED.value,
                "before": before,
                "after": after,
                "error": None,
            }
        except Exception as e:
            # Rollback — no partial state
            conn.rollback()
            # Mark as failed in a new transaction
            conn.execute(
                """UPDATE action_requests
                   SET status = ?, executed_at = ?
                   WHERE action_id = ?""",
                (ActionStatus.FAILED.value, now, action_id),
            )
            conn.commit()

            return {
                "action_id": action_id,
                "status": ActionStatus.FAILED.value,
                "before": before,
                "after": None,
                "error": str(e),
            }
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_evidence_task(
    db_path: str = "data/parcelverify.db",
    case_id: str = "",
    task_type: str = "",
    actor_context: dict | None = None,
    description: str = "",
) -> dict:
    """Create supplementary evidence request (reweigh, rephoto, rescan).

    Idempotent: one open task per ``(case_id, task_type)`` (D-016).
    Duplicate returns existing task with ``is_new=False``.
    """
    actor = _validate_actor(actor_context or {})
    conn = get_connection(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        if actor.role not in ("investigator", "admin", "approver"):
            raise AuthorizationError("Only internal reviewers may request evidence")
        EvidenceTaskType(task_type)
        # Check for existing open task
        existing = conn.execute(
            """SELECT task_id FROM evidence_tasks
               WHERE case_id = ? AND task_type = ? AND status = 'open'
               LIMIT 1""",
            (case_id, task_type),
        ).fetchone()

        if existing:
            return {
                "task_id": existing[0],
                "case_id": case_id,
                "task_type": task_type,
                "status": "open",
                "is_new": False,
            }

        task_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO evidence_tasks
               (task_id, case_id, task_type, description, status,
                created_by, created_at, closed_at, resolution_json)
               VALUES (?, ?, ?, ?, 'open', ?, ?, NULL, NULL)""",
            (task_id, case_id, task_type, description,
             actor.actor_id, _utc_now_iso()),
        )
        conn.commit()

        return {
            "task_id": task_id,
            "case_id": case_id,
            "task_type": task_type,
            "status": "open",
            "is_new": True,
        }
    finally:
        conn.close()
