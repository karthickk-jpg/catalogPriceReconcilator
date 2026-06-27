import pandas as pd
from typing import List, Dict, Any, Tuple
from utils.helpers import get_logger

logger = get_logger("services.validator")


def validate_dataframe(
    df: pd.DataFrame, 
    sku_col: str, 
    price_col: str, 
    file_type: str, 
    platform: str
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Validates the input DataFrame for structural and price data anomalies.
    
    Checks performed:
    - Missing required columns
    - Blank / Missing SKUs
    - Duplicate SKUs
    - Blank / Missing Prices
    - Invalid Price Formats (non-numeric)
    - Negative Prices
    
    Returns:
        A tuple of:
        - summary (dict): Counts of rows checked and counts of errors.
        - errors (list of dict): Individual error records matching ValidationError columns.
    """
    logger.info(f"Validating {file_type} file for platform '{platform}' using columns SKU='{sku_col}', Price='{price_col}'")
    
    errors = []
    total_rows = len(df)
    
    summary = {
        "total_rows": total_rows,
        "critical_error": False,
        "duplicate_skus": 0,
        "blank_skus": 0,
        "blank_prices": 0,
        "invalid_prices": 0,
        "negative_prices": 0,
        "missing_columns": 0
    }

    # 1. Check if mapped columns exist
    if sku_col not in df.columns:
        errors.append({
            "error_type": "Missing Column",
            "row_number": None,
            "sku": None,
            "column_name": sku_col,
            "error_message": f"Required SKU column '{sku_col}' not found in the uploaded file."
        })
        summary["critical_error"] = True
        summary["missing_columns"] += 1
        
    if price_col not in df.columns:
        errors.append({
            "error_type": "Missing Column",
            "row_number": None,
            "sku": None,
            "column_name": price_col,
            "error_message": f"Required Price column '{price_col}' not found in the uploaded file."
        })
        summary["critical_error"] = True
        summary["missing_columns"] += 1

    if summary["critical_error"]:
        logger.warning(f"Critical schema mapping validation failures for {platform} file. Halting further checks.")
        return summary, errors

    # Track duplicates
    seen_skus = set()
    duplicate_skus = set()
    
    # 2. Iterate and validate each row
    for index, row in df.iterrows():
        # Excel rows are 1-based, plus header row, so row index + 2
        row_num = index + 2
        
        raw_sku = row[sku_col]
        raw_price = row[price_col]
        
        sku_str = str(raw_sku).strip() if pd.notna(raw_sku) else ""
        
        # Check Blank SKU
        if not sku_str or sku_str.lower() in ["nan", "null"]:
            errors.append({
                "error_type": "Missing SKU",
                "row_number": row_num,
                "sku": None,
                "column_name": sku_col,
                "error_message": "SKU value is blank or null."
            })
            summary["blank_skus"] += 1
            continue  # Skip further checks for this row since SKU is invalid
            
        # Check Duplicate SKU
        if sku_str in seen_skus:
            errors.append({
                "error_type": "Duplicate SKU",
                "row_number": row_num,
                "sku": sku_str,
                "column_name": sku_col,
                "error_message": f"Duplicate SKU '{sku_str}' found in row {row_num}."
            })
            summary["duplicate_skus"] += 1
            duplicate_skus.add(sku_str)
        else:
            seen_skus.add(sku_str)

        # Check Blank Price
        if pd.isna(raw_price) or str(raw_price).strip() == "":
            errors.append({
                "error_type": "Blank Price",
                "row_number": row_num,
                "sku": sku_str,
                "column_name": price_col,
                "error_message": f"Price is missing or blank for SKU '{sku_str}'."
            })
            summary["blank_prices"] += 1
            continue

        # Check Price Format (convert to float)
        price_val = None
        try:
            # Clean currency symbols and commas if present
            cleaned_price_str = str(raw_price).replace("₹", "").replace("$", "").replace(",", "").strip()
            price_val = float(cleaned_price_str)
        except ValueError:
            errors.append({
                "error_type": "Invalid Price Format",
                "row_number": row_num,
                "sku": sku_str,
                "column_name": price_col,
                "error_message": f"Invalid price format '{raw_price}' for SKU '{sku_str}' (cannot convert to decimal number)."
            })
            summary["invalid_prices"] += 1
            continue

        # Check Negative Price
        if price_val < 0:
            errors.append({
                "error_type": "Invalid Price Format",
                "row_number": row_num,
                "sku": sku_str,
                "column_name": price_col,
                "error_message": f"Negative price value '{price_val}' detected for SKU '{sku_str}'."
            })
            summary["negative_prices"] += 1

    logger.info(f"Completed validation: {len(errors)} warnings/errors found.")
    return summary, errors
