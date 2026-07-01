import json
from typing import Dict

import gspread
import pandas as pd
from gspread.exceptions import APIError

from utils.helpers import get_logger

logger = get_logger("services.google_sheet_reader")


def _get_client(service_account_json_content: str) -> gspread.Client:
    """Create an authenticated gspread client from inline service account JSON."""
    if not service_account_json_content:
        raise ValueError(
            "Missing service account JSON content. "
            "Set CPRP_SERVICE_ACCOUNT_JSON_CONTENT in Streamlit secrets or environment variables."
        )

    try:
        credentials_info = json.loads(service_account_json_content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid service account JSON content: {exc}") from exc

    return gspread.service_account_from_dict(credentials_info)


def read_gsheet_tab_as_dataframe(
    spreadsheet_id: str,
    tab_name: str,
    service_account_json_content: str,
) -> pd.DataFrame:
    """Read a single worksheet tab into a Pandas DataFrame."""
    client = _get_client(service_account_json_content)

    try:
        ss = client.open_by_key(spreadsheet_id)
        ws = ss.worksheet(tab_name)
        records = ws.get_all_records()
        df = pd.DataFrame(records)
    except APIError as exc:
        raise RuntimeError(f"Google Sheets API error while reading tab '{tab_name}': {exc}") from exc

    if df.empty:
        return df

    df.columns = [str(col).strip() for col in df.columns]
    df = df.dropna(how="all")
    return df


def read_all_platform_tabs_as_dataframes(
    spreadsheet_id: str,
    service_account_json_content: str,
    platform_sheet_map: Dict[str, str],
) -> Dict[str, pd.DataFrame]:
    """Read WMS + marketplace tabs into {platform: dataframe}."""
    out: Dict[str, pd.DataFrame] = {}

    for platform, tab_name in platform_sheet_map.items():
        try:
            df = read_gsheet_tab_as_dataframe(
                spreadsheet_id=spreadsheet_id,
                tab_name=tab_name,
                service_account_json_content=service_account_json_content,
            )
            out[platform] = df
            logger.info(
                f"Loaded Google tab '{tab_name}' for platform '{platform}' with {len(df)} rows"
            )
        except Exception as exc:
            logger.error(
                f"Failed loading Google tab '{tab_name}' for platform '{platform}': {exc}"
            )

    return out
