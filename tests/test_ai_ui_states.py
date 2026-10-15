"""Real widgets with mocked AI; case and Settings must agree."""
from tests.test_ui_refactor import app,open_main,widget,healthy
from tests.test_agent import ScriptedProvider,valid_report
from agent.runner import investigate_case

def test_case_settings_failure_retry_and_navigation_do_not_duplicate(app,monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY','private-test-value')
    open_main(app)
    assert any(x.value=='AI review has not started.' for x in app.info)
    assert not widget(app.button,'Review evidence with AI').disabled
    provider=ScriptedProvider([ValueError('simulated output rejected'),{'done':True},valid_report()])
    def fake(path,case_id,actor,**kwargs):
        return investigate_case(path,case_id,actor,provider=provider,**kwargs)
    monkeypatch.setattr('ui.live.investigate_case',fake)
    widget(app.button,'Review evidence with AI').click().run()
    healthy(app)
    assert len(provider.calls)==1
    case_messages=[x.value for x in app.info if x.value.startswith('AI could not')]
    assert len(case_messages)==1
    app.session_state.secondary_view='Settings';app.run();healthy(app)
    assert any(x.value==case_messages[0] for x in app.info)
    assert len(provider.calls)==1
    app.session_state.secondary_view=None;app.run();healthy(app)
    assert len(provider.calls)==1
    widget(app.button,'Retry AI review').click().run();healthy(app)
    assert len(provider.calls)==3
    assert any(x.value=='AI review completed. Check the cited evidence before deciding.' for x in app.success)
    app.run();assert len(provider.calls)==3
