# ParcelVerify

An English logistics investigation prototype for monitoring external partners and verifying shipment handoffs. All records and operational responses are synthetic.

## Run locally

Use Python 3.11. Install `requirements.txt`, then run `python start.py`. On this checkout, use `.venv\Scripts\python.exe start.py`. Open `http://localhost:8501`.

Pages cover partner metrics, shipment source evidence and images, access monitoring, handoff comparison and submission, real model investigation, human approval, simulated execution and JSON exports. No mock AI reports appear in the product.

## Configure Gemini securely

Put the following in `.streamlit/secrets.toml` locally or the Streamlit Community Cloud Secrets editor:

```toml
PV_AI_PROVIDER = "gemini"
PV_AI_MODEL = "gemini-3.5-flash-lite"
GEMINI_API_KEY = "YOUR_KEY_IN_THE_SECRETS_EDITOR_ONLY"
```

The key remains server-side. The official Gemini endpoint is selected automatically. The model is configurable; verify model access and quotas in your own Google AI Studio project. Gemini 3.5 Flash-Lite currently supports function calling and structured output and lists free-tier text inference in the [official model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite) and [pricing](https://ai.google.dev/gemini-api/docs/pricing), checked 13 October 2026. No paid infrastructure is provisioned.

Ollama and other OpenAI-compatible providers remain supported through `PV_AI_PROVIDER`, `PV_AI_MODEL`, `PV_AI_BASE_URL` and `PV_AI_API_KEY`. `.env.example` documents variables but is not loaded automatically.

## Verify

```text
python -m pytest -q
python qa/real_ai_acceptance.py
```

The first command uses temporary databases and deterministic provider mocks. The second makes actual model requests using environment variables and fails honestly if inference is unavailable. It exercises the main exception, supported repackaging and insufficient evidence. It does not automatically read Streamlit Secrets; use the application's investigation page for secret-configured hosting.

Each browser receives a separate synthetic dataset. Save the private recovery token to reopen the same workspace after refresh or application restart while disk data survives. Start a new demo creates a new workspace. Data expires after 24 hours of inactivity; Community Cloud storage may disappear on host restart/redeployment. Export reports and audits before leaving. Role selection illustrates permissions and is not production authentication.

See [deployment](docs/DEPLOYMENT.md), [test report](docs/TEST_REPORT.md), [limitations](docs/KNOWN_LIMITATIONS.md) and the [five-minute demo](docs/DEMO_SCRIPT.md). A deployment URL and remote real-model acceptance are required before claiming the live prototype complete.
