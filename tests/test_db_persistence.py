import os
import sys

import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.connection import get_db, init_db
from database.models import ComparisonDetail
from services.db_persistence import create_reconciliation_run, save_comparison_details


def test_save_comparison_details_handles_missing_sku():
    init_db()

    with get_db() as db:
        run_id = create_reconciliation_run(db, run_type="historical", run_name="test")
        save_comparison_details(
            db,
            run_id,
            [
                {
                    "sku": None,
                    "product_name": "Example",
                    "marketplace": "Shopify",
                    "severity": "Missing in Marketplace",
                }
            ],
        )

        saved = db.query(ComparisonDetail).filter(ComparisonDetail.run_id == run_id).all()

    assert len(saved) == 1
    assert saved[0].sku == "UNKNOWN"
