"""
Daily Reconciliation ORM Models
================================

SQLAlchemy models for the daily_recon domain:
- daily_recon_run: one extraction/validation batch
- daily_recon_row: one source record
- daily_recon_cell: one (row × column) EAV cell
- daily_recon_cell_issue: per-rule failure traceability
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, BigInteger, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from api.database import Base


class ReconRun(Base):
    """Represents one extraction + validation run.

    Attributes:
        id: UUID primary key.
        job_id: Link to the Celery job in the jobs table.
        source_query: The external SQL query executed (for audit).
        row_count: Total rows extracted.
        error_row_count: Rows with at least one errored cell.
        status: pending|running|validated|exported|failed.
        created_at: When the run was created.
        updated_at: Last modification.
    """

    __tablename__ = "daily_recon_run"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    source_query: Mapped[str] = mapped_column(Text, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    rows: Mapped[list["ReconRow"]] = relationship(
        "ReconRow",
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ReconRow(Base):
    """Represents one source record within a run.

    One row per extracted source row; cells are stored separately (EAV).

    Attributes:
        id: UUID primary key.
        run_id: Foreign key to daily_recon_run.
        row_index: Ordinal position within the run (0-based).
        trade_ref: Denormalised TRADEREF for quick lookup.
        has_error: Aggregate error flag (true if any cell is errored).
        approved: User approval flag.
        approved_at: When user approved.
        created_at: When inserted.
        updated_at: Last modification.
    """

    __tablename__ = "daily_recon_row"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("daily_recon_run.id", ondelete="CASCADE"), nullable=False
    )
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    trade_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    has_error: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    run: Mapped["ReconRun"] = relationship("ReconRun", back_populates="rows")
    cells: Mapped[list["ReconCell"]] = relationship(
        "ReconCell",
        back_populates="row",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ReconCell(Base):
    """Represents one (row × column) cell — the EAV model.

    Attributes:
        id: Auto-incrementing bigint PK.
        row_id: FK to daily_recon_row.
        column_name: The column name (e.g. 'BUYER_ID').
        original_value: Raw source text as stored.
        suggested_fix: Auto-suggested correction (nullable).
        corrected_value: User manual correction (nullable).
        is_errored: Per-cell error flag.
        created_at: When inserted.
        updated_at: Last modification.
    """

    __tablename__ = "daily_recon_cell"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    row_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("daily_recon_row.id", ondelete="CASCADE"), nullable=False
    )
    column_name: Mapped[str] = mapped_column(String(64), nullable=False)
    original_value: Mapped[str | None] = mapped_column(String(5000), nullable=True)
    suggested_fix: Mapped[str | None] = mapped_column(String(5000), nullable=True)
    corrected_value: Mapped[str | None] = mapped_column(String(5000), nullable=True)
    is_errored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    row: Mapped["ReconRow"] = relationship("ReconRow", back_populates="cells")
    issues: Mapped[list["ReconCellIssue"]] = relationship(
        "ReconCellIssue",
        back_populates="cell",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ReconCellIssue(Base):
    """Per-rule failure traceability for a cell.

    One row per validation rule that failed for a cell.

    Attributes:
        id: Auto-incrementing bigint PK.
        cell_id: FK to daily_recon_cell.
        rule_id: String identifier of the failed rule.
        message: Human-readable failure message.
        suggested_fix: Optional suggested fix from the rule.
    """

    __tablename__ = "daily_recon_cell_issue"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cell_id: Mapped[int] = mapped_column(
        ForeignKey("daily_recon_cell.id", ondelete="CASCADE"), nullable=False
    )
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    suggested_fix: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    cell: Mapped["ReconCell"] = relationship("ReconCell", back_populates="issues")

