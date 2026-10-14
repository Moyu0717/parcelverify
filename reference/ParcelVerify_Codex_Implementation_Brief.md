# ParcelVerify — Proposal Alignment and Usability Implementation Brief

## 1. Your task

Work in the existing ParcelVerify repository and implement the improvements in this brief. Deliver working code and verified workflows, not just an assessment, a design proposal, or revised button labels.

ParcelVerify helps a logistics company investigate unusual activity involving outsourced partners. It connects **data-access checks (Gate 1)** with **shipment handoff evidence (Gate 2)**. Rules identify and connect findings; AI retrieves permitted evidence and checks explanations; a human decides what happens next.

The current green-and-white visual direction is acceptable. Improve the existing product rather than restarting its design. The goal is a compact, polished investigation tool that a first-time user can understand without knowing its internal architecture. All product copy, demo records, documentation, and implementation handoff deliverables must be in English.

The central user journey is:

**Open a case → understand the evidence → investigate → approve a follow-up if needed → receive evidence → review and record an outcome.**

Finish this journey before adding more dashboards, features, or configuration.

## 2. Sources, inspection, and scope

- Existing deployment: https://parcelverify-fhu5hezcatyb5ko932spwg.streamlit.app/
- Product requirements: `ParcelVerify Proposal(1).docx`, if available in the repository or `reference` directory. Locate it by filename; do not assume the author's temporary workspace path exists on your computer.
- This brief contains the relevant requirements and can be used if that document is unavailable. If another proposal version is present, identify substantive differences rather than silently mixing requirements.
- Read applicable repository instructions and inspect the current branch, changes, application entry point, database schema, investigation tools, permission checks, provider configuration, tests, and demo fixtures before editing.
- Previous UI briefs and reference images provide visual context. This brief is the current task scope. If visual references are available, open the actual files. Do not use an unexplained phrase such as “image 4” as a specification or claim to have seen missing images.

The observations below come from a read-only UI review on 13 October 2026 UTC. They are starting points to verify against the current code, not proof that every unobserved capability is absent. The reviewer did not run AI, submit approvals, or mutate cases. Your repository may already contain subsequent fixes.

| Observed interface | Implementation implication |
| --- | --- |
| Home, Issues, Partners, and Workspace navigation; weight comparisons and timelines are present. | Reuse the working structure and components. |
| Evidence upload, review decisions, approval requests, and audit downloads have visible entry points. | Inspect and complete their integration; do not duplicate them. |
| Weight, photo, and access findings are mainly presented as separate issues. | Verify whether a parent case already exists and make linked investigation usable. |
| AI displayed unavailable; the inspected session had no tool/run records. | Diagnose configuration and execution, and demonstrate a real successful run if credentials are available. This observation alone does not establish a backend failure. |
| A photo-reuse finding for PV-SHIP-010 referenced PV-DEMO-001 in technical evidence. | Surface the authorized matching evidence in the normal UI. |
| A weight comparison displayed 2.26 kg on both sides while reporting a 1.1 g difference. | Use consistent precision and explain tolerances. |
| Evidence images included colored demonstration placeholders. | Replace these with coherent synthetic parcel evidence. |
| Each of three partners showed 20 shipments with issues affecting all 20 shipments. | Check fixture composition and metrics; demonstrate meaningful normal and abnormal examples. |
| Manual issue closure could close remaining evidence tasks without verifying them. | Separate administrative closure from verified resolution. |
| The workspace exposed a simulated identity; request previews lacked a named reviewer or configured delivery contact. | Make the local demo role/task path concrete and honestly labeled. |

Keep the existing stack and service contracts where practical. The proposal names Python 3.11, Streamlit, SQLite, Pillow, SHA-256, ImageHash, Pydantic, and Qwen3 through Ollama. Verify what the repository actually uses. A working supported Gemini or other provider integration may be retained; do not switch models merely to match an outdated technology sentence. Record any discrepancy in the handoff. Do not rewrite the original proposal to conceal missing functionality.

Preserve uncommitted user changes and existing records. Use compatible migrations where necessary. Do not reset a database to make the new UI appear correct. If another process is working in the checkout, avoid conflicting writes. Do not change deployment credentials, publish, or push unless that action is already authorized in the working session.

## 3. Keep the product small

Use three main destinations: **Home, Cases, Partners**. Rename the existing Issues destination only when it genuinely presents cases, and update navigation consistently. Keep Settings, Help, and the clearly labeled demo role switch secondary. Do not create separate top-level products for Gate 1, Gate 2, AI, approvals, evidence, or audits.

Home should show the work that needs attention. Cases should contain the investigation and its follow-ups. Partners should summarize workload and recurring issues. Advanced diagnostics belong behind a secondary disclosure.

Do not add a CRM, a transport-management system, external messaging integrations, a complex role-management console, a speculative risk score, or a new frontend framework for this task. The prototype can simulate users and maintain local evidence tasks. Business state, permission enforcement, evidence associations, and audit records must still be real.

## 4. P0 — One understandable case with related findings

Inspect and reuse the existing data model. Introduce or repair a minimal parent-case relationship only if necessary. Keep individual findings identifiable so they can be explained, reviewed, and resolved separately.

A case should gather findings connected by a clear investigation context: the same shipment, linked evidence, or a documented partner/time relationship relevant to the incident. Do not merge all activity belonging to one partner into an unlimited case. Store the linkage reason, preserve original finding IDs, and make repeated detection idempotent.

Case membership must not widen access. A related shipment or partner can contain records the current viewer cannot inspect. Filter summaries, counts, images, AI inputs, citations, and exports accordingly; do not leak protected metadata through a relationship preview.

Present a case in this order:

1. **What needs checking:** a plain-language title, shipment reference, relevant partner roles, and current status.
2. **What we know:** a short factual summary and the linked findings.
3. **Evidence:** direct comparisons and a compact shipment timeline.
4. **What is still missing:** specific gaps or explanations not yet supported.
5. **Next step:** one visually primary action appropriate to the state.
6. **Activity:** investigation runs, requests, evidence submissions, decisions, and export.

Keep technical IDs, hashes, raw payloads, and tool traces available in details, but do not make users read them to understand the case.

Use neutral language. A discrepancy, repeated image, or denied request is a reason to check; it does not establish theft, fraud, intent, or responsibility.

### Evidence presentation

**Weight:** show earlier and later values, stage, timestamp, unit, source, and the calculated difference. Distinguish recorded precision from display rounding. If a tolerance explains a match, make the tolerance discoverable next to the result. Do not round values to equality while describing an unexplained difference. Missing values remain unknown.

**Photos:** show the submitted image and the authorized matched submission side by side on desktop and vertically on narrow screens. Include shipment reference, stage, time, and source for each. Distinguish exact file equality from a near-image match and name the basis in ordinary language. Use actual detector output; never invent confidence percentages. If the other evidence cannot be viewed, explain the access limitation without exposing protected identifiers or thumbnails.

**Handoffs:** keep available custodian, time, location, quantity, weight, seal, and delivery confirmation connected to their evidence. Make material gaps visible without opening technical JSON. Add missing form fields only where needed by the scenario and supported by the data model; do not turn every submission into a large mandatory form. Use timezone-aware storage and clearly labeled MYT display.

**Access:** separately identify the requesting actor and their owning partner, the requested shipment/data, the assigned actor/partner, the relevant assignment or approved task, and the permission decision. Do not infer partner identity from account prefixes. Check that follow-up ownership and partner statistics use the correct relationship.

Acceptance: a first-time reviewer can identify what happened, inspect the relevant comparisons, name the uncertainty, and select the next step without reading raw JSON or opening several unrelated issues.

## 5. P0 — Make AI investigation real, bounded, and understandable

First inspect why the current interface reports unavailable: configuration, credentials, selected model, hosting/network limitations, tool compatibility, or application errors. Do not expose credentials in UI, logs, commits, or reports.

Implement or complete the proposal's bounded investigation workflow:

- Approved read-only tools cover partner context, shipment timeline, handoff comparison, photo reuse, access scope, contextual events, and partner metrics. Reuse existing tools rather than creating duplicates.
- Enforce a maximum of **four tool rounds per run** in application code, with bounded execution and explicit failure handling. Do not rely on a prompt alone to enforce limits.
- Resolve current identity and object permissions on every retrieval, including evidence reached through links. Validate tool names and arguments before execution.
- Treat uploaded text, partner explanations, filenames, and retrieved records as untrusted evidence. They cannot override instructions or permissions.
- Give the agent no arbitrary SQL, shell, filesystem, or network tools. Server-side provider transport is not an agent-controlled browsing tool.
- Check plausible explanations such as documented repackaging, measurement differences, approved batch work, and authorized export. An explanation without supporting evidence remains unverified.
- Validate structured outputs, conclusion enums, and every evidence reference before displaying the report. A reference must exist, have been available to that run, and remain authorized for the viewer. Reject invalid or invented references.
- Keep conclusions limited to `consistent`, `requires review`, and `insufficient evidence`.
- AI can recommend a follow-up. It cannot approve, execute a follow-up, mark a case resolved, alter permissions, or decide responsibility.

Map the structured conclusion to readable product language, for example:

| Stored conclusion | User-facing label |
| --- | --- |
| `consistent` | Evidence is consistent |
| `requires review` | Human review needed |
| `insufficient evidence` | More evidence needed |

Show a concise explanation, clickable permitted evidence, unresolved questions, and the suggested next step. Keep structured tool traces in diagnostics. Store a concise evidence-based rationale, not private chain-of-thought.

Distinguish **Not checked yet**, **Checking evidence**, **Complete**, and **Could not complete the check**. “More evidence needed” is a valid completed conclusion, not a service error. Explain recoverable failures and preserve the manual review path. When evidence changes, mark earlier AI results as out of date and provide re-investigation.

A recorded demo result may be offered only with an explicit recorded-demo label and provenance. It must not masquerade as a fresh provider response. If credentials or hosting prevent a live run, finish the integration and remaining work, document the exact blocker and required configuration, and mark live verification as blocked. Do not claim end-to-end AI success from mocked tests.

## 6. P0 — Complete approval, evidence response, and human review

Reuse the current approval and upload features to complete this local workflow:

1. An investigator prepares a concrete request: new weight measurement, replacement delivery evidence, or access-context review.
2. A named simulated supervisor approves or rejects the request with a recorded reason.
3. Approval creates or enables the local evidence task through the existing apply mechanism. The effect occurs exactly once.
4. The appropriate simulated partner or operations user sees the task and supplies the requested evidence or explanation.
5. Submission links the response to the task, case, shipment, author, and timestamp. Previous evidence remains traceable.
6. The case returns to review. Recompute affected deterministic checks; offer a fresh AI investigation when relevant.
7. An authorized human records the outcome with supporting evidence and any unresolved findings.

Use the existing case/task views for this workflow. A clearly labeled demo role selector is sufficient; a new identity platform or notification service is unnecessary. Do not claim a local task has been emailed or delivered externally. Authorization must still be enforced in service code rather than by hiding buttons.

Use a small set of visible case statuses, such as **Needs review**, **Waiting for approval**, **Waiting for evidence**, and **Closed**. Derive them consistently from underlying findings and tasks. With multiple open tasks, show their counts and define a deterministic status precedence; do not let one completed child task make the whole case appear complete.

Keep closure outcome separate from status:

- **Verified and resolved:** required findings have supported review outcomes; this does not necessarily mean the original event was normal.
- **Closed with unresolved evidence:** a human deliberately stops investigation, records why, and leaves unresolved facts visible.

Never silently mark missing evidence as verified, or count an administrative closure as successful verification. Requests canceled by closure need their own recorded cancellation reason. Support reopening or follow-up review when evidence arrives later without erasing previous decisions.

Bind approvals to the actual request being approved. A meaningful request edit must not inherit an obsolete approval. Protect state changes with transactions and idempotency so Streamlit reruns, refreshes, retries, or double-clicks cannot create duplicate tasks or decisions.

Keep irreversible or consequential actions explicit, preserve form input on errors, and provide feedback saying what happened and what is next.

## 7. P1 — Enforce and demonstrate Gate 1

Keep permission enforcement deterministic and independent of the AI investigator. Check both object access and permitted fields against the assigned work and its active period. Review suspicious patterns separately from the decision to allow an individual request.

Demonstrate these minimum scenarios using synthetic identities:

- An assigned partner can retrieve only the necessary permitted information.
- An unrelated shipment request is denied without exposing its protected fields.
- A request after assignment expiry is denied.
- An unusual download pattern produces a review finding using an explicit demo rule and recorded workload context.
- An explicitly authorized export with a matching scope and period is treated as a supported exception to the relevant alert; the exception does not clear unrelated findings.

Test authorization at retrieval, image access, export, AI tool, and mutation boundaries. Explain denied requests neutrally. Keep access to diagnostic/audit material appropriately scoped too.

## 8. P1 — Build a convincing, compact demonstration

Create stable, isolated, reproducible fixtures. Seed them without duplicating records or overwriting user work. Use three featured cases, plus enough clean background shipments to make partner summaries meaningful:

| Case | Evidence | Expected behavior |
| --- | --- | --- |
| A — Needs investigation | PV-DEMO-001 or its existing equivalent: 2.00 kg to 1.85 kg; linked reused delivery image; relevant unusual downloads outside normal workload. | Findings appear in one coherent investigation; AI checks explanations; a supervisor can request evidence; a response returns the case to review. Do not predeclare guilt. |
| B — Supported explanation | A recorded repacking event explaining the relevant weight change and an authorized export covering the relevant access activity. | Corresponding findings can be resolved with citations and human review. Any unrelated or missing evidence stays unresolved. |
| C — Incomplete evidence | Missing or unreliable handoff evidence that prevents a conclusion. | Missing facts stay unknown; AI reports insufficient evidence; the next request names the missing information. |

Use believable synthetic package, scale, label, seal, and delivery imagery with no real personal data. Label the dataset as synthetic. Store assets locally for reliable rendering. For an exact-match example, reuse the same file bytes; for a near-match example, use a controlled transformed version and record its ground truth. Images are illustrative evidence, not proof of sealed contents.

Prefer available assets and tools; do not make a new image-generation dependency block functional work. Replace colored text placeholders with coherent evidence assets before calling the visual demonstration finished.

Check that each fixture's captions, measurements, timestamps, assignment periods, detector results, and intended outcome agree. Establish ground truth before evaluation. Keep demo reset scoped to the isolated demo dataset and explicit in its effect.

## 9. P1 — Partner summaries and audit that answer useful questions

For each partner, show only a small useful summary:

- Cases needing review and requests waiting for evidence.
- Recurring finding types.
- Affected shipments out of the total shipments in a stated period.
- Missing-evidence workload or completion, with an explicit denominator.

Define count semantics. One shipment with three findings must not become three affected shipments. A linked case can involve more than one partner in different roles; attribute activity without implying responsibility. Use a declared demo period when the dataset is historical, so real-world current-date filters do not empty the demonstration.

Improve the existing case export rather than adding a reporting subsystem. A readable summary and structured audit should identify the case, linked findings, permitted evidence references, investigation runs and provider/model, validation failures where relevant, requests, approvals/rejections, submitted evidence, decisions, and unresolved items. Preserve chronological history with stable IDs and timezone-aware timestamps. Apply permissions and redact secrets or unnecessary personal fields. Do not claim tamper-proof audit guarantees without implementing and testing them.

## 10. P2 — Refine the current UI through task clarity

Keep the current green-and-white identity, restrained typography, and horizontal navigation. Aim for a professional logistics workbench with clear hierarchy and comfortable spacing.

- Shorten the homepage hero so the initial desktop view exposes useful work. Avoid repeating marketing explanations in the daily workflow.
- Use compact rows or tables for a queue; reserve cards for distinct evidence or decisions. Avoid a wall of equally prominent rounded cards.
- Highlight one primary next step per case state. Keep alternatives visible but secondary.
- Present evidence once in its useful context; eliminate repeated photo galleries and duplicate explanations.
- Use plain action labels such as “Compare photos,” “Request a new weight measurement,” “Submit for approval,” and “Review new evidence.” A button should describe its actual consequence.
- Keep control labels, short help, status, and error text close to the relevant action. Do not compensate for confusing architecture with paragraphs of instructions.
- Give lists useful empty states. Show the next responsible role after a request, with simulated names where necessary for the demo.
- Use consistent units, number precision, date/time format, icon style, borders, spacing, and button hierarchy.
- Make labels persistent, keyboard focus visible, text readable, and controls usable without relying on color alone. Support keyboard navigation and clear validation.
- Verify wide desktop, ordinary laptop, and narrow mobile layouts; stack comparisons on small screens and eliminate horizontal overflow. Keep Streamlit widget labels and accessibility intact when styling.

“Easy enough for a child to follow” means obvious language and actions. It does not mean childish graphics, oversimplified evidence, or hiding uncertainty.

## 11. Implementation order and verification

Work in dependency order and reuse repository conventions:

1. Inspect the current implementation and make a brief requirement-to-code map: already working, incomplete, missing, or blocked. Verify observations that may now be stale.
2. Fix linkage, authorization, state semantics, and compatible persistence changes needed by the main journey.
3. Complete bounded AI execution and the human approval/evidence-response workflow.
4. Integrate direct evidence comparisons, three coherent demo cases, partner summaries, and existing audit export.
5. Refine layout and copy, then perform functional and visual verification.

Do not stop after inspection or implement P2 decoration while leaving P0 unaddressed. If a genuine external dependency blocks one part, complete the other authorized work and state the limitation precisely. Avoid broad unrelated refactoring and repeated full-suite runs without a concrete reason.

Add or adapt focused regression tests for consequential behavior. Reuse the existing test framework. At minimum verify:

| Check | Passing evidence |
| --- | --- |
| Case linkage | Related findings join the intended case; unrelated records remain separate; rerunning detection adds no duplicates. |
| Weight/photo presentation | Precision and tolerance agree; authorized matched images and provenance are visible; restricted comparisons do not leak metadata. |
| AI boundary | A fifth tool round is prevented; invalid tools/arguments and invented references are rejected; injected evidence instructions cannot gain access or execute actions. |
| Human control | AI cannot approve; unauthorized roles cannot mutate decisions; edited requests cannot reuse obsolete approval. |
| Follow-up completion | Approval creates one task; linked evidence submission returns the case to review; a human records a supported outcome. |
| Closure semantics | Unverified tasks remain distinguishable from verified outcomes; administrative closure retains reasons and unresolved facts. |
| Permissions | Unassigned, expired, cross-object, and unnecessary-field access is blocked across tools and export; valid scoped work still succeeds. |
| Reruns and persistence | Refreshes/retries do not duplicate effects; records survive normal application reruns and the supported storage lifecycle. |
| Demo and audit | All three scenarios behave as intended; exports reproduce their permitted event history and outcomes. |

Run a real provider investigation when configuration permits. Record the scenario, result, cited evidence, and tool-round count. Separately identify mocked contract tests. Inspect the final local UI in a browser, take review screenshots when tooling permits, and fix layout defects. If browser or provider access is unavailable, report which acceptance checks remain unverified rather than inventing screenshots or results.

For proposal evaluation, add a small reproducible evaluation script or use the existing harness with labeled synthetic fixtures. Report case/finding-level denominators, false alerts, missed discrepancies, and evidence completeness. Measure review time only from actual timed sessions. Distinguish rules-only detection from AI-assisted interpretation and human decisions. If no human baseline has been collected, provide a short protocol and mark the comparison pending; do not fabricate improvement percentages. Synthetic results do not establish real-world effectiveness.

## 12. Required handoff

Finish with the working repository changes and a concise English handoff covering:

1. What changed, grouped by user workflow.
2. A proposal-alignment checklist with **verified**, **implemented but unverified**, **blocked**, or **not implemented** status.
3. Exact local run commands and required configuration names, without secret values.
4. How to demonstrate Cases A, B, and C, including the simulated roles and evidence response.
5. Tests actually run, real AI verification status, visual checks, and evaluation results or explicitly pending measurements.
6. Any migration, storage-lifecycle, provider, or deployment limitation that affects the demonstration.

Keep the handoff proportional; prefer updating existing project documentation over creating many new reports. Do not mark a capability complete because a button exists. Do not mark a deployment updated merely because local code changed. Leave the implementation concrete, reviewable, and ready for the user's existing deployment process.

Start by inspecting the repository, then implement this brief.
