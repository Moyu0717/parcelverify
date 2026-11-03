"""Permission-checked, record-backed 3D handoff explorer."""
import json
from html import escape
from datetime import datetime
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
from ui.presentation import stage_label, format_time, format_weight
from contracts import WEIGHT_DIFF_MIN_G, WEIGHT_DIFF_PCT

_scene = components.declare_component('parcel_evidence_scene', path=str(Path(__file__).with_name('evidence_scene')))


def build_nodes(events, expected):
    """Compare only measurements actually present in each source record."""
    nodes=[]
    stages={'dispatch_confirmed','handoff_submitted','pod_submitted','collection_submitted','collection_confirmed','collected','collection','warehouse_transfer','transit_update','transit_submitted','transit_handoff','transit','recipient_authorization','repackaging_approved','weight_measured'}
    events=[event for event in events if event['event_type'] in stages]
    for event in sorted(events,key=lambda e:datetime.fromisoformat(e['occurred_at'].replace('Z','+00:00'))):
        payload=json.loads(event['payload_json'])
        facts=[]; different=False; missing=False
        for field,label in (('weight_g','Weight'),('count','Packages'),('seal_id','Seal')):
            actual=payload.get(field)
            if actual is None:
                if event['event_type'] in ('dispatch_confirmed','handoff_submitted','pod_submitted'):
                    facts.append(label+': not recorded');missing=True
                continue
            baseline=expected.get(field)
            mismatch=baseline is not None and (abs(actual-baseline)>max(WEIGHT_DIFF_MIN_G,abs(baseline)*WEIGHT_DIFF_PCT) if field=='weight_g' else actual!=baseline)
            different=different or mismatch
            show=format_weight if field=='weight_g' else str
            facts.append(label+': '+show(actual)+((' · expected '+show(baseline)) if mismatch else ''))
        for field,label in (('handoff_location','Location'),('custodian_name','Custodian'),('recipient_name','Recipient')):
            if payload.get(field):facts.append(label+': '+str(payload[field]))
        nodes.append({'id':event['event_id'],'label':stage_label(event['event_type']),
                      'time':format_time(event['occurred_at']),'source':event['source'],
                      'received':format_time(event['received_at']),
                      'status':'Difference' if different else 'Missing fields' if missing else 'Recorded',
                      'facts':facts or ['No package measurements in this record.'], 'missing':False})
    if not any(e['event_type']=='handoff_submitted' for e in events):
        nodes.append({'id':'missing-handoff','label':'Handover','time':'No handover record','source':'Not recorded','received':'Not recorded',
                      'status':'Missing record','facts':['The handover submission is missing. Other measurements do not replace this source record.'],'missing':True})
    return nodes


def scene_data(case):
    from ui.live import context, rows
    from services.cases import get_case_context
    path,actor=context()
    allowed=get_case_context(path,case['case_id'],actor)
    if case['shipment_id'] not in allowed['shipment_ids']:
        return []
    expected=rows('SELECT expected_weight_g,expected_count,expected_seal FROM shipments WHERE shipment_id=?',(case['shipment_id'],))[0]
    events=rows('SELECT event_id,event_type,occurred_at,received_at,source,payload_json FROM events WHERE shipment_id=?',(case['shipment_id'],))
    return build_nodes(events,{'weight_g':expected['expected_weight_g'],'count':expected['expected_count'],'seal_id':expected['expected_seal']})


def operational_nodes(case, nodes):
    """Join persistent requests, tasks and responses; never infer a task is verified."""
    from ui.live import context, rows
    from services.cases import get_case_context
    from services.followups import list_tasks
    from ui.presentation import ACTION_LABELS, humanize
    path,actor=context()
    ctx=get_case_context(path,case['case_id'],actor)
    ids=[c['case_id'] for c in ctx['cases'] if c['shipment_id']==case['shipment_id']]
    if not ids:return nodes
    slots=','.join('?' for _ in ids)
    actions=rows('SELECT * FROM action_requests WHERE case_id IN ('+slots+') ORDER BY rowid',tuple(ids))
    audits=rows("SELECT details_json FROM audit_log WHERE case_id IN ("+slots+") AND operation='action_proposed'",tuple(ids))
    origins={a['action_id']:a.get('source_event_id') for row in audits for a in [json.loads(row['details_json'])]}
    tasks={t['task_id']:t for t in list_tasks(path,case['case_id'],actor) if t['shipment_id']==case['shipment_id']}
    by_id={n['id']:n for n in nodes}
    for node in nodes:
        node['kind']='event';node['commands']=[]
        if case['work_bucket']!='resolved' and actor['role'] in ('admin','investigator'):
            node['commands']=[['request_reweigh','Request weight check'],['request_rephoto','Request new photo'],['request_rescan','Request package scan']]
        if not node['missing']:node['commands'].append(['photos','Inspect stage photos'])
    task_actions={}
    for action in actions:
        after=json.loads(action['after_json'] or '{}')
        task_id=after.get('evidence_task_id')
        if task_id:task_actions[task_id]=action['action_id']
        task=tasks.get(task_id)
        status={'proposed':'Awaiting approval','approved':'Approved · apply next','executed':'Applied','rejected':'Rejected','failed':'Action failed'}.get(action['status'],humanize(action['status']))
        source=origins.get(action['action_id'])
        workflow={'open':'Awaiting response','received':'Response needs review','completed':'Response reviewed','cancelled':'Task cancelled'}.get(task['status'],status) if task else status
        if source in by_id:
            by_id[source]['workflow']=workflow
            by_id[source]['action_id']=action['action_id']
            if task:by_id[source]['task_id']=task_id
        nodes.append(dict(id='action:'+action['action_id'],kind='action',action_id=action['action_id'],task_id=task_id if task else None,
                          label=ACTION_LABELS.get(action['action_type'],humanize(action['action_type'])),status=status,
                          time='Approval and execution',source='Recorded request',received='',missing=True,
                          facts=[action['reason'] or 'No reason recorded',('Linked source: '+by_id[source]['label']) if source in by_id else 'Case-level request'],
                          commands=[['work','Open approval / task']]))
    for task_id,task in tasks.items():
        status={'open':'Awaiting response','received':'Response needs review','completed':'Response reviewed','cancelled':'Task cancelled'}.get(task['status'],humanize(task['status']))
        submissions=rows('SELECT event_id,review_status FROM task_submissions WHERE task_id=? ORDER BY created_at',(task_id,))
        for sub in submissions:
            if sub['event_id'] in by_id:
                by_id[sub['event_id']]['workflow']={'pending':'Response needs review','accepted':'Response accepted','more_requested':'More evidence requested'}[sub['review_status']]
                by_id[sub['event_id']]['task_id']=task_id
        nodes.append(dict(id='task:'+task_id,kind='task',task_id=task_id,action_id=task_actions.get(task_id),
                          label=humanize(task['task_type'])+' task',status=status,time=format_time(task['created_at']),
                          source='Evidence task',received='',missing=True,facts=[task['description'] or 'Supply requested evidence'],
                          commands=[['work','Submit response' if task['status']=='open' else 'Review response' if task['status']=='received' else 'View task outcome']]))
    return nodes


def prepare_scene_request(case, node, action):
    """Prepare the existing real request form; no business mutation on a scene click."""
    from ui.live import context
    from services.cases import get_case_context
    path,actor=context()
    get_case_context(path,case['case_id'],actor)
    if context()[1]['role'] not in ('admin','investigator') or case['work_bucket']=='resolved':
        raise ValueError('This role cannot prepare a request for this case')
    if action not in {command[0] for command in node.get('commands',[])} or not action.startswith('request_'):
        raise ValueError('This action is not available for the selected node')
    reason='Check '+node['label']+' ('+node['time']+'). '+ '; '.join(node['facts'])
    key='draft-'+case['case_id']+'-request-reason'
    # Explicitly starting a new node request replaces only this request draft.
    st.session_state.setdefault('drafts',{})[key]=reason[:2000]
    st.session_state[key]=reason[:2000]
    st.session_state['step-choice-'+case['case_id']]=action
    st.session_state.setdefault('cancelled_requests',{})[case['case_id']]=False
    st.session_state.setdefault('scene_request',{})[case['case_id']]={'event_id':None if node['missing'] else node['id'],'label':node['label'],'time':node['time'],'action':action}


def render_evidence_scene(case, compact=False):
    from ui.live import rows, display_photo
    from ui import workspace_ui as work
    nodes=operational_nodes(case,scene_data(case))
    if not nodes:
        st.info('No permitted shipment records to display.');return {}
    prefix=('home' if compact else 'detail')+'-scene-'+case['case_id']
    st.markdown('**'+case['shipment_id']+' · 3D review workspace**')
    st.caption('Select a parcel, request or task. Its evidence and working controls open together. Yellow = measurement difference; task badges show live workflow status.')
    default=next((n['id'] for n in reversed(nodes) if n['kind']=='task' and n['status']=='Response needs review'),next((n['id'] for n in nodes if n['status']=='Difference'),nodes[0]['id']))
    initial=st.session_state.get('scene_selection',{}).get(case['case_id'],default)
    selected=_scene(nodes=nodes, initial=initial, compact=compact, key=prefix, default=initial)
    message=selected if isinstance(selected,dict) else {'id':selected}
    pending=st.session_state.get('pending_scene_command')
    if not compact and pending and pending.get('case_id')==case['case_id']:
        message=st.session_state.pop('pending_scene_command')
    valid_selection=any(n['id']==message.get('id') for n in nodes)
    node=next((n for n in nodes if n['id']==message.get('id')),next(n for n in nodes if n['id']==default))
    previous=st.session_state.setdefault('scene_selection',{}).get(case['case_id'])
    if previous!=node['id']:st.session_state[prefix+'-mode']=None
    st.session_state.scene_selection[case['case_id']]=node['id']
    focus={k:node[k] for k in ('task_id','action_id') if node.get(k)}
    intent=message.get('intent');nonce=message.get('nonce')
    if valid_selection and isinstance(intent,str) and isinstance(nonce,str) and nonce and st.session_state.get(prefix+'-consumed')!=nonce:
        st.session_state[prefix+'-consumed']=nonce
        if intent in {c[0] for c in node.get('commands',[])}:
            if compact:
                st.session_state.pending_scene_command=dict(case_id=case['case_id'],id=node['id'],intent=intent,nonce=nonce)
                work.route(case_id=case['case_id']);st.rerun()
            elif intent.startswith('request_'):
                prepare_scene_request(case,node,intent)
                focus={}
                st.session_state[prefix+'-mode']='request'
            else:st.session_state[prefix+'-mode']=intent
    if st.session_state.get(prefix+'-mode')=='request' and node['kind']=='event':focus={'draft':True}
    st.markdown('**'+node['label']+' · '+node['status']+'**')
    st.caption(node['time'])
    st.html('<ul class="stage-facts">'+''.join('<li>'+escape(fact)+'</li>' for fact in node['facts'])+'</ul>')
    if node.get('workflow'):st.info('Linked workflow: '+node['workflow']+'. Original measurements remain unchanged.')
    if not node['missing']:
        if compact:
            st.button('Review this shipment',key=prefix+'-open',on_click=work.route,kwargs={'case_id':case['case_id']},use_container_width=True)
        else:
            st.caption('Source: '+node['source']+' · Uploaded: '+node['received'])
            if st.button('Open selected source record',key=prefix+'-source'):
                from ui.case_workflow import source_view
                source_view(node['id'])
            if st.session_state.get(prefix+'-mode')=='photos':
                st.subheader('Photos at this selected stage')
                photos=rows('SELECT local_path FROM photos WHERE event_id=?',(node['id'],))
                if not photos:st.info('No photo at this stage. Choose Request new photo in the 3D workspace to prepare the real follow-up form.')
                for photo in photos:display_photo(photo['local_path'])
    if not compact:
        st.caption('The working panel below / alongside follows your selection. Requests still require explicit submission and human approval.')
    return focus
