import os
import shutil
import streamlit as st
import pandas as pd
from config.settings import SUPPORTED_PLATFORMS, UPLOADS_DIR, DEFAULT_LOW_THRESHOLD, DEFAULT_MEDIUM_THRESHOLD
from database.connection import get_db
from services.file_reader import read_file, suggest_mappings
from services.validator import validate_dataframe
from services.comparer import reconcile_prices
from services.db_persistence import (
    get_platform_mapping,
    save_platform_mapping,
    create_reconciliation_run,
    update_reconciliation_run_status,
    save_uploaded_file,
    save_validation_errors,
    save_comparison_details
)
from utils.helpers import get_logger, format_currency, format_percent

logger = get_logger("views.reconcile")

# Maximum file size threshold (50 MB)
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Initialize session state variables
if "reconcile_step" not in st.session_state:
    st.session_state.reconcile_step = "UPLOAD"

# Cleanup function to reset run
def reset_reconciliation():
    st.session_state.reconcile_step = "UPLOAD"
    st.session_state.pop("wms_data", None)
    st.session_state.pop("mkt_data", None)
    st.session_state.pop("wms_filename", None)
    st.session_state.pop("mkt_filenames", None)
    st.session_state.pop("wms_mapping", None)
    st.session_state.pop("mkt_mappings", None)
    st.session_state.pop("run_id", None)
    st.session_state.pop("validation_results", None)
    st.session_state.pop("comparison_results", None)
    st.session_state.pop("run_summary", None)
    st.rerun()

# -----------------
# STEP 1: UPLOAD FILES
# -----------------
if st.session_state.reconcile_step == "UPLOAD":
    st.title("🔄 New Reconciliation Run")
    st.info(
        "**Primary workflow:** Update data in the configured Google Sheet and refresh from the"
        " **Dashboard**. Use this page only when you need to upload separate files manually."
    )
    st.write("Compare catalog records. Upload your WMS master sheet and select/upload marketplace listings.")
    
    st.divider()
    st.subheader("Step 1: Upload Spreadsheets")

    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Warehouse Master (WMS)")
        wms_file = st.file_uploader(
            "Upload WMS Master Price Report",
            type=["csv"],
            key="wms_file_input",
            help="Upload master spreadsheet containing target stock SKUs and correct WMS Prices."
        )
        
    with col2:
        st.markdown("### Marketplace Platforms")
        selected_platforms = st.multiselect(
            "Select marketplaces to compare against WMS",
            options=SUPPORTED_PLATFORMS,
            default=[],
            help="Choose one or more platforms. A separate upload box will render for each selected platform."
        )

    mkt_files = {}
    if selected_platforms:
        st.write("---")
        st.subheader("Upload Marketplace Listings")
        mkt_cols = st.columns(len(selected_platforms))
        
        for idx, platform in enumerate(selected_platforms):
            with mkt_cols[idx]:
                mkt_files[platform] = st.file_uploader(
                    f"Upload {platform} Price Report",
                    type=["csv"],
                    key=f"mkt_file_{platform.lower()}",
                    help=f"Upload product listing spreadsheet extracted from {platform} center."
                )

    st.divider()

    # Progress Trigger Button
    if st.button("Proceed to Columns Mapping", type="primary"):
        # Validate inputs
        if not wms_file:
            st.error("WMS Master Price Report file is required to proceed.")
        elif not selected_platforms:
            st.error("Please select at least one marketplace platform to compare.")
        else:
            # Check if all selected marketplace files are uploaded
            missing_uploads = [p for p in selected_platforms if not mkt_files.get(p)]
            if missing_uploads:
                st.error(f"Please upload pricing reports for: {', '.join(missing_uploads)}")
            else:
                # Validate sizes
                oversized_files = []
                if wms_file.size > MAX_FILE_SIZE_BYTES:
                    oversized_files.append(f"WMS File ({wms_file.size / (1024*1024):.1f}MB)")
                for platform, file in mkt_files.items():
                    if file.size > MAX_FILE_SIZE_BYTES:
                        oversized_files.append(f"{platform} File ({file.size / (1024*1024):.1f}MB)")
                
                if oversized_files:
                    st.error(f"Files exceed the maximum limit of {MAX_FILE_SIZE_MB}MB: {', '.join(oversized_files)}")
                else:
                    # Load files into DataFrames
                    with st.spinner("Parsing spreadsheets into memory..."):
                        try:
                            # Read WMS
                            wms_df = read_file(wms_file, wms_file.name)
                            st.session_state.wms_data = wms_df
                            st.session_state.wms_filename = wms_file.name
                            
                            # Read Marketplace files
                            mkt_dfs = {}
                            mkt_filenames = {}
                            for p, file in mkt_files.items():
                                mkt_dfs[p] = read_file(file, file.name)
                                mkt_filenames[p] = file.name
                            
                            st.session_state.mkt_data = mkt_dfs
                            st.session_state.mkt_filenames = mkt_filenames
                            st.session_state.selected_platforms = selected_platforms
                            
                            # Advance stepper
                            st.session_state.reconcile_step = "MAPPING"
                            st.rerun()
                        except Exception as e:
                            st.error(f"An error occurred while loading files: {str(e)}")

# -----------------
# STEP 2: COLUMN MAPPING
# -----------------
elif st.session_state.reconcile_step == "MAPPING":
    st.title("🔄 Column Mapping Setup")
    st.write("Link specific database fields to spreadsheet column headers. Auto-suggestions have been filled where possible.")

    wms_df = st.session_state.wms_data
    mkt_dfs = st.session_state.mkt_data
    selected_platforms = st.session_state.selected_platforms

    st.divider()
    
    col1, col2 = st.columns(2)
    
    # 2A. WMS Mapping UI
    with col1:
        st.subheader("WMS Column Fields")
        # Auto suggest
        s_sku, s_price = suggest_mappings(wms_df)
        
        # UI controls
        wms_sku_sel = st.selectbox(
            "Select WMS SKU Column",
            options=list(wms_df.columns),
            index=list(wms_df.columns).index(s_sku) if s_sku in wms_df.columns else 0,
            key="wms_sku_sel_box"
        )
        wms_price_sel = st.selectbox(
            "Select WMS Price Column",
            options=list(wms_df.columns),
            index=list(wms_df.columns).index(s_price) if s_price in wms_df.columns else 0,
            key="wms_price_sel_box"
        )

    # 2B. Marketplace Mapping UI
    mkt_mappings = {}
    with col2:
        st.subheader("Marketplace Column Fields")
        
        # Load DB maps suggestions
        with get_db() as db:
            for platform in selected_platforms:
                st.write(f"**{platform} Fields:**")
                df_p = mkt_dfs[platform]
                
                # Check DB mapping or fallback to auto matching
                db_mapping = get_platform_mapping(db, platform)
                s_sku_p, s_price_p = suggest_mappings(df_p)
                
                db_sku = db_mapping[0] if db_mapping else None
                db_price = db_mapping[1] if db_mapping else None
                
                # Preferred fallback: Database historic mapping -> auto suggest keyword match -> first column
                val_sku = db_sku if db_sku in df_p.columns else (s_sku_p if s_sku_p in df_p.columns else df_p.columns[0])
                val_price = db_price if db_price in df_p.columns else (s_price_p if s_price_p in df_p.columns else df_p.columns[0])
                
                sel_sku = st.selectbox(
                    f"{platform} SKU Column",
                    options=list(df_p.columns),
                    index=list(df_p.columns).index(val_sku),
                    key=f"mkt_sku_sel_{platform.lower()}"
                )
                sel_price = st.selectbox(
                    f"{platform} Price Column",
                    options=list(df_p.columns),
                    index=list(df_p.columns).index(val_price),
                    key=f"mkt_price_sel_{platform.lower()}"
                )
                
                mkt_mappings[platform] = {"sku": sel_sku, "price": sel_price}

    st.divider()
    
    col_nav1, col_nav2 = st.columns([1, 5])
    with col_nav1:
        if st.button("⬅ Back"):
            st.session_state.reconcile_step = "UPLOAD"
            st.rerun()
    with col_nav2:
        if st.button("Proceed to Schema Verification & Previews", type="primary"):
            st.session_state.wms_mapping = {"sku": wms_sku_sel, "price": wms_price_sel}
            st.session_state.mkt_mappings = mkt_mappings
            
            # Save mapping inputs back to DB PlatformMapping
            with get_db() as db:
                for platform, mappings in mkt_mappings.items():
                    save_platform_mapping(db, platform, mappings["sku"], mappings["price"])
            
            st.session_state.reconcile_step = "VALIDATION"
            st.rerun()

# -----------------
# STEP 3: SCHEMA VALIDATION & PREVIEWS
# -----------------
elif st.session_state.reconcile_step == "VALIDATION":
    st.title("🔍 Schema Validation & Data Preview")
    st.write("Inspect verification previews and resolve warning notes before running reconciliation reports.")

    wms_df = st.session_state.wms_data
    mkt_dfs = st.session_state.mkt_data
    wms_mapping = st.session_state.wms_mapping
    mkt_mappings = st.session_state.mkt_mappings
    selected_platforms = st.session_state.selected_platforms

    # Run validators and gather lists
    validation_results = {}
    critical_block = False

    st.divider()
    st.subheader("Data Validation Report")

    # Validate WMS
    wms_summary, wms_errors = validate_dataframe(
        wms_df, 
        wms_mapping["sku"], 
        wms_mapping["price"], 
        "WMS", 
        "WMS"
    )
    validation_results["WMS"] = {"summary": wms_summary, "errors": wms_errors}
    
    if wms_summary["critical_error"]:
        critical_block = True
        st.error(f"❌ **WMS File Schema Failure**: Mapped columns are missing from the sheet structure.")
    elif wms_errors:
        st.warning(f"⚠️ **WMS File Warnings**: Scanned {wms_summary['total_rows']} rows. Found {len(wms_errors)} anomalies.")
        with st.expander("Show WMS Validation Details"):
            st.write(pd.DataFrame(wms_errors))
    else:
        st.success("✅ **WMS File Verified**: Clean schema structures, no duplicates or empty values.")

    # Validate Marketplaces
    for platform in selected_platforms:
        p_mapping = mkt_mappings[platform]
        p_summary, p_errors = validate_dataframe(
            mkt_dfs[platform], 
            p_mapping["sku"], 
            p_mapping["price"], 
            "Marketplace", 
            platform
        )
        validation_results[platform] = {"summary": p_summary, "errors": p_errors}
        
        if p_summary["critical_error"]:
            critical_block = True
            st.error(f"❌ **{platform} Schema Failure**: Mapped columns are missing.")
        elif p_errors:
            st.warning(f"⚠️ **{platform} Warnings**: Scanned {p_summary['total_rows']} rows. Found {len(p_errors)} anomalies.")
            with st.expander(f"Show {platform} Validation Details"):
                st.write(pd.DataFrame(p_errors))
        else:
            st.success(f"✅ **{platform} Verified**: Schema validated successfully.")

    # Show previews of 20 rows
    st.write("---")
    st.subheader("Sheet Previews (First 20 Rows)")
    
    tab_wms, *tabs_mkt = st.tabs(["WMS Preview"] + [f"{p} Preview" for p in selected_platforms])
    
    with tab_wms:
        st.dataframe(wms_df.head(20))
        
    for i, platform in enumerate(selected_platforms):
        with tabs_mkt[i]:
            st.dataframe(mkt_dfs[platform].head(20))

    st.divider()
    
    col_nav1, col_nav2 = st.columns([1, 5])
    with col_nav1:
        if st.button("⬅ Back"):
            st.session_state.reconcile_step = "MAPPING"
            st.rerun()
    with col_nav2:
        run_btn = st.button(
            "Execute Reconciliation", 
            type="primary", 
            disabled=critical_block,
            help="Disabled if critical schema configuration errors exist."
        )
        
        if run_btn:
            # Create Database run
            with get_db() as db:
                try:
                    run_id = create_reconciliation_run(db, run_type="historical")
                    st.session_state.run_id = run_id
                    
                    # Update status to Processing
                    update_reconciliation_run_status(db, run_id, "Processing")
                    
                    # Save Uploaded Files logs & Validation Errors
                    # WMS File
                    wms_hash_name = f"run_{run_id}_wms_{st.session_state.wms_filename}"
                    wms_path = UPLOADS_DIR / wms_hash_name
                    # Note: streamlit file_uploader needs reset or read file data
                    # Let's save a placeholder text or write from dataframe to verify local storage
                    wms_df.to_excel(wms_path, index=False)
                    
                    wms_file_id = save_uploaded_file(
                        db, 
                        run_id, 
                        "WMS", 
                        st.session_state.wms_filename, 
                        str(wms_path), 
                        "WMS", 
                        len(wms_df)
                    )
                    save_validation_errors(db, run_id, wms_file_id, validation_results["WMS"]["errors"])

                    # Marketplace Files
                    mkt_datasets = {}
                    for platform in selected_platforms:
                        mkt_df = mkt_dfs[platform]
                        m_map = mkt_mappings[platform]
                        mkt_datasets[platform] = (mkt_df, m_map["sku"], m_map["price"])
                        
                        mkt_hash_name = f"run_{run_id}_mkt_{platform.lower()}_{st.session_state.mkt_filenames[platform]}"
                        mkt_path = UPLOADS_DIR / mkt_hash_name
                        mkt_df.to_excel(mkt_path, index=False)
                        
                        mkt_file_id = save_uploaded_file(
                            db, 
                            run_id, 
                            "Marketplace", 
                            st.session_state.mkt_filenames[platform], 
                            str(mkt_path), 
                            platform, 
                            len(mkt_df)
                        )
                        save_validation_errors(db, run_id, mkt_file_id, validation_results[platform]["errors"])

                    # Run Comparer
                    with st.spinner("Comparing SKUs and verifying prices..."):
                        run_summary, comparison_rows = reconcile_prices(
                            wms_df,
                            wms_mapping["sku"],
                            wms_mapping["price"],
                            mkt_datasets,
                            DEFAULT_LOW_THRESHOLD,
                            DEFAULT_MEDIUM_THRESHOLD
                        )
                        
                        # Save Comparison Details in bulk
                        save_comparison_details(db, run_id, comparison_rows)
                        
                        # Set Run to Completed
                        update_reconciliation_run_status(db, run_id, "Completed", run_summary=run_summary)
                        
                        st.session_state.run_summary = run_summary
                        st.session_state.comparison_results = comparison_rows
                        st.session_state.reconcile_step = "RESULTS"
                        st.rerun()

                except Exception as e:
                    if "run_id" in st.session_state:
                        update_reconciliation_run_status(db, st.session_state.run_id, "Failed", error_message=str(e))
                    st.error(f"Reconciliation comparison engine crashed: {str(e)}")
                    logger.error(f"Reconciliation engine failed: {str(e)}", exc_info=True)

# -----------------
# STEP 4: RESULTS VIEW
# -----------------
elif st.session_state.reconcile_step == "RESULTS":
    st.title("🎉 Reconciliation Completed")
    st.write(f"Reconciliation Run **#{st.session_state.run_id}** completed successfully.")

    run_summary = st.session_state.run_summary
    comparison_rows = st.session_state.comparison_results

    st.divider()

    # KPI metric highlights
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total SKU Pairs", run_summary["total_skus"])
    with col2:
        st.metric("Exact Matches", run_summary["exact_matches"])
    with col3:
        st.metric("Price Mismatches", run_summary["mismatches"])
    with col4:
        st.metric("Missing WMS SKUs", run_summary["missing_wms"])
    with col5:
        st.metric("Missing Marketplaces", run_summary["missing_marketplace"])

    st.divider()
    
    st.subheader("Comparison Data Log")
    comp_df = pd.DataFrame(comparison_rows)
    
    # Format prices for preview representation
    display_df = comp_df.copy()
    display_df["wms_price"] = display_df["wms_price"].apply(format_currency)
    display_df["marketplace_price"] = display_df["marketplace_price"].apply(format_currency)
    display_df["price_diff"] = display_df["price_diff"].apply(format_currency)
    display_df["percent_diff"] = display_df["percent_diff"].apply(format_percent)
    
    # Render table (without advanced interactive filters)
    st.dataframe(display_df, use_container_width=True)

    st.divider()
    
    if st.button("Start New Reconciliation", type="primary"):
        reset_reconciliation()
