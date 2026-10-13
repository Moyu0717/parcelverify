"""ParcelVerify: an isolated synthetic logistics investigation demo."""
import os
import streamlit as st
from workspace import open_workspace, prune_expired_workspaces
from services.workflow import initialize_reviews
from ui.live import PAGES

st.set_page_config(page_title="ParcelVerify", page_icon="📦", layout="wide")

def main():
    os.environ.setdefault("PV_AI_PROVIDER", "gemini")
    for name in ("PV_AI_PROVIDER", "PV_AI_BASE_URL", "PV_AI_MODEL", "PV_AI_API_KEY", "GEMINI_API_KEY", "OLLAMA_HOST"):
        try:
            if name in st.secrets:
                os.environ[name] = str(st.secrets[name])
        except FileNotFoundError:
            pass
    if "db_path" not in st.session_state:
        with st.spinner("Preparing your isolated demo workspace..."):
            prune_expired_workspaces()
            token, path = open_workspace()
            st.session_state.workspace_token, st.session_state.db_path = token, path
            initialize_reviews(path, {"actor_id": "ADMIN-001", "role": "admin", "session_id": token})
    from pathlib import Path
    Path(st.session_state.db_path).parent.joinpath(".activity").touch()
    st.sidebar.title("📦 ParcelVerify")
    st.sidebar.caption("Evidence before decisions")
    st.sidebar.info("Synthetic data · isolated demo workspace")
    role = st.sidebar.selectbox("Simulated role", ["admin", "investigator", "approver", "partner_user"])
    partner = None
    actor_id = f"{role.upper()}-001"
    if role == "partner_user":
        partner = st.sidebar.selectbox("Partner", ["P-QUICKRUN", "P-SAFELOG", "P-METROLINE"])
        actor_id = {"P-QUICKRUN": "ACTOR-QR-01", "P-SAFELOG": "ACTOR-SL-01", "P-METROLINE": "ACTOR-ML-01"}[partner]
    st.session_state.actor_context = {"actor_id": actor_id, "partner_id": partner, "role": role,
        "session_id": st.session_state.workspace_token, "is_simulated": True}
    page = st.sidebar.radio("Workspace", list(PAGES))
    with st.sidebar.expander("Save or resume your demo"):
        st.caption("Keep your recovery token private. Data expires after 24 hours of inactivity or host storage loss.")
        st.download_button("Save recovery token", st.session_state.workspace_token, file_name="parcelverify-recovery.txt")
        recovery = st.text_input("Recovery token", type="password")
        if st.button("Resume workspace"):
            try:
                token, path = open_workspace(recovery)
                st.session_state.workspace_token, st.session_state.db_path = token, path
                st.rerun()
            except ValueError as error:
                st.error(str(error))
        if st.button("Start a new isolated demo"):
            del st.session_state.db_path
            st.rerun()
    st.title(page)
    st.caption("A discrepancy is a request for verification, not proof of fraud or responsibility. Roles and operational changes are simulated.")
    try:
        PAGES[page]()
    except Exception as error:
        st.error(f"Operation failed: {error}")

if __name__ == "__main__":
    main()

