"""ParcelVerify: a focused English review workspace for synthetic logistics evidence."""
import os
from pathlib import Path

import streamlit as st
from services.review import ensure_access_cases
from services.cases import ensure_case_links
from workspace import open_workspace, prune_expired_workspaces
from ui.presentation import apply_theme
from ui.workspace_ui import route, search, notice
from ui.design_ui import PAGES, header

st.set_page_config(page_title="ParcelVerify",page_icon=":material/inventory_2:",layout="wide")

def navigate():
    st.session_state.secondary_view=None

def secondary(name):
    st.session_state.secondary_view=name

def request_search():
    st.session_state.search_requested=True

def remember_role():
    st.session_state.actor_role=st.session_state.role_widget

def remember_partner():
    st.session_state.actor_partner=st.session_state.partner_identity_widget

def new_workspace():
    for key in ("db_path","workspace_token","selected_case_id","selected_shipment_id","proposal_ids","case_search","drafts","cancelled_requests","selected_partner_id"):
        st.session_state.pop(key,None)
    route("Home")

def settings():
    st.title("Settings")
    st.caption("Workspace preferences and demonstration tools.")
    import importlib
    import release_info
    import runtime_identity
    # These readers have no mutable workflow state. Refresh diagnostics only;
    # never reload permissions, database services or an active AI semaphore.
    importlib.reload(release_info)
    importlib.reload(runtime_identity)
    from release_info import build_information, dataset_version, DATASET_VERSION, ai_configuration
    active_dataset = dataset_version(st.session_state.db_path)
    with st.expander("Build information"):
        st.caption("Release and commit identify the source checkout. Loaded-function verification below checks the active process separately.")
        for label, value in build_information().items(): st.write(f"{label}: {value}")
        stale=runtime_identity.loaded_source_status()
        if stale:
            st.warning("Loaded Python modules differ from the checked-out source. The owner must use Manage app → Reboot app before this build can be verified.")
            st.caption("Modules requiring refresh: "+', '.join(stale))
        else: st.caption("Loaded Python functions match the checked-out source.")
        st.write(f"Active demo dataset: {active_dataset}")
        st.caption("Schema migration: case-workflow-v3-ai-state. Dataset versions describe seeded records, not schema migrations.")
    if active_dataset != DATASET_VERSION:
        st.warning("This workspace retains older or unversioned demo records. Save its recovery token before opening a separate current demo. Your existing records will remain available within the retention period.")
    with st.expander("Demo tools"):
        st.caption("Simulated identities illustrate permissions. They are not production authentication.")
        roles={"admin":"Administrator","investigator":"Investigator","approver":"Supervisor","partner_user":"Partner"}
        role=st.selectbox("Demo role",list(roles),index=list(roles).index(st.session_state.actor_role),format_func=lambda value:roles[value],key="role_widget",on_change=remember_role)
        if role=="partner_user":
            names={"P-QUICKRUN":"QuickRun Logistics","P-SAFELOG":"SafeLog Express","P-METROLINE":"MetroLine Courier"}
            st.selectbox("Partner identity",list(names),index=list(names).index(st.session_state.get("actor_partner","P-QUICKRUN")),format_func=lambda value:names[value],key="partner_identity_widget",on_change=remember_partner)
        st.divider()
        st.caption("Save your private recovery token to resume this demo while its data survives. Data expires after 24 hours of inactivity or host storage loss.")
        st.download_button("Save recovery token",st.session_state.workspace_token,file_name="parcelverify-recovery.txt")
        recovery=st.text_input("Recovery token",type="password")
        if st.button("Resume workspace"):
            try:
                token,path=open_workspace(recovery)
                st.session_state.workspace_token,st.session_state.db_path=token,path
                route("Home"); st.rerun()
            except ValueError as error: st.error(str(error))
        st.caption("Start a new demo opens a separate current dataset. It does not delete this workspace. Save its recovery token first to return to these records.")
        st.button("Start a new demo",on_click=new_workspace)
        with st.form("test-access"):
            shipment=st.text_input("Shipment to check",value="PV-DEMO-001")
            check=st.form_submit_button("Check shipment access")
        if check:
            from services.access import query_shipment
            result=query_shipment(st.session_state.db_path,st.session_state.actor_context,shipment)
            if result["authorized"]: st.success("Access allowed. The request was recorded.")
            else: st.warning("Access denied. No shipment details were returned. The request was recorded.")
    if st.session_state.actor_context["role"]=="admin":
        from ui.live import rows
        with st.expander("Administrative logs"):
            st.dataframe(rows("SELECT actor_id,shipment_id,occurred_at,outcome FROM access_logs ORDER BY occurred_at DESC LIMIT 100"),hide_index=True,use_container_width=True)
        with st.expander("AI connection diagnostics"):
            from services.ai_state import case_ai_state,derive_ai_state
            from agent.configuration import provider_settings
            config=provider_settings()
            st.write('Provider: '+config['provider']+' · Model: '+config['model'])
            st.caption(('Credential present; not proof of a working connection.' if config['configured'] else 'Credential missing.')+' Execution policy: '+('enabled' if config['enabled'] else 'disabled')+'.')
            latest=rows('SELECT case_id FROM investigation_runs ORDER BY started_at DESC,rowid DESC LIMIT 1')
            selected=st.session_state.get('selected_case_id') or (latest[0]['case_id'] if latest else None)
            state=case_ai_state(st.session_state.db_path,selected,st.session_state.actor_context) if selected else derive_ai_state(config)
            st.info(state['message'])
            if selected:st.caption('Review status for the selected or most recent case; it does not describe every case.')
            st.write('Last provider outcome: '+state['provider_outcome'])
            if state.get('run'):
                st.json({key:state['run'].get(key) for key in ('run_id','status','model_name','error','started_at','finished_at')})
                st.json(state['diagnostics'])
            if st.session_state.get("technical_error"): st.code(st.session_state.technical_error)

def help_page():
    st.title("Help")
    st.subheader("A simple review loop")
    st.write("1. Open a case from Home, or find a shipment by its reference in Cases.")
    st.write("2. Check the concern and its evidence. Missing information is not a mismatch.")
    st.write("3. Submit the next step for approval, or record an authorized review decision.")
    st.info("Groq explanations are optional. Review the evidence and use the human approval workflow when AI is unavailable.")
    st.caption("Operational actions and identities are simulated. Demonstration images are not verified parcel photographs. Flags need review; they do not prove wrongdoing.")

def main():
    apply_theme()
    from agent.configuration import load_server_configuration
    try:
        load_server_configuration(st.secrets)
    except FileNotFoundError:
        load_server_configuration({})
    if "db_path" not in st.session_state:
        with st.spinner("Preparing your isolated demo workspace..."):
            prune_expired_workspaces()
            token,path=open_workspace()
            st.session_state.workspace_token,st.session_state.db_path=token,path
    Path(st.session_state.db_path).parent.joinpath(".activity").touch()
    if st.session_state.get('schema_revision')!='case-workflow-v3-ai-state':
        from db import init_db
        init_db(st.session_state.db_path)
        st.session_state.schema_revision='case-workflow-v3-ai-state'
    role=st.session_state.setdefault("actor_role","admin")
    partner=st.session_state.setdefault("actor_partner","P-QUICKRUN") if role=="partner_user" else None
    actor_id={"P-QUICKRUN":"ACTOR-QR-01","P-SAFELOG":"ACTOR-SL-01","P-METROLINE":"ACTOR-ML-01"}.get(partner,f"{role.upper()}-001")
    st.session_state.actor_context={"actor_id":actor_id,"partner_id":partner,"role":role,"session_id":st.session_state.workspace_token,"is_simulated":True}
    if role in ("admin","investigator"):
        ensure_access_cases(st.session_state.db_path,st.session_state.actor_context)
        ensure_case_links(st.session_state.db_path,st.session_state.actor_context)
    if st.session_state.pop("search_requested",False): search(st.session_state.get("workspace_search",""))
    pending=st.session_state.pop("route_pending",None)
    if pending: st.session_state.primary_destination=pending
    if st.session_state.get("primary_destination") not in PAGES:
        st.session_state.primary_destination="Home"
    header()
    message=st.session_state.pop("notice",None)
    if message: getattr(st,message[0])(message[1])
    try:
        view=st.session_state.get("secondary_view")
        if view=="Settings": settings()
        elif view=="Help": help_page()
        else: PAGES[st.session_state.primary_destination]()
    except Exception as error:
        from agent.runner import _safe_error
        st.session_state.technical_error=_safe_error(error)
        st.error("This operation could not be completed. Review the case activity before trying again.")

if __name__=="__main__": main()
