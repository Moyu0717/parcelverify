"""Reference-led presentation over the existing authorized review services."""
import base64
import json
from datetime import datetime, timezone
from html import escape as esc
from pathlib import Path

import streamlit as st
from ui import workspace_ui as work
from ui.live import context, rows, shipments, display_photo
from ui.presentation import format_time, format_weight, difference_weight, stage_label, humanize, status_badge
from services.handoff import compare_handoff
from services.review import review_counts
from services.access import check_access_scope

ROOT=Path(__file__).resolve().parents[1]

def navigate(destination):
    work.route(destination)

def header():
    current=st.session_state.setdefault("primary_destination","Home")
    with st.container(key="desktop-header"):
        brand,home,issues,partners,account=st.columns([3.6,1,1,1,1.4],vertical_alignment="center")
        brand.html('<div class="brand"><span class="brand-symbol">↗</span>ParcelVerify<span class="demo-tag">DEMO</span></div>')
        for col,name in ((home,"Home"),(issues,"Issues"),(partners,"Partners")):
            col.button(name,key="nav-"+name,type="primary" if current==name and not st.session_state.get("secondary_view") else "tertiary",on_click=navigate,args=(name,),use_container_width=True)
        with account.popover("Workspace",icon=":material/account_circle:",use_container_width=True):
            secondary_menu("desktop")
    with st.container(key="mobile-header"):
        brand,menu=st.columns([2.5,1],vertical_alignment="center")
        brand.html('<div class="brand"><span class="brand-symbol">↗</span>ParcelVerify</div>')
        with menu.popover("Menu",icon=":material/menu:"):
            for name in ("Home","Issues","Partners"):
                st.button(name,key="mobile-nav-"+name,on_click=navigate,args=(name,),use_container_width=True)
            st.caption("Demo workspace")
            secondary_menu("mobile")

def secondary_menu(prefix):
    st.caption(humanize(context()[1]["role"])+" · simulated identity")
    for name in ("Settings","Help"):
        st.button(name,key=prefix+"-"+name,on_click=set_secondary,args=(name,),use_container_width=True)

def set_secondary(name):
    st.session_state.secondary_view=name

def issue_info(case):
    categories={f["category"] for f in case["findings"]}
    if case["issue_type"]=="access":
        return "Access outside assigned work","A request was denied outside the recorded assignment.","Review access","Check an access request"
    if "weight_diff" in categories:
        weight=compare_handoff(context()[0],case["shipment_id"])["weight_g"]
        return "Weight changed",format_weight(weight["expected"])+" before → "+format_weight(weight["actual"])+" at handover","Compare weights","Check a weight difference"
    if "photo_reuse" in categories:
        return "Photo may have been reused","A photo matches another recorded submission.","Compare photos","Check a photo match"
    if "count_discrepancy" in categories:
        return "Package quantity changed",work.concern(case),"Compare quantities","Check a quantity difference"
    if "seal_mismatch" in categories or "id_conflict" in categories:
        return "Seal information differs",work.concern(case),"Compare seals","Check the recorded seal"
    if "time_conflict" in categories:
        return "Recorded timing needs review","The recorded event time conflicts with when it was received.","Review timing","Check the recorded timing"
    return "Delivery information needs checking",work.concern(case),"See missing information","Check delivery information"

def issue_header():
    with st.container(key="issue-table-heading"):
        body,action=st.columns([5.6,1.4],vertical_alignment="center")
        body.html('<div class="issue-grid table-labels"><span>SHIPMENT</span><span>PARTNER</span><span>WHAT NEEDS CHECKING</span><span>STATUS</span></div>')
        action.html('<div class="table-labels">ACTION</div>')

def issue_row(case):
    title,explanation,action,_=issue_info(case)
    with st.container(key="issue-row-"+case["case_id"]):
        body,button=st.columns([5.6,1.4],vertical_alignment="center")
        body.html('<div class="issue-grid"><div><strong>'+esc(case["shipment_id"])+'</strong><small>Issue '+esc(case["case_id"][:6].upper())+'</small></div><div class="partner-cell">'+esc(case["partner_name"] or "Partner not recorded")+'</div><div class="issue-description"><strong>'+esc(title)+'</strong><small>'+esc(explanation)+'</small></div><div><span class="status '+("resolved" if case["work_bucket"]=="resolved" else "attention")+'">'+esc(work.label(case))+'</span></div></div>')
        button.button(action,key="open-"+case["case_id"],icon=":material/arrow_forward:",on_click=work.route,kwargs={"case_id":case["case_id"]},use_container_width=True)

def shortcut(bucket):
    # Summary shortcuts must reconcile exactly, independent of an older search.
    for key in ("case_query","status_widget","issue_widget","partner_widget"):
        st.session_state.pop(key,None)
    st.session_state.case_search=""
    st.session_state.filter_issue="all"
    st.session_state.case_page=0
    work.route(bucket=bucket,partner="")

def show_search():
    work.route("Issues",bucket="all",partner="")
    st.session_state.find_shipment_hint=True

def home():
    with st.container(key="home-intro"):
        text,photo=st.columns([1.15,1],gap="large",vertical_alignment="center")
        with text:
            st.html('<p class="eyebrow">CLARITY AT EVERY HANDOFF</p><h1 class="hero-title">Check every handoff.<br>Understand<br><span>every issue.</span></h1><p class="hero-copy">Review shipment evidence and unusual data access across your delivery partners.</p>')
            primary,secondary=st.columns([1,1.15])
            primary.button("Review issues",type="primary",icon=":material/arrow_forward:",on_click=shortcut,args=("needs_review",),use_container_width=True)
            secondary.button("Find a shipment",on_click=show_search,use_container_width=True)
        with photo:
            encoded=base64.b64encode((ROOT/"assets/logistics-hero.png").read_bytes()).decode()
            st.html('<figure class="hero-photo"><img src="data:image/png;base64,'+encoded+'" alt="Decorative generated photograph of a green delivery truck beside a warehouse"><figcaption>Built around the records behind every delivery.<span>Illustrative image · AI generated</span></figcaption></figure>')
    counts=review_counts(work.cases())
    with st.container(key="summary-strip"):
        for col,title,bucket in zip(st.columns(3),("Needs review","Waiting for approval","Resolved"),("needs_review","awaiting_approval","resolved")):
            with col:
                st.html('<div class="summary-number"><strong>'+str(counts[bucket])+'</strong><span>'+title+'</span></div>')
                st.button("View "+title.lower(),key="counter-"+bucket,type="tertiary",on_click=shortcut,args=(bucket,))
    st.html('<div class="section-heading"><h2>Start with what needs attention</h2><p>All recorded history · only issues you are permitted to review</p></div>')
    queue=[c for c in work.cases() if c["work_bucket"] in ("needs_review","awaiting_approval")]
    queue.sort(key=lambda c:c["priority_score"] or 0,reverse=True)
    issue_header()
    for case in queue[:3]: issue_row(case)
    if not queue: st.success("No issues need a decision. Find a shipment to review its records.")
    st.html('<section class="process"><div class="process-intro"><p class="eyebrow">FROM RECORDS TO REASONS</p><h2>A clearer path<br>to the next step.</h2></div><div><b>01</b><h3>Find an issue</h3><p>See which records need a closer look.</p></div><div><b>02</b><h3>Compare the evidence</h3><p>Check shipment records, photos or account activity.</p></div><div><b>03</b><h3>Choose the next step</h3><p>Request information or submit a decision for approval.</p></div></section>')

def issues():
    cohort=work.cases()
    selected=st.session_state.get("selected_case_id")
    restore_issue_scroll("detail" if selected or st.session_state.get("selected_shipment_id") else "list")
    if selected:
        case=next((c for c in cohort if c["case_id"]==selected),None)
        if case: detail(case)
        else:
            st.warning("This issue is not available to your current role.")
            st.button("Back to issues",on_click=work.back)
        return
    if st.session_state.get("selected_shipment_id"):
        work.shipment_detail(st.session_state.selected_shipment_id);return
    st.title("Issues to review")
    st.write("Check what happened and decide what information is needed next.")
    with st.container(key="issue-search"):
        field,find=st.columns([5,1.4],vertical_alignment="bottom")
        query=field.text_input("Search shipments, partners or issues",value=st.session_state.get("case_search",""),key="case_query",placeholder="For example, PV-DEMO-001 or QuickRun",on_change=work.save_filter,args=("case_query","case_search"))
        if find.button("Find shipment",use_container_width=True): work.search(query);st.rerun()
    if st.session_state.pop("find_shipment_hint",False): st.info("Enter a shipment reference, such as PV-DEMO-001, then choose Find shipment. You can open a record even when it has no issue.")
    with st.container(key="filters"):
        status,kind,partner=st.columns([1,1,1.3])
        bucket=st.session_state.get("filter_bucket","needs_review")
        status.selectbox("Status",list(work.FILTERS),index=list(work.FILTERS.values()).index(bucket),key="status_widget",on_change=work.save_filter,args=("status_widget","filter_bucket",work.FILTERS))
        kind.selectbox("Issue type",list(work.TYPES),index=list(work.TYPES.values()).index(st.session_state.get("filter_issue","all")),key="issue_widget",on_change=work.save_filter,args=("issue_widget","filter_issue",work.TYPES))
        partners={c["partner_id"]:c["partner_name"] for c in cohort};options=["All partners",*partners.values()]
        name=partner.selectbox("Partner",options,index=options.index(partners.get(st.session_state.get("filter_partner"),"All partners")),key="partner_widget")
        st.session_state.filter_partner=next((pid for pid,n in partners.items() if n==name),"")
    filtered=[c for c in cohort if (bucket=="all" or c["work_bucket"]==bucket) and (st.session_state.get("filter_issue","all")=="all" or c["issue_type"]==st.session_state.filter_issue) and (not st.session_state.filter_partner or c["partner_id"]==st.session_state.filter_partner) and (not query or query.lower() in " ".join((c["shipment_id"],c["partner_name"] or "",*issue_info(c),c["case_id"][:6])).lower())]
    filtered.sort(key=lambda c:c["priority_score"] or 0,reverse=True)
    st.caption(f"{len(filtered)} issues across {len({c['shipment_id'] for c in filtered})} shipments · all recorded history")
    if not filtered: st.info("No issues match. Change the filters or use Find shipment to open a permitted record.");return
    page=min(st.session_state.get("case_page",0),(len(filtered)-1)//8)
    issue_header()
    for case in filtered[page*8:page*8+8]:issue_row(case)
    a,b,c=st.columns([1,3,1])
    if a.button("Previous",disabled=page==0):st.session_state.case_page=page-1;st.rerun()
    b.caption(f"Page {page+1} of {(len(filtered)+7)//8}")
    if c.button("Next",disabled=(page+1)*8>=len(filtered)):st.session_state.case_page=page+1;st.rerun()

def weight_evidence(case):
    value=compare_handoff(context()[0],case["shipment_id"])
    source=work.events(case["shipment_id"])
    # Use the same measurement-bearing record selected by compare_handoff.
    handoff=next((e for e in source if e["event_id"]==value["measurement_event_id"]),None)
    dispatch=next((e for e in source if e["event_type"]=="dispatch_confirmed"),None)
    with st.container(key="weight-comparison"):
        a,b=st.columns(2)
        for col,label,weight,event in ((a,"Before dispatch",value["weight_g"]["expected"],dispatch),(b,"At handover",value["weight_g"]["actual"],handoff)):
            with col:
                st.html('<div class="weight-value"><span>'+label+'</span><strong>'+format_weight(weight)+'</strong></div>')
                st.caption((stage_label(event["event_type"])+" · "+format_time(event["occurred_at"])) if event else "Stage record missing")
                st.caption("Source: "+humanize(event["source"]) if event else "Source: shipment expectation only")
        st.html('<div class="weight-result"><span>RECORDED DIFFERENCE</span><strong>'+esc(difference_weight(value["weight_g"]["diff"]))+'</strong></div>')
    st.write("The recorded weights differ. Check the source records and any packaging change before deciding why.")
    for event in source:
        if event["event_type"]=="repackaging_approved":
            payload=json.loads(event["payload_json"])
            st.info("Approved packaging change recorded: "+payload.get("reason","Review its supporting measurements."))
            measurements=[format_weight(json.loads(e["payload_json"]).get("weight_g")) for e in source if e["event_id"] in payload.get("supporting_measurement_ids",[])]
            st.caption("Linked weight checks: "+" → ".join(measurements) if measurements else "Supporting measurements are not recorded.")
    st.subheader("Photos supporting this review")
    images=rows("SELECT p.*,e.event_type,e.occurred_at FROM photos p JOIN events e ON p.event_id=e.event_id WHERE e.shipment_id=? ORDER BY e.occurred_at",(case["shipment_id"],))
    if not images:st.info("A supporting photo is missing. Add one or request a photo before drawing conclusions.")
    for column,photo in zip(st.columns(3),images[:3]):
        with column:
            display_photo(photo["local_path"])
            st.caption("Demonstration image · "+stage_label(photo["event_type"])+" · "+format_time(photo["occurred_at"]))
            if st.button("Enlarge photo",key="weight-enlarge-"+photo["photo_id"],icon=":material/zoom_in:"):work.enlarge(photo)
    return value

def detail(case):
    st.button("Back to issues",icon=":material/arrow_back:",type="tertiary",on_click=work.back)
    title,explanation,_,heading=issue_info(case)
    st.html('<p class="eyebrow">'+("DATA ACCESS REVIEW" if case["issue_type"]=="access" else "SHIPMENT EVIDENCE REVIEW")+'</p>')
    st.title(heading)
    st.caption(case["shipment_id"]+" · "+(case["partner_name"] or "Partner not recorded")+" · Issue "+case["case_id"][:6].upper())
    status_badge(work.label(case),"success" if case["work_bucket"]=="resolved" else "warning")
    evidence,action=st.columns([2.05,1],gap="large")
    with evidence:
        st.subheader("What happened?")
        if case["issue_type"]=="access":
            st.write("A partner account requested a shipment outside its recorded assignment. The access check denied the request; this does not establish intent.")
            access_evidence(case)
        else:
            if any(f["category"]=="weight_diff" for f in case["findings"]):weight_evidence(case)
            else:st.write(explanation)
            # The essential comparison and real photos are visible by default.
            with st.expander("All shipment checks, journey and source records",expanded=not any(f["category"]=="weight_diff" for f in case["findings"])):
                work.shipment_evidence(case["shipment_id"])
            work.add_evidence(case["shipment_id"])
        with st.container(key="ai-explanation"):
            st.subheader("A second look with AI")
            st.caption("Summarize the available evidence and suggest what to check next.")
            work.ai_summary(case)
    with action:
        with st.container(key="action-panel"):
            st.html('<p class="eyebrow">YOUR NEXT STEP</p>')
            work.next_step(case)
    work.activity(case)
    if context()[1]["role"]!="partner_user":
        with st.expander("Technical evidence details"):
            st.caption("Issue source ID: "+case["case_id"])
            st.json(case["findings"])

def access_evidence(case):
    scope=check_access_scope(context()[0],case["case_id"],context()[1])
    refs={i for f in case["findings"] for i in f.get("evidence_ids",[])}
    logs=[log for log in scope["access_logs"] if log["log_id"] in refs]
    for log in logs:
        st.html('<div class="access-facts"><div><span>ACCOUNT</span><strong>'+esc(log["actor_id"])+'</strong></div><div><span>REQUESTED SHIPMENT</span><strong>'+esc(log["shipment_id"])+'</strong></div><div><span>AUTHORIZATION RESULT</span><strong>Access denied</strong></div><div><span>RECORDED TIME</span><strong>'+esc(format_time(log["occurred_at"]))+'</strong></div></div>')
    st.subheader("Check the assignment")
    assignments=rows("SELECT actor_id,valid_from,valid_until FROM assignments WHERE shipment_id=?",(case["shipment_id"],))
    for assignment in assignments:
        st.write("**Assigned account: "+assignment["actor_id"]+"**")
        st.caption(format_time(assignment["valid_from"])+" to "+format_time(assignment["valid_until"]))
    st.info("Still to confirm: whether legitimate work explains the attempted access. An assignment and a business explanation are different checks.")
    with st.expander("Access source and approved-work context"):
        work.access_evidence(case)
    with st.expander("Related shipment evidence"):
        work.shipment_evidence(case["shipment_id"])

def partners():
    st.title("Delivery partners")
    st.write("Review the carriers, warehouses and delivery operators working with your company.")
    st.caption("All recorded history · counts include only your permitted shipments and issues")
    allowed=set(shipments());cohort=work.cases()
    selected=st.session_state.get("selected_partner_id")
    for partner in rows("SELECT partner_id,name FROM partners ORDER BY name"):
        population={s["shipment_id"] for s in rows("SELECT shipment_id FROM shipments WHERE partner_id=?",(partner["partner_id"],))}&allowed
        if not population:continue
        related=[c for c in cohort if c["partner_id"]==partner["partner_id"] and c["work_bucket"] in ("needs_review","awaiting_approval")]
        with st.container(key="partner-directory-"+partner["partner_id"]):
            info,stats,action=st.columns([2.4,2,1.1],vertical_alignment="center")
            info.html('<div class="partner-name"><span>↗</span><h2>'+esc(partner["name"])+'</h2></div>')
            stats.write(f"**{len(population)} shipments · {len(related)} open issues**")
            stats.caption(f"Open issues concern {len({c['shipment_id'] for c in related})} shipments. A shipment can have more than one issue.")
            if action.button("View partner",key="partner-"+partner["partner_id"],use_container_width=True):st.session_state.selected_partner_id=partner["partner_id"];st.rerun()
        if selected==partner["partner_id"]:
            with st.container(key="partner-profile"):
                st.subheader(partner["name"]+" · review profile")
                st.caption("Partner category and named contact are not configured in this demo.")
                recorded=rows("SELECT occurred_at FROM events WHERE shipment_id IN ("+",".join("?" for _ in population)+")",tuple(sorted(population)))
                now=datetime.now(timezone.utc)
                past=[e["occurred_at"] for e in recorded if datetime.fromisoformat(e["occurred_at"].replace("Z","+00:00"))<=now]
                future=len(recorded)-len(past)
                st.write("Latest activity at or before now: "+format_time(max(past) if past else None))
                if future:st.info(f"{future} source records have future timestamps and need timing review. Original records are retained.")
                issue_header()
                for case in sorted(related,key=lambda c:c["priority_score"] or 0,reverse=True)[:3]:issue_row(case)
                st.button("View all partner issues",on_click=work.route,kwargs={"bucket":"all","partner":partner["partner_id"]})

PAGES={"Home":home,"Issues":issues,"Partners":partners}

def restore_issue_scroll(view):
    # Only developer-authored JS; no record fields or user input enter this code.
    code="""<script>(()=>{
      const view=VIEW; const root=document.querySelector('[data-testid="stMain"]');
      if(!root)return;
      if(!window.pvScrollBound){
        document.addEventListener('click',e=>{if(e.target.closest('[class*="st-key-open-"]'))sessionStorage.setItem('pvIssueScroll',String(root.scrollTop));},true);
        window.pvScrollBound=true;
      }
      const before=window.pvIssueView; window.pvIssueView=view;
      if(before!==view){const top=view==='list'?Number(sessionStorage.getItem('pvIssueScroll')||0):0;
        setTimeout(()=>root.scrollTo({top,behavior:'instant'}),180);}
    })()</script>""".replace("VIEW",json.dumps(view))
    with st.container(key="scroll-hook"):st.html(code,unsafe_allow_javascript=True)
