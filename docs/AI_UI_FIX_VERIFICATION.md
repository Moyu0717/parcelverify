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

New runs record stage, exception category, HTTP status, request count, selected
model, safe request ID, allowlisted provider code/type and a sanitized message
excerpt. Known API wording is retained; arbitrary reflected prose, unknown values,
`failed_generation`, headers and full payloads are withheld. These diagnostics
are administrator-only. Additive database migrations preserve existing records.

## Checks actually completed

- 105 focused AI, permissions, security and workflow tests passed.
- 29 focused AI-state/Groq transport tests passed (overlap with the above suite).
- 13 UI/widget/build-identity tests passed, including a mocked failed review,
  Settings/case agreement, deliberate retry and navigation without duplicate calls.
- Eight real-browser local screens: Home, linked case, access-only case and
  shipment-only case at 1366 × 768 and 390 × 844. No horizontal overflow or
  Streamlit exceptions. Two desktop case actions appear within 768 pixels.
- Public HTTPS initially returned 200 and showed the new Home/case UI. A real
  hosted navigation defect was found: Streamlit's transparent toolbar intercepted
  Workspace clicks. CSS now excludes the transparent area from pointer handling
  while keeping actual host buttons clickable.

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
