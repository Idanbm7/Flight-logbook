"""
pages/settings.py — Full CRUD for Aircraft, GCS Types, and Sites.
"""

import streamlit as st
from database import (
    get_aircraft, add_aircraft, update_aircraft, retire_aircraft,
    delete_aircraft, aircraft_has_flights,
    get_gcs_types, add_gcs_type, update_gcs_type, delete_gcs_type,
    get_sites, add_site, update_site, delete_site, site_has_flights,
    get_home_display_prefs, set_home_display_pref,
)


# ---------------------------------------------------------------------------
# Helpers — inline edit state
# ---------------------------------------------------------------------------

def _edit_key(entity: str, item_id: int) -> str:
    return f"settings_editing_{entity}_{item_id}"


def _is_editing(entity: str, item_id: int) -> bool:
    return st.session_state.get(_edit_key(entity, item_id), False)


def _start_edit(entity: str, item_id: int):
    st.session_state[_edit_key(entity, item_id)] = True


def _stop_edit(entity: str, item_id: int):
    st.session_state[_edit_key(entity, item_id)] = False


# ---------------------------------------------------------------------------
# Aircraft section
# ---------------------------------------------------------------------------

def _section_aircraft(user_id: int):
    st.subheader("✈️ Aircraft")

    aircraft_list = get_aircraft(user_id, active_only=False)
    active  = [a for a in aircraft_list if a["is_active"]]
    retired = [a for a in aircraft_list if not a["is_active"]]

    if not active:
        st.info("No active aircraft. Add one below.")

    for ac in active:
        cs_tag = f"  ({ac['call_sign']})" if ac["call_sign"] else ""
        label  = f"{ac['model_type']} — {ac['tail_number']}{cs_tag}"

        with st.expander(label):
            if _is_editing("ac", ac["id"]):
                # ---- Edit form ----
                new_model = st.text_input("Model / Type *",  value=ac["model_type"],
                                          key=f"ac_edit_model_{ac['id']}")
                new_tail  = st.text_input("Tail Number *",   value=ac["tail_number"],
                                          key=f"ac_edit_tail_{ac['id']}")
                new_cs    = st.text_input("Call Sign",       value=ac["call_sign"] or "",
                                          key=f"ac_edit_cs_{ac['id']}")
                b_save, b_cancel = st.columns(2)
                if b_save.button("💾 Save", key=f"ac_save_{ac['id']}", use_container_width=True):
                    ok, msg = update_aircraft(ac["id"], user_id, new_model, new_tail, new_cs)
                    if ok:
                        _stop_edit("ac", ac["id"])
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                if b_cancel.button("Cancel", key=f"ac_cancel_{ac['id']}", use_container_width=True):
                    _stop_edit("ac", ac["id"])
                    st.rerun()
            else:
                # ---- View mode ----
                st.write(f"**Model/Type:** {ac['model_type']}")
                st.write(f"**Tail Number:** {ac['tail_number']}")
                st.write(f"**Call Sign:** {ac['call_sign'] or '—'}")

                has_flights = aircraft_has_flights(ac["id"])
                b1, b2, b3 = st.columns(3)

                if b1.button("✏️ Edit", key=f"ac_edit_btn_{ac['id']}", use_container_width=True):
                    _start_edit("ac", ac["id"])
                    st.rerun()

                if b2.button("🛑 Retire", key=f"ac_retire_{ac['id']}", use_container_width=True):
                    ok, msg = retire_aircraft(ac["id"], user_id)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

                if not has_flights:
                    if b3.button("🗑️ Delete", key=f"ac_del_{ac['id']}", use_container_width=True):
                        ok, msg = delete_aircraft(ac["id"], user_id)
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                else:
                    b3.caption("Delete unavailable\n(has flight logs)")

    if retired:
        with st.expander(f"Retired aircraft ({len(retired)})"):
            for ac in retired:
                st.write(f"~~{ac['model_type']} — {ac['tail_number']}~~")

    # ---- Add new aircraft ----
    st.markdown("**Add New Aircraft**")
    with st.form("add_aircraft_form", clear_on_submit=True):
        nc1, nc2, nc3 = st.columns(3)
        model_type  = nc1.text_input("Model / Type *", placeholder="e.g. DJI Matrice 300")
        tail_number = nc2.text_input("Tail Number *",  placeholder="e.g. 4X-UAV1")
        call_sign   = nc3.text_input("Call Sign",      placeholder="e.g. ALPHA")
        if st.form_submit_button("Add Aircraft", use_container_width=True):
            ok, msg = add_aircraft(user_id, model_type, tail_number, call_sign)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)


# ---------------------------------------------------------------------------
# GCS Types section
# ---------------------------------------------------------------------------

def _section_gcs(user_id: int):
    st.subheader("🎮 GCS Types")

    gcs_list = get_gcs_types(user_id)

    if not gcs_list:
        st.info("No GCS types saved yet. Add one below.")

    for g in gcs_list:
        with st.expander(g["name"]):
            if _is_editing("gcs", g["id"]):
                new_name = st.text_input("GCS Name *", value=g["name"],
                                         key=f"gcs_edit_name_{g['id']}")
                gb1, gb2 = st.columns(2)
                if gb1.button("💾 Save", key=f"gcs_save_{g['id']}", use_container_width=True):
                    ok, msg = update_gcs_type(g["id"], user_id, new_name)
                    if ok:
                        _stop_edit("gcs", g["id"])
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                if gb2.button("Cancel", key=f"gcs_cancel_{g['id']}", use_container_width=True):
                    _stop_edit("gcs", g["id"])
                    st.rerun()
            else:
                gc1, gc2 = st.columns(2)
                if gc1.button("✏️ Edit", key=f"gcs_edit_btn_{g['id']}", use_container_width=True):
                    _start_edit("gcs", g["id"])
                    st.rerun()
                if gc2.button("🗑️ Delete", key=f"gcs_del_{g['id']}", use_container_width=True):
                    ok, msg = delete_gcs_type(g["id"], user_id)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    st.markdown("**Add New GCS Type**")
    with st.form("add_gcs_form", clear_on_submit=True):
        gcs_name = st.text_input("GCS Type Name *",
                                  placeholder="e.g. DJI Smart Controller")
        if st.form_submit_button("Add GCS Type", use_container_width=True):
            ok, msg = add_gcs_type(user_id, gcs_name)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)


# ---------------------------------------------------------------------------
# Sites section
# ---------------------------------------------------------------------------

def _section_sites(user_id: int):
    st.subheader("📍 Saved Sites / Locations")

    sites = get_sites(user_id)

    if not sites:
        st.info("No sites saved yet. Add one below.")

    for s in sites:
        with st.expander(s["name"]):
            if _is_editing("site", s["id"]):
                new_name = st.text_input("Site Name *", value=s["name"],
                                         key=f"site_edit_name_{s['id']}")
                sb1, sb2 = st.columns(2)
                if sb1.button("💾 Save", key=f"site_save_{s['id']}", use_container_width=True):
                    ok, msg = update_site(s["id"], user_id, new_name)
                    if ok:
                        _stop_edit("site", s["id"])
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                if sb2.button("Cancel", key=f"site_cancel_{s['id']}", use_container_width=True):
                    _stop_edit("site", s["id"])
                    st.rerun()
            else:
                sc1, sc2 = st.columns(2)
                if sc1.button("✏️ Edit", key=f"site_edit_btn_{s['id']}", use_container_width=True):
                    _start_edit("site", s["id"])
                    st.rerun()

                has_fl = site_has_flights(s["id"])
                if not has_fl:
                    if sc2.button("🗑️ Delete", key=f"site_del_{s['id']}", use_container_width=True):
                        ok, msg = delete_site(s["id"], user_id)
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                else:
                    sc2.caption("Delete unavailable\n(has flight logs)")

    st.markdown("**Add New Site**")
    with st.form("add_site_form", clear_on_submit=True):
        site_name = st.text_input("Site Name *", placeholder="e.g. Haifa Industrial Zone")
        if st.form_submit_button("Add Site", use_container_width=True):
            ok, msg = add_site(user_id, site_name)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)


# ---------------------------------------------------------------------------
# Display Settings section
# ---------------------------------------------------------------------------

_HOME_STATS = [
    ("show_total_flights",  "Total Flights"),
    ("show_total_hours",    "Total Hours"),
    ("show_pic_hours",      "PIC Hours"),
    ("show_last_flight",    "Last Flight"),
    ("show_sic_hours",      "SIC Hours"),
    ("show_instructor_hrs", "Instructor Hours"),
    ("show_day_events",     "Day T/O & Landings"),
    ("show_night_events",   "Night T/O & Landings"),
]


def _section_display(user_id: int):
    st.subheader("🏠 Home Page Stats")
    st.caption("Toggle which stat cards are visible on the Home page.")

    prefs   = get_home_display_prefs(user_id)
    changed = False

    for key, label in _HOME_STATS:
        current = prefs.get(key, "1") == "1"
        new_val = st.checkbox(label, value=current, key=f"disp_{key}")
        if new_val != current:
            set_home_display_pref(user_id, key, "1" if new_val else "0")
            changed = True

    if changed:
        st.success("Display preferences saved.")
        st.rerun()


# ---------------------------------------------------------------------------
# Main render — tabbed layout
# ---------------------------------------------------------------------------

def render():
    st.header("⚙️ Settings")

    user_id = st.session_state.user["id"]

    tab_ac, tab_gcs, tab_sites, tab_disp = st.tabs(
        ["✈️ Aircraft", "🎮 GCS Types", "📍 Sites", "🖥️ Display"]
    )

    with tab_ac:
        _section_aircraft(user_id)

    with tab_gcs:
        _section_gcs(user_id)

    with tab_sites:
        _section_sites(user_id)

    with tab_disp:
        _section_display(user_id)
