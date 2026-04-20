"""
app.py — Streamlit entry point. Google Sheets setup gate and top-level router.
Run with:  streamlit run app.py
"""

import streamlit as st

st.set_page_config(
    page_title="Flight Logbook",
    page_icon="🚁",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
html, body, .stApp { font-size: 16px; }
.stButton > button {
    min-height: 3rem;
    font-size: 1rem;
    border-radius: 8px;
    width: 100%;
}
input, textarea, select { font-size: 1rem !important; }
#MainMenu { visibility: hidden; }
footer     { visibility: hidden; }
header     { visibility: hidden; }
[data-testid="metric-container"] {
    background: rgba(0, 16, 40, 0.75);
    border: 1px solid rgba(0, 212, 255, 0.2);
    border-radius: 6px;
    padding: 10px 14px;
}
[data-testid="metric-container"] label {
    color: #00d4ff !important;
    font-size: 0.7rem !important;
    letter-spacing: 1.5px;
    text-transform: uppercase;
}
[data-testid="stMetricValue"] {
    color: #ffffff !important;
    font-family: 'Courier New', monospace;
    font-size: 1.4rem !important;
}
</style>
""", unsafe_allow_html=True)

# Auto-install streamlit-local-storage
try:
    from streamlit_local_storage import LocalStorage
except ImportError:
    import subprocess, sys
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "streamlit-local-storage"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    from streamlit_local_storage import LocalStorage

localS = LocalStorage()

# Read from localStorage and cache to session_state (getItem returns None on first render)
_url_ls  = localS.getItem("sheet_url")
_role_ls = localS.getItem("primary_role")

if _url_ls:
    st.session_state["sheet_url"] = _url_ls
if _role_ls:
    st.session_state["primary_role"] = _role_ls

if "page" not in st.session_state:
    st.session_state.page = "home"

sheet_url = st.session_state.get("sheet_url", "")


# ── Setup gate ───────────────────────────────────────────────────────────────

def show_setup():
    st.title("FLIGHT LOGBOOK")
    st.subheader("Initial Setup")

    with st.container(border=True):
        st.markdown("### Connect to Google Sheets")
        st.info(
            "Your flight data is saved to a Google Sheet. "
            "Provide the sheet URL and your primary role to begin."
        )

        with st.expander("How to set up credentials (click to expand)"):
            st.markdown("""
1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create a project.
2. Enable the **Google Sheets API** for that project.
3. Create a **Service Account**, then download its JSON key.
4. Rename the file to `credentials.json` and place it next to `app.py`.
5. Open your Google Sheet, click **Share**, and grant **Editor** access to the service account email (found in `credentials.json`).
6. Paste the full Google Sheet URL below.
""")

        url = st.text_input(
            "Google Sheet URL",
            placeholder="https://docs.google.com/spreadsheets/d/…/edit",
            key="setup_url",
        )
        role = st.selectbox(
            "Primary Role",
            ["IP", "EP", "Dual"],
            key="setup_role",
            help=(
                "IP = Instructor Pilot — manual start/end times.\n"
                "EP = Evaluated Pilot — duration from events (qty × 15 min).\n"
                "Dual = choose mode per flight."
            ),
        )

        if st.button("Save & Open Logbook", use_container_width=True, type="primary"):
            if not url.strip() or "docs.google.com" not in url:
                st.error("Please enter a valid Google Sheets URL.")
            else:
                localS.setItem("sheet_url", url.strip())
                localS.setItem("primary_role", role)
                st.session_state["sheet_url"] = url.strip()
                st.session_state["primary_role"] = role
                st.success("Settings saved — loading your logbook…")
                st.rerun()


if not sheet_url:
    show_setup()
    st.stop()


# ── Page router ──────────────────────────────────────────────────────────────

_PAGE_MAP = {
    "home":           "pages.home",
    "new_flight":     "pages.new_flight",
    "flight_history": "pages.flight_history",
    "settings":       "pages.settings",
}


def _safe_render(module_path: str) -> None:
    try:
        import importlib
        mod = importlib.import_module(module_path)
        mod.render()
    except Exception as exc:
        st.error("An unexpected error occurred on this page.")
        import traceback
        print(f"[RENDER ERROR] {module_path}: {exc}")
        traceback.print_exc()


_safe_render(_PAGE_MAP.get(st.session_state.page, "pages.home"))
