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
GROQ_GLOBAL_DAILY = 30
```

Alternatively set matching server environment variables before starting. `.env.example` is a template and is not automatically loaded. Streamlit Secrets override matching environment variables. Local `.env` and `.streamlit/secrets.toml` are ignored by Git. For Streamlit Community Cloud, open **Manage app > Settings > Secrets**, paste this TOML with your private key, save and use **Manage app > Reboot app**. The entry point is `app.py`. Settings > AI connection diagnostics shows provider/model and saved run status without probing the API. Never share or commit the key.

The only inference endpoint is Groq's official OpenAI-compatible API. The default `openai/gpt-oss-20b` is in [supported models](https://console.groq.com/docs/models), supports [strict structured output](https://console.groq.com/docs/structured-outputs) and [tool use](https://console.groq.com/docs/tool-use/overview), checked 15 October 2026. Native function selections are dispatched locally through the read-only whitelist with current permission checks; the final report uses a separate strict schema without tool declarations. No provider-hosted tools run. Weight, SHA-256 and image-hash comparisons remain deterministic and local. The text model reasons over these results and does not visually inspect photos. Alternative `GROQ_MODEL` values must support required formats; failures never silently switch models.

An explicit `AI_PROVIDER` other than `groq` disables inference. Legacy `PV_AI_*`, `GEMINI_API_KEY` and Ollama settings are ignored and cannot reactivate another provider. Missing credentials disable AI buttons while manual review and deterministic checks remain available. Inference begins only with an explicit investigation click. Stable submission IDs deduplicate reruns and queued double-clicks; a deliberate new click after completion or failure gets a new ID. Changed evidence or permissions cannot reuse stale conclusions.

Each investigation permits four selection rounds plus one final report and at most one transient retry: six requests maximum, 512 output tokens per selection and 1,024 for the final report, 20 seconds per request and 120 seconds overall. HTTP 429 stops immediately and leaves manual review available. No paid-provider fallback or key rotation exists. Default guards permit three investigations/workspace/hour and 30 model requests across workspaces/day, plus conservative shared guards of 10 requests/minute, 6,000 estimated tokens/minute and 60,000/day. Context is bounded to 20,000 characters. The ledger persists on local host storage rather than session state; losing storage resets counters. These guards do not guarantee provider quotas or control billing; see [rate limits](https://console.groq.com/docs/rate-limits).

The owner must keep the account on Free Plan and avoid a paid upgrade. A key alone does not prove free billing; see the [billing FAQ](https://console.groq.com/docs/billing-faqs). Removing an old Google key from app secrets does not revoke it at Google, cancel Google Cloud debts or stop unrelated resources.

## Verify

```text
python -m pytest -q
python qa/real_ai_acceptance.py --confirm-free-plan
```

The first command uses temporary databases and deterministic provider mocks. Run the second only after privately supplying `GROQ_API_KEY` in the server environment for the intended Free Plan account: it runs one small synthetic investigation, checks actual tool calls and final output, and fails honestly if inference is unavailable. Without the flag and key it makes no model requests. It does not automatically read Streamlit Secrets; on hosting use one explicit **Review evidence with AI** action instead. Live AI and hosted verification remain pending until observed. Mocks never substitute for real AI runs.

For hosted verification, check the deployed branch/commit and `app.py`, enter Secrets, reboot, inspect the Groq/model diagnostic, then perform one synthetic investigation and inspect its completed report and tool trace. Manual review must remain usable with AI disabled. Local tests do not imply a push or deployment.

Each browser receives a separate synthetic dataset. Save the private recovery token to reopen the same workspace after refresh or application restart while disk data survives. Start a new demo creates a new workspace. Data expires after 24 hours of inactivity; Community Cloud storage may disappear on host restart/redeployment. Export reports and audits before leaving. Role selection illustrates permissions and is not production authentication.

See [deployment](docs/DEPLOYMENT.md), [test report](docs/TEST_REPORT.md), [limitations](docs/KNOWN_LIMITATIONS.md) and the [five-minute demo](docs/DEMO_SCRIPT.md). A deployment URL and remote real-model acceptance are required before claiming the live prototype complete.

The current [design rebuild handoff](docs/DESIGN_REBUILD_STATE.md) records the GREENWAY reference inspection, actual-screen screenshots, 175-test acceptance and remaining hosted blockers. Home's locally stored decorative image has [documented generated provenance](assets/README.md) and never enters shipment evidence.

The current [AI/UI verification report](docs/AI_UI_FIX_VERIFICATION.md) distinguishes the reproduced Groq failure, protocol correction, mocked checks and remaining live acceptance. The [implementation handoff](docs/IMPLEMENTATION_HANDOFF.md) describes Cases A/B/C, permissions, task responses, migration, exact validation results and prior credential requirements. Run `python qa/evaluate_demo.py` for declared synthetic ground truth; live AI acceptance is a separate check. New demo template v5 preserves existing visitor workspaces and creates 56 clean background shipments alongside three featured investigations.
