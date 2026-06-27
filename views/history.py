import streamlit as st
import pandas as pd
from datetime import date, timedelta
from sqlalchemy import or_
from database.connection import get_db
from database.models import ReconciliationRun, ComparisonDetail, ValidationError, UploadedFile
from services.exporter import (
    build_full_report_csv,
    build_mismatch_report_csv,
    build_critical_report_csv,
    export_validation_errors_csv,
)
from utils.helpers import get_logger, format_currency, format_percent

logger = get_logger("views.history")

st.title("📜 Run History Audit")
st.write(
    "Browse all past reconciliation runs. Inspect validation errors, price mismatch details, "
    "and download reports for any historical run."
)
st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Filters
# ─────────────────────────────────────────────────────────────────────────────
with st.container():
    fc1, fc2, fc3 = st.columns([2, 2, 3])
    with fc1:
        date_from = st.date_input("From Date", value=date.today() - timedelta(days=90), key="hist_from")
    with fc2:
        date_to = st.date_input("To Date", value=date.today(), key="hist_to")
    with fc3:
        search_query = st.text_input(
            "Search by Run ID, Label, or Platform",
            placeholder="e.g. Amazon  /  Run #5",
            key="hist_search"
        )

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Load Runs
# ─────────────────────────────────────────────────────────────────────────────
with get_db() as db:
    runs_query = (
        db.query(ReconciliationRun)
        .filter(
            ReconciliationRun.run_date >= pd.Timestamp(date_from),
            ReconciliationRun.run_date <= pd.Timestamp(date_to) + pd.Timedelta(days=1),
            or_(ReconciliationRun.run_type != "live", ReconciliationRun.run_type.is_(None)),
        )
        .order_by(ReconciliationRun.run_date.desc())
        .all()
    )

    # Map run_id → list of platform names for display
    platform_map: dict[int, list[str]] = {}
    for run in runs_query:
        mkt_files = [
            f.platform for f in run.uploaded_files
            if f.file_type == "Marketplace"
        ]
        platform_map[run.id] = mkt_files

if not runs_query:
    st.info("No reconciliation runs found for the selected date range.")
    st.stop()

# Apply text search filter
def run_matches_search(run: ReconciliationRun, query: str) -> bool:
    if not query.strip():
        return True
    q = query.strip().lower()
    label = (run.run_name or "").lower()
    run_id_str = str(run.id)
    platforms = " ".join(platform_map.get(run.id, [])).lower()
    return q in label or q in run_id_str or q in platforms

filtered_runs = [r for r in runs_query if run_matches_search(r, search_query)]

st.subheader(f"Showing {len(filtered_runs)} run(s)")

# ─────────────────────────────────────────────────────────────────────────────
# Render Each Run Card
# ─────────────────────────────────────────────────────────────────────────────
STATUS_COLOR = {
    "Completed":  "🟢",
    "Failed":     "🔴",
    "Processing": "🟡",
    "Pending":    "⚪",
}

for run in filtered_runs:
    platforms_str = ", ".join(platform_map.get(run.id, [])) or "N/A"
    status_icon   = STATUS_COLOR.get(run.status, "⚪")
    match_rate    = (
        f"{run.exact_matches / run.total_skus * 100:.1f}%"
        if run.total_skus > 0 else "N/A"
    )
    expander_label = (
        f"{status_icon} Run #{run.id} "
        f"— {run.run_name or 'Unlabelled'} "
        f"| {run.run_date.strftime('%Y-%m-%d %H:%M')} "
        f"| Platforms: {platforms_str} "
        f"| SKUs: {run.total_skus:,} | Match Rate: {match_rate}"
    )

    with st.expander(expander_label, expanded=False):
        # ── KPI mini-row ──────────────────────────────────────────────
        mc1, mc2, mc3, mc4, mc5 = st.columns(5)
        mc1.metric("Total SKUs",      f"{run.total_skus:,}")
        mc2.metric("Exact Matches",   f"{run.exact_matches:,}")
        mc3.metric("Mismatches",      f"{run.mismatches:,}")
        mc4.metric("Critical",        f"{run.critical_mismatches:,}")
        mc5.metric("Missing (WMS/Mkt)", f"{run.missing_wms + run.missing_marketplace:,}")

        if run.error_message:
            st.error(f"Run Error: {run.error_message}")

        st.write("---")

        # ── Tabs: Comparison Details | Validation Errors | Downloads ──
        tab_det, tab_err, tab_dl = st.tabs(["Comparison Details", "Validation Errors", "Downloads"])

        # ── Comparison Details Tab ────────────────────────────────────
        with tab_det:
            sev_filter = st.multiselect(
                "Filter by Severity",
                options=["Exact Match", "Low Mismatch", "Medium Mismatch",
                         "Critical Mismatch", "Missing in WMS", "Missing in Marketplace"],
                default=[],
                key=f"sev_filter_{run.id}",
                placeholder="All Severities"
            )
            plat_filter = st.multiselect(
                "Filter by Platform",
                options=platform_map.get(run.id, []),
                default=[],
                key=f"plat_filter_{run.id}",
                placeholder="All Platforms"
            )

            with get_db() as db2:
                detail_q = db2.query(ComparisonDetail).filter(
                    ComparisonDetail.run_id == run.id
                )
                if sev_filter:
                    detail_q = detail_q.filter(ComparisonDetail.severity.in_(sev_filter))
                if plat_filter:
                    detail_q = detail_q.filter(ComparisonDetail.marketplace.in_(plat_filter))
                details = detail_q.limit(2000).all()

            if details:
                det_df = pd.DataFrame([{
                    "SKU":           d.sku,
                    "Product Name":  d.product_name,
                    "Brand":         d.brand,
                    "Category":      d.category,
                    "Platform":      d.marketplace,
                    "WMS Price":     format_currency(d.wms_price),
                    "Mkt Price":     format_currency(d.marketplace_price),
                    "Diff":          format_currency(d.price_diff),
                    "Diff %":        format_percent(d.percent_diff),
                    "Severity":      d.severity,
                    "Status":        d.status,
                } for d in details])
                st.dataframe(det_df, use_container_width=True, hide_index=True)
                st.caption(f"Showing up to 2,000 rows. Use Downloads tab for full export.")
            else:
                st.info("No comparison detail records found with selected filters.")

        # ── Validation Errors Tab ─────────────────────────────────────
        with tab_err:
            with get_db() as db3:
                errors = (
                    db3.query(ValidationError)
                    .filter(ValidationError.run_id == run.id)
                    .all()
                )
            if errors:
                err_df = pd.DataFrame([{
                    "Error Type":  e.error_type,
                    "Row #":       e.row_number,
                    "SKU":         e.sku,
                    "Column":      e.column_name,
                    "Message":     e.error_message,
                } for e in errors])
                st.dataframe(err_df, use_container_width=True, hide_index=True)
            else:
                st.success("No validation errors were logged for this run.")

        # ── Downloads Tab ─────────────────────────────────────────────
        with tab_dl:
            # Fetch full comparison rows for this run for export
            with get_db() as db4:
                all_details = db4.query(ComparisonDetail).filter(
                    ComparisonDetail.run_id == run.id
                ).all()
                all_errors  = db4.query(ValidationError).filter(
                    ValidationError.run_id == run.id
                ).all()

            comp_dicts = [{
                "sku":               d.sku,
                "product_name":      d.product_name,
                "brand":             d.brand,
                "category":          d.category,
                "marketplace":       d.marketplace,
                "wms_price":         d.wms_price,
                "marketplace_price": d.marketplace_price,
                "price_diff":        d.price_diff,
                "percent_diff":      d.percent_diff,
                "severity":          d.severity,
                "status":            d.status,
            } for d in all_details]

            err_dicts = [{
                "error_type":   e.error_type,
                "row_number":   e.row_number,
                "sku":          e.sku,
                "column_name":  e.column_name,
                "error_message":e.error_message,
            } for e in all_errors]

            base_filename = f"CPRP_Run{run.id}_{run.run_date.strftime('%Y%m%d')}"
            dl1, dl2, dl3, dl4, dl5 = st.columns(5)

            with dl1:
                st.download_button(
                    "📥 Full Report (CSV)",
                    data=build_full_report_csv(comp_dicts),
                    file_name=f"{base_filename}_Full.csv",
                    mime="text/csv",
                    key=f"dl_full_csv_{run.id}"
                )
            with dl2:
                st.download_button(
                    "📥 Mismatch (CSV)",
                    data=build_mismatch_report_csv(comp_dicts),
                    file_name=f"{base_filename}_Mismatch.csv",
                    mime="text/csv",
                    key=f"dl_mis_csv_{run.id}"
                )
            with dl3:
                st.download_button(
                    "📥 Critical (CSV)",
                    data=build_critical_report_csv(comp_dicts),
                    file_name=f"{base_filename}_Critical.csv",
                    mime="text/csv",
                    key=f"dl_crit_csv_{run.id}"
                )
            with dl5:
                if err_dicts:
                    st.download_button(
                        "📥 Validation Errors (CSV)",
                        data=export_validation_errors_csv(err_dicts),
                        file_name=f"{base_filename}_ValidationErrors.csv",
                        mime="text/csv",
                        key=f"dl_err_csv_{run.id}"
                    )
                else:
                    st.write("_No validation errors to export_")

        st.write("---")

        # ── Delete Run ────────────────────────────────────────────────
        with st.expander("⚠️ Danger Zone — Delete This Run"):
            st.warning(
                f"Deleting Run #{run.id} will permanently remove all comparison details, "
                "validation errors, and uploaded file records from the database."
            )
            confirm_key = f"confirm_del_{run.id}"
            if st.checkbox("I understand and want to delete this run permanently.", key=confirm_key):
                if st.button("🗑️ Delete Run", type="primary", key=f"del_btn_{run.id}"):
                    with get_db() as db5:
                        target = db5.query(ReconciliationRun).get(run.id)
                        if target:
                            db5.delete(target)
                            db5.commit()
                    st.success(f"Run #{run.id} deleted successfully.")
                    st.rerun()
