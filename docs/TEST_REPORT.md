# Test report — 13 October 2026

Release status: **LOCAL COMPLETE — LIVE DEPLOYMENT BLOCKED**. Real Gemini inference and independent remote acceptance remain unverified.

| Check | Executed result |
| --- | --- |
| Initial integrated service/mocked suite | 116 passed in 60.43 seconds before follow-up integration |
| Expanded Gate 1/Gate 2/actions/security suite | 70 passed in 48.55 seconds |
| Expanded agent/provider/security suite | 34 passed in 19.49 seconds; subsequent schema-normalization provider checks 6 passed |
| Seed/data suite after linked measurements and POD reuse adjustment | 25 passed in 11.53 seconds |
| Current full release suite, including live Streamlit page tests | **134 passed in 104.67 seconds**; command/log: `python -m pytest -q --tb=short`, `qa/artifacts/final-test.log` |
| Final data/workflow/page follow-up after transaction/upload-limit/default-provider changes | **30 passed in 26.71 seconds**; `qa/artifacts/final-integration.log` |
| Local model availability acceptance | Initial three attempts returned `ai_not_running` with Ollama. Final three Gemini attempts returned `error` because GEMINI_API_KEY is absent, before HTTP. No real model response obtained |
| HTTPS deployment | Not deployed: GitHub repository creation and Community Cloud setup pending |
| Independent remote interaction and three actual Gemini reports | Not run; blocked by deployment/key |

Mocks exercise real database evidence retrieval and application control flow, but do not establish model quality or hosted inference. HTTP-contract mocks verify Gemini authentication/header/URL/model and structured report requests without network calls.

Windows sandbox Streamlit AppTest initialization hung inside `asyncio` socketpair. A diagnostic stack trace in `qa/artifacts/workflow-test.log` established the environment issue; the full release suite was rerun outside the sandbox with authorization. No failing or interrupted test is reported as passed.

Service acceptance includes current-time denied access, approved batch permissions, exact photo reuse, linked repackaging, missing measurements/GPS/authorization, quantity contradictions, forged citations, adversarial input, bounded timeouts, failed audit rollback, action rejection/expiry/concurrent idempotency, database persistence and isolated recovery-token workspaces. Live UI tests exercise all pages and partner scope. Refer to tests for executable assertions and `docs/DEPLOYMENT.md` for the remaining remote acceptance procedure.
