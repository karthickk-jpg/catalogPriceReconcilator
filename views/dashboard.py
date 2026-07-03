from datetime import datetime

import pandas as pd
import streamlit as st

from config.settings import SUPPORTED_PLATFORMS
from services.reconciliation import run_live_reconciliation
from utils.helpers import get_logger

logger = get_logger("views.dashboard")

st.markdown(
    """
    <style>
      :root { --bg: #F5F7FA; --card: #FFFFFF; --text: #101828; --muted: #667085; --border: rgba(16,24,40,0.10); --shadow: 0 1px 2px rgba(16,24,40,0.06); }

      body { background: var(--bg); }
      section.main > div { padding-top: 6px; }
      h1, .stTitle { margin-bottom: 0.25rem; }

      .kpi-card {
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 10px 12px;
        background: var(--card);
        box-shadow: var(--shadow);
        min-height: 58px;
      }
      .kpi-title { font-size: 12px; color: var(--muted); margin-bottom: 4px; font-weight: 600; }
      .kpi-value { font-size: 22px; font-weight: 700; color: var(--text); line-height: 1.1; }

      div[data-testid="stDataFrame"] { border-radius: 8px; }
      section[data-testid="stSidebar"] { width: 240px; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _get_last_refreshed_ts() -> str:
    ts = st.session_state.get("last_refreshed_ts")
    return ts.strftime("%Y-%m-%d %H:%M:%S") if ts else "Not yet"


@st.cache_data(show_spinner=False, ttl=60, max_entries=1)
def _get_cached_live_data():
    """Reuse the last successful reconciliation result for a short window."""
    return run_live_reconciliation()


def _render_kpi_card(title: str, value: int) -> None:
    st.markdown(
        f"<div class='kpi-card'><div class='kpi-title'>{title}</div><div class='kpi-value'>{value:,}</div></div>",
        unsafe_allow_html=True,
    )


def _to_display_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["Design No", "Channel", "WMS Price", "Channel price"])
    return df[["sku", "marketplace", "wms_price", "marketplace_price"]].rename(
        columns={
            "sku": "Design No",
            "marketplace": "Channel",
            "wms_price": "WMS Price",
            "marketplace_price": "Channel price",
        }
    )


def _to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def _download_for(platform: str, col_key: str, mismatch_df: pd.DataFrame, label: str | None = None) -> None:
    if mismatch_df.empty:
        return
    dfp = mismatch_df[mismatch_df["marketplace"] == platform]
    out = dfp[["sku", "marketplace", "wms_price", "marketplace_price"]].rename(
        columns={
            "sku": "Design No",
            "marketplace": "Channel",
            "wms_price": "WMS Price",
            "marketplace_price": "Channel price",
        }
    )
    st.download_button(
        label or f"Download {platform} Mismatches",
        data=_to_csv_bytes(out),
        file_name=f"CPRP_Mismatches_{platform}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        key=col_key,
        use_container_width=True,
    )


def render_dashboard() -> None:
    st.title("Catalog Price Validation Portal")

    header_left, header_right = st.columns([3, 1])
    with header_left:
        st.write(f"Last Updated: {_get_last_refreshed_ts()}")
    with header_right:
        if st.button("Refresh dashboard", type="secondary", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    try:
        live_data_result = _get_cached_live_data()
        if live_data_result.get("success"):
            st.session_state["last_refreshed_ts"] = datetime.now()
        else:
            st.error(live_data_result.get("message", "An unknown error occurred."))
            st.stop()

        run_summary = live_data_result.get("run_summary", {})
        comparison_df = live_data_result.get("comparison_df", pd.DataFrame())
        price_mismatch_severities = ["Low Mismatch", "Medium Mismatch", "Critical Mismatch"]
        mismatch_df = (
            comparison_df[comparison_df["severity"].isin(price_mismatch_severities)].copy()
            if not comparison_df.empty
            else pd.DataFrame()
        )
        if not mismatch_df.empty:
            severity_rank = {"Low Mismatch": 1, "Medium Mismatch": 2, "Critical Mismatch": 3}
            mismatch_df = mismatch_df.copy()
            mismatch_df["_severity_rank"] = mismatch_df["severity"].map(severity_rank)
            mismatch_df = mismatch_df.sort_values(
                ["marketplace", "sku", "_severity_rank"], ascending=[True, True, False]
            )
            mismatch_df = mismatch_df.drop_duplicates(subset=["marketplace", "sku"], keep="first")
            mismatch_df = mismatch_df.drop(columns=["_severity_rank"])
        platform_mismatch_counts = {
            p: int((mismatch_df["marketplace"] == p).sum()) for p in SUPPORTED_PLATFORMS
        }
        total_mismatches = int(len(mismatch_df))
        total_design_nos = int(run_summary.get("total_skus", 0))
    except Exception as exc:
        logger.exception("Dashboard render failed")
        st.exception(exc)
        return

    summary_platforms = list(SUPPORTED_PLATFORMS)
    summary_cols = st.columns(len(summary_platforms) + 2)
    with summary_cols[0]:
        _render_kpi_card("Total Design Nos", total_design_nos)
    for idx, platform in enumerate(summary_platforms, start=1):
        with summary_cols[idx]:
            platform_count = platform_mismatch_counts.get(platform, 0)
            row_col, button_col = st.columns([4, 1])
            with row_col:
                _render_kpi_card(f"{platform} Mismatches", platform_count)
            with button_col:
                if platform_count > 0:
                    _download_for(platform, f"dl_{platform.lower()}", mismatch_df, label="⬇")
                else:
                    st.write("")
    with summary_cols[len(summary_platforms) + 1]:
        _render_kpi_card("Total Mismatches", total_mismatches)

    with st.container():
        f1, f2, f3 = st.columns([2, 3, 2])
        with f1:
            platform_filter = st.selectbox("Platform", options=["All"] + SUPPORTED_PLATFORMS, index=0)
        with f2:
            search_design_no = st.text_input("Design No Search")
        with f3:
            show_mismatches_only = st.toggle("Show mismatches only", value=True)

    base_df = mismatch_df if show_mismatches_only else comparison_df
    filtered = base_df.copy()
    if platform_filter != "All":
        filtered = filtered[filtered["marketplace"] == platform_filter]
    query = search_design_no.strip().lower()
    if query:
        filtered = filtered[filtered["sku"].astype(str).str.lower().str.contains(query, na=False)]

    st.markdown("### Mismatch Details" if show_mismatches_only else "### All Reconciliation Results")

    if filtered.empty:
        st.info("No records found for the selected filters. Adjust platform or search criteria to view data.")
    else:
        display_df = _to_display_df(filtered)
        st.dataframe(display_df.to_dict("records"), use_container_width=True)
