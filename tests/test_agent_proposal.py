"""S02 minimal: the agent may file one validated, deduplicated request; it can never approve it."""
import pytest
from contracts import AuthorizationError, InvestigationReport
from db import get_connection
from services.actions import review_action
from agent.runner import _check_proposal, submit_agent_proposal, AGENT_IDENTITY
from tests.test_actions import seeded_db, _create_case

ADMIN = {'actor_id': 'ADMIN-001', 'role': 'admin', 'session_id': 's02', 'is_simulated': True}
APPROVER = {'actor_id': 'APPROVER-001', 'role': 'approver', 'session_id': 's02-sup', 'is_simulated': True}


def _event(db, shipment='PV-DEMO-001', other=False):
    op = '!=' if other else '='
    with get_connection(db) as conn:
        return conn.execute(f'SELECT event_id FROM events WHERE shipment_id {op} ? ORDER BY event_id LIMIT 1', (shipment,)).fetchone()[0]


def _report(event_id, evidence=None, findings=('F-1',)):
    return {'proposed_action': {'action_type': 'request_reweigh', 'source_event_id': event_id, 'finding_ids': list(findings),
                                'reason': 'Recorded weight is outside tolerance', 'evidence_ids': evidence or [event_id],
                                'draft_message': 'Please re-weigh this parcel.'}}


def _agent_rows(db, case_id):
    with get_connection(db) as conn:
        return conn.execute('SELECT action_id,status FROM action_requests WHERE case_id=? AND requested_by=?', (case_id, AGENT_IDENTITY)).fetchall()


def test_schema_allows_null_and_full_enum():
    assert InvestigationReport.model_fields['proposed_action'].default is None
    with pytest.raises(Exception):
        from contracts import ProposedAction
        ProposedAction(action_type='reweigh', source_event_id='E', reason='r')


def test_valid_proposal_creates_exactly_one_request_and_retry_does_not_duplicate(seeded_db):
    case = _create_case(seeded_db)
    report = _report(_event(seeded_db))
    first = submit_agent_proposal(seeded_db, case['case_id'], report, ADMIN, snapshot='v1')
    assert first['status'] == 'proposed', first
    again = submit_agent_proposal(seeded_db, case['case_id'], report, ADMIN, snapshot='v1')
    newer = submit_agent_proposal(seeded_db, case['case_id'], report, ADMIN, snapshot='v2')  # refreshed evidence, same open step
    assert again['status'] == newer['status'] == 'existing'
    assert _agent_rows(seeded_db, case['case_id']) == [(first['action_id'], 'proposed')]


def test_agent_cannot_approve_its_own_proposal_but_a_supervisor_can(seeded_db):
    case = _create_case(seeded_db)
    out = submit_agent_proposal(seeded_db, case['case_id'], _report(_event(seeded_db)), ADMIN, snapshot='v1')
    with pytest.raises(AuthorizationError):
        review_action(seeded_db, out['action_id'], 'approve', dict(ADMIN, actor_id=AGENT_IDENTITY), 'Agent tries to approve itself')
    assert review_action(seeded_db, out['action_id'], 'approve', APPROVER, 'Evidence checked by supervisor')['status'] == 'approved'


def test_null_proposal_creates_nothing(seeded_db):
    case = _create_case(seeded_db)
    assert submit_agent_proposal(seeded_db, case['case_id'], {'proposed_action': None}, ADMIN)['status'] == 'none'
    assert _agent_rows(seeded_db, case['case_id']) == []


@pytest.mark.parametrize('kind', ['unretrieved_target', 'unretrieved_evidence', 'no_evidence', 'other_shipment', 'bad_type', 'no_finding', 'unshown_finding'])
def test_ungrounded_proposal_is_dropped(seeded_db, kind):
    own, other = _event(seeded_db), _event(seeded_db, other=True)
    report = _report(own)
    available = {own, other}
    if kind == 'unretrieved_target':available = {'E-ELSE'}
    if kind == 'unretrieved_evidence':report['proposed_action']['evidence_ids'] = [own, 'E-NOT-RETRIEVED']
    if kind == 'no_evidence':report['proposed_action']['evidence_ids'] = []
    if kind == 'other_shipment':report = _report(other)
    if kind == 'bad_type':report['proposed_action']['action_type'] = 'execute_refund'
    if kind == 'no_finding':report['proposed_action']['finding_ids'] = []
    if kind == 'unshown_finding':report['proposed_action']['finding_ids'] = ['F-1', 'F-FORGED']
    with get_connection(seeded_db) as conn:
        checked, note = _check_proposal(conn, report, 'PV-DEMO-001', available, {'F-1': {}})
    assert checked['proposed_action'] is None and note


def test_closed_case_returns_not_submitted(seeded_db):
    case = _create_case(seeded_db)
    with get_connection(seeded_db) as conn:
        conn.execute("UPDATE case_records SET status='closed' WHERE case_id=?", (case['case_id'],)); conn.commit()
    out = submit_agent_proposal(seeded_db, case['case_id'], _report(_event(seeded_db)), ADMIN, snapshot='v1')
    assert out['status'] == 'not_submitted' and out['action_id'] is None
    assert _agent_rows(seeded_db, case['case_id']) == []


def test_older_report_without_finding_link_is_not_resubmitted(seeded_db):
    case = _create_case(seeded_db)
    report = _report(_event(seeded_db), findings=())
    out = submit_agent_proposal(seeded_db, case['case_id'], report, ADMIN, snapshot='v1')
    assert out['status'] == 'not_submitted' and _agent_rows(seeded_db, case['case_id']) == []


# --- end-to-end with the server prefetch (framework 3.2 / 3.2.1) ---------------
from agent.runner import investigate_case
from tests.test_agent import ScriptedProvider, valid_report, _create_case_for_investigation


def _case_findings(db, case_id):
    from services.cases import ensure_case_links
    ensure_case_links(db, ADMIN)  # the app links findings (stable F- IDs) on load
    with get_connection(db) as conn:
        return [r[0] for r in conn.execute('SELECT finding_id FROM case_findings WHERE case_id=? ORDER BY finding_id', (case_id,))]


def _proposal_report(db, case_id, finding_ids):
    with get_connection(db) as conn:
        event = conn.execute("SELECT event_id FROM events WHERE shipment_id='PV-DEMO-001' AND event_type='handoff_submitted' LIMIT 1").fetchone()[0]
    report = valid_report()
    report['proposed_action'] = {'action_type': 'request_reweigh', 'source_event_id': event, 'finding_ids': finding_ids,
                                 'reason': 'Recorded weight is outside tolerance', 'evidence_ids': [event], 'draft_message': ''}
    return report


def _context_dispatches(db, run_id):
    with get_connection(db) as conn:
        return conn.execute("SELECT source FROM tool_executions WHERE run_id=? AND tool_name='get_case_context' ORDER BY rowid", (run_id,)).fetchall()


def test_prefetched_findings_support_a_proposal_without_model_selecting_context(seeded_db):
    case = _create_case_for_investigation(seeded_db)
    findings = _case_findings(seeded_db, case['case_id'])
    assert findings
    with get_connection(seeded_db) as conn:
        weight = [r[0] for r in conn.execute("SELECT finding_id FROM case_findings WHERE case_id=? AND category='weight_diff'", (case['case_id'],))]
    result = investigate_case(seeded_db, case['case_id'], ADMIN, provider=ScriptedProvider([{'done': True}, _proposal_report(seeded_db, case['case_id'], weight * 2)]))
    assert result['status'] == 'completed', result.get('error')
    assert [c['source'] for c in result['tool_calls']] == ['server_prefetch']
    assert result['report']['proposed_action']['finding_ids'] == weight  # de-duplicated
    assert result['proposal']['status'] == 'proposed'
    assert len(_agent_rows(seeded_db, case['case_id'])) == 1


def test_forged_finding_id_drops_the_proposal(seeded_db):
    case = _create_case_for_investigation(seeded_db)
    _case_findings(seeded_db, case['case_id'])
    result = investigate_case(seeded_db, case['case_id'], ADMIN, provider=ScriptedProvider([{'done': True}, _proposal_report(seeded_db, case['case_id'], ['F-FORGED'])]))
    assert result['status'] == 'completed' and result['report']['proposed_action'] is None
    assert 'finding' in result['diagnostics']['proposal_dropped']
    assert _agent_rows(seeded_db, case['case_id']) == []


def test_repeated_context_selection_is_not_re_executed_and_is_bounded(seeded_db):
    case = _create_case_for_investigation(seeded_db)
    ctx = {'tool_call': {'tool': 'get_case_context', 'params': {}}}
    provider = ScriptedProvider([ctx, ctx, ctx, valid_report()])
    result = investigate_case(seeded_db, case['case_id'], ADMIN, provider=provider)
    assert result['status'] == 'completed'
    assert provider.calls == [False, False, False, True]  # three slots left after the prefetch, then the report
    assert [c['source'] for c in result['tool_calls']] == ['server_prefetch'] + ['duplicate_selection'] * 3
    assert [r[0] for r in _context_dispatches(seeded_db, result['run_id'])] == ['server_prefetch'] + ['duplicate_selection'] * 3
    assert all(c['evidence_ids'] == [] for c in result['tool_calls'][1:])


def test_context_prefetch_failure_blocks_the_run_and_any_proposal(seeded_db, monkeypatch):
    import agent.runner as runner
    case = _create_case_for_investigation(seeded_db)
    real = runner.dispatch_tool
    def failing(db, name, params, ctx, actor):
        out = real(db, name, params, ctx, actor)
        if name == 'get_case_context':out = dict(out, result={'error': 'unauthorized'}, result_summary='Error: unauthorized')
        return out
    monkeypatch.setattr(runner, 'dispatch_tool', failing)
    provider = ScriptedProvider([_proposal_report(seeded_db, case['case_id'], _case_findings(seeded_db, case['case_id']))])
    result = investigate_case(seeded_db, case['case_id'], ADMIN, provider=provider)
    assert result['status'] != 'completed' and result['report'] is None and provider.calls == []
    assert 'case context could not be loaded' in result['error']
    assert _agent_rows(seeded_db, case['case_id']) == []


def test_real_finding_from_another_unlinked_case_is_rejected(seeded_db):
    case = _create_case_for_investigation(seeded_db)
    other = _create_case_for_investigation(seeded_db, shipment_id='PV-SHIP-011')
    foreign = _case_findings(seeded_db, other['case_id'])
    assert foreign and not set(foreign) & set(_case_findings(seeded_db, case['case_id']))
    result = investigate_case(seeded_db, case['case_id'], ADMIN, provider=ScriptedProvider([{'done': True}, _proposal_report(seeded_db, case['case_id'], foreign[:1])]))
    assert result['status'] == 'completed' and result['report']['proposed_action'] is None
    assert _agent_rows(seeded_db, case['case_id']) == []


# --- live run 2026-11-03: wrong photo record and mixed request text -----------------
from agent.runner import _tool_message


def _demo_event(db, event_type):
    with get_connection(db) as conn:
        event = conn.execute("SELECT event_id FROM events WHERE shipment_id='PV-DEMO-001' AND event_type=?", (event_type,)).fetchone()[0]
        photos = [r[0] for r in conn.execute('SELECT photo_id FROM photos WHERE event_id=?', (event,))]
    return event, photos


def _demo_findings(db):
    case = _create_case_for_investigation(db)
    _case_findings(db, case['case_id'])
    with get_connection(db) as conn:
        rows = conn.execute('SELECT finding_id,category FROM case_findings WHERE case_id=?', (case['case_id'],)).fetchall()
    return case, {fid: {'finding_id': fid, 'category': cat} for fid, cat in rows}


def _check(db, proposal, presented):
    with get_connection(db) as conn:
        return _check_proposal(conn, {'proposed_action': proposal}, 'PV-DEMO-001', set(proposal['evidence_ids']) | {proposal['source_event_id']}, presented)


def _ids(presented, category):
    return [f for f, v in presented.items() if v['category'] == category]


def test_rephoto_aimed_at_handover_while_citing_the_delivery_photo_is_dropped(seeded_db):
    """The exact live mistake: target = handover record, cited photo = proof-of-delivery photo."""
    _, presented = _demo_findings(seeded_db)
    handover, _ = _demo_event(seeded_db, 'handoff_submitted')
    _, pod_photos = _demo_event(seeded_db, 'pod_submitted')
    proposal = {'action_type': 'request_rephoto', 'source_event_id': handover, 'finding_ids': list(presented),
                'reason': 'photo reused', 'evidence_ids': [handover] + pod_photos, 'draft_message': 'Please re-photo and re-weigh.'}
    checked, note = _check(seeded_db, proposal, presented)
    assert checked['proposed_action'] is None and 'photo' in note


def test_rephoto_on_the_photo_record_keeps_only_photo_findings_and_uses_fixed_wording(seeded_db):
    _, presented = _demo_findings(seeded_db)
    pod, pod_photos = _demo_event(seeded_db, 'pod_submitted')
    proposal = {'action_type': 'request_rephoto', 'source_event_id': pod, 'finding_ids': list(presented),
                'reason': 'photo reused', 'evidence_ids': [pod] + pod_photos, 'draft_message': 'Please re-photo and also re-weigh the parcel.'}
    checked, note = _check(seeded_db, proposal, presented)
    kept = checked['proposed_action']
    assert note is None and kept['finding_ids'] == _ids(presented, 'photo_reuse')
    assert 'proof of delivery' in kept['draft_message'] and 'weigh' not in kept['draft_message']


@pytest.mark.parametrize('action,event_type,category', [('request_reweigh', 'pod_submitted', 'weight_diff'),
                                                       ('request_reweigh', 'handoff_submitted', 'photo_reuse')])
def test_request_must_match_target_and_finding_kind(seeded_db, action, event_type, category):
    _, presented = _demo_findings(seeded_db)
    event, _ = _demo_event(seeded_db, event_type)
    proposal = {'action_type': action, 'source_event_id': event, 'finding_ids': _ids(presented, category),
                'reason': 'r', 'evidence_ids': [event], 'draft_message': ''}
    checked, note = _check(seeded_db, proposal, presented)
    assert checked['proposed_action'] is None and note


def test_stored_request_reason_never_contains_model_text(seeded_db):
    case, presented = _demo_findings(seeded_db)
    handover, _ = _demo_event(seeded_db, 'handoff_submitted')
    report = {'proposed_action': {'action_type': 'request_reweigh', 'source_event_id': handover, 'finding_ids': _ids(presented, 'weight_diff'),
                                  'reason': 'MODEL-TEXT please also rephoto', 'evidence_ids': [handover], 'draft_message': 'MODEL-DRAFT'}}
    out = submit_agent_proposal(seeded_db, case['case_id'], report, ADMIN, snapshot='v1')
    with get_connection(seeded_db) as conn:
        reason = conn.execute('SELECT reason FROM action_requests WHERE action_id=?', (out['action_id'],)).fetchone()[0]
    assert 'MODEL' not in reason and 'handover to partner' in reason and 'weigh the parcel again' in reason


def test_photo_reuse_result_names_the_record_of_each_photo(seeded_db):
    from agent.tools import dispatch_tool
    case, _ = _demo_findings(seeded_db)
    pod, pod_photos = _demo_event(seeded_db, 'pod_submitted')
    out = dispatch_tool(seeded_db, 'find_photo_reuse', {'photo_id': pod_photos[0]}, {'case_id': case['case_id']}, ADMIN)
    with get_connection(seeded_db) as conn:
        ids = [m['event_id'] for m in out['result']['exact_matches'] + out['result']['similar_candidates'] if m['event_id'] != '[masked]']
        types = dict(conn.execute('SELECT event_id,event_type FROM events WHERE event_id IN (%s)' % ','.join('?' * len(ids)), ids).fetchall()) if ids else {}
    types[('photo', pod_photos[0])] = (pod, 'pod_submitted')
    encoded, _ = _tool_message(out, types)
    assert '"photo_record":"proof of delivery"' in encoded
