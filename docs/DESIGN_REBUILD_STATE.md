# Design and usability rebuild — 14 October 2026

Authoritative brief: `reference/ParcelVerify_Design_and_Usability_Rebuild.md`. Main inspected `reference/GREENWAY.png` and confirmed the headline, truck photography, horizontal navigation, numbered steps, white canvas and green feature region. The prior UI source is recoverable from `dist/ParcelVerify-before-design-rebuild-20261013.zip`; prior GitHub commit is `f2cf20f959b1fcdbd9aa5e6f0d0cf6ca24427293`.

## Composition checklist and implemented change

- Replace the radio sidebar with native horizontal Home / Issues / Partners controls and a secondary Workspace menu; a labelled Menu popover serves mobile users.
- Give Home a large editorial headline and intentional locally stored logistics photography, followed by a compact status strip, aligned operational rows and a numbered green process region.
- Use white surfaces, #075E49 actions, #142B24 text, #52645C secondary text and restrained dividers. Lists have aligned columns and row dividers rather than oversized outlined cards. System font fallbacks preserve readability without font downloads.
- Present meaningful issue titles, actual short comparisons and distinct action labels. The weight page exposes measurements, stage/time/source, signed difference and actual labeled demo thumbnails before further disclosure. Data-access detail shows account, requested shipment, assignment and denied result.
- Put request controls beside evidence on desktop and after the evidence on mobile. Explain approval, intended partner, unassigned reviewer/contact, local task creation and absence of external messaging. Reuse persisted proposal, approval, rejection, execution and audited closure services.

## Working interactions

Home starts review in one click. Issues search opens permitted shipment records even without an issue. Filters, page and Back context persist; a small developer-authored local scroll hook saves queue scroll on opening an issue and restores it on Back. Native Streamlit buttons perform every action. Evidence and request drafts survive errors and navigation; Cancel preserves the request draft without submission. Supervisors may record an idempotent supplementary-information task while leaving a proposal pending. Approval, applying the step and closing an issue remain distinct.

The main AI action is secondary, never automatic on rerender. Missing inference displays “AI explanation is unavailable. You can still review the evidence.” Existing real-provider integration and report provenance remain. No actual AI provider was called in this rebuild acceptance.

The demo time audit found future generated events from one-shipment-per-day spacing. New templates use coherent two-per-day spacing and v3; existing visitor databases remain unchanged. Existing future records receive an honest profile notice. Multiple issues per shipment are retained and partners disclose issue and affected-shipment denominators. See `docs/DESIGN_DATA_AUDIT.md`.

## Validation and delivery

Final full regression: **175 passed in 104.47 seconds**, artifact `qa/artifacts/design-final-tests.log`. Targeted UI tests cover no-issue lookup, data-access closure and matching shortcuts, request cancellation, supplementary-information tasks, evidence drafts, partner scope and request → approval → application → manual closure. The timeline/rule/security audit independently passed 50 focused checks.

Actual Chrome screens at 1440×900, 1024×768 and 390×844 are stored under `qa/artifacts/design-rebuild/`: Home, Issues, weight detail, data-access detail, Partners, partner profile and photo enlargement. All 21 screen/viewport combinations passed runtime-error and horizontal-overflow checks. At 1440×900 the first actionable issue is visible without scrolling; at 390px work actions precede the decorative photograph. `home-process-1440.png` captures the numbered region and `reference-comparison.png` places the actual Home beside GREENWAY. Keyboard focus and 44px targets were inspected. These are technical checks, not a claim of observed first-time comprehension or full accessibility certification.

Core changed files: `app.py`, `ui/design_ui.py`, `ui/workspace_ui.py`, `ui/presentation.py`, `ui/theme.css`, `.streamlit/config.toml`, `assets/logistics-hero.png`, `seed.py`, `workspace.py`, targeted tests, QA and documentation. Product assets remain local and are included in source packaging.

Local launch remains `python start.py`. Existing public address: `https://parcelverify-fhu5hezcatyb5ko932spwg.streamlit.app/`; use the same GitHub repository / main / app.py deployment. This rebuild does not establish current deployed UI or real Gemini acceptance. Earlier hosted Gemini attempts failed without reports; current key/model/project access, deployment synchronization and remote photo delivery remain unresolved. Demo identities are not production authentication, operations do not contact carriers and host storage can be ephemeral. No second deployment or paid service was created.
