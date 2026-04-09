"""
Job Model
=========

SQLAlchemy ORM model for the ``jobs`` table, which tracks the lifecycle
of every background Celery task triggered via the API.
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from api.database import Base


class Job(Base):
    """ORM model representing a single background processing job.

    Attributes:
        id: UUID primary key, generated automatically.
        script_name: Name of the accuracy-testing script or action executed.
        status: Current lifecycle status (pending/running/success/failed/cancelled).
        created_at: Timestamp set by the database when the row is inserted.
        started_at: Timestamp recorded when the Celery task begins execution.
        completed_at: Timestamp recorded when the Celery task finishes.
        error_message: Human-readable error description when status is ``failed``.
        log_output: Full captured stdout/stderr of the script run, persisted on completion.
        config_snapshot: JSON copy of the configuration used for this run.
        output_files: JSON list of relative output file paths produced by the run.
    """

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    script_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    log_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_files: Mapped[list | None] = mapped_column(JSON, nullable=True)
