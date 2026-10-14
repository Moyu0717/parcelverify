"""Authorized review cohorts and audited manual dispositions."""
from __future__ import annotations

import json
from contracts import ActorContext, AuthorizationError, RULE_VERSION
from db import get_connection
from services.access import _is_authorized, _utc_now_iso
from services.audit import append_audit
from services.handoff import create_or_update_case


def list_review_cases(db_path: str, actor_context: dict) -> list[dict]:
    actor = ActorContext(**actor_context)
    now = _utc_now_iso()
    with get_connection(db_path) as conn:
        rows = conn.execute("""SELECT c.case_id,c.shipment_id,c.partner_id,p.name,
            c.status,c.priority_score,c.findings_json,c.updated_at,c.triggering_event_id
            FROM case_records c LEFT JOIN partners p ON p.partner_id=c.partner_id
            ORDER BY c.updated_at DESC,c.case_id""").fetchall()
        result = []
        for row in rows:
            if not _is_authorized(conn, actor, row[1], now)[0]:
                continue
            states = {r[0] for r in conn.execute(
                "SELECT status FROM action_requests WHERE case_id=?", (row[0],))}
            tasks = bool(conn.execute("SELECT 1 FROM evidence_tasks WHERE case_id=? AND status='open'", (row[0],)).fetchone())
            proposed, approved = 'proposed' in states, 'approved' in states
            if row[4] == 'closed':
                bucket = 'resolved'
            elif proposed:
                bucket = 'awaiting_approval'
            elif approved or tasks or states & {'rejected', 'failed'} or row[4] != 'review_completed':
                bucket = 'needs_review'
            else:
                bucket = 'review_complete'
            result.append(dict(case_id=row[0], shipment_id=row[1], partner_id=row[2],
                partner_name=row[3], status=row[4], priority_score=row[5],
                findings=json.loads(row[6] or '[]'), updated_at=row[7],
                issue_type='access' if (row[8] or '').startswith('access:') else 'shipment',
                has_open_tasks=tasks, has_proposed_actions=proposed,
                has_approved_actions=approved, work_bucket=bucket))
        return result


def review_counts(cases: list[dict]) -> dict:
    counts = dict.fromkeys(('needs_review', 'awaiting_approval', 'waiting_evidence', 'resolved', 'review_complete'), 0)
    for case in cases:
        counts[case['work_bucket']] += 1
    return counts


def ensure_access_cases(db_path: str, actor_context: dict) -> int:
    actor = ActorContext(**actor_context)
    if actor.role not in ('admin', 'investigator'):
        raise AuthorizationError('Only internal investigators and admins can materialize access reviews')
    with get_connection(db_path) as conn:
        rows = conn.execute("""SELECT l.log_id,l.shipment_id,l.actor_id,l.batch_job_id
            FROM access_logs l JOIN shipments s ON s.shipment_id=l.shipment_id
            WHERE l.outcome='denied' AND NOT EXISTS
            (SELECT 1 FROM case_records c WHERE c.shipment_id=l.shipment_id
            AND c.triggering_event_id='access:' || l.log_id)""").fetchall()
    count = 0
    for log_id, shipment_id, actor_id, batch_job_id in rows:
        finding = dict(category='access_anomaly', severity='blocking', evidence_ids=[log_id],
            description=f'Access gate blocked unauthorized query by {actor_id}. '
            'This is an access review, not evidence of shipment fraud. '
            + (f'Batch job {batch_job_id} may explain the attempt; legitimate batch context requires review.'
               if batch_job_id else 'Intent and legitimate batch context are unknown.'))
        case = create_or_update_case(db_path, shipment_id, 'access:' + log_id, [finding], RULE_VERSION)
        count += int(case['is_new'])
    return count


def record_review_decision(db_path: str, case_id: str, actor_context: dict,
                           decision: str, reason: str) -> dict:
    actor = ActorContext(**actor_context)
    roles = {'review_complete': ('admin', 'investigator', 'approver'), 'close': ('admin', 'approver')}
    if decision not in roles:
        raise ValueError('Unsupported review decision')
    if actor.role not in roles[decision]:
        raise AuthorizationError('Role cannot record this review decision')
    if not isinstance(reason, str) or len(reason.strip()) < 10:
        raise ValueError('A meaningful reason of at least 10 characters is required')
    reason = reason.strip()
    status = 'closed' if decision == 'close' else 'review_completed'
    with get_connection(db_path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        case = conn.execute('SELECT status FROM case_records WHERE case_id=?', (case_id,)).fetchone()
        if not case:
            raise ValueError('Case not found')
        prior = conn.execute("SELECT details_json FROM audit_log WHERE case_id=? AND operation='review_decision' ORDER BY occurred_at DESC LIMIT 1", (case_id,)).fetchone()
        if case[0] == status and prior:
            details = json.loads(prior[0])
            if details.get('decision') == decision and details.get('reason') == reason:
                return dict(case_id=case_id, status=status, is_new=False)
        if case[0] == 'closed' and decision != 'close':
            raise ValueError('Closed cases cannot be reopened by review completion')
        closed_tasks = []
        now = _utc_now_iso()
        if decision == 'close':
            if conn.execute("SELECT 1 FROM action_requests WHERE case_id=? AND status IN ('proposed','approved')", (case_id,)).fetchone():
                raise ValueError('Outstanding proposed or approved actions must be settled before closure')
            closed_tasks = [r[0] for r in conn.execute("SELECT task_id FROM evidence_tasks WHERE case_id=? AND status='open'", (case_id,))]
            resolution = json.dumps(dict(disposition='manual_case_closure', reason=reason,
                evidence_verified=False, closed_by=actor.actor_id))
            conn.execute("UPDATE evidence_tasks SET status='closed',closed_at=?,resolution_json=? WHERE case_id=? AND status='open'", (now, resolution, case_id))
        conn.execute('UPDATE case_records SET status=?,updated_at=? WHERE case_id=?', (status, now, case_id))
        append_audit(db_path, actor.actor_id, case_id, 'review_decision',
            dict(decision=decision, reason=reason, previous_status=case[0], status=status,
                 closed_task_ids=closed_tasks, evidence_verified=False), tx=conn)
    return dict(case_id=case_id, status=status, is_new=True)
