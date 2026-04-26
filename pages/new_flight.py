"""
pages/new_flight.py — New flight log entry.

IP mode   : manual Start/End times; duration = end − start.
EP mode   : events × 15 min each; if Start ≠ End the manual gap is ADDED on top.
BOTH mode : toggle at top to choose IP or EP per flight.

Aircraft selection uses three independent session_state-bound text fields plus a
separate "Auto-Fill from Saved Aircraft" selectbox.  The on_change callback
force-writes all three fields directly to session_state so they refresh
immediately when a different aircraft is chosen — eliminating the stale-data bug.

Saves to SQLite first, then POSTs to Google Sheets (Apps Script Web App).
"""

import streamlit as st
from datetime import date, time, datetime, timedelta

from database import (
    add_flight_log, get_aircraft, add_aircraft,
    get_aircraft_display_list,
    get_gcs_types, get_sites,
    get_custom_site_suggestions,
)
from utils import (
    calculate_ep_duration, append_flight_to_gsheet,
    aggregate_event_rows,
    MISSION_PURPOSES, CREW_ROLES, EVENT_TYPES, PERIODS, METHODS,
)

_MINS_PER_EVENT = 15
_AC_NONE        = "(none — type manually below)"


# ── Aircraft display label ─────────────────────────────────────────────────────

def _ac_label(a: dict) -> str:
    model = (a.get("model_type", "") or "").strip()
    tail  = (a.get("tail_number", "") or "").strip() or "—"
    cs    = (a.get("call_sign",   "") or "").strip() or "—"
    return f"{model} - {tail} - {cs}"


# ── Auto-fill on_change callback ───────────────────────────────────────────────
# Must be defined at module level so Streamlit can reference the same object
# across renders.  Reads the dropdown value and force-writes the three aircraft
# fields to session_state; the next render picks up the new values automatically.

def _autofill_cb():
    label   = st.session_state.get("nf_autofill_ac", _AC_NONE)
    ac_list = st.session_state.get("_nf_ac_cache", [])

    if label == _AC_NONE or not label:
        st.session_state["nf_aircraft_model"] = ""
        st.session_state["nf_tail_number"]    = ""
        st.session_state["nf_call_sign"]      = ""
        st.session_state["nf_selected_ac_id"] = None
        return

    labels = [_ac_label(a) for a in ac_list]
    if label not in labels:
        return

    a = ac_list[labels.index(label)]
    st.session_state["nf_aircraft_model"] = (a.get("model_type", "") or "").strip()
    st.session_state["nf_tail_number"]    = (a.get("tail_number", "") or "").strip()
    st.session_state["nf_call_sign"]      = (a.get("call_sign",   "") or "").strip()
    st.session_state["nf_selected_ac_id"] = a.get("id")


# ── State helpers ──────────────────────────────────────────────────────────────

def _init_state():
    defaults = [
        ("nf_version",        0),
        ("nf_events",         []),
        ("nf_event_ctr",      0),
        ("nf_autofill_ac",    _AC_NONE),
        ("nf_aircraft_model", ""),
        ("nf_tail_number",    ""),
        ("nf_call_sign",      ""),
        ("nf_selected_ac_id", None),
    ]
    for key, val in defaults:
        if key not in st.session_state:
            st.session_state[key] = val


def _clear_form():
    v = st.session_state.nf_version + 1
    for k in list(st.session_state.keys()):
        if k.startswith(("nf_et_", "nf_ep_", "nf_eq_", "nf_em_")):
            del st.session_state[k]
    st.session_state.nf_version              = v
    st.session_state.nf_events               = []
    st.session_state.nf_event_ctr            = 0
    st.session_state["nf_autofill_ac"]       = _AC_NONE
    st.session_state["nf_aircraft_model"]    = ""
    st.session_state["nf_tail_number"]       = ""
    st.session_state["nf_call_sign"]         = ""
    st.session_state["nf_selected_ac_id"]    = None


def _collect_events() -> list[dict]:
    return [
        {
            "type":   st.session_state.get(f"nf_et_{rid}", "Takeoff"),
            "period": st.session_state.get(f"nf_ep_{rid}", "Day"),
            "qty":    int(st.session_state.get(f"nf_eq_{rid}", 1)),
            "method": st.session_state.get(f"nf_em_{rid}", "Manual"),
        }
        for rid in st.session_state.nf_events
    ]


def _manual_minutes(start_t: time, end_t: time) -> int:
    if start_t == end_t:
        return 0
    s = datetime.combine(date.today(), start_t)
    e = datetime.combine(date.today(), end_t)
    if e < s:
        e += timedelta(days=1)
    return int((e - s).total_seconds() / 60)


def _derive_control_mode(events: list[dict]) -> str:
    """Return Manual / Automatic / Mixed derived from the event method toggles."""
    if not events:
        return "Manual"
    methods = {e.get("method", "Manual") for e in events}
    if methods == {"Automatic"}:
        return "Automatic"
    if methods == {"Manual"}:
        return "Manual"
    return "Mixed"


# ── Main render ────────────────────────────────────────────────────────────────

def render():
    _init_state()

    if st.session_state.pop("nf_save_success", False):
        st.success("✅ Flight saved successfully!")

    user_id      = st.session_state.user["id"]
    primary_role = st.session_state.get("primary_role", "IP")
    sheet_url    = st.session_state.get("sheet_url", "")
    v            = st.session_state.nf_version

    if st.button("← Home", key="nf_back"):
        st.session_state.page = "home"
        st.rerun()

    st.header("✈️ New Flight Log")

    # ── Mode toggle (BOTH role only) ───────────────────────────────────────────
    if primary_role == "BOTH":
        use_ep   = st.checkbox(
            "EP Mode — duration from events (qty × 15 min)",
            key=f"nf_ep_mode_{v}",
        )
        log_type = "EP" if use_ep else "IP"
    else:
        use_ep   = (primary_role == "EP")
        log_type = primary_role

    # ── Core flight fields ─────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown(f"**Log Type: {log_type}**")

        flight_date = st.date_input(
            "Date", value=date.today(), key=f"nf_date_{v}", format="DD/MM/YYYY"
        )

        # ── Aircraft ───────────────────────────────────────────────────────────
        # Load deduplicated list; cache it so the callback can look up records.
        ac_list = get_aircraft_display_list(user_id)
        st.session_state["_nf_ac_cache"] = ac_list
        ac_labels = [_ac_label(a) for a in ac_list]

        st.selectbox(
            "Auto-Fill from Saved Aircraft",
            options=[_AC_NONE] + ac_labels,
            key="nf_autofill_ac",
            on_change=_autofill_cb,
            help="Selecting here force-fills the three fields below.",
        )

        # Field A — bound to session_state; callback writes here directly
        st.text_input("Aircraft Model", key="nf_aircraft_model", placeholder="e.g. Heron 1")

        # Fields B & C
        _ct, _cc = st.columns(2)
        _ct.text_input("Tail Number", key="nf_tail_number", placeholder="e.g. 279")
        _cc.text_input("Call Sign",   key="nf_call_sign",   placeholder="e.g. UMD")

        # ── Site ────────────────────────────────────────────────────────────────
        sites_list         = get_sites(user_id)
        custom_suggestions = get_custom_site_suggestions(user_id)
        site_names         = [s["name"] for s in sites_list]
        site_opts          = site_names + ["Other / Custom Location"]
        sel_site           = st.selectbox("Site", site_opts, key=f"nf_site_{v}")

        if sel_site == "Other / Custom Location":
            site_id = None
            if custom_suggestions:
                prev = st.selectbox(
                    "Previous custom location",
                    [""] + custom_suggestions + ["Type new…"],
                    key=f"nf_site_prev_{v}",
                )
                if prev and prev != "Type new…":
                    custom_loc = prev
                else:
                    custom_loc = st.text_input(
                        "Location name", placeholder="e.g. Haifa Industrial Zone",
                        key=f"nf_site_txt_{v}",
                    )
            else:
                custom_loc = st.text_input(
                    "Location name", placeholder="e.g. Haifa Industrial Zone",
                    key=f"nf_site_txt_{v}",
                )
        else:
            match      = next((s for s in sites_list if s["name"] == sel_site), None)
            site_id    = match["id"] if match else None
            custom_loc = ""

        # ── Mission Type | GCS Type ────────────────────────────────────────────
        cm, cg = st.columns(2)
        mission_purpose = cm.selectbox("Mission Type", MISSION_PURPOSES, key=f"nf_mission_{v}")

        gcs_list  = get_gcs_types(user_id)
        gcs_names = [g["name"] for g in gcs_list]
        if gcs_names:
            gcs_opts = gcs_names + ["Other (free text)"]
            sel_gcs  = cg.selectbox("GCS Type", gcs_opts, key=f"nf_gcs_{v}")
            gcs_text = (
                st.text_input("GCS Type (custom)", key=f"nf_gcs_txt_{v}")
                if sel_gcs == "Other (free text)"
                else sel_gcs
            )
        else:
            gcs_text = cg.text_input(
                "GCS Type", placeholder="e.g. DJI Smart Controller", key=f"nf_gcs_txt_{v}"
            )

        # ── Crew Role | Instructor ────────────────────────────────────────────
        c_r, c_i      = st.columns(2)
        pilot_role    = c_r.selectbox("Pilot Role", CREW_ROLES, key=f"nf_role_{v}")
        is_instructor = c_i.checkbox("Instructor", key=f"nf_instructor_{v}")

        # ── Start / End time ──────────────────────────────────────────────────
        c1, c2  = st.columns(2)
        start_t = c1.time_input("Start Time", value=time(9, 0), step=900, key=f"nf_start_{v}")

        if use_ep:
            end_t   = c2.time_input("End Time", value=time(9, 0), step=900, key=f"nf_end_{v}")
            man_min = _manual_minutes(start_t, end_t)
            st.caption(
                "⏱ Manual time override active — added on top of events total."
                if man_min > 0 else
                "💡 Keep Start = End for events-only time. Set End later to add manual time."
            )
        else:
            end_t   = c2.time_input("End Time", value=time(9, 0), step=900, key=f"nf_end_{v}")
            man_min = _manual_minutes(start_t, end_t)
            h, m    = divmod(man_min, 60)
            st.caption(f"Duration: {h}h {m:02d}m")
            duration_minutes = man_min

    # ── Events table ──────────────────────────────────────────────────────────
    st.subheader("Events")
    ep_note = f" — each qty × {_MINS_PER_EVENT} min" if use_ep else " (optional)"
    with st.container(border=True):
        st.caption(f"Flight events{ep_note}.")

        if st.session_state.nf_events:
            hc = st.columns([2, 2, 1, 2, 0.6])
            hc[0].markdown("**Type**");  hc[1].markdown("**Day / Night**")
            hc[2].markdown("**Qty**");   hc[3].markdown("**Manual / Auto**")
            hc[4].markdown("**Del**")

        rows_to_remove = []
        for rid in st.session_state.nf_events:
            rc = st.columns([2, 2, 1, 2, 0.6])
            rc[0].selectbox("", EVENT_TYPES, key=f"nf_et_{rid}", label_visibility="collapsed")
            rc[1].selectbox("", PERIODS,     key=f"nf_ep_{rid}", label_visibility="collapsed")
            rc[2].number_input("", min_value=1, max_value=99, value=1,
                               key=f"nf_eq_{rid}", label_visibility="collapsed")
            rc[3].selectbox("", METHODS,     key=f"nf_em_{rid}", label_visibility="collapsed")
            if rc[4].button("✕", key=f"nf_del_{rid}", use_container_width=True):
                rows_to_remove.append(rid)

        for rid in rows_to_remove:
            st.session_state.nf_events.remove(rid)
            st.rerun()

        if st.button("＋ Add Event", use_container_width=True):
            st.session_state.nf_events.append(st.session_state.nf_event_ctr)
            st.session_state.nf_event_ctr += 1
            st.rerun()

    events = _collect_events()

    # ── EP duration summary ────────────────────────────────────────────────────
    if use_ep:
        events_min       = calculate_ep_duration(events)
        man_min          = _manual_minutes(start_t, end_t)
        duration_minutes = events_min + man_min
        h, m             = divmod(duration_minutes, 60)
        if man_min > 0:
            h_e, m_e = divmod(events_min, 60)
            h_m, m_m = divmod(man_min, 60)
            st.info(
                f"**{h}h {m:02d}m** total  —  "
                f"Events {h_e}h {m_e:02d}m  +  Manual {h_m}h {m_m:02d}m"
            )
        else:
            st.info(f"**{h}h {m:02d}m**  ({len(events)} event(s) × {_MINS_PER_EVENT} min)")

    # ── Comments ──────────────────────────────────────────────────────────────
    comments = st.text_area("Comments (optional)", height=80, key=f"nf_comments_{v}")

    # ── Save ──────────────────────────────────────────────────────────────────
    st.divider()
    if st.button("💾  Save Flight Log", use_container_width=True, type="primary"):

        if not sheet_url:
            st.error("No Google Sheet URL configured. Set it up in ⚙️ Settings first.")
            st.stop()

        # Read aircraft from session_state — single source of truth
        aircraft_model = st.session_state.get("nf_aircraft_model", "").strip()
        tail_number    = st.session_state.get("nf_tail_number",    "").strip()
        call_sign      = st.session_state.get("nf_call_sign",      "").strip()
        selected_ac_id = st.session_state.get("nf_selected_ac_id")

        if not aircraft_model:
            st.error("Aircraft Model is required.")
            st.stop()

        # Resolve to a DB record — verify saved ID is still valid, else create
        aircraft_record = None
        if selected_ac_id:
            aircraft_record = next(
                (a for a in get_aircraft(user_id) if a["id"] == selected_ac_id), None
            )

        if not aircraft_record:
            ok_ac, msg_ac = add_aircraft(user_id, aircraft_model, tail_number, call_sign)
            if not ok_ac:
                st.error(f"Could not save aircraft: {msg_ac}")
                st.stop()
            refreshed = get_aircraft(user_id)
            aircraft_record = next(
                (a for a in reversed(refreshed) if a["model_type"] == aircraft_model), None
            )
            if not aircraft_record:
                st.error("Failed to retrieve aircraft after creation.")
                st.stop()

        # Duration
        if use_ep:
            events_min_final = calculate_ep_duration(events)
            man_min_final    = _manual_minutes(start_t, end_t)
            duration_minutes = events_min_final + man_min_final
            if duration_minutes == 0:
                st.error("Total duration is 0. Add events or set End time later than Start.")
                st.stop()
            if duration_minutes >= 24 * 60:
                st.error("Duration exceeds 24 h. Check quantities or time values.")
                st.stop()
            h_ep, m_ep = divmod(duration_minutes, 60)
            db_start   = "00:00"
            db_end     = f"{h_ep:02d}:{m_ep:02d}"
        else:
            duration_minutes = _manual_minutes(start_t, end_t)
            if duration_minutes <= 0:
                st.error("End time must be after Start time.")
                st.stop()
            db_start = start_t.strftime("%H:%M")
            db_end   = end_t.strftime("%H:%M")

        event_data = aggregate_event_rows(events)

        # 1 — Save to SQLite
        ok_db, msg_db = add_flight_log(
            user_id         = user_id,
            aircraft_id     = aircraft_record["id"],
            date            = flight_date.strftime("%Y-%m-%d"),
            start_time      = db_start,
            end_time        = db_end,
            mission_purpose = mission_purpose,
            crew_role       = pilot_role,
            is_instructor   = is_instructor,
            gcs_type        = gcs_text,
            site_id         = site_id,
            site_custom     = custom_loc,
            comments        = comments.strip(),
            **event_data,
        )
        if not ok_db:
            st.error(f"Save failed: {msg_db}")
            st.stop()

        # 2 — Append to Google Sheets
        h_gs, m_gs = divmod(duration_minutes, 60)
        dur_str    = f"{h_gs}h {m_gs:02d}m"

        day_events = (
            event_data.get("takeoffs_day_manual",  0) + event_data.get("takeoffs_day_auto",  0)
          + event_data.get("landings_day_manual",   0) + event_data.get("landings_day_auto",  0)
        )
        night_events = (
            event_data.get("takeoffs_night_manual", 0) + event_data.get("takeoffs_night_auto", 0)
          + event_data.get("landings_night_manual",  0) + event_data.get("landings_night_auto", 0)
        )
        day_approaches = (
            event_data.get("approaches_day_manual",  0) + event_data.get("approaches_day_auto",  0)
        )
        night_approaches = (
            event_data.get("approaches_night_manual", 0) + event_data.get("approaches_night_auto", 0)
        )

        ok_gs, msg_gs = append_flight_to_gsheet(
            script_url=sheet_url,
            row={
                "date":             flight_date.strftime("%Y-%m-%d"),
                "pilot_name":       st.session_state.get("display_name", ""),
                "aircraft_type":    aircraft_model,
                "tail_number":      tail_number,
                "call_sign":        call_sign,
                "role":             pilot_role,
                "log_type":         log_type,
                "mission_type":     mission_purpose,
                "control_mode":     _derive_control_mode(events),
                "day_approaches":   day_approaches,
                "night_approaches": night_approaches,
                "instructor":       "Yes" if is_instructor else "No",
                "duration":         dur_str,
                "day_events":       day_events,
                "night_events":     night_events,
                "comments":         comments.strip(),
            },
        )

        if not ok_gs:
            st.warning(f"Saved locally. Google Sheets sync failed: {msg_gs}")

        st.session_state["nf_save_success"] = True
        _clear_form()
        st.rerun()
