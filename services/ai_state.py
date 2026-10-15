"""One truthful AI state for case screens and Settings; never calls a model."""
import json
from datetime import datetime,timezone
from agent.configuration import provider_settings
from db import get_connection

MESSAGES={
 'not_started':'AI review has not started.',
 'missing_configuration':'AI review is not set up for this workspace. You can still review the evidence manually.',
 'config_disabled':'AI review is turned off for this workspace.',
 'running':'Reviewing the available evidence…',
 'completed':'AI review completed. Check the cited evidence before deciding.',
 'outdated':'This AI review used earlier evidence. Review the updated records.',
 'authentication_failed':'AI could not connect. Ask the workspace administrator to check the connection.',
 'model_unavailable':'The selected AI model is unavailable. Ask the workspace administrator to check the model setting.',
 'rate_limited':'AI usage limit reached. Please try again later.',
 'usage_limited':'The demo AI usage limit is reached. Please try again later.',
 'timeout':'AI could not finish this review. Your evidence is saved.',
 'service_failure':'AI could not finish this review. Your evidence is saved.',
 'invalid_output':'AI could not produce a verified review. You can continue manually.',
 'interrupted':'The previous AI review was interrupted. Your evidence is saved; you can start a new review.',
}

def derive_ai_state(config,run=None,report=None,outdated=False,now=None):
    run=run or {};now=now or datetime.now(timezone.utc)
    try:diagnostics=json.loads(run.get('diagnostics_json') or '{}')
    except (ValueError,TypeError):diagnostics={}
    if not isinstance(diagnostics,dict):diagnostics={}
    status=run.get('status','not_started')
    if status not in MESSAGES:status='invalid_output' if diagnostics.get('exception') in ('ValueError','ValidationError') else 'service_failure'
    if run.get('status')=='ai_not_running':status='service_failure'
    if not run:status='not_started'
    if report and run.get('status')=='completed':status='outdated' if outdated else 'completed'
    if run.get('status')=='completed' and not report:status='invalid_output'
    if not config['enabled']:status='config_disabled'
    elif not config['configured']:status='missing_configuration'
    retry_at=diagnostics.get('retry_at')
    cooldown=False
    if retry_at:
        try:cooldown=datetime.fromisoformat(retry_at)>now
        except (ValueError,TypeError):retry_at=None
    can_run=config['enabled'] and config['configured'] and status!='running' and not cooldown
    action='Review evidence with AI' if not run else 'Review updated evidence' if outdated else 'Run another AI review' if run.get('status')=='completed' else 'Retry AI review'
    http=diagnostics.get('http_status')
    provider_outcome='Unvalidated'
    if isinstance(http,int):provider_outcome='Successful request' if 200<=http<300 else 'Request failed (HTTP '+str(http)+')'
    elif run.get('status')=='completed':provider_outcome='Successful request'
    return {'state':status,'message':MESSAGES[status],'can_run':can_run,'action':action,'reference':run.get('run_id'),
            'provider_outcome':provider_outcome,'diagnostics':diagnostics,'retry_at':retry_at if cooldown else None,
            'report':report,'report_outdated':outdated,'previous_report':bool(report and run.get('status')!='completed')}

def case_ai_state(path,case_id,actor):
    from services.cases import require_case
    from agent.runner import validate_saved_report,recover_abandoned_runs
    from agent.usage import evidence_snapshot
    from contracts import ActorContext,AuthorizationError
    with get_connection(path) as conn:require_case(conn,case_id,ActorContext(**actor))
    recover_abandoned_runs(path,case_id)
    with get_connection(path) as conn:
        conn.row_factory=__import__('sqlite3').Row
        row=conn.execute('SELECT * FROM investigation_runs WHERE case_id=? ORDER BY started_at DESC,rowid DESC LIMIT 1',(case_id,)).fetchone()
        run=dict(row) if row else None
        saved=conn.execute('SELECT * FROM report_versions WHERE case_id=? ORDER BY version DESC LIMIT 1',(case_id,)).fetchone()
        report=None;outdated=False;record=dict(saved) if saved else None
        if record:
            try:report=validate_saved_report(path,record,actor)
            except (ValueError,TypeError,AuthorizationError):report=None
            original=conn.execute('SELECT snapshot FROM investigation_runs WHERE run_id=?',(record.get('run_id'),)).fetchone()
            outdated=not original or not original[0] or original[0]!=evidence_snapshot(conn,ActorContext(**actor))
    state=derive_ai_state(provider_settings(),run,report,outdated)
    state.update(run=run,report_record=record)
    return state
