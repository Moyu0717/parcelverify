# Design data audit — 13 October 2026

## Completed activity timeline

The future “Last activity” was generated data, not a timezone conversion bug. `seed.py` started at 1 September 2026 and added one day for each of 60 shipment indices, then added handover, delivery and customer-report offsets. This produces completed events in late October / early November, after the screenshot date.

New demo seeds now dispatch two shipments per day. The existing September start, event order, discrepancy scenarios, assignment validity and contract history remain coherent; completed fixture events and access logs all predate 13 October. Workspace template v3 makes this correction apply to newly created demo workspaces. Existing visitor databases and v2 templates are untouched. Their original recorded timestamps must remain visible as such, with a notice when recorded events are future-dated. Contract expiry dates are genuinely future dates and should not be changed.

## Twenty shipments and twenty-one cases

Shipments and cases have different denominators. Shipment reviews are scoped to triggering events; denied-access reviews are scoped to individual access logs. A denied-access case can coexist with the handover case on the same shipment. `ensure_access_cases` attributes that case to the target shipment and its owning partner, while preserving the querying actor in evidence. Thus 21 open cases across 20 shipments is possible and is not 105% affected shipments.

Use “Open cases” for case row counts, “Affected shipments” for distinct shipment IDs, and disclose “X open cases across Y affected shipments.” `get_partner_metrics.anomaly_count` already deduplicates shipments. Its completeness percentage measures presence of handover and delivery events, not verified quality. Reporting defaults to all recorded history; any period filter needs one disclosed cohort across metrics.

## Action copy and actual backend effects

All actions are local prototype operations. No backend mail, carrier API, external queue or named recipient is invoked by these three actions.

| Action | Proposal and approval | Effect after execution | Accurate user explanation |
|---|---|---|---|
| `request_reweigh` | Investigator or admin proposes; approver or admin approves/rejects and executes | Creates/reuses one open `reweigh` evidence task on the case, stores reason/creator; marks case `action_executed`; saves action before/after and audit | Request a weight check in this demo workspace. An approver must approve and execute it. No message is sent to a partner. |
| `submit_to_contract_ops` | Same roles | Marks case/action executed and records before/after plus audit; no recipient, contract-ops task, notification or contract change | Record a simulated referral for contract review. No external team is contacted. |
| `enhance_inspection` | Same roles | Marks case/action executed and records before/after plus audit; no inspection task, partner-status change or external process | Record a simulated inspection decision. No inspection is scheduled outside this workspace. |

Approval alone does not execute. Partner users cannot propose, approve or execute. The backend permits an admin to perform both steps and does not enforce distinct proposer and approver identities. Executing these actions does not resolve/close the case; open evidence tasks still require attention. Rejected requests are terminal. Execution checks approval, expiry, current authority and terminal case state; repeat execution is idempotent.

The direct `create_evidence_task` helper additionally allows investigators/admins/approvers to create a local task without the action approval flow. If surfaced independently, distinguish that local task request from proposing an approved action.

## Validation

A focused test verifies every generated completed event/access timestamp precedes 13 October 2026 and dispatch < handover < delivery for all shipments. Existing rule and security suites are also run against isolated temporary databases; no production or visitor database is edited and no AI calls are made.
