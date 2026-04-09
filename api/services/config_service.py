"""
Config Service
==============

Async service layer for CRUD operations on the ``saved_configs`` table.

All methods accept an ``AsyncSession`` injected via ``Depends(get_db)``
and perform their own commit so that callers do not need to manage
transactions directly.

Usage:
    from api.services.config_service import config_service
    from api.database import get_db

    async def route(db: AsyncSession = Depends(get_db)):
        configs = await config_service.list_configs(db)
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.saved_config import SavedConfig


class ConfigService:
    """Service class encapsulating all saved-configuration persistence operations.

    Methods are intentionally stateless — the ``AsyncSession`` is accepted
    as a parameter so that the service can be used with any session,
    including the test-provided in-memory SQLite session.
    """

    async def list_configs(
        self,
        db: AsyncSession,
        script_name: str | None = None,
    ) -> list[SavedConfig]:
        """List all saved configs, optionally filtered by script name.

        Results are ordered alphabetically by ``name``.

        Args:
            db: Active async database session.
            script_name: When provided, only configs matching this script
                identifier are returned.

        Returns:
            A list of ``SavedConfig`` ORM instances, possibly empty.
        """
        stmt = select(SavedConfig).order_by(SavedConfig.name)
        if script_name is not None:
            stmt = stmt.where(SavedConfig.script_name == script_name)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_config(
        self,
        db: AsyncSession,
        config_id: str,
    ) -> SavedConfig | None:
        """Get a single saved config by its UUID string.

        Args:
            db: Active async database session.
            config_id: String representation of the config UUID.

        Returns:
            The matching ``SavedConfig`` ORM instance, or ``None`` if not found
            or if ``config_id`` is not a valid UUID.
        """
        try:
            parsed_id = uuid.UUID(config_id)
        except ValueError:
            return None

        result = await db.execute(
            select(SavedConfig).where(SavedConfig.id == parsed_id)
        )
        return result.scalar_one_or_none()

    async def get_config_by_name(
        self,
        db: AsyncSession,
        name: str,
    ) -> SavedConfig | None:
        """Get a saved config by its unique human-readable name.

        Args:
            db: Active async database session.
            name: The unique name to look up.

        Returns:
            The matching ``SavedConfig`` ORM instance, or ``None`` if not found.
        """
        result = await db.execute(
            select(SavedConfig).where(SavedConfig.name == name)
        )
        return result.scalar_one_or_none()

    async def create_config(
        self,
        db: AsyncSession,
        name: str,
        script_name: str,
        config_data: dict,
    ) -> SavedConfig:
        """Create a new saved configuration row and return it.

        Args:
            db: Active async database session.
            name: Human-readable name for the new configuration.
            script_name: Registered script identifier the configuration belongs to.
            config_data: Arbitrary key-value configuration data.

        Returns:
            The newly created ``SavedConfig`` ORM instance with all
            server-default fields populated after a flush.

        Raises:
            ValueError: If a configuration with the given ``name`` already exists.
        """
        existing = await self.get_config_by_name(db, name)
        if existing is not None:
            raise ValueError(f"A saved configuration named '{name}' already exists.")

        config = SavedConfig(
            name=name,
            script_name=script_name,
            config_data=config_data,
        )
        db.add(config)
        await db.commit()
        await db.refresh(config)
        return config

    async def update_config(
        self,
        db: AsyncSession,
        config_id: str,
        name: str | None,
        config_data: dict | None,
    ) -> SavedConfig | None:
        """Update an existing saved configuration.

        Only fields that are not ``None`` are modified.

        Args:
            db: Active async database session.
            config_id: String representation of the config UUID to update.
            name: New name to assign, or ``None`` to leave unchanged.
            config_data: Replacement configuration data, or ``None`` to leave unchanged.

        Returns:
            The updated ``SavedConfig`` ORM instance, or ``None`` if not found.
        """
        config = await self.get_config(db, config_id)
        if config is None:
            return None

        if name is not None:
            config.name = name
        if config_data is not None:
            config.config_data = config_data

        await db.commit()
        await db.refresh(config)
        return config

    async def delete_config(
        self,
        db: AsyncSession,
        config_id: str,
    ) -> bool:
        """Delete a saved configuration by its UUID string.

        Args:
            db: Active async database session.
            config_id: String representation of the config UUID to delete.

        Returns:
            ``True`` if the row was found and deleted, ``False`` if not found.
        """
        config = await self.get_config(db, config_id)
        if config is None:
            return False

        await db.delete(config)
        await db.commit()
        return True


config_service = ConfigService()
