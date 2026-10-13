# Five-minute English demonstration

**0:00–0:40 — Partner overview.** “ParcelVerify helps logistics operators verify supplier evidence before responding. This is synthetic data in an isolated workspace. The sample contains three partners and 60 shipments. We show unique affected shipments per 1,000, unresolved cases and evidence completeness. Small samples do not establish reliability.”

**0:40–1:20 — Shipment timeline.** Select `PV-DEMO-001`. “Dispatch records 2,000 g and seal SEAL-07. A later handoff records 1,850 g. The POD file matches another shipment. These are verification signals, not proof of responsibility.” Open the event payloads and photo metadata.

**1:20–1:50 — Gate 1.** Select simulated partner SafeLog in Access Monitoring and query `PV-DEMO-001`. “The request is denied and logged before sensitive fields are returned. Approved bulk work cannot override shipment assignments.” Return to admin.

**1:50–3:10 — Investigation.** Open the main case in AI Investigation and run it. “The live model selects bounded read-only tools. The trace shows retrieved source IDs. The report separates evidence, possible explanations, missing information and recommendations. It cannot execute an operational change or claim visual inspection.” If inference fails, show the saved incomplete run and state the actual error; do not substitute a canned report.

**3:10–4:05 — Human response.** Propose `request_reweigh`, approve as simulated approver, then execute. “Approval and simulated state updates persist with the audit transaction. Repeated execution cannot apply the same change twice. Rejected requests cannot run.” Export the audit.

**4:05–4:40 — Counter-evidence.** Open `PV-SHIP-011`. Show approved repackaging and its two linked measurements. “A supported explanation changes the interpretation of the weight difference. Other anomalies and missing evidence remain visible.”

**4:40–5:00 — Isolation and limits.** Open another browser session. “Each visitor has a separate demo. Keep the recovery token private to resume yours while storage survives. Data expires after 24 hours of inactivity. A production system would add real authentication, durable hosted storage and operational integrations.”
