"""Plain English and presentation shared by the operational workspace."""
from datetime import datetime
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

MYT = ZoneInfo("Asia/Kuala_Lumpur")
STATUS_LABELS = {"pending_review": "Needs review", "under_investigation": "Reviewing evidence",
    "review_completed": "Review complete", "action_proposed": "Awaiting approval", "action_approved": "Approved — ready to apply",
    "action_rejected": "Request rejected", "action_executed": "Action recorded", "action_failed": "Action needs attention",
    "closed": "Resolved", "proposed": "Awaiting approval", "approved": "Approved", "rejected": "Rejected",
    "executed": "Recorded", "failed": "Not completed", "open": "Waiting for information", "completed": "Complete"}
STAGES = {"dispatch_confirmed": "Prepared", "handoff_submitted": "Handed over", "pod_submitted": "Delivered",
    "collection_submitted": "Collected", "warehouse_transfer": "Warehouse transfer", "transit_update": "In transit",
    "recipient_authorization": "Recipient approved", "repackaging_approved": "Packaging change approved",
    "weight_measured": "Weight checked", "approved_batch_job": "Batch work approved", "scale_calibration": "Scale check"}
ACTION_LABELS = {"request_reweigh": "Confirm weight", "request_rephoto": "Request a photo", "request_rescan": "Check package count",
    "hold_handoff": "Pause handover", "hold_pod": "Pause delivery confirmation", "enhance_inspection": "Request closer inspection",
    "pause_high_value_assignment": "Pause high-value assignments", "restrict_account": "Restrict an account",
    "submit_to_contract_ops": "Request an explanation"}
MISSING_LABELS = {"actual_gps": "Delivery location is missing", "destination_gps": "Expected delivery location is missing",
    "recipient_authorization": "Recipient approval has not been confirmed", "pod_recipient": "Recipient name is missing",
    "handoff_count": "Package quantity is missing", "handoff_weight": "Handover weight is missing",
    "handoff_seal": "Seal information is missing", "per_item_scan": "Individual package scans are missing",
    "no_handoff_event": "Handover measurements have not been recorded"}

def apply_theme():
    st.html("<style>" + Path(__file__).with_name("theme.css").read_text(encoding="utf-8") + "</style>")

def humanize(value):
    return str(value).replace("_", " ").capitalize() if value else "Not provided"

def status_label(value):
    return STATUS_LABELS.get(value, humanize(value))

def stage_label(value):
    return STAGES.get(value, humanize(value))

def format_time(value):
    if not value:
        return "Time not recorded"
    try:
        date = datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(MYT)
        return f"{date.day} {date:%b %Y}, {date:%I:%M}".replace(", 0", ", ") + f" {date:%p}".lower() + " MYT"
    except ValueError:
        return "Time not confirmed"

def format_weight(value):
    return f"{float(value)/1000:.2f} kg" if value is not None else "Missing"

def difference_weight(value):
    if value is None:
        return "Not checked"
    if value == 0:
        return "No difference"
    return f"{abs(value):g} g {'lower' if value < 0 else 'higher'}"

def status_badge(label, tone="neutral"):
    if tone not in ("neutral", "warning", "success", "danger"):
        tone = "neutral"
    st.html(f'<span class="pv-badge pv-badge-{tone}">{escape(label)}</span>')

def issue_label(findings, comparison=None, missing=None):
    categories = {f.get("category") for f in findings or []}
    if "access_anomaly" in categories:
        return "Access outside the recorded assignment"
    if "weight_diff" in categories:
        diff = (comparison or {}).get("weight_g", {}).get("diff")
        return "Recorded weight is " + difference_weight(diff) if diff is not None else "Recorded weight needs checking"
    if "count_discrepancy" in categories:
        return "Package quantity changed"
    if "photo_reuse" in categories:
        return "A photo file was reused"
    if "seal_mismatch" in categories or "id_conflict" in categories:
        return "The recorded seal is different"
    if "recipient_conflict" in categories:
        return "Recipient confirmation needs checking"
    if "location_conflict" in categories:
        return "Recorded delivery location needs checking"
    if "time_conflict" in categories:
        return "The recorded timing needs checking"
    return "More information is needed" if missing else "Evidence review"
