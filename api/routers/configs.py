"""
Configs Router
==============

REST endpoints for managing saved script configurations.

Endpoints:
    GET    /api/configs                 — List all saved configs (optional ?script_name= filter)
    GET    /api/configs/{config_id}     — Retrieve a single saved config
    POST   /api/configs                 — Create a new saved config
    PUT    /api/configs/{config_id}     — Update an existing saved config
    DELETE /api/configs/{config_id}     — Delete a saved config
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.schemas.configs import (
    SavedConfigCreate,
    SavedConfigResponse,
    SavedConfigUpdate,
)
from api.services.config_service import config_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["configs"])


@router.get("/configs", response_model=list[SavedConfigResponse])
async def list_configs(
    script_name: str | None = Query(None, description="Filter by script name"),
    db: AsyncSession = Depends(get_db),
) -> list[SavedConfigResponse]:
    """Return all saved configurations, optionally filtered by script name.

    Results are ordered alphabetically by name.

    Args:
        script_name: Optional script identifier to filter results by.
        db: Async database session injected by FastAPI.

    Returns:
        A list of ``SavedConfigResponse`` objects, possibly empty.
    """
    configs = await config_service.list_configs(db, script_name=script_name)
    return [SavedConfigResponse.from_orm_config(c) for c in configs]


@router.get("/configs/{config_id}", response_model=SavedConfigResponse)
async def get_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
) -> SavedConfigResponse:
    """Retrieve a single saved configuration by its UUID.

    Args:
        config_id: String UUID of the saved config to retrieve.
        db: Async database session injected by FastAPI.

    Returns:
        The ``SavedConfigResponse`` for the requested configuration.

    Raises:
        HTTPException: 404 if no configuration with the given UUID exists.
    """
    config = await config_service.get_config(db, config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Saved configuration not found.")
    return SavedConfigResponse.from_orm_config(config)


@router.post("/configs", response_model=SavedConfigResponse)
async def create_config(
    body: SavedConfigCreate,
    db: AsyncSession = Depends(get_db),
) -> SavedConfigResponse:
    """Create a new saved configuration.

    Args:
        body: Request body containing the name, script name, and config data.
        db: Async database session injected by FastAPI.

    Returns:
        The newly created ``SavedConfigResponse``.

    Raises:
        HTTPException: 409 if a configuration with the given name already exists.
    """
    try:
        config = await config_service.create_config(
            db,
            name=body.name,
            script_name=body.script_name,
            config_data=body.config_data,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return SavedConfigResponse.from_orm_config(config)


@router.put("/configs/{config_id}", response_model=SavedConfigResponse)
async def update_config(
    config_id: str,
    body: SavedConfigUpdate,
    db: AsyncSession = Depends(get_db),
) -> SavedConfigResponse:
    """Update an existing saved configuration.

    Only fields present in the request body are updated.

    Args:
        config_id: String UUID of the saved config to update.
        body: Request body containing optional new name and/or config data.
        db: Async database session injected by FastAPI.

    Returns:
        The updated ``SavedConfigResponse``.

    Raises:
        HTTPException: 404 if no configuration with the given UUID exists.
        HTTPException: 409 if the new name conflicts with an existing configuration.
    """
    # Check for name conflict when a new name is requested.
    if body.name is not None:
        existing = await config_service.get_config_by_name(db, body.name)
        if existing is not None and str(existing.id) != config_id:
            raise HTTPException(
                status_code=409,
                detail=f"A saved configuration named '{body.name}' already exists.",
            )

    config = await config_service.update_config(
        db,
        config_id=config_id,
        name=body.name,
        config_data=body.config_data,
    )
    if config is None:
        raise HTTPException(status_code=404, detail="Saved configuration not found.")
    return SavedConfigResponse.from_orm_config(config)


@router.delete("/configs/{config_id}")
async def delete_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """Delete a saved configuration by its UUID.

    Args:
        config_id: String UUID of the saved config to delete.
        db: Async database session injected by FastAPI.

    Returns:
        A dict ``{"deleted": true}`` on success.

    Raises:
        HTTPException: 404 if no configuration with the given UUID exists.
    """
    deleted = await config_service.delete_config(db, config_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Saved configuration not found.")
    return {"deleted": True}
