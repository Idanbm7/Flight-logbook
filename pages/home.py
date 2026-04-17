"""
pages/home.py — Home screen.
Features: permanent Heron-1.jpg background, semi-transparent overlay, HUD-style stats panel.
All data access is wrapped in try/except so no exception ever surfaces to the UI.
"""

import os
import base64
import html as _html
from datetime import date

import streamlit as st

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BG_IMAGE = os.path.join(_ROOT, "Heron1.jpg")


# ---------------------------------------------------------------------------
# Image helper
# ---------------------------------------------------------------------------

def _load_b64(path: str) -> tuple[str, str]:
    """Return (base64_string, mime_type) or ('', '') on any failure."""
    try:
        ext  = os.path.splitext(path)[1].lower()
        mime = "image/png" if ext == ".png" else "image/jpeg"
        with open(path, "rb") as fh:
            return base64.b64encode(fh.read()).decode(), mime
    except Exception:
        return "", ""


# ---------------------------------------------------------------------------
# HUD card builder
# ---------------------------------------------------------------------------

def _hud_card(label: str, value: str, accent: str = "#00d4ff") -> str:
    """Return HTML for a single HUD-style stat card."""
    return (
        f'<div style="'
        f'background:rgba(2,12,30,0.82);'
        f'border:1px solid {accent}28;'
        f'border-top:2px solid {accent};'
        f'border-radius:5px;'
        f'padding:13px 8px 11px;'
        f'text-align:center;'
        f'">'
        f'<div style="'
        f'color:{accent};font-size:0.6rem;letter-spacing:2.5px;'
        f'text-transform:uppercase;font-family:Courier New,monospace;'
        f'">{_html.escape(str(label))}</div>'
        f'<div style="'
        f'color:#ffffff;font-size:1.5rem;font-weight:700;'
        f'font-family:Courier New,monospace;margin-top:5px;line-height:1.1;'
        f'">{_html.escape(str(value))}</div>'
        f'</div>'
    )


def _hud_grid(cards_html: str) -> str:
    return (
        '<div style="'
        'display:grid;'
        'grid-template-columns:repeat(auto-fit,minmax(130px,1fr));'
        'gap:10px;margin:0.6rem 0 0.3rem;'
        f'">{cards_html}</div>'
    )


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------

def render():
    # ---- safe imports ----
    try:
        from database import get_user_stats, get_recent_flights, get_home_display_prefs
        from utils import minutes_to_hhmm
    except Exception as exc:
        st.error(f"Module load error: {exc}")
        return

    user = st.session_state.get("user") or {}
    if not user:
        return

    username = user.get("username", "Pilot")
    today    = date.today().strftime("%A, %B %d, %Y")

    # ================================================================== #
    # 1 ▸  HERO BANNER  (permanent Heron-1.jpg background)                #
    # ================================================================== #
    b64, mime = _load_b64(_BG_IMAGE)
    if b64:
        bg_css = (
            f"background-image:"
            f"linear-gradient(rgba(3,10,24,0.74),rgba(3,10,24,0.80)),"
            f"url('data:{mime};base64,{b64}');"
            f"background-size:cover;background-position:center;"
        )
    else:
        bg_css = (
            "background:linear-gradient("
            "135deg,#060d1b 0%,#0d2035 45%,#0a2a40 100%);"
        )

    safe_user = _html.escape(username.upper())
    safe_date = _html.escape(today)

    st.markdown(
        f"""
        <div style="
            {bg_css}
            border-radius:12px;
            padding:2.8rem 2rem 2.2rem;
            text-align:center;
            margin-bottom:1.2rem;
            box-shadow:0 6px 28px rgba(0,0,0,0.55);
            border:1px solid rgba(0,212,255,0.14);
        ">
            <h1 style="
                color:#ffffff;margin:0.5rem 0 0.15rem;
                font-size:1.9rem;letter-spacing:5px;
                text-transform:uppercase;
                font-family:'Courier New',monospace;
                text-shadow:0 0 22px rgba(0,212,255,0.55);
            ">FLIGHT LOGBOOK</h1>
            <div style="
                color:#00d4ff;font-size:0.95rem;margin:0.15rem 0 0.35rem;
                font-family:'Courier New',monospace;letter-spacing:2px;
            ">── WELCOME, {safe_user} ──</div>
            <p style="
                color:#6a9fbf;margin:0;font-size:0.8rem;
                font-family:'Courier New',monospace;
            ">{safe_date}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ================================================================== #
    # 2 ▸  STATS                                                          #
    # ================================================================== #
    try:
        stats = get_user_stats(user["id"]) or {}
    except Exception:
        stats = {}

    total_flights = int(stats.get("total_flights") or 0)

    if total_flights == 0:
        st.markdown(
            """
            <div style="
                background:rgba(2,12,30,0.75);
                border:1px solid rgba(0,212,255,0.25);
                border-radius:8px;padding:1.5rem;text-align:center;margin:1rem 0;
            ">
                <p style="color:#8abbd0;font-family:'Courier New',monospace;
                           margin:0;letter-spacing:1px;">
                    LOGBOOK EMPTY &nbsp;—&nbsp; LOG YOUR FIRST FLIGHT TO BEGIN
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("➕  Log Your First Flight", use_container_width=True):
            st.session_state.page = "new_flight"
            st.rerun()
        return

    def _hhmm(key: str) -> str:
        try:
            return minutes_to_hhmm(int(stats.get(key) or 0))
        except Exception:
            return "0:00"

    def _num(key: str) -> str:
        try:
            return str(int(stats.get(key) or 0))
        except Exception:
            return "0"

    last_flight = _html.escape(str(stats.get("last_flight_date") or "—"))

    # Load display preferences (default: all shown)
    try:
        prefs = get_home_display_prefs(user["id"])
    except Exception:
        prefs = {}

    def _show(key: str) -> bool:
        return prefs.get(key, "1") == "1"

    # Row 1 — primary hours
    row1_cards = []
    if _show("show_total_flights"):
        row1_cards.append(_hud_card("TOTAL FLIGHTS", _num("total_flights")))
    if _show("show_total_hours"):
        row1_cards.append(_hud_card("TOTAL HOURS",   _hhmm("total_minutes")))
    if _show("show_pic_hours"):
        row1_cards.append(_hud_card("PIC HOURS",     _hhmm("pic_minutes")))
    if _show("show_last_flight"):
        row1_cards.append(_hud_card("LAST FLIGHT",   last_flight))

    # Row 2 — secondary stats
    # Day T/O & Landings  = total_day_takeoffs  + total_day_landings
    # Night T/O & Landings= total_night_takeoffs+ total_night_landings
    day_tol   = (int(stats.get("total_day_takeoffs")   or 0)
               + int(stats.get("total_day_landings")    or 0))
    night_tol = (int(stats.get("total_night_takeoffs")  or 0)
               + int(stats.get("total_night_landings")  or 0))

    row2_cards = []
    if _show("show_sic_hours"):
        row2_cards.append(_hud_card("SIC HOURS",           _hhmm("sic_minutes"),        "#00e5a0"))
    if _show("show_instructor_hrs"):
        row2_cards.append(_hud_card("INSTRUCTOR HRS",      _hhmm("instructor_minutes"), "#00e5a0"))
    if _show("show_day_events"):
        row2_cards.append(_hud_card("DAY T/O & LANDINGS",   str(day_tol),   "#ffc857"))
    if _show("show_night_events"):
        row2_cards.append(_hud_card("NIGHT T/O & LANDINGS", str(night_tol), "#ffc857"))

    if row1_cards:
        st.markdown(_hud_grid("".join(row1_cards)), unsafe_allow_html=True)
    if row2_cards:
        st.markdown(_hud_grid("".join(row2_cards)), unsafe_allow_html=True)

    st.markdown(
        "<hr style='border:none;border-top:1px solid rgba(0,212,255,0.18);"
        "margin:1.2rem 0 0.8rem;'>",
        unsafe_allow_html=True,
    )

    # ================================================================== #
    # 3 ▸  RECENT FLIGHTS                                                 #
    # ================================================================== #
    try:
        recent = get_recent_flights(user["id"], limit=5) or []
    except Exception:
        recent = []

    if recent:
        st.markdown(
            "<div style='color:#00d4ff;font-size:0.68rem;letter-spacing:3px;"
            "text-transform:uppercase;font-family:Courier New,monospace;"
            "margin-bottom:0.55rem;'>▸ RECENT ACTIVITY</div>",
            unsafe_allow_html=True,
        )

        rows_html = ""
        for i, log in enumerate(recent):
            bg_row = "rgba(0,20,50,0.55)" if i % 2 == 0 else "rgba(0,10,30,0.35)"
            instr  = " 🎓" if log.get("is_instructor") else ""
            try:
                dur = minutes_to_hhmm(int(log.get("duration_minutes") or 0))
            except Exception:
                dur = "—"
            rows_html += (
                f'<div style="background:{bg_row};border-left:3px solid #00d4ff33;'
                f'padding:8px 12px;margin-bottom:4px;border-radius:0 5px 5px 0;'
                f'font-family:Courier New,monospace;font-size:0.82rem;">'
                f'<span style="color:#ffc857;">'
                f'{_html.escape(str(log.get("date","")))}   </span>'
                f'&nbsp;│&nbsp;'
                f'<span style="color:#ffffff;">'
                f'{_html.escape(str(log.get("model_type","")))} '
                f'{_html.escape(str(log.get("tail_number","")))}   </span>'
                f'&nbsp;│&nbsp;'
                f'<span style="color:#9fc8e0;">'
                f'{_html.escape(str(log.get("location_name","")))}   </span>'
                f'&nbsp;│&nbsp;'
                f'<span style="color:#00e5a0;">'
                f'{_html.escape(str(log.get("crew_role","")))}   {instr}</span>'
                f'&nbsp;│&nbsp;'
                f'<span style="color:#00d4ff;">⏱ {_html.escape(dur)}</span>'
                f'</div>'
            )

        st.markdown(rows_html, unsafe_allow_html=True)

        st.markdown(
            "<hr style='border:none;border-top:1px solid rgba(0,212,255,0.18);"
            "margin:1rem 0 0.8rem;'>",
            unsafe_allow_html=True,
        )

    # ================================================================== #
    # 4 ▸  QUICK ACTIONS                                                  #
    # ================================================================== #
    qa1, qa2 = st.columns(2)
    if qa1.button("➕  New Flight",     use_container_width=True):
        st.session_state.page = "new_flight"
        st.rerun()
    if qa2.button("📋  Flight History", use_container_width=True):
        st.session_state.page = "flight_history"
        st.rerun()
