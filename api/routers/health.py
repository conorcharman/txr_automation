"""
Health Router
=============

Provides a lightweight liveness endpoint for load balancers, Docker
healthchecks, and monitoring systems.

Endpoints:
    GET /api/health — Returns ``{"status": "ok", "version": "<version>"}``
"""

from fastapi import APIRouter, Depends

from api.config import Settings, get_settings
from api.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Return the API liveness status and current version.

    Args:
        settings: Application settings injected via ``Depends``.

    Returns:
        A ``HealthResponse`` with ``status="ok"`` and the current version string.
    """
    return HealthResponse(status="ok", version=settings.version)
