"""
database.py — SQLite schema, connection management, and all CRUD helpers.
"""

import sqlite3
import hashlib
import os
from datetime import datetime
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "logbook.db")


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create data directory and all tables if they don't already exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                username        TEXT    UNIQUE NOT NULL,
                password_hash   TEXT    NOT NULL,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS aircraft (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                model_type  TEXT    NOT NULL,
                tail_number TEXT    NOT NULL,
                call_sign   TEXT,
                is_active   INTEGER DEFAULT 1,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS sites (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                name        TEXT    NOT NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS gcs_types (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                name        TEXT    NOT NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id    INTEGER NOT NULL,
                pref_key   TEXT    NOT NULL,
                pref_value TEXT    NOT NULL DEFAULT '1',
                PRIMARY KEY (user_id, pref_key),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS flight_logs (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id                 INTEGER NOT NULL,
                aircraft_id             INTEGER NOT NULL,
                site_id                 INTEGER,
                site_custom             TEXT,
                date                    TEXT    NOT NULL,
                start_time              TEXT    NOT NULL,
                end_time                TEXT    NOT NULL,
                duration_minutes        INTEGER NOT NULL,
                mission_purpose         TEXT    NOT NULL,
                gcs_type                TEXT,
                crew_role               TEXT    NOT NULL,
                is_instructor           INTEGER DEFAULT 0,
                takeoffs_day_manual     INTEGER DEFAULT 0,
                takeoffs_day_auto       INTEGER DEFAULT 0,
                takeoffs_night_manual   INTEGER DEFAULT 0,
                takeoffs_night_auto     INTEGER DEFAULT 0,
                landings_day_manual     INTEGER DEFAULT 0,
                landings_day_auto       INTEGER DEFAULT 0,
                landings_night_manual   INTEGER DEFAULT 0,
                landings_night_auto     INTEGER DEFAULT 0,
                approaches_day_manual   INTEGER DEFAULT 0,
                approaches_day_auto     INTEGER DEFAULT 0,
                approaches_night_manual INTEGER DEFAULT 0,
                approaches_night_auto   INTEGER DEFAULT 0,
                comments                TEXT,
                created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id)     REFERENCES users(id),
                FOREIGN KEY (aircraft_id) REFERENCES aircraft(id),
                FOREIGN KEY (site_id)     REFERENCES sites(id)
            );
        """)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def register_user(username: str, password: str) -> tuple[bool, str]:
    if not username.strip() or not password.strip():
        return False, "Username and password are required."
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username.strip(), _hash_password(password)),
            )
        return True, "Account created successfully."
    except sqlite3.IntegrityError:
        return False, "Username already exists. Please choose another."
    except Exception as e:
        return False, f"Unexpected error: {e}"


def authenticate_user(username: str, password: str) -> Optional[dict]:
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ? AND password_hash = ?",
                (username.strip(), _hash_password(password)),
            ).fetchone()
        return dict(row) if row else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Aircraft CRUD
# ---------------------------------------------------------------------------

def add_aircraft(user_id: int, model_type: str, tail_number: str = "",
                 call_sign: str = "") -> tuple[bool, str]:
    if not model_type.strip():
        return False, "Model/Type is required."
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO aircraft (user_id, model_type, tail_number, call_sign) VALUES (?, ?, ?, ?)",
                (user_id, model_type.strip(), tail_number.strip(), call_sign.strip()),
            )
        return True, "Aircraft added."
    except Exception as e:
        return False, f"Error adding aircraft: {e}"


def get_aircraft(user_id: int, active_only: bool = True) -> list[dict]:
    try:
        with get_connection() as conn:
            query = "SELECT * FROM aircraft WHERE user_id = ?"
            params: list = [user_id]
            if active_only:
                query += " AND is_active = 1"
            query += " ORDER BY model_type"
            rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_aircraft_display_list(user_id: int) -> list[dict]:
    """Return active aircraft deduplicated by (model_type, tail_number, call_sign).
    Uses MIN(id) so a representative DB record is always returned."""
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT MIN(id) AS id,
                          model_type,
                          tail_number,
                          COALESCE(call_sign, '') AS call_sign
                   FROM aircraft
                   WHERE user_id = ? AND is_active = 1
                   GROUP BY model_type, tail_number, COALESCE(call_sign, '')
                   ORDER BY model_type""",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def update_aircraft(aircraft_id: int, user_id: int, model_type: str,
                    tail_number: str, call_sign: str = "") -> tuple[bool, str]:
    if not model_type.strip() or not tail_number.strip():
        return False, "Model/Type and Tail Number are required."
    try:
        with get_connection() as conn:
            conn.execute(
                """UPDATE aircraft SET model_type=?, tail_number=?, call_sign=?
                   WHERE id=? AND user_id=?""",
                (model_type.strip(), tail_number.strip(), call_sign.strip(),
                 aircraft_id, user_id),
            )
        return True, "Aircraft updated."
    except Exception as e:
        return False, f"Error updating aircraft: {e}"


def retire_aircraft(aircraft_id: int, user_id: int) -> tuple[bool, str]:
    try:
        with get_connection() as conn:
            conn.execute(
                "UPDATE aircraft SET is_active = 0 WHERE id = ? AND user_id = ?",
                (aircraft_id, user_id),
            )
        return True, "Aircraft retired."
    except Exception as e:
        return False, f"Error retiring aircraft: {e}"


def aircraft_has_flights(aircraft_id: int) -> bool:
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM flight_logs WHERE aircraft_id = ?",
                (aircraft_id,),
            ).fetchone()
        return row["cnt"] > 0
    except Exception:
        return True  # safe default


def delete_aircraft(aircraft_id: int, user_id: int) -> tuple[bool, str]:
    """Hard-delete only when no associated flight logs exist."""
    if aircraft_has_flights(aircraft_id):
        return False, "Aircraft has flight logs — use Retire instead of Delete."
    try:
        with get_connection() as conn:
            conn.execute(
                "DELETE FROM aircraft WHERE id = ? AND user_id = ?",
                (aircraft_id, user_id),
            )
        return True, "Aircraft deleted."
    except Exception as e:
        return False, f"Error deleting aircraft: {e}"


# ---------------------------------------------------------------------------
# Sites CRUD
# ---------------------------------------------------------------------------

def add_site(user_id: int, name: str) -> tuple[bool, str]:
    if not name.strip():
        return False, "Site name is required."
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO sites (user_id, name) VALUES (?, ?)",
                (user_id, name.strip()),
            )
        return True, "Site added."
    except Exception as e:
        return False, f"Error adding site: {e}"


def get_sites(user_id: int) -> list[dict]:
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM sites WHERE user_id = ? ORDER BY name",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def update_site(site_id: int, user_id: int, name: str) -> tuple[bool, str]:
    if not name.strip():
        return False, "Site name is required."
    try:
        with get_connection() as conn:
            conn.execute(
                "UPDATE sites SET name = ? WHERE id = ? AND user_id = ?",
                (name.strip(), site_id, user_id),
            )
        return True, "Site updated."
    except Exception as e:
        return False, f"Error updating site: {e}"


def site_has_flights(site_id: int) -> bool:
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM flight_logs WHERE site_id = ?",
                (site_id,),
            ).fetchone()
        return row["cnt"] > 0
    except Exception:
        return True


def delete_site(site_id: int, user_id: int) -> tuple[bool, str]:
    if site_has_flights(site_id):
        return False, "Site has associated flight logs and cannot be deleted."
    try:
        with get_connection() as conn:
            conn.execute(
                "DELETE FROM sites WHERE id = ? AND user_id = ?",
                (site_id, user_id),
            )
        return True, "Site removed."
    except Exception as e:
        return False, f"Error removing site: {e}"


def get_custom_site_suggestions(user_id: int) -> list[str]:
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT DISTINCT site_custom FROM flight_logs
                   WHERE user_id = ? AND site_custom IS NOT NULL AND site_custom != ''
                   ORDER BY site_custom""",
                (user_id,),
            ).fetchall()
        return [r["site_custom"] for r in rows]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# GCS Types CRUD
# ---------------------------------------------------------------------------

def add_gcs_type(user_id: int, name: str) -> tuple[bool, str]:
    if not name.strip():
        return False, "GCS type name is required."
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO gcs_types (user_id, name) VALUES (?, ?)",
                (user_id, name.strip()),
            )
        return True, "GCS type added."
    except Exception as e:
        return False, f"Error adding GCS type: {e}"


def get_gcs_types(user_id: int) -> list[dict]:
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM gcs_types WHERE user_id = ? ORDER BY name",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def update_gcs_type(gcs_id: int, user_id: int, name: str) -> tuple[bool, str]:
    if not name.strip():
        return False, "GCS type name is required."
    try:
        with get_connection() as conn:
            conn.execute(
                "UPDATE gcs_types SET name = ? WHERE id = ? AND user_id = ?",
                (name.strip(), gcs_id, user_id),
            )
        return True, "GCS type updated."
    except Exception as e:
        return False, f"Error updating GCS type: {e}"


def delete_gcs_type(gcs_id: int, user_id: int) -> tuple[bool, str]:
    try:
        with get_connection() as conn:
            conn.execute(
                "DELETE FROM gcs_types WHERE id = ? AND user_id = ?",
                (gcs_id, user_id),
            )
        return True, "GCS type deleted."
    except Exception as e:
        return False, f"Error deleting GCS type: {e}"


# ---------------------------------------------------------------------------
# Flight Log CRUD
# ---------------------------------------------------------------------------

def _validate_flight_fields(date: str, start_time: str, end_time: str,
                             mission_purpose: str, crew_role: str
                             ) -> tuple[bool, int, str]:
    """Shared validation for add and update. Returns (ok, duration_minutes, error)."""
    if not date or not start_time or not end_time:
        return False, 0, "Date, start time, and end time are required."
    if not mission_purpose:
        return False, 0, "Mission purpose is required."
    if crew_role not in ("PIC", "SIC"):
        return False, 0, "Crew role must be PIC or SIC."
    try:
        start_dt = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
        end_dt   = datetime.strptime(f"{date} {end_time}",   "%Y-%m-%d %H:%M")
        if end_dt <= start_dt:
            return False, 0, "End time must be after start time."
        return True, int((end_dt - start_dt).total_seconds() / 60), ""
    except ValueError:
        return False, 0, "Invalid date or time format."


def add_flight_log(
    user_id: int, aircraft_id: int,
    date: str, start_time: str, end_time: str,
    mission_purpose: str, crew_role: str, is_instructor: bool,
    gcs_type: str = "", site_id: Optional[int] = None, site_custom: str = "",
    takeoffs_day_manual: int = 0, takeoffs_day_auto: int = 0,
    takeoffs_night_manual: int = 0, takeoffs_night_auto: int = 0,
    landings_day_manual: int = 0, landings_day_auto: int = 0,
    landings_night_manual: int = 0, landings_night_auto: int = 0,
    approaches_day_manual: int = 0, approaches_day_auto: int = 0,
    approaches_night_manual: int = 0, approaches_night_auto: int = 0,
    comments: str = "",
) -> tuple[bool, str]:
    ok, duration, err = _validate_flight_fields(date, start_time, end_time,
                                                mission_purpose, crew_role)
    if not ok:
        return False, err
    if site_custom.strip():
        site_id = None
    try:
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO flight_logs (
                    user_id, aircraft_id, site_id, site_custom,
                    date, start_time, end_time, duration_minutes,
                    mission_purpose, gcs_type, crew_role, is_instructor,
                    takeoffs_day_manual, takeoffs_day_auto,
                    takeoffs_night_manual, takeoffs_night_auto,
                    landings_day_manual, landings_day_auto,
                    landings_night_manual, landings_night_auto,
                    approaches_day_manual, approaches_day_auto,
                    approaches_night_manual, approaches_night_auto,
                    comments
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    user_id, aircraft_id, site_id, site_custom.strip() or None,
                    date, start_time, end_time, duration,
                    mission_purpose, gcs_type.strip(), crew_role, int(is_instructor),
                    takeoffs_day_manual, takeoffs_day_auto,
                    takeoffs_night_manual, takeoffs_night_auto,
                    landings_day_manual, landings_day_auto,
                    landings_night_manual, landings_night_auto,
                    approaches_day_manual, approaches_day_auto,
                    approaches_night_manual, approaches_night_auto,
                    comments.strip() or None,
                ),
            )
        return True, "Flight logged successfully."
    except Exception as e:
        return False, f"Error saving flight log: {e}"


def update_flight_log(
    log_id: int, user_id: int, aircraft_id: int,
    date: str, start_time: str, end_time: str,
    mission_purpose: str, crew_role: str, is_instructor: bool,
    gcs_type: str = "", site_id: Optional[int] = None, site_custom: str = "",
    takeoffs_day_manual: int = 0, takeoffs_day_auto: int = 0,
    takeoffs_night_manual: int = 0, takeoffs_night_auto: int = 0,
    landings_day_manual: int = 0, landings_day_auto: int = 0,
    landings_night_manual: int = 0, landings_night_auto: int = 0,
    approaches_day_manual: int = 0, approaches_day_auto: int = 0,
    approaches_night_manual: int = 0, approaches_night_auto: int = 0,
    comments: str = "",
) -> tuple[bool, str]:
    ok, duration, err = _validate_flight_fields(date, start_time, end_time,
                                                mission_purpose, crew_role)
    if not ok:
        return False, err
    if site_custom.strip():
        site_id = None
    try:
        with get_connection() as conn:
            conn.execute(
                """UPDATE flight_logs SET
                    aircraft_id=?, site_id=?, site_custom=?,
                    date=?, start_time=?, end_time=?, duration_minutes=?,
                    mission_purpose=?, gcs_type=?, crew_role=?, is_instructor=?,
                    takeoffs_day_manual=?, takeoffs_day_auto=?,
                    takeoffs_night_manual=?, takeoffs_night_auto=?,
                    landings_day_manual=?, landings_day_auto=?,
                    landings_night_manual=?, landings_night_auto=?,
                    approaches_day_manual=?, approaches_day_auto=?,
                    approaches_night_manual=?, approaches_night_auto=?,
                    comments=?
                WHERE id=? AND user_id=?""",
                (
                    aircraft_id, site_id, site_custom.strip() or None,
                    date, start_time, end_time, duration,
                    mission_purpose, gcs_type.strip(), crew_role, int(is_instructor),
                    takeoffs_day_manual, takeoffs_day_auto,
                    takeoffs_night_manual, takeoffs_night_auto,
                    landings_day_manual, landings_day_auto,
                    landings_night_manual, landings_night_auto,
                    approaches_day_manual, approaches_day_auto,
                    approaches_night_manual, approaches_night_auto,
                    comments.strip() or None,
                    log_id, user_id,
                ),
            )
        return True, "Flight log updated."
    except Exception as e:
        return False, f"Error updating flight log: {e}"


def get_flight_logs(user_id: int, limit: int = 200) -> list[dict]:
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT fl.*,
                          a.model_type, a.tail_number, a.call_sign,
                          COALESCE(s.name, fl.site_custom, 'N/A') AS location_name
                   FROM flight_logs fl
                   JOIN aircraft a ON fl.aircraft_id = a.id
                   LEFT JOIN sites s ON fl.site_id = s.id
                   WHERE fl.user_id = ?
                   ORDER BY fl.date DESC, fl.start_time DESC
                   LIMIT ?""",
                (user_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_flight_log_by_id(log_id: int, user_id: int) -> Optional[dict]:
    try:
        with get_connection() as conn:
            row = conn.execute(
                """SELECT fl.*,
                          a.model_type, a.tail_number, a.call_sign,
                          COALESCE(s.name, fl.site_custom, 'N/A') AS location_name
                   FROM flight_logs fl
                   JOIN aircraft a ON fl.aircraft_id = a.id
                   LEFT JOIN sites s ON fl.site_id = s.id
                   WHERE fl.id = ? AND fl.user_id = ?""",
                (log_id, user_id),
            ).fetchone()
        return dict(row) if row else None
    except Exception:
        return None


def get_recent_flights(user_id: int, limit: int = 5) -> list[dict]:
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT fl.*,
                          a.model_type, a.tail_number,
                          COALESCE(s.name, fl.site_custom, 'N/A') AS location_name
                   FROM flight_logs fl
                   JOIN aircraft a ON fl.aircraft_id = a.id
                   LEFT JOIN sites s ON fl.site_id = s.id
                   WHERE fl.user_id = ?
                   ORDER BY fl.date DESC, fl.start_time DESC, fl.id DESC
                   LIMIT ?""",
                (user_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def delete_flight_log(log_id: int, user_id: int) -> tuple[bool, str]:
    try:
        with get_connection() as conn:
            conn.execute(
                "DELETE FROM flight_logs WHERE id = ? AND user_id = ?",
                (log_id, user_id),
            )
        return True, "Flight log deleted."
    except Exception as e:
        return False, f"Error deleting flight log: {e}"


# ---------------------------------------------------------------------------
# Dashboard stats
# ---------------------------------------------------------------------------

def get_user_stats(user_id: int) -> dict:
    try:
        with get_connection() as conn:
            row = conn.execute(
                """SELECT
                    COUNT(*)                                             AS total_flights,
                    COALESCE(SUM(duration_minutes), 0)                  AS total_minutes,
                    COALESCE(SUM(CASE WHEN crew_role='PIC' THEN duration_minutes ELSE 0 END), 0) AS pic_minutes,
                    COALESCE(SUM(CASE WHEN crew_role='SIC' THEN duration_minutes ELSE 0 END), 0) AS sic_minutes,
                    COALESCE(SUM(CASE WHEN is_instructor=1 THEN duration_minutes ELSE 0 END), 0)  AS instructor_minutes,
                    COALESCE(SUM(takeoffs_day_manual  + takeoffs_day_auto),   0) AS total_day_takeoffs,
                    COALESCE(SUM(takeoffs_night_manual+ takeoffs_night_auto), 0) AS total_night_takeoffs,
                    COALESCE(SUM(landings_day_manual  + landings_day_auto),   0) AS total_day_landings,
                    COALESCE(SUM(landings_night_manual+ landings_night_auto), 0) AS total_night_landings,
                    COALESCE(SUM(approaches_day_manual + approaches_day_auto +
                                 approaches_night_manual + approaches_night_auto), 0) AS total_approaches,
                    COUNT(DISTINCT aircraft_id)                          AS unique_aircraft,
                    MIN(date)                                            AS first_flight_date,
                    MAX(date)                                            AS last_flight_date
                FROM flight_logs WHERE user_id = ?""",
                (user_id,),
            ).fetchone()
        return dict(row) if row else {}
    except Exception:
        return {}


def get_monthly_hours(user_id: int) -> list[dict]:
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT strftime('%Y-%m', date) AS month,
                          SUM(duration_minutes)  AS total_minutes
                   FROM flight_logs WHERE user_id = ?
                   GROUP BY month ORDER BY month""",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# User Preferences
# ---------------------------------------------------------------------------

def get_home_display_prefs(user_id: int) -> dict:
    """Return dict of pref_key → pref_value for the user. Missing keys default to '1'."""
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT pref_key, pref_value FROM user_preferences WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        return {r["pref_key"]: r["pref_value"] for r in rows}
    except Exception:
        return {}


def set_home_display_pref(user_id: int, key: str, value: str) -> None:
    """UPSERT a single Home page display preference."""
    try:
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO user_preferences (user_id, pref_key, pref_value)
                   VALUES (?, ?, ?)
                   ON CONFLICT(user_id, pref_key)
                   DO UPDATE SET pref_value = excluded.pref_value""",
                (user_id, key, value),
            )
    except Exception:
        pass
