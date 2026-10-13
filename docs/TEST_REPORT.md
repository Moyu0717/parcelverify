# Test report — 13 October 2026

Current priority: **UI REFACTOR REQUESTED — GEMINI/REMOTE INVESTIGATION PAUSED**. Core app locally verified; complete remote acceptance has not passed.

| Check | Executed result |
| --- | --- |
| Initial integrated service/mocked suite | 116 passed in 60.43 seconds before follow-up integration |
| Expanded Gate 1/Gate 2/actions/security suite | 70 passed in 48.55 seconds |
| Expanded agent/provider/security suite | 34 passed in 19.49 seconds; subsequent schema-normalization provider checks 6 passed |
| Seed/data suite after linked measurements and POD reuse adjustment | 25 passed in 11.53 seconds |
| Final full release suite, including live Streamlit page tests and final response-state/task repairs | **156 passed in 91.81 seconds**; command/log: `python -m pytest -q --tb=short`, `qa/artifacts/release-final.log` |
| Final data/workflow/page follow-up after transaction/upload-limit/default-provider changes | **30 passed in 26.71 seconds**; `qa/artifacts/final-integration.log` |
| Internal report scope page regression | 5 workflow/page tests passed in 6.66 seconds |
| Portable launch and actual HTTP service | Passed: `python qa/smoke_server.py` started `start.py`, received HTTP 200 / `ok` from Streamlit health, then stopped its own process tree |
| Local model availability acceptance | Initial three attempts returned `ai_not_running` with Ollama. Final three Gemini attempts returned `error` because GEMINI_API_KEY is absent, before HTTP. No real model response obtained |
| GitHub source publication | Public `Moyu0717/parcelverify` main verified; initial 71-file release 8801763, final repairs follow in the release commit |
| HTTPS deployment | Public URL returns HTTP 200: https://parcelverify-fhu5hezcatyb5ko932spwg.streamlit.app/ |
| Independent remote pages | All six pages loaded in an independent Chrome context after resolving Community Cloud's embedded application route |
| Remote actual investigation | Two independent main-case attempts returned `error` and no completed report. Cause not yet confirmed; failed diagnostics require current deployment or secure configuration verification |
| Three completed Gemini reports | Not passed; investigation paused at user's request |
| Remote photos | Hosted media route produced 404 errors; inline evidence-byte rendering committed in 8d2faa4, remote fix verification pending |
| Latest deployment synchronization | Remote browser still observed earlier UI without trace export; Reboot/source verification pending, investigation paused |

Mocks exercise real database evidence retrieval and application control flow, but do not establish model quality or hosted inference. HTTP-contract mocks verify Gemini authentication/header/URL/model and structured report requests without network calls.

Historical baseline: following startup-template optimization, five workflow/page/isolation tests passed in 11.24 seconds. Following inline-photo and trace-export changes, five workflow/page tests passed in 9.59 seconds. The pre-refactor full suite was 156 passed in 91.81 seconds. Current UI acceptance is recorded below.

Windows sandbox Streamlit AppTest initialization hung inside `asyncio` socketpair. A diagnostic stack trace in `qa/artifacts/workflow-test.log` established the environment issue; the full release suite was rerun outside the sandbox with authorization. No failing or interrupted test is reported as passed.

Service acceptance includes current-time denied access, approved batch permissions, exact photo reuse, linked repackaging, missing measurements/GPS/authorization, quantity contradictions, forged citations, adversarial input, bounded timeouts, failed audit rollback, action rejection/expiry/concurrent idempotency, database persistence and isolated recovery-token workspaces. Live UI tests exercise all pages and partner scope. Refer to tests for executable assertions and `docs/DEPLOYMENT.md` for the remaining remote acceptance procedure.

## UI refactor acceptance — 13 October 2026

Final full regression: **171 passed in 108.51 seconds**. Artifact: `qa/artifacts/ui-refactor-final-tests.log`. Targeted service acceptance passed 44 tests. Current AppTest flows verify the three primary destinations, persistent partner role and authorized case scope, access filtering, honest absent AI, request → approve → apply → manual close, unchecked confirmation rejection, validation with retained drafts, Back with draft recovery, and kg-to-g persistence. No actual AI provider was called during UI acceptance.

The initial full run found a real disabled-submit defect caused by confirmation inside a Streamlit form. It was repaired by checking confirmation at submission; the final full run passed after the repair. Request and evidence text fields now save private session drafts independently of navigation.

Actual Chrome inspection passed 15 screen/viewport combinations: Overview, Cases, Summary, Evidence and Partners at 1440, 1024 and 390 pixels. No whole-page horizontal overflow or operational runtime error occurred. Real inline demonstration photos enlarged at every width. Keyboard Tab reached a live input; inspected partner buttons measured 44px high. Computed caption color #53645F on #F6F8F7 yields 5.87:1 contrast; the primary green/white palette yields 7.35:1. Screenshots and `results.json` are under `qa/artifacts/ui-refactor/`. These checks do not constitute complete accessibility certification or first-time user testing.

Real Gemini and revised HTTPS deployment remain **not accepted**. Earlier model attempts failed without reports. Source synchronization, server Secrets/model availability and remote media delivery require resumed hosted acceptance. `qa/remote_browser.py` still describes historical navigation; adapt it before the next online test. No user data was reset during this refactor.
