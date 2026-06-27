from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.post("/reconcile")
def reconcile(payload: dict) -> dict:
    """Run a reconciliation end-to-end.

    Phase 2 wiring:
    API -> ingestion/google_adapter -> core/engine -> persistence

    NOTE: payload is accepted for future parameterization; current engine uses
    thresholds from payload if provided, otherwise defaults.
    """

    from sqlalchemy.orm import Session
    from database.connection import get_db

    from config.settings import DEFAULT_LOW_THRESHOLD, DEFAULT_MEDIUM_THRESHOLD

    from ingestion.google_adapter import load_google_platform_data
    from core.engine import ReconciliationInput, run_reconciliation_engine

    # Thresholds (optional)
    low = float(payload.get("low_threshold", DEFAULT_LOW_THRESHOLD))
    medium = float(payload.get("medium_threshold", DEFAULT_MEDIUM_THRESHOLD))

    # Persistence: create run, save comparison details
    with get_db() as db:  # type: Session
        # ingestion adapter already needs session for mappings/settings
        sheets = load_google_platform_data(session=db)

        # Column mapping is currently resolved inside services.spreadsheet_reader.resolve_column_mapping
        # called by spreadsheet_reader.read_all_platform_sheets + resolve_column_mapping.
        # However, load_google_platform_data only loads tabs; we still need columns.
        # For Phase 2, we reuse legacy resolver logic by calling spreadsheet_reader.resolve_column_mapping.
        from services.spreadsheet_reader import resolve_column_mapping

        if "WMS" not in sheets or sheets["WMS"].empty:
            # NOTE: resolve_column_mapping signature is (platform: str, df: DataFrame)
            # Do not pass session/auto_save here; this route only needs column auto-mapping.
            return {"ok": False, "success": False, "message": "WMS sheet missing or empty"}

        wms_sku_col, wms_price_col = resolve_column_mapping("WMS", sheets["WMS"])

        marketplace_datasets = {}
        from config.settings import SUPPORTED_PLATFORMS
        for platform in SUPPORTED_PLATFORMS:
            if platform not in sheets or sheets[platform].empty:
                continue
            sku_col, price_col = resolve_column_mapping(platform, sheets[platform])
            marketplace_datasets[platform] = (sheets[platform], sku_col, price_col)

        # Run core engine
        engine_inp = ReconciliationInput(
            wms_df=sheets["WMS"],
            wms_sku_col=wms_sku_col,
            wms_price_col=wms_price_col,
            marketplace_datasets=marketplace_datasets,
            low_threshold=low,
            medium_threshold=medium,
        )

        result = run_reconciliation_engine(engine_inp)

        # Persist results
        from services.db_persistence import (
            create_reconciliation_run,
            update_reconciliation_run_status,
            save_comparison_details,
            save_validation_errors,
            get_live_snapshot_run,
            delete_live_snapshot_runs,
        )

        # For now, store as a historical run to avoid relying on legacy live snapshot layer.
        run_id = create_reconciliation_run(db, run_type="historical", run_name="API Reconcile")
        if not result.success:
            update_reconciliation_run_status(db, run_id, "Failed", error_message=result.message)
            return {
                "ok": False,
                "success": False,
                "run_id": run_id,
                "message": result.message,
                "warnings": result.warnings or [],
            }

        # Persist comparison rows
        if result.comparison_df is not None and len(result.comparison_df) > 0:
            # Reuse existing persistence schema: expects list[dict] comparison_rows
            comparison_rows = result.comparison_df.to_dict("records")
            save_comparison_details(db, run_id, comparison_rows)

        # Update run summary
        update_reconciliation_run_status(db, run_id, "Completed", run_summary=result.run_summary)

        # Prepare comparison rows payload if available so UI can render immediately
        comparison_rows = None
        if result.comparison_df is not None and len(result.comparison_df) > 0:
            comparison_rows = result.comparison_df.to_dict("records")

        return {
            "ok": True,
            "success": True,
            "run_id": run_id,
            "message": result.message,
            "run_summary": result.run_summary,
            "comparison_rows": comparison_rows,
            "warnings": result.warnings or [],
        }


