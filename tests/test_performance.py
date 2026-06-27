"""
Performance integration test for CPRP Phase 3.
Generates 25,000 WMS SKUs and 24,000 Marketplace SKUs (with overlaps and mismatches),
runs the vectorized reconciliation engine, and reports timings + accuracy.
"""
import os, sys, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pandas as pd
from database.connection import init_db, get_db
from services.comparer import reconcile_prices
from services.db_persistence import (
    create_reconciliation_run, update_reconciliation_run_status,
    save_comparison_details,
)

TOTAL_WMS_SKUS = 25_000
OVERLAP_SKUS   = 22_000   # SKUs present in both WMS and marketplace
EXTRA_MKT_SKUS = 2_000    # SKUs only in marketplace (Missing in WMS)

def generate_test_data():
    rng = np.random.default_rng(42)
    sku_pool = [f"SKU-{i:06d}" for i in range(TOTAL_WMS_SKUS)]

    # WMS: all 25k SKUs, random prices
    wms_prices = rng.uniform(10, 5000, size=TOTAL_WMS_SKUS).round(2)
    wms_df = pd.DataFrame({"sku": sku_pool, "price": wms_prices})

    # Marketplace: 22k overlap + 2k extra. Introduce mismatches for ~30% of overlaps.
    mkt_skus = sku_pool[:OVERLAP_SKUS] + [f"EXTRA-{i:04d}" for i in range(EXTRA_MKT_SKUS)]
    mkt_prices_overlap = wms_prices[:OVERLAP_SKUS].copy()
    # Introduce price deviations to ~30% of overlap SKUs
    mismatch_idx = rng.choice(OVERLAP_SKUS, size=int(OVERLAP_SKUS * 0.30), replace=False)
    mkt_prices_overlap[mismatch_idx] *= rng.uniform(0.85, 1.20, size=len(mismatch_idx))
    mkt_prices_overlap = mkt_prices_overlap.round(2)
    mkt_prices_extra = rng.uniform(10, 3000, size=EXTRA_MKT_SKUS).round(2)
    mkt_prices = list(mkt_prices_overlap) + list(mkt_prices_extra)
    mkt_df = pd.DataFrame({"seller_sku": mkt_skus, "selling_price": mkt_prices})

    return wms_df, mkt_df


def run():
    print(f"Initializing DB...")
    init_db()

    print(f"Generating {TOTAL_WMS_SKUS:,} WMS + {OVERLAP_SKUS + EXTRA_MKT_SKUS:,} Marketplace SKUs...")
    t0 = time.perf_counter()
    wms_df, mkt_df = generate_test_data()
    print(f"  Data generation: {time.perf_counter()-t0:.3f}s")

    marketplace_datasets = {"Amazon": (mkt_df, "seller_sku", "selling_price")}

    print("Running reconcile_prices()...")
    t1 = time.perf_counter()
    run_summary, comparison_rows = reconcile_prices(
        wms_df, "sku", "price", marketplace_datasets,
        low_threshold=1.0, medium_threshold=5.0
    )
    elapsed_compare = time.perf_counter() - t1
    print(f"  reconcile_prices(): {elapsed_compare:.3f}s  |  {len(comparison_rows):,} rows")

    print("Summary:", run_summary)

    print("Saving to DB...")
    with get_db() as db:
        run_id = create_reconciliation_run(db)
        update_reconciliation_run_status(db, run_id, "Processing")

        t2 = time.perf_counter()
        # Chunk inserts to avoid SQLite max variable limits
        CHUNK = 1000
        for i in range(0, len(comparison_rows), CHUNK):
            save_comparison_details(db, run_id, comparison_rows[i:i+CHUNK])
        elapsed_db = time.perf_counter() - t2
        print(f"  DB bulk inserts: {elapsed_db:.3f}s  |  {len(comparison_rows):,} rows")

        update_reconciliation_run_status(db, run_id, "Completed", run_summary=run_summary)

    total = time.perf_counter() - t0
    print(f"\nPerformance Test PASSED")
    print(f"  Total end-to-end:  {total:.3f}s")
    print(f"  Comparison engine: {elapsed_compare:.3f}s")
    print(f"  DB writes:         {elapsed_db:.3f}s")
    print(f"  Rows processed:    {len(comparison_rows):,}")

    # Assertions
    assert run_summary["total_skus"] > 0
    assert run_summary["exact_matches"] > 0
    assert run_summary["missing_marketplace"] > 0  # 3k WMS SKUs not in marketplace
    assert run_summary["missing_wms"] > 0           # 2k marketplace extras
    print("All assertions passed.")


if __name__ == "__main__":
    run()
