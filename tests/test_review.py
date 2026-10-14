import json
import pytest
from contracts import AuthorizationError, AuditError
from db import init_db, get_connection
from services import review


def actor(role='investigator', partner=None):
    return dict(actor_id='reviewer', session_id='test', role=role, partner_id=partner)


@pytest.fixture
def database(tmp_path):
    path = str(tmp_path / 'review.db')
    init_db(path)
    with get_connection(path) as conn:
        conn.execute("INSERT INTO partners(partner_id,name,status,contract_end) VALUES('p','Partner','active','2999-01-01')")
        for i in range(6):
            conn.execute("INSERT INTO shipments(shipment_id,partner_id,status) VALUES(?, 'p','active')", (f's{i}',))
            conn.execute("INSERT INTO case_records(case_id,shipment_id,partner_id,status,findings_json,created_at) VALUES(?,?,'p',?,'[]','2026-01-01')", (f'c{i}', f's{i}', 'closed' if i == 0 else 'review_completed'))
        conn.execute("INSERT INTO assignments VALUES('assignment','s1','p','reviewer','2020-01-01','2999-01-01','[\"view\"]')")
        for i, state in ((2, 'proposed'), (3, 'approved'), (4, 'rejected')):
            conn.execute("INSERT INTO action_requests(action_id,case_id,action_type,target_id,status) VALUES(?,?,'test','p',?)", (f'a{i}', f'c{i}', state))
        conn.execute("INSERT INTO evidence_tasks(task_id,case_id,task_type,status,created_at) VALUES('t5','c5','photo','open','2026-01-01')")
    return path


def test_cohort_counts_and_live_scope(database):
    cases = review.list_review_cases(database, actor())
    assert review.review_counts(cases) == dict(needs_review=3, awaiting_approval=1, waiting_evidence=0, resolved=1, review_complete=1)
    scoped = review.list_review_cases(database, actor('partner_user', 'p'))
    assert [c['case_id'] for c in scoped] == ['c1']
    assert sum(review.review_counts(scoped).values()) == len(scoped)
    with get_connection(database) as conn:
        conn.execute("UPDATE assignments SET allowed_actions='[]'")
    assert review.list_review_cases(database, actor('partner_user', 'p')) == []


def test_access_cases_real_logs_idempotent(database):
    with get_connection(database) as conn:
        conn.execute("INSERT INTO access_logs(log_id,shipment_id,actor_id,occurred_at,action,outcome,batch_job_id) VALUES('log','s1','external','2026-01-01','query_shipment','denied','batch')")
    with pytest.raises(AuthorizationError):
        review.ensure_access_cases(database, actor('partner_user', 'p'))
    assert review.ensure_access_cases(database, actor()) == 1
    assert review.ensure_access_cases(database, actor()) == 0
    access = [c for c in review.list_review_cases(database, actor()) if c['issue_type'] == 'access']
    assert len(access) == 1
    assert access[0]['priority_score'] == 10
    assert access[0]['work_bucket'] == 'needs_review'
    assert access[0]['findings'][0]['evidence_ids'] == ['log']
    with get_connection(database) as conn:
        assert conn.execute('SELECT count(*) FROM events').fetchone()[0] == 0


def test_close_permissions_actions_and_manual_task_resolution(database):
    with pytest.raises(AuthorizationError):
        review.record_review_decision(database, 'c5', actor(), 'close', 'Manual disposition after review')
    with pytest.raises(ValueError):
        review.record_review_decision(database, 'c5', actor('admin'), 'close', ' ')
    with pytest.raises(ValueError):
        review.record_review_decision(database, 'c2', actor('admin'), 'close', 'Manual disposition after review')
    assert review.record_review_decision(database, 'c5', actor('admin'), 'close', 'Manual disposition after review')['is_new']
    assert not review.record_review_decision(database, 'c5', actor('admin'), 'close', 'Manual disposition after review')['is_new']
    with get_connection(database) as conn:
        status, resolution = conn.execute("SELECT status,resolution_json FROM evidence_tasks WHERE task_id='t5'").fetchone()
        assert status == 'closed'
        assert json.loads(resolution)['evidence_verified'] is False
        rows = conn.execute("SELECT details_json FROM audit_log WHERE case_id='c5'").fetchall()
        assert len(rows) == 1
        assert json.loads(rows[0][0])['closed_task_ids'] == ['t5']


def test_audit_failure_rolls_back_tasks_and_case(database, monkeypatch):
    def fail(*args, **kwargs):
        raise AuditError('Injected audit failure')
    monkeypatch.setattr(review, 'append_audit', fail)
    with pytest.raises(AuditError):
        review.record_review_decision(database, 'c5', actor('admin'), 'close', 'Manual disposition after review')
    with get_connection(database) as conn:
        assert conn.execute("SELECT status FROM evidence_tasks WHERE task_id='t5'").fetchone()[0] == 'open'
        assert conn.execute("SELECT status FROM case_records WHERE case_id='c5'").fetchone()[0] == 'review_completed'


def test_review_completion_is_separate_and_cannot_reopen(database):
    with pytest.raises(AuthorizationError):
        review.record_review_decision(database, 'missing', actor('partner_user', 'p'), 'review_complete', 'Reviewed available evidence')
    review.record_review_decision(database, 'c1', actor(), 'review_complete', 'Reviewed available evidence')
    assert next(c for c in review.list_review_cases(database, actor()) if c['case_id'] == 'c1')['work_bucket'] == 'review_complete'
    with pytest.raises(ValueError):
        review.record_review_decision(database, 'c0', actor(), 'review_complete', 'Reviewed available evidence')
