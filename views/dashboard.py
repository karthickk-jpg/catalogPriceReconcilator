import streamlit as st
import pandas as pd
from datetime import datetime
import requests

from config.settings import SUPPORTED_PLATFORMS
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

st.set_page_config(layout="wide")

st.title("Catalog Price Validation Portal")
# st.caption("Live comparison of WMS prices against marketplaces")


def _get_last_refreshed_ts() -> str:
    ts = st.session_state.get("last_refreshed_ts")
    return ts.strftime("%Y-%m-%d %H:%M:%S") if ts else "Not yet"


def get_live_data():
    """UI-only: calls FastAPI /reconcile and returns JSON payload."""
    try:
        resp = requests.post("http://127.0.0.1:8004/reconcile", json={"run_type": "historical"}, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        comparison_rows = data.get("comparison_rows") or data.get("comparison") or data.get("comparison_df")
        data["comparison_df"] = pd.DataFrame(comparison_rows) if comparison_rows else pd.DataFrame()
        return data
    except Exception as exc:
        logger.error(f"API reconcile failed: {exc}", exc_info=True)
        return {"success": False, "message": str(exc), "run_summary": {}, "comparison_df": pd.DataFrame()}


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


def _download_for(platform: str, col_key: str, mismatch_df: pd.DataFrame) -> None:
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
        f"Download {platform} Mismatches",
        data=_to_csv_bytes(out),
        file_name=f"CPRP_Mismatches_{platform}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        key=col_key,
        use_container_width=True,
    )


header_left, header_right = st.columns([3, 1])
with header_left:
    # st.markdown("#### Marketplace reconciliation powered by Google Sheets")
    st.write(f"Last Updated: {_get_last_refreshed_ts()}")
with header_right:
    if st.button("Refresh dashboard", type="secondary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

try:
    live_data_result = get_live_data()
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
        mismatch_df = mismatch_df.sort_values(["marketplace", "sku", "_severity_rank"], ascending=[True, True, False])
        mismatch_df = mismatch_df.drop_duplicates(subset=["marketplace", "sku"], keep="first")
        mismatch_df = mismatch_df.drop(columns=["_severity_rank"])
    platform_mismatch_counts = {
        p: int((mismatch_df["marketplace"] == p).sum()) for p in SUPPORTED_PLATFORMS
    }
    total_mismatches = int(len(mismatch_df))
    total_design_nos = int(run_summary.get("total_skus", 0))
except Exception as exc:
    st.exception(exc)

summary_platforms = list(SUPPORTED_PLATFORMS)
summary_cols = st.columns(len(summary_platforms) + 2)
with summary_cols[0]:
    _render_kpi_card("Total Design Nos", total_design_nos)
for idx, platform in enumerate(summary_platforms, start=1):
    with summary_cols[idx]:
        _render_kpi_card(f"{platform} Mismatches", platform_mismatch_counts.get(platform, 0))
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

export_cols = st.columns(len(SUPPORTED_PLATFORMS))
for idx, platform in enumerate(SUPPORTED_PLATFORMS):
    with export_cols[idx]:
        st.markdown(f"**{platform}**")
        count = platform_mismatch_counts.get(platform, 0)
        st.write(f"{count:,} mismatches")
        if count > 0:
            _download_for(platform, f"dl_{platform.lower()}", mismatch_df)
        else:
            st.caption("No export available")

if filtered.empty:
    st.info("No records found for the selected filters. Adjust platform or search criteria to view data.")
else:
    display_df = _to_display_df(filtered)
    st.dataframe(display_df, use_container_width=True)
