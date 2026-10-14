"""English pages backed by scoped evidence, rules, investigations and actions."""
import json
import base64
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from agent.runner import investigate_case
from agent.configuration import provider_settings
from contracts import ActionType
from db import get_connection
from services.access import _is_authorized, query_shipment
from services.actions import propose_action, review_action, execute_action
from services.audit import export_audit
from services.handoff import compare_handoff
from services.photos import inspect_photo
from services.risk import get_partner_metrics
from services.workflow import process_evidence, submit_handoff


def context():
    return st.session_state.db_path, st.session_state.actor_context


def display_photo(path):
    """Inline validated evidence bytes so hosted iframe media routes cannot break images."""
    file = Path(path)
    if not file.exists():
        st.info("Photo file unavailable.")
        return
    mime = "image/png" if file.suffix.lower() == ".png" else "image/jpeg"
    encoded = base64.b64encode(file.read_bytes()).decode("ascii")
    st.html(f'<img src="data:{mime};base64,{encoded}" alt="Submitted shipment evidence" style="width:280px;max-width:100%;height:auto;border-radius:8px">')


def rows(sql, params=()):
    path, _ = context()
    conn = get_connection(path)
    try:
        cursor = conn.execute(sql, params)
        names = [d[0] for d in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def shipments():
    from contracts import ActorContext
    path, actor = context()
    conn = get_connection(path)
    try:
        now = datetime.now(timezone.utc).isoformat()
        return [sid for (sid,) in conn.execute("SELECT shipment_id FROM shipments ORDER BY shipment_id")
                if _is_authorized(conn, ActorContext(**actor), sid, now)[0]]
    finally:
        conn.close()


def select_shipment():
    options = shipments()
    if not options:
        st.info("No shipments assigned to your current role.")
        return None
    sid = st.selectbox("Shipment", options)
    path, actor = context()
    result = query_shipment(path, actor, sid)
    if not result["authorized"]:
        st.error(result["denied_reason"])
        return None
    return sid


def cases():
    allowed = set(shipments())
    return [case for case in rows("SELECT case_id, shipment_id, status, priority_score FROM case_records ORDER BY priority_score DESC")
            if case["shipment_id"] in allowed]


def select_case():
    options = cases()
    if not options:
        st.info("No cases yet. Submit or evaluate evidence in Handoff Verification.")
        return None
    return st.selectbox("Case", options, format_func=lambda c: f"{c['shipment_id']} · {c['priority_score']} points · {c['status']} · {c['case_id'][:8]}")


def partner_overview():
    path, actor = context()
    partners = rows("SELECT partner_id, name FROM partners")
    if actor["role"] == "partner_user":
        partners = [p for p in partners if p["partner_id"] == actor["partner_id"]]
    st.write("Monitor partners using shipment volume and evidence quality over the same reporting period.")
    st.caption("Evidence completeness measures handoff/POD event presence; unknown measurements and photos still require verification.")
    for partner in partners:
        metrics = get_partner_metrics(path, partner["partner_id"])
        with st.container(border=True):
            st.subheader(partner["name"])
            cols = st.columns(4)
            cols[0].metric("Shipment sample", metrics["sample_size"])
            cols[1].metric("Affected shipments / 1,000", f"{metrics['anomaly_rate_per_1000']:.1f}")
            cols[2].metric("Unresolved cases", metrics["open_cases"])
            cols[3].metric("Evidence completeness", f"{metrics['evidence_completeness_rate']:.1%}")
            st.caption(f"Unique affected shipments: {metrics['anomaly_count']}. Display threshold met: {metrics['meets_display_threshold']}. Sample size does not establish statistical reliability.")
            if metrics.get("period_start"):
                st.caption(f"Period: {metrics['period_start']} to {metrics.get('period_end') or 'present'}")
            else:
                st.caption("Reporting period: all recorded synthetic history.")
    st.subheader("Review queue")
    st.dataframe(cases(), use_container_width=True, hide_index=True)


def shipment_timeline():
    sid = select_shipment()
    if not sid:
        return
    for event in rows("SELECT * FROM events WHERE shipment_id=? ORDER BY occurred_at", (sid,)):
        with st.expander(f"{event['occurred_at']} · {event['event_type']}", expanded=True):
            st.caption(f"Evidence {event['event_id']} · source {event['source']} · received {event['received_at']}")
            st.json(json.loads(event["payload_json"]))
            for photo in rows("SELECT photo_id, local_path, sha256, phash, manual_observation FROM photos WHERE event_id=?", (event["event_id"],)):
                if Path(photo["local_path"]).exists():
                    display_photo(photo["local_path"])
                st.caption(f"{photo['photo_id']} · SHA-256 {photo['sha256']} · pHash {photo['phash']}")
                st.caption(photo["manual_observation"] or "No manual observation supplied.")


def access_monitoring():
    path, actor = context()
    st.write("Assignments apply before shipment details are returned. Approved batch jobs cannot bypass access controls.")
    with st.form("access_query"):
        sid = st.text_input("Shipment ID", "PV-DEMO-001")
        submit = st.form_submit_button("Check access and log request")
    if submit:
        result = query_shipment(path, actor, sid)
        if result["authorized"]:
            st.success("Access allowed and logged.")
            st.json(result["fields"])
        else:
            st.error("Access denied and logged. No shipment fields returned.")
            st.caption(result["denied_reason"])
    if actor["role"] == "partner_user":
        logs = rows("SELECT log_id, actor_id, shipment_id, action, outcome, occurred_at FROM access_logs WHERE actor_id=? ORDER BY occurred_at DESC LIMIT 100", (actor["actor_id"],))
    else:
        logs = rows("SELECT log_id, actor_id, shipment_id, action, outcome, occurred_at FROM access_logs ORDER BY occurred_at DESC LIMIT 100")
    st.dataframe(logs, use_container_width=True, hide_index=True)


def handoff_verification():
    sid = select_shipment()
    if not sid:
        return
    path, actor = context()
    comparison = compare_handoff(path, sid)
    st.subheader("Evidence comparison")
    st.dataframe([{"measurement": key, **comparison[key]} for key in ("count", "weight_g", "seal", "recipient")], hide_index=True, use_container_width=True)
    if comparison["unknowns"]:
        st.info("Unknown evidence: " + "; ".join(comparison["unknowns"]))
    events = rows("SELECT event_id, event_type, occurred_at FROM events WHERE shipment_id=? ORDER BY occurred_at", (sid,))
    event = st.selectbox("Evidence to evaluate", events, format_func=lambda e: f"{e['event_type']} · {e['occurred_at']}")
    if st.button("Evaluate evidence and create verification case"):
        st.json(process_evidence(path, actor, sid, event["event_id"]))
    for photo in rows("SELECT p.photo_id, p.local_path FROM photos p JOIN events e ON p.event_id=e.event_id WHERE e.shipment_id=?", (sid,)):
        with st.expander(f"Photo evidence · {photo['photo_id']}"):
            if Path(photo["local_path"]).exists():
                display_photo(photo["local_path"])
            st.json(inspect_photo(path, photo["photo_id"], actor))
            st.caption("Exact hashes establish file reuse. Perceptual hashes indicate similarity candidates. Neither establishes intent or package contents.")
    if actor["role"] == "approver":
        return
    st.subheader("Submit handoff evidence")
    with st.form("handoff"):
        event_type = st.selectbox("Event type", ["handoff_submitted", "pod_submitted", "collection_submitted", "warehouse_transfer", "transit_update"])
        count = st.number_input("Package count", min_value=0, value=100)
        weight = st.number_input("Weight (g)", min_value=0.0, value=1850.0)
        seal = st.text_input("Seal ID", "SEAL-07")
        occurred = st.text_input("Occurred at (UTC ISO 8601)", datetime.now(timezone.utc).isoformat())
        recipient = st.text_input("Recipient name (if available)")
        gps = st.text_input("GPS latitude,longitude (leave empty when unknown)")
        notes = st.text_area("Original evidence notes")
        upload = st.file_uploader("Photo (JPEG/PNG, up to 10 MB)", type=["jpg", "jpeg", "png"])
        submit = st.form_submit_button("Submit evidence")
    if submit:
        date = datetime.fromisoformat(occurred.replace("Z", "+00:00"))
        if date.tzinfo is None:
            raise ValueError("A UTC offset is required.")
        payload = {"count": count, "weight_g": weight, "seal_id": seal, "notes": notes}
        if recipient:
            payload["recipient_name"] = recipient
        if gps:
            latitude, longitude = [float(value.strip()) for value in gps.split(",")]
            if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
                raise ValueError("GPS coordinates are outside valid bounds.")
            payload.update({"lat": latitude, "lon": longitude, "gps_accuracy_m": 10})
        result = submit_handoff(path, actor, sid, event_type, payload, date.astimezone(timezone.utc).isoformat(), upload.getvalue() if upload else None)
        st.success("Evidence persisted. Review results below.")
        st.json(result)


def ai_request_token(case_id):
    # A generation-specific widget rejects queued clicks from the previous run.
    return st.session_state.setdefault('ai-generation-' + case_id, str(uuid.uuid4()))


def ai_failure_message(result):
    error = str(result.get('error') or '').lower()
    statuses={'authentication_failed':'Groq rejected the credentials or permissions. Check private configuration; manual review remains available.',
              'invalid_output':'AI returned an invalid result. No conclusion was saved; review the evidence manually.',
              'rate_limited':'Groq has reached a temporary usage limit. Review evidence manually or try later.',
              'usage_limited':'The demo AI usage limit is reached. Review evidence manually or try later.'}
    if result.get('status') in statuses:return statuses[result['status']]
    if result.get('status') == 'config_disabled':
        return 'AI is disabled by server configuration. Manual review remains available.'
    if result.get('status') in ('missing_config', 'missing_configuration'):
        return 'AI is unavailable because GROQ_API_KEY is missing. Manual review remains available.'
    if '429' in error or 'limit' in error or 'rate' in error:
        return 'AI has reached a temporary usage limit. Review evidence manually or try later.'
    if 'missing' in error and ('key' in error or 'credential' in error):
        return 'AI is unavailable because GROQ_API_KEY is missing. Manual review remains available.'
    if 'auth' in error or '401' in error or '403' in error:
        return 'AI credentials could not be validated. Manual review remains available.'
    if 'model' in error and ('unavailable' in error or 'not found' in error):
        return 'The configured Groq model is unavailable. Manual review remains available.'
    if 'timeout' in error or 'timed out' in error:
        return 'AI took too long to respond. Manual review remains available.'
    return 'AI could not complete this investigation. Manual review remains available.'


def run_case_ai(path, case_id, actor, token):
    result = investigate_case(path, case_id, actor, request_id=token)
    if result.get('status') != 'running':
        st.session_state['ai-generation-' + case_id] = str(uuid.uuid4())
    return result


def investigation():
    _, current_actor = context()
    if current_actor["role"] == "partner_user":
        st.info("Investigation reports and internal tool traces are available to internal reviewers.")
        return
    case = select_case()
    if not case:
        return
    path, actor = context()
    st.write("The model selects permitted read-only tools, examines source evidence and counter-evidence, then generates an English report. Every run is saved, including failures.")
    token = ai_request_token(case["case_id"])
    settings = provider_settings()
    configured = settings['configured'] and settings['enabled']
    if not configured:
        st.info('Groq AI is unavailable. Configure GROQ_API_KEY and AI_PROVIDER=groq in server settings. Manual review remains available.')
    if actor["role"] in ("admin", "investigator") and st.button("Run AI investigation", disabled=not configured, key='live-ai-' + case['case_id'] + '-' + token):
        with st.spinner("Investigating source evidence..."):
            result = run_case_ai(path, case["case_id"], actor, token)
        if result["status"] == "completed":
            st.success("Real model investigation saved.")
        else:
            st.warning(ai_failure_message(result))
    st.subheader("Saved runs")
    runs = rows("SELECT run_id, status, model_name, error, started_at, finished_at FROM investigation_runs WHERE case_id=? ORDER BY started_at DESC", (case["case_id"],))
    st.dataframe(runs, hide_index=True, use_container_width=True)
    if runs and runs[0].get("error"):
        st.caption("Latest run diagnostic: " + runs[0]["error"])
    st.subheader("Tool execution trace")
    trace = rows("SELECT run_id, tool_name, parameters_json, result_summary, evidence_ids_json, duration_ms FROM tool_executions WHERE case_id=? ORDER BY created_at", (case["case_id"],))
    st.dataframe(trace, hide_index=True, use_container_width=True)
    st.download_button("Export investigation trace", json.dumps({"runs": runs, "tools": trace}, indent=2), file_name="parcelverify-trace.json", mime="application/json")
    reports = rows("SELECT report_json, model_name, version FROM report_versions WHERE case_id=? ORDER BY version DESC", (case["case_id"],))
    if not reports:
        st.info("No completed AI report. Configure a running model through server secrets to investigate.")
    else:
        report = json.loads(reports[0]["report_json"])
        st.caption(f"Model: {reports[0]['model_name']} · version {reports[0]['version']}")
        st.json(report)
        st.download_button("Export English report", json.dumps(report, indent=2), file_name="parcelverify-report.json", mime="application/json")


def approvals():
    case = select_case()
    if not case:
        return
    path, actor = context()
    st.dataframe(rows("SELECT task_id, task_type, description, status FROM evidence_tasks WHERE case_id=?", (case["case_id"],)), hide_index=True)
    if actor["role"] in ("admin", "investigator"):
        with st.form("propose"):
            action_type = st.selectbox("Proposed response", [action.value for action in ActionType])
            reason = st.text_area("Evidence-based reason")
            if st.form_submit_button("Propose for human approval"):
                st.json(propose_action(path, case["case_id"], action_type, actor, reason=reason))
    for action in rows("SELECT action_id, action_type, status, reason FROM action_requests WHERE case_id=?", (case["case_id"],)):
        with st.container(border=True):
            st.write(f"**{action['action_type']}** · {action['status']}")
            st.caption(action["reason"] or "No reason supplied")
            if actor["role"] in ("admin", "approver"):
                if action["status"] == "proposed":
                    cols = st.columns(2)
                    if cols[0].button("Approve", key="approve"+action["action_id"]):
                        review_action(path, action["action_id"], "approve", actor)
                        st.rerun()
                    if cols[1].button("Reject", key="reject"+action["action_id"]):
                        review_action(path, action["action_id"], "reject", actor)
                        st.rerun()
                if action["status"] == "approved" and st.button("Execute simulated response", key="execute"+action["action_id"]):
                    result = execute_action(path, action["action_id"], actor)
                    st.json(result)
    audit = export_audit(path, case["case_id"], actor)
    st.subheader("Audit trail")
    st.json(audit)
    st.download_button("Export audit", json.dumps(audit, indent=2, default=str), file_name="parcelverify-audit.json", mime="application/json")


PAGES = {"Partner Overview": partner_overview, "Shipment Timeline": shipment_timeline,
         "Access Monitoring": access_monitoring, "Handoff Verification": handoff_verification,
         "AI Investigation": investigation, "Approvals & Audit": approvals}
