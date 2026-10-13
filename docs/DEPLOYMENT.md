# Streamlit Community Cloud deployment

Selected route: existing Python/Streamlit application plus Google Gemini Developer API. No laptop tunnel, static imitation or database migration is needed. Deployment requires your GitHub repository, Community Cloud authorization and server-side Gemini key. No account credentials belong in this repository.

## 1. Create the repository

1. Sign in to [GitHub](https://github.com) and choose **New repository**.
2. Name it `parcelverify`. Use a private repository if available to your Community Cloud workspace; a public repository contains synthetic source only. Do not add a second starter README.
3. Download and extract the provided `ParcelVerify-source.zip`.
4. On the repository page, choose **uploading an existing file**. Drag the extracted files and folders into the upload area, preserving paths. Commit as `Initial ParcelVerify prototype`.
5. Verify `app.py`, `requirements.txt`, `schema.sql`, twelve `fixtures/*.jpg` images, `services/`, `agent/`, `ui/`, and `.streamlit/config.toml` exist in the repository root.

The package deliberately excludes `.venv`, `.env`, live databases, uploads, recovery tokens, secrets, temporary reports and agent memory. Do not upload the entire original workspace unfiltered. The GitHub integration can assist once connected, but repository creation and Community Cloud sign-in still require your account authorization.

## 2. Deploy

1. Sign in to [Streamlit Community Cloud](https://share.streamlit.io) and authorize the GitHub account owning the repository.
2. Choose **Create app**, then select your repository and branch (`main`). Set the entrypoint to `app.py`.
3. In **Advanced settings**, select Python 3.11 where offered and add these Secrets:

```toml
PV_AI_PROVIDER = "gemini"
PV_AI_MODEL = "gemini-3.5-flash-lite"
GEMINI_API_KEY = "PASTE_YOUR_KEY_HERE_IN_STREAMLIT_ONLY"
```

4. Deploy and keep the returned `https://...streamlit.app` URL. Ensure reviewers have access to the app's selected audience.
5. In Google AI Studio, confirm this project has free-tier access to the selected model and inspect its actual quotas. Do not enable billing solely to complete this demo. A `429` is an incomplete investigation, never permission to switch to a paid model.

Instructions are based on [official deployment](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) and [Secrets management](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management), checked 13 October 2026. Models and quotas remain account-specific.

## 3. Remote acceptance

1. Open the HTTPS URL in an independent browser/incognito session. Save that workspace's recovery token privately.
2. Confirm partner overview contains three partners and 60 total synthetic shipments.
3. Investigate `PV-DEMO-001`: model must select actual read-only tools, save a report and reference retrieved evidence. Review the 2,000 g to 1,850 g discrepancy, `SEAL-07`, and reused POD file. Expected rule score: 45. No responsibility claim is acceptable.
4. Investigate `PV-SHIP-011`: linked reweigh records must explain the weight change. Keep unrelated findings and unknown evidence visible.
5. Submit incomplete evidence on another shipment, then investigate it. Missing measurements remain unknown. The workspace allows three real attempts per hour, including failures.
6. Propose a verification action, approve it, execute once and export the audit. Reject a separate action and confirm it cannot execute.
7. Refresh and resume using the token; the same saved evidence and reports must remain while disk data survives.
8. Open a second browser session. Its approvals and submissions must not affect the first workspace.
9. Record URL, UTC test time, provider/model, three run/report IDs, reviewer context and pass/fail results in `docs/TEST_REPORT.md`. Deployment success alone does not prove inference or interaction.

## Storage and service limits

SQLite databases and uploads live under `PV_DATA_DIR` or `data/workspaces`. Workspaces expire after 24 hours of inactivity and are pruned when a new demo starts. Recovery tokens are private bearer credentials for synthetic data only; they never appear in shared URLs. Community Cloud does not provide a persistence guarantee for these local files. For retention across host rebuilds, use the supplied Docker image on one authorized Python host with a persistent `/data` volume and HTTPS termination; this route is prepared, not deployed or tested.

Real inference is serialized per application process and limited to three attempts per workspace per hour. Each investigation has four selected tool rounds and a 120-second total budget. Photos accept JPEG/PNG only, up to 10 MB and 20 megapixels. Free-tier quotas may interrupt investigations; evidence and rule pages remain usable.
