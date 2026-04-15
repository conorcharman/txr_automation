"""
Reconciliation Model
====================

SQLAlchemy ORM model for the ``reconciliation_schedules`` table, which
stores the configuration and state of scheduled reconciliation runs.

A reconciliation schedule periodically extracts transaction data for a
rolling date window, validates a fixed subset of scripts (buyer/seller ID,
DM, and inconsistent ID), and pushes the results to template files.
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from api.database import Base


class ReconciliationSchedule(Base):
    """ORM model representing a scheduled reconciliation.

    Attributes:
        id: UUID primary key, generated automatically.
        name: Unique human-readable name for the reconciliation.
        rec_period_days: Number of days for the trade-by-trade validation
            window (default 90).
        lookback_days: Number of days for the inconsistent ID lookback
            window (default 365).
        selected_scripts: JSON array of script keys to execute (subset of
            the 6 valid reconciliation scripts).
        config_overrides: JSON dict of per-stage path overrides.
        stop_on_error: When ``True``, halt on first script failure.
        frequency: Recurrence cadence — hourly/daily/weekly/monthly/
            quarterly/custom.
        cron_expression: Five-field cron string (only when ``custom``).
        is_active: When ``False`` the schedule is paused.
        next_run_at: Timestamp of the next scheduled execution.
        last_run_at: Timestamp of the most recent execution attempt.
        last_status: Status string of the most recent execution attempt.
        created_at: Timestamp set by the database when the row is inserted.
        updated_at: Timestamp updated on every write.
    """

    __tablename__ = "reconciliation_schedules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    rec_period_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    lookback_days: Mapped[int] = mapped_column(Integer, nullable=False, default=365)
    selected_scripts: Mapped[list] = mapped_column(JSON, nullable=False)
    config_overrides: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    stop_on_error: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    cron_expression: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
