# ParcelVerify implementation handoff — 14 October 2026

## Requirement-to-code inspection

The existing application already had the green/white horizontal UI, current-time assignment checks, protected photo matching, persisted actions, transactional audit, bounded model transport, reference validation and isolated workspaces. The incomplete parts were event-scoped cases presented separately, no task-linked evidence response/review, administrative closure without a separate outcome, seed evaluation before recorded delivery, and colored demonstration assets. This iteration completes those integrations rather than replacing the stack.

`ParcelVerify Proposal(1).docx` was not found. The supplied Implementation Brief governs this work. An older Full Idea PDF remains unchanged. Existing Gemini support is retained instead of reverting to proposal-era Qwen3/Ollama. The prototype uses Python 3.11, Streamlit, SQLite, Pillow, SHA-256, ImageHash and Pydantic.

## Workflow changes and alignment

| Capability | Status | Evidence / practical limit |
| --- | --- | --- |
| Bounded parent cases with original finding IDs and linkage reasons | Verified | Same-shipment and exact-photo linkage; current permission filtering; repeated detection is idempotent |
| Three primary destinations: Home, Cases, Partners | Verified | Existing green/white UI retained; rendered browser inspection |
| Real read-only AI integration, four tool rounds, structured enums and retrieved references | Verified contract behavior; live blocked | Real Gemini adapter remains; new linked context tool; invented/currently unauthorized citations rejected; AI cannot approve or complete review |
| Fresh provider investigation for A/B/C | Blocked | Real harness ran; all three stopped before transport: `GEMINI_API_KEY is required in server secrets`; zero tool rounds and no reports |
| Named simulated supervisor and partner task workflow | Verified | Investigator proposes; supervisor approves/applies; assigned partner submits; internal reviewer accepts/requests more |
| Approval bound to actual request | Verified | Approval fingerprint checks original action/type/target/reason; revisions create a fresh unapproved request; terminal rejection prevents execution |
| Atomic task response and human review | Verified | Author/time/field checks, original evidence preserved, retry conflict detection, transactional event/photo association/task/audit; injected audit failure rolls back |
| Verified vs unresolved closure; late response and reopening | Verified | Missing measurements cannot become verified from a narrative; cancelled tasks retain reasons; later evidence returns the case to review |
| Gate 1 assigned/unassigned/expired access and restricted fields | Verified | Live retrieval uses current server time; partner responses remain scoped; deterministic workload rule does not widen permission |
| Unusual downloads and approved export exception | Verified on synthetic fixtures | Eight downloads vs recorded workload of three per fifteen minutes; exception checks actor, job, shipment, fields, period and count; unrelated findings remain |
| Exact/near photo evidence and precision/tolerance | Implemented, locally inspected | Identical file reuse A/linked shipment; controlled brightness variant B with distinct bytes; no confidence percentage; display preserves differences and explains tolerance |
| Scoped case and readable audit export | Verified service behavior | Includes original members/findings, runs/model, proposals/decisions, task submissions, unresolved facts and chronological audit; no tamper-proof claim |
| Current deployed revision | Not verified | Existing Streamlit address remains; a repository commit or local test is not hosted acceptance |
| Human review-time improvement / first-time usability | Not implemented measurement | Requires observed, timed sessions; no fabricated improvement percentages |

## Run and configuration

```text
python -m pip install -r requirements.txt
python start.py
python -m pytest -q
python qa/evaluate_demo.py
python qa/real_ai_acceptance.py
```

Windows checkout: `.venv\Scripts\python.exe start.py`. Default local address: `http://localhost:8501`. Existing HTTPS address: `https://parcelverify-fhu5hezcatyb5ko932spwg.streamlit.app/`.

Configure securely through server environment or Streamlit Secrets; never paste secret values into source or chat:

```toml
PV_AI_PROVIDER = "gemini"
PV_AI_MODEL = "gemini-3.5-flash-lite"
GEMINI_API_KEY = "CONFIGURE_SECURELY"
```

The official endpoint is automatic. The model remains configurable; [official model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite) supports function calling and structured output, and [pricing](https://ai.google.dev/gemini-api/docs/pricing) lists free-tier text inference, checked 14 October 2026. Actual project quota/access still requires verification. `.env.example` is documentation, not an automatic environment loader. Real acceptance reads environment variables; the app additionally reads Streamlit Secrets.

## Demonstrate the three cases

Use a new isolated demo to get template v5; old visitor records are preserved. Workspace > Settings > Demo tools switches the server-provided simulated role.

**A — Investigation:** find `PV-DEMO-001`. Its 2.00→1.85 kg discrepancy, exact reused delivery file linked to `PV-SHIP-010`, workload alert and denied request are gathered in one case. View the permitted source pairs and account owners. Mira Patel (investigator) prepares the request. Nora Lee (supervisor) approves with a reason and separately applies it. Sam Tan (QuickRun partner) opens the same case and supplies a new weight/optional photo. Mira reviews the response, then records supported findings. Nora closes with a supported outcome or explicitly unresolved facts. No partner is contacted externally.

**B — Supported explanation:** find `PV-SHIP-011`. Inspect approved repackaging and linked 2.00→1.85 kg measurements, plus the specifically authorized export. Human review cites the actual sources; the exception resolves only its own context. The near-photo variant is illustrative and is not an exact-file match.

**C — Insufficient evidence:** find `PV-SHIP-021`, or use Waiting for evidence. The handover weight remains missing. The local task names the gap; an assigned partner can provide a measurement and explanation. An accepted narrative alone cannot produce verified closure while required fields remain unknown. A real configured AI check should return More evidence needed; this live outcome is not yet verified.

For live AI, use Explain this case/issue with AI after configuring the provider. The model retrieves permitted evidence using bounded tools, returns an advisory conclusion, and cannot approve/execute/resolve. Supporting buttons open permitted evidence. New linked evidence marks older results out of date. Failed inference leaves manual operation intact.

## Validation and evaluation

The recorded full regression passed 181 tests in 244.15 seconds before final approval-binding/closure refinements. Follow-ups passed 46 approval-binding tests, 13 case/UI tests, 34 closure/security tests and 26 final measurement/security tests. Logs include `approval-binding-final.log`, `implementation-final-focused.log`, `closure-final-tests.log` and `measurement-final-tests.log`. These are local deterministic/mock provider tests, not successful Gemini inference.

Actual Chrome inspection passed 21 rendered screen/viewport combinations at 1440×900, 1024×768 and 390×844, plus keyboard/44px checks, photo enlargement, mobile navigation, root scroll restoration and first Home action above the fold. Screenshots are in `qa/artifacts/design-rebuild/`; late screenshot refreshes preserve this scope. No user-comprehension study was performed.

`qa/evaluate_demo.py` reports 60 synthetic shipments, 3 featured cases, 56 clean background shipments, zero missed required fixture categories, no missed labeled flagged shipments and no false-alert shipments against the declared synthetic ground truth. Required fields are complete for 59/60 shipments. Presence is not verified quality; this tiny rules-only sample does not establish real-world effectiveness. AI-assisted evaluation and timed human comparison remain pending. A useful human protocol is: randomize A/B/C, ask a new reviewer to state the concern, locate evidence, predict a button's effect and complete the next step; record actual elapsed time, errors and hesitation for manual vs AI-assisted sessions.

## Migration and limitations

Additive `CREATE TABLE IF NOT EXISTS` migrations add case membership/findings/reviews, explicit closure decisions and task submissions. Original case/event/action/audit records are not dropped. Existing approved requests without the new exact-request fingerprint require a fresh recorded approval; they cannot silently execute as if bound. Existing workspaces keep their historical demo data; use explicit Start a new demo for new fixtures. User databases are never reset for QA.

Generated parcel assets are local and synthetic. The generator documents exact reuse and a controlled near variant; they do not prove contents or visual condition. Recovery tokens restore a visitor workspace only while host storage survives. Data expires after 24-hour inactivity; Streamlit host rebuilds can remove ephemeral storage. Simulated identities are not production authentication. Internal investigators remain trusted staff, and citation existence/permission validation does not replace human semantic review of an AI claim.

Two GPT-6.1 Sol agents left reusable partial changes before quota limits stopped them; main finished sequentially. No Astra, extra deployment, external messages or paid infrastructure was used. Real credentials and the existing hosting account are the remaining external dependencies.
