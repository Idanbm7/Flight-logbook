"""
pages/new_flight.py — New Flight Log entry form.

Dynamic event rows (outside st.form) let users add/remove Takeoff / Landing /
Approach rows on the fly.  Time inputs snap to 15-minute increments (step=900 s).
"""

import streamlit as st
from datetime import date, time, datetime, timedelta

from database import (
    get_aircraft, add_aircraft, get_gcs_types, get_sites,
    add_flight_log, get_custom_site_suggestions,
)
from utils import (
    MISSION_PURPOSES, CREW_ROLES,
    EVENT_TYPES, PERIODS, METHODS,
    aggregate_event_rows,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sync_end_time():
    """Set end time = start time + 1 hour when start time changes."""
    v     = st.session_state.get("nf_version", 0)
    start = st.session_state.get(f"nf_start_{v}")
    if isinstance(start, time):
        new_end = (datetime.combine(date.today(), start) + timedelta(hours=1)).time()
        st.session_state[f"nf_end_{v}"] = new_end


def _init_state():
    if "nf_version"    not in st.session_state:
        st.session_state.nf_version    = 0
    if "nf_events"     not in st.session_state:
        st.session_state.nf_events     = []   # list of stable row IDs
    if "nf_event_ctr"  not in st.session_state:
        st.session_state.nf_event_ctr  = 0


def _clear_form():
    """Reset all nf_ widget keys and event rows after a successful save."""
    st.session_state.nf_version   = st.session_state.nf_version + 1
    st.session_state.nf_events    = []
    st.session_state.nf_event_ctr = 0
    for k in list(st.session_state.keys()):
        if k.startswith(("nf_et_", "nf_ep_", "nf_eq_", "nf_em_")):
            del st.session_state[k]


def _collect_events() -> list[dict]:
    return [
        {
            "type":   st.session_state.get(f"nf_et_{rid}", "Takeoff"),
            "period": st.session_state.get(f"nf_ep_{rid}", "Day"),
            "qty":    st.session_state.get(f"nf_eq_{rid}", 1),
            "method": st.session_state.get(f"nf_em_{rid}", "Manual"),
        }
        for rid in st.session_state.nf_events
    ]


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------

def render():
    _init_state()

    user_id          = st.session_state.user["id"]
    aircraft_list    = get_aircraft(user_id)
    gcs_list         = get_gcs_types(user_id)
    sites_list       = get_sites(user_id)
    custom_suggestions = get_custom_site_suggestions(user_id)

    v = st.session_state.nf_version   # version suffix — changing it resets widgets

    st.header("➕ New Flight Log")

    # ------------------------------------------------------------------ #
    # Date & Time                                                          #
    # ------------------------------------------------------------------ #
    st.subheader("Date & Time")
    c1, c2, c3 = st.columns(3)
    flight_date = c1.date_input("Date",       value=date.today(),  key=f"nf_date_{v}", format="DD/MM/YYYY")
    start_time  = c2.time_input("Start Time", value=time(9, 0),    step=900, key=f"nf_start_{v}",
                                on_change=_sync_end_time)
    end_time    = c3.time_input("End Time",   value=time(10, 0),   step=900, key=f"nf_end_{v}")

    # ------------------------------------------------------------------ #
    # Aircraft                                                             #
    # ------------------------------------------------------------------ #
    st.subheader("Aircraft")
    ac_opts = {
        f"{a['model_type']} — {a['tail_number']}"
        + (f"  ({a['call_sign']})" if a["call_sign"] else ""): a
        for a in aircraft_list
    }
    ac_choices = list(ac_opts.keys()) + ["Other / Enter manually"]
    selected_ac_label = st.selectbox("Select Aircraft", ac_choices, key=f"nf_ac_{v}")

    custom_ac_model = ""
    custom_ac_tail  = ""
    custom_ac_cs    = ""
    if selected_ac_label == "Other / Enter manually":
        ca1, ca2, ca3 = st.columns(3)
        custom_ac_model = ca1.text_input(
            "Model / Type *", placeholder="e.g. DJI Matrice 300", key=f"nf_ac_model_{v}"
        )
        custom_ac_tail = ca2.text_input(
            "Tail Number *", placeholder="e.g. 4X-UAV1", key=f"nf_ac_tail_{v}"
        )
        custom_ac_cs = ca3.text_input(
            "Call Sign", placeholder="e.g. ALPHA", key=f"nf_ac_cs_{v}"
        )
        st.caption("Aircraft will be added to your fleet automatically on save.")

    # ------------------------------------------------------------------ #
    # Location                                                             #
    # ------------------------------------------------------------------ #
    st.subheader("Location")
    site_names = [s["name"] for s in sites_list]
    site_opts  = site_names + ["Other / New Location"]
    site_choice = st.selectbox("Select Site", site_opts, key=f"nf_site_{v}")

    custom_loc = ""
    if site_choice == "Other / New Location":
        custom_loc = st.text_input(
            "Enter location name",
            placeholder="e.g. Haifa Bay",
            help="Will appear as a suggestion in future logs.",
            key=f"nf_custom_loc_{v}",
        )
        if custom_suggestions:
            st.caption("Previously used: " + " · ".join(custom_suggestions[:8]))

    # ------------------------------------------------------------------ #
    # Mission Details                                                       #
    # ------------------------------------------------------------------ #
    st.subheader("Mission Details")
    c4, c5 = st.columns(2)
    mission_purpose = c4.selectbox(
        "Mission Purpose", MISSION_PURPOSES, key=f"nf_mission_{v}"
    )

    # GCS type: dropdown from settings, plus optional free-text fallback
    gcs_names = [g["name"] for g in gcs_list]
    if gcs_names:
        gcs_opts   = gcs_names + ["Other (type below)"]
        gcs_choice = c5.selectbox("GCS Type", gcs_opts, key=f"nf_gcs_{v}")
        if gcs_choice == "Other (type below)":
            gcs_text = st.text_input(
                "GCS Type (custom)", placeholder="e.g. Custom GCS", key=f"nf_gcs_text_{v}"
            )
        else:
            gcs_text = gcs_choice
    else:
        gcs_text = c5.text_input(
            "GCS Type", placeholder="Add GCS types in Settings",
            key=f"nf_gcs_text_{v}"
        )

    c6, c7 = st.columns(2)
    crew_role     = c6.selectbox("Crew Role", CREW_ROLES, key=f"nf_role_{v}")
    is_instructor = c7.checkbox("Acting as Instructor", key=f"nf_instr_{v}")

    st.divider()

    # ------------------------------------------------------------------ #
    # Dynamic Events                                                        #
    # ------------------------------------------------------------------ #
    st.subheader("Events")

    with st.container(border=True):
        st.caption(
            "Add one card per event type / condition combination. "
            "Leave empty if no events to record."
        )

        rows_to_remove = []
        for rid in st.session_state.nf_events:
            with st.container(border=True):
                top = st.columns(2)
                top[0].selectbox("Event Type", EVENT_TYPES, key=f"nf_et_{rid}")
                top[1].selectbox("Day / Night", PERIODS,    key=f"nf_ep_{rid}")

                bot = st.columns([1, 2, 1])
                bot[0].number_input("Qty", min_value=1, max_value=99, value=1, key=f"nf_eq_{rid}")
                bot[1].selectbox("Method", METHODS, key=f"nf_em_{rid}")
                if bot[2].button("✕", key=f"nf_del_{rid}", use_container_width=True,
                                 help="Remove this event"):
                    rows_to_remove.append(rid)

        for rid in rows_to_remove:
            st.session_state.nf_events.remove(rid)
            st.rerun()

        if st.button("＋ Add Event", use_container_width=True):
            new_id = st.session_state.nf_event_ctr
            st.session_state.nf_events.append(new_id)
            st.session_state.nf_event_ctr += 1
            st.rerun()

    st.divider()

    # ------------------------------------------------------------------ #
    # Comments                                                             #
    # ------------------------------------------------------------------ #
    comments = st.text_area(
        "Comments (optional)", height=90, key=f"nf_comments_{v}"
    )

    # ------------------------------------------------------------------ #
    # Save                                                                  #
    # ------------------------------------------------------------------ #
    if st.button("💾  Save Flight Log", use_container_width=True, type="primary"):
        # Resolve aircraft
        if selected_ac_label == "Other / Enter manually":
            if not custom_ac_model.strip() or not custom_ac_tail.strip():
                st.error("Model/Type and Tail Number are required for a new aircraft.")
                st.stop()
            existing_ac = next(
                (a for a in aircraft_list
                 if a["model_type"].lower() == custom_ac_model.strip().lower()
                 and a["tail_number"].lower() == custom_ac_tail.strip().lower()),
                None,
            )
            if existing_ac:
                resolved_aircraft_id = existing_ac["id"]
            else:
                ok_ac, _ = add_aircraft(user_id, custom_ac_model.strip(),
                                        custom_ac_tail.strip(), custom_ac_cs.strip())
                if not ok_ac:
                    st.error("Could not save the new aircraft. Please try again.")
                    st.stop()
                fresh_ac = get_aircraft(user_id)
                found_ac = next(
                    (a for a in fresh_ac if a["tail_number"] == custom_ac_tail.strip()), None
                )
                if not found_ac:
                    st.error("Aircraft was not saved correctly. Please try again.")
                    st.stop()
                resolved_aircraft_id = found_ac["id"]
        else:
            resolved_aircraft_id = ac_opts[selected_ac_label]["id"]

        # Resolve site
        site_id       = None
        site_custom   = ""
        if site_choice != "Other / New Location":
            match = next((s for s in sites_list if s["name"] == site_choice), None)
            site_id = match["id"] if match else None
        else:
            site_custom = custom_loc

        event_data = aggregate_event_rows(_collect_events())

        ok, msg = add_flight_log(
            user_id        = user_id,
            aircraft_id    = resolved_aircraft_id,
            date           = flight_date.strftime("%Y-%m-%d"),
            start_time     = start_time.strftime("%H:%M"),
            end_time       = end_time.strftime("%H:%M"),
            mission_purpose= mission_purpose,
            crew_role      = crew_role,
            is_instructor  = is_instructor,
            gcs_type       = gcs_text,
            site_id        = site_id,
            site_custom    = site_custom,
            comments       = comments,
            **event_data,
        )

        if ok:
            st.success(msg)
            _clear_form()
            st.rerun()
        else:
            st.error(msg)
