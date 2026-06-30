import os
from dataclasses import dataclass
from typing import Dict

import pandas as pd
import gspread
from gspread.exceptions import APIError

from utils.helpers import get_logger

logger = get_logger("services.google_sheet_reader")

DEFAULT_TIMEOUT_SEC = 60





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



