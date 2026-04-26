"""
pages/home.py — Hero image with title overlay, single-row 3-button nav,
and colorful summary metric cards.
"""

import os
import base64
import streamlit as st

from database import get_user_stats, get_recent_flights, get_home_display_prefs
from utils import minutes_to_hhmm, format_date_eu

_ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BG_IMAGE = os.path.join(_ROOT, "Heron1.jpg")

# Card colour palettes  (border, background, text)
_BLUE   = ("#1565c0", "#e3f2fd", "#0d47a1")
_GREEN  = ("#2e7d32", "#e8f5e9", "#1b5e20")
_ORANGE = ("#e65100", "#fff3e0", "#bf360c")
_PURPLE = ("#6a1b9a", "#f3e5f5", "#4a148c")


def _img_to_base64(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""


def _card(label: str, value: str, palette: tuple) -> str:
    border, bg, text = palette
    return (
        f'<div style="background:{bg};border-left:4px solid {border};border-radius:8px;'
        f'padding:10px 14px;text-align:center;margin:4px 0;">'
        f'<div style="font-size:0.65rem;color:{text};font-weight:700;letter-spacing:1.2px;'
        f'text-transform:uppercase;">{label}</div>'
        f'<div style="font-size:1.45rem;font-weight:700;color:{text};'
        f'font-family:\'Courier New\',monospace;">{value}</div>'
        f'</div>'
    )


def _row(cards: list[tuple]) -> None:
    """Render a row of (label, value, palette) card tuples side-by-side."""
    cols = st.columns(len(cards))
    for col, (label, value, palette) in zip(cols, cards):
        col.markdown(_card(label, value, palette), unsafe_allow_html=True)


def render():
    # ── Hero image with title overlay ─────────────────────────────────────────
    img_b64 = _img_to_base64(_BG_IMAGE)
    if img_b64:
        st.markdown(
            f"""
            <div style="position:relative;text-align:center;color:white;">
                <img src="data:image/jpeg;base64,{img_b64}"
                     style="width:100%;filter:brightness(120%);border-radius:10px;">
                <h1 style="position:absolute;top:50%;left:50%;
                           transform:translate(-50%,-50%);
                           text-shadow:2px 2px 4px #000000;width:100%;">
                    FLIGHT LOGBOOK
                </h1>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.title("FLIGHT LOGBOOK")

    st.write("")  # Spacer

    # ── Single-row 3-button navigation ────────────────────────────────────────
    st.markdown(
        """<style>
        div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(3)) {
            flex-wrap: nowrap !important;
            gap: 0.4rem !important;
        }
        div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(3))
            > div[data-testid="column"] {
            min-width: 0 !important;
            flex: 1 1 0% !important;
        }
        </style>""",
        unsafe_allow_html=True,
    )
    nav_col1, nav_col2, nav_col3 = st.columns(3, gap="small")
    with nav_col1:
        if st.button("NEW FLIGHT", use_container_width=True):
            st.session_state.page = "new_flight"
            st.rerun()
    with nav_col2:
        if st.button("MY FLIGHTS", use_container_width=True):
            st.session_state.page = "my_flights"
            st.rerun()
    with nav_col3:
        if st.button("SETTINGS", use_container_width=True):
            st.session_state.page = "settings"
            st.rerun()

    # ── Summary stats ─────────────────────────────────────────────────────────
    st.divider()

    display_name = st.session_state.get("display_name", "")
    st.subheader(f"Summary — {display_name}" if display_name else "Summary")

    user_id = st.session_state.user["id"]
    stats   = get_user_stats(user_id) or {}
    total   = int(stats.get("total_flights") or 0)

    if total == 0:
        st.info("No flights logged yet. Tap **NEW FLIGHT** to get started.")
        return

    # Load display preferences (all default to shown if not set)
    prefs = get_home_display_prefs(user_id)

    def _shown(key: str) -> bool:
        return prefs.get(key, "1") == "1"

    # Compute consolidated event counts
    day_events   = (int(stats.get("total_day_takeoffs")   or 0)
                  + int(stats.get("total_day_landings")   or 0))
    night_events = (int(stats.get("total_night_takeoffs") or 0)
                  + int(stats.get("total_night_landings") or 0))

    # Build card rows conditionally
    row1 = []
    if _shown("show_total_flights"):
        row1.append(("Total Flights", str(total), _BLUE))
    if _shown("show_total_hours"):
        row1.append(("Total Hours", minutes_to_hhmm(int(stats.get("total_minutes") or 0)), _BLUE))
    if _shown("show_last_flight"):
        row1.append(("Last Flight", format_date_eu(stats.get("last_flight_date") or "—"), _BLUE))
    if row1:
        _row(row1)

    row2 = []
    if _shown("show_pic_hours"):
        row2.append(("PIC Hours", minutes_to_hhmm(int(stats.get("pic_minutes") or 0)), _GREEN))
    if _shown("show_sic_hours"):
        row2.append(("SIC Hours", minutes_to_hhmm(int(stats.get("sic_minutes") or 0)), _GREEN))
    if _shown("show_instructor_hrs"):
        row2.append(("Instructor Hrs", minutes_to_hhmm(int(stats.get("instructor_minutes") or 0)), _GREEN))
    if row2:
        st.write("")
        _row(row2)

    row3 = []
    if _shown("show_day_events"):
        row3.append(("Day Events", str(day_events), _ORANGE))
    if _shown("show_night_events"):
        row3.append(("Night Events", str(night_events), _ORANGE))
    if _shown("show_approaches"):
        row3.append(("Approaches", str(int(stats.get("total_approaches") or 0)), _ORANGE))
    if row3:
        st.write("")
        _row(row3)

    # Recent flights
    recent = get_recent_flights(user_id, limit=3)
    if recent:
        st.write("")
        st.markdown("**Recent Flights**")
        for log in recent:
            log_type = "EP" if log.get("start_time") == "00:00" else "IP"
            st.caption(
                f"{format_date_eu(log['date'])}  ·  [{log_type}]  ·  "
                f"{log['model_type']}  ·  {log['location_name']}  ·  "
                f"{minutes_to_hhmm(log['duration_minutes'])} hrs"
            )
