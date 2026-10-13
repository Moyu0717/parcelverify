"""A focused case-review workspace using persisted, authorized business services."""
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from html import escape
from pathlib import Path

import streamlit as st
from agent.runner import investigate_case
from services.access import query_shipment, check_access_scope
from services.actions import propose_action, review_action, execute_action, create_evidence_task
from services.audit import export_audit
from services.handoff import compare_handoff
from services.review import list_review_cases, review_counts, record_review_decision
from services.risk import get_partner_metrics
from services.workflow import submit_handoff
from ui.live import context, rows, shipments, display_photo
from ui.presentation import (MYT, ACTION_LABELS, MISSING_LABELS, format_time, format_weight,
    difference_weight, status_label, stage_label, status_badge, issue_label, humanize)

FILTERS = {"Needs review":"needs_review", "Waiting for approval":"awaiting_approval", "Resolved":"resolved", "Review complete":"review_complete", "All":"all"}
TYPES = {"All":"all", "Shipment checks":"shipment", "Data access":"access"}

def remember_draft(key):
    st.session_state.setdefault("drafts",{})[key]=st.session_state[key]

def cancel_request(case_id,cancelled=True):
    st.session_state.setdefault("cancelled_requests",{})[case_id]=cancelled

def draft_input(kind,label,scope,field,**kwargs):
    key="draft-"+scope+"-"+field
    saved=st.session_state.setdefault("drafts",{}).get(key,kwargs.pop("value",""))
    return getattr(st,kind)(label,value=saved,key=key,on_change=remember_draft,args=(key,),**kwargs)

def cases():
    return list_review_cases(*context())

def route(destination="Issues", case_id=None, shipment_id=None, bucket=None, partner=None):
    st.session_state.route_pending = destination
    st.session_state.secondary_view = None
    st.session_state.selected_case_id = case_id
    st.session_state.selected_shipment_id = shipment_id
    if bucket:
        st.session_state.filter_bucket = bucket
    if partner is not None:
        st.session_state.filter_partner = partner

def back():
    st.session_state.selected_case_id = None
    st.session_state.selected_shipment_id = None

def notice(text, kind="success"):
    st.session_state.notice = (kind,text)

def label(case):
    if case["work_bucket"]=="resolved": return "Resolved"
    if case["has_proposed_actions"]: return "Waiting for approval"
    if case["has_approved_actions"]: return "Ready to apply"
    if case["has_open_tasks"] and case["status"]=="review_completed": return "More information needed"
    return status_label(case["status"])

def concern(case):
    comparison=compare_handoff(context()[0],case["shipment_id"]) if any(f["category"]=="weight_diff" for f in case["findings"]) else None
    return issue_label(case["findings"],comparison,["pending"] if case["has_open_tasks"] else [])

def case_row(case, updated=False):
    with st.container(border=True,key="pv-case-"+case["case_id"]):
        body,action=st.columns([6,1.2],vertical_alignment="center")
        with body:
            text='<div class="pv-case-row"><strong>'+escape(case["shipment_id"])+'</strong><span>'+escape(case["partner_name"] or "Partner")+'</span><span>'+escape(concern(case))+'</span><span class="pv-badge pv-badge-'+("success" if case["work_bucket"]=="resolved" else "warning")+'">'+escape(label(case))+'</span>'
            if updated: text+='<small>Updated '+escape(format_time(case["updated_at"]))+'</small>'
            st.html(text+'</div>')
        action.button("Review case",key="open-"+case["case_id"],use_container_width=True,on_click=route,kwargs={"case_id":case["case_id"]})

def search(query):
    query=query.strip()
    if not query:
        notice("Enter a shipment or case reference.","info"); return
    available=cases()
    matched=next((c for c in available if query.lower() in (c["case_id"].lower(),("case-"+c["case_id"][:6]).lower())),None)
    if matched:
        route(case_id=matched["case_id"]); return
    shipment=next((sid for sid in shipments() if sid.lower()==query.lower()),None)
    if shipment:
        related=[c for c in available if c["shipment_id"]==shipment and c["work_bucket"]!="resolved"]
        related.sort(key=lambda c:c["priority_score"] or 0,reverse=True)
        route(case_id=related[0]["case_id"] if related else None,shipment_id=shipment if not related else None); return
    if query.upper().startswith("PV-"):
        result=query_shipment(context()[0],context()[1],query.upper())
        if not result["authorized"]:
            notice("No permitted shipment or case was found. The access check was recorded.","warning"); return
    st.session_state.case_search=query
    route(bucket="all")

def overview():
    cohort=cases(); counts=review_counts(cohort)
    st.title("Your review overview")
    st.caption("All recorded demo activity, using the same authorized cases throughout.")
    columns=st.columns(3)
    for column,name,bucket in zip(columns,("Needs review","Awaiting approval","Resolved"),("needs_review","awaiting_approval","resolved")):
        with column,st.container(border=True,key="pv-counter-"+bucket):
            st.metric(name,counts[bucket])
            st.button("View "+name.lower(),key="counter-"+bucket,use_container_width=True,on_click=route,kwargs={"bucket":bucket})
    st.subheader("Needs your attention")
    queue=[c for c in cohort if c["work_bucket"] in ("needs_review","awaiting_approval")]
    queue.sort(key=lambda c:c["priority_score"] or 0,reverse=True)
    if not queue:
        st.success("You're all caught up"); st.caption("Find a shipment or case to view another record.")
    for case in queue[:5]: case_row(case)
    if len(queue)>5:
        st.button("View all open cases",on_click=route,kwargs={"bucket":"needs_review"})

def save_filter(widget,target,mapping=None):
    value=st.session_state[widget]
    st.session_state[target]=mapping[value] if mapping else value
    st.session_state.case_page=0

def render_cases():
    cohort=cases(); selected=st.session_state.get("selected_case_id")
    if selected:
        case=next((c for c in cohort if c["case_id"]==selected),None)
        if case: detail(case)
        else:
            st.warning("This case is not available to your current role."); st.button("Back to cases",on_click=back)
        return
    if st.session_state.get("selected_shipment_id"):
        shipment_detail(st.session_state.selected_shipment_id); return
    st.title("Cases"); st.caption("Review the concern, check its evidence and record the next step.")
    query=st.text_input("Find a shipment or case",value=st.session_state.get("case_search",""),key="case_query",placeholder="Shipment, partner or issue",on_change=save_filter,args=("case_query","case_search"))
    columns=st.columns(3)
    bucket=st.session_state.get("filter_bucket","needs_review")
    with columns[0]:
        st.selectbox("Status",list(FILTERS),index=list(FILTERS.values()).index(bucket),key="status_widget",on_change=save_filter,args=("status_widget","filter_bucket",FILTERS))
    with columns[1]:
        st.selectbox("Issue type",list(TYPES),index=list(TYPES.values()).index(st.session_state.get("filter_issue","all")),key="issue_widget",on_change=save_filter,args=("issue_widget","filter_issue",TYPES))
    partners={c["partner_id"]:c["partner_name"] for c in cohort}; options=["All partners",*partners.values()]
    with columns[2]:
        selected_partner=st.selectbox("Partner",options,index=options.index(partners.get(st.session_state.get("filter_partner"),"All partners")),key="partner_widget",on_change=save_filter,args=("partner_widget","filter_partner_name"))
    st.session_state.filter_partner=next((pid for pid,name in partners.items() if name==selected_partner),"")
    filtered=[c for c in cohort if (bucket=="all" or c["work_bucket"]==bucket) and (st.session_state.get("filter_issue","all")=="all" or c["issue_type"]==st.session_state.filter_issue)
        and (not st.session_state.filter_partner or c["partner_id"]==st.session_state.filter_partner)
        and (not query or query.lower() in " ".join((c["shipment_id"],c["partner_name"] or "",concern(c),"case-"+c["case_id"][:6])).lower())]
    filtered.sort(key=lambda c:c["priority_score"] or 0,reverse=True)
    if not filtered:
        st.info("No cases match. Try All, or find a shipment from the navigation."); return
    page=min(st.session_state.get("case_page",0),(len(filtered)-1)//8)
    st.caption(f"Showing {page*8+1}–{min(page*8+8,len(filtered))} of {len(filtered)} cases")
    st.html('<div class="pv-list-heading">Shipment · Partner · Issue · Status · Updated</div>')
    for case in filtered[page*8:page*8+8]: case_row(case,True)
    previous,next_column,_=st.columns([1,1,4])
    if previous.button("Previous",disabled=page==0): st.session_state.case_page=page-1; st.rerun()
    if next_column.button("Next",disabled=(page+1)*8>=len(filtered)): st.session_state.case_page=page+1; st.rerun()

def events(shipment):
    return rows("SELECT event_id,event_type,occurred_at,received_at,source,payload_json FROM events WHERE shipment_id=? ORDER BY occurred_at",(shipment,))

def comparison(shipment):
    value=compare_handoff(context()[0],shipment)
    check=lambda result:"Missing" if result is None else "Matches" if result else "Different"
    weight=value["weight_g"]; missing=value["unknowns"]
    data=[("Quantity",value["count"]["expected"],value["count"]["actual"],check(value["count"]["match"])),
        ("Weight",format_weight(weight["expected"]),format_weight(weight["actual"]),check(weight["match"])+(": "+difference_weight(weight["diff"]) if weight["diff"] else "")),
        ("Seal",value["seal"]["expected"],value["seal"]["actual"],check(value["seal"]["match"])),
        ("Location","Expected destination" if "destination_gps" not in missing else None,"Not recorded" if "actual_gps" in missing else "Location recorded","Missing" if "actual_gps" in missing else "Different" if value.get("location_conflict") else "Not checked"),
        ("Recipient confirmation",value["recipient"]["expected"],value["recipient"]["actual"],check(value["recipient"]["authorized"]))]
    st.html('<div class="pv-compare pv-compare-head"><span>Check</span><span>Before</span><span>At handover / delivery</span><span>Result</span></div>')
    for name,before,after,result in data:
        st.html('<div class="pv-compare"><strong>'+escape(name)+'</strong><span><small>Before</small>'+escape(str(before) if before is not None else "Missing")+'</span><span><small>At handover / delivery</small>'+escape(str(after) if after is not None else "Missing")+'</span><span>'+escape(result)+'</span></div>')
    return value

@st.dialog("Evidence photo",width="large")
def enlarge(photo):
    import base64
    file=Path(photo["local_path"])
    mime="image/png" if file.suffix.lower()==".png" else "image/jpeg"
    if file.exists(): st.html('<img alt="Demonstration shipment evidence" style="width:100%;height:auto" src="data:'+mime+';base64,'+base64.b64encode(file.read_bytes()).decode()+'">')
    else: st.info("Photo unavailable.")
    st.caption("Demonstration image · "+stage_label(photo["event_type"])+" · "+format_time(photo["occurred_at"]))

def shipment_evidence(shipment):
    st.subheader("Shipment checks"); comparison(shipment)
    source=events(shipment)
    for event in [e for e in source if e["event_type"]=="repackaging_approved"]:
        payload=json.loads(event["payload_json"])
        st.info("An approved packaging change is recorded. Consider its supporting weight checks.")
        with st.expander("Approved packaging change"):
            st.write(payload.get("reason","No explanation was recorded."))
            for measure in [e for e in source if e["event_id"] in payload.get("supporting_measurement_ids",[])]:
                st.write("Weight check: "+format_weight(json.loads(measure["payload_json"]).get("weight_g")))
    st.subheader("Shipment journey")
    journey=[e for e in source if e["event_type"] in ("dispatch_confirmed","handoff_submitted","pod_submitted","collection_submitted","warehouse_transfer","transit_update")]
    st.html('<div class="pv-journey">'+''.join('<div class="pv-stop"><strong>'+escape(stage_label(e["event_type"]))+'</strong><small>'+escape(format_time(e["occurred_at"]))+'</small></div>' for e in journey)+'</div>')
    st.subheader("Photos")
    images=rows("SELECT p.*,e.event_type,e.occurred_at FROM photos p JOIN events e ON p.event_id=e.event_id WHERE e.shipment_id=? ORDER BY e.occurred_at",(shipment,))
    if not images: st.info("No photo has been provided. You can add one or request a photo.")
    for start in range(0,len(images),3):
        for column,photo in zip(st.columns(3),images[start:start+3]):
            with column:
                display_photo(photo["local_path"])
                st.caption("Demonstration image · "+stage_label(photo["event_type"]))
                st.caption(format_time(photo["occurred_at"]))
                if st.button("Enlarge photo",key="enlarge-"+photo["photo_id"],icon=":material/zoom_in:"): enlarge(photo)
    with st.expander("Source records"):
        for index,event in enumerate(source,1):
            st.write(f"**Evidence {index}: {stage_label(event['event_type'])}**")
            st.caption(format_time(event["occurred_at"])+" · "+humanize(event["source"]))
            payload=json.loads(event["payload_json"])
            if payload.get("notes"): st.write(payload["notes"])
            if context()[1]["role"]!="partner_user":
                with st.expander("Technical source details"):
                    st.caption("Source ID: "+event["event_id"]); st.json(payload)

def access_evidence(case):
    scope=check_access_scope(context()[0],case["case_id"],context()[1])
    st.subheader("Data access")
    st.caption("Check the request against the assignment and approved work. A denied request does not establish intent.")
    references={identifier for finding in case["findings"] for identifier in finding.get("evidence_ids",[])}
    relevant=[log for log in scope["access_logs"] if log["log_id"] in references]
    for log in relevant:
        with st.container(border=True):
            st.write("**"+log["shipment_id"]+"** · requested by "+log["actor_id"])
            status_badge("Access allowed" if log["outcome"]=="authorized" else "Access denied","warning")
            st.caption(format_time(log["occurred_at"]))
            st.write("The request was outside the recorded assignment. Check whether a legitimate job explains it.")
    with st.expander("Assignment and approved-work context"):
        for assignment in rows("SELECT actor_id,valid_from,valid_until FROM assignments WHERE shipment_id=?",(case["shipment_id"],)):
            st.write(assignment["actor_id"]+" · assigned from "+format_time(assignment["valid_from"]))
        batches=[e for e in events(case["shipment_id"]) if e["event_type"]=="approved_batch_job"]
        if not batches: st.caption("No shipment-specific approved batch work is recorded. Missing context is not proof of wrongdoing.")
        for event in batches: st.write("Approved batch work recorded · "+format_time(event["occurred_at"]))

def ai_summary(case):
    path,actor=context()
    if actor["role"]=="partner_user":
        st.caption("AI summaries are available to internal reviewers. You can still view the shipment evidence."); return
    reports=rows("SELECT * FROM report_versions WHERE case_id=? ORDER BY version DESC",(case["case_id"],))
    runs=rows("SELECT run_id,status,error,model_name,started_at FROM investigation_runs WHERE case_id=? ORDER BY started_at DESC",(case["case_id"],))
    report=json.loads(reports[0]["report_json"]) if reports else None
    if not report: st.info("AI explanation is unavailable. You can still review the evidence.")
    else:
        if rows("SELECT event_id FROM events WHERE shipment_id=? AND julianday(received_at)>julianday(?)",(case["shipment_id"],reports[0]["created_at"])):
            st.warning("New evidence has been added since this summary. Review it manually or request an updated summary.")
        st.markdown("**What we found**"); st.write(report["summary"])
        source={e["event_id"]:index+1 for index,e in enumerate(events(case["shipment_id"]))}
        for fact in report["facts"]:
            st.write(fact["text"])
            if fact["evidence_ids"]:
                with st.expander("Supporting evidence"):
                    for identifier in fact["evidence_ids"]:
                        st.write("Evidence "+str(source[identifier])+" in Source records" if identifier in source else "Photo or access evidence shown above")
        st.markdown("**What is missing**")
        for item in report["missing_evidence"]: st.write("• "+item)
        if not report["missing_evidence"]: st.caption("No further gaps were listed by this review.")
        if report.get("alternative_explanations"):
            with st.expander("Other explanations to consider"):
                for item in report["alternative_explanations"]: st.write(item)
        st.markdown("**Suggested next step**"); st.write(ACTION_LABELS.get(report["recommended_action"],report["recommended_action"]))
    configured=bool(os.environ.get("GEMINI_API_KEY")) if os.environ.get("PV_AI_PROVIDER","gemini")=="gemini" else True
    if actor["role"] in ("admin","investigator") and st.button("Retry AI explanation" if runs and not report else "Explain this issue with AI",disabled=not configured,key="ai-"+case["case_id"]):
        with st.spinner("Reviewing the recorded evidence..."): result=investigate_case(path,case["case_id"],actor)
        notice("AI explanation saved. Review it before deciding." if result["status"]=="completed" else "AI explanation is unavailable. You can still review the evidence.","success" if result["status"]=="completed" else "info"); st.rerun()
    st.caption("Flags need review. They do not prove wrongdoing.")
    with st.expander("Technical details"):
        if reports: st.caption("Provider model: "+str(reports[0]["model_name"]))
        if actor["role"]=="admin" and runs and runs[0].get("error"): st.code(runs[0]["error"])
        trace=rows("SELECT tool_name,result_summary,evidence_ids_json FROM tool_executions WHERE case_id=?",(case["case_id"],))
        visible_runs=runs if actor["role"]=="admin" else [{key:value for key,value in run.items() if key!="error"} for run in runs]
        st.json({"runs":visible_runs,"tools":trace})
        st.download_button("Download technical review record",json.dumps({"runs":visible_runs,"tools":trace},indent=2),file_name="parcelverify-review-record.json")

def next_step(case):
    path,actor=context()
    st.subheader("Choose what happens next")
    if case["status"]=="closed":
        st.success("This issue is resolved. Evidence and decisions remain available."); return
    actions=rows("SELECT action_id,action_type,status,reason FROM action_requests WHERE case_id=? ORDER BY rowid DESC",(case["case_id"],))
    active=[a for a in actions if a["status"] in ("proposed","approved")]
    for index,action in enumerate(active):
        with st.container(border=True):
            st.write("**"+ACTION_LABELS.get(action["action_type"],humanize(action["action_type"]))+"**")
            status_badge(status_label(action["status"]),"warning")
            st.write(action["reason"] or "No reason was provided.")
            st.caption("Reviewer: authorized supervisor. Approval and applying the step are separate.")
            st.caption("Demo only — no message will be sent")
            if actor["role"] in ("admin","approver"):
                if action["status"]=="proposed":
                    confirmed=st.checkbox("I reviewed this request and its evidence.",key="confirm-"+action["action_id"])
                    approve,reject=st.columns(2)
                    if approve.button("Approve request",type="primary" if index==0 else "secondary",disabled=not confirmed,key="approve-"+action["action_id"]):
                        review_action(path,action["action_id"],"approve",actor,"Evidence and proposed verification reviewed.")
                        notice("Request approved. It has not been applied yet."); st.rerun()
                    if reject.button("Reject request",disabled=not confirmed,key="reject-"+action["action_id"]):
                        review_action(path,action["action_id"],"reject",actor,"Request rejected after evidence review.")
                        notice("Request rejected. It cannot be applied."); st.rerun()
                    with st.expander("Ask for more information before deciding"):
                        clarification=st.text_area("What information is needed?",key="clarification-"+action["action_id"])
                        st.caption("Creates a local information task. This proposal stays waiting for approval; no message is sent.")
                        if st.button("Record information request",key="clarify-"+action["action_id"]):
                            if len(clarification.strip())<10:st.error("Describe the missing information in at least 10 characters.")
                            else:
                                create_evidence_task(path,case["case_id"],"supplementary_statement",actor,clarification.strip())
                                notice("Information task recorded. The proposal still needs a decision.");st.rerun()
                elif st.button("Apply approved step",type="primary" if index==0 else "secondary",key="apply-"+action["action_id"]):
                    result=execute_action(path,action["action_id"],actor)
                    good=result["status"] in ("executed","already_executed")
                    notice("Approved step applied. A local evidence task was created; no message was sent." if good and action["action_type"] in ("request_reweigh","request_rephoto","request_rescan") else "Approved step recorded in this demo; no external operation was performed." if good else "This step was not applied. Review the request or ask a supervisor.","success" if good else "error"); st.rerun()
            else: st.caption("An authorized supervisor must review and apply this request.")
    if actor["role"] in ("admin","investigator") and not active:
        if st.session_state.get("cancelled_requests",{}).get(case["case_id"]):
            st.caption("Request cancelled. Your draft is kept; nothing was submitted.")
            st.button("Prepare a request",on_click=cancel_request,args=(case["case_id"],False))
            return
        categories={f["category"] for f in case["findings"]}
        values=compare_handoff(path,case["shipment_id"])
        choices=[]
        if case["issue_type"]=="shipment":
            if "weight_diff" in categories or values["weight_g"]["actual"] is None: choices.append("request_reweigh")
            if "photo_reuse" in categories or not rows("SELECT p.photo_id FROM photos p JOIN events e ON p.event_id=e.event_id WHERE e.shipment_id=?",(case["shipment_id"],)): choices.append("request_rephoto")
            if "count_discrepancy" in categories or values["count"]["actual"] is None: choices.append("request_rescan")
        choices.append("submit_to_contract_ops")
        with st.container():
            with st.expander("Other actions"):
                action_type=st.selectbox("Requested step",choices,format_func=lambda action:ACTION_LABELS[action],key="step-choice-"+case["case_id"])
            st.markdown("**"+ACTION_LABELS[action_type]+"**")
            descriptions={"request_reweigh":"Ask for a fresh weighing of this parcel. A supporting photo can be added as evidence.","request_rephoto":"Ask for an additional parcel photo to check the recorded evidence.","request_rescan":"Ask for a new package scan to check the recorded quantity.","submit_to_contract_ops":"Record a referral for an operations review of the issue. This demo does not route the referral to another system."}
            st.write(descriptions[action_type])
            initial="The handover weight is "+difference_weight(values["weight_g"]["diff"])+" than the dispatch record." if action_type=="request_reweigh" and values["weight_g"]["diff"] else concern(case)+". Please review the source evidence."
            reason=draft_input("text_area","Reason for the request",case["case_id"],"request-reason",value=initial,max_chars=2000)
            st.caption("Shipment: "+case["shipment_id"])
            st.caption("Reviewer: authorized supervisor (no named reviewer assigned).")
            st.caption("Intended partner: "+(case["partner_name"] or "Unassigned")+". Delivery contact is not configured.")
            st.caption("Next state: Waiting for approval. After approval, applying a verification request creates a local evidence task.")
            st.caption("Demo only — no message will be sent")
            submitted=st.button("Send request for approval",type="primary",use_container_width=True,key="submit-step-"+case["case_id"])
            st.button("Cancel request",type="tertiary",key="cancel-"+case["case_id"],on_click=cancel_request,args=(case["case_id"],))
        if submitted:
            if len(reason.strip())<10: st.error("Add a short reason of at least 10 characters. Your draft has been kept.")
            else:
                fingerprint=hashlib.sha256(json.dumps([case["case_id"],actor["actor_id"],action_type,reason.strip()]).encode()).hexdigest()
                request_id=st.session_state.setdefault("proposal_ids",{}).setdefault(fingerprint,str(uuid.uuid4()))
                result=propose_action(path,case["case_id"],action_type,actor,reason=reason.strip(),request_id=request_id)
                notice("Request submitted. Waiting for supervisor approval." if result["status"]=="proposed" else "This request already has a recorded decision. Change the next step or reason to submit another request."); st.rerun()
    elif actor["role"]=="partner_user": st.caption("An internal reviewer can request the next verification step.")
    if actor["role"] in ("admin","investigator","approver"):
        with st.expander("Record a review decision"):
            with st.form("decision-"+case["case_id"]):
                decisions=["review_complete"]+(["close"] if actor["role"] in ("admin","approver") else [])
                decision=st.selectbox("Decision",decisions,format_func=lambda value:"Record review complete" if value=="review_complete" else "Close issue")
                reason=st.text_area("Decision reason",max_chars=3000)
                st.caption("Shipment: "+case["shipment_id"]+". Review complete leaves open requests active. Close issue manually closes remaining evidence tasks without verifying them.")
                confirmed=st.checkbox("I reviewed the evidence and this decision. Closing records a manual disposition of open information requests.")
                save=st.form_submit_button("Record decision")
            if save:
                if not confirmed:
                    st.error("Confirm that you reviewed the evidence and decision before recording it.")
                    return
                try:
                    result=record_review_decision(path,case["case_id"],actor,decision,reason)
                    notice("Issue resolved and decision recorded." if result["status"]=="closed" else "Review recorded. Open evidence requests remain available."); st.rerun()
                except ValueError as error: st.error(str(error))

def case_summary(case):
    value=compare_handoff(context()[0],case["shipment_id"])
    text=["# ParcelVerify issue summary","", "Shipment: "+case["shipment_id"],"Partner: "+(case["partner_name"] or "Not recorded"),"Status: "+label(case),"Updated: "+format_time(case["updated_at"]),"","## What needs checking",concern(case),"","## Recorded evidence"]
    if case["issue_type"]=="shipment":
        text.extend(["Quantity: "+str(value["count"]["expected"])+" before; "+str(value["count"]["actual"])+" at handover.","Weight: "+format_weight(value["weight_g"]["expected"])+" before; "+format_weight(value["weight_g"]["actual"])+" at handover.","Difference: "+difference_weight(value["weight_g"]["diff"])+".","","## Missing information",*("- "+MISSING_LABELS.get(key,humanize(key)) for key in value["unknowns"])])
    else: text.append("An access request was denied outside the recorded assignment. Legitimate job context still requires review.")
    audit=export_audit(context()[0],case["case_id"],context()[1])
    text.extend(["","## Recorded decisions"])
    for event in audit["events"]:
        text.append("- "+format_time(event["occurred_at"])+": "+humanize(event["operation"])+(" — "+event["details"]["reason"] if event["details"].get("reason") else ""))
    text.extend(["","Flags need review. They do not prove wrongdoing.","Operational actions are simulated in this demo."])
    return "\n".join(text).replace("None","Missing")

def activity(case):
    with st.expander("Activity"):
        audit=export_audit(context()[0],case["case_id"],context()[1])
        if not audit["events"]: st.caption("No decisions have been recorded yet.")
        for event in audit["events"]:
            st.write("**"+humanize(event["operation"])+"** · "+format_time(event["occurred_at"]))
            if event["details"].get("reason"): st.write(event["details"]["reason"])
        for action in rows("SELECT action_type,status FROM action_requests WHERE case_id=?",(case["case_id"],)):
            st.write(ACTION_LABELS.get(action["action_type"],humanize(action["action_type"]))+" · "+status_label(action["status"]))
        st.download_button("Download issue summary",case_summary(case),file_name=case["shipment_id"]+"-issue-summary.md",mime="text/markdown")
        if context()[1]["role"]!="partner_user":
            with st.expander("Audit details"):
                st.json(audit)
                st.download_button("Download audit record",json.dumps(audit,indent=2),file_name="parcelverify-audit.json")

def add_evidence(shipment):
    path,actor=context()
    if actor["role"]=="approver": return
    with st.expander("Add evidence"):
        stages=["handoff_submitted","pod_submitted","dispatch_confirmed","collection_submitted","warehouse_transfer","transit_update"]
        stage=st.selectbox("Recorded stage",stages,format_func=stage_label,key="stage-"+shipment)
        with st.container():
            if stage!="pod_submitted":
                quantity=draft_input("text_input","Quantity (packages)",shipment,"quantity",placeholder="Leave empty if not recorded")
                weight=draft_input("text_input","Weight (kg)",shipment,"weight",placeholder="For example, 1.85")
                seal=draft_input("text_input","Seal reference",shipment,"seal",max_chars=120)
                recipient=""
            else:
                quantity=weight=seal=""
                recipient=draft_input("text_input","Recipient name",shipment,"recipient",max_chars=120)
            now=datetime.now(timezone.utc).astimezone(MYT)
            col1,col2=st.columns(2)
            date=col1.date_input("Recorded date (MYT)",now.date())
            time=col2.time_input("Recorded time (MYT)",now.time().replace(second=0,microsecond=0))
            note=draft_input("text_area","Supporting note",shipment,"note",max_chars=4000)
            photo=st.file_uploader("Attach a photo",type=["jpg","jpeg","png"],help="JPEG or PNG, up to 10 MB.")
            st.caption("Check these facts before saving. Missing measurements will stay unconfirmed.")
            save=st.button("Save evidence",type="primary",key="save-evidence-"+shipment)
        if save:
            try:
                payload={"notes":note}
                if quantity:
                    if not quantity.isdigit(): raise ValueError("Quantity must be a whole number of packages.")
                    payload["count"]=int(quantity)
                if weight:
                    measured=Decimal(weight)
                    if not measured.is_finite() or measured<0: raise ValueError("Weight must be a valid non-negative number in kilograms.")
                    payload["weight_g"]=float(measured*1000)
                if seal.strip(): payload["seal_id"]=seal.strip()
                if recipient.strip(): payload["recipient_name"]=recipient.strip()
                occurred=datetime.combine(date,time,tzinfo=MYT).astimezone(timezone.utc).isoformat()
                result=submit_handoff(path,actor,shipment,stage,payload,occurred,photo.getvalue() if photo else None,source="manual_evidence")
                notice("Evidence saved and checked." if result["event"]["is_new"] else "This evidence was already saved. No duplicate was added.")
                if result["case"]: route(case_id=result["case"]["case_id"])
                st.rerun()
            except (ValueError,InvalidOperation) as error:
                st.error("Evidence was not saved: "+str(error)+" Your draft has been kept.")

def detail(case):
    st.button("Back to issues",icon=":material/arrow_back:",on_click=back)
    st.title(case["shipment_id"])
    st.caption((case["partner_name"] or "Partner")+" · updated "+format_time(case["updated_at"]))
    status_badge(label(case),"success" if case["work_bucket"]=="resolved" else "warning")
    st.write(concern(case)+".")
    summary,evidence=st.tabs(["Summary","Evidence"])
    with summary:
        st.html('<div class="pv-summary">'+escape(concern(case))+'. Review the supporting records before choosing the next step.</div>')
        if case["issue_type"]=="shipment":
            value=compare_handoff(context()[0],case["shipment_id"])
            missing=[MISSING_LABELS.get(key,humanize(key)) for key in value["unknowns"]]
            if missing: st.caption("Still to confirm: "+"; ".join(missing[:3])+".")
        with st.expander("AI summary"): ai_summary(case)
        next_step(case)
    with evidence:
        if case["issue_type"]=="access":
            access_evidence(case)
            with st.expander("Related shipment record"): shipment_evidence(case["shipment_id"])
        else: shipment_evidence(case["shipment_id"])
        add_evidence(case["shipment_id"])
    activity(case)
    if context()[1]["role"]!="partner_user":
        with st.expander("Case technical details"):
            st.caption("Case source ID: "+case["case_id"])
            st.caption("Rule priority: "+str(case["priority_score"])+" points. Review thresholds and blocking checks are unchanged.")
            st.json(case["findings"])

def shipment_detail(shipment):
    if shipment not in shipments(): st.warning("This shipment is not assigned to your role."); return
    result=query_shipment(context()[0],context()[1],shipment)
    if not result["authorized"]: st.warning("This shipment is not available."); return
    st.button("Back to issues",icon=":material/arrow_back:",on_click=back)
    st.title(shipment)
    st.caption("Shipment record · no case is created just to view a shipment.")
    shipment_evidence(shipment); add_evidence(shipment)

def partners():
    st.title("Partners")
    st.caption("All recorded demo shipments. Open cases still need a decision or more information.")
    allowed=set(shipments()); cohort=cases()
    for partner in rows("SELECT partner_id,name FROM partners ORDER BY name"):
        population={s["shipment_id"] for s in rows("SELECT shipment_id FROM shipments WHERE partner_id=?",(partner["partner_id"],))}&allowed
        if not population: continue
        related=[c for c in cohort if c["partner_id"]==partner["partner_id"]]
        opened=[c for c in related if c["work_bucket"] in ("needs_review","awaiting_approval")]
        last=rows("SELECT MAX(occurred_at) last_activity FROM events WHERE shipment_id IN ("+",".join("?" for _ in population)+")",tuple(sorted(population)))[0]["last_activity"]
        with st.container(border=True):
            columns=st.columns([2.8,1,1,2,1.4],vertical_alignment="center")
            columns[0].markdown("**"+partner["name"]+"**")
            columns[1].caption("Shipments"); columns[1].write(len(population))
            columns[2].caption("Open cases"); columns[2].write(len(opened))
            columns[3].caption("Last activity"); columns[3].write(format_time(last))
            if columns[4].button("View partner",key="partner-"+partner["partner_id"]):
                st.session_state.selected_partner_id=partner["partner_id"]; st.rerun()
        if st.session_state.get("selected_partner_id")==partner["partner_id"]:
            st.write(f"{len(opened)} open cases across {len({c['shipment_id'] for c in opened})} affected shipments. Completed evidence does not mean verified evidence.")
            for case in sorted(opened,key=lambda c:c["priority_score"] or 0,reverse=True)[:3]: case_row(case)
            st.button("View related cases",key="related-"+partner["partner_id"],on_click=route,kwargs={"bucket":"all","partner":partner["partner_id"]})
            with st.expander("Reporting details"):
                if context()[1]["role"]=="partner_user":
                    st.caption("Counts above cover your permitted shipments and cases. Full partner reporting is available to internal reviewers.")
                    continue
                metrics=get_partner_metrics(context()[0],partner["partner_id"])
                st.write(f"Reporting sample: {metrics['sample_size']} shipments. Affected shipments: {metrics['anomaly_count']}.")
                st.write(f"Affected shipments per 1,000: {metrics['anomaly_rate_per_1000']:.1f}.")
                st.caption("All recorded history; one shipment cohort throughout. The display threshold does not establish statistical reliability. Completeness measures handover/delivery event presence.")

PAGES={"Overview":overview,"Cases":render_cases,"Partners":partners}
