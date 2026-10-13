"""Persisted submission and review pipeline used by the application."""
from contracts import RULE_VERSION
from db import get_connection, submit_event, upload_photo
from db import _validate_image, _MAX_PHOTO_BYTES
from services.access import query_shipment
from services.actions import create_evidence_task
from services.handoff import create_or_update_case, evaluate_handoff

def process_evidence(db_path, actor_context, shipment_id, event_id):
    access = query_shipment(db_path, actor_context, shipment_id)
    if not access["authorized"]:
        raise PermissionError(access["denied_reason"])
    with get_connection(db_path) as conn:
        event = conn.execute("SELECT shipment_id FROM events WHERE event_id=?", (event_id,)).fetchone()
    if not event or event[0] != shipment_id:
        raise ValueError("Evidence does not belong to this shipment")
    evaluation = evaluate_handoff(db_path, shipment_id, event_id, actor_context=actor_context)
    case = None
    if evaluation["findings"] or evaluation["missing_evidence"]:
        case = create_or_update_case(db_path, shipment_id, event_id, evaluation["findings"], RULE_VERSION)
        if evaluation["missing_evidence"]:
            system_actor = {"actor_id": "SYSTEM-VERIFICATION", "role": "investigator", "session_id": actor_context["session_id"]}
            create_evidence_task(db_path, case["case_id"], "supplementary_statement", system_actor,
                                 "; ".join(evaluation["missing_evidence"]))
    return {"evaluation": evaluation, "case": case}

def submit_handoff(db_path, actor_context, shipment_id, event_type, payload, occurred_at,
                   file_bytes=None, source="demo_form"):
    if file_bytes:
        if len(file_bytes) > _MAX_PHOTO_BYTES:
            raise ValueError("Photo exceeds the 10 MB limit")
        _validate_image(file_bytes)
    event = submit_event(db_path, actor_context, shipment_id, event_type, payload, source, occurred_at)
    photo = upload_photo(db_path, actor_context, event["event_id"], file_bytes) if file_bytes else None
    return {"event": event, "photo": photo, **process_evidence(db_path, actor_context, shipment_id, event["event_id"])}

def initialize_reviews(db_path, actor_context):
    with get_connection(db_path) as conn:
        if conn.execute("SELECT COUNT(*) FROM case_records").fetchone()[0]:
            return
        rows = conn.execute("SELECT shipment_id, event_id FROM events WHERE event_type='handoff_submitted'").fetchall()
    for shipment_id, event_id in rows:
        process_evidence(db_path, actor_context, shipment_id, event_id)
