import os
from dataclasses import dataclass
from typing import Dict, Any, Optional, List


import pandas as pd
import gspread
from gspread.exceptions import APIError

from utils.helpers import get_logger

logger = get_logger("services.google_sheet_reader")

DEFAULT_TIMEOUT_SEC = 60


# ─────────────────────────────────────────────────────────────────────────────
# TEMP hardcoded config for debugging/testing connection to Google Sheets
# ─────────────────────────────────────────────────────────────────────────────
DEBUG_GOOGLE_SHEET_ID = "13Y9VsscBWAvFCfzV77nN87QOI-WM7Cq8GNYERCFfp4s"
DEBUG_GOOGLE_SERVICE_ACCOUNT_JSON_PATH = r"C:\\Users\\Kushals\\Desktop\\CPRP\\credentials\\service_account.json"


@dataclass
class GoogleSheetConfig:
    spreadsheet_id: str
    service_account_json_path: str


def _get_client(service_account_json_path: str) -> gspread.Client:
    """Create an authenticated gspread client using a service account JSON file."""
    if not service_account_json_path:
        raise ValueError(
            "Missing service account JSON path. Provide the path to the service account JSON file."
        )

    if not os.path.isfile(service_account_json_path):
        raise FileNotFoundError(f"Service account JSON not found: {service_account_json_path}")

    return gspread.service_account(filename=service_account_json_path)


def read_gsheet_tab_as_dataframe(
    spreadsheet_id: str,
    tab_name: str,
    service_account_json_path: str,
) -> pd.DataFrame:
    """Read a single worksheet tab into a Pandas DataFrame.

    We rely on the first row as headers (like pd.read_excel default behavior).
    """
    client = _get_client(service_account_json_path)

    try:
        ss = client.open_by_key(spreadsheet_id)
        ws = ss.worksheet(tab_name)
        records = ws.get_all_records()  # list[dict]
        df = pd.DataFrame(records)
    except APIError as e:
        raise RuntimeError(f"Google Sheets API error while reading tab '{tab_name}': {e}")

    if df.empty:
        return df

    df.columns = [str(col).strip() for col in df.columns]
    df = df.dropna(how="all")
    return df


def read_all_platform_tabs_as_dataframes(
    spreadsheet_id: str,
    service_account_json_path: str,
    platform_sheet_map: Dict[str, str],
) -> Dict[str, pd.DataFrame]:
    """Read WMS + marketplaces tabs into {platform: dataframe}.

    Tabs that fail to load are omitted (validator/live sync will handle missing data).
    """
    out: Dict[str, pd.DataFrame] = {}

    for platform, tab_name in platform_sheet_map.items():
        try:
            df = read_gsheet_tab_as_dataframe(
                spreadsheet_id=spreadsheet_id,
                tab_name=tab_name,
                service_account_json_path=service_account_json_path,
            )
            out[platform] = df
            logger.info(
                f"Loaded Google tab '{tab_name}' for platform '{platform}' with {len(df)} rows"
            )
        except Exception as e:
            logger.error(
                f"Failed loading Google tab '{tab_name}' for platform '{platform}': {e}"
            )

    return out


def debug_google_connection() -> Dict[str, Any]:
    """TEMP diagnostics: connect CPRP to a hardcoded Google Sheet and report tab samples.

    Requirements (per task):
    - Return structured dict for dashboard display
    - Log/print same information via logger.info()
    - On failure: return {"success": False, "error": str(exception)} and log full exception
    - Do not suppress exceptions at call site (we catch here only to format return payload)
    """

    from config.settings import PLATFORM_SHEETS

    try:
        spreadsheet_id = DEBUG_GOOGLE_SHEET_ID
        sa_json_path = DEBUG_GOOGLE_SERVICE_ACCOUNT_JSON_PATH

        logger.info("[debug_google_connection] Starting debug connection")
        logger.info(f"[debug_google_connection] Google Sheet ID: {spreadsheet_id}")
        logger.info(f"[debug_google_connection] Service account JSON path: {sa_json_path}")

        client = _get_client(sa_json_path)

        # Extract service account email if available
        service_account_email: Optional[str] = None
        try:
            sa_info = client.auth.service_account_email  # type: ignore[attr-defined]
            service_account_email = sa_info
        except Exception:
            service_account_email = None

        if service_account_email:
            logger.info(
                f"[debug_google_connection] Service account email: {service_account_email}"
            )

        ss = client.open_by_key(spreadsheet_id)

        worksheet_names: List[str] = [ws.title for ws in ss.worksheets()]
        logger.info(f"[debug_google_connection] Worksheet names: {worksheet_names}")

        # Row counts for each platform tab we care about
        platform_sheet_map = {platform: tab for platform, tab in PLATFORM_SHEETS.items()}
        row_counts: Dict[str, int] = {}

        wms_df = read_gsheet_tab_as_dataframe(
            spreadsheet_id=spreadsheet_id,
            tab_name=platform_sheet_map.get("WMS", "WMS"),
            service_account_json_path=sa_json_path,
        )
        wms_rows = len(wms_df)
        row_counts["WMS"] = wms_rows

        # Samples: first 5 rows (raw dict rows)
        wms_sample = (
            wms_df.head(5).to_dict(orient="records") if not wms_df.empty else []
        )

        amazon_sample: List[Dict[str, Any]] = []
        if "Amazon" in platform_sheet_map:
            amazon_df = read_gsheet_tab_as_dataframe(
                spreadsheet_id=spreadsheet_id,
                tab_name=platform_sheet_map["Amazon"],
                service_account_json_path=sa_json_path,
            )
            row_counts["Amazon"] = len(amazon_df)
            amazon_sample = (
                amazon_df.head(5).to_dict(orient="records")
                if not amazon_df.empty
                else []
            )

        # Other platforms row counts (no samples required)
        for platform in ["Flipkart", "Myntra", "Shopify"]:
            tab_name = platform_sheet_map.get(platform)
            if not tab_name:
                continue
            df = read_gsheet_tab_as_dataframe(
                spreadsheet_id=spreadsheet_id,
                tab_name=tab_name,
                service_account_json_path=sa_json_path,
            )
            row_counts[platform] = len(df)

        payload: Dict[str, Any] = {
            "success": True,
            "sheet_id": spreadsheet_id,
            "service_account_email": service_account_email,
            "worksheets": worksheet_names,
            "row_counts": row_counts,
            "wms_sample": wms_sample,
            "amazon_sample": amazon_sample,
        }

        logger.info(f"[debug_google_connection] Row counts: {row_counts}")
        logger.info(f"[debug_google_connection] WMS first 5 rows: {wms_sample}")
        logger.info(
            f"[debug_google_connection] Amazon first 5 rows: {amazon_sample}"
        )

        return payload

    except Exception as e:
        logger.error("[debug_google_connection] Debug connection failed", exc_info=True)
        return {"success": False, "error": str(e)}



