"""
pages/new_flight.py — New flight log entry with IP, EP, and Dual modes.

IP mode  : enter start/end times manually; duration = end − start.
EP mode  : add events with quantities; duration = sum(qty × 15 min).
Dual mode: per-flight checkbox to toggle IP or EP logic.
"""

import streamlit as st
from datetime import date, time, datetime, timedelta

from utils import calculate_ep_duration, append_flight_to_gsheet

EVENT_TYPES = ["Takeoff", "Landing", "Approach"]
PILOT_ROLES = ["PIC", "SIC"]


def _init_state():
    if "nf_version"   not in st.session_state:
        st.session_state.nf_version   = 0
    if "nf_events"    not in st.session_state:
        st.session_state.nf_events    = []
    if "nf_event_ctr" not in st.session_state:
        st.session_state.nf_event_ctr = 0


def _clear_form():
    st.session_state.nf_version   = st.session_state.nf_version + 1
    st.session_state.nf_events    = []
    st.session_state.nf_event_ctr = 0
    for k in list(st.session_state.keys()):
        if k.startswith(("nf_et_", "nf_eq_")):
            del st.session_state[k]


def _collect_events() -> list[dict]:
    return [
        {
            "type": st.session_state.get(f"nf_et_{rid}", "Takeoff"),
            "qty":  int(st.session_state.get(f"nf_eq_{rid}", 1)),
        }
        for rid in st.session_state.nf_events
    ]


def render():
    _init_state()

    primary_role = st.session_state.get("primary_role", "IP")
    sheet_url    = st.session_state.get("sheet_url", "")
    v            = st.session_state.nf_version

    if st.button("← Home", key="nf_back"):
        st.session_state.page = "home"
        st.rerun()

    st.header("✈️ New Flight Log")

    # ── Mode ─────────────────────────────────────────────────────────────────
    if primary_role == "Dual":
        # Dual: checkbox per flight to choose IP or EP
        use_ep   = st.checkbox(
            "EP Mode — duration calculated from events (qty × 15 min)",
            key=f"nf_ep_mode_{v}",
        )
        log_type = "EP" if use_ep else "IP"
    else:
        use_ep   = (primary_role == "EP")
        log_type = primary_role

    # ── Core flight info ─────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown(f"**Log Type: {log_type}**")

        flight_date = st.date_input(
            "Date", value=date.today(), key=f"nf_date_{v}", format="DD/MM/YYYY"
        )
        pilot_role = st.selectbox("Pilot Role", PILOT_ROLES, key=f"nf_role_{v}")

        if not use_ep:
            # IP mode — manual start / end time entry
            c1, c2 = st.columns(2)
            start_t = c1.time_input("Start Time", value=time(9, 0),  step=900, key=f"nf_start_{v}")
            end_t   = c2.time_input("End Time",   value=time(10, 0), step=900, key=f"nf_end_{v}")

            start_dt = datetime.combine(date.today(), start_t)
            end_dt   = datetime.combine(date.today(), end_t)
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)
            duration_minutes = int((end_dt - start_dt).total_seconds() / 60)
            h, m = divmod(duration_minutes, 60)
            st.caption(f"Duration: {h}h {m:02d}m")
        else:
            duration_minutes = 0  # recalculated from events after this block

    # ── Events ───────────────────────────────────────────────────────────────
    st.subheader("Events")
    ep_note = " — each qty × 15 min added to duration" if use_ep else " (optional)"
    with st.container(border=True):
        st.caption(f"Add flight events{ep_note}.")

        rows_to_remove = []
        for rid in st.session_state.nf_events:
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.selectbox("Event Type", EVENT_TYPES, key=f"nf_et_{rid}")
                c2.number_input("Qty", min_value=1, max_value=99, value=1, key=f"nf_eq_{rid}")
                if c3.button("✕", key=f"nf_del_{rid}", use_container_width=True):
                    rows_to_remove.append(rid)

        for rid in rows_to_remove:
            st.session_state.nf_events.remove(rid)
            st.rerun()

        if st.button("＋ Add Event", use_container_width=True):
            st.session_state.nf_events.append(st.session_state.nf_event_ctr)
            st.session_state.nf_event_ctr += 1
            st.rerun()

    events = _collect_events()

    # EP: calculate and display duration from events
    if use_ep:
        duration_minutes = calculate_ep_duration(events)
        h, m = divmod(duration_minutes, 60)
        st.info(f"Calculated Duration: {h}h {m:02d}m ({duration_minutes} min total)")

    # ── Comments ─────────────────────────────────────────────────────────────
    comments = st.text_area("Comments (optional)", height=80, key=f"nf_comments_{v}")

    # ── Save ─────────────────────────────────────────────────────────────────
    st.divider()
    if st.button("💾  Save Flight Log", use_container_width=True, type="primary"):
        if not sheet_url:
            st.error("No Google Sheet URL configured. Please run the app setup again.")
            st.stop()

        if use_ep and not events:
            st.error("EP mode requires at least one event to calculate duration.")
            st.stop()

        # Final duration (EP recalculates in case events changed after display)
        if use_ep:
            duration_minutes = calculate_ep_duration(events)

        h, m       = divmod(duration_minutes, 60)
        dur_str    = f"{h}h {m:02d}m"
        events_str = ", ".join(f"{e['type']} ×{e['qty']}" for e in events) if events else ""

        ok, msg = append_flight_to_gsheet(
            sheet_url=sheet_url,
            row={
                "date":       flight_date.strftime("%Y-%m-%d"),
                "pilot_role": pilot_role,
                "log_type":   log_type,
                "duration":   dur_str,
                "events":     events_str,
                "comments":   comments.strip(),
            },
        )

        if ok:
            st.success(msg)
            _clear_form()
            st.rerun()
        else:
            st.error(msg)
