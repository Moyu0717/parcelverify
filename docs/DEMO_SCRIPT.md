# Local demonstration — 18 October 2026

All records, identities and operations are synthetic. No external message is
sent. See `AI_UI_FIX_VERIFICATION.md` for the latest deployment and live acceptance status.

## Start

From the repository run `.venv\Scripts\python.exe -X utf8 start.py`, then open
`http://localhost:8501`. A browser gets an isolated demo workspace. Preserve an
existing workspace with its private recovery token and audit export. Without a
privately configured Groq key, evidence checks and human review still work.

## Gate 1: permitted and denied access

Open Workspace → Settings → Demo tools. Select **Partner**, **QuickRun Logistics**,
and check `PV-DEMO-001`: assignment permits minimized data. Select **SafeLog Express**
and check the same shipment: denial returns no parcel details. Return to
**Administrator**, inspect Administrative logs and the access case. Demo roles
illustrate server permissions; they are not production authentication.

## Gate 2 and three controls

1. Home → **Compare weights**: `PV-DEMO-001` has 2.00 kg before dispatch and
   1.85 kg at handover. Show the recorded hub, unknown stage expectation/identities,
   MYT event/upload times and exact photo pair with `PV-SHIP-010`. Identical bytes
   establish reuse, not intent or parcel contents. Later account access is labelled
   post-delivery and does not establish the cause of the earlier weight difference.
2. Cases → search `PV-SHIP-011` → **Find shipment**. Inspect approved packaging,
   linked measurements and the authorized export scope. High volume alone is not
   misconduct; explanations must be supported by records.
3. Find `PV-SHIP-021`, or Home → Waiting for evidence. Missing measurements remain
   unknown and are not a confirmed discrepancy.

## Approval, task, response, review and closure

1. Select **Investigator**. Open `PV-DEMO-001`, enter a meaningful reason and choose
   **Send request for approval** for a new weight check.
2. Select **Supervisor**. Confirm the evidence was reviewed, enter a decision reason,
   then **Approve request** and **Apply approved step**. One approved action creates
   one task; retries cannot create another.
3. Select the assigned **QuickRun Partner** or Investigator. Expand **Supply
   evidence**, enter actual kg, context and the actual observation timestamp with
   timezone, such as `2026-10-18T14:30:00+08:00` only if that was the real observation
   time. Submit once. Server receipt time is separate.
4. Return to Supervisor, enter a review reason and choose **Request more**. Submit
   revised supporting context under the same observation time if appropriate,
   then **Accept evidence**. A supervisor may also request a supplementary statement
   before approving: the pending proposal and its clarification task remain usable.
5. Review findings independently. A fresh 2.00 kg reading does not prove the earlier
   difference harmless or resolve photo/access findings. Verified closure requires
   documented evidence/outcomes; otherwise choose **Closed unresolved** with an
   explicit reason and confirmation.
6. Expand **Activity**, download the summary and audit, and inspect actors, reasons,
   linked sources and transitions. Demonstrate rejection on a separate proposal:
   **Reject request** must prevent execution.

## Optional AI and partner context

Configure `GROQ_API_KEY` privately in `.streamlit/secrets.toml` using the example
template. Never share the key. Settings and cases derive the same availability;
a present credential does not prove a working connection. Click **Review evidence
with AI** once. If successful, inspect actual tools and cited facts. Mocks never
appear as product reports. Failure leaves manual review usable and diagnostics
restricted to administrators.

Partners shows all recorded history, permitted shipment denominator, affected
shipments/categories, missing fields, human outcomes and sample caveats. Field
completeness does not verify contents. See `AI_UI_FIX_VERIFICATION.md` for exact
checks, the missing local credential and the unmeasured human evaluation protocol.
