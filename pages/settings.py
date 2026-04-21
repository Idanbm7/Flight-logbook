"""
pages/settings.py — App settings: connection, defaults, display, aircraft, GCS, sites.
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
# LocalStorage helper
# ---------------------------------------------------------------------------

def _local_storage():
    try:
        from streamlit_local_storage import LocalStorage
    except ImportError:
        import subprocess, sys
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "streamlit-local-storage"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        from streamlit_local_storage import LocalStorage
    return LocalStorage()


# ---------------------------------------------------------------------------
# Inline edit state helpers
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
# Tab: Connection
# ---------------------------------------------------------------------------

_APPS_SCRIPT_HELP = """
**Setup (one-time, no credentials needed):**

1. Open your Google Sheet → **Extensions → Apps Script**.
2. Delete any existing code and paste the script below, then click **Save**.
3. Click **Deploy → New deployment**, set:
   - Type: **Web app**
   - Execute as: **Me**
   - Who has access: **Anyone**
4. Click **Deploy**, approve permissions, and copy the **Web app URL**.
5. Paste that URL in the field below and click **Save Connection Settings**.

```js
function doPost(e) {
  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    var data  = JSON.parse(e.postData.contents);
    // Write header row if the sheet is empty
    if (sheet.getLastRow() === 0) {
      sheet.appendRow([
        "Date","Pilot_Name","Aircraft_Type","Role","Log_Type",
        "Instructor","Duration","Day_Events","Night_Events","Comments"
      ]);
    }
    sheet.appendRow([
      data.Date, data.Pilot_Name, data.Aircraft_Type, data.Role,
      data.Log_Type, data.Instructor, data.Duration,
      data.Day_Events, data.Night_Events, data.Comments
    ]);
    return ContentService
      .createTextOutput("OK")
      .setMimeType(ContentService.MimeType.TEXT);
  } catch(err) {
    return ContentService
      .createTextOutput("Error: " + err.message)
      .setMimeType(ContentService.MimeType.TEXT);
  }
}
```
"""


def _tab_connection(localS):
    st.subheader("Google Sheets Connection")
    with st.expander("Setup instructions", expanded=False):
        st.markdown(_APPS_SCRIPT_HELP)

    current_url = st.session_state.get("sheet_url", "")
    new_url = st.text_input(
        "Apps Script Web App URL",
        value=current_url,
        placeholder="https://script.google.com/macros/s/…/exec",
        key="cfg_url",
    )

    st.subheader("Primary Role")
    role_options = ["IP", "EP", "BOTH"]
    current_role = st.session_state.get("primary_role", "IP")
    if current_role not in role_options:
        current_role = "IP"
    new_role = st.selectbox("Role", role_options,
                            index=role_options.index(current_role), key="cfg_role")

    st.divider()
    if st.button("💾  Save Connection Settings", use_container_width=True, type="primary"):
        url_clean = new_url.strip()
        # Validate format only — no network call of any kind
        if url_clean and "script.google.com" not in url_clean:
            st.error("Please paste a Google Apps Script Web App URL "
                     "(starts with https://script.google.com/…).")
        else:
            # Write to session state first so the app works immediately
            st.session_state["sheet_url"]    = url_clean
            st.session_state["primary_role"] = new_role
            # Persist to local storage (best-effort — never crash on failure)
            try:
                localS.setItem("sheet_url",    url_clean)
                localS.setItem("primary_role", new_role)
            except Exception:
                pass
            st.toast("✅ Connection settings saved!")
            st.rerun()


# ---------------------------------------------------------------------------
# Tab: Defaults
# ---------------------------------------------------------------------------

def _tab_defaults(user_id: int, localS):
    st.subheader("Display Name")
    current_name = st.session_state.get("display_name", "")
    new_name = st.text_input(
        "Your name (shown in exports and Home summary)",
        value=current_name, placeholder="e.g. John Smith", key="cfg_name",
    )

    st.subheader("Preferred Aircraft")
    aircraft_list = get_aircraft(user_id)
    new_ac_id = ""
    if aircraft_list:
        ac_labels = ["(none)"] + [
            f"{a['model_type']} — {a['tail_number']}"
            + (f"  ({a['call_sign']})" if a["call_sign"] else "")
            for a in aircraft_list
        ]
        pref_id  = st.session_state.get("default_aircraft_id", "")
        pref_idx = 0
        for i, a in enumerate(aircraft_list, start=1):
            if str(a["id"]) == str(pref_id):
                pref_idx = i
                break
        sel_label = st.selectbox("Default aircraft (pre-selected in New Flight)",
                                 ac_labels, index=pref_idx, key="cfg_ac")
        if sel_label != "(none)":
            sel_ac    = aircraft_list[ac_labels.index(sel_label) - 1]
            new_ac_id = str(sel_ac["id"])
    else:
        st.info("No aircraft yet. Add one in the Aircraft tab.")

    st.divider()
    if st.button("💾  Save Defaults", use_container_width=True, type="primary"):
        localS.setItem("display_name",        new_name.strip())
        localS.setItem("default_aircraft_id", new_ac_id)
        st.session_state["display_name"]        = new_name.strip()
        st.session_state["default_aircraft_id"] = new_ac_id
        st.toast("✅ Defaults saved!")
        st.rerun()


# ---------------------------------------------------------------------------
# Tab: Display (Home page metric toggles)
# ---------------------------------------------------------------------------

_DISPLAY_PREFS = [
    ("show_total_flights",  "Total Flights"),
    ("show_total_hours",    "Total Hours"),
    ("show_last_flight",    "Last Flight Date"),
    ("show_pic_hours",      "PIC Hours"),
    ("show_sic_hours",      "SIC Hours"),
    ("show_instructor_hrs", "Instructor Hours"),
    ("show_day_events",     "Day Events (T/O + Landings)"),
    ("show_night_events",   "Night Events (T/O + Landings)"),
    ("show_approaches",     "Approaches"),
]


def _tab_display(user_id: int):
    st.subheader("Home Page Metrics")
    st.caption("Toggle which stat cards appear on the Home page.")

    prefs   = get_home_display_prefs(user_id)
    changed = False

    for key, label in _DISPLAY_PREFS:
        current = prefs.get(key, "1") == "1"
        new_val = st.checkbox(label, value=current, key=f"disp_{key}")
        if new_val != current:
            set_home_display_pref(user_id, key, "1" if new_val else "0")
            changed = True

    if changed:
        st.toast("✅ Display preferences saved!")
        st.rerun()


# ---------------------------------------------------------------------------
# Tab: Aircraft
# ---------------------------------------------------------------------------

def _tab_aircraft(user_id: int):
    st.subheader("✈️ Aircraft")

    aircraft_list = get_aircraft(user_id, active_only=False)
    active        = [a for a in aircraft_list if     a["is_active"]]
    retired       = [a for a in aircraft_list if not a["is_active"]]

    if not active:
        st.info("No active aircraft. Add one below.")

    for ac in active:
        cs_tag = f"  ({ac['call_sign']})" if ac["call_sign"] else ""
        label  = f"{ac['model_type']} — {ac['tail_number']}{cs_tag}"
        with st.expander(label):
            if _is_editing("ac", ac["id"]):
                new_model = st.text_input("Model / Type *",  value=ac["model_type"], key=f"ac_edit_model_{ac['id']}")
                new_tail  = st.text_input("Tail Number *",   value=ac["tail_number"], key=f"ac_edit_tail_{ac['id']}")
                new_cs    = st.text_input("Call Sign",       value=ac["call_sign"] or "", key=f"ac_edit_cs_{ac['id']}")
                b1, b2    = st.columns(2)
                if b1.button("💾 Save", key=f"ac_save_{ac['id']}", use_container_width=True):
                    ok, msg = update_aircraft(ac["id"], user_id, new_model, new_tail, new_cs)
                    if ok:
                        _stop_edit("ac", ac["id"])
                        st.toast("✅ Aircraft updated!")
                        st.rerun()
                    else:
                        st.error(msg)
                if b2.button("Cancel", key=f"ac_cancel_{ac['id']}", use_container_width=True):
                    _stop_edit("ac", ac["id"])
                    st.rerun()
            else:
                st.write(f"**Model/Type:** {ac['model_type']}")
                st.write(f"**Tail Number:** {ac['tail_number']}")
                st.write(f"**Call Sign:** {ac['call_sign'] or '—'}")
                has_fl = aircraft_has_flights(ac["id"])
                b1, b2, b3 = st.columns(3)
                if b1.button("✏️ Edit",   key=f"ac_edit_{ac['id']}", use_container_width=True):
                    _start_edit("ac", ac["id"]); st.rerun()
                if b2.button("🛑 Retire", key=f"ac_retire_{ac['id']}", use_container_width=True):
                    ok, msg = retire_aircraft(ac["id"], user_id)
                    if ok:
                        st.toast("✅ Retired.")
                        st.rerun()
                    else:
                        st.error(msg)
                if not has_fl:
                    if b3.button("🗑️ Delete", key=f"ac_del_{ac['id']}", use_container_width=True):
                        ok, msg = delete_aircraft(ac["id"], user_id)
                        if ok:
                            st.toast("✅ Deleted.")
                            st.rerun()
                        else:
                            st.error(msg)
                else:
                    b3.caption("Has logs —\nretire instead")

    if retired:
        with st.expander(f"Retired ({len(retired)})"):
            for ac in retired:
                st.write(f"~~{ac['model_type']} — {ac['tail_number']}~~")

    st.markdown("**Add New Aircraft**")
    with st.form("add_aircraft_form", clear_on_submit=True):
        nc1, nc2, nc3 = st.columns(3)
        model_type  = nc1.text_input("Model / Type *", placeholder="e.g. DJI Matrice 300")
        tail_number = nc2.text_input("Tail Number *",  placeholder="e.g. 4X-UAV1")
        call_sign   = nc3.text_input("Call Sign",      placeholder="e.g. ALPHA")
        if st.form_submit_button("Add Aircraft", use_container_width=True):
            ok, msg = add_aircraft(user_id, model_type, tail_number, call_sign)
            if ok:
                st.toast("✅ Aircraft added!")
                st.rerun()
            else:
                st.error(msg)


# ---------------------------------------------------------------------------
# Tab: GCS Types
# ---------------------------------------------------------------------------

def _tab_gcs(user_id: int):
    st.subheader("🎮 GCS Types")
    gcs_list = get_gcs_types(user_id)

    if not gcs_list:
        st.info("No GCS types saved yet. Add one below.")

    for g in gcs_list:
        with st.expander(g["name"]):
            if _is_editing("gcs", g["id"]):
                new_name = st.text_input("GCS Name *", value=g["name"], key=f"gcs_edit_{g['id']}")
                gb1, gb2 = st.columns(2)
                if gb1.button("💾 Save", key=f"gcs_save_{g['id']}", use_container_width=True):
                    ok, msg = update_gcs_type(g["id"], user_id, new_name)
                    if ok:
                        _stop_edit("gcs", g["id"])
                        st.toast("✅ Updated!")
                        st.rerun()
                    else:
                        st.error(msg)
                if gb2.button("Cancel", key=f"gcs_cancel_{g['id']}", use_container_width=True):
                    _stop_edit("gcs", g["id"]); st.rerun()
            else:
                gc1, gc2 = st.columns(2)
                if gc1.button("✏️ Edit",   key=f"gcs_edit_{g['id']}", use_container_width=True):
                    _start_edit("gcs", g["id"]); st.rerun()
                if gc2.button("🗑️ Delete", key=f"gcs_del_{g['id']}", use_container_width=True):
                    ok, msg = delete_gcs_type(g["id"], user_id)
                    if ok:
                        st.toast("✅ Deleted.")
                        st.rerun()
                    else:
                        st.error(msg)

    st.markdown("**Add New GCS Type**")
    with st.form("add_gcs_form", clear_on_submit=True):
        gcs_name = st.text_input("GCS Type Name *", placeholder="e.g. DJI Smart Controller")
        if st.form_submit_button("Add GCS Type", use_container_width=True):
            ok, msg = add_gcs_type(user_id, gcs_name)
            if ok:
                st.toast("✅ GCS type added!")
                st.rerun()
            else:
                st.error(msg)


# ---------------------------------------------------------------------------
# Tab: Sites
# ---------------------------------------------------------------------------

def _tab_sites(user_id: int):
    st.subheader("📍 Sites / Locations")
    sites = get_sites(user_id)

    if not sites:
        st.info("No sites saved yet. Add one below.")

    for s in sites:
        with st.expander(s["name"]):
            if _is_editing("site", s["id"]):
                new_name = st.text_input("Site Name *", value=s["name"], key=f"site_edit_{s['id']}")
                sb1, sb2 = st.columns(2)
                if sb1.button("💾 Save", key=f"site_save_{s['id']}", use_container_width=True):
                    ok, msg = update_site(s["id"], user_id, new_name)
                    if ok:
                        _stop_edit("site", s["id"])
                        st.toast("✅ Updated!")
                        st.rerun()
                    else:
                        st.error(msg)
                if sb2.button("Cancel", key=f"site_cancel_{s['id']}", use_container_width=True):
                    _stop_edit("site", s["id"]); st.rerun()
            else:
                sc1, sc2 = st.columns(2)
                if sc1.button("✏️ Edit", key=f"site_edit_{s['id']}", use_container_width=True):
                    _start_edit("site", s["id"]); st.rerun()
                has_fl = site_has_flights(s["id"])
                if not has_fl:
                    if sc2.button("🗑️ Delete", key=f"site_del_{s['id']}", use_container_width=True):
                        ok, msg = delete_site(s["id"], user_id)
                        if ok:
                            st.toast("✅ Deleted.")
                            st.rerun()
                        else:
                            st.error(msg)
                else:
                    sc2.caption("Has logs —\ncannot delete")

    st.markdown("**Add New Site**")
    with st.form("add_site_form", clear_on_submit=True):
        site_name = st.text_input("Site Name *", placeholder="e.g. Haifa Industrial Zone")
        if st.form_submit_button("Add Site", use_container_width=True):
            ok, msg = add_site(user_id, site_name)
            if ok:
                st.toast("✅ Site added!")
                st.rerun()
            else:
                st.error(msg)


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------

def render():
    if st.button("← Home", key="settings_back"):
        st.session_state.page = "home"
        st.rerun()

    st.header("⚙️ Settings")

    user_id = st.session_state.user["id"]
    localS  = _local_storage()

    tab_conn, tab_def, tab_disp, tab_ac, tab_gcs, tab_sites = st.tabs(
        ["🔗 Connection", "👤 Defaults", "🖥️ Display",
         "✈️ Aircraft",   "🎮 GCS Types", "📍 Sites"]
    )

    with tab_conn:  _tab_connection(localS)
    with tab_def:   _tab_defaults(user_id, localS)
    with tab_disp:  _tab_display(user_id)
    with tab_ac:    _tab_aircraft(user_id)
    with tab_gcs:   _tab_gcs(user_id)
    with tab_sites: _tab_sites(user_id)
