# AI review and workspace verification

## Authorized Cloud delivery — 18 October 2026

The updated fix plan authorizes the existing application at
`https://parcelverify-fhu5hezcatyb5ko932spwg.streamlit.app/`. The baseline was
independently read from the public app: repository `Moyu0717/parcelverify`,
matching `main` commit `3003b9dcacf03884da3310d61a0f50e9d32e11ed`, entry `app.py`,
dataset `linked-cases-v5`, Groq credentials present and execution enabled. No
provider call was made during baseline inspection. The local directory still
has no Git metadata; GitHub's connected Git data API preserves the remote base
tree and updates main with an expected-head lease, never a force push.

Candidate release: `groq-repair-20261018.1`. Deployment and live acceptance are
pending until their actual results are appended here. The local-only statements
in the next section describe the earlier implementation phase, not the current
authorization. The URL, audience, server Secrets and existing data are preserved.

Pinned dependencies are reused. Runtime identification exposes Python and entry
point without secrets. Bundled images resolve from the project directory;
Pillow's built-in font is the Linux fallback. Writable data stays below
`PV_DATA_DIR` or the repository's `data/workspaces`, with separate random-token
workspace databases and repeatable additive migrations. The shared Groq ledger
stores usage counts, not credentials or case contents. No mutable role/case state
is cached across sessions. Local disk remains ephemeral; recovery/export limits
from the earlier section still apply.

## Current local repair — 18 October 2026

Release: `local-repair-20261018.1`, source build `fb07b8f0e37690c8`. This round is local only: no Git push,
public deployment, provider/billing change, external message or existing-data
reset. No applicable `AGENTS.md` was found in the repository or its ancestors.
The workspace has no `.git` metadata; changed files remain available in place.

### What was confirmed, reused and still unverified

The latest owner's native-function run fetched `get_case_context` successfully,
then Groq rejected request 2 with HTTP 400 / `tool_use_failed` /
`invalid_request_error`, message suffix `not in request.tools`. This is **not**
the older first-request/no-tools failure described in the historical section.
Current continuation code already retained all eight tool definitions and
paired IDs. Missing continuation tools is therefore not an established cause.
The confirmed failure is provider-side rejection of an unregistered generated
function. The exact rejected name was removed by the old sanitizer and cannot
be reconstructed from that record. A namespace/name mismatch remains a
hypothesis, not an observed literal function name.

Deterministic mocked HTTP reproduces the observed sequence: a successful context
read, an unregistered-function rejection on request 2, and either a valid
continuation or a repeated rejection. The repair provides:

- One canonical `agent/tool_registry.py` for names, descriptions, schemas and
  arguments, consumed by contracts, provider declarations and dispatch.
- Original provider function IDs retained in correctly paired tool messages.
- Exactly one correction retry for a selection-phase `tool_use_failed`; this
  shares the existing one-retry allowance with transient failures. There are
  still at most four executed tool rounds and six requests. No retry for quota,
  authentication, unauthorized data, fabricated citations or invalid arguments.
- A closed list of exact function names in correction feedback. Evidence cannot
  introduce functions. Unknown calls are never aliased or executed.
- Separate request history and executed-round counts, declared function names,
  safe HTTP metadata and canonical error wording. No raw failed generation,
  prompt, authorization header or key is retained.

The 512-token selection budget was reviewed against Groq's reasoning guidance.
The supplied failure was a tool-validation HTTP error, not a `length` finish.
The budget remains bounded at 512/1,024 for selection/report; truncation remains
a failure, without saving a conclusion. The final strict schema and current
object/evidence permission checks are unchanged. One corrected mock completes
with real locally retrieved citation IDs; repeated rejection stops truthfully.

Existing permissions, deterministic access/download detection, approved export,
linked shipment findings, task execution, finding outcomes and audit export
were reused. Actual additional repairs:

- Stage-local location now displays its actual record (for example Hub B),
  expectation and comparison status. An intermediate hub is never compared with
  the delivery destination. Delivery GPS retains its separate existing rule.
- Nullable custodian/sender/receiver JSON fields require no schema migration.
  Historical missing identities remain Unknown. Recorded claims do not verify
  an identity or route. Event and upload times are shown separately in MYT.
- Invalid/nonfinite measurements, fractional package counts and ambiguous event
  timestamps are rejected before persistence. Future source handoffs remain
  detectable anomalies; task responses retain the existing no-future-time rule.
- Clarification tasks remain usable while approval is pending. Revised responses
  can add context to the same observation time: each submission has its own
  source identity, while the existing submission key still deduplicates retries.
  Equal observation times use received time and record order to select the latest
  recorded correction, retaining both submissions in the audit.
- Rejection audit operation is correctly named `action_rejected`. Active demo
  identities and reasons are recorded; no fictional supervisor name is displayed.
- Post-delivery account access is labelled explicitly, without implying it
  caused an earlier weight difference. Partner context uses a permitted shipment
  denominator, all-history period, distinct affected/category counts, field
  completeness, human outcomes and small-sample caveats.
- SQLite's template connection closes before Windows rename. A SQLite connection
  context alone commits/rolls back but does not close; no data reset is involved.

### Reproducible checks

Commands use `.venv\Scripts\python.exe -X utf8`. Counts below overlap and must
not be added into a claimed independent sample size.

| Check | Actual result | Method |
|---|---|---|
| Existing AI, native protocol, state, security and Groq guard suite | 80 passed | pytest, mocked HTTP and isolated databases |
| Second-request rejection, bounded correction, canonical arguments and truncation | 9 passed | `tests/test_fix_plan_ai.py` |
| Actions, permissions, new workflow/demo regressions | 65 passed | agent's focused actions/security suite |
| Completion, evidence, workflow and seed timing | 36 passed | focused pytest after Windows connection fix |
| Clarification drafts, existing UI approvals, AI state/navigation | 9 passed | real Streamlit widgets, mocked AI |
| Desktop/mobile evidence, next-action and partner views | 18 passed | local browser, 1366×768 and 390×844, no AI |
| Final input/AI fixture/build check | 27 passed | handoff fields, corrected native calls and build/runtime tests |
| Same-time correction / completion check | 24 passed | latest received evidence selected with retained audit |
| Live Groq success | Blocked | no local `GROQ_API_KEY` or secrets file; no provider calls made |
| Hosted behavior for this release | Not tested | public deployment explicitly not authorized |

### Scenario evaluation

| Scenario | Expected | Actual / evidence | Status |
|---|---|---|---|
| Weight and exact photo pair | Independent flags and real references, no guilt claim | PV-DEMO-001 and linked PV-SHIP-010; existing rules and completion tests | Pass, synthetic |
| Packaging/measurement explanation | Use approved, linked measurements | PV-SHIP-011 suppresses unsupported weight flag | Pass, synthetic |
| Approved export | Allowed only in recorded scope/period | Existing access-pattern evaluation returns authorized_export | Pass, synthetic |
| Unassigned/linked-object access | No protected data; denial logged | Security tests and minimized-output assertion | Pass, synthetic |
| Missing evidence | Unknown, not a fabricated match | PV-SHIP-021 retains missing fields | Pass, synthetic |
| Bad tool/arguments or injected instructions | No execution or authority grant | Registry and existing agent-security tests | Pass, mocked |
| Invented/out-of-scope citation | No saved report | Existing final report/security tests | Pass, mocked |
| Repeated provider failure / round limit | Bounded stop, manual workflow intact | New second-request fixture plus existing bound tests | Pass, mocked |
| Approval/rejection/duplicate execution | Server authority and one approved task | Completion/action tests; actor, reason and audit assertions | Pass, synthetic |
| Request more, revised response, closure | Preserve other findings; explicit disposition | New workflow and widget regressions | Pass, synthetic |
| Real AI investigation after this repair | Completed report with permitted tools/citations | No private key in local environment | Blocked |

`qa/evaluate_demo.py` measured 60 synthetic shipments, three featured cases,
56 background controls, no missed required categories, no false-alert shipments
and 59/60 records with required field presence. These are fixture/rules results,
not production accuracy or verification of parcel contents. Results are in
`qa/artifacts/demo-evaluation.json`; browser captures are in
`qa/artifacts/review-workspace/`.

For manual versus AI-assisted review, recruit reviewers, counterbalance case
order, use equal evidence and record actual start/finish time, missed discrepancies,
unsupported alerts, citation quality and completed decisions. Do not use test
runtime as human review time. No human study has been run: all comparative review
time and productivity results are **not measured**.

### Proposal alignment

`reference/ParcelVerify_Full_Idea.pdf` exists and has not been edited. Proposed
replacement for its Gemini-provider technical wording:

> The prototype uses Groq Chat Completions at the official
> Groq endpoint, with configurable GROQ_MODEL (default openai/gpt-oss-20b).
> Only local, read-only, permission-checked evidence functions are available to
> the investigation. Final reports require structured validation and authorized
> evidence references; all business decisions require human approval. No other
> provider or paid fallback is activated.

Alternative Groq models are configurable but not live-verified here. Demo role
selection is not production authentication. Evidence tasks are local records;
they send no external messages. Workspaces expire after 24 hours inactivity or
host storage loss; recovery tokens only work while that storage survives. All
records/images are synthetic. The latest implementation is not publicly deployed.

For startup and both gates, follow `docs/DEMO_SCRIPT.md`. For one real smoke test,
privately configure the existing Free Plan key, run the mocked tests first, then
run `qa/real_ai_acceptance.py --confirm-free-plan` once. No key should be pasted
in a report, chat, screenshot or tracked file.

## Historical verification — 16 October 2026

## Scope and preserved behavior

Home is a review queue rather than a promotional hero. Four status controls filter
the current queue, with search and evidence type beside it. Desktop 1366 × 768
shows two case actions above the fold. Mobile uses stacked summaries.

Case pages show understandable findings, measured weights, the actual photo
comparison and a next action. Candidate counts, account identifiers, formulas and
raw records are available in collapsed details. Authorized requests are summarized
separately from blocked requests. Separate access and shipment finding outcomes,
evidence provenance and the human approval/submission/review workflow remain.

`services/ai_state.py` derives the state for both case pages and Settings. Key
presence is separate from provider outcome and a validated saved review. Never
started, running, failed, completed and outdated are distinct. A failed retry
retains an earlier validated report with its date and evidence-version warning.
Interrupted stale runs can be retried without deleting history. No navigation
starts inference. The existing durable click tokens and bounded Groq-only guard
remain; no paid-provider fallback exists.

## Diagnosing the reported failure

The owner supplied `real-70bb23d3-4399-459f-8fb9-f1c8fc404ce4`, started
2026-10-15T16:45:46.453544+00:00, status `error`, model
`openai/gpt-oss-20b`, error `AI provider returned HTTP 400`, tools `[]`.
This establishes failure before a tool executed, but does not establish an
invalid key, unavailable model or quota exhaustion. The old run did not preserve
Groq's reason; it cannot be recovered retrospectively from that record.

One controlled public synthetic investigation reproduced the failure on checked-out
commit `c0a971288434c6ef5c9d536c659a1f591faf5768`, source build
`aad81ba1d6d05ffe`, with loaded Python functions verified against source and
dataset `linked-cases-v5`. Run `real-fb1b3dc7-7dd3-4ed9-aab7-fb06e2769cc4`
made exactly one provider request and no local tool calls. Groq returned HTTP 400,
code `tool_use_failed`, type `invalid_request_error`, at `tool_selection_request`;
request ID `req_01m508128hevcr1m1v1qks8c5c`. No report was saved. The previous
record's cause cannot retrospectively be proven identical.

The confirmed defect in the request path was a tool protocol mismatch: the prompt
asked a tool-capable model to select record readers, but the request declared no
native functions and requested JSON content. Groq rejected tool selection rather
than returning a report. Its message was conservatively redacted; no original
body or failed generation was retained. We do not infer a credential or quota
problem from this result.

The correction declares **only the existing local read-only whitelist** as native
functions, accepts a single function choice, and converts it to the existing
permission-checked dispatcher. Subsequent messages pair each function call with
its actual local result. The final request remains a separate strict JSON report
request without native tool declarations. Unknown or parallel calls, malformed
arguments, unauthorized requests and unverified citations remain failures.
This follows Groq's [local function protocol](https://console.groq.com/docs/tool-use/local-tool-calling)
and its [structured-output restrictions](https://console.groq.com/docs/structured-outputs).

The correction is tested with mocked HTTP responses. The one live investigation
was used to diagnose the failure; no second live attempt was made. Successful
real investigation after the protocol correction remains **unverified**.

New runs record stage, exception category, HTTP status, request count, selected
model, safe request ID, allowlisted provider code/type and a sanitized message
excerpt. Known API wording is retained; arbitrary reflected prose, unknown values,
`failed_generation`, headers and full payloads are withheld. These diagnostics
are administrator-only. Additive database migrations preserve existing records.

## Checks actually completed

- Final protocol/state/security/UI regression suite: **64 passed**, all model
  responses mocked. Build/runtime identity suite: **5 passed** separately.
- 105 focused AI, permissions, security and workflow tests passed.
- 29 focused AI-state/Groq transport tests passed (overlap with the above suite).
- 13 UI/widget/build-identity tests passed, including a mocked failed review,
  Settings/case agreement, deliberate retry and navigation without duplicate calls.
- Fourteen real-browser local screens: Home, linked case, photo comparison,
  AI review, next step, access-only case and shipment-only case at
  1366 × 768 and 390 × 844. No horizontal overflow or
  Streamlit exceptions. Two desktop case actions appear within 768 pixels.
- Public HTTPS initially returned 200 and showed the new Home/case UI. A real
  hosted navigation defect was found: Streamlit's transparent toolbar intercepted
  Workspace clicks. CSS now excludes the transparent area from pointer handling
  while keeping actual host buttons clickable.
- Public read-only verification of application commit `1e607ff4557c43ebb67ae8fdc922c2b07f30ceb4`
  confirmed release `groq-review-20261016.2`, source build `1334003d26a242aa`,
  loaded functions matching source and dataset `linked-cases-v5`. No provider
  request was made by that check. Mobile review then caught a menu that stayed
  open after navigation; navigation now replaces that menu so the queue is visible.
- Final application commit `dc710918926c9762256daf272dc61c618fd41440` reached
  the hosted checkout with source build `3322e4b72a852f3d`. The final read-only
  probe correctly stopped: the running process still held old
  `ui.design_ui.navigate`. **The final menu correction is not yet verified live.**
  The owner must reboot the Community Cloud app to refresh that cached module.

The final read-only public check is separate from the diagnostic live-run artifact;
`diagnostic-live-result.json` preserves the single failed live attempt and
`public-result.json` records the latest checkout/UI check. Do not interpret a
successful read-only probe as a successful live investigation.

All automated model tests use mocked transport and isolated temporary databases.
They do not prove that a real provider investigation succeeds.

## Artifacts and execution

Actual public before screenshots (old release `a99f08d`):
`qa/artifacts/ai-ui-fix/before-public-home.png` and `before-public-case.png`.
Final local screenshots and viewport assertions:
`qa/artifacts/review-workspace/` (`results.json` includes exact viewports).
Historical October 14 screenshots are separately identified in that manifest;
they are not a fresh baseline of the immediately previous version.

Run locally with `.venv\Scripts\python.exe -m streamlit run app.py`.
Keep `GROQ_API_KEY` privately in `.streamlit/secrets.toml`, or Streamlit Community
Cloud app Secrets. Do not put it in source files, screenshots or chat.

`qa/ai_review_probe.py URL EXPECTED_COMMIT` checks the actual public checkout and
loaded functions. Only explicit `--ai` enables one synthetic investigation, after
build and configuration checks. It never loops AI attempts or resumes an owner's
private workspace. Hosted AI outcome is recorded separately in its result artifact.

## Remaining live check

First reboot the app from the owner's Streamlit workspace: open
`share.streamlit.io`, select this app's overflow menu, choose **Reboot**, then
confirm the reboot. In the app, Settings → Build information must show the current
checkout and **Loaded Python functions match the checked-out source**. The public
visitor cannot perform the owner-only restart.

After confirming release `groq-review-20261016.2` and matching loaded functions in
Settings, the owner can open one synthetic case and click **Review evidence with
AI** once. A successful run must include permitted tool executions and validated
citations; a quota error or invalid output remains a failure. On failure, download
the administrator-only diagnostic record and share only its sanitized metadata.
Do not repeatedly retry, enable another provider or reset existing records.
