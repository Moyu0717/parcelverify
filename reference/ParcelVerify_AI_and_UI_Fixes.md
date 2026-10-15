# ParcelVerify — AI Reliability and Usability Fixes
Date: 15 October 2026 (Malaysia)
Public app: https://parcelverify-fhu5hezcatyb5ko932spwg.streamlit.app/

## Objective

Implement all three fixes in the existing project:
1. Diagnose and fix failed Groq investigations and contradictory AI states.
2. Simplify case details using progressive disclosure and plain English.
3. Turn Home into a practical review workspace, with pending work visible before decorative content.

Do the implementation, relevant tests, and visual verification. Do not stop at a proposal. Read AGENTS.md and current project instructions. Preserve unrelated edits and existing records. Use the existing Streamlit stack and green/white identity. Do not change AI providers or rewrite the application.

All product UI and documentation produced for the project must be in English.

## Evidence and scope

Previously observed online:
- Release: groq-free-20261015.1.
- Checked-out commit: a99f08d5493e7d1c0d461a0fdcafdeaf0f9dfb2f.
- Settings reported loaded functions matching source, provider groq, model openai/gpt-oss-20b, credentials configured but unvalidated, execution enabled.
- Before a run, case details showed "AI explanation is unavailable" while the run button was enabled.
- Case details exposed "91 permitted near-image candidates", repeated "Related account activity" headings, actor IDs, and implementation language.
- Home devoted most of its upper area to a large truck image and marketing headline.

Latest user screenshot shows:
- "AI explanation is unavailable. You can still review the evidence."
- "Retry AI explanation"
- "Could not complete the check. Manual review remains available."
- Collapsed Technical details, Activity, and Technical evidence details.

This is evidence of a failed attempt in the UI, not proof of a particular cause. The screenshot does not expose an HTTP status or exception. Do not assume the key is invalid, the model is unavailable, or the free quota is exhausted. Inspect current source and safe diagnostic records.

If code or deployment has advanced since these observations, work from the current version and avoid reverting later fixes.

## P0 — Diagnose the actual AI failure

1. Trace the path from the explicit button action through configuration, provider request, tool execution, output validation, persistence, and UI rendering.
2. Inspect available sanitized failure records before making another provider call. Record the stage of failure, exception category, HTTP status if available, run ID, selected provider/model, and safe provider request ID if available.
3. Check SDK/client configuration, model capabilities, tool-message formatting, JSON schema compatibility, timeouts, token budget, stop reasons, permission checks, and final-result parsing against the actual observed error. Consult current official Groq documentation for any compatibility change.
4. Fix the underlying cause. Do not weaken evidence validation, disable permission checks, discard tool errors, or replace a failed run with a canned successful report.
5. If the blocker is external (invalid credentials, account restriction, quota), show the specific category with a practical next action. Do not claim code has fixed an external account issue.
6. Keep detailed traces restricted to appropriate diagnostic views. Never expose keys, authorization headers, secret values, full provider payloads, or private evidence in generic error messages.

No automatic Gemini, Vertex AI, OpenAI, or other paid-provider fallback. The model identifier openai/gpt-oss-20b on Groq must not be confused with an OpenAI API endpoint. Do not enable paid plans, rotate keys to bypass limits, or change Google Cloud billing settings.

## One consistent AI state model

Use one shared state derivation for the case page and Settings. Separate:
- Provider configuration: key present, execution policy enabled, selected model.
- Last provider outcome: unvalidated, successful request, or categorized error.
- Per-investigation state and evidence version: not started, running, complete, failed, or outdated.

"Configured" means a credential exists, not that it works. "Not started" is not "unavailable". A failure on one case must not automatically label the entire provider unavailable.

Suggested UI behavior:

| Condition | Main message | Action |
| --- | --- | --- |
| Configured, no run | AI review has not started. | Review evidence with AI |
| Missing key | AI review is not set up for this workspace. You can still review the evidence manually. | Disable run; setup guidance for authorized users |
| Execution disabled | AI review is turned off for this workspace. | Disable run |
| Running | Reviewing the available evidence… | Disable duplicate submission; show progress |
| Completed | Show validated result, evidence references, and next step. | Optional explicit rerun |
| Invalid credentials | AI could not connect. Ask the workspace administrator to check the connection. | No automatic retry |
| Rate limit | AI usage limit reached. Please try again later. | Respect provider retry timing when available |
| Timeout/service failure | AI could not finish this review. Your evidence is saved. | Explicit retry when appropriate |
| Invalid tool/output/schema | AI could not produce a verified review. You can continue manually. | Safe error reference; diagnostics for maintainer |
| Evidence changed after result | This AI review used earlier evidence. | Review updated evidence |

Use these as semantic requirements; adapt wording to the actual cause. Do not show multiple repetitive blue/yellow banners for the same state. Prefer one concise status near the action.

"Insufficient evidence" is a successfully completed review conclusion. It must remain distinct from technical failure. Preserve previous successful reports after a failed rerun, clearly labeled with their evidence version/date; never present them as a fresh result.

Persist run outcomes consistently across reruns. Prevent duplicate execution on double clicks or Streamlit reruns. Ensure a failed run releases its in-flight lock; handle abandoned runs explicitly rather than leaving users stuck forever.

## P1 — Simplify case details

An ordinary reviewer should quickly answer:
- What needs checking?
- What evidence supports it?
- What should I do next?

Arrange the default view in this order:
1. Case header: shipment, partner, status, one plain-language summary.
2. Key evidence: concise weight comparison and/or relevant photo pair/account event.
3. AI review: compact state, one action, validated result when available.
4. Next step: one contextually recommended action with alternative actions secondary.
5. Collapsed supporting records and activity.

Preserve existing business rules and approval gates. Do not delete functionality just to make the page shorter.

Specific changes:
- Replace raw labels such as "Weight diff · Photo reuse · Access anomaly" with understandable terms such as "Weight changed", "Photo used on another shipment", and "Access request blocked", only when supported by the records.
- Move candidate counts, hash values, raw schemas/JSON, technical actor IDs, model parameters, matching algorithms, and threshold formulas into appropriately labeled expandable details.
- For the photo pair, keep shipment IDs, relevant dates, the two images, and the actual matching result visible. State "The same photo file appears on both shipment records" for byte equality. Do not describe a near-image match as exact reuse.
- Do not turn 91 candidate matches into 91 confirmed problems. Keep that diagnostic count out of the default view.
- Group account events under one heading; clearly distinguish authorized activity from blocked requests. Do not label authorized access suspicious without separate evidence.
- Use real display names when available; otherwise a neutral label with an identifier in details. Never invent names or infer ownership from an ID prefix.
- Explain any cross-record linkage in one short sentence beside the related evidence. A shared shipment can establish a relationship, but not causation or guilt.
- Preserve independent Data Access and Shipment Evidence findings and their individual review outcomes. Never force unrelated findings into one incident.
- Consolidate overlapping technical expanders where practical. Keep evidence accessible and navigable; do not hide the basic reason a case needs review.
- Keep synthetic/demo labeling, human approval requirements, and "no message sent" behavior clear where relevant.

No giant explanatory paragraphs, raw debug text, decorative badges for every field, or tutorial content above the work.

## P1 — Make Home a work queue

Replace the dominant promotional hero with a compact workspace introduction, for example:
- Heading: "Review workspace"
- Supporting line: "Check flagged records and decide the next step."

Show this above the fold on a normal desktop:
1. Compact navigation and page heading.
2. A small status summary: Needs review, Waiting for approval, Waiting for evidence, Closed.
3. The beginning of the actionable case list, including at least two rows at 1366 × 768 where feasible.

The work queue is the main content. Put search and relevant filters near it. Status counts should filter the list predictably and indicate the active filter.

Remove the large truck image from the main workflow or reduce it to a secondary element below the queue. Do not replace it with another oversized hero, gradient banner, or illustration. Move the "Find an issue / Compare evidence / Choose the next step" tutorial to Help or an optional onboarding area.

Retain a restrained green/white visual identity, consistent typography, clear alignment, modest borders, and purposeful spacing. Use labels and icons together where meaning is not obvious. Status must not rely on color alone.

On mobile, present readable stacked case summaries with clear action buttons. Avoid horizontal page overflow and tiny table text. Maintain accessible contrast, visible keyboard focus, useful labels, and comfortable touch targets. Use the existing component system rather than adding a heavy design library.

## Verification and acceptance

Use focused tests for behavior; avoid spending time writing brittle tests that merely mirror layout code.

Behavior checks:
- Configured + never run does not show unavailable.
- Missing key and disabled execution prevent requests.
- Every failure category produces one truthful status and a safe diagnostic reference.
- Invalid outputs remain failures; insufficient evidence remains a valid conclusion.
- A rerun/double click does not duplicate API requests.
- Failed runs can be retried deliberately without a permanent lock.
- Tool allowlists, permission checks, evidence citation validation, four-tool-round limit, human approval, and manual review still work.
- No paid-provider fallback or API calls on page load/navigation.

Visual checks at desktop 1366 × 768 and mobile approximately 390 × 844:
- Home foregrounds pending work, not marketing.
- Case details show key evidence and a clear next step.
- Candidate counts and raw technical data are collapsed by default.
- The same AI state has consistent wording on Settings and the case page.
- No clipped controls, unreadable text, or horizontal page overflow.
- Review access-only, shipment-only, and legitimately linked cases.

Use mocked tests first. A single small synthetic-data live investigation may be used after private credentials and the intended account setup are available. Capture the actual result or categorized error. Do not loop live calls, perform load tests, or repeatedly consume quota while guessing.

For a genuine successful live investigation, record the run ID, provider/model, completion status, permitted tools actually used, and validated evidence references. Do not present mocks or screenshots of configuration as live AI success.

## Delivery

Follow existing repository and deployment authorization. Preserve user records; do not reset a workspace to make the fix look successful.

Provide:
1. A short root-cause explanation supported by diagnostic evidence; if unresolved, state exactly what evidence is missing.
2. Changed files and the implemented fixes.
3. Focused test results.
4. Before/after screenshots of Home and case details using synthetic data, without secrets.
5. Live investigation outcome, or an explicit pending/blocker status.
6. Source commit/release and a truthful distinction between local verification and hosted verification.
7. Only the concrete remaining owner steps, if any.

The task is not complete merely because copy changed. All three requested areas must be addressed, and any remaining live AI blocker must be clearly identified.

