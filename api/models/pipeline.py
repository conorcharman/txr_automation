"""
Pipeline Model
==============

SQLAlchemy ORM model for the ``pipelines`` table, which stores the
configuration and state of accuracy testing pipeline schedules.

A pipeline is an ordered sequence of accuracy testing scripts that run
sequentially, with a shared fiscal year, quarter, and directory structure.
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from api.database import Base


class Pipeline(Base):
    """ORM model representing a scheduled accuracy testing pipeline.

    Attributes:
        id: UUID primary key, generated automatically.
        name: Unique human-readable name for the pipeline.
        fiscal_year: Fiscal year string, e.g. ``"FY26"``.
        quarter: Quarter string, e.g. ``"Q1"``.
        selected_scripts: JSON array of script keys in execution order.
        frequency: Recurrence cadence — hourly/daily/weekly/monthly/custom.
        cron_expression: Five-field cron string (only used when frequency is ``custom``).
        config_overrides: JSON dict of per-stage path overrides.
        stop_on_error: When ``True``, halt the pipeline on first script failure.
        is_active: When ``False`` the pipeline is paused and will not fire.
        next_run_at: Timestamp of the next scheduled execution.
        last_run_at: Timestamp of the most recent execution attempt.
        last_status: Status string of the most recent execution attempt.
        created_at: Timestamp set by the database when the row is inserted.
        updated_at: Timestamp updated on every write.
    """

    __tablename__ = "pipelines"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    fiscal_year: Mapped[str] = mapped_column(String(10), nullable=False)
    quarter: Mapped[str] = mapped_column(String(5), nullable=False)
    selected_scripts: Mapped[list] = mapped_column(JSON, nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    cron_expression: Mapped[str | None] = mapped_column(String(100), nullable=True)
    config_overrides: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    stop_on_error: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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
