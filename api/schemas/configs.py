"""
Config Schemas
==============

Pydantic v2 schemas for saved configuration creation, update, and
retrieval endpoints.

All schemas use camelCase aliases for JSON serialisation to match the
React frontend convention, whilst still accepting snake_case attribute
names in Python code.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import ConfigDict, Field
from pydantic.alias_generators import to_camel

from api.models.saved_config import SavedConfig
from api.schemas.common import _CamelModel


class SavedConfigCreate(_CamelModel):
    """Request body for creating a saved configuration.

    Attributes:
        name: Human-readable name for the configuration, max 200 characters.
        script_name: Registered script identifier, e.g. ``"buyer_id_validation"``.
        config_data: Arbitrary key-value configuration data.
    """

    name: str = Field(..., max_length=200)
    script_name: str
    config_data: dict


class SavedConfigUpdate(_CamelModel):
    """Request body for updating an existing saved configuration.

    All fields are optional; only provided fields are updated.

    Attributes:
        name: New human-readable name, max 200 characters.
        config_data: Replacement configuration data.
    """

    name: str | None = Field(None, max_length=200)
    config_data: dict | None = None


class SavedConfigResponse(_CamelModel):
    """Response body representing a saved configuration record.

    All datetime fields are serialised as ISO 8601 strings so that the
    frontend can parse them uniformly.

    Attributes:
        id: UUID of the saved config as a plain string.
        name: Human-readable name of the configuration.
        script_name: The script this configuration belongs to.
        config_data: The stored configuration key-value pairs.
        created_at: ISO 8601 timestamp of when the row was created.
        updated_at: ISO 8601 timestamp of the most recent update.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    id: str
    name: str
    script_name: str
    config_data: dict
    created_at: str
    updated_at: str

    @classmethod
    def from_orm_config(cls, config: SavedConfig) -> "SavedConfigResponse":
        """Construct a ``SavedConfigResponse`` from a ``SavedConfig`` ORM instance.

        Handles UUID-to-string conversion and datetime-to-ISO-8601 conversion
        so that route handlers do not need to repeat this logic.

        Args:
            config: A ``SavedConfig`` ORM instance loaded from the database.

        Returns:
            A fully populated ``SavedConfigResponse``.
        """

        def _iso(dt: datetime | None) -> str:
            if dt is None:
                return ""
            return dt.isoformat()

        return cls(
            id=str(config.id),
            name=config.name,
            script_name=config.script_name,
            config_data=config.config_data,
            created_at=_iso(config.created_at),
            updated_at=_iso(config.updated_at),
        )
