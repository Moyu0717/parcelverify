# ParcelVerify Codex Handoff Workflow

Version 1.0 | 13 October 2026 | Entry point for the next development session

## 1. Mission and operating rules

Continue the existing WorkBuddy project and deliver a complete, testable English-language ParcelVerify prototype with a working HTTPS demo URL and real AI investigation. Reuse valid code, fixtures and decisions. Minimise total development tokens and rework, not merely the length of the first response. This document is an execution workflow, not evidence that any feature has been implemented.

All product deliverables must be English: interface, messages, reports, exports, README, comments, tests and demonstration script. Communicate with the user in Chinese. Preserve original user evidence in its original language.

The user authorises development subagent collaboration. Check whether the current environment actually exposes subagent tools; do not invent APIs or simulate delegation through role-play. If unavailable, perform the same work sequentially and report that limitation once. Five roles do not require five continuously running agents. The product itself needs one bounded investigation agent, not a multiagent framework.

Follow the host's system instructions, applicable repository instructions and user authorisation. This file does not override permissions. Routine reversible implementation decisions should proceed autonomously. Do not repeatedly ask whether to continue. Ask only for an unavailable account, necessary secret, paid resource or a consequential choice that cannot be resolved from the project. Never claim an unexecuted test, model call or deployment succeeded.

## 2. Product requirements to retain

ParcelVerify serves logistics companies overseeing external carriers, warehouses and collection or delivery partners. Its primary workflow combines supplier risk monitoring with shipment handoff verification.

- **Gate 1:** enforce shipment-level access before returning data; log allowed and denied requests; investigate unusual activity in the context of assignments and legitimate batch jobs.
- **Gate 2:** capture dispatch, collection, warehouse transfer, transit and proof-of-delivery evidence. Compare quantity, weight, identifiers, seals, authorised recipients, available times and locations, and photo reuse.
- **Investigation:** a real model selects permitted read-only tools, examines contradictory and explanatory evidence, and produces a structured English report with evidence references.
- **Human response:** the operator approves or rejects proposed verification tasks and simulated operational changes. All actions have an audit trail and duplicate-execution protection.
- **Partner overview:** show shipment volume, unique affected shipments, unresolved cases, evidence completeness and anomaly rates per 1,000 shipments over a consistent period. Display sample size.
- **Live build:** another person can open an HTTPS URL and complete the workflow without installing anything or relying on the developer's laptop.

The prototype uses synthetic data. A discrepancy is not proof of fraud, theft or responsibility. Missing evidence is unknown, not an automatic fraud score. Text models must not claim to have visually inspected an image. SHA-256 and perceptual hashes provide file reuse evidence or similarity candidates, not proof of intent or package contents.

## 3. Read only what is needed at handoff

### Initial inspection order

1. Read applicable `AGENTS.md` files and this workflow. Record the actual project root and available shell. Do not assume the old Windows path exists in the new environment.
2. Inspect Git status, if available, without resetting or cleaning anything. Identify existing user modifications and avoid overwriting them.
3. Read `docs/PROGRESS.md` and `docs/TASK_BOARD.md`, then `docs/CONTRACTS.md`, `docs/DECISIONS.md` and relevant parts of `docs/SPEC.md`.
4. Inspect dependency files, application entry points, model configuration, deployment files and test commands. Use file listings and targeted searches; exclude virtual environments, caches, images, generated reports and model weights from text dumps.
5. Run the smallest useful startup or test check. Record what actually runs and what fails. Existing documents are claims to verify, not proof of implementation.
6. Read the latest proposal and original prototype manual only where a requirement remains unclear. Extract a PDF once if necessary; reuse the extraction. Do not repeatedly load all references.

Authority for implementation: current explicit user requirements, then accepted corrections in this workflow, then current agreed contracts. Code and executed tests establish the actual state. Neither stale docs nor buggy code silently overrides requirements. Record conflicts once and resolve them locally where possible.

### Known context that must be verified

The earlier WorkBuddy handoff reported Python 3.11, Streamlit, SQLite and planned Ollama/Qwen3:4b, with five developer roles and shared files. It reported that Ollama was not installed at that time. The user may have continued work since then. Do not repeat installation, assume unfinished features are still missing, or declare success from these historical notes.

### Output of the inspection

Update one compact `docs/HANDOFF_STATE.md`, preferably under 600 words:

- Actual project root, runtime and launch command.
- Working features, verified by command or browser evidence.
- Broken or incomplete features, with the first actionable error.
- Current hosting and inference configuration; names only, never secret values.
- Active file ownership, next task IDs and dependency order.
- Last tests, current limitations and next exact command.

Report the initial findings in at most eight short bullets, then begin the highest-value implementation task. Do not regenerate six planning documents before writing code.

## 4. Token efficiency policy

These are operating targets, not claimed platform token limits.

1. Maintain one main conversation as the integration owner. Delegate only bounded independent work that benefits from a separate context.
2. Default to two concurrent implementation subagents; allow three when dependencies and file ownership are clear. Do not start all five roles automatically.
3. Prefer a fresh, narrowly scoped subagent context where supported. Supply a short task packet and exact file paths, not the entire conversation or all reference documents.
4. Reuse a role's context for a direct follow-up fix. Start fresh when its responsibility changes substantially. Do not keep idle agents repeatedly reporting status.
5. The main agent owns cross-module reasoning. No duplicate full-repository exploration, independent redesigns or competing implementations of the same feature.
6. Read relevant functions and errors, not complete dependency trees. Save lengthy logs locally; return only exit status, the first meaningful failure and the log path.
7. Batch independent reads and checks when useful. Keep dependent edits, migrations and integration steps sequential.
8. Prefer existing dependencies and service boundaries. Do not replace Streamlit with a new frontend or SQLite with a new database merely for appearance. Make such a change only for a verified deployment or functional requirement.
9. Use focused tests during edits. Run the relevant integration suite at integration, and the full required suite before release. Do not rerun unchanged expensive suites or real model cases without a concrete reason.
10. Use mock model responses for routine control-flow tests, then a small real-model acceptance set. Never present mock output as real investigation.
11. Require concise subagent reports, ideally no more than 250 words. Code and logs belong in files, not chat transcripts.
12. Checkpoint after a completed milestone or before interruption. Avoid repeated long summaries and rewriting every document after every small edit.
13. If a fix fails twice for the same reason, inspect the error and narrow the hypothesis. Do not repeat the same command or ask another agent to restart the whole task.
14. Stop adding optional features after the complete acceptance criteria pass. Report measured token usage only if the environment actually exposes it; otherwise report tasks and tool calls without inventing token savings.

## 5. Main agent responsibilities

The main agent is the technical lead and integrator. It should implement small or tightly coupled changes directly instead of creating a subagent for every task.

Own shared schemas, public contracts, dependency manifests, app entry points, migrations, global configuration, startup scripts, deployment configuration and concise release documentation. Preserve the repository's existing layout where practical.

Before parallel edits, publish exact path ownership and stable public interfaces. A function required by another role must have a defined return shape and failure behaviour. A stub may support early integration only if clearly marked and replaced before acceptance.

Integrate each completed task, inspect its changes, run its relevant checks and resolve conflicts. A subagent's statement that something works is not sufficient release evidence. Delegate source fixes back to the owner when that owner is active; otherwise take ownership explicitly before editing.

For Git repositories, use existing branches or isolated worktrees only where they genuinely reduce conflict. Do not force-push, discard changes or create unnecessary repository copies. Without worktree support, strict file ownership is adequate. Agents must not write to the same demo database concurrently.

## 6. Subagent roles and task packets

Map these roles onto the actual repository before assignment. Paths below are defaults, not a requirement to rename valid existing modules. All tests use temporary databases and temporary upload directories.

| Role | Responsibility | Default owned paths | Required evidence |
|---|---|---|---|
| A Data | Database access, fixtures, safe initialisation, deterministic seed data, history support | `db.py`, `seed.py`, `fixtures/`, data tests | Schema works; seed is repeatable and non-destructive; evidence relationships persist |
| B Evidence | Gate 1, Gate 2, photo checks, priority rules, partner metrics and case creation if assigned | `services/access.py`, `handoff.py`, `photos.py`, `risk.py`, assigned event/case modules, rule tests | Normal, contradictory, explained and incomplete cases behave correctly; permissions enforced |
| C Investigation | Provider adapter, read-only tools, model loop, report validation and execution trace | `agent/`, agent tests | Real tool calls on actual evidence; bounded execution; invalid references rejected |
| D Application | English UI, evidence forms, operator actions, audits, report export | `ui/`, `services/actions.py`, `services/audit.py`, action/UI tests | Buttons use real services; state persists; approval and repeated-click checks pass |
| E QA | Independent scenario validation, browser walkthrough, deployment verification | `tests/integration/`, `tests/acceptance/`, `evaluation/`, `qa/` | Reproducible pass/fail/not-run results; independent browser evidence |

A and D are usually the first useful pair if the foundation is incomplete. B and C can proceed together after data contracts are ready; C uses explicit fixtures until B is integrated. E begins with a short acceptance checklist and performs its substantial work after integration. Skip any role whose deliverable already passes.

### Task packet template

```text
TASK ID: <unique ID>
ROLE: <A/B/C/D/E>
OUTCOME: <one concrete completed behaviour>
PROJECT ROOT: <actual path>
READ FIRST: <specific contract sections and files>
DEPENDENCIES: <completed interfaces or prerequisite IDs>
OWNED FILES: <exact writable paths>
DO NOT MODIFY: <shared files and other active owners>
IMPLEMENT: <bounded requirements and failure handling>
ACCEPTANCE: <observable behaviours and commands>
RETURN: status; changed paths; commands and results; unresolved blocker.
Do not rewrite the architecture, install an unrelated framework, change
shared contracts unilaterally, reset data or duplicate another role's work.
Ask the main agent for a specific interface decision only when necessary.
```

### Role-specific instructions to include in a packet

**A:** preserve raw events; store UTC times and distinguish occurrence from receipt; enable foreign keys; provide a consistent database dependency that services and tests can override. Store time-bounded authorisations and contract history. Never seed or migrate by dropping an existing user database. Demo reset is a separate explicit operation scoped to synthetic records.

**B:** compare the same shipment and packaging level with a defensible baseline. Include source event IDs in findings. Missing GPS, photo or measurements stay unknown. Approved batch jobs never bypass permissions. A quantity mismatch can block acceptance without a new score category. Avoid duplicate cases for repeated processing of the same event. Upload storage and event/case ownership must be explicitly assigned before implementation.

**C:** keep provider selection configurable and credentials server-side. Validate every selected tool against case and operator scope. Limit rounds and total elapsed time. Separate tool execution from final JSON report generation. Include facts, counter-evidence, hypotheses, missing evidence, proposed actions and limitations. Report model failure honestly; never silently substitute canned prose.

**D:** use business services rather than copying rule logic into pages. Make the normal-to-exception workflow obvious. English pages must include partner overview, shipment timeline, evidence comparison, access monitoring, investigation, approvals and audit/export. Keep business state in persistence rather than only UI memory. Show loading, empty, error and AI-unavailable states clearly. Display simulated-data and simulated-role labels without exposing implementation jargon unnecessarily.

**E:** evaluate observable requirements rather than mirroring implementation details. Check denied access, legitimate exceptions, unsupported model claims, action failure/rollback, duplicate execution, persistence and separate demo sessions. Read only the necessary source for diagnosis; report minimal reproduction steps and return fixes to the implementation owner. Distinguish rule tests, mocked agent tests, actual model tests and live deployment tests.

## 7. Correct the previously identified contract issues only if still present

- Use a dedicated approved repackaging event linked to the shipment, handoff, approver and supporting measurements. A batch-query approval or route exception is not a repackaging record. Approval alone does not explain every weight difference.
- Review eligibility is score at least 30 **or** a blocking contradiction. High priority starts at 60 in the initial demonstration rules. Missing evidence may require a separate pending-verification task even with zero score.
- No photo-reuse helper may bypass permissions through an alternative call path. Trusted operator context comes from the application, not the model or an editable partner ID.
- Audit writes can fail. Commit a simulated business change and its audit entry atomically; expose failure without claiming success. Preserve failure diagnostics in a separate appropriate path after rollback.
- Define submission, upload, rule evaluation, case upsert and verification-task interfaces with an owner. Do not leave “submit event → detect → create case” as an unspecified UI side effect.
- Provide one database dependency/configuration mechanism across services so tests cannot accidentally write into the demo database.
- A 20-shipment display threshold is not statistical reliability. Use a name such as `meets_display_threshold`, not `has_reliable_sample`.
- Reject expired or unauthorised actions at execution time. Rejected actions cannot execute. Unique action IDs and transaction logic must prevent duplicates even across concurrent requests.
- Preserve authorisation and contract validity at the relevant time; never evaluate historical activity using only today's partner status. Users cannot choose an earlier time to bypass a current live access check.
- Persist tool runs and incomplete investigations even when no final report exists. Use a run identifier that report versions can reference; avoid a schema that requires a completed report before recording tool calls.

Synchronise only the affected contracts and decisions. Do not treat this list as evidence that the latest code still contains every defect.

## 8. Execution order and checkpoints

### P0 Inspect and choose the delivery route

Complete the short audit in section 3. Preserve working functionality. Identify one feasible hosting route, one inference route and storage needs before broad deployment-specific changes. Update `HANDOFF_STATE` and the existing task board. Exit when the next implementation tasks have owners and stable interfaces.

### P1 Make one real vertical workflow work

Seed a normal shipment, submit a handoff, upload or select evidence, create a real exception case and display its source records. Build the missing pieces only. Exit when data persists across application restart and UI refresh does not duplicate events or cases.

### P2 Complete investigation and action handling

Integrate the actual model, read-only tools, structured reports and operator decisions. Execute approved actions only against simulated records. Exit when a real case runs through evidence retrieval, English report, human approval, idempotent execution and audit export.

### P3 Complete the remaining required scenarios

Finish Gate 1, partner metrics, legitimate-exception handling, missing-data paths and all English UI pages. Add bounded upload validation and reliable error handling. Exit when the local acceptance set passes, except explicitly recorded infrastructure dependencies.

### P4 Deploy and verify remotely

Build deployment assets, configure persistence and inference, deploy through an authorised available route and test from an independent browser context. Exit only when the deployed URL supports real interaction and inference, not just a landing page or precomputed report.

### P5 Deliver and stop optional work

Run the required final checks, complete concise operating instructions and provide the demo URL, source, test evidence and remaining limitations. Do not add marketing pages, extra frameworks or speculative integrations after the release gate passes.

## 9. Live build requirements and deployment decision

“Live build” means an HTTPS application reachable by the reviewer while the developer laptop is off. A repository link, local screenshot, static HTML imitation or tunnel dependent on a personal machine does not meet this project's online objective.

### Select the smallest compatible route

- Inspect any existing deployment first. Keep it if it supports the application, real inference and required persistence.
- Preserve the Python/Streamlit application where practical. Verify that the chosen host actually runs a persistent Python service; a static frontend host alone is insufficient.
- Use one application instance with persistent SQLite and uploads when supported and adequate for demo concurrency. Move to a managed database/object store only if the selected host requires it or the expected workload justifies it.
- Keep inference behind a provider adapter. Prefer the existing Ollama setup on a suitable server if available. Otherwise select an accessible hosted model with verified tool-calling and structured-output support, subject to the user's cost constraint and approval for paid use.
- Check current official hosting/model documentation, account access, memory, idle behaviour, quotas and prices at deployment time. Do not assume a free tier is permanent, large enough or available to this account.
- Do not expose unauthenticated Ollama directly to the internet. Store credentials in server-side secrets; never put them in frontend code, exports, screenshots or commits.

Separate development-token cost from runtime inference/hosting cost. The user's request to minimise development tokens does not authorise paid infrastructure. Prefer available free resources for the demo, but do not promise indefinite free online inference.

### Public demo isolation

Use only synthetic records. Give each visitor a session-scoped dataset or isolated demo workspace; do not let one visitor approve or reset another visitor's cases. Scope database queries and exports consistently. A simulated role selector is acceptable for illustrating workflow but is not production authentication. Administrative actions remain protected. Bound uploads, model requests and retention, and make reset behaviour explicit.

The runtime must not depend on Windows absolute paths or application working-directory assumptions. Pin validated dependencies, provide a portable start command, and support host-provided ports/configuration. Keep reports and photos outside disposable runtime storage, or clearly implement intentional per-session data expiry. Test the declared restart and retention behaviour.

### If credentials or hosting are unavailable

Continue all local code, packaging and tests. Prepare the deployment configuration and document the exact missing prerequisite. Ask for the minimum remaining user action through an appropriate secure channel; never ask the user to paste secrets into ordinary chat. Mark the result `LOCAL COMPLETE — LIVE DEPLOYMENT BLOCKED`, not complete. Resume deployment when access is available.

## 10. Required demonstration and acceptance set

Use fixed seed 42, three fictional partners, approximately 60 shipments, three to five events per shipment and at least 12 self-created/permitted images. Retain useful existing fixtures. Hold back scenario labels from agent-visible evidence.

Main scenario: fictional QuickRun, shipment `PV-DEMO-001`, dispatch weight 2,000 g, seal `SEAL-07`, later weight 1,850 g and a POD file reused from another shipment. Initial weight threshold is the greater of 100 g or five percent of baseline. Unexplained weight contributes 20 points and photo reuse 25, for 45 points. SHA and pHash do not count twice. No responsibility claim is allowed.

| Test | Required observable result |
|---|---|
| Normal shipment | Consistent records; no manufactured exception |
| Weight difference without explanation | Evidence-linked discrepancy and verification request |
| Approved repackaging with supporting reweigh | Relevant explanation considered; unrelated issues retained |
| Reused photo across shipments | Exact match or similarity candidate identified correctly |
| Quantity 100 to 98 without scans | Discrepancy and missing evidence shown; no blame assigned |
| Missing or inaccurate GPS | Unknown or insufficient evidence, not location 0,0 |
| Approved bulk queries | Allowed only within actual shipment permissions |
| Unassigned shipment query | Denied before sensitive fields are returned; denial logged |
| Malicious instructions inside evidence | Cannot change tools, permissions or action approval |
| Invented evidence ID or unsupported assertion | Rejected, marked unverified or referred for review |
| Model unavailable or time budget exhausted | Honest incomplete state; rule/evidence pages remain usable |
| Reject, approve and repeated execution | Rejected action does not run; approved action executes once |
| Failed audit or state update | No partial operational change or false success |
| Refresh and application restart | Required data remains; no duplicate case/action |
| Independent demo sessions | One visitor cannot access or alter another visitor's workspace |
| English review | All product text, reports, exports and instructions are English |
| Remote real-AI test | Deployed server retrieves evidence, calls model and saves a report |

At least three real-model cases should cover the main exception, a legitimate explanation and insufficient evidence. Use deterministic mocks for invalid JSON, timeout and adversarial branches where they give reproducible coverage, and label them accordingly. Compare manual evidence review against agent-assisted review using the same records and rule alerts if reporting time savings. Do not invent accuracy or performance percentages.

## 11. Definition of done

All of the following are required for the complete prototype claim:

- Working HTTPS URL tested outside the developer session; access instructions supplied if needed.
- English UI covering all required functions, with genuine service calls and persistent evidence.
- Real model investigation with visible tool execution and evidence-linked reports on the deployed backend.
- Gate 1 permissions, Gate 2 evidence checks, contextual partner metrics and missing-data handling.
- Human approval, verification tasks, simulated actions, idempotency and audit export.
- Independent demo-session isolation and documented reset/retention behaviour.
- Reproducible source, validated dependency versions and synthetic seed data.
- Passing required tests with separate status for mocked, local real-AI and deployed real-AI checks.
- A short README, deployment guide, test report, limitations and five-minute English demo script.

Expected files, reusing existing equivalents: `README.md`, dependency lock/constraints, `.env.example` without secrets, portable startup/deployment configuration, seed fixtures, `docs/DEPLOYMENT.md`, `docs/TEST_REPORT.md`, `docs/KNOWN_LIMITATIONS.md`, `docs/DEMO_SCRIPT.md` and `docs/HANDOFF_STATE.md`.

Report completion separately for `CORE APP`, `REAL AI`, `ONLINE DEPLOYMENT` and `REMOTE ACCEPTANCE`. A missing model key or hosting account may be a valid blocker; it does not make the live build complete. Provide a clear status instead of silently reducing scope.

## 12. Resume protocol

At interruption, save only the current state, changed files, last meaningful test result, active task ownership and next command. Do not copy the entire conversation into the repository.

On resume, read `HANDOFF_STATE`, relevant task-board rows and the working-tree diff. Check whether old subagents or processes still exist before launching replacements. Recover unfinished work, avoid overlapping ownership, and continue the next unmet acceptance gate. Do not restart planning or reseed/reset data automatically.

## 13. User launch message

Paste this into the Codex session opened on the existing project:

> Read `reference/ParcelVerify_Codex_Handoff_Workflow.md` and follow it to take over the current ParcelVerify project. Inspect the real code and progress first; reuse completed work. I authorise bounded development subagents where supported. Minimise total tokens through narrow tasks and concise reports, while completing the full English prototype with real AI and a working HTTPS live build. Communicate with me in Chinese. Proceed through implementation, tests and deployment preparation without repeated confirmation. Do not purchase infrastructure or expose secrets. If account access is the only remaining blocker, complete everything else and tell me the exact final action required.

The workflow is not automatically loaded merely because it is inside `reference`; explicitly point the receiving session to this file. Provide the whole existing source project and its current docs, not just this workflow.
