# Known limitations

- All data, roles and operational changes are synthetic. The role selector demonstrates authorization; it is not production login, identity governance or approval-role revocation.
- Gemini integration must be tested with an actual securely configured key. No completed real-model or remote acceptance result may be inferred from deterministic mocks.
- The model selects tools through a bounded JSON protocol. No model can execute actions, SQL, URLs or file operations. Structural citation checks and prohibited-claim filtering cannot prove semantic entailment of every free-form statement; humans must review reports.
- The investigation uses text and image file metadata, not visual inspection. Exact SHA reuse and perceptual similarity do not establish intent, responsibility or package contents.
- Partner metrics describe the displayed shipment cohort. A 20-shipment display threshold does not establish statistical reliability. Completeness currently measures handoff/POD event presence, not every required field or photo.
- Historical access logs without trusted role metadata can only support potential assignment concerns. New requests preserve simulated role metadata.
- Data expires after 24 hours of inactivity. Community Cloud local storage is disposable on host rebuild; recovery tokens work only while the corresponding files survive. Export data before leaving.
- Upload storage is bounded to 25 uploaded files or 50 MB per workspace, in addition to per-file image limits. A photo-upload failure may leave its submitted source event available for a corrected retry; the application reports the failure.
- One process serializes real inference and enforces per-workspace quotas. This is a bounded demonstration, not a production abuse-prevention or multi-instance service.
- No accuracy percentages or time-saving measurements have been collected.
