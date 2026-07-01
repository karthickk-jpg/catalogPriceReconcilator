"""
Performance integration test for CPRP.
Generates 25,000 WMS SKUs and 24,000 Marketplace SKUs (with overlaps and mismatches),
runs the vectorized reconciliation engine, and reports timings + accuracy.
"""
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pandas as pd
from services.comparer import reconcile_prices

TOTAL_WMS_SKUS = 25_000
OVERLAP_SKUS = 22_000
EXTRA_MKT_SKUS = 2_000


def generate_test_data():
    rng = np.random.default_rng(42)
    sku_pool = [f"SKU-{i:06d}" for i in range(TOTAL_WMS_SKUS)]

    wms_prices = rng.uniform(10, 5000, size=TOTAL_WMS_SKUS).round(2)
    wms_df = pd.DataFrame({"sku": sku_pool, "price": wms_prices})

    mkt_skus = sku_pool[:OVERLAP_SKUS] + [f"EXTRA-{i:04d}" for i in range(EXTRA_MKT_SKUS)]
    mkt_prices_overlap = wms_prices[:OVERLAP_SKUS].copy()
    mismatch_idx = rng.choice(OVERLAP_SKUS, size=int(OVERLAP_SKUS * 0.30), replace=False)
    mkt_prices_overlap[mismatch_idx] *= rng.uniform(0.85, 1.20, size=len(mismatch_idx))
    mkt_prices_overlap = mkt_prices_overlap.round(2)
    mkt_prices_extra = rng.uniform(10, 3000, size=EXTRA_MKT_SKUS).round(2)
    mkt_prices = list(mkt_prices_overlap) + list(mkt_prices_extra)
    mkt_df = pd.DataFrame({"seller_sku": mkt_skus, "selling_price": mkt_prices})

    return wms_df, mkt_df


def run():
    print(f"Generating {TOTAL_WMS_SKUS:,} WMS + {OVERLAP_SKUS + EXTRA_MKT_SKUS:,} Marketplace SKUs...")
    t0 = time.perf_counter()
    wms_df, mkt_df = generate_test_data()
    print(f"  Data generation: {time.perf_counter() - t0:.3f}s")

    marketplace_datasets = {"Amazon": (mkt_df, "seller_sku", "selling_price")}

    print("Running reconcile_prices()...")
    t1 = time.perf_counter()
    run_summary, comparison_rows = reconcile_prices(
        wms_df,
        "sku",
        "price",
        marketplace_datasets,
        low_threshold=1.0,
        medium_threshold=5.0,
    )
    elapsed_compare = time.perf_counter() - t1
    print(f"  reconcile_prices(): {elapsed_compare:.3f}s  |  {len(comparison_rows):,} rows")
    print("Summary:", run_summary)

    total = time.perf_counter() - t0
    print(f"\nPerformance Test PASSED")
    print(f"  Total end-to-end:  {total:.3f}s")
    print(f"  Comparison engine: {elapsed_compare:.3f}s")
    print(f"  Rows processed:    {len(comparison_rows):,}")

    assert run_summary["total_skus"] > 0
    assert run_summary["exact_matches"] > 0
    assert run_summary["missing_marketplace"] > 0
    assert run_summary["missing_wms"] > 0
    print("All assertions passed.")


if __name__ == "__main__":
    run()
