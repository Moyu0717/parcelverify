# Streamlit deployment — Groq-only free demo

Existing repository: Moyu0717/parcelverify, main, app.py (confirmed by owner logs). Do not reset visitor databases or change app visibility. Migration case-workflow-v2-groq is additive; the dataset remains linked-cases-v5.

In the existing application open **Manage app → Settings → Secrets** and save this configuration privately:

```toml
AI_PROVIDER = "groq"
GROQ_API_KEY = "REPLACE_PRIVATELY_WITH_YOUR_KEY"
GROQ_MODEL = "openai/gpt-oss-20b"
GROQ_WORKSPACE_HOURLY = 3
GROQ_GLOBAL_DAILY = 30
```

Use **Manage app → Reboot app** after changing credentials or if loaded-function diagnostics show a genuine mismatch. Check Settings for release groq-free-20261015.1, checkout identity, matching loaded functions, provider groq and model. Configured credentials are not proof of a successful live investigation.

Locally copy .streamlit/secrets.example.toml to .streamlit/secrets.toml, enter the key in that private file and run .venv\Scripts\python.exe -m streamlit run app.py. Matching environment variables are supported; Streamlit Secrets take precedence. .env is not automatically loaded. Local secrets are ignored by Git.

Keep the intended account on Groq Free Plan; a key does not establish billing status. Only the official Groq endpoint is called. Gemini/PV_AI variables cannot activate a provider. Removing an old Google key from Secrets does not revoke it at Google or cancel debts/resources.

Use a separate current synthetic workspace. Confirm Cases A/B/C, photographs and manual workflows, then run **one** explicit AI investigation if the key is privately configured for the intended Free Plan account. Inspect actual saved tools and validated citations. Failed, partial or usage-limited runs are not conclusions. No automatic page-load/navigation calls or bulk live tests occur.

Optional local smoke: python qa/real_ai_acceptance.py --confirm-free-plan. It requires GROQ_API_KEY in the environment, runs one synthetic scenario, and refuses to call without flag/key. It does not read Streamlit Secrets automatically.

Usage guards persist on local host storage and are shared across its visitor workspaces. They may reset on storage loss and do not combine across multiple independent hosts. Default guards and exact request/token/time bounds are in README.md; they are not provider-wide quota or billing controls.

Official references checked 15 October 2026: [models](https://console.groq.com/docs/models), [structured output](https://console.groq.com/docs/structured-outputs), [rate limits](https://console.groq.com/docs/rate-limits), [billing FAQ](https://console.groq.com/docs/billing-faqs), [Streamlit Secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management).
