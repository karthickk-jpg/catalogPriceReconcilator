import io
import csv
from typing import List, Dict, Any, Optional

from utils.helpers import get_logger

logger = get_logger("services.exporter")


# Simple CSV/bytes exporters only — Excel exports removed for Google-only mode
COMPARISON_COLUMNS = [
    ("Design No", "sku"),
    ("Product Name", "product_name"),
    ("Brand", "brand"),
    ("Category", "category"),
    ("Platform", "marketplace"),
    ("WMS Price", "wms_price"),
    ("Marketplace Price", "marketplace_price"),
    ("Difference", "price_diff"),
    ("Difference %", "percent_diff"),
]

ERROR_COLUMNS = [
    ("Error Type", "error_type"),
    ("Row Number", "row_number"),
    ("Design No", "sku"),
    ("Column", "column_name"),
    ("Error Message", "error_message"),
]


def _filter_rows(comparison_rows: List[Dict], severity_filter: Optional[List[str]] = None) -> List[Dict]:
    if severity_filter is None:
        return comparison_rows
    return [r for r in comparison_rows if r.get("severity") in severity_filter]


def _build_comparison_table(rows: List[Dict]) -> tuple:
    headers = [col[0] for col in COMPARISON_COLUMNS]
    field_keys = [col[1] for col in COMPARISON_COLUMNS]
    data_rows = []
    for row in rows:
        data_rows.append([row.get(k) for k in field_keys])
    return headers, data_rows


def export_csv(comparison_rows: List[Dict], severity_filter: Optional[List[str]] = None) -> bytes:
    logger.info(f"Generating CSV export: filter={severity_filter}")
    filtered = _filter_rows(comparison_rows, severity_filter)
    headers, data_rows = _build_comparison_table(filtered)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(data_rows)
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


def export_validation_errors_csv(validation_errors: List[Dict]) -> bytes:
    headers = [col[0] for col in ERROR_COLUMNS]
    field_keys = [col[1] for col in ERROR_COLUMNS]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for err in validation_errors:
        writer.writerow([err.get(k) for k in field_keys])
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


def build_mismatch_report_csv(rows):
    return export_csv(rows, severity_filter=None)


def build_full_report_csv(rows):
    return export_csv(rows, severity_filter=None)


def build_critical_report_csv(rows):
    return export_csv(rows, severity_filter=["Critical Mismatch"])
