import time
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional
from utils.helpers import normalize_sku, get_logger

logger = get_logger("services.comparer")

# Columns that may optionally be present in WMS for enrichment
OPTIONAL_WMS_COLS = ["product_name", "brand", "category"]


def _safe_float_series(series: pd.Series) -> pd.Series:
    """Vectorized safe conversion of a price series to float, replacing
    currency symbols/commas and coercing non-numeric to NaN."""
    cleaned = (
        series.astype(str)
        .str.replace(r"[₹$,]", "", regex=True)
        .str.strip()
    )
    return pd.to_numeric(cleaned, errors="coerce")


def reconcile_prices(
    wms_df: pd.DataFrame,
    wms_sku_col: str,
    wms_price_col: str,
    marketplace_datasets: Dict[str, Tuple[pd.DataFrame, str, str]],
    low_threshold: float,
    medium_threshold: float,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Reconciles WMS master prices against one or more marketplace files.

    Uses vectorized Pandas merges for performance on large datasets (25k+ SKUs).
    Propagates optional enrichment columns (product_name, brand, category) from WMS.

    Args:
        wms_df: WMS DataFrame.
        wms_sku_col: SKU column name in WMS.
        wms_price_col: Price column name in WMS.
        marketplace_datasets: {platform: (DataFrame, sku_col, price_col)}.
        low_threshold: % upper bound for Low Mismatch.
        medium_threshold: % upper bound for Medium Mismatch.

    Returns:
        (run_summary dict, list of comparison row dicts)
    """
    t_start = time.perf_counter()
    logger.info("Starting vectorized price reconciliation engine...")

    # --- 1. Prepare WMS DataFrame ---
    # Identify which optional enrichment columns exist in WMS
    enrich_cols = [c for c in OPTIONAL_WMS_COLS if c in wms_df.columns]
    keep_cols = [wms_sku_col, wms_price_col] + enrich_cols
    wms_clean = wms_df[keep_cols].copy()

    # Normalize SKU
    wms_clean["norm_sku"] = wms_clean[wms_sku_col].astype(str).apply(normalize_sku)
    wms_clean = wms_clean[wms_clean["norm_sku"] != ""]
    wms_clean = wms_clean.drop_duplicates(subset=["norm_sku"], keep="last")

    # Convert WMS price to float safely
    wms_clean["wms_price_f"] = _safe_float_series(wms_clean[wms_price_col])

    # Rename for merge clarity
    wms_merge = wms_clean.rename(columns={
        wms_sku_col: "_wms_sku_raw",
        wms_price_col: "_wms_price_raw",
    })
    # Add enrichment cols with standard names
    for col in OPTIONAL_WMS_COLS:
        if col not in wms_merge.columns:
            wms_merge[col] = None

    all_comparison_rows: List[Dict[str, Any]] = []
    unique_skus_global: set = set()
    exact_matches_cnt = mismatches_cnt = missing_wms_cnt = missing_marketplace_cnt = critical_cnt = 0

    # --- 2. Process each marketplace ---
    for platform, (mkt_df, mkt_sku_col, mkt_price_col) in marketplace_datasets.items():
        logger.info(f"Reconciling against {platform} ({len(mkt_df):,} rows)...")

        mkt_clean = mkt_df[[mkt_sku_col, mkt_price_col]].copy()
        mkt_clean["norm_sku"] = mkt_clean[mkt_sku_col].astype(str).apply(normalize_sku)
        mkt_clean = mkt_clean[mkt_clean["norm_sku"] != ""]
        mkt_clean = mkt_clean.drop_duplicates(subset=["norm_sku"], keep="last")
        mkt_clean["mkt_price_f"] = _safe_float_series(mkt_clean[mkt_price_col])
        mkt_clean = mkt_clean.rename(columns={mkt_sku_col: "_mkt_sku_raw"})

        # Outer merge on normalized SKU
        merged = pd.merge(
            wms_merge[["norm_sku", "_wms_sku_raw", "wms_price_f"] + OPTIONAL_WMS_COLS],
            mkt_clean[["norm_sku", "_mkt_sku_raw", "mkt_price_f"]],
            on="norm_sku",
            how="outer",
            indicator=True,
        )

        unique_skus_global.update(merged["norm_sku"].dropna().tolist())

        # --- 3. Derive display SKU ---
        merged["sku_display"] = merged["_wms_sku_raw"].where(
            merged["_merge"] != "right_only",
            merged["_mkt_sku_raw"]
        )

        # --- 4. Compute diffs & severity vectorized ---
        both = merged["_merge"] == "both"
        left_only = merged["_merge"] == "left_only"   # In WMS, not Marketplace
        right_only = merged["_merge"] == "right_only" # In Marketplace, not WMS

        # Price diff (only for both-sides rows)
        merged["price_diff"]   = np.nan
        merged["percent_diff"] = np.nan
        merged.loc[both, "price_diff"] = (
            merged.loc[both, "mkt_price_f"] - merged.loc[both, "wms_price_f"]
        ).round(2)

        # % diff — guard against zero WMS price
        wms_nonzero = both & (merged["wms_price_f"] != 0) & merged["wms_price_f"].notna()
        merged.loc[wms_nonzero, "percent_diff"] = (
            merged.loc[wms_nonzero, "price_diff"] / merged.loc[wms_nonzero, "wms_price_f"] * 100
        ).round(2)
        # Zero WMS price edge case: diff != 0 → 100%, else 0
        wms_zero = both & (merged["wms_price_f"] == 0) & merged["wms_price_f"].notna()
        merged.loc[wms_zero, "percent_diff"] = merged.loc[wms_zero, "price_diff"].apply(
            lambda d: 100.0 if d != 0 else 0.0
        )

        # Severity classification via vectorized conditions
        abs_pct = merged["percent_diff"].abs()
        conditions = [
            right_only,                                # Missing in WMS
            left_only,                                 # Missing in Marketplace
            both & abs_pct.isna(),                    # Price parse failure → critical
            both & (abs_pct == 0.0),                  # Exact Match
            both & (abs_pct > 0) & (abs_pct <= low_threshold),
            both & (abs_pct > low_threshold) & (abs_pct <= medium_threshold),
            both & (abs_pct > medium_threshold),
        ]
        choices = [
            "Missing in WMS",
            "Missing in Marketplace",
            "Critical Mismatch",
            "Exact Match",
            "Low Mismatch",
            "Medium Mismatch",
            "Critical Mismatch",
        ]
        merged["severity"] = np.select(conditions, choices, default="Unknown")

        # --- 5. Count metrics ---
        exact_matches_cnt   += int((merged["severity"] == "Exact Match").sum())
        mismatches_cnt      += int(merged["severity"].isin(["Low Mismatch", "Medium Mismatch", "Critical Mismatch"]).sum())
        missing_wms_cnt     += int((merged["severity"] == "Missing in WMS").sum())
        missing_marketplace_cnt += int((merged["severity"] == "Missing in Marketplace").sum())
        critical_cnt        += int((merged["severity"] == "Critical Mismatch").sum())

        # --- 6. Build output rows ---
        for _, row in merged.iterrows():
            all_comparison_rows.append({
                "sku":                row["sku_display"],
                "product_name":       row.get("product_name"),
                "brand":              row.get("brand"),
                "category":           row.get("category"),
                "wms_price":          row["wms_price_f"] if pd.notna(row.get("wms_price_f")) else None,
                "marketplace":        platform,
                "marketplace_price":  row["mkt_price_f"] if pd.notna(row.get("mkt_price_f")) else None,
                "price_diff":         row["price_diff"] if pd.notna(row.get("price_diff")) else None,
                "percent_diff":       row["percent_diff"] if pd.notna(row.get("percent_diff")) else None,
                "severity":           row["severity"],
                "status":             "Open",
            })

        logger.info(f"  {platform}: {len(merged):,} records processed.")

    elapsed = time.perf_counter() - t_start
    run_summary = {
        "total_skus":           len(unique_skus_global),
        "exact_matches":        exact_matches_cnt,
        "mismatches":           mismatches_cnt,
        "missing_wms":          missing_wms_cnt,
        "missing_marketplace":  missing_marketplace_cnt,
        "critical_mismatches":  critical_cnt,
    }
    logger.info(
        f"Reconciliation done in {elapsed:.2f}s | "
        f"Total={run_summary['total_skus']:,} | "
        f"Matches={exact_matches_cnt:,} | Mismatches={mismatches_cnt:,} | "
        f"Critical={critical_cnt:,}"
    )
    return run_summary, all_comparison_rows
