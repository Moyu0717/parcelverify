"""
ParcelVerify — Agent Tools
Owner: Role C (Investigation Agent)

Provides:
- dispatch_tool(): Validate tool name, params, case scope, and actor permissions
- 7 read-only tools for investigation (TOOL_WHITELIST)

Constraints (D-014):
- actor_context is always server-provided (from session), never from model
- All tool params validated: case scope, actor permissions
- Evidence IDs must exist in retrieved results
- No SQL, file paths, commands, URLs, or approval actions from model
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

from contracts import TOOL_WHITELIST, ActorContext, AuthorizationError
from db import get_connection
from services.access import check_access_scope, get_contract_at_time
from services.handoff import compare_handoff
from services.photos import find_photo_reuse
from services.risk import get_partner_metrics


def _validate_actor(actor_context: dict) -> ActorContext:
    return ActorContext(**actor_context)


def _get_case_shipment(conn: sqlite3.Connection, case_id: str) -> tuple[str, str]:
    """Return (shipment_id, partner_id) for a case."""
    row = conn.execute(
        """SELECT c.shipment_id, c.partner_id
           FROM case_records c
           WHERE c.case_id = ?""",
        (case_id,),
    ).fetchone()
    if not row:
        raise ValueError(f"Case {case_id} not found")
    return row[0], row[1]


def _get_vendor_context(
    conn: sqlite3.Connection, case_id: str, params: dict, actor: ActorContext, db_path: str
) -> dict:
    """Get vendor contract context (from contract_history if at_time)."""
    _, partner_id = _get_case_shipment(conn, case_id)
    at_time = params.get("at_time")

    if at_time:
        return get_contract_at_time(
            db_path=db_path,
            partner_id=partner_id,
            at_time=at_time,
        )

    # Return current contract info
    partner = conn.execute(
        "SELECT partner_id, name, status, contract_end, service_area, "
        "approved_scope, vendor_evidence_id FROM partners WHERE partner_id = ?",
        (partner_id,),
    ).fetchone()

    if not partner:
        return {"partner_id": partner_id, "contract": None}

    return {
        "partner_id": partner[0],
        "contract": {
            "name": partner[1],
            "status": partner[2],
            "contract_end": partner[3],
            "service_area": partner[4],
            "approved_scope": partner[5],
            "vendor_evidence_id": partner[6],
        },
    }


def _get_shipment_timeline(
    conn: sqlite3.Connection, case_id: str, params: dict, actor: ActorContext, db_path: str
) -> dict:
    """Get ordered events with sources."""
    shipment_id, _ = _get_case_shipment(conn, case_id)

    events = conn.execute(
        """SELECT event_id, event_type, occurred_at, received_at,
                  source, payload_json, is_synthetic
           FROM events
           WHERE shipment_id = ?
           ORDER BY occurred_at""",
        (shipment_id,),
    ).fetchall()

    return {
        "shipment_id": shipment_id,
        "events": [
            {
                "event_id": e[0],
                "photos": [dict(zip(("photo_id", "capture_method", "claimed_capture_at", "manual_observation"), p)) for p in conn.execute("SELECT photo_id, capture_method, claimed_capture_at, manual_observation FROM photos WHERE event_id = ?", (e[0],)).fetchall()],
                "event_type": e[1],
                "occurred_at": e[2],
                "received_at": e[3],
                "source": e[4],
                "payload": json.loads(e[5]) if e[5] else {},
                "is_synthetic": e[6],
            }
            for e in events
        ],
    }


def _compare_handoff(
    conn: sqlite3.Connection, case_id: str, params: dict, actor: ActorContext, db_path: str
) -> dict:
    """Compare count/weight/seal/recipient across handoff events."""
    shipment_id, _ = _get_case_shipment(conn, case_id)
    # We need db_path for compare_handoff; extract from connection
    # compare_handoff opens its own connection, so we pass the db path
    return compare_handoff(db_path, shipment_id)


def _find_photo_reuse(
    conn: sqlite3.Connection, case_id: str, params: dict, actor: ActorContext, db_path: str
) -> dict:
    """Find exact + similar photo matches (actor_context from session)."""
    photo_id = params.get("photo_id", "")
    if not photo_id:
        return {"error": "photo_id is required"}

    return find_photo_reuse(db_path, photo_id, actor.model_dump())


def _check_access_scope(
    conn: sqlite3.Connection, case_id: str, params: dict, actor: ActorContext, db_path: str
) -> dict:
    """Check access logs vs permissions."""
    return check_access_scope(db_path, case_id, actor.model_dump())


def _get_context_events(
    conn: sqlite3.Connection, case_id: str, params: dict, actor: ActorContext, db_path: str
) -> dict:
    """Get calibration, repackaging_approved, weather, etc. events."""
    shipment_id, _ = _get_case_shipment(conn, case_id)

    context_types = [
        "scale_calibration",
        "repackaging_approved",
        "route_exception",
        "approved_batch_job",
        "official_notice",
    ]

    events = conn.execute(
        """SELECT event_id, event_type, occurred_at, source, payload_json
           FROM events
           WHERE shipment_id = ? AND event_type IN ({})
           ORDER BY occurred_at""".format(
            ",".join("?" * len(context_types))
        ),
        (shipment_id, *context_types),
    ).fetchall()

    return {
        "shipment_id": shipment_id,
        "context_events": [
            {
                "event_id": e[0],
                "event_type": e[1],
                "occurred_at": e[2],
                "source": e[3],
                "payload": json.loads(e[4]) if e[4] else {},
            }
            for e in events
        ],
    }


def _get_partner_metrics(
    conn: sqlite3.Connection, case_id: str, params: dict, actor: ActorContext, db_path: str
) -> dict:
    """Get normalized metrics + sample size."""
    _, partner_id = _get_case_shipment(conn, case_id)
    return get_partner_metrics(db_path, partner_id)


# Tool dispatch table
_TOOL_DISPATCH = {
    "get_vendor_context": _get_vendor_context,
    "get_shipment_timeline": _get_shipment_timeline,
    "compare_handoff": _compare_handoff,
    "find_photo_reuse": _find_photo_reuse,
    "check_access_scope": _check_access_scope,
    "get_context_events": _get_context_events,
    "get_partner_metrics": _get_partner_metrics,
}


def authorize_case(conn, case_id, actor):
    shipment_id, partner_id = _get_case_shipment(conn, case_id)
    if actor.role not in ("admin", "investigator"):
        raise AuthorizationError("Only investigators and admins may investigate cases")
    if actor.partner_id and actor.partner_id != partner_id:
        raise AuthorizationError("Case is outside the actor's partner scope")
    return shipment_id, partner_id


def _evidence_ids(value):
    ids = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ("payload", "contract_snapshot"):
                continue
            if key in ("event_id", "photo_id", "log_id", "history_id", "vendor_evidence_id") and isinstance(item, str) and not item.startswith("[masked]"):
                ids.add(item)
            else:
                ids.update(_evidence_ids(item))
    elif isinstance(value, list):
        for item in value:
            ids.update(_evidence_ids(item))
    return ids


def dispatch_tool(db_path, tool_name, params, case_context, actor_context):
    start = time.monotonic()
    conn = None
    try:
        actor = _validate_actor(actor_context)
        conn = get_connection(db_path)
        case_id = case_context.get("case_id")
        if not case_id:
            raise ValueError("missing_case_id")
        shipment_id, partner_id = authorize_case(conn, case_id, actor)
        if tool_name not in TOOL_WHITELIST:
            raise ValueError(f"unknown_tool: {tool_name}")
        if not isinstance(params, dict):
            raise ValueError("Tool params must be an object")
        allowed = {"photo_id"} if tool_name == "find_photo_reuse" else ({"at_time"} if tool_name == "get_vendor_context" else set())
        if set(params) - allowed:
            raise ValueError("Unexpected tool parameters; scope is server controlled")
        if "at_time" in params:
            from datetime import datetime
            datetime.fromisoformat(params["at_time"].replace("Z", "+00:00"))
        if tool_name == "find_photo_reuse":
            photo_id = params.get("photo_id")
            if not isinstance(photo_id, str) or not conn.execute("SELECT 1 FROM photos p JOIN events e ON e.event_id=p.event_id WHERE p.photo_id=? AND e.shipment_id=?", (photo_id, shipment_id)).fetchone():
                raise ValueError("Photo does not belong to this case's shipment")
        result = _TOOL_DISPATCH[tool_name](conn, case_id, params, actor, db_path)
        if "error" in result:
            raise ValueError(str(result["error"]))
        evidence_ids = []
        for evidence_id in sorted(_evidence_ids(result)):
            # Payload fields are untrusted; only persisted identifiers are admissible.
            if any(conn.execute(f"SELECT 1 FROM {table} WHERE {column}=?", (evidence_id,)).fetchone()
                   for table, column in (("events", "event_id"), ("photos", "photo_id"),
                                         ("access_logs", "log_id"), ("contract_history", "history_id"))):
                evidence_ids.append(evidence_id)
        summary = f"Retrieved {tool_name}: {len(evidence_ids)} evidence references"
    except Exception as exc:
        result = {"error": str(exc)}
        evidence_ids = []
        summary = f"Error: {exc}"
    finally:
        if conn is not None:
            conn.close()
    return {"tool": tool_name, "params": params, "result_summary": summary,
            "evidence_ids": evidence_ids, "duration_ms": int((time.monotonic()-start)*1000), "result": result}
