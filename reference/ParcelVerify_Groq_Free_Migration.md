# ParcelVerify — Groq Free Plan Migration Brief

## Goal and scope

Replace ParcelVerify's active Gemini application integration with Groq for a small, free-plan hackathon demo. Implement the change in the existing repository; do not merely propose a plan. This does not change the model powering the Codex coding session.

Preserve the current UI, records, approval workflow, and independent detection streams. Avoid a framework rewrite, unrelated UI redesign, or database reset. Read AGENTS.md and relevant project instructions first; inspect the current provider implementation and repository status before editing. Preserve unrelated work.

The owner wants no paid-provider fallback. Account billing status is controlled by the provider, not by a variable in this application. A Groq key alone does not prove the account is on Free Plan. The owner should keep the Groq account on Free Plan and not enable a paid upgrade.

Changing providers does not cancel existing Google Cloud debts or stop unrelated cloud resources. Do not claim otherwise or change the owner's cloud billing configuration.

## 1. Discover and replace the active integration

- Locate Gemini clients, model configuration, agent orchestration, health checks, startup calls, tests, deployment configuration, and documentation.
- Replace the active provider with Groq using its official SDK or supported OpenAI-compatible endpoint.
- Consult current official documentation before selecting a model. Choose a currently available model suitable for local function calling and structured output validation; document the actual selected model and its limitations.
- Keep the model configurable via GROQ_MODEL. Do not copy a model ID from an outdated guide or silently select a different provider.
- Disable Gemini calls and any automatic fallback to Gemini, Vertex AI, OpenAI, or other paid endpoints, including background probes and fallback exception handlers.
- Leaving an old Gemini environment variable present must never reactivate Gemini.
- Remove unused dependencies only where the migration makes them unnecessary.

## 2. Configuration and secret handling

Use environment variables or Streamlit secrets, consistently with the existing application. Define explicit precedence and never log secret values.

Example Streamlit secrets template (placeholders only):

```toml
AI_PROVIDER = "groq"
GROQ_API_KEY = "REPLACE_PRIVATELY_WITH_YOUR_KEY"
GROQ_MODEL = "REPLACE_WITH_VERIFIED_SUPPORTED_MODEL_ID"
```

Replace the model placeholder in the delivered example with the verified model ID, but never insert a real key into committed files.

- Keep local secrets and .env files ignored by Git.
- Provide the matching environment-variable template and exact local setup instructions.
- For hosted Streamlit, explain how the owner enters the values in app Settings → Secrets.
- Missing or invalid credentials must produce a clear English status and leave non-AI features usable.
- Never request a key in a chat message, commit it, print it, or include it in screenshots or logs.
- If no key is available, complete the implementation and mocked tests, then identify the single remaining private configuration step.

## 3. Preserve ParcelVerify's actual behavior

Data Access and Shipment Evidence are independent detection streams sharing a review workspace. Support access-only, shipment-only, and genuinely related cross-stream cases. Link findings only through verifiable relationships; the same partner or nearby timestamp alone is insufficient. Do not infer causation from a link.

Preserve:
- Maximum four tool rounds per investigation, with bounded model requests.
- Read-only allowlisted investigation tools.
- Permission checks on every evidence retrieval.
- Validation of tool names, arguments, record IDs, evidence citations, and final output.
- Existing conclusion categories: consistent, requires review, insufficient evidence.
- Human approval before any operational action.
- Existing evidence follow-up, audit records, and distinction between verified resolution and administrative closure.
- Uploaded or retrieved text is evidence, never instructions.

Use local function calling through existing safe tools. Do not enable provider-hosted browsing, code execution, arbitrary SQL, shell commands, external MCP servers, or unrestricted filesystem/network tools.

Preserve deterministic local weight comparison, SHA-256 checks, and photo similarity hashing. A text-only model may reason over those tool results but must not claim to have visually inspected a photo. If the current application requires visual reasoning, document the capability gap explicitly rather than fabricating visual findings.

## 4. Bound usage and handle failures

- Run an investigation only after an explicit user action.
- Do not call the model on page load, navigation, Streamlit reruns, or periodic connection checks.
- Deduplicate in-flight/completed submissions so reruns or double clicks cannot start the same investigation twice.
- Allow deliberate reruns and new evidence to create a new investigation; do not reuse stale conclusions after evidence or permissions change.
- Set explicit timeout and output-token limits, a total request budget per investigation, and at most one transient-error retry per investigation. Disable hidden SDK retry multiplication.
- On HTTP 429, stop the investigation and show a concise English message indicating a temporary usage limit. Do not loop, rotate keys, or switch to a paid provider.
- Handle authentication failures, unavailable models, timeouts, malformed output, and invalid tool requests distinctly.
- Never present partial or failed investigations as successful AI conclusions.
- Keep manual review and deterministic checks available when AI is unavailable.
- Add a modest configurable application usage guard appropriate to a public demo. Explain its scope and persistence: per-session counters are not global cost controls, and local counters may reset on restart.
- Do not add a complex administration dashboard for this migration.

## 5. Verification

Use mocked provider responses first. Add or adapt focused tests for:
1. Valid tool-call sequence and validated final conclusion.
2. Rejected tool names, invalid arguments, invented evidence IDs, and unauthorized evidence.
3. Four-round/request-budget enforcement and bounded retries.
4. HTTP 429, missing key, invalid key, timeout, unavailable model, and malformed output.
5. No duplicate calls on rerun or double submission.
6. No Gemini or other paid-provider fallback.
7. Manual review and deterministic checks still work without AI credentials.

Do not run bulk live API tests or chargeable comparison benchmarks. When the owner has privately configured the intended Free Plan account, run only one small synthetic-data smoke investigation to verify tool use and final output. If that cannot be verified, mark live AI verification as pending.

Do not represent mocked results as a real AI run. Do not silently fall back to a fake/demo AI answer.

## 6. Deployment and handoff

- Update requirements, example configuration, relevant README/setup sections, and provider/model labels.
- Follow the repository's established Git and deployment workflow and existing authorization. Do not overwrite unrelated changes or claim a push/deploy that did not happen.
- Clearly distinguish: implemented locally, tested locally, committed/pushed if applicable, and verified on the public Streamlit app.
- Identify the branch, entry point, and commit to deploy. The expected app entry is app.py, but verify against this repository.
- Give exact instructions for updating Streamlit Secrets and restarting the app when necessary.
- Verify the hosted app uses Groq and the intended model without revealing credentials. If host access is unavailable, supply a short owner checklist and leave hosted verification pending.
- Removing an old key from Streamlit secrets does not revoke it at Google; explain that distinction without changing cloud resources.

Deliver a concise completion report:
- Files changed and why.
- Selected provider/model and checked capabilities.
- Tests run and results.
- Exact private key configuration instructions.
- One live smoke-test result, or a clear pending status.
- Deployment status and remaining owner actions.

## Official references

Recheck current availability and limits during implementation:
- API keys: https://console.groq.com/keys
- Models: https://console.groq.com/docs/models
- Tool use: https://console.groq.com/docs/tool-use/overview
- Rate limits: https://console.groq.com/docs/rate-limits
- Billing: https://console.groq.com/docs/billing-faqs
- OpenAI compatibility: https://console.groq.com/docs/openai

This brief specifies a migration target, not a claim that the repository has already been changed.

