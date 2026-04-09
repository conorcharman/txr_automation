"""
Schedule Model
==============

SQLAlchemy ORM model for the ``schedules`` table, which stores the
configuration and state of each scheduled pipeline run.
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from api.database import Base


class Schedule(Base):
    """ORM model representing a scheduled pipeline run.

    Attributes:
        id: UUID primary key, generated automatically.
        name: Unique human-readable name for the schedule.
        script_name: Registered script identifier matching the job registry.
        frequency: Recurrence cadence — hourly/daily/weekly/monthly/custom.
        cron_expression: Five-field cron string (only used when frequency is ``custom``).
        config_data: JSON configuration forwarded to the script on each run.
        is_active: When ``False`` the schedule is paused and will not fire.
        next_run_at: Timestamp of the next scheduled execution.
        last_run_at: Timestamp of the most recent execution attempt.
        last_status: Status string of the most recent execution attempt.
        created_at: Timestamp set by the database when the row is inserted.
        updated_at: Timestamp updated on every write.
    """

    __tablename__ = "schedules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    script_name: Mapped[str] = mapped_column(String(200), nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    cron_expression: Mapped[str | None] = mapped_column(String(100), nullable=True)
    config_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
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
