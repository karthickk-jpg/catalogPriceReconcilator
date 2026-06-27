#!/usr/bin/env python3
import sys
import os
import traceback

# Ensure project root is on sys.path so local packages can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import SUPPORTED_PLATFORMS, DEFAULT_LOW_THRESHOLD, DEFAULT_MEDIUM_THRESHOLD
from database.connection import get_db
from ingestion.google_adapter import load_google_platform_data
from services.spreadsheet_reader import resolve_column_mapping
from core.engine import ReconciliationInput, run_reconciliation_engine


def main():
    try:
        with get_db() as db:
            print("Loading Google platform data...")
            sheets = load_google_platform_data(session=db)

            if "WMS" not in sheets or sheets["WMS"].empty:
                print("WMS sheet missing or empty")
                return

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
                low_threshold=DEFAULT_LOW_THRESHOLD,
                medium_threshold=DEFAULT_MEDIUM_THRESHOLD,
            )

            print("Running reconciliation engine...")
            result = run_reconciliation_engine(engine_inp)

            comparison_rows = result.comparison_df.to_dict("records") if result.comparison_df is not None else []

            # Requested prints
            print("Comparison rows:", len(comparison_rows))
            print(result.comparison_df.head())
            print(result.comparison_df.columns.tolist())
            print(result.run_summary)

            # Confirmations
            print("result.comparison_df empty?", result.comparison_df is None or result.comparison_df.empty)
            print("comparison_rows contains records?", bool(comparison_rows))

            required = ["sku", "marketplace", "wms_price", "marketplace_price", "price_diff", "severity"]
            cols = result.comparison_df.columns.tolist() if result.comparison_df is not None else []
            missing = [c for c in required if c not in cols]
            print("missing columns:", missing)

    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    main()
