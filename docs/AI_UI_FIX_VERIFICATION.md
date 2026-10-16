# AI review and workspace verification — 16 October 2026

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
