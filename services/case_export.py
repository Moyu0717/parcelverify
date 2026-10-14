"""Chronological exports of the current viewer's permitted case membership."""
import json
from db import get_connection
from services.cases import get_case_context
from services.audit import export_audit
from services.followups import list_tasks
from agent.runner import validate_saved_report

def export_case(db_path,case_id,actor_context):
    ctx=get_case_context(db_path,case_id,actor_context);ids=[m['case_id'] for m in ctx['cases']]
    with get_connection(db_path) as conn:
        conn.row_factory=__import__('sqlite3').Row
        marks=','.join('?' for _ in ids)
        runs=[dict(r) for r in conn.execute('SELECT run_id,case_id,status,model_name,error,started_at,finished_at FROM investigation_runs WHERE case_id IN ('+marks+') ORDER BY started_at',ids)]
        if actor_context['role']!='admin':
            for run in runs:run.pop('error',None)
        requests=[dict(r) for r in conn.execute('SELECT action_id,case_id,action_type,target_id,status,requested_by,approved_by,approved_at,executed_at,reason FROM action_requests WHERE case_id IN ('+marks+') ORDER BY rowid',ids)]
        submissions=[dict(r) for r in conn.execute('SELECT s.* FROM task_submissions s JOIN evidence_tasks t ON t.task_id=s.task_id WHERE t.case_id IN ('+marks+') ORDER BY s.created_at',ids)]
        for s in submissions:
            s.pop('intent_hash',None);s.pop('submission_key',None)
        decisions=[dict(r) for r in conn.execute('SELECT * FROM case_decisions WHERE case_id IN ('+marks+') ORDER BY created_at',ids)]
        reports=[]
        for r in conn.execute('SELECT * FROM report_versions WHERE case_id IN ('+marks+') ORDER BY created_at',ids):
            try:reports.append(dict(run_id=r['run_id'],model=r['model_name'],report=validate_saved_report(db_path,dict(r),actor_context)))
            except ValueError:reports.append(dict(run_id=r['run_id'],validation='References are no longer permitted; report withheld'))
    history=sorted([event for cid in ids for event in export_audit(db_path,cid,actor_context)['events']],key=lambda e:(e['occurred_at'],e['audit_id']))
    return dict(case_id=ctx['case_id'],shipments=ctx['shipment_ids'],members=[{'case_id':m['case_id'],'shipment_id':m['shipment_id'],'partner_name':m['partner_name'],'linkage_reason':m['linkage_reason']} for m in ctx['cases']],findings=ctx['findings'],tasks=list_tasks(db_path,case_id,actor_context),requests=requests,submissions=submissions,decisions=decisions,investigation_runs=runs,reports=reports,activity=history,audit_guarantee='Transactional application history; no tamper-proof guarantee')

def readable_case(export):
    lines=['# ParcelVerify case review','', 'Shipments: '+', '.join(export['shipments']),'','## Findings']
    for finding in export['findings']:
        lines.append('- '+finding['category'].replace('_',' ')+': '+finding['description']+' — '+finding['state'])
        lines.append('  Sources: '+', '.join(finding['evidence_ids']))
    for section in ('requests','submissions','decisions','investigation_runs','activity'):
        lines.extend(['','## '+section.replace('_',' ').title()])
        for row in export[section]:
            title=(row.get('action_type') or row.get('operation') or row.get('outcome') or row.get('review_status') or row.get('status') or 'Recorded submission').replace('_',' ')
            moment=row.get('occurred_at') or row.get('created_at') or row.get('started_at') or row.get('approved_at') or ''
            actor=row.get('actor_id') or row.get('requested_by') or row.get('reviewed_by') or ''
            reason=row.get('reason') or row.get('review_reason') or row.get('details',{}).get('reason') or ''
            lines.append('- '+moment+' — '+title+' — '+actor+(' — '+reason if reason else '')+(' (model: '+row['model_name']+')' if row.get('model_name') else ''))
    lines.extend(['','Unresolved facts remain visible. A closed case is not necessarily verified.','Synthetic demo; no external request was sent.'])
    return '\n'.join(lines)
