import pandas as pd
from typing import Tuple, Optional
from config.settings import SKU_KEYWORDS, PRICE_KEYWORDS
from utils.helpers import get_logger

logger = get_logger("services.file_reader")


def read_file(file_data, filename: str) -> pd.DataFrame:
    """Reads CSV files into a Pandas DataFrame.
    Normalizes column headers by stripping whitespace.
    """
    logger.info(f"Attempting to read file: {filename}")
    ext = filename.split(".")[-1].lower()

    try:
        if ext == "csv":
            # Read CSV file
            df = pd.read_csv(file_data)
        else:
            raise ValueError(f"Unsupported file format: .{ext}. Only CSV is supported in Google Sheets mode.")
        
        # Clean column headers
        df.columns = [str(col).strip() for col in df.columns]
        logger.info(f"Successfully loaded file '{filename}' with {len(df)} rows and {len(df.columns)} columns.")
        return df

    except Exception as e:
        logger.error(f"Error reading file '{filename}': {str(e)}", exc_info=True)
        raise e


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
