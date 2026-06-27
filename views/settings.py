import streamlit as st

from config.settings import DEFAULT_LOW_THRESHOLD, DEFAULT_MEDIUM_THRESHOLD


# Settings page must not expose or mutate Google connection details.
# Google Sheets connectivity is verified via a read-only check.



st.title("⚙️ Portal Configuration Settings")
st.write("Operational configuration: severity thresholds and internal-only connection status.")

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Google Sheets Source (read-only)
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("Google Sheets Status")

from config.settings import GOOGLE_SHEET_ID, SERVICE_ACCOUNT_JSON_PATH

# Check if config values are loaded
if not GOOGLE_SHEET_ID or not SERVICE_ACCOUNT_JSON_PATH:
    st.error(
        "**Configuration Missing:** The `GOOGLE_SHEET_ID` or `SERVICE_ACCOUNT_JSON_PATH` is not set. "
        "The application cannot connect to Google Sheets."
    )
    st.warning(
        "**Action Required:** Create a file named `.env` in the project's root directory "
        "and add your configuration values to it."
    )
    st.code(
        '# Create this file: .env\n'
        'CPRP_GOOGLE_SHEET_ID="your_sheet_id_here"\n'
        'CPRP_SERVICE_ACCOUNT_JSON_PATH="C:/path/to/your/credentials.json"',
        language="shell"
    )
else:
    # Optional: simple admin-only indicator. No credentials or IDs are displayed.
    connected = False
    try:
        from services.google_sheet_reader import read_gsheet_tab_as_dataframe
        from config.settings import PLATFORM_SHEETS
        first_tab = next(iter(PLATFORM_SHEETS.values()))
        _ = read_gsheet_tab_as_dataframe(
            spreadsheet_id=GOOGLE_SHEET_ID,
            tab_name=first_tab,
            service_account_json_path=SERVICE_ACCOUNT_JSON_PATH,
        )
        connected = True
    except Exception:
        connected = False
    if connected:
        st.success("✓ Connection Verified")
    else:
        st.error("Connection Failed: Could not connect to Google Sheets. Verify your Sheet ID, service account path, and sharing permissions.")






st.markdown(
    """
**Expected sheet layout in Google Sheets:**

| Sheet | Required Columns |

|-------|-----------------|
| WMS | SKU, product_name, brand, category, WMS Price |
| Amazon | SKU, Product Name, Selling Price |
| Flipkart | SKU, Product Name, Selling Price |
| Myntra | SKU, Product Name, MRP |
| Shopify | SKU, Product Name, Price |

Catalog associates paste data into each sheet. CPRP reads directly from this file.
"""
)

st.divider()

st.subheader("Severity Threshold Tuning")

st.write("Determine percentage pricing differences boundaries for discrepancies categorization.")

low_thresh = st.slider(
    "Low Mismatch Upper Bound (%)",
    min_value=0.1,
    max_value=5.0,
    value=DEFAULT_LOW_THRESHOLD,
    step=0.1,
    help="Differences below or equal to this limit are tagged as Low Mismatch.",
)

med_thresh = st.slider(
    "Medium Mismatch Upper Bound (%)",
    min_value=1.0,
    max_value=20.0,
    value=DEFAULT_MEDIUM_THRESHOLD,
    step=0.5,
    help="Differences above the Low bound but below or equal to this limit are tagged as Medium Mismatch. Anything above is tagged as Critical.",
)

st.divider()

st.subheader("Data Purge Options")
st.write("Remove past records, uploaded spreadsheets, and generated Excel sheets from the portal database.")

if st.button("Purge Historical Audit Data", type="secondary"):
    st.warning("This function is not active in the skeleton version. It will cascade delete tables on final implementation.")
