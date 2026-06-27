from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from database.models import ReconciliationRun, UploadedFile, ComparisonDetail, ValidationError, PlatformMapping
from utils.helpers import get_logger

logger = get_logger("services.db_persistence")


def get_platform_mapping(session: Session, platform: str) -> Optional[Tuple[str, str]]:
    """Retrieves the saved column mapping (sku_column, price_column) for a platform."""
    try:
        mapping = session.query(PlatformMapping).filter(PlatformMapping.platform == platform).first()
        if mapping:
            return mapping.sku_column, mapping.price_column
        return None
    except Exception as e:
        logger.error(f"Error fetching mapping for {platform}: {str(e)}")
        return None


def save_platform_mapping(session: Session, platform: str, sku_col: str, price_col: str):
    """Saves or updates column mapping for a specific marketplace platform."""
    try:
        mapping = session.query(PlatformMapping).filter(PlatformMapping.platform == platform).first()
        if mapping:
            mapping.sku_column = sku_col
            mapping.price_column = price_col
            mapping.updated_at = datetime.utcnow()
            logger.info(f"Updated platform mapping for {platform}: SKU='{sku_col}', Price='{price_col}'")
        else:
            mapping = PlatformMapping(
                platform=platform,
                sku_column=sku_col,
                price_column=price_col,
                updated_at=datetime.utcnow()
            )
            session.add(mapping)
            logger.info(f"Created new platform mapping for {platform}: SKU='{sku_col}', Price='{price_col}'")
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to save platform mapping for {platform}: {str(e)}", exc_info=True)
        raise e


def create_reconciliation_run(session: Session, run_type: str = "historical", run_name: Optional[str] = None) -> int:
    """Creates a new reconciliation run record in 'Pending' state. Returns run ID."""
    try:
        run = ReconciliationRun(
            status="Pending",
            run_type=run_type,
            run_name=run_name,
            run_date=datetime.utcnow()
        )
        session.add(run)
        session.commit()
        logger.info(f"Created new ReconciliationRun ID={run.id} (type={run_type})")
        return run.id
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to create reconciliation run record: {str(e)}", exc_info=True)
        raise e


def update_reconciliation_run_status(
    session: Session, 
    run_id: int, 
    status: str, 
    error_message: Optional[str] = None, 
    run_summary: Optional[Dict[str, int]] = None
):
    """Updates the status and summary metrics of an active reconciliation run."""
    try:
        run = session.query(ReconciliationRun).filter(ReconciliationRun.id == run_id).first()
        if not run:
            raise ValueError(f"ReconciliationRun with ID {run_id} not found.")

        run.status = status
        if error_message:
            run.error_message = error_message
        
        if run_summary:
            run.total_skus = run_summary.get("total_skus", 0)
            run.exact_matches = run_summary.get("exact_matches", 0)
            run.mismatches = run_summary.get("mismatches", 0)
            run.missing_wms = run_summary.get("missing_wms", 0)
            run.missing_marketplace = run_summary.get("missing_marketplace", 0)
            run.critical_mismatches = run_summary.get("critical_mismatches", 0)

        session.commit()
        logger.info(f"Updated ReconciliationRun ID={run_id} status to '{status}'")
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update reconciliation run ID={run_id}: {str(e)}", exc_info=True)
        raise e


def save_uploaded_file(
    session: Session, 
    run_id: int, 
    file_type: str, 
    filename: str, 
    filepath: str, 
    platform: str, 
    row_count: int
) -> int:
    """Logs metadata for an uploaded file linked to a reconciliation run."""
    try:
        uploaded_file = UploadedFile(
            run_id=run_id,
            file_type=file_type,
            filename=filename,
            filepath=filepath,
            platform=platform,
            row_count=row_count,
            upload_timestamp=datetime.utcnow()
        )
        session.add(uploaded_file)
        session.commit()
        logger.info(f"Logged UploadedFile ID={uploaded_file.id} for run {run_id} ({platform})")
        return uploaded_file.id
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to save uploaded file log: {str(e)}", exc_info=True)
        raise e


def save_validation_errors(
    session: Session, 
    run_id: int, 
    file_id: Optional[int], 
    errors_list: List[Dict[str, Any]]
):
    """Saves structural validation errors to the database in bulk."""
    if not errors_list:
        return

    try:
        db_errors = []
        for err in errors_list:
            db_errors.append(ValidationError(
                run_id=run_id,
                file_id=file_id,
                error_type=err.get("error_type"),
                row_number=err.get("row_number"),
                sku=err.get("sku"),
                column_name=err.get("column_name"),
                error_message=err.get("error_message")
            ))
        
        session.bulk_save_objects(db_errors)
        session.commit()
        logger.info(f"Saved {len(db_errors)} validation errors to database for run {run_id}")
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to save validation errors: {str(e)}", exc_info=True)
        raise e


def save_comparison_details(
    session: Session, 
    run_id: int, 
    comparison_rows: List[Dict[str, Any]]
):
    """Saves the final calculated comparison rows to the database in bulk."""
    if not comparison_rows:
        return

    try:
        db_details = []
        for row in comparison_rows:
            db_details.append(ComparisonDetail(
                run_id=run_id,
                sku=row.get("sku"),
                product_name=row.get("product_name"),
                brand=row.get("brand"),
                category=row.get("category"),
                wms_price=row.get("wms_price"),
                marketplace=row.get("marketplace"),
                marketplace_price=row.get("marketplace_price"),
                price_diff=row.get("price_diff"),
                percent_diff=row.get("percent_diff"),
                severity=row.get("severity"),
                status=row.get("status", "Open")
            ))
        
        session.bulk_save_objects(db_details)
        session.commit()
        logger.info(f"Saved {len(db_details)} comparison detail records to database for run {run_id}")
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to save comparison details: {str(e)}", exc_info=True)
        raise e


def get_live_snapshot_run(session: Session) -> Optional[ReconciliationRun]:
    """Returns the current live snapshot run, if one exists."""
    return (
        session.query(ReconciliationRun)
        .filter(ReconciliationRun.run_type == "live")
        .order_by(ReconciliationRun.run_date.desc())
        .first()
    )


def delete_live_snapshot_runs(session: Session) -> int:
    """Removes all live snapshot runs and cascaded child records. Returns count deleted."""
    live_runs = session.query(ReconciliationRun).filter(ReconciliationRun.run_type == "live").all()
    count = len(live_runs)
    for run in live_runs:
        session.delete(run)
    if count:
        session.commit()
        logger.info(f"Deleted {count} live snapshot run(s)")
    return count


def get_setting(session: Session, key: str) -> Optional[str]:
    """Retrieves a portal setting value by key."""
    from database.models import Settings
    row = session.query(Settings).filter(Settings.key == key).first()
    return row.value if row else None


def set_setting(session: Session, key: str, value: str, description: Optional[str] = None):
    """Creates or updates a portal setting."""
    from database.models import Settings
    row = session.query(Settings).filter(Settings.key == key).first()
    if row:
        row.value = value
        if description:
            row.description = description
    else:
        session.add(Settings(key=key, value=value, description=description))
    session.commit()


def get_platform_mismatch_counts(session: Session, run_id: int) -> Dict[str, Dict[str, int]]:
    """Returns per-platform mismatch breakdown for a reconciliation run."""
    rows = (
        session.query(ComparisonDetail.marketplace, ComparisonDetail.severity)
        .filter(ComparisonDetail.run_id == run_id)
        .all()
    )
    stats: Dict[str, Dict[str, int]] = {}
    for platform, severity in rows:
        if platform not in stats:
            stats[platform] = {
                "total": 0,
                "exact_matches": 0,
                "mismatches": 0,
                "critical": 0,
                "missing_wms": 0,
                "missing_marketplace": 0,
            }
        stats[platform]["total"] += 1
        if severity == "Exact Match":
            stats[platform]["exact_matches"] += 1
        elif severity == "Critical Mismatch":
            stats[platform]["mismatches"] += 1
            stats[platform]["critical"] += 1
        elif severity in ("Low Mismatch", "Medium Mismatch"):
            stats[platform]["mismatches"] += 1
        elif severity == "Missing in WMS":
            stats[platform]["missing_wms"] += 1
        elif severity == "Missing in Marketplace":
            stats[platform]["missing_marketplace"] += 1
    return stats


def copy_run_to_history(session: Session, source_run_id: int, run_name: str) -> int:
    """Copies a live snapshot run into a new historical run for audit retention."""
    source = session.query(ReconciliationRun).filter(ReconciliationRun.id == source_run_id).first()
    if not source:
        raise ValueError(f"Source run {source_run_id} not found.")

    new_run = ReconciliationRun(
        run_name=run_name,
        run_type="historical",
        status=source.status,
        run_date=datetime.utcnow(),
        total_skus=source.total_skus,
        exact_matches=source.exact_matches,
        mismatches=source.mismatches,
        missing_wms=source.missing_wms,
        missing_marketplace=source.missing_marketplace,
        critical_mismatches=source.critical_mismatches,
        error_message=source.error_message,
    )
    session.add(new_run)
    session.flush()

    file_id_map: Dict[int, int] = {}
    for uploaded in source.uploaded_files:
        copy_file = UploadedFile(
            run_id=new_run.id,
            file_type=uploaded.file_type,
            filename=uploaded.filename,
            filepath=uploaded.filepath,
            platform=uploaded.platform,
            row_count=uploaded.row_count,
            upload_timestamp=uploaded.upload_timestamp,
        )
        session.add(copy_file)
        session.flush()
        file_id_map[uploaded.id] = copy_file.id

    for err in source.validation_errors:
        session.add(ValidationError(
            run_id=new_run.id,
            file_id=file_id_map.get(err.file_id) if err.file_id else None,
            error_type=err.error_type,
            row_number=err.row_number,
            sku=err.sku,
            column_name=err.column_name,
            error_message=err.error_message,
        ))

    for detail in source.comparison_details:
        session.add(ComparisonDetail(
            run_id=new_run.id,
            sku=detail.sku,
            product_name=detail.product_name,
            brand=detail.brand,
            category=detail.category,
            wms_price=detail.wms_price,
            marketplace=detail.marketplace,
            marketplace_price=detail.marketplace_price,
            price_diff=detail.price_diff,
            percent_diff=detail.percent_diff,
            severity=detail.severity,
            status=detail.status,
        ))

    session.commit()
    logger.info(f"Copied run {source_run_id} to historical run {new_run.id} as '{run_name}'")
    return new_run.id
