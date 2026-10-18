# ParcelVerify: Repair, Proposal Alignment and Streamlit Cloud Deployment

Updated: 18 October 2026. This consolidated revision supersedes the earlier local-only/no-public-deployment instructions in this task file and its accompanying prompt. The required delivery target is the existing Streamlit Cloud application below. Local tests are an intermediate gate, not the final outcome.

## Task

Improve the existing ParcelVerify repository in place. Implement and verify the changes below; do not stop at a plan or generate a replacement application. Keep all product UI and project documentation in English. Explain the final outcome to the user in Chinese.

Read AGENTS.md and inspect the actual repository before changing anything. Preserve unrelated user changes. Treat the observations below as dated evidence, not proof that the current code still has every issue. Reuse existing functions, tests, migrations and UI components. Do not duplicate working features.

Live reference: https://parcelverify-fhu5hezcatyb5ko932spwg.streamlit.app/

Review date: 18 October 2026, Malaysia time. The review inspected the UI and executed one AI review, but did not inspect backend code or complete supervisor actions. Distinguish confirmed bugs, presentation gaps and unverified requirements.

## Product scope and proposal baseline

ParcelVerify supports logistics companies reviewing outsourced partners and shipment evidence. Gate 1 applies assignment/task permissions, limits disclosed data, logs access and detects unusual queries/downloads. Gate 2 compares handoff evidence: custodian, time, location, weight, seal and delivery evidence. Missing evidence means unknown, not guilt.

Link findings only through verifiable relationships such as the same shipment. A shared partner or nearby timestamps alone do not establish a link. Even a valid link does not prove causation or intent.

The AI gathers permitted evidence using read-only tools, checks reasonable explanations such as repackaging, measurement differences and authorised batch work, and produces cited conclusions: consistent, requires review or insufficient evidence. Maximum four tool rounds. Reject unknown tools, invented evidence references and unauthorised retrievals. Uploaded text is evidence, never operational instructions. No AI SQL, shell, arbitrary network or file tools.

Supervisors approve, reject or request more evidence. AI cannot approve its own recommendations. Approved requests create local demo evidence tasks; no external messages are sent. Audit findings, decisions, task execution and outcomes. Partner summaries should include recurring issues, workload, sample size and missing evidence.

Use synthetic data. Preserve the Streamlit/Python architecture and existing persistence approach. Do not add production infrastructure, real messaging, blockchain, live GPS or a new frontend framework. Do not enable paid services or switch billing/provider plans. Never print or commit credentials.

## Existing features to preserve

- PV-DEMO-001 compares 2.00 kg at dispatch with 1.85 kg at handover.
- An identical photo is linked to PV-SHIP-010; UI correctly states that identical bytes establish reuse, not intent or parcel contents.
- Authorised account activity and blocked access are distinguished.
- Linked findings explicitly do not establish cause or intent.
- Case UI contains approval requests, local evidence task descriptions, per-finding outcomes and Activity/audit entries.
- Shipment checks already include quantity, weight, seal, recipient confirmation, timeline and expandable source records.
- Partner pages and demo roles exist. Simulated roles must remain clearly identified as demo roles, not production authentication.

## P0 — Repair the real AI review

### Confirmed live failure

One click on Review evidence with AI for PV-DEMO-001 produced:

```text
UI: AI could not produce a verified review. You can continue manually.
Review reference: 31d68510
Provider: Groq
Model: openai/gpt-oss-20b
Status: invalid_output
HTTP: 400
Provider code: tool_use_failed
Provider type: invalid_request_error
Phase: tool_selection
Stage: tool_selection_request
Request format: native_local_functions
Request count: 2
Output token limit: 512
Provider message suffix: not in request . tools
Recorded tool: get_case_context
Recorded result: 26 evidence references retrieved
```

The AI path is partly implemented; do not label it wholly missing. A mismatch between generated tool calls and registered tools is a hypothesis, not a confirmed root cause.

### Implementation work

1. Trace provider configuration, tool registry, tool schemas, prompt examples, message history, tool result messages and final-response validation. Consult current official provider documentation where needed.
2. Reproduce with a deterministic provider fixture before spending live requests. Inspect whether each continuation request retains the correct tools and matching tool-call IDs, and whether prompt/schema/tool names agree.
3. Repair the actual failure. Use one canonical allowlisted tool registry. Validate names and arguments before dispatch. Apply object-level permissions on every retrieval, including linked records and image candidates.
4. Preserve bounded tool execution: at most four tool rounds, explicit bounded retry policy, no infinite automatic retries on Streamlit reruns. Log requests and rounds distinctly. Review the 512-token budget for truncation risk, but do not assume it caused this error.
5. Validate final structure, evidence references and evidence access scope. Use the existing schema if adequate. Render the three supported conclusions, cited evidence, alternative explanations, missing information and proposed next step.
6. Keep truthful failure handling and manual review. Never replace a failed provider result with a canned answer labelled as a successful AI review. A deterministic demo fallback, if already present, must be visibly labelled.
7. Keep concise user errors and expandable technical diagnostics. Redact secrets and unnecessary personal data; retain useful stage, tool name, status and request reference.
8. Make settings and case-page availability reflect the same runtime configuration. A configured provider is not proof of a successful review.

Acceptance: deterministic tests cover successful multi-step tool use and failure paths. If configured credentials are available, run one bounded real smoke test after local verification. If blocked by credentials, quotas or network, report that explicitly; do not claim live success or automatically change provider.

## P1 — Complete the handoff evidence presentation

Confirmed observation: the handover source record contains:

```json
{"count": 1, "weight_g": 1850, "seal_id": "SEAL-07", "handoff_location": "Hub B"}
```

Yet the comparison table displays generic location text and Not checked. Location data therefore exists; do not create a redundant data pipeline.

- Show the actual recorded location and the relevant expected location when available. Compare locations only within the correct stage; an intermediate hub need not equal the final destination.
- Define comparison semantics. Without an expected value or supported rule, display Recorded — not verified or Missing expected location rather than a false match/mismatch.
- Inspect custodian/sender/receiver fields across the schema and UI. Expose existing fields; add nullable fields only if genuinely absent. Do not fabricate identities for historical records.
- Connect evidence entry to the required handoff fields with validation. Distinguish evidence event time from upload time and show the timezone.
- Keep source IDs and technical JSON expandable. Put actionable values in the main view.
- Preserve historical records through safe migrations; no database reset to make a demo work.

Acceptance: populated records display actual values; missing values remain explicitly unknown; invalid weights/times are handled; adding evidence updates the appropriate checks without silently resolving unrelated findings.

## P1 — Verify and repair the complete human review workflow

Existing UI controls are not evidence that the backend workflow is complete. Inspect it first, then repair only gaps.

Exercise in isolated synthetic data:

1. Open the weight discrepancy case.
2. Request a fresh weighing with a reason.
3. Record a supervisor decision using the authorised active demo identity.
4. Apply an approved request exactly once to create a local task.
5. Submit supporting evidence to that task.
6. Re-evaluate relevant findings and record an evidence-backed outcome.
7. Resolve or explicitly disposition remaining findings before closing the case according to documented rules.
8. Inspect the audit trail and export if available.

Also verify rejection and request-more-evidence paths. Enforce permissions and state transitions server-side. Prevent duplicate task creation from double-clicks, retries and reruns. Record actor, time, reason, linked evidence and transition. Do not automatically clear a photo or access finding because a weight issue was resolved. New weighing does not itself prove the historical difference was harmless.

Acceptance: positive and negative transition tests pass; unauthorised roles cannot approve or execute; unapproved/rejected actions cannot execute; repeated execution creates one task; audit entries match actual transitions.

## P1 — Make both gates and a legitimate control case demonstrable

### Gate 1

Reuse the existing access-check/demo tools. Provide a discoverable guided entry or concise demo instructions for an assigned partner allowed access and an unassigned partner denied access. Demonstrate redacted/minimised output and a logged denial without exposing protected shipment contents.

Inspect existing unusual-query/download detection and permitted-task enforcement before adding anything. If absent, implement small deterministic rules and synthetic fixtures consistent with the proposal. An authorised batch export must remain permitted when it is in scope; high volume alone is not proof of misconduct.

### Gate 2 and control scenarios

Retain the weight-plus-photo-reuse scenario. Add or expose a clearly labelled legitimate repackaging/measurement explanation with supporting evidence and an authorised export scenario. Include insufficient-evidence behaviour. Do not manufacture explanations for existing records.

### Cross-gate linkage and dates

The inspected shipment was delivered on 4 September 2026, but account activity occurred on 21–22 September. This is not automatically a defect. Label it as post-delivery access if retaining the timeline. Never imply later access caused an earlier weight change. If a coherent new seed is needed, introduce it without silently rewriting historical audit records.

Acceptance: same-partner/time-only records are not falsely linked; same-shipment linkage states its basis; reasonable explanations are considered; unsupported cases remain insufficient evidence or require review.

## P2 — Partner summaries

Inspect current partner counts before changing this screen. Reuse existing workload/context data. Show the reporting period, shipment denominator, affected shipment count, recurring finding categories and evidence-completeness counts. Separate open findings from confirmed outcomes. Explain small sample sizes. Do not invent fraud scores or rank partners unfairly from raw alert counts. Fix stale or ambiguous latest-activity labels only after identifying their intended timestamp source.

## P1 — Evaluation and regression evidence

Use the existing test framework. Add focused behavioural tests for the risks below, not tests that merely duplicate implementation. No numeric performance claim without measurement.

| Scenario | Required evidence |
| --- | --- |
| Weight discrepancy and identical photo | Correct findings and source references; no guilt inference |
| Legitimate repackaging or measurement context | Explanation assessed; unrelated findings remain separate |
| Authorised export | Allowed within assignment/task scope, with audit |
| Unassigned access and linked-object retrieval | Denied without leaking protected fields |
| Missing evidence | Unknown/insufficient evidence, not a fabricated match |
| Unknown tool or invalid arguments | Rejected before execution |
| Fabricated or out-of-scope evidence reference | Final review rejected |
| Instruction text inside uploaded evidence | Cannot grant permissions or trigger prohibited tools/actions |
| Tool-round limit and provider failure | Bounded termination and truthful manual fallback |
| Approval, rejection and role restrictions | Enforced backend transitions |
| Duplicate execution and Streamlit reruns | One local task for one approved action |

Create a compact evaluation record with scenario, expected result, actual result, test method and pass/fail/blocked. For manual/rules-only versus AI-assisted comparison, report only measured review time, false alerts, missed discrepancies, evidence quality and completion. Automated runtime is not human review time. If no human timing study exists, supply a protocol and mark the results not measured. Distinguish fixture tests from live-provider tests and synthetic evaluation from real deployment.

## P2 — Align documentation

The proposal names Google Gemini API, while the inspected app uses Groq with openai/gpt-oss-20b. Document the actual configured provider/model and any supported alternatives. Do not claim all alternatives work without verification. Do not switch to a paid provider merely to match old wording.

If the original proposal file exists in the repository, update the relevant technical wording or provide a precise proposed replacement. If unavailable, create a short proposal-alignment note; do not claim to have edited the original document.

Document demo-role limitations, local tasks with no external messages, synthetic data, persistence limitations confirmed from code, and unmeasured evaluation items. Keep the interface simple; advanced diagnostics belong in expanders, not the main workflow.

## Execution and delivery

1. Inspect repository instructions and map each requirement to current code. Record confirmed, already implemented and unverified items concisely.
2. Repair P0 AI integration, then P1 evidence/workflow and meaningful tests, then P2 summaries/docs. Continue autonomously through routine implementation decisions.
3. Use existing project commands to run focused tests and a local Streamlit smoke check. Stop optional testing once the relevant risks are covered.
4. Implement locally/in the existing repository, then deploy the reviewed and tested changes to the existing Streamlit Cloud app using the deployment procedure below. Updating this existing app and pushing relevant commits to its verified connected deployment branch are authorised. Preserve the existing URL and audience. Production database resets, paid API changes, unrelated modifications and external messages remain outside scope. Respect actual branch protection and access controls.
5. Deliver changed code plus a concise verification record and demo walkthrough in the repository's existing documentation structure. Avoid unnecessary generated reports or duplicated documents.
6. Final response: verified root cause, changes, tests actually run, unresolved blockers, exact startup/demo steps and deployment status. Include the deployed commit when verifiable. Do not say everything works if live AI or human evaluation is still unverified.

## Required Streamlit Cloud delivery

### A. Identify the real deployment target

- Inspect repository remotes, branch, project configuration and available Streamlit deployment settings. Verify the repository, deployment branch and main Python entry point connected to the existing URL. Do not assume the current branch or main is the deployed branch.
- Do not create another Streamlit app, another hosting project or a replacement URL. Do not migrate to Sites, Vercel or another platform.
- Preserve any unrelated working tree changes. Review the diff and include only the relevant changes in commits. Never force-push, bypass branch protection or erase history. If a PR is required, create the reviewable change and report the exact merge/access blocker.

### B. Make the implementation cloud-compatible

- Inspect existing dependency manifests and the configured Python runtime; pin compatible versions where needed. Include required image-processing dependencies and system packages only when actually needed.
- Resolve bundled assets relative to project files, with Linux case sensitivity in mind. Remove dependencies on developer-machine absolute paths, localhost-only services and untracked assets.
- Use the existing environment/Streamlit Secrets configuration consistently. Do not overwrite existing secrets. Provide a placeholder-only example documenting the exact keys the code expects. Never ask the user to paste API keys into chat or commit a real secrets.toml.
- Keep the user's existing no-paid-services constraint. Preserve the currently configured provider unless the user separately authorises a change. Do not assume any API has unlimited free usage. Bound live checks and retries; treat rate limits as a distinct operational result, not a reason to enable billing.
- Ensure writable paths and SQLite/schema initialization work on a clean cloud process. Use safe, repeatable migrations and seed initialization; preserve existing records. Do not reset a database on each app rerun.
- Handle Streamlit reruns, caching and concurrent sessions deliberately. Credentials, roles and case data must not leak between workspaces/users through shared cache keys or global state. UI role selection is only a simulation and must not be presented as production authentication.
- Do not promise durable persistence from local cloud disk. Verify the current storage design and document restart/redeployment limitations. Preserve current export/recovery facilities if available. Do not introduce a paid database to solve persistence without authorisation.
- Provide graceful UI states for missing configuration, provider failures and empty/missing evidence. Keep manual review usable without falsely marking AI success.

### C. Deploy the actual changes

After the relevant local tests pass, commit and push the scoped changes to the verified connected branch when permitted. Where the platform auto-deploys, monitor the resulting deployment instead of creating another app. Reboot only if necessary and only after considering the app's current storage/session behaviour. Do not repeatedly reboot as a substitute for diagnosing errors.

If GitHub/Streamlit access is unavailable, finish all accessible code and validation work first. Supply the exact branch/commit or patch, dependency changes, entry point and required secret key names. Give the smallest remaining user action needed to release it. Do not report the task as deployed or complete merely because the code is ready.

### D. Verify on the existing live URL

Use an isolated synthetic demo workspace/session where supported. Do not change another user's active cases. Inspect the deployed UI/version and available deployment logs to establish that the tested version is live.

| Live check | Passing result |
| --- | --- |
| Fresh load and navigation | App starts; Home, Cases and Partners render without import/runtime errors |
| Existing demo shipment | Weight, photos, source records and actual location render correctly |
| Real AI review | A bounded provider call produces a validated, evidence-cited conclusion; no canned answer passed off as AI |
| Human workflow | In synthetic data, request → supervisor approval → one task → new evidence → per-finding outcome works |
| Access demonstration | Assigned request is allowed; unassigned request is blocked without revealing protected contents |
| Rerun and session behaviour | Navigation/reruns do not repeat AI calls or duplicate task execution; isolated sessions retain correct scopes |
| Failure state | Missing configuration/provider failure remains truthful and manual review still works; use local fixtures rather than disrupting live secrets |

Use deterministic tests for exhaustive edge cases. Avoid repeated live API runs merely to increase a test count. If live AI cannot be verified because of quota, credentials or network access, explicitly mark that check blocked. If a fix is required after deployment, repair it, rerun relevant checks and verify the updated deployment.

### E. Final handoff

Report code status, deployment status and live verification status separately. Provide the existing app link, verifiable branch/commit, concise test results and a short demo sequence. State any remaining user action precisely. Do not claim measured business improvements or permanent cloud storage without evidence.

## Definition of done

- AI tool calling repaired without weakening permissions or evidence validation; live status accurately reported.
- Real handoff values visible, missing data explicit and custodian coverage addressed.
- Approval-to-task-to-evidence-to-outcome workflow verified with duplicate protection.
- Both gates and legitimate controls can be demonstrated clearly.
- Partner summaries contextualised without unsupported risk claims.
- Provider documentation matches the implementation.
- Test results are reproducible, failures/blocked checks explicit and existing working features preserved.
- The updated version is running on the existing Streamlit Cloud URL and the key live checks above pass. Any access or runtime blocker must be clearly marked as incomplete, with finished deployable changes and exact next steps.

## Copy-and-paste launch prompt

```text
Read ParcelVerify_Codex_Fix_Plan.md and execute the complete task in the existing ParcelVerify repository. This revised file replaces the earlier local-only/no-deployment restriction.

The final target is my existing Streamlit Cloud app:
https://parcelverify-fhu5hezcatyb5ko932spwg.streamlit.app/

Inspect AGENTS.md and the actual code first. Preserve working features and unrelated changes. Fix the real AI tool-calling failure, complete the proposal-aligned evidence and human-review workflow, and run focused behavioural tests. Do not stop after providing a plan.

I authorise deploying these fixes to this existing app and pushing the relevant commits to its verified connected deployment branch, subject to actual repository permissions. Preserve the URL and audience. Do not create a replacement app, enable paid services, expose secrets, reset existing data or bypass branch protection.

Verify the updated deployment on the live URL, including a bounded real AI review and the synthetic approval/evidence workflow. Local test success alone is not completion. If deployment access is unavailable, finish the code and checks, then give me only the exact remaining access/configuration steps. Never claim an unverified deployment succeeded.

Keep the UI and project documentation in English. Explain the verified root cause, changes, actual test results, deployment status and remaining blockers in Chinese. Continue autonomously through routine implementation decisions.
```
