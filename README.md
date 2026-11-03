# ParcelVerify

An English logistics investigation prototype for monitoring external partners and verifying shipment handoffs. All records and operational responses are synthetic.

## Run locally

Use Python 3.11. Install `requirements.txt`, then run `python start.py`. On this checkout, use `.venv\Scripts\python.exe start.py`. Open `http://localhost:8501`.

Three horizontal destinations cover the review loop: Home, Cases and Partners. Related shipment and access findings share a permission-filtered investigation while retaining original records. Propose a request, obtain a human approval, apply it once, receive linked partner evidence, review the response and record an explicit closure outcome. Missing evidence cannot silently become verified. Workspace > Settings contains named demo roles and recovery tools. Real AI has bounded read-only retrieval and current citation validation; unavailable inference leaves manual operation intact. No mock AI reports appear in the product.

## Configure Groq securely

Copy `.streamlit/secrets.example.toml` privately to `.streamlit/secrets.toml` locally and enter your key:

```toml
AI_PROVIDER = "groq"
GROQ_API_KEY = "REPLACE_PRIVATELY_WITH_YOUR_KEY"
GROQ_MODEL = "openai/gpt-oss-20b"
GROQ_WORKSPACE_HOURLY = 3
GROQ_GLOBAL_DAILY = 60
GROQ_MINUTE_TOKENS = 7500
GROQ_DAILY_TOKENS = 150000
```

Alternatively set matching server environment variables before starting. `.env.example` is a template and is not automatically loaded. Streamlit Secrets override matching environment variables. Local `.env` and `.streamlit/secrets.toml` are ignored by Git. For Streamlit Community Cloud, open **Manage app > Settings > Secrets**, paste this TOML with your private key, save and use **Manage app > Reboot app**. The entry point is `app.py`. Settings > AI connection diagnostics shows provider/model and saved run status without probing the API. Never share or commit the key.

The only inference endpoint is Groq's official OpenAI-compatible API. The default `openai/gpt-oss-20b` is in [supported models](https://console.groq.com/docs/models), supports [strict structured output](https://console.groq.com/docs/structured-outputs) and [tool use](https://console.groq.com/docs/tool-use/overview), checked 18 October 2026. Native function selections are dispatched locally through the read-only whitelist with current permission checks; the final report uses a separate strict schema without tool declarations. No provider-hosted tools run. Weight, SHA-256 and image-hash comparisons remain deterministic and local. The text model reasons over these results and does not visually inspect photos. Alternative `GROQ_MODEL` values must support required formats; failures never silently switch models.

An explicit `AI_PROVIDER` other than `groq` disables inference. Legacy `PV_AI_*`, `GEMINI_API_KEY` and Ollama settings are ignored and cannot reactivate another provider. Missing credentials disable AI buttons while manual review and deterministic checks remain available. Inference begins only with an explicit investigation click. Stable submission IDs deduplicate reruns and queued double-clicks; a deliberate new click after completion or failure gets a new ID. Changed evidence or permissions cannot reuse stale conclusions.

Each investigation permits four selection rounds plus one final report and at most one retry shared between transient failures and a rejected tool selection. If Groq rejects a native tool call, selection falls back to a JSON format, and the final report gets one json_object retry. Each request has 20 seconds and the whole run has 240 seconds, because the free tier (8K tokens/minute) needs one to three minutes for a full run. HTTP 429 stops immediately and leaves manual review available. No paid-provider fallback or key rotation exists. Default guards permit three investigations/workspace/hour and 60 model requests across workspaces/day (`GROQ_GLOBAL_DAILY`), plus shared guards of 7,500 estimated tokens/minute (`GROQ_MINUTE_TOKENS`) and 150,000/day (`GROQ_DAILY_TOKENS`), set just under the free-tier limits. Context is bounded to 20,000 characters. The ledger persists on local host storage rather than session state; losing storage resets counters. These guards do not guarantee provider quotas or control billing; see [rate limits](https://console.groq.com/docs/rate-limits).

The owner must keep the account on Free Plan and avoid a paid upgrade. A key alone does not prove free billing; see the [billing FAQ](https://console.groq.com/docs/billing-faqs). Removing an old Google key from app secrets does not revoke it at Google, cancel Google Cloud debts or stop unrelated resources.

## Verify

```text
python -m pytest -q
python qa/real_ai_acceptance.py --confirm-free-plan
```

The first command uses temporary databases and deterministic provider mocks. Run the second only after privately supplying `GROQ_API_KEY` in the server environment for the intended Free Plan account: it runs one small synthetic investigation, checks actual tool calls and final output, and fails honestly if inference is unavailable. Without the flag and key it makes no model requests. It does not automatically read Streamlit Secrets; on hosting use one explicit **Review evidence with AI** action instead. Live AI and hosted verification remain pending until observed. Mocks never substitute for real AI runs.

For hosted verification, check the deployed branch/commit and `app.py`, enter Secrets, reboot, inspect the Groq/model diagnostic, then perform one synthetic investigation and inspect its completed report and tool trace. Manual review must remain usable with AI disabled. Local tests do not imply a push or deployment.

Each browser receives a separate synthetic dataset. Save the private recovery token to reopen the same workspace after refresh or application restart while disk data survives. Start a new demo creates a new workspace. Data expires after 24 hours of inactivity; Community Cloud storage may disappear on host restart/redeployment. Export reports and audits before leaving. Role selection illustrates permissions and is not production authentication.

**Separation of duties.** The person who proposes a request cannot approve it (they may withdraw it by rejecting it), every approve/reject decision needs a written reason of at least 10 characters, and the AI agent identity (`AGENT-…`) can never approve or apply a request. A self-approved historic request cannot be applied. These rules run on the server, not only in the UI. In the demo one browser can switch roles, so this shows the control, not production identity isolation.

**Main limitations.** Package-count shortfalls are marked "per-item scan status unknown, needs review" because the data has no reliable per-item scan records. Access-pattern detection only checks shipments that have a recorded workload baseline; it is not a general enumeration detector. It has not been shown that ParcelVerify saves review time or reduces false positives. Full list: [limitations](docs/KNOWN_LIMITATIONS.md).

See [deployment](docs/DEPLOYMENT.md), [test report](docs/TEST_REPORT.md), [limitations](docs/KNOWN_LIMITATIONS.md) and the [demo walkthrough](docs/DEMO_SCRIPT.md). A deployment URL and remote real-model acceptance are required before claiming the live prototype complete.

The current [design rebuild handoff](docs/DESIGN_REBUILD_STATE.md) records the GREENWAY reference inspection, actual-screen screenshots, 175-test acceptance and remaining hosted blockers. Home's locally stored decorative image has [documented generated provenance](assets/README.md) and never enters shipment evidence.

The current [AI/UI verification report](docs/AI_UI_FIX_VERIFICATION.md) distinguishes the reproduced Groq failure, protocol correction, mocked checks and remaining live acceptance. The [implementation handoff](docs/IMPLEMENTATION_HANDOFF.md) describes Cases A/B/C, permissions, task responses, migration, exact validation results and prior credential requirements. Run `python qa/evaluate_demo.py` for declared synthetic ground truth; live AI acceptance is a separate check. New demo template v6 (2 November: separation of duties, unverified count shortfalls, baseline-wide access checks) preserves existing visitor workspaces and creates 56 clean background shipments alongside three featured investigations.

The 25 October logistics redesign adds a yellow/charcoal interface, a priority review shortcut, state-specific workflow guidance and an interactive, record-backed 3D handoff explorer. See [redesign notes](docs/LOGISTICS_REDESIGN.md).

The 26 October 3D workspace connects source selection to prefilled verification requests, approval controls, partner response forms and human evidence review. Request/task nodes and source-linked status badges read persisted workflow state. Run `python qa/scene_workflow_browser.py` for the full desktop/mobile interaction check.

The 26 October guided rebuild replaces the multi-form case page with one next step at a time (Check → Ask for proof → Review reply → Finish) and a Three.js city map that reads and drives the workflow: tap a building to inspect or re-check that stop, and watch the van carry the request out and the reply back. See [workflow and 3D rebuild](docs/WORKFLOW_3D_REBUILD.md).
