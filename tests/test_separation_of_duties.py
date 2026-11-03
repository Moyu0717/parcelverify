"""S04: the proposer cannot approve, decisions need a reason, and the agent identity can only propose."""
import pytest
from contracts import AuthorizationError
from db import get_connection
from services.actions import propose_action, review_action, execute_action
from tests.test_actions import seeded_db, _create_case, INVESTIGATOR, APPROVER

ADMIN = {'actor_id': 'ADMIN-001', 'role': 'admin', 'session_id': 'sod', 'is_simulated': True}
AGENT = {'actor_id': 'AGENT-INVESTIGATOR', 'role': 'investigator', 'session_id': 'sod', 'is_simulated': True}
REASON = 'Weight is outside tolerance; request a fresh measurement'


def test_proposer_cannot_approve_own_request_even_as_admin(seeded_db):
    case = _create_case(seeded_db)
    action = propose_action(seeded_db, case['case_id'], 'request_reweigh', ADMIN, reason='Check the weight')
    with pytest.raises(AuthorizationError):
        review_action(seeded_db, action['action_id'], 'approve', ADMIN, REASON)
    assert review_action(seeded_db, action['action_id'], 'approve', APPROVER, REASON)['status'] == 'approved'


def test_proposer_may_withdraw_by_rejecting(seeded_db):
    case = _create_case(seeded_db)
    action = propose_action(seeded_db, case['case_id'], 'request_reweigh', ADMIN, reason='Check the weight')
    assert review_action(seeded_db, action['action_id'], 'reject', ADMIN, 'Withdrawn: proposed by mistake')['status'] == 'rejected'


@pytest.mark.parametrize('reason', ['', '   ', 'ok'])
def test_decision_reason_is_required_and_not_prefilled(seeded_db, reason):
    case = _create_case(seeded_db)
    action = propose_action(seeded_db, case['case_id'], 'request_reweigh', INVESTIGATOR)
    with pytest.raises(ValueError):
        review_action(seeded_db, action['action_id'], 'approve', APPROVER, reason)
    with get_connection(seeded_db) as conn:
        assert conn.execute('SELECT status FROM action_requests WHERE action_id=?', (action['action_id'],)).fetchone()[0] == 'proposed'


def test_agent_can_propose_but_never_approve_or_execute(seeded_db):
    case = _create_case(seeded_db)
    action = propose_action(seeded_db, case['case_id'], 'request_reweigh', AGENT, reason='Agent proposal')
    agent_admin = dict(AGENT, role='admin')  # renaming the role does not lift the restriction
    for actor in (AGENT, agent_admin):
        with pytest.raises(AuthorizationError):
            review_action(seeded_db, action['action_id'], 'approve', actor, REASON)
    review_action(seeded_db, action['action_id'], 'approve', APPROVER, REASON)
    with pytest.raises(AuthorizationError):
        execute_action(seeded_db, action['action_id'], agent_admin)
    assert execute_action(seeded_db, action['action_id'], APPROVER)['status'] == 'executed'


def test_historic_self_approval_cannot_execute(seeded_db):
    case = _create_case(seeded_db)
    action = propose_action(seeded_db, case['case_id'], 'request_reweigh', INVESTIGATOR)
    review_action(seeded_db, action['action_id'], 'approve', APPROVER, REASON)
    with get_connection(seeded_db) as conn:  # simulate a record created before the rule existed
        conn.execute("UPDATE action_requests SET requested_by='APPROVER-001' WHERE action_id=?", (action['action_id'],))
    with pytest.raises(AuthorizationError):
        execute_action(seeded_db, action['action_id'], APPROVER)
