"""Reference-led presentation over the existing authorized review services."""
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
from ui.case_workflow import linked_evidence, photo_comparison
from ui.evidence_map import scene_data, operational_nodes
from ui import flow
from ui.scene3d import city_scene, case_scene, ordered_stations, van_target

ROOT=Path(__file__).resolve().parents[1]

def navigate(destination):
    st.session_state.navigation_generation=st.session_state.get('navigation_generation',0)+1
    work.route(destination)

def header():
    current=st.session_state.setdefault("primary_destination","Home")
    generation=st.session_state.get('navigation_generation',0)
    role=context()[1]["role"]
    with st.container(key="desktop-header"):
        brand,home,issues,partners,account=st.columns([3.4,1,1,1,1.6],vertical_alignment="center")
        brand.html('<div class="brand"><span class="brand-symbol">↗</span>ParcelVerify<span class="brand-dot">.</span><span class="demo-tag">DEMO</span></div>')
        for col,name in ((home,"Home"),(issues,"Cases"),(partners,"Partners")):
            col.button(name,key="nav-"+name,type="primary" if current==name and not st.session_state.get("secondary_view") else "tertiary",on_click=navigate,args=(name,),use_container_width=True)
        with account.popover(flow.ROLE_NAMES[role],key='workspace-menu-'+str(generation),icon=":material/account_circle:",use_container_width=True):
            secondary_menu("desktop")
    with st.container(key="mobile-header"):
        brand,menu=st.columns([2.5,1],vertical_alignment="center")
        brand.html('<div class="brand"><span class="brand-symbol">↗</span>ParcelVerify<span class="brand-dot">.</span></div>')
        with menu.popover("Menu",key='mobile-menu-'+str(generation),icon=":material/menu:"):
            for name in ("Home","Cases","Partners"):
                st.button(name,key="mobile-nav-"+name,on_click=navigate,args=(name,),use_container_width=True)
            secondary_menu("mobile")

def remember_role(prefix):
    flow.switch_role(st.session_state[prefix+"-role"])

def secondary_menu(prefix):
    role=context()[1]["role"]
    st.radio("Act as (demo role)",list(flow.ROLE_NAMES),index=list(flow.ROLE_NAMES).index(role),format_func=flow.ROLE_NAMES.get,key=prefix+"-role",on_change=remember_role,args=(prefix,))
    st.caption("Simulated identities show who may do which step.")
    for name in ("Settings","Help"):
        st.button(name,key=prefix+"-"+name,on_click=set_secondary,args=(name,),use_container_width=True)

def set_secondary(name):
    st.session_state.navigation_generation=st.session_state.get('navigation_generation',0)+1
    st.session_state.secondary_view=name

def issue_info(case):
    categories={f["category"] for f in case["findings"]}
    if 'authorized_export' in categories and not (categories-{'authorized_export'}):
        return 'Supported legitimate explanation','Approved export and linked packaging evidence are available.','Review explanation','Review a supported explanation'
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

BUCKET_STYLE={"needs_review":("attention","Needs review"),"awaiting_approval":("dark","Waiting for approval"),"waiting_evidence":("blue","Waiting for partner"),"resolved":("resolved","Closed")}

def initials(name):
    parts=[p for p in (name or "?").replace("-"," ").split() if p[:1].isalpha()]
    return "".join(p[0] for p in parts[:2]).upper() or "?"

def issue_header():
    with st.container(key="issue-table-heading"):
        st.html('<div class="list-head"><span>Case</span><span>Status</span></div>')

def issue_row(case):
    title,explanation,action,_=issue_info(case)
    tone,_label=BUCKET_STYLE.get(case["work_bucket"],("attention",""))
    with st.container(key="issue-row-"+case["case_id"]):
        st.html('<div class="order-row"><span class="avatar">'+esc(initials(case["partner_name"]))+'</span><div class="order-main"><strong>'+esc(case["shipment_id"])+' <em>→</em> '+esc(title)+'</strong><small>'+esc(case["partner_name"] or "Partner not recorded")+' · Case '+esc(case["case_id"][:6].upper())+' · '+esc(explanation)+'</small></div><span class="status '+tone+'"><i></i>'+esc(work.label(case))+'</span><span class="chev">›</span></div>')
        st.button(action+" · "+case["shipment_id"],key="open-"+case["case_id"],on_click=work.route,kwargs={"case_id":case["case_id"]},use_container_width=True)

def shortcut(bucket):
    # Summary shortcuts must reconcile exactly, independent of an older search.
    for key in ("case_query","status_widget","issue_widget","partner_widget"):
        st.session_state.pop(key,None)
    st.session_state.case_search=""
    st.session_state.filter_issue="all"
    st.session_state.case_page=0
    work.route(bucket=bucket,partner="")

def show_search():
    work.route("Cases",bucket="all",partner="")
    st.session_state.find_shipment_hint=True

def home_filter(bucket):
    st.session_state.home_bucket=bucket

STAT_CARDS=(("needs_review","Needs review","Check these first","🔎"),("awaiting_approval","Waiting for approval","A supervisor decides","✍️"),("waiting_evidence","Waiting for partner","Proof requested","📨"),("resolved","Closed","Decision recorded","✅"))

def city_cases(cohort):
    ranked=sorted(cohort,key=lambda c:c["priority_score"] or 0,reverse=True)
    picked=[]
    for bucket,limit in (("needs_review",6),("awaiting_approval",3),("waiting_evidence",3),("resolved",2)):
        picked+=[c for c in ranked if c["work_bucket"]==bucket][:limit]
    return [dict(id=c["case_id"],shipment=c["shipment_id"],title=issue_info(c)[0],bucket=c["work_bucket"]) for c in picked]

def home():
    cohort=work.cases()
    counts=review_counts(cohort)
    candidates=sorted((c for c in cohort if c['work_bucket']=='needs_review'),key=lambda c:c['priority_score'] or 0,reverse=True)
    first=candidates[0] if candidates else None
    with st.container(key="welcome"):
        scene,intro=st.columns([1.45,1],gap="large")
        with scene:
            opened=city_scene(city_cases(cohort),first["case_id"] if first else None)
            if opened:
                work.route(case_id=opened);st.rerun()
        with intro:
            st.html('<p class="eyebrow">YOUR REVIEW DESK</p>')
            st.title("Every handoff, a little clearer.")
            st.write("Tap a building on the map, or let us pick the most urgent case for you.")
            if first:
                with st.container(key="next-card"):
                    st.html('<div class="next-card"><span class="tag">NEXT UP</span><strong>'+esc(first["shipment_id"])+'</strong><span>'+esc(issue_info(first)[0])+' · '+esc(first["partner_name"] or "Partner")+'</span></div>')
                    st.button("Start next review",key="start-next-review",type="primary",icon=":material/arrow_forward:",on_click=work.route,kwargs={"case_id":first['case_id']},use_container_width=True)
            else:
                st.success("No new reviews waiting. Check your follow-ups below.")
            st.button("Find a shipment",key="home-find",on_click=show_search,type="tertiary",icon=":material/search:")
    bucket=st.session_state.get("home_bucket","needs_review")
    with st.container(key="summary-strip"):
        for col,(value,title,hint,icon) in zip(st.columns(4),STAT_CARDS):
            with col,st.container(key="stat-"+value):
                st.html('<div class="stat-card'+(' active' if bucket==value else '')+'"><span class="stat-icon">'+icon+'</span><b>'+str(counts[value])+'</b><strong>'+title+'</strong><small>'+hint+'</small></div>')
                st.button("Show "+title.lower()+" ("+str(counts[value])+")",key="counter-"+value,on_click=home_filter,args=(value,),use_container_width=True)
    st.html('<ol class="how-it-works"><li><b>1</b>Check the difference</li><li><b>2</b>Ask the partner for proof</li><li><b>3</b>Review the reply</li><li><b>4</b>Finish the case</li></ol>')
    label=next(name for name,value in work.FILTERS.items() if value==bucket)
    st.html('<div class="review-intro"><h2>My cases</h2><span>'+esc(label)+'</span></div>')
    with st.container(key="home-search"):
        search,kind=st.columns([2.2,1])
        query=search.text_input("Search this list",key="home_query",placeholder="Shipment, partner or case",label_visibility="collapsed")
        selected=kind.selectbox("Evidence type",["All","Shipment evidence","Data access"],key="home_kind",label_visibility="collapsed")
    queue=[c for c in cohort if c["work_bucket"]==bucket and (selected=="All" or selected=="Data access" and c.get("contains_access") or selected=="Shipment evidence" and c["issue_type"]=="shipment") and (not query or query.lower() in " ".join((c["shipment_id"],c["partner_name"] or "",*issue_info(c),c["case_id"])).lower())]
    queue.sort(key=lambda c:c["priority_score"] or 0,reverse=True)
    for case in queue[:8]:issue_row(case)
    if not queue:st.info("No cases match this list. Choose another card above or change the search.")
    if len(queue)>8:
        st.caption(f"Showing 8 of {len(queue)} cases.")
        st.button("View all cases",key="all-home-cases",on_click=shortcut,args=(bucket,))
    st.caption("Demo workspace · synthetic records · nothing leaves this demo")


def issues():
    cohort=work.cases()
    selected=st.session_state.get("selected_case_id")
    restore_issue_scroll("detail" if selected or st.session_state.get("selected_shipment_id") else "list")
    if selected:
        case=next((c for c in cohort if c["case_id"]==selected),None)
        if case: detail(case)
        else:
            st.warning("This issue is not available to your current role.")
            st.button("Back to cases",on_click=work.back)
        return
    if st.session_state.get("selected_shipment_id"):
        work.shipment_detail(st.session_state.selected_shipment_id);return
    st.title("Cases to review")
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
    filtered=[c for c in cohort if (bucket=="all" or c["work_bucket"]==bucket) and (st.session_state.get("filter_issue","all")=="all" or (st.session_state.filter_issue=='access' and c.get('contains_access')) or (st.session_state.filter_issue=='shipment' and c['issue_type']=='shipment')) and (not st.session_state.filter_partner or c["partner_id"]==st.session_state.filter_partner) and (not query or query.lower() in " ".join((c["shipment_id"],c["partner_name"] or "",*issue_info(c),c["case_id"][:6])).lower())]
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
        after_label='New weight measurement' if handoff and handoff['event_type']=='weight_measured' else 'At handover'
        for col,label,weight,event in ((a,"Before dispatch",value["weight_g"]["expected"],dispatch),(b,after_label,value["weight_g"]["actual"],handoff)):
            with col:
                st.html('<div class="weight-value"><span>'+label+'</span><strong>'+format_weight(weight)+'</strong></div>')
                st.caption((stage_label(event["event_type"])+" · "+format_time(event["occurred_at"])) if event else "Stage record missing")
                st.caption("Source: "+humanize(event["source"]) if event else "Source: shipment expectation only")
                if event:st.caption('Uploaded: '+format_time(event['received_at']))
        st.html('<div class="weight-result"><span>RECORDED DIFFERENCE</span><strong>'+esc(difference_weight(value["weight_g"]["diff"]))+'</strong></div>')
    st.write("The latest weight matches the expectation; review the original signal and subsequent evidence before closing." if value['weight_g']['match'] else "The recorded weights differ. Check the source records and any packaging change before deciding why.")
    location=value.get('location',{})
    st.write('Recorded stage location: '+str(location.get('actual') or 'Unknown')+' · Expected here: '+str(location.get('expected') or 'Unknown'))
    st.caption(location.get('status','Recorded — not verified')+'. Stage locations are separate from the delivery destination.')
    st.caption('Custodian: '+str(location.get('custodian') or 'Unknown')+' · Sender: '+str(location.get('sender') or 'Unknown')+' · Receiver: '+str(location.get('receiver') or 'Unknown'))
    with st.expander('How the weight comparison works'):
        st.caption('Rule tolerance: the larger of 100 g or 5% of the earlier weight. Display precision preserves recorded differences; a small difference can still match within tolerance.')
    for event in source:
        if event["event_type"]=="repackaging_approved":
            payload=json.loads(event["payload_json"])
            st.info("Approved packaging change recorded: "+payload.get("reason","Review its supporting measurements."))
            measurements=[format_weight(json.loads(e["payload_json"]).get("weight_g")) for e in source if e["event_id"] in payload.get("supporting_measurement_ids",[])]
            st.caption("Linked weight checks: "+" → ".join(measurements) if measurements else "Supporting measurements are not recorded.")
    if any(f['category']=='photo_reuse' for f in case['findings']):return value
    st.subheader("Photos supporting this review")
    images=rows("SELECT p.*,e.event_type,e.occurred_at FROM photos p JOIN events e ON p.event_id=e.event_id WHERE e.shipment_id=? ORDER BY e.occurred_at",(case["shipment_id"],))
    if not images:st.info("A supporting photo is missing. Add one or request a photo before drawing conclusions.")
    for column,photo in zip(st.columns(3),images[:3]):
        with column:
            display_photo(photo["local_path"])
            st.caption("Demonstration image · "+stage_label(photo["event_type"])+" · "+format_time(photo["occurred_at"]))
            if st.button("Enlarge photo",key="weight-enlarge-"+photo["photo_id"],icon=":material/zoom_in:"):work.enlarge(photo)
    return value

def ask_here(case_id,node):
    st.session_state['choice-'+case_id]=flow.ASK
    facts=' '.join(node.get('facts',[])).lower()
    st.session_state.scene_request_type='request_rephoto' if 'photo' in facts else 'request_rescan' if 'packages' in facts and 'expected' in facts else 'request_reweigh'

def map_panel(case,stations,selected,phase):
    path,actor=context()
    node=next((n for n in stations if n['id']==selected),None)
    if not node:
        st.html('<p class="eyebrow">ON THE MAP</p><h3 class="step-title">Tap a building</h3><p class="step-copy">Each building is one recorded stop of this parcel. Yellow means a measurement differs; dashed means a record is missing.</p>')
        return
    number=stations.index(node)+1
    tone='attention' if node['status']=='Difference' else 'blue' if node['missing'] else 'resolved'
    st.html('<p class="eyebrow">ON THE MAP · STOP '+str(number).zfill(2)+'</p><div class="stop-head"><h3 class="step-title">'+esc(node['label'])+'</h3><span class="status '+tone+'"><i></i>'+esc(node['status'])+'</span></div><p class="step-copy">'+esc(node['time'])+'</p>')
    st.html('<ul class="stage-facts">'+''.join('<li>'+esc(f)+'</li>' for f in node['facts'])+'</ul>')
    if node.get('workflow'):st.info('Workflow here: '+node['workflow']+'. The original measurement stays unchanged.')
    can_ask=phase in ('check','finish') and actor['role'] in ('admin','investigator') and case['issue_type']=='shipment'
    a,b=st.columns(2)
    if not node['missing'] and a.button('Open original record',key='src-'+node['id'],icon=':material/description:',use_container_width=True):
        from ui.case_workflow import source_view
        source_view(node['id'])
    if can_ask:
        b.button('Ask for a missing record' if node['missing'] else 'Ask partner to re-check here',key='ask-here-'+node['id'],on_click=ask_here,args=(case['case_id'],node),icon=':material/replay:',use_container_width=True)
    if not node['missing']:
        photos=rows('SELECT local_path FROM photos WHERE event_id=?',(node['id'],))
        if photos:
            with st.expander('Photo at this stop'):
                for photo in photos[:2]:display_photo(photo['local_path'])

def detail(case):
    path,actor=context()
    title,explanation,_,heading=issue_info(case)
    tasks,actions=flow.load(case)
    phase=flow.phase_of(case,tasks,actions)
    stations=ordered_stations(operational_nodes(case,scene_data(case)))
    store=st.session_state.setdefault('scene_selection',{})
    if store.get(case['case_id']) not in {n['id'] for n in stations}|{'hq'}:
        store[case['case_id']]=van_target(stations,phase)
    st.button("Back",icon=":material/arrow_back:",type="tertiary",on_click=work.back,key="back-to-cases")
    picked=case_scene(case,stations,phase,store[case['case_id']],title)
    if picked:
        store[case['case_id']]=picked
    selected=store[case['case_id']]
    tone,_=BUCKET_STYLE.get(case["work_bucket"],("attention",""))
    with st.container(key="case-sheet"):
        st.html('<div class="sheet-head"><span class="avatar big">'+esc(initials(case["partner_name"]))+'</span><div><strong>'+esc(case["partner_name"] or "Partner not recorded")+'</strong><small>'+('Data access review' if case["issue_type"]=="access" else 'Delivery partner')+'</small></div><span class="status '+tone+'"><i></i>'+esc(work.label(case))+'</span></div>')
        st.title(heading)
        st.caption(case["shipment_id"]+" · Case "+case["case_id"][:6].upper()+" · "+explanation)
        st.html(flow.progress_html(phase))
    step,where=st.columns([1.2,1],gap="large")
    with step:
        with st.container(key="action-panel"):
            st.html('<div id="review-actions"></div>')
            flow.next_step(case,stations,selected if selected!='hq' else None,concern=title)
    with where:
        with st.container(key="map-panel"):
            map_panel(case,stations,selected,phase)
    st.html('<h2 class="section-title">More details</h2>')
    with st.expander("📄 Evidence and photos",expanded=case["issue_type"]=="access"):
        linked_evidence(case)
        if case["issue_type"]=="access":
            st.write("A partner account requested a shipment outside its recorded assignment. The access check denied the request; this does not establish intent.")
            access_evidence(case)
        else:
            if any(f["category"]=="weight_diff" for f in case["findings"]):weight_evidence(case)
            else:
                st.write(explanation)
                comparison=compare_handoff(context()[0],case['shipment_id'])
                weight=comparison['weight_g']
                if weight['actual'] is None:
                    st.write('Handover weight is missing. Before dispatch: '+format_weight(weight['expected'])+'.')
                else:
                    st.write('Weight before dispatch: '+format_weight(weight['expected'])+'; at handover: '+format_weight(weight['actual'])+'.')
                for field,label in (('count','Package quantity'),('seal','Seal reference')):
                    check=comparison[field]
                    st.caption(label+': expected '+str(check['expected'] if check['expected'] is not None else 'not recorded')+'; recorded '+str(check['actual'] if check['actual'] is not None else 'missing'))
            photo_comparison(case)
            linked_evidence(case,details=True)
            with st.popover("All shipment checks and source records",use_container_width=True):
                work.shipment_evidence(case["shipment_id"])
    with st.expander("🤖 AI review agent",expanded=actor["role"] in ("admin","investigator","approver")):
        with st.container(key="ai-explanation"):
            st.caption("The agent picks read-only tools, collects evidence with IDs, then recommends one next step. Every claim is checked against the evidence, and a person always decides.")
            work.ai_summary(case)
    if case["issue_type"]!="access":work.add_evidence(case["shipment_id"])
    work.activity(case)
    if actor["role"]!="partner_user":
        with st.expander("Technical evidence details"):
            st.caption("Issue source ID: "+case["case_id"])
            st.json(case["findings"])

def access_evidence(case):
    linked_evidence(case,details=True)
    st.info("Still to confirm: whether legitimate work explains the request. An assignment and a business explanation are different checks.")
    with st.popover("Access source and approved-work context",use_container_width=True):
        work.access_evidence(case)
    with st.popover("Related shipment evidence",use_container_width=True):
        work.shipment_evidence(case["shipment_id"])


def partners():
    from services.risk import summarize_permitted_shipments
    st.title("Delivery partners")
    st.write("Review the carriers, warehouses and delivery operators working with your company.")
    st.caption("All recorded history · counts include only your permitted shipments and issues")
    allowed=set(shipments());cohort=work.cases()
    selected=st.session_state.get("selected_partner_id")
    for partner in rows("SELECT partner_id,name FROM partners ORDER BY name"):
        population={s["shipment_id"] for s in rows("SELECT shipment_id FROM shipments WHERE partner_id=?",(partner["partner_id"],))}&allowed
        if not population:continue
        summary=summarize_permitted_shipments(context()[0],population)
        related=[c for c in cohort if c["partner_id"]==partner["partner_id"] and c["work_bucket"] in ("needs_review","awaiting_approval","waiting_evidence")]
        with st.container(key="partner-directory-"+partner["partner_id"]):
            info,stats,action=st.columns([2.4,2,1.1],vertical_alignment="center")
            info.html('<div class="partner-name"><span>↗</span><h2>'+esc(partner["name"])+'</h2></div>')
            affected={sid for c in related for sid in c.get('shipment_ids',[c['shipment_id']])}&population
            stats.write(f"**{len(population)} shipments · {len(related)} open cases**")
            stats.caption(f"Shipments with recorded findings: {summary['affected_shipments']} / {len(population)}. Waiting tasks: {sum(c.get('open_task_count',0) for c in related)}.")
            stats.caption(f"Evidence complete: {summary['complete_shipments']} / {len(population)}; missing required evidence: {summary['missing_evidence_shipments']}. Completeness is not verification.")
            stats.caption(f"Finding outcomes: {summary['open_findings']} unreviewed or unresolved; {summary['supported_findings']} supported; {summary['resolved_findings']} resolved by human review.")
            recurring=[humanize(key)+f' ({count} shipments)' for key,count in summary['recurring_categories'].items()]
            if recurring:stats.caption('Recorded categories: '+', '.join(recurring))
            if summary['small_sample']:stats.caption('Small sample: these counts do not support a reliable partner comparison or a misconduct conclusion.')
            if action.button("View partner",key="partner-"+partner["partner_id"],use_container_width=True):st.session_state.selected_partner_id=partner["partner_id"];st.rerun()
        if selected==partner["partner_id"]:
            with st.container(key="partner-profile"):
                st.subheader(partner["name"]+" · review profile")
                st.caption("Partner category and named contact are not configured in this demo.")
                recorded=rows("SELECT occurred_at FROM events WHERE shipment_id IN ("+",".join("?" for _ in population)+")",tuple(sorted(population)))
                now=datetime.now(timezone.utc)
                past=[e["occurred_at"] for e in recorded if datetime.fromisoformat(e["occurred_at"].replace("Z","+00:00"))<=now]
                future=len(recorded)-len(past)
                st.write("Latest evidence event time at or before now: "+format_time(max(past,key=lambda value:datetime.fromisoformat(value.replace('Z','+00:00'))) if past else None))
                if future:st.info(f"{future} source records have future timestamps and need timing review. Original records are retained.")
                issue_header()
                for case in sorted(related,key=lambda c:c["priority_score"] or 0,reverse=True)[:3]:issue_row(case)
                st.button("View all partner issues",on_click=work.route,kwargs={"bucket":"all","partner":partner["partner_id"]})

PAGES={"Home":home,"Cases":issues,"Partners":partners}

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
