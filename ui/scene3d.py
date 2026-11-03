"""Bidirectional Three.js workspace: the 3D map reads persisted workflow state and drives selection.

The browser component never writes business data. It returns a selection (or a case to open);
Python re-checks permissions and the user still confirms every request, approval and closure.
"""
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

_component = components.declare_component('parcel_scene_3d', path=str(Path(__file__).with_name('scene3d')))


def _consume(message, key):
    """Return a component message once; reruns replay the last value."""
    if not isinstance(message, dict) or not isinstance(message.get('nonce'), str):
        return None
    seen = st.session_state.setdefault('scene3d_seen', {})
    if seen.get(key) == message['nonce']:
        return None
    seen[key] = message['nonce']
    return message


def city_scene(cases, featured_id, height=430, key='home-city'):
    """Overview of permitted cases as buildings. Returns a case id the user opened, or None."""
    payload = dict(mode='city', featured=featured_id, height=height,
                   cases=[dict(id=c['id'], shipment=c['shipment'], title=c['title'], bucket=c['bucket']) for c in cases])
    message = _consume(_component(payload=payload, key=key, default=None), key)
    if message and message.get('type') == 'open' and any(c['id'] == message.get('id') for c in cases):
        return message['id']
    return None


def ordered_stations(nodes):
    """Event nodes in journey order; a missing handover sits before delivery, not after it."""
    events = [n for n in nodes if n.get('kind', 'event') == 'event']
    missing = [n for n in events if n['missing']]
    present = [n for n in events if not n['missing']]
    for node in missing:
        spot = next((i for i, n in enumerate(present) if n['label'] in ('Delivered', 'Recipient approved')), len(present))
        present.insert(spot, node)
    return present


def van_target(stations, phase):
    """The record the active request or task concerns; otherwise the first problem record."""
    linked = [n for n in stations if n.get('workflow')]
    if linked and phase not in ('check',):
        return linked[-1]['id']
    problem = next((n for n in stations if n['status'] == 'Difference'), None) or next((n for n in stations if n['missing']), None)
    return problem['id'] if problem else (stations[-1]['id'] if stations else None)


def case_scene(case, stations, phase, selected, headline, height=440):
    """Render one shipment journey plus the review workflow. Returns a newly selected id or None."""
    present = [i for i, n in enumerate(stations) if not n['missing']]
    payload = dict(mode='case', case_id=case['case_id'], shipment=case['shipment_id'], headline=headline,
                   phase=phase, selected=selected, height=height, journey=present[-1] if present else 0,
                   van_target=van_target(stations, phase),
                   stations=[{k: n.get(k) for k in ('id', 'label', 'status', 'time', 'workflow', 'missing')} for n in stations])
    key = 'case-scene-' + case['case_id']
    message = _consume(_component(payload=payload, key=key, default=None), key)
    if message and message.get('type') == 'select':
        ident = message.get('id')
        if ident == 'hq' or any(n['id'] == ident for n in stations):
            return ident
    return None
