"""
utils.py — Shared helpers: time formatting, event aggregation, export utilities.
"""

import os
from datetime import datetime


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MISSION_PURPOSES = ["Training", "Demo", "Operational", "Experimental", "Other"]
CREW_ROLES = ["PIC", "SIC"]
EVENT_TYPES = ["Takeoff", "Landing", "Approach"]
PERIODS = ["Day", "Night"]
METHODS = ["Manual", "Automatic"]


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def format_date_eu(date_str: str) -> str:
    """Convert YYYY-MM-DD to DD/MM/YYYY for display."""
    try:
        from datetime import date as _date
        return _date.fromisoformat(str(date_str)).strftime("%d/%m/%Y")
    except Exception:
        return str(date_str) if date_str else "—"


def minutes_to_hhmm(minutes: int) -> str:
    """90 → '1:30'"""
    if minutes < 0:
        return "0:00"
    h, m = divmod(int(minutes), 60)
    return f"{h}:{m:02d}"


def minutes_to_decimal_hours(minutes: int, decimals: int = 1) -> float:
    return round(minutes / 60, decimals)


# ---------------------------------------------------------------------------
# Event row ↔ 12-column helpers
# ---------------------------------------------------------------------------

_TYPE_MAP   = {"Takeoff": "takeoffs",  "Landing": "landings",  "Approach": "approaches"}
_PERIOD_MAP = {"Day": "day",           "Night": "night"}
_METHOD_MAP = {"Manual": "manual",     "Automatic": "auto"}

_INV_TYPE   = {v: k for k, v in _TYPE_MAP.items()}
_INV_PERIOD = {v: k for k, v in _PERIOD_MAP.items()}
_INV_METHOD = {v: k for k, v in _METHOD_MAP.items()}


def aggregate_event_rows(rows: list[dict]) -> dict:
    """
    Convert a list of dynamic event row dicts into the 12 flat DB columns.
    Each row: {"type": "Takeoff", "period": "Day", "qty": 2, "method": "Manual"}
    """
    result = {
        "takeoffs_day_manual": 0,  "takeoffs_day_auto": 0,
        "takeoffs_night_manual": 0,"takeoffs_night_auto": 0,
        "landings_day_manual": 0,  "landings_day_auto": 0,
        "landings_night_manual": 0,"landings_night_auto": 0,
        "approaches_day_manual": 0,"approaches_day_auto": 0,
        "approaches_night_manual":0,"approaches_night_auto": 0,
    }
    for row in rows:
        evt = _TYPE_MAP.get(row.get("type", ""), "takeoffs")
        per = _PERIOD_MAP.get(row.get("period", "Day"), "day")
        mth = _METHOD_MAP.get(row.get("method", "Manual"), "manual")
        key = f"{evt}_{per}_{mth}"
        result[key] = result.get(key, 0) + max(0, int(row.get("qty", 1)))
    return result


def flight_log_to_event_rows(log: dict) -> list[dict]:
    """
    Convert a flight log's 12 flat event columns back into a list of event row dicts
    (only rows with qty > 0 are included).
    """
    combos = [
        ("takeoffs",  "day",   "manual"),
        ("takeoffs",  "day",   "auto"),
        ("takeoffs",  "night", "manual"),
        ("takeoffs",  "night", "auto"),
        ("landings",  "day",   "manual"),
        ("landings",  "day",   "auto"),
        ("landings",  "night", "manual"),
        ("landings",  "night", "auto"),
        ("approaches","day",   "manual"),
        ("approaches","day",   "auto"),
        ("approaches","night", "manual"),
        ("approaches","night", "auto"),
    ]
    rows = []
    for evt, per, mth in combos:
        qty = int(log.get(f"{evt}_{per}_{mth}", 0) or 0)
        if qty > 0:
            rows.append({
                "type":   _INV_TYPE.get(evt, "Takeoff"),
                "period": _INV_PERIOD.get(per, "Day"),
                "qty":    qty,
                "method": _INV_METHOD.get(mth, "Manual"),
            })
    return rows


# ---------------------------------------------------------------------------
# Stats display
# ---------------------------------------------------------------------------

def format_stats_for_display(stats: dict) -> dict:
    return {
        "Total Flights":    str(stats.get("total_flights", 0)),
        "Total Flight Time":minutes_to_hhmm(stats.get("total_minutes", 0)) + " hrs",
        "PIC Time":         minutes_to_hhmm(stats.get("pic_minutes", 0)) + " hrs",
        "SIC Time":         minutes_to_hhmm(stats.get("sic_minutes", 0)) + " hrs",
        "Instructor Time":  minutes_to_hhmm(stats.get("instructor_minutes", 0)) + " hrs",
        "Day Takeoffs":     str(stats.get("total_day_takeoffs", 0)),
        "Night Takeoffs":   str(stats.get("total_night_takeoffs", 0)),
        "Day Landings":     str(stats.get("total_day_landings", 0)),
        "Night Landings":   str(stats.get("total_night_landings", 0)),
        "Total Approaches": str(stats.get("total_approaches", 0)),
        "Aircraft Flown":   str(stats.get("unique_aircraft", 0)),
        "First Flight":     stats.get("first_flight_date", "—") or "—",
        "Last Flight":      stats.get("last_flight_date", "—") or "—",
    }


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def flight_logs_to_dataframe(logs: list[dict]):
    import pandas as pd
    if not logs:
        return pd.DataFrame()
    column_map = {
        "id": "Log ID", "date": "Date", "start_time": "Start", "end_time": "End",
        "duration_minutes": "Duration (min)", "model_type": "Aircraft Model",
        "tail_number": "Tail #", "call_sign": "Call Sign", "location_name": "Location",
        "mission_purpose": "Mission", "gcs_type": "GCS", "crew_role": "Role",
        "is_instructor": "Instructor",
        "takeoffs_day_manual": "T/O Day Manual", "takeoffs_day_auto": "T/O Day Auto",
        "takeoffs_night_manual": "T/O Night Manual", "takeoffs_night_auto": "T/O Night Auto",
        "landings_day_manual": "Ldg Day Manual", "landings_day_auto": "Ldg Day Auto",
        "landings_night_manual": "Ldg Night Manual", "landings_night_auto": "Ldg Night Auto",
        "approaches_day_manual": "App Day Manual", "approaches_day_auto": "App Day Auto",
        "approaches_night_manual": "App Night Manual", "approaches_night_auto": "App Night Auto",
        "comments": "Comments",
    }
    df = pd.DataFrame(logs)
    existing = [c for c in column_map if c in df.columns]
    df = df[existing].rename(columns=column_map)
    if "Instructor" in df.columns:
        df["Instructor"] = df["Instructor"].map({1: "Yes", 0: "No"})
    return df


def export_to_excel(logs: list[dict], filepath: str) -> tuple[bool, str]:
    try:
        import pandas as pd
        df = flight_logs_to_dataframe(logs)
        df.to_excel(filepath, index=False, engine="openpyxl")
        return True, f"Exported to {filepath}"
    except ImportError:
        return False, "openpyxl is not installed. Run: pip install openpyxl"
    except Exception as e:
        return False, f"Export failed: {e}"


def _safe_str(value, max_len: int = 0) -> str:
    """Convert to string, optionally truncate; strip non-Latin-1 for Helvetica fallback."""
    s = str(value) if value is not None else ""
    if max_len:
        s = s[:max_len]
    return s.encode("latin-1", errors="replace").decode("latin-1")


def _find_unicode_font() -> tuple[str, str]:
    """Return (regular_path, bold_path) for Arial TTF, or ('', '') if not found."""
    candidates = [
        (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
        ("/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
         "/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf"),
    ]
    for reg, bold in candidates:
        if os.path.isfile(reg):
            return reg, bold if os.path.isfile(bold) else reg
    return "", ""


def export_to_pdf(
    logs: list[dict],
    filepath: str,
    username: str = "",
    date_from: str = None,
    date_to: str = None,
) -> tuple[bool, str]:
    """
    Export flight logs to a landscape A4 PDF table.
    Uses Arial Unicode TTF (supports Hebrew/RTL) when available; falls back to Helvetica.
    date_from / date_to are YYYY-MM-DD strings shown in the report header.
    """
    try:
        from fpdf import FPDF
        from fpdf.enums import XPos, YPos

        font_path, bold_path = _find_unicode_font()
        use_unicode = bool(font_path)

        pdf = FPDF(orientation="L", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=15)

        if use_unicode:
            pdf.add_font("Arial", "",  font_path)
            pdf.add_font("Arial", "B", bold_path)

        FONT = "Arial" if use_unicode else "Helvetica"

        # RTL (bidi) support — python-bidi reverses Hebrew/Arabic for correct PDF display
        try:
            from bidi.algorithm import get_display as _bidi_fn
        except ImportError:
            _bidi_fn = None

        def _s(value, max_len: int = 0) -> str:
            s = str(value) if value is not None else ""
            if max_len:
                s = s[:max_len]
            if not use_unicode:
                return s.encode("latin-1", errors="replace").decode("latin-1")
            return _bidi_fn(s) if _bidi_fn else s

        def _align(value) -> str:
            """Return 'R' if the raw value contains Hebrew or Arabic characters."""
            if not use_unicode or not _bidi_fn:
                return "L"
            s = str(value) if value is not None else ""
            return "R" if any(
                "\u0590" <= c <= "\u05FF" or "\u0600" <= c <= "\u06FF" for c in s
            ) else "L"

        pdf.add_page()

        # ---- Title block ----
        pdf.set_font(FONT, "B", 14)
        pdf.cell(0, 10, _s(f"Flight Logbook — {username}" if username else "Flight Logbook"),
                 align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font(FONT, "", 9)
        pdf.cell(0, 6, _s(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"),
                 align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        if date_from or date_to:
            pdf.cell(0, 6, _s(f"Period: {date_from or '—'} → {date_to or '—'}"),
                     align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.ln(4)

        # ---- Column definitions: (header label, width mm) ----
        headers = [
            ("Date", 22), ("Start", 13), ("End", 13), ("Min", 11),
            ("Aircraft", 34), ("Tail #", 19), ("Location", 34),
            ("Mission", 22), ("Role", 10), ("Instr.", 11), ("Comments", 48),
        ]

        # ---- Header row ----
        pdf.set_fill_color(30, 30, 30)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font(FONT, "B", 8)
        for i, (label, w) in enumerate(headers):
            last = i == len(headers) - 1
            pdf.cell(w, 7, label, border=1, align="C", fill=True,
                     new_x=(XPos.LMARGIN if last else XPos.RIGHT),
                     new_y=(YPos.NEXT    if last else YPos.TOP))

        # ---- Data rows ----
        pdf.set_text_color(0, 0, 0)
        pdf.set_font(FONT, "", 8)
        fill = False

        # max truncation lengths per column (0 = no limit)
        _max_lens = [0, 0, 0, 0, 22, 12, 22, 14, 0, 0, 32]

        for log in logs:
            pdf.set_fill_color(238, 238, 238) if fill else pdf.set_fill_color(255, 255, 255)
            raw_vals = [
                log.get("date", ""),
                log.get("start_time", ""),
                log.get("end_time", ""),
                log.get("duration_minutes", ""),
                log.get("model_type", ""),
                log.get("tail_number", ""),
                log.get("location_name", ""),
                log.get("mission_purpose", ""),
                log.get("crew_role", ""),
                "Yes" if log.get("is_instructor") else "No",
                log.get("comments", "") or "",
            ]
            for i, (raw, ml, (_, w)) in enumerate(zip(raw_vals, _max_lens, headers)):
                val  = _s(raw, ml)
                alg  = _align(raw)
                last = i == len(headers) - 1
                pdf.cell(w, 6, val, border=1, fill=fill, align=alg,
                         new_x=(XPos.LMARGIN if last else XPos.RIGHT),
                         new_y=(YPos.NEXT    if last else YPos.TOP))
            fill = not fill

        pdf.output(filepath)
        return True, f"PDF saved to {filepath}"

    except ImportError:
        return False, "fpdf2 is not installed. Run: pip install fpdf2"
    except Exception as e:
        return False, f"PDF export failed: {e}"
