from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import pandas as pd

# Core engine is framework/UI agnostic — no Streamlit or external service imports.
from services.validator import validate_dataframe
from services.comparer import reconcile_prices


@dataclass(frozen=True)
class ReconciliationInput:
    """Pure-engine input for reconciliation.

    This object is intentionally UI/DB/API/framework agnostic.
    """

    wms_df: pd.DataFrame
    wms_sku_col: str
    wms_price_col: str

    marketplace_datasets: Dict[str, Tuple[pd.DataFrame, str, str]]
    low_threshold: float
    medium_threshold: float


@dataclass(frozen=True)
class ReconciliationEngineResult:
    success: bool
    message: str
    run_summary: Dict[str, Any] | None = None
    comparison_df: pd.DataFrame | None = None
    warnings: List[str] | None = None


def run_reconciliation_engine(inp: ReconciliationInput) -> ReconciliationEngineResult:
    """Single orchestration function for the reconciliation pipeline.

    IMPORTANT:
    - This calls existing validate_dataframe/comparer logic.
    - It does not call DB or Streamlit.
    """

    warnings: List[str] = []

    # Validate WMS
    wms_summary, wms_errors = validate_dataframe(
        inp.wms_df, inp.wms_sku_col, inp.wms_price_col, file_type="WMS", platform="WMS"
    )
    if wms_summary.get("critical_error"):
        return ReconciliationEngineResult(
            success=False,
            message="WMS sheet has critical schema errors. Check column mappings.",
            warnings=[e.get("error_message", "") for e in wms_errors[:5]],
        )

    # Validate marketplaces
    for platform, (mkt_df, sku_col, price_col) in inp.marketplace_datasets.items():
        summary, errors = validate_dataframe(
            mkt_df, sku_col, price_col, file_type="Marketplace", platform=platform
        )
        if summary.get("critical_error"):
            warnings.append(f"{platform}: critical schema error — skipped")
            continue
        # Non-critical errors are still logged as warnings for UI consumption.
        if errors:
            warnings.append(f"{platform}: schema warnings — {len(errors)} issue(s)")

    # Reconcile
    run_summary, comparison_rows = reconcile_prices(
        inp.wms_df,
        inp.wms_sku_col,
        inp.wms_price_col,
        inp.marketplace_datasets,
        inp.low_threshold,
        inp.medium_threshold,
    )

    return ReconciliationEngineResult(
        success=True,
        message=(
            f"Live data loaded — {run_summary.get('total_skus', 0):,} SKUs, "
            f"{run_summary.get('mismatches', 0):,} mismatches across {len(inp.marketplace_datasets)} platform(s)."
        ),
        run_summary=run_summary,
        comparison_df=pd.DataFrame(comparison_rows),
        warnings=warnings,
    )

