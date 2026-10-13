# Verified handoff state — 13 October 2026

Project: `F:\celin\User\Study\Year 3\Hackathon\ParcelVerify`; PowerShell; Python 3.11.9 in `.venv`. No Git repository was present. Launch: `.venv\Scripts\python.exe start.py`; portable launch: `python start.py`.

The previous implementation already contained seed fixtures, rules, actions and a partly functional investigation loop. Progress documents were stale and UI pages were fixture skeletons. The existing code and twelve permitted images were retained. Two bounded GPT-6.1 Sol subagents repaired services and investigation modules; main owns shared schema/data changes, runtime, live UI, workflow, tests and release packaging.

Working evidence: full release suite passed 134 tests in 104.67 seconds, including all live Streamlit pages and partner scope. New UI uses real services and saves events, cases, investigation traces, reports, approvals and audits. Main case fixture preserves 45-point discrepancy/reuse rules; repackaging has linked measurements. Live requests use server-time authorization; duplicate event/upload paths also check access before returning existing records.

Investigation: configurable Gemini Developer API, Ollama or OpenAI-compatible HTTP adapter. Selected route is Gemini with server-side `GEMINI_API_KEY`, configurable `PV_AI_MODEL`; default `gemini-3.5-flash-lite`. Credentials unavailable in this session. Actual local model acceptance attempts returned `ai_not_running`; no successful real inference was claimed. Report versions and tool traces refer to persisted run IDs. No canned fallback.

Hosting: selected Streamlit Community Cloud. GitHub integration is connected as Moyu0717. User created the public repository `https://github.com/Moyu0717/parcelverify`; repository metadata and starter README were verified. Source publication follows local checks. Sites Workers cannot directly host this retained Python service. No live URL or independent remote interaction has been verified. User has a Community Cloud account; Gemini key will be configured securely there.

Isolation: each visitor receives a private token and separate SQLite/upload directory. Token recovery supports refresh/application restart while disk data survives. Retention is 24 hours of inactivity; Community Cloud host rebuilds can remove local files. Roles and operations are explicitly simulated.

Next: complete missing user setup: create/upload GitHub source repository; select `app.py` in Community Cloud; configure Gemini Secrets securely; deploy; run three actual model cases and independent-session remote acceptance. Record actual URL and run IDs before claiming online completion. Exact local acceptance command: `python qa/real_ai_acceptance.py` with server environment configured. All tests use temporary data; never reset the user's existing database.
