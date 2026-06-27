from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from database.connection import Base


class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_name = Column(String(255), nullable=True)                  # Optional human-readable label
    run_type = Column(String(20), nullable=False, default="historical")  # live | historical
    status = Column(String(50), nullable=False, default="Pending") # Pending, Processing, Completed, Failed
    run_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    total_skus = Column(Integer, nullable=False, default=0)
    exact_matches = Column(Integer, nullable=False, default=0)
    mismatches = Column(Integer, nullable=False, default=0)
    missing_wms = Column(Integer, nullable=False, default=0)
    missing_marketplace = Column(Integer, nullable=False, default=0)
    critical_mismatches = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)

    # Relationships
    uploaded_files = relationship(
        "UploadedFile",
        back_populates="reconciliation_run",
        cascade="all, delete-orphan"
    )
    comparison_details = relationship(
        "ComparisonDetail",
        back_populates="reconciliation_run",
        cascade="all, delete-orphan"
    )
    validation_errors = relationship(
        "ValidationError",
        back_populates="reconciliation_run",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<ReconciliationRun id={self.id} status={self.status} date={self.run_date}>"


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("reconciliation_runs.id"), nullable=False)
    file_type = Column(String(20), nullable=False)      # WMS, Marketplace
    filename = Column(String(255), nullable=False)
    filepath = Column(String(512), nullable=False)
    platform = Column(String(50), nullable=False)       # WMS, Amazon, Flipkart, Myntra, Shopify, etc.
    row_count = Column(Integer, nullable=False, default=0)
    upload_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    reconciliation_run = relationship("ReconciliationRun", back_populates="uploaded_files")
    validation_errors = relationship(
        "ValidationError",
        back_populates="uploaded_file",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<UploadedFile id={self.id} platform={self.platform} file_type={self.file_type}>"


class ComparisonDetail(Base):
    __tablename__ = "comparison_details"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("reconciliation_runs.id"), nullable=False)
    sku = Column(String(100), nullable=False, index=True)
    product_name = Column(String(255), nullable=True)
    brand = Column(String(100), nullable=True)
    category = Column(String(100), nullable=True)
    wms_price = Column(Float, nullable=True)
    marketplace = Column(String(50), nullable=False, index=True)
    marketplace_price = Column(Float, nullable=True)
    price_diff = Column(Float, nullable=True)
    percent_diff = Column(Float, nullable=True)
    severity = Column(String(50), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="Open")  # Open, Reviewed, Resolved

    # Relationships
    reconciliation_run = relationship("ReconciliationRun", back_populates="comparison_details")

    def __repr__(self):
        return f"<ComparisonDetail sku={self.sku} marketplace={self.marketplace} severity={self.severity}>"


class ValidationError(Base):
    __tablename__ = "validation_errors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("reconciliation_runs.id"), nullable=False)
    file_id = Column(Integer, ForeignKey("uploaded_files.id"), nullable=True)
    error_type = Column(String(100), nullable=False)  # Duplicate SKU, Blank Price, Invalid Price, Missing Column
    row_number = Column(Integer, nullable=True)        # 1-indexed Excel row
    sku = Column(String(100), nullable=True)
    column_name = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=False)

    # Relationships
    reconciliation_run = relationship("ReconciliationRun", back_populates="validation_errors")
    uploaded_file = relationship("UploadedFile", back_populates="validation_errors")

    def __repr__(self):
        return f"<ValidationError id={self.id} type={self.error_type} sku={self.sku}>"


class PlatformMapping(Base):
    __tablename__ = "platform_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(50), nullable=False, unique=True, index=True)
    sku_column = Column(String(100), nullable=False)
    price_column = Column(String(100), nullable=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<PlatformMapping platform={self.platform} sku={self.sku_column} price={self.price_column}>"


class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), nullable=False, unique=True, index=True)
    value = Column(String(255), nullable=False)
    description = Column(String(255), nullable=True)

    def __repr__(self):
        return f"<Settings key={self.key} value={self.value}>"
