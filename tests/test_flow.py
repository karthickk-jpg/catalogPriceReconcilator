import os
import sys
import pandas as pd

# Add project root to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.connection import get_db, init_db
from database.models import ReconciliationRun, ComparisonDetail, ValidationError
from services.file_reader import read_file
from services.validator import validate_dataframe
from services.comparer import reconcile_prices
from services.db_persistence import (
    create_reconciliation_run,
    update_reconciliation_run_status,
    save_uploaded_file,
    save_validation_errors,
    save_comparison_details
)


def run_integration_test():
    print("Starting integration test...")

    # 1. Initialize DB
    init_db()

    # 2. Setup mock dataframes
    print("Creating mock datasets...")
    wms_data = {
        "SKU Code": ["SKU-001", "SKU-002", "SKU-003", "SKU-004", "SKU-002"],  # SKU-002 is duplicate
        "Base Price": [100.0, 150.0, 200.0, 250.0, 150.0]
    }
    wms_df = pd.DataFrame(wms_data)
    
    amazon_data = {
        "Seller SKU": ["SKU-001", "SKU-002", "SKU-003", "SKU-005"],  # SKU-004 is missing, SKU-005 is extra
        "Sale Price": [100.0, 145.0, 220.0, "invalid_price"]  # SKU-002 mismatch, SKU-003 mismatch, SKU-005 price formatting issue
    }
    amazon_df = pd.DataFrame(amazon_data)

    wms_sku_col = "SKU Code"
    wms_price_col = "Base Price"
    amazon_sku_col = "Seller SKU"
    amazon_price_col = "Sale Price"

    # 3. Create run record
    with get_db() as db:
        run_id = create_reconciliation_run(db)
        print(f"Created ReconciliationRun #{run_id}")

        # Update status
        update_reconciliation_run_status(db, run_id, "Processing")

        # 4. Validate
        print("Validating datasets...")
        wms_summary, wms_errors = validate_dataframe(wms_df, wms_sku_col, wms_price_col, "WMS", "WMS")
        amazon_summary, amazon_errors = validate_dataframe(amazon_df, amazon_sku_col, amazon_price_col, "Marketplace", "Amazon")

        print("WMS Errors found:", len(wms_errors))
        print("Amazon Errors found:", len(amazon_errors))

        # Save files log & errors
        wms_file_id = save_uploaded_file(db, run_id, "WMS", "mock_wms.xlsx", "uploads/mock_wms.xlsx", "WMS", len(wms_df))
        save_validation_errors(db, run_id, wms_file_id, wms_errors)

        amazon_file_id = save_uploaded_file(db, run_id, "Marketplace", "mock_amazon.xlsx", "uploads/mock_amazon.xlsx", "Amazon", len(amazon_df))
        save_validation_errors(db, run_id, amazon_file_id, amazon_errors)

        # 5. Run Comparison
        print("Running reconciliation comparer...")
        marketplace_datasets = {
            "Amazon": (amazon_df, amazon_sku_col, amazon_price_col)
        }
        
        # Clean amazon df of invalid prices manually like comparer would (handled by validator report usually, but let's see how comparer behaves)
        # Comparer attempts float conversion on rows
        run_summary, comparison_rows = reconcile_prices(
            wms_df,
            wms_sku_col,
            wms_price_col,
            marketplace_datasets,
            1.0,
            5.0
        )

        print("Comparison rows count:", len(comparison_rows))
        print("Comparison summary:", run_summary)

        # Save results
        save_comparison_details(db, run_id, comparison_rows)
        
        # Mark completed
        update_reconciliation_run_status(db, run_id, "Completed", run_summary=run_summary)
        print(f"ReconciliationRun #{run_id} marked as Completed.")

        # 6. Verify insertions
        print("Verifying database records...")
        db_run = db.query(ReconciliationRun).filter(ReconciliationRun.id == run_id).first()
        print(f"DB Run status: {db_run.status}, Total SKUs: {db_run.total_skus}")
        assert db_run.status == "Completed"
        assert db_run.total_skus > 0

        details = db.query(ComparisonDetail).filter(ComparisonDetail.run_id == run_id).all()
        print(f"DB Details records count: {len(details)}")
        assert len(details) == len(comparison_rows)

        errs = db.query(ValidationError).filter(ValidationError.run_id == run_id).all()
        print(f"DB Validation errors count: {len(errs)}")
        assert len(errs) == (len(wms_errors) + len(amazon_errors))

    print("Integration test passed successfully!")


if __name__ == "__main__":
    run_integration_test()
