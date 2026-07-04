from datetime import datetime
import base64

import pandas as pd
import streamlit as st

from config.settings import SUPPORTED_PLATFORMS
from services.reconciliation import run_live_reconciliation
from utils.helpers import get_logger

logger = get_logger("views.dashboard")

st.markdown(
    """
    <style>
      :root {
        --bg: #F5F7FA;
        --card: #FFFFFF;
        --title: #111827;
        --text: #111827;
        --muted: #6B7280;
        --border: rgba(0,0,0,0.05);
        --shadow: 0 4px 12px rgba(15,23,42,0.05), 0 10px 28px rgba(15,23,42,0.08);
      }

      body { background: var(--bg); }
      .stApp { background: var(--bg); }
      section.main > div { padding-top: 8px; padding-bottom: 2rem; }
      .block-container {
        padding: 1.35rem 1.7rem 2rem;
        max-width: 1440px;
      }
      h1, .stTitle {
        font-size: 2.15rem !important;
        font-weight: 800 !important;
        color: var(--title) !important;
        letter-spacing: -0.02em;
        margin-bottom: 0.35rem;
      }
      div[data-testid="stMarkdownContainer"] p {
        color: var(--muted);
        font-size: 0.95rem;
      }

      .kpi-card {
        position: relative;
        display: flex;
        flex-direction: column;
        justify-content: center;
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 18px;
        padding: 22px 22px 24px;
        box-shadow: var(--shadow);
        min-height: 132px;
        color: var(--text);
        text-align: left;
        margin: 0 0 1rem;
        transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease;
      }
      .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(15,23,42,0.08), 0 14px 32px rgba(15,23,42,0.12);
        border-color: rgba(37,99,235,0.16);
      }
      .kpi-title {
        font-size: 14px;
        color: var(--muted);
        margin-bottom: 10px;
        font-weight: 600;
        letter-spacing: 0.01em;
      }
      .kpi-value {
        font-size: 40px;
        font-weight: 800;
        color: var(--title);
        line-height: 1.05;
        margin-top: 4px;
      }
      .kpi-download-icon {
        position: absolute;
        top: 12px;
        right: 12px;
        width: 34px;
        height: 34px;
        display: grid;
        place-items: center;
        border-radius: 999px;
        background: rgba(15,23,42,0.03);
        text-decoration: none;
        transition: all 180ms ease;
      }
      .kpi-download-icon svg {
        width: 16px;
        height: 16px;
        stroke: #6B7280;
        transition: stroke 180ms ease, transform 180ms ease;
      }
      .kpi-download-icon:hover {
        background: rgba(37,99,235,0.10);
      }
      .kpi-download-icon:hover svg {
        stroke: #2563EB;
        transform: translateY(-1px);
      }

      div[data-testid="stDataFrame"] {
        border-radius: 16px;
        overflow: hidden;
        border: 1px solid var(--border);
        box-shadow: var(--shadow);
        width: 100%;
      }
      div[data-testid="stDataFrame"] .dataframe {
        border-radius: 16px;
      }
      section[data-testid="stSidebar"] { width: 240px; }

      div.stButton > button,
      div.stDownloadButton > button {
        border: 1px solid rgba(0,0,0,0.08);
        border-radius: 10px;
        padding: 0.6rem 0.95rem;
        box-shadow: 0 1px 2px rgba(15,23,42,0.04);
        background: #FFFFFF;
        color: var(--title);
        font-weight: 600;
        transition: all 180ms ease;
      }
      div.stButton > button:hover,
      div.stDownloadButton > button:hover {
        border-color: rgba(37,99,235,0.18);
        box-shadow: 0 6px 16px rgba(15,23,42,0.08);
        transform: translateY(-1px);
      }

      .stTextInput > div > div > input,
      .stSelectbox > div > div {
        border-radius: 10px !important;
        border: 1px solid rgba(0,0,0,0.08) !important;
        box-shadow: none !important;
        min-height: 42px;
      }
      .stTextInput > div > div > input:focus,
      .stSelectbox > div > div:focus-within {
        border-color: rgba(37,99,235,0.28) !important;
        box-shadow: 0 0 0 3px rgba(37,99,235,0.10) !important;
      }
      .stSelectbox {
        margin-bottom: 0.25rem;
      }
      .stTextInput {
        margin-bottom: 0.25rem;
      }
      .stToggle {
        margin-top: 0.2rem;
      }
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


def _render_kpi_card(
    title: str,
    value: int,
    download_href: str | None = None,
    download_filename: str | None = None,
    download_disabled: bool = False,
) -> None:
    download_icon = ""
    if download_href and download_filename and not download_disabled:
        download_icon = (
            "<a class='kpi-download-icon' href='" + download_href + "' download='" + download_filename + "'>"
            "<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>"
            "<path d='M12 3v12' />"
            "<polyline points='7 10 12 15 17 10' />"
            "<path d='M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4' />"
            "</svg>"
            "</a>"
        )
    elif download_disabled:
        download_icon = (
            "<span class='kpi-download-icon' style='opacity:0.35; cursor:default;'>"
            "<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>"
            "<path d='M12 3v12' />"
            "<polyline points='7 10 12 15 17 10' />"
            "<path d='M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4' />"
            "</svg>"
            "</span>"
        )

    st.markdown(
        f"<div class='kpi-card'>{download_icon}<div class='kpi-title'>{title}</div><div class='kpi-value'>{value:,}</div></div>",
        unsafe_allow_html=True,
    )


def _build_export_df(platform: str, mismatch_df: pd.DataFrame) -> pd.DataFrame:
    dfp = mismatch_df[mismatch_df["marketplace"] == platform]
    return dfp[["sku", "marketplace", "wms_price", "marketplace_price"]].rename(
        columns={
            "sku": "Design No",
            "marketplace": "Channel",
            "wms_price": "WMS Price",
            "marketplace_price": "Channel price",
        }
    )


def _build_download_link(platform: str, mismatch_df: pd.DataFrame) -> tuple[str, str] | None:
    if mismatch_df.empty:
        return None

    export_df = _build_export_df(platform, mismatch_df)
    if export_df.empty:
        return None

    file_name = f"CPRP_Mismatches_{platform}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    href = (
        "data:text/csv;base64,"
        + base64.b64encode(_to_csv_bytes(export_df)).decode("utf-8")
    )
    return href, file_name


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
            download_data = _build_download_link(platform, mismatch_df)
            if download_data:
                download_href, download_filename = download_data
            else:
                download_href, download_filename = None, None
            _render_kpi_card(
                f"{platform} Mismatches",
                platform_count,
                download_href=download_href,
                download_filename=download_filename,
                download_disabled=platform_count == 0,
            )
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
