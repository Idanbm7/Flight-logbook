"""
app.py — Entry point. Auto-creates a single default pilot user, loads settings
from SQLite user_preferences, and routes to pages.
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
</style>
""", unsafe_allow_html=True)

# ── Database bootstrap ────────────────────────────────────────────────────────
from database import (
    init_db, authenticate_user, register_user,
    get_connection, get_home_display_prefs,
)

init_db()

# Migrate: add log_type column to flight_logs if the schema predates it
try:
    with get_connection() as _conn:
        _conn.execute("ALTER TABLE flight_logs ADD COLUMN log_type TEXT DEFAULT 'IP'")
except Exception:
    pass  # column already exists — safe to ignore

# Auto-create / auto-login a single default pilot user (no login screen)
_DEFAULT_USER = "pilot"
_DEFAULT_PASS  = "logbook2025"

if "user" not in st.session_state:
    user = authenticate_user(_DEFAULT_USER, _DEFAULT_PASS)
    if not user:
        register_user(_DEFAULT_USER, _DEFAULT_PASS)
        user = authenticate_user(_DEFAULT_USER, _DEFAULT_PASS)
    st.session_state.user = user

# ── Load persisted settings from SQLite on first run ─────────────────────────
# Settings are stored in user_preferences with keys:
#   sheet_url, primary_role, display_name, default_aircraft_id
if "settings_loaded" not in st.session_state:
    _prefs = get_home_display_prefs(st.session_state.user["id"])
    for _k in ("sheet_url", "primary_role", "display_name", "default_aircraft_id"):
        if _k in _prefs:
            st.session_state[_k] = _prefs[_k]
    st.session_state.settings_loaded = True

if "page" not in st.session_state:
    st.session_state.page = "home"

# ── Page router ───────────────────────────────────────────────────────────────

_PAGE_MAP = {
    "home":       "pages.home",
    "new_flight": "pages.new_flight",
    "my_flights": "pages.flight_history",
    "settings":   "pages.settings",
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
