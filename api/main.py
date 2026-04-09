"""
TXR Automation API
==================

FastAPI application entry point for the TXR Automation backend.

Start with uvicorn::

    uvicorn api.main:app --reload

Or with Docker Compose::

    docker compose up api
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import get_settings as _get_settings

# NOTE: ``src.core.logging.create_logger`` requires the project root on
# sys.path, which is guaranteed in production (installed package) and in
# tests (via tests/conftest.py). Standard ``logging`` is used here to
# keep the import unconditionally safe at module level.
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle.

    On startup, imports all ORM models so SQLAlchemy registers their
    table metadata with ``Base``, then runs ``create_all`` to ensure the
    schema exists.  Errors (e.g. Postgres unavailable in test
    environments) are caught and logged as warnings rather than crashing
    the process — tests supply their own in-memory database via
    ``app.dependency_overrides``.

    Args:
        app: The FastAPI application instance.

    Yields:
        Control to the running application.
    """
    # Import models here to register their metadata with Base before create_all.
    import api.models.job  # noqa: F401
    import api.models.saved_config  # noqa: F401

    from api.database import Base, get_engine

    try:
        async with get_engine().begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created / verified.")
    except Exception as exc:  # noqa: BLE001
        # In test environments Postgres is not available; tests override
        # get_db with an in-memory SQLite engine and create tables themselves.
        logger.warning("Could not create database tables: %s", exc)

    yield

    logger.info("API shutting down.")


_settings = _get_settings()
_settings.validate_production()

# Disable OpenAPI docs in production to avoid exposing API schema publicly.
_docs_url = "/docs" if _settings.environment != "production" else None
_redoc_url = "/redoc" if _settings.environment != "production" else None

app = FastAPI(
    title="TXR Automation API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url="/openapi.json" if _settings.environment != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# ── Routers ────────────────────────────────────────────────────────────────
from api.routers.accuracy import router as accuracy_router  # noqa: E402
from api.routers.configs import router as configs_router  # noqa: E402
from api.routers.dashboard import router as dashboard_router  # noqa: E402
from api.routers.filesystem import router as filesystem_router  # noqa: E402
from api.routers.firds import router as firds_router  # noqa: E402
from api.routers.gleif import router as gleif_router  # noqa: E402
from api.routers.health import router as health_router  # noqa: E402
from api.routers.jobs import router as jobs_router  # noqa: E402
from api.routers.replay import router as replay_router  # noqa: E402
from api.routers.utilities import router as utilities_router  # noqa: E402

app.include_router(health_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")
app.include_router(configs_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(accuracy_router, prefix="/api")
app.include_router(replay_router, prefix="/api")
app.include_router(firds_router, prefix="/api")
app.include_router(gleif_router, prefix="/api")
app.include_router(utilities_router, prefix="/api")
app.include_router(filesystem_router, prefix="/api")
