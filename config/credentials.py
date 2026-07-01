import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

_BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_BASE_DIR / ".env")


def _get_secret(key: str) -> Optional[str]:
    """Read from Streamlit secrets first, then environment variables."""
    try:
        import streamlit as st

        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.getenv(key)


def _strip_quotes(value: str) -> str:
    return value.strip().strip('"').strip("'")


def get_google_sheet_id() -> Optional[str]:
    value = _get_secret("CPRP_GOOGLE_SHEET_ID")
    return _strip_quotes(value) if value else None


def get_service_account_json_content() -> Optional[str]:
    content = _get_secret("CPRP_SERVICE_ACCOUNT_JSON_CONTENT")
    if content:
        return content

    # Local development fallback: read from a service account JSON file.
    path_value = _get_secret("CPRP_SERVICE_ACCOUNT_JSON_PATH")
    candidates = []
    if path_value:
        path = Path(_strip_quotes(path_value))
        candidates.append(path if path.is_absolute() else _BASE_DIR / path)
    candidates.append(_BASE_DIR / "credentials" / "service_account.json")

    for file_path in candidates:
        if file_path.is_file():
            return file_path.read_text(encoding="utf-8")

    return None
