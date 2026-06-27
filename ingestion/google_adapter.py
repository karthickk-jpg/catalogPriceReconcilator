from __future__ import annotations

from typing import Dict

import pandas as pd
from sqlalchemy.orm import Session

from services.spreadsheet_reader import read_all_platform_sheets


def load_google_platform_data(session: Session) -> Dict[str, pd.DataFrame]:
    """Ingestion adapter: Google Sheets -> {platform: DataFrame}.

    This keeps ingestion responsibilities out of the core engine.
    """

    return read_all_platform_sheets(session=session)

