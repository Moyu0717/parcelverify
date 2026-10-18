"""A complete synthetic review can wait for the existing rolling free guard."""
import sqlite3
from agent.runner import investigate_case
from tests.test_agent import seeded_db,ADMIN_ACTOR,_create_case_for_investigation,ScriptedProvider,valid_report

def test_rolling_window_wait_stays_inside_budget_without_extra_provider_calls(seeded_db,monkeypatch,tmp_path):
    monkeypatch.setenv('PV_DATA_DIR',str(tmp_path))
    clock=[1000.0]
    monkeypatch.setattr('agent.usage.time.time',lambda:clock[0])
    monkeypatch.setattr('agent.runner.time.monotonic',lambda:clock[0])
    monkeypatch.setattr('agent.runner.time.sleep',lambda seconds:clock.__setitem__(0,clock[0]+seconds))
    provider=ScriptedProvider([{'tool_call':{'tool':'get_case_context','params':{}}},{'done':True},valid_report()])
    monkeypatch.setattr('agent.runner.ModelProvider',lambda:provider)
    cid=_create_case_for_investigation(seeded_db)['case_id']
    result=investigate_case(seeded_db,cid,ADMIN_ACTOR)
    assert result['status']=='completed' and result['request_count']==3 and len(provider.calls)==3
    assert 60<=result['diagnostics']['local_quota_wait_seconds']<120
    assert result['total_duration_ms']<120000
    with sqlite3.connect(tmp_path/'groq-usage.db') as conn:records=conn.execute('SELECT at,estimated_tokens FROM requests ORDER BY at').fetchall()
    assert len(records)==3
    for stamp,_ in records:
        assert sum(tokens for at,tokens in records if stamp-60<=at<=stamp)<=6000
