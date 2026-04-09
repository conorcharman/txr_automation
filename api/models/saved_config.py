"""
Saved Config Model
==================

SQLAlchemy ORM model for the ``saved_configs`` table, which persists
named YAML-equivalent configuration snapshots for reuse via the UI.
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from api.database import Base


class SavedConfig(Base):
    """ORM model for a persisted, named script configuration.

    Attributes:
        id: UUID primary key, generated automatically.
        name: Human-readable name for the saved configuration (unique).
        script_name: The accuracy-testing script this configuration belongs to.
        config_data: JSON object holding the configuration key-value pairs.
        created_at: Timestamp set by the database on insert.
        updated_at: Timestamp updated automatically on every row update.
    """

    __tablename__ = "saved_configs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    script_name: Mapped[str] = mapped_column(String(200), nullable=False)
    config_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
