import os
from pathlib import Path
from dotenv import load_dotenv

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file for local development
load_dotenv(BASE_DIR / ".env")
REPORTS_DIR = BASE_DIR / "reports"

# Ensure directories exist
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Auto-refresh settings
DEFAULT_AUTO_REFRESH_INTERVAL_SEC = 60
SETTING_AUTO_REFRESH_INTERVAL = "auto_refresh_interval_sec"

# Database Configuration
DATABASE_PATH = BASE_DIR / "cprp.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# Reconciliation Configuration
SUPPORTED_PLATFORMS = ["Amazon", "Flipkart", "Myntra", "Shopify"]

# Google Sheets configuration
# NOTE: WMS remains the master source of truth.

# Sheet names/tabs in the Google Sheet (must match tab names exactly)
PLATFORM_SHEETS = {
    "WMS": "WMS",
    "Amazon": "Amazon",
    "Flipkart": "Flipkart",
    "Myntra": "Myntra",
    "Shopify": "Shopify",
}

# Default column mappings. Can be overridden by auto-detection if not found.
COLUMN_MAPPINGS = {
    "WMS": {"sku": "SKU", "price": "WMS Price"},
    "Amazon": {"sku": "SKU", "price": "Selling Price"},
    "Flipkart": {"sku": "SKU", "price": "Selling Price"},
    "Myntra": {"sku": "SKU", "price": "MRP"},
    "Shopify": {"sku": "SKU", "price": "Price"},
}

# Google Sheets configuration (hardcoded for internal deployment)
# NOTE: Users must not be able to view or modify these values via UI.
# It is recommended to set these as environment variables: CPRP_GOOGLE_SHEET_ID and CPRP_SERVICE_ACCOUNT_JSON_PATH
GOOGLE_SHEET_ID = os.getenv("CPRP_GOOGLE_SHEET_ID")
SERVICE_ACCOUNT_JSON_PATH = os.getenv("CPRP_SERVICE_ACCOUNT_JSON_PATH")


# Legacy setting keys (retained to avoid import/runtime breakage)
# These keys are no longer used by the UI, but some modules still reference the constants.
SETTING_DATA_SOURCE = "data_source"
SETTING_GOOGLE_SHEET_ID = "google_sheet_id"
SETTING_GOOGLE_SHEET_URL = "google_sheet_url"
SETTING_GOOGLE_SERVICE_ACCOUNT_JSON = "google_service_account_json_path"
DATA_SOURCE_GOOGLE_SHEETS = "google_sheets"

# Reconciliation run types (stored in reconciliation_runs.run_type)
RUN_TYPE_LIVE = "live"
RUN_TYPE_HISTORICAL = "historical"
LIVE_RUN_NAME = "Live Snapshot"



# Severity Thresholds (in percentage)
# Mismatch <= LOW_THRESHOLD: Low Mismatch
# LOW_THRESHOLD < Mismatch <= MEDIUM_THRESHOLD: Medium Mismatch
# Mismatch > MEDIUM_THRESHOLD: Critical Mismatch
DEFAULT_LOW_THRESHOLD = 1.0
DEFAULT_MEDIUM_THRESHOLD = 5.0

# Auto-mapping keywords (lowercase list for case-insensitive keyword searches)
SKU_KEYWORDS = [
    "sku", 
    "seller sku", 
    "seller-sku", 
    "seller_sku", 
    "item code", 
    "item_code", 
    "article", 
    "article code", 
    "article_code", 
    "article number", 
    "article_number",
    "fsn", 
    "product code", 
    "product_code",
    "code",
    "barcode",
    "id"
]

PRICE_KEYWORDS = [
    "price", 
    "selling price", 
    "selling_price", 
    "sale price", 
    "sale_price", 
    "mrp", 
    "listing price", 
    "listing_price", 
    "retail price", 
    "retail_price", 
    "rate", 
    "unit price", 
    "unit_price", 
    "amount"
]
