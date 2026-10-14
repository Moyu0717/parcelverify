# Groq-only migration — 15 October 2026

Provider: Groq official OpenAI-compatible endpoint, default model openai/gpt-oss-20b (configurable with GROQ_MODEL). Official model, tool-use and strict structured-output support were checked on 15 October. No Gemini, Vertex AI, OpenAI or custom paid endpoint fallback exists. Legacy provider environment values cannot reactivate calls. Direct HTTPX has no hidden retry multiplication or provider-hosted tools.

The existing safe local tool selection phase and separate schema-validated conclusion remain. Compact case overviews explicitly omit detailed timelines/logs; only identifiers actually sent to the model can be cited. Original evidence and audit records remain. A text model cannot visually inspect photos or assign intent. Independent detection/linkage and human approval logic were not changed.

Limits: four tool rounds, five normal model requests plus at most one transient retry; 512 selection / 1024 final output tokens, 20-second response deadline, 120-second investigation deadline. HTTP 429 stops with no retry or fallback. The process gate stays held until a timed-out network worker drains. Persistent actor/request/snapshot binding deduplicates in-flight and completed submissions. New evidence/permissions require a new submission; deliberate new clicks receive new widget generations.

Default public guard: three investigations/workspace/hour; shared 30 model requests/rolling day, ten/minute, 6000 conservative estimated tokens/minute, 60000/day. The ledger is on host disk, shared across this host's workspaces. Session changes do not reset it; loss of storage does. Multiple independent hosts have independent ledgers. These guards do not guarantee provider quotas or billing.

Changed files: agent/runner.py, configuration.py, usage.py; additive schema.sql; app.py, release_info.py, UI helpers; requirements/lock (unused Ollama removed); README, deployment guide, examples, one-scenario smoke harness and focused tests. Records and manual workflows were preserved.

Actual local checks: 71 selected migration/security/case/version tests passed, then 18 focused deadline/configuration/guard tests passed after the final timeout refinement. These overlap and are not 89 distinct tests. Chrome passed 24 desktop/tablet/phone checks with Groq credentials absent. No live Groq calls were made locally; GROQ_API_KEY and private local secrets are absent. Mocked tests do not verify real AI. The smoke harness refuses to call without key and explicit Free Plan confirmation.

Local setup: privately copy .streamlit/secrets.example.toml to .streamlit/secrets.toml, replace GROQ_API_KEY there, run .venv\Scripts\python.exe -m streamlit run app.py. Environment variables are supported; .env is not automatically loaded. Streamlit Secrets override environment. Hosted setup: Manage app → Settings → Secrets, save the same configuration, then Reboot app. Exact template and limits are documented in README.md.

Keep the account on Free Plan; the application cannot verify billing status. Removing old Google secrets does not revoke their keys, cancel existing debts or stop unrelated resources. No cloud account/billing settings were changed.

Publication and actual public diagnostics must be checked independently. Real AI acceptance remains pending until one small synthetic investigation retrieves authorized tools and persists a validated conclusion.
