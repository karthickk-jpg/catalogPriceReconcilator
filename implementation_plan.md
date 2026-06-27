# Production Cleanup Audit & Safe Removal Plan — CPRP

This document details the audit findings and proposed execution steps to clean up the Catalog Price Reconciliation Portal (CPRP) repository. The target architecture is a streamlined **Dashboard-only microservice** with a single Streamlit dashboard and a FastAPI `/reconcile` endpoint.

---

## 1. Current Repository Snapshot

The current workspace contains:
- `app.py` as the Streamlit shell.
- `views/dashboard.py` as the sole user-facing page.
- `api/main.py` and `api/routes/reconcile.py` for the backend API.
- `services/spreadsheet_reader.py`, `services/google_sheet_reader.py`, `services/validator.py`, `services/comparer.py`, and `services/db_persistence.py` for ingestion, validation, comparison, and persistence.
- `api/routes/history.py` and `api/routes/settings.py` as unused placeholder routes.
- `services/live_sync.py` as an unused legacy sync module.
- `tests/test_flow.py` and `tests/test_performance.py` for validation.

---

## 2. Dependency Graph

```mermaid
graph TD
    subgraph UI [Streamlit View (Presentation)]
        app[app.py Entrypoint]
        dash[views/dashboard.py]
        app -->|Launches| dash
    end

    subgraph Service [Service Backend Layer]
        dash -->|HTTP Refresh| API[FastAPI: api/main.py]
        API -->|Reconcile Endpoint| route[api/routes/reconcile.py]
        route -->|Fetch Google Sheet Tabs| s_reader[services/spreadsheet_reader.py]
        s_reader -->|gspread Client| g_reader[services/google_sheet_reader.py]
        
        route -->|Execute Run Orchestration| engine[core/engine.py]
        engine -->|Validate Data| val[services/validator.py]
        engine -->|Vectorized Compare| comp[services/comparer.py]
        
        route -->|Persist DB Records| db_p[services/db_persistence.py]
    end

    subgraph DB [Database Access Layer]
        db_p -->|SQLAlchemy Sessions| conn[database/connection.py]
        db_p -->|ORM Models| models[database/models.py]
    end
```

---

## 3. Current Dead Code Report

| File / Module | Current Status | Proposed Action | Evidence / Rationale |
| :--- | :---: | :--- | :--- |
| **views/dashboard.py** | Active | **KEEP** | Single dashboard page used by `app.py`. |
| **api/routes/reconcile.py** | Active | **KEEP / REFACTOR** | Core `/reconcile` API endpoint. Keep and remove stale comments. |
| **api/main.py** | Active | **REFACTOR** | Remove unused history/settings router imports and registration. |
| **api/routes/history.py** | Unused | **DELETE** | Placeholder route not referenced by app or tests. |
| **api/routes/settings.py** | Unused | **DELETE** | Placeholder route not referenced by app or tests. |
| **services/spreadsheet_reader.py** | Active | **KEEP / REFACTOR** | Google Sheets ingestion and column mapping. |
| **services/google_sheet_reader.py** | Active | **KEEP** | gspread integration. |
| **services/validator.py** | Active | **KEEP** | Data validation logic. |
| **services/comparer.py** | Active | **KEEP** | Reconciliation engine. |
| **services/db_persistence.py** | Active | **KEEP** | Persistence functions used by the API route. |
| **services/live_sync.py** | Present | **DELETE** | Legacy sync module with no external references. |
| **tests/test_flow.py** | Active | **REFACTOR** | Remove the stale `services.file_reader` import and align with current APIs. |
| **tests/test_performance.py** | Active | **KEEP** | Performance regression tests. |
| **app.py** | Active | **REFACTOR** | Simplify Streamlit startup/navigation logic. |
| **utils/helpers.py** | Active | **KEEP** | Shared helper utilities. |

---

## 4. Safe Cleanup Plan

1. Update `app.py` to preserve only `views/dashboard.py` and remove unused navigation or startup blocks.
2. Refactor `api/main.py` to remove `history` and `settings` router imports and router registration.
3. Delete `api/routes/history.py` and `api/routes/settings.py`.
4. Delete `services/live_sync.py` if it remains unused after verification.
5. Update `tests/test_flow.py` to remove the broken import of `services.file_reader` and use the current persistence/comparer flow.
6. Run a repository-wide syntax and import validation.

---

## 5. Refactoring Opportunities

- `app.py` can be simplified to a single-page Streamlit app.
- `api/main.py` should no longer include unused router registration.
- `tests/test_flow.py` should be corrected for current service module structure.
- `services/spreadsheet_reader.py` already supports Google Sheets only; keep this model and avoid reintroducing workbook support.

---

## 6. Final Production Architecture

```
CPRP/
├── app.py                      # Streamlit entrypoint for dashboard-only UI
├── requirements.txt            # Python dependencies
├── .streamlit/
│   └── config.toml             # Streamlit settings
├── config/
│   └── settings.py             # App configuration values
├── database/
│   ├── connection.py           # SQLAlchemy session and engine setup
│   ├── migrate.py              # Schema migration helper
│   └── models.py               # ORM model definitions
├── core/
│   └── engine.py               # Reconciliation orchestration
├── api/
│   ├── main.py                 # FastAPI application setup
│   └── routes/
│       └── reconcile.py        # Reconciliation endpoint
├── services/
│   ├── spreadsheet_reader.py   # Google Sheets ingestion and mapping
│   ├── google_sheet_reader.py  # gspread API helpers
│   ├── validator.py            # Validation logic
│   ├── comparer.py             # Reconciliation engine
│   └── db_persistence.py       # Persistence logic
├── tests/
│   ├── test_flow.py            # Integration test
│   └── test_performance.py     # Performance benchmarks
└── utils/
    └── helpers.py              # Utility helpers
```

---

## 7. Verification Plan

### Automated Verification

* Run integration and performance tests:
  ```powershell
  python tests/test_flow.py
  python tests/test_performance.py
  ```
* Run syntax/import validation across all remaining modules:
  ```powershell
  python -m py_compile app.py services/*.py database/*.py views/*.py api/*.py api/routes/*.py core/*.py
  ```

### Manual Verification

* Start Streamlit and verify the dashboard loads.
* Confirm the `Refresh` button calls `http://127.0.0.1:8004/reconcile` successfully.
* Verify the Google Sheets debug and CSV download functionality.
