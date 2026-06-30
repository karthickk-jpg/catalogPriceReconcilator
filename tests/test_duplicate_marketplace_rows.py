import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.comparer import reconcile_prices


def test_reconcile_prices_keeps_and_compares_duplicate_marketplace_rows():
    wms_df = pd.DataFrame(
        {
            "SKU Code": ["SKU-001", "SKU-001"],
            "Base Price": [100.0, 120.0],
        }
    )
    marketplace_df = pd.DataFrame(
        {
            "Seller SKU": ["SKU-001", "SKU-001"],
            "Sale Price": [95.0, 125.0],
        }
    )

    run_summary, comparison_rows = reconcile_prices(
        wms_df=wms_df,
        wms_sku_col="SKU Code",
        wms_price_col="Base Price",
        marketplace_datasets={"Amazon": (marketplace_df, "Seller SKU", "Sale Price")},
        low_threshold=1.0,
        medium_threshold=5.0,
    )

    assert run_summary["total_skus"] == 1
    assert len(comparison_rows) == 4
    assert sum(1 for row in comparison_rows if row["severity"] == "Low Mismatch") >= 2
