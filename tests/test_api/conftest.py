"""
Test API Fixtures
=================

Shared pytest fixtures for the ``tests/test_api/`` suite.

An in-memory SQLite database (via ``aiosqlite``) is used in place of
PostgreSQL so that tests run without any external services.  The
``get_db`` dependency is overridden for every test via
``app.dependency_overrides``.
"""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from api.database import Base, get_db
from api.main import app

pytest_plugins = ("anyio",)

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Select the asyncio backend for anyio.

    Returns:
        The string ``"asyncio"``.
    """
    return "asyncio"


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Yield an ``AsyncClient`` wired to the FastAPI app with a clean
    in-memory SQLite database for each test.

    The fixture:

    1. Creates an in-memory SQLite engine and runs ``create_all``.
    2. Overrides ``get_db`` so route handlers use the test session.
    3. Yields an ``AsyncClient`` targeting the ASGI app directly.
    4. Drops all tables and disposes the engine on teardown.

    Yields:
        An ``AsyncClient`` ready to make requests against the API.
    """
    # Build a fresh in-memory engine for each test.
    test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    # Create schema in the test database.
    # Import models to ensure their metadata is registered with Base.
    import api.models.drr_submission  # noqa: F401
    import api.models.job  # noqa: F401
    import api.models.saved_config  # noqa: F401

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    # Teardown.
    app.dependency_overrides.clear()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()
