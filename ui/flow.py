"""One clear next step per case: Check -> Ask for proof -> Review reply -> Finish.

Every write still goes through the existing permission-checked services. This module only
decides which single step to show and pre-fills sensible defaults so a newcomer can proceed.
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from html import escape

import streamlit as st
from contracts import AuthorizationError, IdempotencyError
from services.actions import propose_action, review_action, execute_action
from services.cases import get_case_context, review_finding, close_case, reopen_case
from services.followups import list_tasks, submit_task_response, review_task_response
from services.handoff import compare_handoff
from ui.live import context, rows, display_photo
from ui.presentation import ACTION_LABELS, format_time, format_weight, humanize

STEPS = ('Check', 'Ask for proof', 'Review reply', 'Finish')
STEP_OF = {'check': 0, 'approve': 1, 'send': 1, 'waiting': 2, 'review': 2, 'finish': 3, 'closed_ok': 3, 'closed_open': 3}
FRIENDLY = {'request_reweigh': '⚖️ Weigh it again', 'request_rephoto': '📷 Take a new photo',
            'request_rescan': '🔢 Count the packages', 'submit_to_contract_ops': '📋 Refer to operations'}
ROLE_NAMES = {'admin': 'Administrator', 'investigator': 'Investigator', 'approver': 'Supervisor', 'partner_user': 'Partner'}
ASK, FINISH = 'Ask the partner for proof', 'Finish the case'


def member_ids(case):
    return [c['case_id'] for c in case.get('member_cases') or []] or [case['case_id']]


def load(case):
    path, actor = context()
    ids = member_ids(case)
    actions = rows('SELECT action_id,case_id,action_type,status,reason,requested_by FROM action_requests WHERE case_id IN (' + ','.join('?' for _ in ids) + ') ORDER BY rowid DESC', tuple(ids))
    return list_tasks(path, case['case_id'], actor), actions


def phase_of(case, tasks, actions):
    """Single source of truth for the step shown on the page and on the 3D map."""
    if case['work_bucket'] == 'resolved':
        return 'closed_ok' if case.get('closure_outcome') == 'verified_resolved' else 'closed_open'
    if any(a['status'] == 'proposed' for a in actions):
        return 'approve'
    if any(a['status'] == 'approved' for a in actions):
        return 'send'
    if any(t['status'] == 'received' for t in tasks):
        return 'review'
    if any(t['status'] == 'open' for t in tasks):
        return 'waiting'
    if any(t['status'] == 'completed' for t in tasks):
        return 'finish'
    return 'check'


def switch_role(role):
    st.session_state.actor_role = role
    for key in ('role_widget', 'desktop-role', 'mobile-role'):
        st.session_state.pop(key, None)


def role_shortcut(role, why):
    st.info(why)
    st.button('Switch to ' + ROLE_NAMES[role] + ' (demo)', key='switch-' + role, on_click=switch_role, args=(role,), icon=':material/swap_horiz:')


def progress_html(phase):
    current = STEP_OF[phase]
    done = phase in ('closed_ok', 'closed_open')
    items = []
    for i, name in enumerate(STEPS):
        state = 'done' if i < current or done else 'current' if i == current else ''
        items.append('<li class="' + state + '"' + (' aria-current="step"' if state == 'current' else '') + '><span class="dot"></span><b>' + name + '</b></li>')
    fill = 100 if done else current * 100 / (len(STEPS) - 1)
    return '<ol class="pv-progress" style="--fill:' + format(fill, '.0f') + '%" aria-label="Review progress">' + ''.join(items) + '</ol>'


def request_choices(case, values):
    path, _ = context()
    categories = {f['category'] for f in case['findings']}
    choices = []
    if case['issue_type'] == 'shipment':
        if 'weight_diff' in categories or values['weight_g']['actual'] is None:
            choices.append('request_reweigh')
        if 'photo_reuse' in categories or not rows('SELECT p.photo_id FROM photos p JOIN events e ON p.event_id=e.event_id WHERE e.shipment_id=?', (case['shipment_id'],)):
            choices.append('request_rephoto')
        if 'count_discrepancy' in categories or values['count']['actual'] is None:
            choices.append('request_rescan')
        for extra in ('request_reweigh', 'request_rephoto', 'request_rescan'):
            if extra not in choices:
                choices.append(extra)
    choices.append('submit_to_contract_ops')
    return choices


def card(eyebrow, title, text=None):
    st.html('<p class="eyebrow">' + escape(eyebrow) + '</p><h3 class="step-title">' + escape(title) + '</h3>' + ('<p class="step-copy">' + escape(text) + '</p>' if text else ''))


def next_step(case, stations, selected, concern):
    """Render exactly one step. `stations` come from the 3D map so requests can target a record."""
    from ui import workspace_ui as work
    path, actor = context()
    tasks, actions = load(case)
    phase = phase_of(case, tasks, actions)
    role = actor['role']
    internal = role in ('admin', 'investigator', 'approver')
    by_id = {n['id']: n for n in stations}

    if phase in ('closed_ok', 'closed_open'):
        card('DONE', 'Case verified and closed' if phase == 'closed_ok' else 'Case closed with open questions',
             'The decision, its reason and every record stay saved. Reopen only if new information arrives.')
        st.success('Case closed: ' + humanize(case.get('closure_outcome') or 'closed_unresolved'))
        nxt = next_case_id(case['case_id'])
        if nxt:
            st.button('Go to the next case', key='next-case', type='primary', icon=':material/arrow_forward:', on_click=work.route, kwargs={'case_id': nxt}, use_container_width=True)
        if internal:
            with st.expander('Reopen this case'):
                reason = st.text_area('Why reopen this case?', key='reopen-reason')
                if st.button('Reopen for follow-up', key='reopen'):
                    try:
                        reopen_case(path, case['case_id'], actor, reason)
                        st.rerun()
                    except ValueError as error:
                        st.error(str(error))
        return phase

    if phase in ('approve', 'send'):
        action = next(a for a in actions if a['status'] == ('proposed' if phase == 'approve' else 'approved'))
        target = request_target(case, action['action_id'], by_id)
        card('STEP 2 · APPROVE', 'Approve the request' if phase == 'approve' else 'Send the approved request',
             'A second person checks the request before anything goes to the partner.' if phase == 'approve' else 'Approval is saved. Sending creates the task for the partner.')
        st.html('<div class="request-box"><b>' + escape(FRIENDLY.get(action['action_type'], ACTION_LABELS.get(action['action_type'], humanize(action['action_type'])))) + '</b>'
                + ('<span>at ' + escape(target) + '</span>' if target else '') + '<p>' + escape(action['reason'] or 'No reason recorded.') + '</p></div>')
        if role not in ('admin', 'approver'):
            role_shortcut('approver', 'A supervisor approves requests. In this demo you can switch roles to continue.')
            return phase
        if phase == 'approve' and action.get('requested_by') == actor['actor_id']:
            role_shortcut('approver', 'You proposed this request, so a different person must approve it. In this demo, switch to Supervisor to continue.')
            return phase
        if phase == 'approve':
            if (action.get('requested_by') or '').upper().startswith('AGENT-'):
                st.caption('Proposed by the AI review agent. It cannot approve or send anything; your decision is required.')
            note = st.text_area('Why do you approve or reject this? (required)', key='approval-note-' + action['action_id'],
                                placeholder='For example: the handover weight is outside tolerance and no repackaging is recorded.')
            ready = len(note.strip()) >= 10
            if not ready:st.caption('Write at least 10 characters to enable the decision buttons.')
            go, stop = st.columns([1.6, 1])
            if go.button('Approve & send to partner', type='primary', key='approve-send-' + action['action_id'], icon=':material/send:', use_container_width=True, disabled=not ready):
                try:
                    review_action(path, action['action_id'], 'approve', actor, note)
                except (ValueError, AuthorizationError) as error:
                    st.error(str(error));return phase
                result = execute_action(path, action['action_id'], actor)
                ok = result['status'] in ('executed', 'already_executed')
                work.notice('Approved and sent. The partner now has a task in this demo; no real message was sent.' if ok else 'Approved, but sending failed. Try Send again.', 'success' if ok else 'error')
                st.rerun()
            if stop.button('Reject', key='reject-' + action['action_id'], use_container_width=True, disabled=not ready):
                try:
                    review_action(path, action['action_id'], 'reject', actor, note)
                except (ValueError, AuthorizationError) as error:
                    st.error(str(error));return phase
                work.notice('Request rejected. Choose another step when ready.', 'info')
                st.rerun()
        else:
            if st.button('Send to partner', type='primary', key='apply-' + action['action_id'], icon=':material/send:', use_container_width=True):
                result = execute_action(path, action['action_id'], actor)
                ok = result['status'] in ('executed', 'already_executed')
                work.notice('Sent. The partner task is open; no real message was sent.' if ok else 'This step could not be sent.', 'success' if ok else 'error')
                st.rerun()
        return phase

    if phase == 'waiting':
        task = next(t for t in tasks if t['status'] == 'open')
        card('STEP 3 · WAITING', 'Waiting for ' + (case['partner_name'] or 'the partner'),
             task['description'] or 'The partner has been asked for proof.')
        if role in ('admin', 'investigator', 'partner_user'):
            st.caption('Demo: answer as the partner to see the rest of the flow.')
            partner_reply_form(task, path, actor)
        else:
            role_shortcut('admin', 'Approved and sent. The partner (or an investigator) supplies the reply next. In this demo, switch back to Administrator to enter it.')
        if internal:
            with st.expander('Stop waiting and close the case'):
                finish_form(case, phase, compare_handoff(path, case['shipment_id']), path, actor)
        return phase

    if phase == 'review':
        task = next(t for t in tasks if t['status'] == 'received')
        submission = rows("SELECT s.*,e.payload_json,e.occurred_at FROM task_submissions s JOIN events e ON s.event_id=e.event_id WHERE s.task_id=? AND s.review_status='pending' ORDER BY s.created_at DESC", (task['task_id'],))[0]
        payload = json.loads(submission['payload_json'])
        card('STEP 3 · REVIEW', 'Check the partner reply', 'Compare the new proof with the original record, then accept it or ask again.')
        values = compare_handoff(path, task['shipment_id'])
        if payload.get('weight_g') is not None:
            expected = values['weight_g']['expected']
            st.html('<div class="compare-pair"><div><span>Expected</span><b>' + escape(format_weight(expected)) + '</b></div><div class="arrow">→</div><div class="new"><span>New measurement</span><b>' + escape(format_weight(payload['weight_g'])) + '</b></div></div>')
        if payload.get('count') is not None and task['task_type'] == 'rescan':
            st.write('New package count: **' + str(payload['count']) + '** (expected ' + str(values['count']['expected']) + ')')
        if payload.get('notes'):
            st.html('<blockquote class="reply-note">' + escape(payload['notes']) + '</blockquote>')
        for photo in rows('SELECT local_path FROM photos WHERE event_id=?', (submission['event_id'],)):
            display_photo(photo['local_path'])
        st.caption('Recorded ' + format_time(submission['occurred_at']) + ' · received ' + format_time(submission['created_at']))
        if not internal:
            st.info('An internal reviewer checks this reply.')
            return phase
        reason = st.text_area('Review note', value='Checked the new evidence against the original record.', key='review-reason-' + submission['submission_id'])
        accept, more = st.columns([1.6, 1])
        for col, label, decision in ((accept, 'Accept evidence', 'accept'), (more, 'Ask again', 'request_more')):
            if col.button(label, type='primary' if decision == 'accept' else 'secondary', key=decision + '-' + submission['submission_id'], use_container_width=True):
                try:
                    review_task_response(path, submission['submission_id'], actor, decision, reason)
                    st.session_state.get('task_retry_keys', {}).pop(task['task_id'], None)
                    work.notice('Evidence accepted. You can finish the case now.' if decision == 'accept' else 'Asked the partner again. The task is open again.')
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
        return phase

    # check / finish
    if not internal:
        card('NEXT STEP', 'Nothing to do yet', 'An internal reviewer decides the next step. Any task for you appears here.')
        return phase
    values = compare_handoff(path, case['shipment_id'])
    can_ask = role in ('admin', 'investigator')
    card('STEP 1 · CHECK' if phase == 'check' else 'STEP 4 · FINISH',
         'What do you want to do?' if phase == 'check' else 'Ready to finish',
         concern + '.' if phase == 'check' else 'The reply was accepted. Record the outcome to close the case.')
    options = [ASK, FINISH] if can_ask else [FINISH]
    choice_key = 'choice-' + case['case_id']
    if st.session_state.get(choice_key) not in options:
        st.session_state[choice_key] = FINISH if phase == 'finish' or not can_ask else ASK
    choice = st.radio('What do you want to do?', options, key=choice_key, horizontal=True, label_visibility='collapsed')
    if choice == ASK:
        ask_form(case, values, concern, by_id, selected, path, actor)
    else:
        finish_form(case, phase, values, path, actor)
    return phase


def request_target(case, action_id, by_id):
    audit = rows("SELECT details_json FROM audit_log WHERE case_id IN (" + ','.join('?' for _ in member_ids(case)) + ") AND operation='action_proposed'", tuple(member_ids(case)))
    for row in audit:
        details = json.loads(row['details_json'])
        if details.get('action_id') == action_id and details.get('source_event_id') in by_id:
            return by_id[details['source_event_id']]['label']
    return None


def default_target(stations, selected):
    if selected in {n['id'] for n in stations if not n['missing']}:
        return selected
    problem = next((n for n in stations if n['status'] == 'Difference' and not n['missing']), None)
    return problem['id'] if problem else None


def ask_form(case, values, concern, by_id, selected, path, actor):
    from ui import workspace_ui as work
    choices = request_choices(case, values)
    type_key = 'request-type-' + case['case_id']
    preset = st.session_state.pop('scene_request_type', None)
    if preset in choices:
        st.session_state[type_key] = preset
    if st.session_state.get(type_key) not in choices:
        st.session_state[type_key] = choices[0]
    action_type = st.radio('What proof do you need?', choices, key=type_key, format_func=lambda a: FRIENDLY[a])
    target = default_target(list(by_id.values()), selected)
    if target:
        node = by_id[target]
        st.html('<div class="target-pill">📍 At <b>' + escape(node['label']) + '</b> · ' + escape(node['time']) + '<small>Tap another building on the map to change it</small></div>')
    initial = ('The handover weight is ' + work.difference_weight(values['weight_g']['diff']) + ' than the dispatch record. Please provide a fresh measurement.'
               if action_type == 'request_reweigh' and values['weight_g']['diff'] else concern + '. Please provide supporting proof.')
    reason = work.draft_input('text_area', 'Message to the partner', case['case_id'], 'request-reason', value=initial, max_chars=2000)
    st.caption('Nothing leaves this demo. A supervisor approves the request first.')
    if st.button('Send request', type='primary', key='send-request-' + case['case_id'], icon=':material/arrow_forward:', use_container_width=True):
        if len(reason.strip()) < 10:
            st.error('Write a short message of at least 10 characters. Your draft is kept.')
            return
        source = target if action_type != 'submit_to_contract_ops' else None
        fingerprint = hashlib.sha256(json.dumps([case['case_id'], actor['actor_id'], action_type, reason.strip(), source]).encode()).hexdigest()
        request_id = st.session_state.setdefault('proposal_ids', {}).setdefault(fingerprint, str(uuid.uuid4()))
        try:
            result = propose_action(path, case['case_id'], action_type, actor, reason=reason.strip(), request_id=request_id, source_event_id=source)
        except (ValueError, AuthorizationError, IdempotencyError) as error:
            st.error(str(error))
            return
        work.notice('Request created. Next: a supervisor approves it.' if result['status'] == 'proposed' else 'This request already has a decision. Change the message to send another.', 'success')
        st.rerun()


def finish_form(case, phase, values, path, actor):
    from ui import workspace_ui as work
    outcome_key = 'outcome-' + case['case_id']
    labels = {'verified_resolved': '✅ Verified — the evidence checks out', 'closed_unresolved': '⚠️ Close with open questions'}
    if st.session_state.get(outcome_key) not in labels:
        st.session_state[outcome_key] = 'verified_resolved' if phase == 'finish' else 'closed_unresolved'
    outcome = st.radio('Outcome', list(labels), key=outcome_key, format_func=labels.get)
    default = ('The partner supplied proof that resolves the recorded difference.' if outcome == 'verified_resolved'
               else 'Reviewed the records; some facts remain unconfirmed and are kept open in the record.')
    reason = st.text_area('Why?', value=default, key='finish-reason-' + case['case_id'] + '-' + outcome)
    confirmed = st.checkbox('I checked the evidence and this outcome.', key='finish-confirm-' + case['case_id'])
    if actor['role'] not in ('admin', 'approver'):
        role_shortcut('approver', 'A supervisor closes cases. In this demo you can switch roles to finish.')
        return
    if st.button('Finish case', type='primary', key='finish-' + case['case_id'], icon=':material/task_alt:', use_container_width=True):
        if not confirmed:
            st.error('Tick “I checked the evidence” first.')
            return
        try:
            finish_case(case, outcome, reason, path, actor)
        except (ValueError, AuthorizationError) as error:
            st.error(friendly_close_error(str(error)))
            return
        work.notice('Case closed. Nice work.')
        st.rerun()


def finish_case(case, outcome, reason, path, actor):
    """Record finding reviews (verified outcome only) and close — prechecked so nothing is half-written."""
    ctx = get_case_context(path, case['case_id'], actor)
    evidence = sorted({r['event_id'] for sid in ctx['shipment_ids'] for r in rows('SELECT event_id FROM events WHERE shipment_id=?', (sid,))})
    if outcome == 'verified_resolved':
        tasks = list_tasks(path, case['case_id'], actor)
        if any(t['status'] in ('open', 'received') for t in tasks):
            raise ValueError('Verified resolution requires supported finding outcomes and reviewed evidence tasks')
        if any(compare_handoff(path, sid)['unknowns'] for sid in ctx['shipment_ids']):
            raise ValueError('Required measurements or confirmation remain missing; use unresolved closure or collect evidence')
        for finding in ctx['findings']:
            if finding['required'] and finding['state'] not in ('supported', 'resolved'):
                refs = finding['evidence_ids'] or evidence
                review_finding(path, finding['finding_id'], actor, 'resolved', reason, refs)
    close_case(path, case['case_id'], actor, outcome, reason, evidence if outcome == 'verified_resolved' else [])


def friendly_close_error(message):
    if 'missing' in message.lower():
        return 'Can’t mark this as verified yet: some measurements or confirmations are still missing. Ask the partner for proof, or choose “Close with open questions”.'
    if 'tasks' in message.lower():
        return 'Can’t mark this as verified while a partner task is still open. Review the reply first, or choose “Close with open questions”.'
    return message


def partner_reply_form(task, path, actor):
    from ui import workspace_ui as work
    values = compare_handoff(path, task['shipment_id'])
    with st.form('partner-' + task['task_id']):
        weight = st.text_input('New weight (kg)', placeholder='e.g. 1.85') if task['task_type'] == 'reweigh' or values['weight_g']['actual'] is None else ''
        count = st.text_input('Package count') if task['task_type'] == 'rescan' else ''
        photo = st.file_uploader('Photo', type=['jpg', 'jpeg', 'png']) if task['task_type'] in ('rephoto', 'reweigh') else None
        note = st.text_area('Message from the partner', placeholder='What did you check?')
        with st.expander('When was this checked?'):
            default_time = st.session_state.setdefault('task_recorded_times', {}).setdefault(task['task_id'], datetime.now(timezone.utc).isoformat())
            occurred = st.text_input('Check time (ISO 8601)', value=default_time, key='task-event-time-' + task['task_id'])
        submit = st.form_submit_button('Send reply as partner', type='primary', use_container_width=True)
    if submit:
        try:
            payload = {'notes': note}
            if weight:
                payload['weight_g'] = float(Decimal(weight) * 1000)
                if values['count']['actual'] is not None:
                    payload['count'] = values['count']['actual']
                if values['seal']['actual'] is not None:
                    payload['seal_id'] = values['seal']['actual']
                payload['inherited_from_event_id'] = values['measurement_event_id']
            if count:
                payload['count'] = int(count)
            key = st.session_state.setdefault('task_retry_keys', {}).setdefault(task['task_id'], str(uuid.uuid4()))
            submit_task_response(path, task['task_id'], actor, payload, occurred, file_bytes=photo.getvalue() if photo else None, submission_key=key)
            work.notice('Reply received. Next: review it.')
            st.rerun()
        except (ValueError, ArithmeticError, InvalidOperation, AuthorizationError) as error:
            st.error(str(error))


def next_case_id(current):
    from ui import workspace_ui as work
    queue = sorted((c for c in work.cases() if c['work_bucket'] == 'needs_review' and c['case_id'] != current), key=lambda c: c['priority_score'] or 0, reverse=True)
    return queue[0]['case_id'] if queue else None
