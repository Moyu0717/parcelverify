# Verified handoff state — 13 October 2026

Superseded for current UI work by `docs/DESIGN_REBUILD_STATE.md` on 14 October 2026. Navigation is now Home / Issues / Partners with a horizontal header, evidence-first details and 175 passing regression tests. The historical state below records the earlier iteration.

Current priority: implement `reference/ParcelVerify_UI_Refactor.md`, verify local interactions and screenshots, then resume real Gemini and HTTPS acceptance. Never infer real inference from mocked tests.

Python 3.11.9 / Streamlit 1.65.0 / SQLite are retained. Run `python start.py`, or `.venv\Scripts\python.exe start.py` on this Windows checkout. No local Git repository exists; source is published through connected GitHub at `Moyu0717/parcelverify`, preserving the user's `.devcontainer` files.

The UI now uses Overview, Cases and Partners. Cases combine Summary, Evidence, manual next steps, explicit approval/rejection, separate application, collapsed Activity and readable exports. Settings contains Demo tools and administrative diagnostics. Evidence is persisted, authorization remains server-side, photos are actual labeled demo images, and AI unavailability does not prevent manual review. Review counts use one current authorized cohort. Closing records a manual disposition, never evidence verification.

Existing rule thresholds, protected case states, transactional action/audit writes, evidence tasks, linked packaging measurements, configurable real-provider adapter and isolated visitor workspaces remain. Proposal retries accept a stable request ID with conflict detection. Denied real access records are materialized as access-review cases; they do not establish intent. Partner reports use permitted shipments; internal reporting details stay restricted.

Checkpoint before refactor: `dist/ParcelVerify-pre-ui-refactor-20261013.zip`. Source packaging excludes credentials, user databases, recovery tokens, uploads and QA artifacts. Every visitor has a private SQLite/upload workspace, with recovery while storage survives and 24-hour inactivity retention. Community Cloud rebuilds may remove local data. Demo roles and operations are simulated, not production authentication or carrier APIs.

Local browser QA checks Overview, Cases, Summary, Evidence and Partners at 1440, 1024 and 390 pixels, including photo enlargement, keyboard focus, 44-pixel controls and horizontal overflow. Screenshots and results are in `qa/artifacts/ui-refactor/`. Local service/UI tests and final suite status are recorded in `docs/TEST_REPORT.md`.

Public URL: `https://parcelverify-fhu5hezcatyb5ko932spwg.streamlit.app/`. Previous six-page deployment loaded independently with HTTPS 200; the user confirmed its Overview rendered. Two actual hosted main-case Gemini attempts failed without reports. Root cause, secure key/model/project access, current source synchronization and remote photo fix remain unverified. These checks were explicitly paused during the UI work and must not be marked accepted. Next resume task: confirm this revision is serving, inspect sanitized saved-run diagnostics as administrator, and complete three actual model cases and independent browser acceptance using the revised navigation.

Latest pre-refactor commit: `8d2faa47c046c75de2ea486fb401e70929fad8fb`. The old `qa/remote_browser.py` targets historical six-page navigation and must be adapted before final hosted acceptance. The local UI browser script never calls an AI provider.
