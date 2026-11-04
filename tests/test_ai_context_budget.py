"""Baseline 2026-11-03: the live final request reached 36,400 chars and was blocked by the
20,000-char bound. Tool data is now compacted and withheld (not citable) past a budget."""
import json
import agent.runner as runner
from agent.runner import investigate_case, _tool_message, TOOL_CONTEXT_BUDGET
from agent.tools import dispatch_tool
from services.cases import ensure_case_links
from tests.test_agent import seeded_db, ADMIN_ACTOR, _create_case_for_investigation, valid_report


class Recorder:
    model_name = 'mock-model'
    def __init__(self, script):
        self.script, self.sizes, self.calls = list(script), [], []
    def generate(self, messages, timeout, final=False):
        self.sizes.append(len(json.dumps(messages)));self.calls.append(final)
        return json.dumps(self.script.pop(0))


def _photo(db, cid):
    timeline = dispatch_tool(db, 'get_shipment_timeline', {}, {'case_id': cid}, ADMIN_ACTOR)
    return [p['photo_id'] for e in timeline['result']['events'] for p in e['photos']][0]


def test_compact_messages_keep_citable_ids_and_drop_noise(seeded_db):
    cid = _create_case_for_investigation(seeded_db)['case_id']
    for tool, params in (('get_shipment_timeline', {}), ('find_photo_reuse', {'photo_id': _photo(seeded_db, cid)}), ('check_access_scope', {})):
        out = dispatch_tool(seeded_db, tool, params, {'case_id': cid}, ADMIN_ACTOR)
        encoded, refs = _tool_message(out)
        assert len(encoded) < len(json.dumps(out['result']))
        for noise in ('received_at', 'is_synthetic', 'sha256', 'manual_observation'):
            assert '"' + noise + '"' not in encoded
        assert refs and all(json.dumps(r) in encoded for r in refs)  # only shown IDs are citable


def test_full_live_like_run_stays_inside_the_bound(seeded_db):
    case = _create_case_for_investigation(seeded_db);ensure_case_links(seeded_db, ADMIN_ACTOR)
    photo = _photo(seeded_db, case['case_id'])
    script = [{'tool_call': {'tool': 'get_shipment_timeline', 'params': {}}},
              {'tool_call': {'tool': 'find_photo_reuse', 'params': {'photo_id': photo}}},
              {'tool_call': {'tool': 'compare_handoff', 'params': {}}}, valid_report()]
    provider = Recorder(script)
    result = investigate_case(seeded_db, case['case_id'], ADMIN_ACTOR, provider=provider)
    assert result['status'] == 'completed', result.get('error')
    assert max(provider.sizes) < 20000


def test_tool_data_past_the_budget_is_withheld_and_not_citable(seeded_db, monkeypatch):
    case = _create_case_for_investigation(seeded_db)
    monkeypatch.setattr(runner, 'TOOL_CONTEXT_BUDGET', 3600)  # room for the prefetched context (~2.9K here), not the timeline
    script = [{'tool_call': {'tool': 'get_shipment_timeline', 'params': {}}}, {'done': True}]
    timeline_ids = _tool_message(dispatch_tool(seeded_db, 'get_shipment_timeline', {}, {'case_id': case['case_id']}, ADMIN_ACTOR))[1]
    context_ids = _tool_message(dispatch_tool(seeded_db, 'get_case_context', {}, {'case_id': case['case_id']}, ADMIN_ACTOR))[1]
    only_timeline = sorted(timeline_ids - context_ids)
    assert only_timeline
    report = valid_report();report['facts'] = [{'text': 'A recorded event needs review.', 'evidence_ids': [only_timeline[0]]}]
    result = investigate_case(seeded_db, case['case_id'], ADMIN_ACTOR, provider=Recorder(script + [report]))
    assert result['diagnostics']['withheld_tools'] == ['get_shipment_timeline']
    assert result['status'] != 'completed' and result['report'] is None  # a withheld ID cannot support a fact


def test_oversized_case_context_fails_closed(seeded_db, monkeypatch):
    case = _create_case_for_investigation(seeded_db)
    monkeypatch.setattr(runner, 'TOOL_CONTEXT_BUDGET', 500)
    provider = Recorder([valid_report()])
    result = investigate_case(seeded_db, case['case_id'], ADMIN_ACTOR, provider=provider)
    assert result['status'] != 'completed' and provider.calls == []
    assert 'case context could not be loaded' in result['error']


def test_final_request_uses_short_field_guide_not_full_schema(seeded_db):
    case = _create_case_for_investigation(seeded_db)
    seen = {}
    class P(Recorder):
        def generate(self, messages, timeout, final=False):
            if final:seen['last'] = messages[-1]['content']
            return super().generate(messages, timeout, final)
    investigate_case(seeded_db, case['case_id'], ADMIN_ACTOR, provider=P([{'done': True}, valid_report()]))
    assert '"$defs"' not in seen['last'] and 'proposed_action' in seen['last'] and 'finding_ids' in seen['last']


def test_local_token_estimate_counts_declared_tools_and_schema(seeded_db, monkeypatch):
    """Live 2026-11-03: the final report got Groq 429 (tokens) because chars/4 under-counted."""
    case = _create_case_for_investigation(seeded_db)
    reserved = []
    monkeypatch.setattr(runner, 'reserve_request', lambda tokens: reserved.append(tokens))
    class Native(Recorder):
        protocol = 'native'
        def generate(self, messages, timeout, final=False):
            self.last = len(json.dumps(messages))
            return super().generate(messages, timeout, final)
    provider = Native([{'done': True}, valid_report()])
    monkeypatch.setattr(runner, 'ModelProvider', lambda: provider)
    result = investigate_case(seeded_db, case['case_id'], ADMIN_ACTOR)  # real-provider path uses the guard
    assert result['status'] == 'completed', result.get('error')
    selection, final = reserved
    assert selection == (provider.sizes[0] + runner._TOOL_DEFS_CHARS + 2) // 3 + 512
    assert final == (provider.sizes[1] + runner._REPORT_SCHEMA_CHARS + 2) // 3 + 1024
    assert [attempt['reserved_tokens'] for attempt in result['diagnostics']['request_history']]==reserved


def test_low_remaining_time_skips_tool_selection_and_still_writes_the_report(seeded_db, monkeypatch):
    """Live 2026-11-04: an extra selection request used the time the final report needed."""
    case = _create_case_for_investigation(seeded_db)
    monkeypatch.setattr(runner, 'reserve_request', lambda tokens: None)
    monkeypatch.setattr(runner, 'FINAL_REPORT_RESERVE_S', runner.TOTAL_TIME_BUDGET_S + 1)
    provider = Recorder([valid_report()])
    monkeypatch.setattr(runner, 'ModelProvider', lambda: provider)
    result = investigate_case(seeded_db, case['case_id'], ADMIN_ACTOR)
    assert result['status'] == 'completed', result.get('error')
    assert provider.calls == [True]  # no selection request, straight to the report
    assert result['diagnostics']['selection_stopped_for_time'] == 1  # only the server-prefetched context
