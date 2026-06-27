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
    SKU_KEYWORDS,
    PRICE_KEYWORDS,
)

from utils.helpers import get_logger

logger = get_logger("services.spreadsheet_reader")


def suggest_mappings(df: pd.DataFrame) -> Tuple[Optional[str], Optional[str]]:
    """Scans the DataFrame columns and attempts to auto-suggest column names 
    representing the SKU and Price based on keyword settings.
    """
    sku_col = None
    price_col = None

    # Normalise headers to lowercase for keyword matching
    columns = list(df.columns)
    lower_columns = [col.lower().strip() for col in columns]

    # Find SKU Column suggestion
    for kw in SKU_KEYWORDS:
        if kw in lower_columns:
            idx = lower_columns.index(kw)
            sku_col = columns[idx]
            break
    
    # If no exact match, look for contains matching for SKU
    if not sku_col:
        for col in columns:
            col_lower = col.lower()
            if any(kw in col_lower for kw in SKU_KEYWORDS if len(kw) > 2):
                sku_col = col
                break

    # Find Price Column suggestion
    for kw in PRICE_KEYWORDS:
        if kw in lower_columns:
            idx = lower_columns.index(kw)
            price_col = columns[idx]
            break

    # If no exact match, look for contains matching for Price
    if not price_col:
        for col in columns:
            col_lower = col.lower()
            if any(kw in col_lower for kw in PRICE_KEYWORDS if len(kw) > 2):
                price_col = col
                break

    logger.info(f"Auto-mapping suggestions: SKU='{sku_col}', Price='{price_col}'")
    return sku_col, price_col


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
