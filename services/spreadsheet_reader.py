from typing import Dict, Optional, Tuple

import pandas as pd

from config.credentials import get_google_sheet_id, get_service_account_json_content
from config.settings import (
    COLUMN_MAPPINGS,
    PLATFORM_SHEETS,
    SKU_KEYWORDS,
    PRICE_KEYWORDS,
)
from utils.helpers import get_logger

logger = get_logger("services.spreadsheet_reader")


def suggest_mappings(df: pd.DataFrame) -> Tuple[Optional[str], Optional[str]]:
    """Auto-suggest SKU and price columns based on keyword settings."""
    sku_col = None
    price_col = None

    columns = list(df.columns)
    lower_columns = [col.lower().strip() for col in columns]

    for kw in SKU_KEYWORDS:
        if kw in lower_columns:
            idx = lower_columns.index(kw)
            sku_col = columns[idx]
            break

    if not sku_col:
        for col in columns:
            col_lower = col.lower()
            if any(kw in col_lower for kw in SKU_KEYWORDS if len(kw) > 2):
                sku_col = col
                break

    for kw in PRICE_KEYWORDS:
        if kw in lower_columns:
            idx = lower_columns.index(kw)
            price_col = columns[idx]
            break

    if not price_col:
        for col in columns:
            col_lower = col.lower()
            if any(kw in col_lower for kw in PRICE_KEYWORDS if len(kw) > 2):
                price_col = col
                break

    logger.info(f"Auto-mapping suggestions: SKU='{sku_col}', Price='{price_col}'")
    return sku_col, price_col


def read_all_platform_sheets() -> Dict[str, pd.DataFrame]:
    """Read WMS and all marketplace sheets from Google Sheets."""
    from services.google_sheet_reader import read_all_platform_tabs_as_dataframes

    spreadsheet_id = get_google_sheet_id()
    service_account_json_content = get_service_account_json_content()

    if not spreadsheet_id or not service_account_json_content:
        raise ValueError(
            "Google Sheets configuration is missing. "
            "Set CPRP_GOOGLE_SHEET_ID and CPRP_SERVICE_ACCOUNT_JSON_CONTENT "
            "in Streamlit secrets or environment variables."
        )

    platform_sheet_map = dict(PLATFORM_SHEETS)
    return read_all_platform_tabs_as_dataframes(
        spreadsheet_id=spreadsheet_id,
        service_account_json_content=service_account_json_content,
        platform_sheet_map=platform_sheet_map,
    )


def resolve_column_mapping(platform: str, df: pd.DataFrame) -> Tuple[str, str]:
    """Resolve SKU and price columns using config, then auto-detection."""
    config_mapping = COLUMN_MAPPINGS.get(platform, {})
    suggested_sku, suggested_price = suggest_mappings(df)

    sku_col = config_mapping.get("sku") if config_mapping.get("sku") in df.columns else suggested_sku
    price_col = (
        config_mapping.get("price") if config_mapping.get("price") in df.columns else suggested_price
    )

    if not sku_col or sku_col not in df.columns:
        sku_col = df.columns[0]
    if not price_col or price_col not in df.columns:
        price_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]

    logger.info(f"Column mapping for {platform}: SKU='{sku_col}', Price='{price_col}'")
    return sku_col, price_col
