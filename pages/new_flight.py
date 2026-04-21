"""
pages/new_flight.py — New flight log entry.

IP mode   : manual Start/End times; duration = end − start.
EP mode   : events × 15 min each; if Start ≠ End the manual gap is ADDED on top.
BOTH mode : toggle at top to choose IP or EP per flight.

Saves to SQLite first, then POSTs to Google Sheets (Apps Script Web App).
"""

import streamlit as st
from datetime import date, time, datetime, timedelta

from database import (
    add_flight_log, get_aircraft, get_gcs_types, get_sites,
    get_custom_site_suggestions,
)
from utils import (
    calculate_ep_duration, append_flight_to_gsheet,
    aggregate_event_rows,
    MISSION_PURPOSES, CREW_ROLES, EVENT_TYPES, PERIODS, METHODS,
)

_MINS_PER_EVENT = 15


# ── State helpers ──────────────────────────────────────────────────────────────

def _init_state():
    for key, default in [
        ("nf_version",   0),
        ("nf_events",    []),
        ("nf_event_ctr", 0),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default


def _clear_form():
    v = st.session_state.nf_version + 1
    for k in list(st.session_state.keys()):
        if k.startswith(("nf_et_", "nf_ep_", "nf_eq_", "nf_em_")):
            del st.session_state[k]
    st.session_state.nf_version   = v
    st.session_state.nf_events    = []
    st.session_state.nf_event_ctr = 0


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
    """Return minutes between start and end (0 if equal; handles overnight)."""
    if start_t == end_t:
        return 0
    s = datetime.combine(date.today(), start_t)
    e = datetime.combine(date.today(), end_t)
    if e < s:
        e += timedelta(days=1)
    return int((e - s).total_seconds() / 60)


# ── Main render ────────────────────────────────────────────────────────────────

def render():
    _init_state()

    # One-cycle green success flash
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

        # Aircraft
        aircraft_list = get_aircraft(user_id)
        if not aircraft_list:
            st.warning("No aircraft found. Add one in **Settings** first.")
            return

        ac_labels = [
            f"{a['model_type']} — {a['tail_number']}"
            + (f"  ({a['call_sign']})" if a["call_sign"] else "")
            for a in aircraft_list
        ]
        pref_ac_id  = st.session_state.get("default_aircraft_id", "")
        pref_ac_idx = 0
        if pref_ac_id:
            for i, a in enumerate(aircraft_list):
                if str(a["id"]) == str(pref_ac_id):
                    pref_ac_idx = i
                    break

        sel_ac_label      = st.selectbox("Aircraft", ac_labels, index=pref_ac_idx, key=f"nf_ac_{v}")
        selected_aircraft = aircraft_list[ac_labels.index(sel_ac_label)]

        # Tail Number + Call Sign (pre-populated from aircraft, editable)
        ct, cc = st.columns(2)
        tail_number = ct.text_input(
            "Tail Number",
            value=selected_aircraft.get("tail_number", ""),
            key=f"nf_tail_{v}",
        )
        call_sign = cc.text_input(
            "Call Sign",
            value=selected_aircraft.get("call_sign", "") or "",
            key=f"nf_cs_{v}",
        )

        # Site
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

        # Mission Type | GCS Type | Control Mode
        cm, cg, cem = st.columns(3)
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

        control_mode = cem.selectbox("Control Mode", ["Manual", "Automatic"], key=f"nf_ctrl_mode_{v}")

        # Crew Role + Instructor
        c_r, c_i      = st.columns(2)
        pilot_role    = c_r.selectbox("Pilot Role", CREW_ROLES, key=f"nf_role_{v}")
        is_instructor = c_i.checkbox("Instructor", key=f"nf_instructor_{v}")

        # Start / End time — always visible for both IP and EP
        c1, c2  = st.columns(2)
        start_t = c1.time_input("Start Time", value=time(9, 0), step=900, key=f"nf_start_{v}")

        if use_ep:
            # EP default: same time → 0 manual override
            end_t   = c2.time_input("End Time", value=time(9, 0), step=900, key=f"nf_end_{v}")
            man_min = _manual_minutes(start_t, end_t)
            if man_min > 0:
                st.caption("⏱ Manual time override active — added on top of events total.")
            else:
                st.caption("💡 Keep Start = End for events-only time. Set End later to add manual time.")
        else:
            # IP: default end same as start; user sets manually
            end_t    = c2.time_input("End Time", value=time(9, 0), step=900, key=f"nf_end_{v}")
            man_min  = _manual_minutes(start_t, end_t)
            h, m     = divmod(man_min, 60)
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

    # ── EP duration summary (after events so totals are known) ────────────────
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

        # Final duration (re-evaluate widget state at save time)
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
            aircraft_id     = selected_aircraft["id"],
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
            event_data.get("takeoffs_day_manual",  0) + event_data.get("takeoffs_day_auto",    0)
          + event_data.get("landings_day_manual",   0) + event_data.get("landings_day_auto",     0)
        )
        night_events = (
            event_data.get("takeoffs_night_manual", 0) + event_data.get("takeoffs_night_auto",   0)
          + event_data.get("landings_night_manual",  0) + event_data.get("landings_night_auto",    0)
        )
        approach_count = (
            event_data.get("approaches_day_manual",   0) + event_data.get("approaches_day_auto",    0)
          + event_data.get("approaches_night_manual",  0) + event_data.get("approaches_night_auto",   0)
        )

        ok_gs, msg_gs = append_flight_to_gsheet(
            script_url=sheet_url,
            row={
                "date":           flight_date.strftime("%Y-%m-%d"),
                "pilot_name":     st.session_state.get("display_name", ""),
                "aircraft_type":  selected_aircraft["model_type"],
                "tail_number":    tail_number,
                "call_sign":      call_sign,
                "role":           pilot_role,
                "log_type":       log_type,
                "mission_type":   mission_purpose,
                "control_mode":   control_mode,
                "approach_count": approach_count,
                "instructor":     "Yes" if is_instructor else "No",
                "duration":       dur_str,
                "day_events":     day_events,
                "night_events":   night_events,
                "comments":       comments.strip(),
            },
        )

        if not ok_gs:
            st.warning(f"Saved locally. Google Sheets sync failed: {msg_gs}")

        # Green checkmark for one render cycle, then clear form
        st.session_state["nf_save_success"] = True
        _clear_form()
        st.rerun()
