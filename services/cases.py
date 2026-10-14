"""Bounded case linkage, permitted findings and explicit human outcomes."""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from contracts import ActorContext, AuthorizationError
from db import get_connection
from services.access import _is_authorized, _utc_now_iso
from services.audit import append_audit

def require_case(conn,case_id,actor):
    row=conn.execute('SELECT shipment_id FROM case_records WHERE case_id=?',(case_id,)).fetchone()
    if not row or not _is_authorized(conn,actor,row[0],_utc_now_iso())[0]:
        raise AuthorizationError('Case is not permitted for the current identity')
    if actor.partner_id and conn.execute('SELECT partner_id FROM shipments WHERE shipment_id=?',row).fetchone()[0]!=actor.partner_id:raise AuthorizationError('Case is outside the current partner scope')
    return row[0]

def ensure_case_links(db_path,actor_context):
    actor=ActorContext(**actor_context)
    if actor.role not in ('admin','investigator'):raise AuthorizationError('Only investigators can link findings')
    with get_connection(db_path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        records=conn.execute('SELECT case_id,shipment_id,triggering_event_id,findings_json,created_at FROM case_records ORDER BY created_at,case_id').fetchall()
        by_shipment={}
        for row in records:by_shipment.setdefault(row[1],[]).append(row)
        roots={sid:next((r[0] for r in group if not (r[2] or '').startswith('access:')),group[0][0]) for sid,group in by_shipment.items()}
        # Only an actual exact-match detector finding can join a second shipment.
        for row in records:
            for finding in json.loads(row[3] or '[]'):
                if finding.get('category')!='photo_reuse':continue
                ids=finding.get('evidence_ids',[])
                if not ids:continue
                related=conn.execute('SELECT DISTINCT e.shipment_id FROM photos p JOIN events e ON e.event_id=p.event_id WHERE p.photo_id IN ('+','.join('?' for _ in ids)+')',ids).fetchall()
                for (sid,) in related:
                    if sid in roots and sid!=row[1]:
                        target=min((roots[sid],roots[row[1]]),key=lambda cid:next((r[4],r[0]) for r in records if r[0]==cid))
                        previous=roots[sid] if target==roots[row[1]] else roots[row[1]]
                        for key,value in list(roots.items()):
                            if value==previous:roots[key]=target
        for cid,sid,trigger,encoded,created in records:
            parent=roots[sid]
            reason='Same shipment investigation' if next(r[1] for r in records if r[0]==parent)==sid else 'Exact reused photo connects these shipment records'
            conn.execute('INSERT INTO case_members VALUES(?,?,?,?) ON CONFLICT(member_case_id) DO UPDATE SET parent_case_id=excluded.parent_case_id,linkage_reason=excluded.linkage_reason',(parent,cid,reason,_utc_now_iso()))
            if cid!=parent and conn.execute('SELECT status FROM case_records WHERE case_id=?',(cid,)).fetchone()[0]!='closed' and conn.execute('SELECT status FROM case_records WHERE case_id=?',(parent,)).fetchone()[0]=='closed':
                conn.execute("UPDATE case_records SET status='pending_review',updated_at=? WHERE case_id=?",(_utc_now_iso(),parent))
                append_audit(db_path,actor.actor_id,parent,'case_reopened',dict(reason='A newly detected linked finding requires follow-up',member_case_id=cid),tx=conn)
            for finding in json.loads(encoded or '[]'):
                fid='F-'+hashlib.sha256((cid+json.dumps(finding,sort_keys=True)).encode()).hexdigest()[:24]
                conn.execute('INSERT OR IGNORE INTO case_findings VALUES(?,?,?,?,?,?)',(fid,cid,finding['category'],finding['description'],json.dumps(finding.get('evidence_ids',[])),int(finding.get('severity')!='info')))

def get_case_context(db_path,case_id,actor_context):
    actor=ActorContext(**actor_context)
    with get_connection(db_path) as conn:
        require_case(conn,case_id,actor)
        parent=conn.execute('SELECT parent_case_id FROM case_members WHERE member_case_id=?',(case_id,)).fetchone()
        root=parent[0] if parent else case_id
        try:require_case(conn,root,actor)
        except AuthorizationError:root=case_id
        conn.row_factory=__import__('sqlite3').Row
        members=conn.execute('SELECT c.*,p.name partner_name,m.linkage_reason FROM case_records c LEFT JOIN partners p ON c.partner_id=p.partner_id LEFT JOIN case_members m ON m.member_case_id=c.case_id WHERE c.case_id=? OR m.parent_case_id=? ORDER BY c.created_at,c.case_id',(root,root)).fetchall()
        permitted=[];findings=[]
        for row in members:
            if not _is_authorized(conn,actor,row['shipment_id'],_utc_now_iso())[0] or (actor.partner_id and row['partner_id']!=actor.partner_id):continue
            # A restricted root is displayed alone, without revealing its graph.
            if root==case_id and parent and parent[0]!=root and row['case_id']!=case_id:continue
            item=dict(row);item['findings']=json.loads(item.pop('findings_json') or '[]')
            for f in item['findings']:
                f['evidence_ids']=[eid for eid in f.get('evidence_ids',[]) if permitted_evidence(conn,eid,actor)]
                if f.get('category')=='photo_reuse':f['description']='A recorded photo matches another submission. Compare only permitted sources.'
            item.pop('report_json',None);permitted.append(item)
            for f in conn.execute('SELECT f.*,r.outcome state,r.reason review_reason,r.evidence_ids_json reviewed_evidence FROM case_findings f LEFT JOIN finding_reviews r ON f.finding_id=r.finding_id WHERE f.case_id=?',(row['case_id'],)):
                finding=dict(f);finding['evidence_ids']=json.loads(finding.pop('evidence_ids_json'));finding['state']=finding['state'] or 'unreviewed'
                # Never expose a cross-object citation solely through a link.
                finding['evidence_ids']=[eid for eid in finding['evidence_ids'] if permitted_evidence(conn,eid,actor)]
                if finding['category']=='photo_reuse':finding['description']='A recorded photo matches another submission. Compare only permitted sources.'
                finding.pop('reviewed_evidence',None)
                findings.append(finding)
        return dict(case_id=root,cases=permitted,shipment_ids=sorted({r['shipment_id'] for r in permitted}),findings=findings,linkage_reasons=list(dict.fromkeys(r['linkage_reason'] or 'Original finding' for r in permitted)))

def list_cases(db_path,actor_context):
    from services.review import list_review_cases
    raw=list_review_cases(db_path,actor_context);result={}
    for record in raw:
        ctx=get_case_context(db_path,record['case_id'],actor_context)
        root=ctx['case_id']
        if root in result:continue
        anchor=next((r for r in raw if r['case_id']==root),record).copy()
        ids=[r['case_id'] for r in ctx['cases']]
        with get_connection(db_path) as conn:
            marks=','.join('?' for _ in ids)
            task_states=[r[0] for r in conn.execute('SELECT status FROM evidence_tasks WHERE case_id IN ('+marks+')',ids)]
            action_states=[r[0] for r in conn.execute('SELECT status FROM action_requests WHERE case_id IN ('+marks+')',ids)]
            decision=conn.execute('SELECT outcome FROM case_decisions WHERE case_id=? ORDER BY created_at DESC LIMIT 1',(root,)).fetchone()
        closed=all(r['status']=='closed' for r in ctx['cases'])
        bucket='resolved' if closed else 'awaiting_approval' if 'proposed' in action_states else 'needs_review' if 'approved' in action_states or 'received' in task_states else 'waiting_evidence' if 'open' in task_states else 'needs_review'
        anchor.update(work_bucket=bucket,display_status={'resolved':'Closed','awaiting_approval':'Waiting for approval','needs_review':'Needs review','waiting_evidence':'Waiting for evidence'}[bucket],findings=[f for r in ctx['cases'] for f in r['findings']],member_cases=ctx['cases'],linked_findings=ctx['findings'],shipment_ids=ctx['shipment_ids'],open_task_count=task_states.count('open'),received_task_count=task_states.count('received'),closure_outcome=decision[0] if decision else None,has_proposed_actions='proposed' in action_states,has_approved_actions='approved' in action_states,has_open_tasks='open' in task_states)
        anchor['contains_access']=any(f['category'] in ('access_anomaly','authorized_export') for f in ctx['findings'])
        if any(f['category']=='authorized_export' for f in ctx['findings']):anchor['issue_type']='shipment'
        result[root]=anchor
    return list(result.values())

def permitted_evidence(conn,evidence_id,actor):
    row=conn.execute('SELECT shipment_id FROM events WHERE event_id=? UNION SELECT e.shipment_id FROM photos p JOIN events e ON p.event_id=e.event_id WHERE p.photo_id=? UNION SELECT shipment_id FROM access_logs WHERE log_id=?',(evidence_id,evidence_id,evidence_id)).fetchone()
    return bool(row and _is_authorized(conn,actor,row[0],_utc_now_iso())[0] and (not actor.partner_id or conn.execute('SELECT partner_id FROM shipments WHERE shipment_id=?',row).fetchone()[0]==actor.partner_id))

def review_finding(db_path,finding_id,actor_context,outcome,reason,evidence_ids):
    actor=ActorContext(**actor_context)
    if actor.role not in ('admin','investigator','approver'):raise AuthorizationError('Only an internal reviewer can resolve findings')
    if outcome not in ('supported','resolved','unresolved') or len(reason.strip())<10:raise ValueError('Provide a valid outcome and a meaningful review reason')
    with get_connection(db_path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute('SELECT case_id,evidence_ids_json FROM case_findings WHERE finding_id=?',(finding_id,)).fetchone()
        if not row:raise ValueError('Finding not found')
        require_case(conn,row[0],actor)
        if outcome!='unresolved' and not evidence_ids:raise ValueError('A supported outcome requires cited evidence')
        scope=get_case_context(db_path,row[0],actor_context)['shipment_ids']
        for eid in evidence_ids:
            if not permitted_evidence(conn,eid,actor):raise AuthorizationError('Review cites unavailable evidence')
            shipment=conn.execute('SELECT shipment_id FROM events WHERE event_id=? UNION SELECT e.shipment_id FROM photos p JOIN events e ON e.event_id=p.event_id WHERE p.photo_id=? UNION SELECT shipment_id FROM access_logs WHERE log_id=?',(eid,eid,eid)).fetchone()
            if shipment[0] not in scope:raise ValueError('Evidence must belong to this permitted investigation')
        previous=conn.execute('SELECT outcome,reason,evidence_ids_json FROM finding_reviews WHERE finding_id=?',(finding_id,)).fetchone()
        values=(outcome,reason.strip(),json.dumps(sorted(set(evidence_ids))))
        if previous==values:return {'is_new':False}
        conn.execute('INSERT OR REPLACE INTO finding_reviews VALUES(?,?,?,?,?,?)',(finding_id,*values,actor.actor_id,_utc_now_iso()))
        append_audit(db_path,actor.actor_id,row[0],'finding_reviewed',dict(finding_id=finding_id,outcome=outcome,reason=reason.strip(),evidence_ids=evidence_ids),tx=conn)
    return {'is_new':True}

def close_case(db_path,case_id,actor_context,outcome,reason,evidence_ids=None):
    actor=ActorContext(**actor_context)
    if actor.role not in ('admin','approver'):raise AuthorizationError('Only supervisors can close a case')
    if outcome not in ('verified_resolved','closed_unresolved') or len(reason.strip())<10:raise ValueError('Choose an outcome and record a meaningful reason')
    ctx=get_case_context(db_path,case_id,actor_context);ids=[c['case_id'] for c in ctx['cases']];marks=','.join('?' for _ in ids)
    unresolved=[f['finding_id'] for f in ctx['findings'] if f['required'] and f['state'] not in ('supported','resolved')]
    with get_connection(db_path) as conn:
        conn.execute('BEGIN IMMEDIATE');require_case(conn,case_id,actor)
        tasks=conn.execute('SELECT task_id,status FROM evidence_tasks WHERE case_id IN ('+marks+") AND status IN ('open','received')",ids).fetchall()
        unresolved=[r[0] for r in conn.execute('SELECT f.finding_id FROM case_findings f LEFT JOIN finding_reviews r ON r.finding_id=f.finding_id WHERE f.case_id IN ('+marks+") AND f.required=1 AND (r.outcome IS NULL OR r.outcome='unresolved')",ids)]
        if outcome=='verified_resolved' and (unresolved or tasks):raise ValueError('Verified resolution requires supported finding outcomes and reviewed evidence tasks')
        if outcome=='verified_resolved' and not evidence_ids:raise ValueError('Verified closure needs supporting evidence references')
        if outcome=='verified_resolved':
            from services.handoff import compare_handoff
            if any(compare_handoff(db_path,sid)['unknowns'] for sid in ctx['shipment_ids']):raise ValueError('Required measurements or confirmation remain missing; use unresolved closure or collect evidence')
        if conn.execute('SELECT 1 FROM action_requests WHERE case_id IN ('+marks+") AND status IN ('proposed','approved')",ids).fetchone():raise ValueError('Settle pending proposals before closing the case')
        for eid in evidence_ids or []:
            if not permitted_evidence(conn,eid,actor):raise AuthorizationError('Closure cites unavailable evidence')
            scope=conn.execute('SELECT shipment_id FROM events WHERE event_id=? UNION SELECT e.shipment_id FROM photos p JOIN events e ON e.event_id=p.event_id WHERE p.photo_id=? UNION SELECT shipment_id FROM access_logs WHERE log_id=?',(eid,eid,eid)).fetchone()
            if scope[0] not in ctx['shipment_ids']:raise ValueError('Closure evidence is outside this case')
        previous=conn.execute('SELECT outcome,reason FROM case_decisions WHERE case_id=? ORDER BY created_at DESC LIMIT 1',(ctx['case_id'],)).fetchone()
        closed=conn.execute('SELECT status FROM case_records WHERE case_id=?',(ctx['case_id'],)).fetchone()[0]=='closed'
        if closed and previous==(outcome,reason.strip()):return {'is_new':False,'outcome':outcome}
        resolution=json.dumps(dict(disposition='cancelled_by_closure',reason=reason.strip(),evidence_verified=False,actor_id=actor.actor_id))
        conn.execute("UPDATE evidence_tasks SET status='cancelled',closed_at=?,resolution_json=? WHERE case_id IN ("+marks+") AND status IN ('open','received')",[_utc_now_iso(),resolution,*ids])
        conn.execute("UPDATE case_records SET status='closed',updated_at=? WHERE case_id IN ("+marks+')',[_utc_now_iso(),*ids])
        conn.execute('INSERT INTO case_decisions VALUES(?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),ctx['case_id'],outcome,reason.strip(),json.dumps(evidence_ids or []),json.dumps(unresolved),actor.actor_id,_utc_now_iso()))
        append_audit(db_path,actor.actor_id,ctx['case_id'],'case_closed',dict(outcome=outcome,reason=reason.strip(),unresolved_findings=unresolved,cancelled_task_ids=[t[0] for t in tasks],evidence_verified=outcome=='verified_resolved'),tx=conn)
    return {'is_new':True,'outcome':outcome}

def reopen_case(db_path,case_id,actor_context,reason):
    actor=ActorContext(**actor_context)
    if actor.role not in ('admin','investigator','approver'):raise AuthorizationError('Only internal reviewers can reopen')
    if len(reason.strip())<10:raise ValueError('Record why follow-up is needed')
    ctx=get_case_context(db_path,case_id,actor_context)
    with get_connection(db_path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        if conn.execute('SELECT status FROM case_records WHERE case_id=?',(ctx['case_id'],)).fetchone()[0]!='closed':return {'is_new':False}
        for case in ctx['cases']:conn.execute("UPDATE case_records SET status='pending_review',updated_at=? WHERE case_id=?",(_utc_now_iso(),case['case_id']))
        append_audit(db_path,actor.actor_id,ctx['case_id'],'case_reopened',dict(reason=reason.strip()),tx=conn)
    return {'is_new':True}
