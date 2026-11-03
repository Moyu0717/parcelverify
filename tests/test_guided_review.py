"""Novice entry must use permitted queue data; the single next step must not skip approval."""
from tests.test_ui_refactor import app,healthy
from ui.flow import phase_of, STEP_OF
from ui.scene3d import ordered_stations, van_target
from services.cases import list_cases

def test_start_next_review_uses_highest_priority_permitted_case(app):
    cohort=list_cases(app.session_state.db_path,app.session_state.actor_context)
    expected=sorted((c for c in cohort if c['work_bucket']=='needs_review'),key=lambda c:c['priority_score'] or 0,reverse=True)[0]
    app.button(key='start-next-review').click().run()
    healthy(app)
    assert app.session_state.selected_case_id==expected['case_id']

def test_phase_distinguishes_approval_sending_reply_and_outcome():
    case={'work_bucket':'needs_review'}
    assert phase_of(case,[],[{'status':'proposed'}])=='approve'
    assert phase_of(case,[],[{'status':'approved'}])=='send'
    assert phase_of(case,[{'status':'open'}],[{'status':'executed'}])=='waiting'
    assert phase_of(case,[{'status':'received'}],[{'status':'executed'}])=='review'
    assert phase_of(case,[{'status':'completed'}],[{'status':'executed'}])=='finish'
    assert phase_of(case,[],[])=='check'
    assert phase_of({'work_bucket':'resolved','closure_outcome':'verified_resolved'},[],[])=='closed_ok'
    assert phase_of({'work_bucket':'resolved','closure_outcome':'closed_unresolved'},[{'status':'open'}],[])=='closed_open'
    assert [STEP_OF[p] for p in ('check','approve','waiting','finish')]==[0,1,2,3]

def test_map_orders_missing_handover_before_delivery_and_targets_linked_record():
    nodes=[dict(id='a',label='Prepared',status='Recorded',missing=False,kind='event'),
           dict(id='b',label='Delivered',status='Recorded',missing=False,kind='event'),
           dict(id='missing-handoff',label='Handover',status='Missing record',missing=True,kind='event'),
           dict(id='task:x',label='Reweigh task',status='Awaiting response',missing=True,kind='task')]
    stations=ordered_stations(nodes)
    assert [n['id'] for n in stations]==['a','missing-handoff','b']
    assert van_target(stations,'check')=='missing-handoff'
    stations[0]['workflow']='Awaiting response'
    assert van_target(stations,'waiting')=='a'
