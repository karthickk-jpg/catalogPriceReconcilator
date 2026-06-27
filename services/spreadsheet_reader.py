from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd
from sqlalchemy.orm import Session

from config.settings import (
    COLUMN_MAPPINGS,
    PLATFORM_SHEETS,
    SETTING_GOOGLE_SERVICE_ACCOUNT_JSON,
    GOOGLE_SHEET_ID,
    SETTING_GOOGLE_SHEET_ID,
    SUPPORTED_PLATFORMS,
)

from services.file_reader import suggest_mappings
from utils.helpers import get_logger

logger = get_logger("services.spreadsheet_reader")


def _use_google_sheets(session: Optional[Session]) -> bool:
    # This function is now obsolete as Google Sheets is the only source.
    return True


# NOTE: Excel workbook functions are obsolete in Google-only mode.
# Keep functions referenced by older UI code, but resolve to a no-op path.

def get_workbook_path(session: Optional[Session] = None) -> Path:
    """Google-only mode: no local workbook path.

    Returns a non-existent path so workbook_exists/workbook_last_modified
    behave as 'not available'.
    """
    return Path("./CPRP_GOOGLE_ONLY_NO_WORKBOOK.xlsx")



def workbook_exists(path: Optional[Path] = None, session: Optional[Session] = None) -> bool:
    """Returns True if the configured master workbook exists on disk."""
    target = path or get_workbook_path(session)
    return target.is_file()


def get_workbook_last_modified(path: Optional[Path] = None, session: Optional[Session] = None) -> Optional[datetime]:
    """Returns the filesystem last-modified timestamp of the master workbook."""
    target = path or get_workbook_path(session)
    if not target.is_file():
        return None
    return datetime.fromtimestamp(target.stat().st_mtime)


def list_workbook_sheets(path: Optional[Path] = None, session: Optional[Session] = None) -> list[str]:
    """Returns sheet names present in the master workbook."""
    raise NotImplementedError("Workbook sheet listing is not supported in Google Sheets mode.")


def read_sheet(
    sheet_name: str,
    path: Optional[Path] = None,
    session: Optional[Session] = None,
) -> pd.DataFrame:
    """Reads a single sheet from the master workbook into a DataFrame."""
    raise NotImplementedError("Reading individual workbook sheets is not supported in Google Sheets mode.")


def read_all_platform_sheets(
    path: Optional[Path] = None,
    session: Optional[Session] = None,
) -> Dict[str, pd.DataFrame]:
    """Reads WMS and all marketplace sheets from Google Sheets only.

    WMS remains the master source of truth.
    Excel workbook support is intentionally removed.
    """
    from services.google_sheet_reader import read_all_platform_tabs_as_dataframes

    # Directly use settings from config, which loads from .env
    from config.settings import GOOGLE_SHEET_ID, SERVICE_ACCOUNT_JSON_PATH
    spreadsheet_id, service_account_json_path = GOOGLE_SHEET_ID, SERVICE_ACCOUNT_JSON_PATH

    if not spreadsheet_id or not service_account_json_path:
        raise ValueError(
            "Google Sheets configuration (GOOGLE_SHEET_ID or SERVICE_ACCOUNT_JSON_PATH) is missing. "
            "Please create a .env file in the project root with these values."
        )

    platform_sheet_map = {platform: tab_name for platform, tab_name in PLATFORM_SHEETS.items()}
    return read_all_platform_tabs_as_dataframes(
        spreadsheet_id=spreadsheet_id,
        service_account_json_path=service_account_json_path,
        platform_sheet_map=platform_sheet_map,
    )




def resolve_column_mapping(
    platform: str,
    df: pd.DataFrame,
) -> Tuple[str, str]:
    """Resolves SKU and price columns using config, then auto-detection."""
    config_mapping = COLUMN_MAPPINGS.get(platform, {})
    suggested_sku, suggested_price = suggest_mappings(df)

    # Prefer config, then suggestion, then fallback to first/second column
    sku_col = config_mapping.get("sku") if config_mapping.get("sku") in df.columns else suggested_sku
    price_col = config_mapping.get("price") if config_mapping.get("price") in df.columns else suggested_price

    if not sku_col or sku_col not in df.columns:
        sku_col = df.columns[0]
    if not price_col or price_col not in df.columns:
        price_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]

    logger.info(f"Column mapping for {platform}: SKU='{sku_col}', Price='{price_col}'")
    return sku_col, price_col


def get_active_marketplace_sheets(sheets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """Returns marketplace sheets that contain data, excluding WMS."""
    return {
        platform: df
        for platform, df in sheets.items()
        if platform in SUPPORTED_PLATFORMS and len(df) > 0
    }
