"""
pages/dashboard.py — Personal flight statistics and summary charts.
All chart rendering is wrapped in try/except so pandas/altair errors stay silent.
"""

import streamlit as st
from database import get_user_stats, get_monthly_hours
from utils import format_stats_for_display, minutes_to_decimal_hours


def render():
    st.header("📊 Dashboard")

    user_id = st.session_state.user["id"]

    try:
        stats = get_user_stats(user_id) or {}
    except Exception:
        stats = {}

    if not stats or int(stats.get("total_flights") or 0) == 0:
        st.info("No flights logged yet. Your dashboard will populate once you start logging flights.")
        return

    try:
        display = format_stats_for_display(stats)
    except Exception:
        st.warning("Could not format statistics.")
        return

    # ---- Overview KPIs ----
    st.subheader("Overview")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Flights",     display.get("Total Flights", "0"))
    k2.metric("Total Flight Time",  display.get("Total Flight Time", "0:00 hrs"))
    k3.metric("Aircraft Flown",    display.get("Aircraft Flown", "0"))
    k4.metric(
        "First → Last",
        f"{display.get('First Flight','—')} → {display.get('Last Flight','—')}",
    )

    st.divider()

    # ---- Role breakdown ----
    st.subheader("Time by Role")
    r1, r2, r3 = st.columns(3)
    r1.metric("PIC Time",        display.get("PIC Time", "0:00 hrs"))
    r2.metric("SIC Time",        display.get("SIC Time", "0:00 hrs"))
    r3.metric("Instructor Time", display.get("Instructor Time", "0:00 hrs"))

    try:
        import pandas as pd
        pic_hrs  = minutes_to_decimal_hours(int(stats.get("pic_minutes")  or 0))
        sic_hrs  = minutes_to_decimal_hours(int(stats.get("sic_minutes")  or 0))
        inst_hrs = minutes_to_decimal_hours(int(stats.get("instructor_minutes") or 0))
        role_df  = pd.DataFrame({
            "Role":  ["PIC", "SIC", "Instructor"],
            "Hours": [pic_hrs, sic_hrs, inst_hrs],
        })
        role_df = role_df[role_df["Hours"] > 0].copy()
        if not role_df.empty:
            st.bar_chart(role_df.set_index("Role")["Hours"])
    except Exception:
        pass   # chart is optional — never show a traceback here

    st.divider()

    # ---- Day / Night events ----
    st.subheader("Day vs. Night Events")
    ev1, ev2, ev3 = st.columns(3)
    ev1.metric("Day Takeoffs",     display.get("Day Takeoffs", "0"))
    ev2.metric("Night Takeoffs",   display.get("Night Takeoffs", "0"))
    ev3.metric("Total Approaches", display.get("Total Approaches", "0"))

    ev4, ev5 = st.columns(2)
    ev4.metric("Day Landings",   display.get("Day Landings", "0"))
    ev5.metric("Night Landings", display.get("Night Landings", "0"))

    st.divider()

    # ---- Monthly trend ----
    st.subheader("Monthly Flight Hours")
    try:
        monthly = get_monthly_hours(user_id) or []
    except Exception:
        monthly = []

    if monthly:
        try:
            import pandas as pd
            df = pd.DataFrame(monthly)
            df["Hours"] = df["total_minutes"].apply(
                lambda m: minutes_to_decimal_hours(int(m or 0), 1)
            )
            df = df.rename(columns={"month": "Month"}).set_index("Month")
            st.bar_chart(df["Hours"])
        except Exception:
            # Fallback: plain text list
            for row in monthly:
                try:
                    hrs = minutes_to_decimal_hours(int(row.get("total_minutes") or 0))
                    st.write(f"{row.get('month','?')}: {hrs} hrs")
                except Exception:
                    pass
    else:
        st.caption("No monthly data to display yet.")
