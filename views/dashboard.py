import streamlit as st
import pandas as pd
from datetime import datetime
import requests

from config.settings import SUPPORTED_PLATFORMS
from services.google_sheet_reader import debug_google_connection
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

st.title("Catalog Price Reconciliation Portal")
st.caption("Live comparison of WMS prices against marketplaces")


def _get_last_refreshed_ts() -> str:
    ts = st.session_state.get("last_refreshed_ts")
    return ts.strftime("%Y-%m-%d %H:%M:%S") if ts else "Not yet"


@st.cache_data(show_spinner="Refreshing via API...")
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
        return pd.DataFrame(columns=["Design No", "Marketplace", "WMS Price", "Marketplace Price", "Difference"])
    return df[["sku", "marketplace", "wms_price", "marketplace_price", "price_diff"]].rename(
        columns={
            "sku": "Design No",
            "marketplace": "Marketplace",
            "wms_price": "WMS Price",
            "marketplace_price": "Marketplace Price",
            "price_diff": "Difference",
        }
    )


def _to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def _download_for(platform: str, col_key: str, mismatch_df: pd.DataFrame) -> None:
    if mismatch_df.empty:
        return
    dfp = mismatch_df[mismatch_df["marketplace"] == platform]
    out = dfp[["sku", "marketplace", "wms_price", "marketplace_price", "price_diff", "percent_diff"]].rename(
        columns={
            "sku": "Design No",
            "marketplace": "Marketplace",
            "wms_price": "WMS Price",
            "marketplace_price": "Marketplace Price",
            "price_diff": "Difference",
            "percent_diff": "Difference %",
        }
    )
    st.download_button(
        f"Download {platform} Mismatches",
        data=_to_csv_bytes(out),
        file_name=f"CPRP_Live_Mismatches_{platform}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        key=col_key,
        use_container_width=True,
    )


left, right = st.columns([2, 1])
with left:
    st.write(f"Last Updated: {_get_last_refreshed_ts()}")
with right:
    st.write("Google Sheets Status: Connected")

st.session_state.setdefault("_google_debug_clicked", False)
cols = st.columns([2, 1])
with cols[0]:
    if st.button("Debug Google Connection", type="secondary", use_container_width=True):
        st.session_state["_google_debug_clicked"] = True

if st.session_state["_google_debug_clicked"]:
    st.subheader("🧪 Debug Google Connection")
    with st.spinner("Connecting to Google Sheets..."):
        dbg_payload = debug_google_connection()

    if dbg_payload.get("success"):
        st.success("Google connection successful")
        st.write(f"Sheet ID: {dbg_payload.get('sheet_id')}")
        st.write(f"Service account email: {dbg_payload.get('service_account_email') or 'N/A'}")
        st.write("Worksheets:")
        st.code("\n".join(dbg_payload.get("worksheets") or []))
        st.write("Row counts:")
        st.json(dbg_payload.get("row_counts") or {})
        with st.expander("WMS sample (first 5 rows)"):
            st.dataframe(pd.DataFrame(dbg_payload.get("wms_sample") or []), use_container_width=True)
        with st.expander("Amazon sample (first 5 rows)"):
            st.dataframe(pd.DataFrame(dbg_payload.get("amazon_sample") or []), use_container_width=True)
    else:
        st.error(dbg_payload.get("error", "Google debug failed"))

if st.button("Refresh", type="secondary"):
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
    platform_mismatch_counts = {
        p: int((mismatch_df["marketplace"] == p).sum()) for p in SUPPORTED_PLATFORMS
    }
    total_mismatches = int(len(mismatch_df))
    total_design_nos = int(run_summary.get("total_skus", 0))
except Exception as exc:
    st.exception(exc)

c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    _render_kpi_card("Total Design Nos", total_design_nos)
with c2:
    _render_kpi_card("Amazon Mismatches", platform_mismatch_counts.get("Amazon", 0))
with c3:
    _render_kpi_card("Flipkart Mismatches", platform_mismatch_counts.get("Flipkart", 0))
with c4:
    _render_kpi_card("Myntra Mismatches", platform_mismatch_counts.get("Myntra", 0))
with c5:
    _render_kpi_card("Shopify Mismatches", platform_mismatch_counts.get("Shopify", 0))
with c6:
    _render_kpi_card("Total Mismatches", total_mismatches)

with st.container():
    f1, f2, f3 = st.columns([2, 3, 2])
    with f1:
        platform_filter = st.selectbox("Platform", options=["All"] + SUPPORTED_PLATFORMS, index=0)
    with f2:
        search_design_no = st.text_input("Design No Search")
    with f3:
        show_mismatches_only = st.toggle("Show Mismatches Only", value=True)

base_df = mismatch_df if show_mismatches_only else comparison_df
filtered = base_df.copy()
if platform_filter != "All":
    filtered = filtered[filtered["marketplace"] == platform_filter]
query = search_design_no.strip().lower()
if query:
    filtered = filtered[filtered["sku"].astype(str).str.lower().str.contains(query, na=False)]

st.markdown("### Mismatch Details" if show_mismatches_only else "### All Reconciliation Results")

display_df = _to_display_df(filtered)
st.dataframe(display_df, use_container_width=True)

st.divider()
with st.container():
    d1, d2, d3, d4 = st.columns(4)
    with d1:
        _download_for("Amazon", "dl_amazon", mismatch_df)
    with d2:
        _download_for("Flipkart", "dl_flipkart", mismatch_df)
    with d3:
        _download_for("Myntra", "dl_myntra", mismatch_df)
    with d4:
        _download_for("Shopify", "dl_shopify", mismatch_df)
