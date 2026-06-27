# CPRP Architecture Review & Implementation Plan

This document establishes a robust, maintainable, and scalable software architecture for the **Catalog Price Reconciliation Portal (CPRP)**. The design uses standard software engineering patterns to decouple presentation logic (Streamlit UI) from core business logic (Service Layer) and data storage (ORM/SQLite Database).

---

## Architecture Review

### Decoupled 3-Tier Architecture
We structure the application into three decoupled layers:
1. **Presentation Layer (UI)**: Built with Streamlit views. Pages capture user files, inputs, and triggers. They only format and display tables, charts, and messages. They contain **no business logic** or raw SQL queries.
2. **Services Layer (Business Logic)**: Standalone Python modules containing pure functions and classes. This layer handles CSV/Excel parsing, row-level validation, price comparison metrics, Excel export formatting, and data transformation using Pandas and OpenPyXL.
3. **Data Access Layer (Database)**: SQLAlchemy ORM models mapping to SQLite. Handles data persistence for settings, historical runs, validation errors, mappings, and raw comparison items.

```
┌────────────────────────────────────────────────────────┐
│               Streamlit Presentation (UI)              │
│  views/dashboard.py   views/reconcile.py   ...         │
└───────────────────────────┬────────────────────────────┘
                            │ Calls Services
                            ▼
┌────────────────────────────────────────────────────────┐
│                     Services Layer                     │
│  services/file_reader.py      services/validator.py    │
│  services/comparer.py         services/exporter.py     │
└───────────────────────────┬────────────────────────────┘
                            │ Interacts with DB Models
                            ▼
┌────────────────────────────────────────────────────────┐
│                Database ORM Access Layer               │
│  database/connection.py       database/models.py       │
└────────────────────────────────────────────────────────┘
```

### Flow of Operations during Reconciliation
1. User uploads a WMS file and a Marketplace file in `views/reconcile.py` and specifies the platform mapping.
2. The UI invokes `services/file_reader.py` to parse files into Pandas DataFrames.
3. The UI runs `services/validator.py` to run initial sanity checks (duplicate SKUs, blank values, invalid pricing fields).
4. If validation checks pass, files are saved locally under `uploads/` named by run hash, and data is saved to `database/models.py:UploadedFile`.
5. A `ReconciliationRun` record is instantiated in `Pending` then `Processing` state.
6. The UI calls `services/comparer.py` to reconcile prices, calculating absolute and percent differences and severity classification.
7. Discrepancies and comparison details are persisted as bulk rows in `database/models.py:ComparisonDetail`.
8. Validation anomalies are persisted in `database/models.py:ValidationError`.
9. The run state updates to `Completed` (or `Failed` on errors) and the user is redirected to the dynamic Plotly results dashboard.

---

## Improved Database Schema & Entity Relationships

The relational model handles structural validation errors, historical file logging, mapping recommendations, and all comparison records.

```mermaid
erDiagram
    ReconciliationRun ||--o{ UploadedFile : "has"
    ReconciliationRun ||--o{ ComparisonDetail : "contains"
    ReconciliationRun ||--o{ ValidationError : "flags"
    UploadedFile ||--o{ ValidationError : "contains"

    ReconciliationRun {
        int id PK
        string status "Pending / Processing / Completed / Failed"
        datetime run_date
        int total_skus
        int exact_matches
        int mismatches
        int missing_wms
        int missing_marketplace
        string error_message
    }

    UploadedFile {
        int id PK
        int run_id FK
        string file_type "WMS / Marketplace"
        string filename
        string filepath
        string platform "WMS / Amazon / Flipkart / Shopify / etc."
        int row_count
        datetime upload_timestamp
    }

    ComparisonDetail {
        int id PK
        int run_id FK
        string sku
        float wms_price
        float marketplace_price
        float price_diff
        float percent_diff
        string severity "Exact / Low / Medium / Critical / Missing WMS / Missing Mkt"
    }

    ValidationError {
        int id PK
        int run_id FK
        int file_id FK
        string error_type "Duplicate SKU / Blank Price / Invalid Price / Missing Column"
        int row_number
        string sku
        string column_name
        string error_message
    }

    PlatformMapping {
        int id PK
        string platform "Amazon / Flipkart / Myntra / Shopify / etc."
        string sku_column
        string price_column
        datetime updated_at
    }

    Settings {
        int id PK
        string key UNIQUE
        string value
        string description
    }
```

---

## Project Folder Structure

An organized workspace separates modules strictly by purpose:

```
CPRP/
├── .streamlit/
│   └── config.toml             # Streamlit visual configurations (custom slate theme)
├── app.py                      # Main entrypoint, setups wide layout and st.navigation
├── config/
│   ├── __init__.py
│   └── settings.py             # Constants, severity limits, storage paths, logging configs
├── database/
│   ├── __init__.py
│   ├── connection.py           # SQLAlchemy engine, session maker, DB initialization hook
│   └── models.py               # Declarative ORM models mapped to database tables
├── reports/                    # Directory to store exported spreadsheet outputs
├── services/
│   ├── __init__.py
│   ├── file_reader.py          # CSV/Excel parsing into unified Pandas DataFrames
│   ├── validator.py            # Check schemas, nulls, duplicates, bad datatypes
│   ├── comparer.py             # Main price reconciliation algorithm
│   └── exporter.py             # OpenPyXL formatter for mismatch reports
├── tests/
│   ├── __init__.py
│   ├── test_services.py        # Independent unit testing for comparer and validators
│   └── test_db.py              # Tests database insertion and mappings
├── uploads/                    # Stores uploaded WMS/Marketplace files securely
├── utils/
│   ├── __init__.py
│   └── helpers.py              # Formatting numbers, standard logs, datetimes helper
└── views/
    ├── __init__.py
    ├── dashboard.py            # Landing view: high-level summary cards, quick run links
    ├── reconcile.py            # Upload, mapping dropdowns, validation errors list, triggers
    ├── history.py              # History records table, reload button, export downloads
    └── settings.py             # Adjust severity thresholds (%), database cleaning utilities
```

### Folder and File Responsibility Directory
| Component | Target File | Purpose & Responsibilities |
| :--- | :--- | :--- |
| **Root** | `app.py` | Sets up Streamlit app setup parameters and builds standard multi-page sidebar navigation (`st.navigation`). |
| **Config** | `config/settings.py` | Global configuration options (such as `%` difference severity thresholds, path mappings, platform names). |
| **Database** | `database/connection.py` | Sets up the sqlite connector, engine connection pool, declarative base, database session generator helper. |
| **Database** | `database/models.py` | Defines tables: `ReconciliationRun`, `UploadedFile`, `ComparisonDetail`, `ValidationError`, `PlatformMapping`, `Settings`. |
| **Services** | `services/file_reader.py` | Uses Pandas/OpenPyXL/CSV reader to load binary spreadsheets. Normalizes headers. Handles formats. |
| **Services** | `services/validator.py` | Performs structural analysis. Finds empty cells, column presence, numeric formats, duplicate entries. |
| **Services** | `services/comparer.py` | Runs comparative operations, evaluates pricing margins, generates comparison outputs. |
| **Services** | `services/exporter.py` | Writes reports using OpenPyXL with color-coded discrepancy highlights for the Operations team. |
| **Views** | `views/dashboard.py` | Visual summary widgets, aggregate match statistics, dynamic Plotly dashboard indicators. |
| **Views** | `views/reconcile.py` | Drag-and-drop workspace, column maps, real-time validations view, execution run progression. |
| **Views** | `views/history.py` | Historical log lookup, comparison details visualizer, rerun options, download buttons. |
| **Views** | `views/settings.py` | Editable portal parameter controls, configuration parameters editor, purging utilities. |

---

## Design Decisions

- **SQLite + SQLAlchemy ORM**: Decouples the schema design from database engines. If the client shifts CPRP to Postgres or MySQL in the future, only the connection string in `config/settings.py` needs updating. SQLite is serverless and fits desktop environments.
- **Service Layer decoupling from Streamlit**: All core services accept and return generic Python/Pandas types (`pd.DataFrame`, lists, dictionaries, strings). They do not import Streamlit. This keeps business code clean and testable via regular CLI `pytest` or `unittest`.
- **Validation-to-DB pattern**: Storing warnings/validation errors directly in database tables instead of plain logs makes them searchable. The catalog team can view specific anomalies (like duplicate SKUs or missing prices) inside the dashboard.
- **Disk File Persistence**: Storing uploads in `uploads/` matching unique run hashes allows audits and prevents data loss if raw records are updated.

---

## Scalability Recommendations & Future Extensions

- **Database Performance**: Use SQLAlchemy bulk operations (`db.bulk_insert_mappings` or pandas `to_sql` using SQLAlchemy connection) to insert comparison details. Loops can slow down database writes for files exceeding 100,000 items.
- **Background Threading**: When processing large sheets, run calculation tasks using Python's `threading` or `concurrent.futures` to prevent Streamlit from freezing.
- **Multiple Marketplace Uploads (Expansion)**: The data schema allows multiple `UploadedFile` records per `ReconciliationRun`. We can extend the comparer service to handle an arbitrary list of marketplace files and match them together.
- **API and Automation Integration**:
  - The services layer functions can run independently of Streamlit.
  - Adding a CLI script or Celery task runner that calls `file_reader.py` and `comparer.py` would allow scheduling run inputs automatically via cron.
  - API endpoints could easily interface with these services.

---

## Risks and Mitigation

| Identified Risk | Severity | Mitigation Strategy |
| :--- | :--- | :--- |
| **Memory constraints with large files** | Medium | Check file size during upload. If it exceeds 100MB, suggest CSV parsing over XLSX, or chunk data loading with Pandas to keep RAM usage low. |
| **Mismatched SKU formats** | High | Normalization in `comparer.py`: strip spaces, convert to uppercase, drop leading zeros if one side uses numeric and the other text. |
| **Simultaneous DB writes (SQLite locks)** | Low | SQLite is single-write only. Since this is desktop/internal software, write locking is rare. Scoped context managers in `connection.py` close sessions immediately. |

---

## Detailed Implementation Roadmap

### Phase 1: Project Setup & Structure (Infrastructure Setup)
1. Initialize file structure inside `c:\Users\Kushals\Desktop\CPRP`.
2. Configure `requirements.txt` and `.streamlit/config.toml` dark slate aesthetic.
3. Write `app.py` skeleton and page views layout with navigation sidebar.
4. Establish logging, folder targets (`uploads/`, `reports/`) inside `config/settings.py`.

### Phase 2: Database Layer & Schema Definitions
1. Write SQLAlchemy configuration in `database/connection.py`.
2. Implement declarative mapping classes in `database/models.py`.
3. Create test runs to verify schema creation on local SQLite file (`cprp.db`).

### Phase 3: Core Service Layer & Unit Tests
1. Code `services/file_reader.py` with automatic normalization features.
2. Build validation routines in `services/validator.py` returning catalog errors.
3. Build the reconciliation algorithm in `services/comparer.py`.
4. Implement formatted Excel reports export via `services/exporter.py`.
5. Establish verification tests inside the `tests/` directory.

### Phase 4: Streamlit UI pages
1. **Settings View**: Implement configuration parameters and mapping managers.
2. **Reconcile View**: Hook up Drag/Drop boxes, show schema validations, execute runs.
3. **History View**: Bind database runs table, add details views, download report buttons.
4. **Dashboard View**: Code charts (Plotly) and match analytics.

---

## Verification Plan

### Automated Verification
- Execute Python syntax checking: `python -m py_compile app.py services/*.py database/*.py views/*.py`
- Setup automated test framework validation running service unit checks.

### Manual Verification
1. Run server: `streamlit run app.py`
2. Test navigability of pages: Dashboard ➔ Reconcile ➔ History ➔ Settings.
3. Upload mock data files to confirm the validation panel correctly flags duplicate SKUs and blank values.
4. Run comparisons and check calculations.
5. Export sheets to confirm color formatting and details.
