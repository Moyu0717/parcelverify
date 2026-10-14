"""Permission-checked task responses and human acceptance, with atomic audit writes."""
import hashlib
import json
import math
import uuid
from pathlib import Path
from contracts import ActorContext, AuthorizationError, IdempotencyError
from db import get_connection, _validate_image, _compute_phash, _MAX_PHOTO_BYTES
from services.access import _is_authorized, _utc_now_iso, _parse_time
from services.audit import append_audit
from services.cases import require_case, get_case_context

def list_tasks(db_path,case_id,actor_context):
    ctx=get_case_context(db_path,case_id,actor_context);ids=[c['case_id'] for c in ctx['cases']]
    with get_connection(db_path) as conn:
        conn.row_factory=__import__('sqlite3').Row
        tasks=conn.execute('SELECT t.*,c.shipment_id,c.partner_id FROM evidence_tasks t JOIN case_records c ON c.case_id=t.case_id WHERE t.case_id IN ('+','.join('?' for _ in ids)+') ORDER BY t.created_at',ids).fetchall()
        return [dict(t) for t in tasks]

def submit_task_response(db_path,task_id,actor_context,payload,occurred_at,*,file_bytes=None,submission_key):
    actor=ActorContext(**actor_context)
    if actor.role not in ('admin','investigator','partner_user'):raise AuthorizationError('Supervisors review evidence rather than submit it')
    if not isinstance(payload,dict) or not submission_key:raise ValueError('Provide evidence and a retry reference')
    allowed={'count','weight_g','seal_id','notes','location_lat','location_lon','recipient_name','inherited_from_event_id'}
    if set(payload)-allowed:raise ValueError('Unsupported response fields')
    for key in ('weight_g','count','location_lat','location_lon'):
        if key in payload and (isinstance(payload[key],bool) or not isinstance(payload[key],(int,float)) or not math.isfinite(payload[key])):raise ValueError('Measurements must be finite numbers')
    if 'weight_g' in payload and payload['weight_g']<0:raise ValueError('Weight cannot be negative')
    if 'count' in payload and (payload['count']<0 or int(payload['count'])!=payload['count']):raise ValueError('Quantity must be a whole number')
    recorded=_parse_time(occurred_at)
    if recorded>_parse_time(_utc_now_iso()):raise ValueError('Submitted evidence cannot have a future recorded time')
    fmt=None
    if file_bytes:
        if len(file_bytes)>_MAX_PHOTO_BYTES:raise ValueError('Photo exceeds 10 MB')
        fmt=_validate_image(file_bytes)
    intent=hashlib.sha256(json.dumps([task_id,actor.actor_id,payload,occurred_at,hashlib.sha256(file_bytes or b'').hexdigest()],sort_keys=True).encode()).hexdigest()
    created_file=None
    try:
        with get_connection(db_path) as conn:
            conn.execute('BEGIN IMMEDIATE')
            task=conn.execute('SELECT t.case_id,t.task_type,t.status,c.shipment_id,c.partner_id FROM evidence_tasks t JOIN case_records c ON c.case_id=t.case_id WHERE task_id=?',(task_id,)).fetchone()
            if not task:raise ValueError('Task not found')
            cid,kind,status,sid,pid=task
            require_case(conn,cid,actor)
            if payload.get('inherited_from_event_id'):
                inherited=conn.execute('SELECT shipment_id,payload_json FROM events WHERE event_id=?',(payload['inherited_from_event_id'],)).fetchone()
                if not inherited or inherited[0]!=sid:raise ValueError('Inherited facts must reference this shipment')
                prior=json.loads(inherited[1])
                if any(payload.get(key)!=prior.get(key) for key in ('count','seal_id') if key in payload):raise ValueError('Inherited count or seal does not match its source record')
            if not _is_authorized(conn,actor,sid,occurred_at)[0]:raise AuthorizationError('The author was not assigned at the recorded time')
            previous=conn.execute('SELECT submission_id,intent_hash,event_id,photo_id FROM task_submissions WHERE submission_key=?',(submission_key,)).fetchone()
            if previous:
                if previous[1]!=intent:raise IdempotencyError('Retry reference belongs to different evidence')
                return dict(submission_id=previous[0],event_id=previous[2],photo_id=previous[3],is_new=False)
            if status not in ('open','cancelled'):raise ValueError('This task already has a response awaiting review or completion')
            if kind=='reweigh' and 'weight_g' not in payload:raise ValueError('This task needs a new weight measurement')
            if kind=='rephoto' and not file_bytes:raise ValueError('This task needs a new photo')
            if kind=='rescan' and 'count' not in payload:raise ValueError('This task needs a package count')
            if kind=='supplementary_statement' and len(str(payload.get('notes','')).strip())<10:raise ValueError('Explain the requested context in at least 10 characters')
            now=_utc_now_iso();eid=str(uuid.uuid4());photo_id=None
            event_type='weight_measured' if kind=='reweigh' or 'weight_g' in payload else 'handoff_submitted' if kind in ('rescan','rephoto') else 'message_reported'
            conn.execute('INSERT INTO events(event_id,shipment_id,partner_id,actor_id,event_type,occurred_at,received_at,source,payload_json) VALUES(?,?,?,?,?,?,?,?,?)',(eid,sid,pid,actor.actor_id,event_type,occurred_at,now,'task_response:'+task_id,json.dumps(payload)))
            if file_bytes:
                directory=Path(db_path).resolve().parent/'photos';directory.mkdir(exist_ok=True)
                existing=[p for p in directory.iterdir() if p.is_file()]
                if len(existing)>=25 or sum(p.stat().st_size for p in existing)+len(file_bytes)>50*1024*1024:raise ValueError('Workspace photo capacity reached')
                photo_id=str(uuid.uuid4());created_file=directory/(photo_id+('.jpg' if fmt=='JPEG' else '.png'))
                created_file.write_bytes(file_bytes)
                conn.execute('INSERT INTO photos VALUES(?,?,?,?,?,?,?,?,?)',(photo_id,eid,str(created_file),hashlib.sha256(file_bytes).hexdigest(),_compute_phash(file_bytes),now,occurred_at,'task_upload',str(payload.get('notes',''))))
            submission_id=str(uuid.uuid4())
            conn.execute('INSERT INTO task_submissions(submission_id,task_id,submission_key,intent_hash,event_id,photo_id,actor_id,created_at) VALUES(?,?,?,?,?,?,?,?)',(submission_id,task_id,submission_key,intent,eid,photo_id,actor.actor_id,now))
            conn.execute("UPDATE evidence_tasks SET status='received',resolution_json=? WHERE task_id=?",(json.dumps(dict(submission_id=submission_id,evidence_verified=False)),task_id))
            parent=conn.execute('SELECT parent_case_id FROM case_members WHERE member_case_id=?',(cid,)).fetchone()
            root=parent[0] if parent else cid
            conn.execute("UPDATE case_records SET status='pending_review',updated_at=? WHERE case_id=? OR case_id IN (SELECT member_case_id FROM case_members WHERE parent_case_id=?)",(now,root,root))
            append_audit(db_path,actor.actor_id,cid,'evidence_submitted',dict(task_id=task_id,submission_id=submission_id,event_id=eid,photo_id=photo_id,previous_task_status=status,reopened=status=='cancelled'),tx=conn)
        return dict(submission_id=submission_id,event_id=eid,photo_id=photo_id,is_new=True)
    except Exception:
        if created_file and created_file.parent==Path(db_path).resolve().parent/'photos':created_file.unlink(missing_ok=True)
        raise

def review_task_response(db_path,submission_id,actor_context,decision,reason):
    actor=ActorContext(**actor_context)
    if actor.role not in ('admin','investigator','approver'):raise AuthorizationError('Only internal reviewers can accept task evidence')
    if decision not in ('accept','request_more') or len(reason.strip())<10:raise ValueError('Record a review decision and meaningful reason')
    with get_connection(db_path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute('SELECT s.task_id,s.review_status,s.event_id,t.case_id FROM task_submissions s JOIN evidence_tasks t ON t.task_id=s.task_id WHERE submission_id=?',(submission_id,)).fetchone()
        if not row:raise ValueError('Response not found')
        require_case(conn,row[3],actor)
        status='accepted' if decision=='accept' else 'more_requested'
        if row[1]==status:return {'is_new':False}
        if row[1]!='pending':raise ValueError('This response already has a recorded review')
        resolution=json.dumps(dict(submission_id=submission_id,event_id=row[2],evidence_verified=decision=='accept',reason=reason.strip(),reviewed_by=actor.actor_id))
        conn.execute('UPDATE task_submissions SET review_status=?,review_reason=?,reviewed_by=?,reviewed_at=? WHERE submission_id=?',(status,reason.strip(),actor.actor_id,_utc_now_iso(),submission_id))
        conn.execute('UPDATE evidence_tasks SET status=?,closed_at=?,resolution_json=? WHERE task_id=?',('completed' if decision=='accept' else 'open',_utc_now_iso() if decision=='accept' else None,resolution,row[0]))
        conn.execute("UPDATE case_records SET status='pending_review',updated_at=? WHERE case_id=?",(_utc_now_iso(),row[3]))
        append_audit(db_path,actor.actor_id,row[3],'evidence_reviewed',dict(task_id=row[0],submission_id=submission_id,decision=decision,reason=reason.strip(),event_id=row[2]),tx=conn)
    return {'is_new':True}
