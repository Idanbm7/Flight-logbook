# Flight Logbook — Project Guidelines for Claude

## Project Overview
A mobile-first UAV/drone flight logbook application built with Python and Streamlit.
- **UI Language:** English (all user-facing text must be in English)
- **Code Language:** English (variable names, function names, file names, comments)
- **Stack:** Python, Streamlit, SQLite (via sqlite3), pandas, fpdf2, openpyxl

---

## Rules

### 1. Autonomy — Auto-install Missing Libraries
If any required library is missing, install it automatically via pip before proceeding.
Do not ask for permission to install. Example:
```bash
pip install streamlit pandas fpdf2 openpyxl
```

### 2. Verify Before Reporting
Always run a syntax check (`python -m py_compile <file>`) in the terminal before telling
the user a file is ready. Never report "it's ready" without a successful verification run.

### 3. Incremental Development
Build in small, tested layers:
1. Database schema & CRUD (database.py)
2. Business logic helpers (utils.py)
3. UI pages (app.py + pages/)
4. Export features (PDF / Excel)
5. Dashboard / summary stats

### 4. UI/UX Standards
- All user-facing text, labels, placeholders, error messages, and tooltips must be in **English**.
- Layout must be **mobile-first**: large tap targets (buttons ≥ 44 px), big inputs, no horizontal scroll.
- Prefer `st.form`, `st.columns`, and `st.expander` for clean mobile layout.

### 5. Error Handling
- Validate all inputs before DB writes (required fields, time logic, numeric ranges).
- Show user-friendly errors via `st.error()` / `st.warning()`.
- Wrap all DB and file I/O in try/except with console logging.

---

## Data Model (SQLite)

### `users`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| username | TEXT UNIQUE | |
| password_hash | TEXT | SHA-256 hex digest |
| created_at | TIMESTAMP | |

### `aircraft`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| user_id | INTEGER FK | |
| model_type | TEXT | e.g. "DJI Matrice 300" |
| tail_number | TEXT | |
| call_sign | TEXT | optional |
| is_active | INTEGER | 1=active, 0=retired |

### `sites`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| user_id | INTEGER FK | per-user site list |
| name | TEXT | e.g. "Tel Aviv Beach" |

### `flight_logs`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| user_id | INTEGER FK | |
| aircraft_id | INTEGER FK | |
| site_id | INTEGER FK | NULL if custom location |
| site_custom | TEXT | used when site_id is NULL; auto-suggested next time |
| date | TEXT | YYYY-MM-DD |
| start_time | TEXT | HH:MM |
| end_time | TEXT | HH:MM |
| duration_minutes | INTEGER | computed on save |
| mission_purpose | TEXT | Training/Demo/Operational/Experimental/Other |
| gcs_type | TEXT | free text |
| crew_role | TEXT | PIC / SIC |
| is_instructor | INTEGER | 0 / 1 |
| takeoffs_day_manual | INTEGER | default 0 |
| takeoffs_day_auto | INTEGER | default 0 |
| takeoffs_night_manual | INTEGER | default 0 |
| takeoffs_night_auto | INTEGER | default 0 |
| landings_day_manual | INTEGER | default 0 |
| landings_day_auto | INTEGER | default 0 |
| landings_night_manual | INTEGER | default 0 |
| landings_night_auto | INTEGER | default 0 |
| approaches_day_manual | INTEGER | default 0 |
| approaches_day_auto | INTEGER | default 0 |
| approaches_night_manual | INTEGER | default 0 |
| approaches_night_auto | INTEGER | default 0 |
| comments | TEXT | free text |
| created_at | TIMESTAMP | |

---

## App Pages
1. **Login / Register** — session-based auth
2. **New Flight Log** — primary data entry (big, touch-friendly form)
3. **Flight History** — filterable table of past logs
4. **Dashboard** — personal stats (total hours, PIC/SIC split, day/night, etc.)
5. **Settings** — manage aircraft fleet and saved sites

## File Layout
```
flight-logbook/
├── CLAUDE.md
├── app.py             # Streamlit entry point + login
├── database.py        # Schema creation, connection, all CRUD helpers
├── utils.py           # Time calculations, validation, export helpers
├── pages/
│   ├── new_flight.py
│   ├── flight_history.py
│   ├── dashboard.py
│   └── settings.py
└── data/              # SQLite DB lives here (gitignored)
```

## Environment
- Platform: Windows 11
- Shell: bash (Git Bash)
- Python: system install (verify with `python --version` or `py --version`)
