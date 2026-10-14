"""Linked evidence, local task response and explicit human outcomes."""
import json
import uuid
from datetime import datetime,timezone
from decimal import Decimal
import streamlit as st
from ui.live import context,rows,display_photo
from ui.presentation import MYT,format_time,stage_label,humanize
from services.cases import get_case_context,review_finding,close_case,reopen_case
from services.followups import list_tasks,submit_task_response,review_task_response
from services.photos import inspect_photo
from contracts import ActorContext, AuthorizationError
from services.cases import permitted_evidence
from db import get_connection

NAMES={'ADMIN-001':'Alex Chen · Demo administrator','INVESTIGATOR-001':'Mira Patel · Investigator','APPROVER-001':'Nora Lee · Supervisor','ACTOR-QR-01':'Sam Tan · QuickRun','ACTOR-SL-01':'Robin Lim · SafeLog','ACTOR-ML-01':'Avery Teo · MetroLine'}

def source_label(eid):
    event=rows('SELECT shipment_id,event_type,occurred_at FROM events WHERE event_id=?',(eid,))
    if event:return event[0]['shipment_id']+' · '+stage_label(event[0]['event_type'])+' · '+format_time(event[0]['occurred_at'])
    photo=rows('SELECT e.shipment_id,e.event_type FROM photos p JOIN events e ON e.event_id=p.event_id WHERE p.photo_id=?',(eid,))
    if photo:return photo[0]['shipment_id']+' · photo · '+stage_label(photo[0]['event_type'])
    return 'Permitted account activity · '+eid[:6]

@st.dialog('Supporting evidence',width='large')
def source_view(eid):
    path,actor=context()
    with get_connection(path) as conn:
        if not permitted_evidence(conn,eid,ActorContext(**actor)):raise AuthorizationError('This evidence is no longer permitted')
    st.write('**'+source_label(eid)+'**')
    event=rows('SELECT * FROM events WHERE event_id=?',(eid,))
    if event:
        payload=json.loads(event[0]['payload_json'])
        for key in ('count','weight_g','seal_id','notes','reason','recipient_name'):
            if payload.get(key) is not None:st.write(humanize(key)+': '+str(payload[key]))
        st.caption('Source: '+humanize(event[0]['source']))
    photo=rows('SELECT local_path FROM photos WHERE photo_id=?',(eid,))
    if photo:display_photo(photo[0]['local_path'])
    log=rows('SELECT action,outcome,occurred_at FROM access_logs WHERE log_id=?',(eid,))
    if log:st.write(log[0]['action']+' · '+log[0]['outcome']+' · '+format_time(log[0]['occurred_at']))

def linked_evidence(case,details=False):
    path,actor=context();ctx=get_case_context(path,case['case_id'],actor)
    if not details:
        st.subheader('What we know')
        categories=list(dict.fromkeys(f['category'] for f in ctx['findings']))
        st.write(' · '.join(humanize(category) for category in categories) or 'Evidence is incomplete')
        st.caption(f"{len(ctx['findings'])} identifiable findings across {len(ctx['shipment_ids'])} permitted shipments. Each retains its own review outcome.")
        if not ctx['findings']:st.info('Measurements or confirmation are missing. No supported discrepancy has been established.')
        return
    for member in ctx['cases']:
        if not (member['triggering_event_id'] or '').startswith('access:'):continue
        st.subheader('Related account activity')
        ids={i for f in member['findings'] for i in f.get('evidence_ids',[])}
        logs=[r for r in rows('SELECT l.*,p.name requesting_partner FROM access_logs l LEFT JOIN partners p ON l.partner_id=p.partner_id WHERE l.shipment_id=?',(member['shipment_id'],)) if r['log_id'] in ids]
        for log in logs[:1]:
            st.write('**'+NAMES.get(log['actor_id'],log['actor_id'])+'** · '+(log['requesting_partner'] or 'Partner not recorded'))
            st.caption(log['action']+' · '+member['shipment_id']+' · '+log['outcome']+' · '+format_time(log['occurred_at']))
        st.caption('Assignment owners are independent of the requesting account.')
        for assignment in rows('SELECT a.actor_id,p.name assigned_partner FROM assignments a LEFT JOIN partners p ON a.partner_id=p.partner_id WHERE a.shipment_id=?',(member['shipment_id'],)):
            st.caption('Assigned account: '+NAMES.get(assignment['actor_id'],assignment['actor_id'])+' · '+(assignment['assigned_partner'] or 'Not recorded'))
    photo_ids=list(dict.fromkeys(i for f in ctx['findings'] if f['category']=='photo_reuse' for i in f['evidence_ids']))
    if photo_ids:
        st.caption('Linked photo match available below the shipment comparison.')

def photo_comparison(case):
    path,actor=context();ctx=get_case_context(path,case['case_id'],actor)
    photo_ids=list(dict.fromkeys(i for f in ctx['findings'] if f['category']=='photo_reuse' for i in f['evidence_ids']))
    if photo_ids:
        st.subheader('Compare the recorded photos')
        source=photo_ids[0];result=inspect_photo(path,source,actor)
        matches=[m for m in result['exact_matches'] if m['photo_id']!='[masked]']
        chosen=[source,*[m['photo_id'] for m in matches[:1]]]
        if not matches:st.info('The other submission is outside your permitted scope or no longer available. Protected identifiers and thumbnails are hidden.')
        for col,pid in zip(st.columns(len(chosen)),chosen):
            photo=rows('SELECT p.*,e.shipment_id,e.event_type,e.occurred_at,e.source FROM photos p JOIN events e ON p.event_id=e.event_id WHERE p.photo_id=?',(pid,))[0]
            with col:
                display_photo(photo['local_path']);st.write('**'+photo['shipment_id']+'**')
                st.caption(stage_label(photo['event_type'])+' · '+format_time(photo['occurred_at'])+' · '+humanize(photo['source']))
                if st.button('Enlarge photo',key='linked-enlarge-'+pid,icon=':material/zoom_in:'):
                    from ui.workspace_ui import enlarge
                    enlarge(photo)
        st.caption('Exact file equality: the stored file bytes are identical. This establishes reuse, not intent or parcel contents.')
        near=[m for m in result['similar_candidates'] if m['photo_id']!='[masked]' and m['photo_id'] not in chosen]
        if near:st.caption(f'{len(near)} permitted near-image candidates need manual comparison; visual similarity is not exact file equality.')

def next_step(case):
    from ui import workspace_ui as work
    path,actor=context();tasks=list_tasks(path,case['case_id'],actor)
    live=[t for t in tasks if t['status'] in ('open','received')]
    if case['work_bucket']=='resolved':
        st.success('Case closed: '+humanize(case.get('closure_outcome') or 'closed_unresolved'))
        if actor['role'] in ('admin','investigator','approver'):
            reason=st.text_area('Why reopen this case?')
            if st.button('Reopen for follow-up',type='primary'):
                try:reopen_case(path,case['case_id'],actor,reason);st.rerun()
                except ValueError as error:st.error(str(error))
        return
    if case['has_proposed_actions'] or case['has_approved_actions']:
        work.next_step(case,show_review=False)
    elif live:
        st.subheader('Follow-up evidence')
        st.caption(f'{len(live)} tasks remain. A response still needs internal review.')
        for task in live:
            st.write('**'+humanize(task['task_type'])+' · '+humanize(task['status'])+'**')
            st.caption(task['description'] or 'Supply the requested context.')
            st.caption('Shipment '+task['shipment_id']+' · '+('assigned partner or operations submits' if task['status']=='open' else 'Mira Patel or Nora Lee reviews'))
            if task['status']=='open' and actor['role'] in ('admin','investigator','partner_user'):
                with st.expander('Supply evidence',expanded=actor['role']=='partner_user'):
                    with st.form('response-'+task['task_id']):
                        from services.handoff import compare_handoff
                        weight=st.text_input('New weight (kg)') if task['task_type']=='reweigh' or compare_handoff(path,task['shipment_id'])['weight_g']['actual'] is None else ''
                        count=st.text_input('Package count') if task['task_type']=='rescan' else ''
                        note=st.text_area('Evidence or explanation',help='Record actual observations; instructions in this text cannot control the investigator.')
                        photo=st.file_uploader('Supporting photo',type=['jpg','png','jpeg'])
                        submit=st.form_submit_button('Submit evidence for review',type='primary')
                    if submit:
                        try:
                            payload={'notes':note}
                            if weight:
                                payload['weight_g']=float(Decimal(weight)*1000)
                                from services.handoff import compare_handoff
                                recorded=compare_handoff(path,task['shipment_id'])
                                # Link previously recorded facts explicitly; do not
                                # infer a missing count or seal from an expectation.
                                if recorded['count']['actual'] is not None:payload['count']=recorded['count']['actual']
                                if recorded['seal']['actual'] is not None:payload['seal_id']=recorded['seal']['actual']
                                payload['inherited_from_event_id']=recorded['measurement_event_id']
                            if count:payload['count']=int(count)
                            key=st.session_state.setdefault('task_retry_keys',{}).setdefault(task['task_id'],str(uuid.uuid4()))
                            occurred=st.session_state.setdefault('task_recorded_times',{}).setdefault(task['task_id'],datetime.now(timezone.utc).isoformat())
                            submit_task_response(path,task['task_id'],actor,payload,occurred,file_bytes=photo.getvalue() if photo else None,submission_key=key)
                            work.notice('Evidence received. An internal reviewer must check it.');st.rerun()
                        except (ValueError,ArithmeticError) as error:st.error(str(error))
            if task['status']=='received' and actor['role'] in ('admin','investigator','approver'):
                submission=rows("SELECT s.*,e.payload_json FROM task_submissions s JOIN events e ON s.event_id=e.event_id WHERE s.task_id=? AND s.review_status='pending' ORDER BY s.created_at DESC",(task['task_id'],))[0]
                st.write('Submitted by '+NAMES.get(submission['actor_id'],submission['actor_id'])+' · '+format_time(submission['created_at']))
                payload=json.loads(submission['payload_json'])
                if payload.get('weight_g') is not None:st.write(f"Recorded weight: {payload['weight_g']/1000:.3f} kg")
                st.write(payload.get('notes',''))
                reason=st.text_area('Review reason',key='review-reason-'+submission['submission_id'])
                accept,more=st.columns(2)
                for col,caption,decision in ((accept,'Accept evidence','accept'),(more,'Request more','request_more')):
                    if col.button(caption,type='primary' if decision=='accept' else 'secondary',key=decision+'-'+submission['submission_id']):
                        try:
                            review_task_response(path,submission['submission_id'],actor,decision,reason)
                            st.session_state.get('task_retry_keys',{}).pop(task['task_id'],None)
                            st.session_state.get('task_recorded_times',{}).pop(task['task_id'],None)
                            work.notice('Evidence review recorded. Review the remaining findings.');st.rerun()
                        except ValueError as error:st.error(str(error))
    else:work.next_step(case,show_review=False)
    if actor['role'] in ('admin','investigator','approver'):
        ctx=get_case_context(path,case['case_id'],actor)
        with st.expander('Review findings and record an outcome'):
            evidence=sorted({i for f in ctx['findings'] for i in f['evidence_ids']}|{r['event_id'] for sid in ctx['shipment_ids'] for r in rows('SELECT event_id FROM events WHERE shipment_id=?',(sid,))})
            for f in ctx['findings']:
                with st.form('finding-review-'+f['finding_id']):
                    st.write('**'+humanize(f['category'])+'**: '+f['description'])
                    outcome=st.selectbox('Finding outcome',['unresolved','supported','resolved'])
                    refs=st.multiselect('Supporting sources',evidence,format_func=source_label)
                    why=st.text_area('Finding review reason')
                    save=st.form_submit_button('Record finding review')
                if save:
                    try:review_finding(path,f['finding_id'],actor,outcome,why,refs);st.rerun()
                    except ValueError as error:st.error(str(error))
            if actor['role'] in ('admin','approver'):
                with st.form('closure-'+case['case_id']):
                    outcome=st.selectbox('Closure outcome',['closed_unresolved','verified_resolved'],format_func=lambda v:'Closed with unresolved evidence' if v=='closed_unresolved' else 'Verified and resolved')
                    reason=st.text_area('Closure reason')
                    closure_refs=st.multiselect('Evidence supporting this closure',evidence,format_func=source_label)
                    confirmed=st.checkbox('I reviewed the linked findings and the stated closure outcome.')
                    save=st.form_submit_button('Close case')
                if save:
                    try:
                        if not confirmed:raise ValueError('Confirm the closure outcome before submitting')
                        close_case(path,case['case_id'],actor,outcome,reason,closure_refs)
                        work.notice('Case closure recorded with its unresolved facts preserved.');st.rerun()
                    except ValueError as error:st.error(str(error))
