"""
pages/flight_history.py — Browse, filter (incl. IP/EP), edit, and export flight logs.
"""

import os
import datetime
import streamlit as st

from utils import (
    flight_logs_to_dataframe, export_to_excel, export_to_pdf,
    minutes_to_hhmm, MISSION_PURPOSES, CREW_ROLES,
    aggregate_event_rows, flight_log_to_event_rows,
    EVENT_TYPES, PERIODS, METHODS, format_date_eu,
    delete_flight_from_gsheet,
)
from database import (
    get_flight_logs, get_flight_log_by_id,
    delete_flight_log, update_flight_log,
    get_aircraft, get_gcs_types, get_sites,
)

EXPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _derive_log_type(log: dict) -> str:
    """EP flights are stored with start_time '00:00'; all others are IP."""
    return "EP" if log.get("start_time") == "00:00" else "IP"


# ---------------------------------------------------------------------------
# Edit dialog
# ---------------------------------------------------------------------------

@st.dialog("Edit Flight Log", width="large")
def _edit_dialog(log_id: int):
    user_id       = st.session_state.user["id"]
    log           = get_flight_log_by_id(log_id, user_id)
    if not log:
        st.error("Flight log not found.")
        return

    aircraft_list = get_aircraft(user_id)
    gcs_list      = get_gcs_types(user_id)
    sites_list    = get_sites(user_id)

    ev_key  = f"ded_events_{log_id}"
    ctr_key = f"ded_ctr_{log_id}"
    ini_key = f"ded_init_{log_id}"

    if ini_key not in st.session_state:
        initial = flight_log_to_event_rows(log)
        st.session_state[ev_key]  = list(range(len(initial)))
        st.session_state[ctr_key] = len(initial)
        for i, row in enumerate(initial):
            st.session_state[f"ded_et_{log_id}_{i}"] = row["type"]
            st.session_state[f"ded_ep_{log_id}_{i}"] = row["period"]
            st.session_state[f"ded_eq_{log_id}_{i}"] = row["qty"]
            st.session_state[f"ded_em_{log_id}_{i}"] = row["method"]
        st.session_state[ini_key] = True

    c1, c2, c3     = st.columns(3)
    existing_date  = datetime.date.fromisoformat(log["date"])
    existing_start = datetime.time.fromisoformat(log["start_time"])
    existing_end   = datetime.time.fromisoformat(log["end_time"])

    flight_date = c1.date_input("Date",       value=existing_date,  key=f"ded_date_{log_id}",  format="DD/MM/YYYY")
    start_time  = c2.time_input("Start Time", value=existing_start, step=900, key=f"ded_start_{log_id}")
    end_time    = c3.time_input("End Time",   value=existing_end,   step=900, key=f"ded_end_{log_id}")

    ac_opts = {
        f"{a['model_type']} — {a['tail_number']}"
        + (f"  ({a['call_sign']})" if a["call_sign"] else ""): a
        for a in aircraft_list
    }
    ac_keys = list(ac_opts.keys())
    cur_ac  = next((k for k, v in ac_opts.items() if v["id"] == log["aircraft_id"]),
                   ac_keys[0] if ac_keys else "")
    ac_idx  = ac_keys.index(cur_ac) if cur_ac in ac_keys else 0
    sel_ac  = st.selectbox("Aircraft", ac_keys, index=ac_idx, key=f"ded_ac_{log_id}")

    site_names  = [s["name"] for s in sites_list]
    cur_site    = next((s["name"] for s in sites_list if s["id"] == log.get("site_id")),
                       "Other / Custom Location")
    site_opts   = site_names + ["Other / Custom Location"]
    s_idx       = site_opts.index(cur_site) if cur_site in site_opts else len(site_opts) - 1
    site_choice = st.selectbox("Site", site_opts, index=s_idx, key=f"ded_site_{log_id}")

    custom_loc = ""
    if site_choice == "Other / Custom Location":
        custom_loc = st.text_input(
            "Location name", value=log.get("site_custom", "") or "",
            key=f"ded_custom_{log_id}",
        )

    c4, c5          = st.columns(2)
    mp_idx          = MISSION_PURPOSES.index(log["mission_purpose"]) \
                      if log["mission_purpose"] in MISSION_PURPOSES else 0
    mission_purpose = c4.selectbox("Mission Purpose", MISSION_PURPOSES,
                                   index=mp_idx, key=f"ded_mission_{log_id}")

    gcs_names = [g["name"] for g in gcs_list]
    if gcs_names:
        gcs_opts = gcs_names + ["Other (free text)"]
        cur_gcs  = log.get("gcs_type", "") or ""
        g_idx    = gcs_names.index(cur_gcs) if cur_gcs in gcs_names else len(gcs_opts) - 1
        gcs_sel  = c5.selectbox("GCS Type", gcs_opts, index=g_idx, key=f"ded_gcs_{log_id}")
        gcs_text = (
            st.text_input("GCS Type (custom)",
                          value=cur_gcs if cur_gcs not in gcs_names else "",
                          key=f"ded_gcs_text_{log_id}")
            if gcs_sel == "Other (free text)" else gcs_sel
        )
    else:
        gcs_text = c5.text_input("GCS Type",
                                  value=log.get("gcs_type", "") or "",
                                  key=f"ded_gcs_text_{log_id}")

    c6, c7        = st.columns(2)
    r_idx         = CREW_ROLES.index(log["crew_role"]) if log["crew_role"] in CREW_ROLES else 0
    crew_role     = c6.selectbox("Crew Role", CREW_ROLES, index=r_idx, key=f"ded_role_{log_id}")
    is_instructor = c7.checkbox("Instructor",
                                value=bool(log.get("is_instructor")),
                                key=f"ded_instr_{log_id}")

    st.subheader("Events")
    ev_list = st.session_state[ev_key]

    if ev_list:
        hc = st.columns([2, 2, 1, 2, 0.6])
        hc[0].markdown("**Type**");      hc[1].markdown("**Day / Night**")
        hc[2].markdown("**Qty**");       hc[3].markdown("**Manual / Auto**")
        hc[4].markdown("**Del**")

    to_del = []
    for rid in ev_list:
        rc = st.columns([2, 2, 1, 2, 0.6])
        rc[0].selectbox("", EVENT_TYPES, key=f"ded_et_{log_id}_{rid}", label_visibility="collapsed")
        rc[1].selectbox("", PERIODS,     key=f"ded_ep_{log_id}_{rid}", label_visibility="collapsed")
        rc[2].number_input("", min_value=1, max_value=99, value=1,
                           key=f"ded_eq_{log_id}_{rid}", label_visibility="collapsed")
        rc[3].selectbox("", METHODS,     key=f"ded_em_{log_id}_{rid}", label_visibility="collapsed")
        if rc[4].button("✕", key=f"ded_del_{log_id}_{rid}"):
            to_del.append(rid)

    for rid in to_del:
        st.session_state[ev_key].remove(rid)
        st.rerun()

    if st.button("＋ Add Event Row", key=f"ded_add_{log_id}"):
        new_id = st.session_state[ctr_key]
        st.session_state[ev_key].append(new_id)
        st.session_state[ctr_key] += 1
        st.rerun()

    comments = st.text_area("Comments", value=log.get("comments", "") or "",
                             key=f"ded_comments_{log_id}")

    btn_save, btn_cancel = st.columns(2)
    if btn_save.button("💾 Save Changes", use_container_width=True, type="primary"):
        event_rows = [
            {
                "type":   st.session_state.get(f"ded_et_{log_id}_{rid}", "Takeoff"),
                "period": st.session_state.get(f"ded_ep_{log_id}_{rid}", "Day"),
                "qty":    st.session_state.get(f"ded_eq_{log_id}_{rid}", 1),
                "method": st.session_state.get(f"ded_em_{log_id}_{rid}", "Manual"),
            }
            for rid in st.session_state[ev_key]
        ]
        event_data  = aggregate_event_rows(event_rows)
        site_id     = None
        site_custom = ""
        if site_choice != "Other / Custom Location":
            match   = next((s for s in sites_list if s["name"] == site_choice), None)
            site_id = match["id"] if match else None
        else:
            site_custom = custom_loc

        ok, msg = update_flight_log(
            log_id=log_id, user_id=user_id, aircraft_id=ac_opts[sel_ac]["id"],
            date=flight_date.strftime("%Y-%m-%d"),
            start_time=start_time.strftime("%H:%M"),
            end_time=end_time.strftime("%H:%M"),
            mission_purpose=mission_purpose, crew_role=crew_role,
            is_instructor=is_instructor, gcs_type=gcs_text,
            site_id=site_id, site_custom=site_custom, comments=comments,
            **event_data,
        )
        if ok:
            del st.session_state[ini_key]
            st.toast("✅ Flight updated!")
            st.rerun()
        else:
            st.error(msg)

    if btn_cancel.button("Cancel", use_container_width=True):
        del st.session_state[ini_key]
        st.rerun()


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------

def render():
    if st.button("← Home", key="fh_back"):
        st.session_state.page = "home"
        st.rerun()

    st.header("📋 My Flights")

    user_id = st.session_state.user["id"]
    logs    = get_flight_logs(user_id)

    if not logs:
        st.info("No flights logged yet. Use **New Flight** to add your first entry.")
        return

    # ── Filters ───────────────────────────────────────────────────────────────
    with st.expander("🔍 Filters", expanded=False):
        fc1, fc2, fc3 = st.columns(3)
        f_mission  = fc1.selectbox("Mission",  ["All"] + sorted({l["mission_purpose"] for l in logs}))
        f_role     = fc2.selectbox("Role",     ["All", "PIC", "SIC"])
        f_aircraft = fc3.selectbox("Aircraft", ["All"] + sorted({l["model_type"] for l in logs}))

        fc4, fc5 = st.columns(2)
        f_instructor = fc4.selectbox("Instructor", ["All", "Yes", "No"])
        f_log_type   = fc5.selectbox("Log Type",   ["All", "IP", "EP"])

        dc1, dc2 = st.columns(2)
        f_date_from = dc1.date_input("From Date", value=None, key="fh_from", format="DD/MM/YYYY")
        f_date_to   = dc2.date_input("To Date",   value=None, key="fh_to",   format="DD/MM/YYYY")

    filtered = []
    for l in logs:
        lt = _derive_log_type(l)
        if (f_mission    != "All" and l["mission_purpose"] != f_mission):    continue
        if (f_role       != "All" and l["crew_role"]       != f_role):       continue
        if (f_aircraft   != "All" and l["model_type"]      != f_aircraft):   continue
        if (f_instructor == "Yes" and not l["is_instructor"]):                continue
        if (f_instructor == "No"  and     l["is_instructor"]):                continue
        if (f_log_type   != "All" and lt                   != f_log_type):   continue
        if (f_date_from  and l["date"] < f_date_from.strftime("%Y-%m-%d")):  continue
        if (f_date_to    and l["date"] > f_date_to.strftime("%Y-%m-%d")):    continue
        filtered.append(l)

    st.caption(f"Showing {len(filtered)} of {len(logs)} flights")

    # ── Export ────────────────────────────────────────────────────────────────
    with st.expander("📤 Export", expanded=False):
        st.caption("Exports apply to the currently filtered list.")
        os.makedirs(EXPORT_DIR, exist_ok=True)

        username = st.session_state.get(
            "display_name", st.session_state.user.get("username", "pilot")
        )
        exp_c1, exp_c2, exp_c3 = st.columns(3)

        # CSV
        try:
            df_exp = flight_logs_to_dataframe(filtered)
            if not df_exp.empty:
                exp_c1.download_button(
                    "⬇️ CSV", data=df_exp.to_csv(index=False).encode("utf-8-sig"),
                    file_name="flight_logbook.csv", mime="text/csv",
                    use_container_width=True, key="dl_csv",
                )
            else:
                exp_c1.caption("No data.")
        except Exception as e:
            exp_c1.error(f"CSV: {e}")

        # Excel
        if exp_c2.button("📊 Excel", use_container_width=True, key="exp_xlsx_btn"):
            fp = os.path.join(EXPORT_DIR, "flight_logbook.xlsx")
            ok, msg = export_to_excel(filtered, fp)
            if ok:
                with open(fp, "rb") as fh:
                    exp_c2.download_button(
                        "⬇️ Download", data=fh.read(),
                        file_name="flight_logbook.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_xlsx", use_container_width=True,
                    )
            else:
                exp_c2.error(msg)

        # PDF
        if exp_c3.button("📄 PDF", use_container_width=True, key="exp_pdf_btn"):
            fp = os.path.join(EXPORT_DIR, "flight_logbook.pdf")
            ok, msg = export_to_pdf(filtered, fp, username=username)
            if ok:
                with open(fp, "rb") as fh:
                    exp_c3.download_button(
                        "⬇️ Download", data=fh.read(),
                        file_name="flight_logbook.pdf", mime="application/pdf",
                        key="dl_pdf", use_container_width=True,
                    )
            else:
                exp_c3.error(msg)

    st.divider()

    # ── Flight cards ──────────────────────────────────────────────────────────
    for log in filtered:
        log_type    = _derive_log_type(log)
        instr_badge = " 🎓" if log["is_instructor"] else ""
        lt_badge    = f" [{log_type}]"

        with st.expander(
            f"**{format_date_eu(log['date'])}**{lt_badge} · {log['model_type']} · "
            f"{log['location_name']} · {log['crew_role']}{instr_badge} · "
            f"{minutes_to_hhmm(log['duration_minutes'])} hrs"
        ):
            r1c1, r1c2, r1c3 = st.columns(3)
            r1c1.metric("Duration",   minutes_to_hhmm(log["duration_minutes"]) + " hrs")
            r1c2.metric("Mission",    log["mission_purpose"])
            r1c3.metric("GCS",        log["gcs_type"] or "—")

            r2c1, r2c2, r2c3 = st.columns(3)
            r2c1.metric("Tail #",     log["tail_number"])
            r2c2.metric("Call Sign",  log["call_sign"] or "—")
            r2c3.metric("Instructor", "Yes" if log["is_instructor"] else "No")

            t_day   = log["takeoffs_day_manual"]    + log["takeoffs_day_auto"]
            t_night = log["takeoffs_night_manual"]  + log["takeoffs_night_auto"]
            l_day   = log["landings_day_manual"]    + log["landings_day_auto"]
            l_night = log["landings_night_manual"]  + log["landings_night_auto"]
            a_total = (log["approaches_day_manual"] + log["approaches_day_auto"]
                       + log["approaches_night_manual"] + log["approaches_night_auto"])

            ec1, ec2, ec3 = st.columns(3)
            ec1.metric("Takeoffs (D/N)", f"{t_day} / {t_night}")
            ec2.metric("Landings (D/N)", f"{l_day} / {l_night}")
            ec3.metric("Approaches",     str(a_total))

            if log["comments"]:
                st.caption(f"💬 {log['comments']}")

            act1, act2 = st.columns(2)
            if act1.button("✏️ Edit",   key=f"edit_{log['id']}", use_container_width=True):
                _edit_dialog(log["id"])
            if act2.button("🗑️ Delete", key=f"del_{log['id']}", use_container_width=True):
                ok, msg = delete_flight_log(log["id"], user_id)
                if ok:
                    sheet_url = st.session_state.get("sheet_url", "")
                    if sheet_url:
                        h, m = divmod(log["duration_minutes"], 60)
                        delete_flight_from_gsheet(
                            sheet_url,
                            match={
                                "date":       log["date"],
                                "pilot_name": st.session_state.get("display_name", ""),
                                "duration":   f"{h}h {m:02d}m",
                            },
                        )
                    st.toast("✅ Flight deleted.")
                    st.rerun()
                else:
                    st.error(msg)
