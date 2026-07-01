import pandas as pd

from config.settings import (
    DEFAULT_LOW_THRESHOLD,
    DEFAULT_MEDIUM_THRESHOLD,
    SUPPORTED_PLATFORMS,
)
from core.engine import ReconciliationInput, run_reconciliation_engine
from services.spreadsheet_reader import read_all_platform_sheets, resolve_column_mapping


def run_live_reconciliation(
    low_threshold: float = DEFAULT_LOW_THRESHOLD,
    medium_threshold: float = DEFAULT_MEDIUM_THRESHOLD,
) -> dict:
    """Load Google Sheets, run the comparison engine, and return mismatch data."""
    sheets = read_all_platform_sheets()

    if "WMS" not in sheets or sheets["WMS"].empty:
        return {
            "success": False,
            "message": "WMS sheet missing or empty",
            "run_summary": {},
            "comparison_df": pd.DataFrame(),
            "warnings": [],
        }

    wms_sku_col, wms_price_col = resolve_column_mapping("WMS", sheets["WMS"])

    marketplace_datasets = {}
    for platform in SUPPORTED_PLATFORMS:
        if platform not in sheets or sheets[platform].empty:
            continue
        sku_col, price_col = resolve_column_mapping(platform, sheets[platform])
        marketplace_datasets[platform] = (sheets[platform], sku_col, price_col)

    engine_inp = ReconciliationInput(
        wms_df=sheets["WMS"],
        wms_sku_col=wms_sku_col,
        wms_price_col=wms_price_col,
        marketplace_datasets=marketplace_datasets,
        low_threshold=low_threshold,
        medium_threshold=medium_threshold,
    )
    result = run_reconciliation_engine(engine_inp)

    return {
        "success": result.success,
        "message": result.message,
        "run_summary": result.run_summary or {},
        "comparison_df": result.comparison_df if result.comparison_df is not None else pd.DataFrame(),
        "warnings": result.warnings or [],
    }
