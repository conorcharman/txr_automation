"""DRR Submission Model
=====================

SQLAlchemy ORM model for the ``drr_submissions`` table, which records the
result of each DRR compliance check run via ``POST /api/drr/compliance-check``.
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from api.database import Base


class DRRSubmission(Base):
    """ORM model for a single DRR compliance check result.

    Attributes:
        id: UUID primary key.
        transaction_ref: The transaction reference string supplied by the caller.
        checked_at: Timestamp when the check was performed.
        overall_status: Aggregate result — pass | fail | warning.
        total_rules: Number of rules evaluated.
        passed: Rules that passed.
        failed: Rules that failed.
        warnings: Rules that produced warnings.
        results: Full JSON array of per-rule results.
    """

    __tablename__ = "drr_submissions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    transaction_ref: Mapped[str] = mapped_column(
        String(200), nullable=False, index=True
    )
    checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    overall_status: Mapped[str] = mapped_column(String(20), nullable=False)
    total_rules: Mapped[int] = mapped_column(nullable=False, default=0)
    passed: Mapped[int] = mapped_column(nullable=False, default=0)
    failed: Mapped[int] = mapped_column(nullable=False, default=0)
    warnings: Mapped[int] = mapped_column(nullable=False, default=0)
    results: Mapped[list | None] = mapped_column(JSON, nullable=True)
