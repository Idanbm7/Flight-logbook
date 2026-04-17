"""
pages/home.py — Home screen.
Layout: Heron-1 image as header background → 2×2 quick-action buttons → stats → recent activity.
"""

import base64
import html as _html
import os
from datetime import date
from io import BytesIO

import streamlit as st

_ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BG_IMAGE = os.path.join(_ROOT, "Heron1.jpg")


def _load_brightened(path: str, factor: float = 1.5):
    try:
        from PIL import Image, ImageEnhance
    except ImportError:
        import subprocess, sys
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "Pillow"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        from PIL import Image, ImageEnhance
    try:
        return ImageEnhance.Brightness(Image.open(path)).enhance(factor)
    except Exception:
        return None


def _header_with_bg(img, safe_user: str, safe_date: str) -> str:
    """Return HTML for a full-width banner: Heron image as background, title overlaid."""
    if img:
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=82)
        b64 = base64.b64encode(buf.getvalue()).decode()
        bg = (
            f"background-image:url('data:image/jpeg;base64,{b64}');"
            "background-size:cover;background-position:center 40%;"
        )
    else:
        bg = "background:linear-gradient(135deg,#060d1b 0%,#0d2035 45%,#0a2a40 100%);"

    return f"""
    <div style="
        {bg}
        border-radius:12px;
        margin-bottom:1rem;
        overflow:hidden;
        position:relative;
        min-height:160px;
        display:flex;
        align-items:center;
        justify-content:center;
        box-shadow:0 4px 18px rgba(0,0,0,0.5);
        border:1px solid rgba(0,212,255,0.14);
    ">
        <div style="
            position:absolute;inset:0;
            background:rgba(2,10,25,0.52);
        "></div>
        <div style="position:relative;z-index:1;text-align:center;padding:2.2rem 1.5rem;">
            <h1 style="
                color:#ffffff;margin:0 0 0.2rem;
                font-size:2rem;letter-spacing:5px;
                text-transform:uppercase;
                font-family:'Courier New',monospace;
                text-shadow:0 0 24px rgba(0,212,255,0.7);
            ">FLIGHT LOGBOOK</h1>
            <div style="
                color:#00d4ff;font-size:0.9rem;margin:0.2rem 0 0.4rem;
                font-family:'Courier New',monospace;letter-spacing:2px;
            ">── WELCOME, {safe_user} ──</div>
            <p style="
                color:#c0d8e8;margin:0;font-size:0.78rem;
                font-family:'Courier New',monospace;
            ">{safe_date}</p>
        </div>
    </div>
    """


def _hud_card(label: str, value: str, accent: str = "#00d4ff") -> str:
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


def render():
    try:
        from database import get_user_stats, get_recent_flights, get_home_display_prefs
        from utils import minutes_to_hhmm, format_date_eu
    except Exception as exc:
        st.error(f"Module load error: {exc}")
        return

    user = st.session_state.get("user") or {}
    if not user:
        return

    username  = user.get("username", "Pilot")
    today     = date.today().strftime("%A, %B %d, %Y")
    safe_user = _html.escape(username.upper())
    safe_date = _html.escape(today)

    # ================================================================== #
    # 1 ▸  HEADER — Heron image as background banner                      #
    # ================================================================== #
    img = _load_brightened(_BG_IMAGE, factor=1.5)
    st.markdown(_header_with_bg(img, safe_user, safe_date), unsafe_allow_html=True)

    # ================================================================== #
    # 2 ▸  QUICK ACTIONS — 2 × 2 grid                                    #
    # ================================================================== #
    qa1, qa2 = st.columns(2)
    if qa1.button("➕  New Flight",     use_container_width=True):
        st.session_state.page = "new_flight"
        st.rerun()
    if qa2.button("📋  My Flights",     use_container_width=True):
        st.session_state.page = "flight_history"
        st.rerun()

    qa3, qa4 = st.columns(2)
    if qa3.button("📊  Dashboard",      use_container_width=True):
        st.session_state.page = "dashboard"
        st.rerun()
    if qa4.button("⚙️  Settings",       use_container_width=True):
        st.session_state.page = "settings"
        st.rerun()

    # ================================================================== #
    # 3 ▸  STATS                                                          #
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

    last_flight_raw = str(stats.get("last_flight_date") or "")
    last_flight     = _html.escape(format_date_eu(last_flight_raw) if last_flight_raw else "—")

    try:
        prefs = get_home_display_prefs(user["id"])
    except Exception:
        prefs = {}

    def _show(key: str) -> bool:
        return prefs.get(key, "1") == "1"

    row1_cards = []
    if _show("show_total_flights"):
        row1_cards.append(_hud_card("TOTAL FLIGHTS", _num("total_flights")))
    if _show("show_total_hours"):
        row1_cards.append(_hud_card("TOTAL HOURS",   _hhmm("total_minutes")))
    if _show("show_pic_hours"):
        row1_cards.append(_hud_card("PIC HOURS",     _hhmm("pic_minutes")))
    if _show("show_last_flight"):
        row1_cards.append(_hud_card("LAST FLIGHT",   last_flight))

    day_tol   = (int(stats.get("total_day_takeoffs")  or 0)
               + int(stats.get("total_day_landings")   or 0))
    night_tol = (int(stats.get("total_night_takeoffs") or 0)
               + int(stats.get("total_night_landings") or 0))

    row2_cards = []
    if _show("show_sic_hours"):
        row2_cards.append(_hud_card("SIC HOURS",           _hhmm("sic_minutes"),        "#00e5a0"))
    if _show("show_instructor_hrs"):
        row2_cards.append(_hud_card("INSTRUCTOR HRS",      _hhmm("instructor_minutes"), "#00e5a0"))
    if _show("show_day_events"):
        row2_cards.append(_hud_card("DAY T/O & LANDINGS",   str(day_tol),   "#ffc857"))
    if _show("show_night_events"):
        row2_cards.append(_hud_card("NIGHT T/O & LANDINGS", str(night_tol), "#ffc857"))

    st.markdown(
        "<hr style='border:none;border-top:1px solid rgba(0,212,255,0.18);margin:0.8rem 0;'>",
        unsafe_allow_html=True,
    )

    if row1_cards:
        st.markdown(_hud_grid("".join(row1_cards)), unsafe_allow_html=True)
    if row2_cards:
        st.markdown(_hud_grid("".join(row2_cards)), unsafe_allow_html=True)

    st.markdown(
        "<hr style='border:none;border-top:1px solid rgba(0,212,255,0.18);margin:1.2rem 0 0.8rem;'>",
        unsafe_allow_html=True,
    )

    # ================================================================== #
    # 4 ▸  RECENT ACTIVITY                                                #
    # ================================================================== #
    try:
        recent = get_recent_flights(user["id"], limit=5) or []
    except Exception:
        recent = []

    if not recent:
        return

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
        display_date = _html.escape(format_date_eu(str(log.get("date", ""))))
        rows_html += (
            f'<div style="background:{bg_row};border-left:3px solid #00d4ff33;'
            f'padding:8px 12px;margin-bottom:4px;border-radius:0 5px 5px 0;'
            f'font-family:Courier New,monospace;font-size:0.82rem;">'
            f'<span style="color:#ffc857;">{display_date}   </span>'
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
