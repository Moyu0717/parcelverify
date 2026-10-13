# ParcelVerify — Decision Log

## 13 October 2026 handoff decisions

- Retain Python 3.11, Streamlit, SQLite and existing synthetic images. Replace fixture UI with live service calls; no frontend rewrite.
- User selected Gemini Developer API and Streamlit Community Cloud. Use configurable `gemini-3.5-flash-lite` and the official compatible endpoint; credentials live in server Secrets. This supersedes the earlier local-only Ollama plan. Do not enable paid infrastructure.
- User selected a public GitHub repository at `Moyu0717/parcelverify`. Publish allowlisted source and synthetic fixtures, excluding secrets and runtime data.
- Use separate database/upload directories per visitor; recovery tokens stay private. Expire after 24 hours of inactivity and state Community Cloud host-rebuild data loss explicitly.
- Enforce current-time access, preserve failed investigation traces, link reports to runs, reject invented references, require supported repackaging measurements and transact approval/execution with audit.

**Owner:** Main Agent  
**Rule:** Engineering trade-offs can be decided by Main Agent. Conflicts between source materials must be recorded here.

---

## D-001: Seal ID — S-001 vs SEAL-07

**Conflict:** PDF demo story uses `S-001`; Prototype Manual uses `SEAL-07`.  
**Decision:** Standardize on `SEAL-07` for the main demo scenario (PV-DEMO-001). Use `S-001` in a separate standalone case only.  
**Rationale:** Manual is the implementation spec; PDF is product brief.  
**Date:** 2026-10-12

## D-002: Scoring — Identity Conflict vs Number Mismatch

**Conflict:** PDF says "identity conflict 25 pts"; Manual says "number/seal mismatch 25 pts".  
**Decision:** Define a single 25-point category: `seal_mismatch / id_conflict`. Covers seal ID mismatch, recipient identity conflict, and parcel number mismatch. One case gets max 25 in this category, not cumulative.  
**Rationale:** Prevents double-counting related evidence.  
**Date:** 2026-10-12

## D-003: Quantity Discrepancy — 100→98 Without Separate Scoring

**Conflict:** No explicit scoring item for quantity mismatch.  
**Decision:** Return quantity contradiction as a finding with `insufficient_evidence` status if no per-item scan exists. Do NOT auto-add score. If seal/number mismatch is also present, it falls under D-002's 25-point category.  
**Rationale:** Missing scan = missing evidence, not proof of theft.  
**Date:** 2026-10-12

## D-004: Review Queue — Score ≥30 vs Blocking Contradictions

**Conflict:** Rules say ≥30 enters review queue, but some contradictions (25 pts) may not reach 30 alone.  
**Decision:** Any contradiction that blocks handoff acceptance enters `pending_review` **regardless of total score**. Priority score only determines processing order.  
**Rationale:** Safety-first; a single seal mismatch shouldn't be ignored because score < 30.  
**Date:** 2026-10-12

## D-005: Repackaging Explanation for Weight Difference

**Conflict:** Repackaging could explain weight difference but no validation standard. Original decision conflated repackaging approval with `approved_batch_job` and `route_exception`.  
**Decision:** Introduce a dedicated `repackaging_approved` event type. Only this event — with linked shipment, handoff reference, approver identity, and supporting evidence — can partially explain a weight difference. It does NOT automatically clear all weight discrepancies; the remaining weight delta must still be evaluated. `approved_batch_job` and `route_exception` are separate event types and cannot substitute for repackaging approval. Unverified verbal explanations remain as open findings.  
**Rationale:** Repackaging is a distinct operational action with its own authorization chain. Conflating it with batch jobs or route exceptions hides the approval trail.  
**Date:** 2026-10-12 (revised 2026-10-12)

## D-006: Demo Case Weight Threshold

**Conflict:** 2000g→1850g, diff=150g.  
**Decision:** Threshold = `max(100g, base_weight × 5%)`. For 2000g base: `max(100, 100) = 100g`. Diff of 150g > 100g → weight finding triggered (20 pts). Combined with photo reuse (25 pts) = 45 pts if no valid explanation.  
**Date:** 2026-10-12

## D-007: AI "Scale Error" Hypothesis

**Conflict:** Model might suggest "scale calibration difference" as explanation.  
**Decision:** Treated as unverified hypothesis unless a `scale_calibration` event with calibration records exists. Cannot be written as confirmed cause.  
**Date:** 2026-10-12

## D-008: pHash + SHA Same Photo — Single Deduction

**Conflict:** Same photo could trigger both SHA-256 exact match (25 pts) and pHash similarity.  
**Decision:** Photo reuse category scores max 25 per case, regardless of how many detection methods match. SHA and pHash are complementary detection methods, not independent findings.  
**Date:** 2026-10-12

## D-009: GPS Missing Handling

**Conflict:** GPS data might be absent.  
**Decision:** Return `unknown` for location. Never convert missing GPS to (0, 0). Never infer address mismatch from absence.  
**Date:** 2026-10-12

## D-010: Report Language

**Conflict:** Original materials contain Chinese examples.  
**Decision:** All deliverables in English: UI, reports, error messages, README, test reports, demo scripts. User's free-text input preserved as-is; analysis and reports in English. AI system prompt explicitly requires English output.  
**Rationale:** Workflow §3 language requirement.  
**Date:** 2026-10-12

## D-011: Schema Additions Beyond Manual

**Conflict:** Manual schema lacks `report_versions` and `tool_executions` tables for full auditability.  
**Decision:** Main Agent adds `report_versions` and `tool_executions` tables. Documented in SPEC.md §3.1.  
**Rationale:** Workflow §5 Phase 0 requires persisting report versions and tool execution records.  
**Date:** 2026-10-12

## D-012: Python Version

**Conflict:** System has Python 3.13 and 3.11. Spec requires 3.11.  
**Decision:** Use `py -3.11` for venv creation and all execution. Never modify system Python. Dependencies isolated in `.venv`.  
**Date:** 2026-10-12

## D-013: Review Queue Logic — Score OR Blocking Issues

**Conflict:** Original contract said `review_queue = score >= 30` only.  
**Decision:** `review_queue = (total_score >= 30) OR (len(blocking_issues) > 0)`. This is consistent with case status `pending_review`. A case enters `pending_review` when review_queue is True. The two concepts are unified: review_queue is the boolean condition; `pending_review` is the business status it maps to.  
**Date:** 2026-10-12

## D-014: find_photo_reuse Authorization Enforcement

**Conflict:** Original contract removed `actor_context` from `find_photo_reuse`, allowing cross-shipment search without auth.  
**Decision:** `find_photo_reuse(photo_id, actor_context)` — the `actor_context` is always provided by the server (from session), never by the model. Authorization is enforced in: (1) UI calls, (2) Agent tool dispatch, (3) export/report generation paths. The model cannot specify `actor_context` or override identity. Cross-shipment matches only reveal metadata (photo_id, event_id, shipment_id) the actor is authorized to see; unauthorized fields are masked.  
**Date:** 2026-10-12

## D-015: Audit Transactional Semantics

**Conflict:** Original contract said `append_audit` "always succeeds".  
**Decision:** `append_audit` is not guaranteed to always succeed. Failure handling: if the audit write fails within a business transaction, the entire transaction rolls back — the business state change does NOT persist. Audit failure = operation failure. If called outside a business transaction (standalone audit), it raises `AuditError` and the caller handles it. Business state changes and their corresponding audit records are written in the same SQLite transaction.  
**Date:** 2026-10-12

## D-016: Submission → Detection → Case Creation → Investigation Chain

**Conflict:** No explicit interface for event submission, photo upload, case creation, and evidence tasks.  
**Decision:** Define the following chain with idempotency rules:

1. `submit_event(actor_context, shipment_id, event_type, payload, source)` → creates event with server-assigned `event_id` and `received_at`. Idempotent: duplicate submission (same shipment_id + event_type + occurred_at + source) returns existing event.
2. `upload_photo(actor_context, event_id, file_bytes, claimed_capture_at, capture_method, manual_observation)` → stores photo, computes SHA-256 and pHash. Idempotent: same SHA-256 for same event_id returns existing photo_id.
3. `create_or_update_case(shipment_id, triggering_event_id, findings, rule_version)` → creates case if not exists for this shipment+triggering event; updates findings if case already exists. Streamlit refresh does NOT create duplicate cases. Idempotent key: `(shipment_id, triggering_event_id)`.
4. `create_evidence_task(case_id, task_type, actor_context, description)` → creates a supplementary evidence request (reweigh, rephoto, rescan). Idempotent: one active task per (case_id, task_type) — duplicate returns existing.

Call chain: `submit_event → evaluate_handoff → create_or_update_case → investigate_case`.

File ownership for these new interfaces:
- `submit_event`, `upload_photo`: Role A (data layer) — `db.py`
- `create_or_update_case`: Role B (evidence) — `services/handoff.py`
- `create_evidence_task`: Role D (application) — `services/actions.py`

**Date:** 2026-10-12

## D-017: Database Injection / Configuration Mechanism

**Conflict:** No unified DB injection mechanism; tests could accidentally write to demo database.  
**Decision:** All service functions accept a `db_path: str` parameter (default `"data/parcelverify.db"`). The `DBConfig` dataclass in `contracts.py` centralizes the default path and test utilities. Every test must use `tempfile.mkdtemp()` to create an isolated database, call `init_db(temp_path)` and `seed_demo(temp_path)` on it. No test may reference `"data/parcelverify.db"` directly. The demo database is only written by `seed.py` and application runtime.  
**Date:** 2026-10-12

## D-018: Display Threshold vs Statistical Reliability

**Conflict:** `has_reliable_sample` implied statistical reliability at 20 shipments.  
**Decision:** Rename to `meets_display_threshold`. 20 shipments is a **demo display threshold** — it controls whether comparison metrics are shown in the UI. It does NOT indicate statistical significance or reliability. The field name and documentation must make this clear.  
**Date:** 2026-10-12

## D-019: Contract History, Authorization Lifecycle & Action State Machine

**Conflict:** No explicit contract/authorization history storage; action lifecycle gaps (rejected → executed?).  
**Decision:**

**Contract History:** Add `contract_history` table to store historical contract snapshots. When a partner's contract or scope changes, the previous version is archived with effective/expiry dates. Authorization checks at a past `at_time` use the version that was active at that time, not the current version.

**Action State Machine (strict):**
```
proposed → approved → executed
proposed → approved → failed (can retry → executed)
proposed → rejected (TERMINAL — cannot transition to executed or approved)
```

**Pre-execution checks (in order):**
1. Action status must be `approved` (not `rejected`, not `proposed`, not already `executed`)
2. Action must not be expired (`expires_at` is null or in the future)
3. Approver must still have authority at execution time
4. Case must still be in a state that allows this action
5. Idempotency: if status is already `executed`, return `already_executed` without re-executing

**Rejected is terminal:** Once rejected, the action cannot be approved, executed, or revived. A new action must be proposed if the situation changes.

**Date:** 2026-10-12
