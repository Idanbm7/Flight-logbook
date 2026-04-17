"""
app.py — Streamlit entry point. Login/register and top-level navigation.
Run with:  venv/Scripts/streamlit run app.py
"""

import streamlit as st
from database import init_db, register_user, authenticate_user

# ---------------------------------------------------------------------------
# Page config  (must be the very first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Flight Logbook",
    page_icon="🚁",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Global CSS — aviation dark theme, mobile-friendly touch targets
# NOTE: avoid [class*="css"] — that selector is deprecated in Streamlit 1.35+
#       and produces silent internal warnings that Streamlit surfaces as UI noise.
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* Base font */
    html, body, .stApp { font-size: 16px; }

    /* Touch-friendly buttons */
    .stButton > button {
        min-height: 3rem;
        font-size: 1rem;
        border-radius: 8px;
        width: 100%;
    }

    /* Larger form inputs */
    input, textarea, select { font-size: 1rem !important; }

    /* Hide Streamlit chrome */
    #MainMenu  { visibility: hidden; }
    footer     { visibility: hidden; }
    header     { visibility: hidden; }

    /* Stack columns vertically on narrow screens */
    @media (max-width: 640px) {
        [data-testid="column"] {
            min-width: 100% !important;
            flex: 1 1 100% !important;
        }
    }

    /* Tighten metric cards */
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

# ---------------------------------------------------------------------------
# Bootstrap DB (creates data/ dir if needed)
# ---------------------------------------------------------------------------
try:
    init_db()
except Exception as _db_err:
    st.error(f"Database initialisation failed: {_db_err}")
    st.stop()

# ---------------------------------------------------------------------------
# Session defaults
# ---------------------------------------------------------------------------
if "user" not in st.session_state:
    st.session_state.user = None
if "page" not in st.session_state:
    st.session_state.page = "home"
if "show_register" not in st.session_state:
    st.session_state.show_register = False


# ---------------------------------------------------------------------------
# Login / Register
# ---------------------------------------------------------------------------

def show_login():
    st.title("🚁 Flight Logbook")
    st.subheader("Sign In")

    with st.form("login_form"):
        username  = st.text_input("Username")
        password  = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In", use_container_width=True)

    if submitted:
        user = authenticate_user(username, password)
        if user:
            st.session_state.user = user
            st.session_state.page = "home"
            st.session_state.show_register = False
            st.rerun()
        else:
            st.error("Invalid username or password.")

    if not st.session_state.show_register:
        if st.button("New user? Sign Up", use_container_width=False):
            st.session_state.show_register = True
            st.rerun()
    else:
        st.divider()
        st.subheader("Create an Account")

        with st.form("register_form"):
            new_user  = st.text_input("Choose a username")
            new_pass  = st.text_input("Choose a password", type="password")
            new_pass2 = st.text_input("Confirm password",  type="password")
            reg_ok    = st.form_submit_button("Create Account", use_container_width=True)

        if reg_ok:
            if new_pass != new_pass2:
                st.error("Passwords do not match.")
            else:
                ok, msg = register_user(new_user, new_pass)
                if ok:
                    st.success(msg + " You can now sign in.")
                    st.session_state.show_register = False
                    st.rerun()
                else:
                    st.error(msg)

        if st.button("← Back to Sign In", use_container_width=True):
            st.session_state.show_register = False
            st.rerun()


# ---------------------------------------------------------------------------
# Navigation bar
# ---------------------------------------------------------------------------

def show_nav():
    user = st.session_state.user
    top_l, top_r = st.columns([3, 1])
    top_l.markdown(f"**Logged in as:** {user['username']}")
    if top_r.button("Sign Out"):
        st.session_state.user = None
        st.session_state.page = "home"
        st.rerun()

    st.divider()

    pages = [
        ("home",           "🏠 Home"),
        ("new_flight",     "➕ New Flight"),
        ("flight_history", "📋 My Flights"),
        ("settings",       "⚙️ Settings"),
    ]
    cols = st.columns(len(pages))
    for col, (key, label) in zip(cols, pages):
        if col.button(label, use_container_width=True):
            st.session_state.page = key
            st.rerun()

    st.divider()


# ---------------------------------------------------------------------------
# Router — each render() wrapped so unhandled exceptions never reach the UI
# ---------------------------------------------------------------------------

_PAGE_MAP = {
    "home":           "pages.home",
    "new_flight":     "pages.new_flight",
    "flight_history": "pages.flight_history",
    "settings":       "pages.settings",
}


def _safe_render(module_path: str) -> None:
    """Import module and call render(), catching all exceptions cleanly."""
    try:
        import importlib
        mod = importlib.import_module(module_path)
        mod.render()
    except Exception as exc:
        st.error(
            "An unexpected error occurred on this page. "
            "Please try refreshing or navigating away and back."
        )
        # Print to server console only — never expose tracebacks in the UI
        import traceback
        print(f"[RENDER ERROR] {module_path}: {exc}")
        traceback.print_exc()


def main():
    if st.session_state.user is None:
        show_login()
        return

    show_nav()

    page   = st.session_state.page
    module = _PAGE_MAP.get(page, "pages.home")
    _safe_render(module)


if __name__ == "__main__":
    main()
