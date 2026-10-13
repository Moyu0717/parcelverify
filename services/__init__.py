"""
ParcelVerify — Services Package
Owner: Roles B and D

Sub-modules:
- access.py (Role B) — Gate 1: query_shipment, check_access_scope, get_contract_at_time
- handoff.py (Role B) — Gate 2: evaluate_handoff, compare_handoff, create_or_update_case
- photos.py (Role B) — inspect_photo, find_photo_reuse
- risk.py (Role B) — calculate_priority, get_partner_metrics
- actions.py (Role D) — propose_action, review_action, execute_action, create_evidence_task
- audit.py (Role D) — append_audit, export_audit
"""
