"""
Database
========

Async SQLAlchemy engine, session factory, and declarative base for the
TXR Automation API.

All ORM models inherit from ``Base``. Route handlers receive an
``AsyncSession`` via ``Depends(get_db)``.

Usage:
    from api.database import Base, get_db

    # In a route handler:
    async def my_route(db: AsyncSession = Depends(get_db)) -> ...:
        ...
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from api.config import get_settings


class Base(DeclarativeBase):
    """Declarative base class for all ORM models."""


# Engine and session factory are initialised lazily on first use so that
# importing this module does not trigger a database driver import.  This
# is required for the test environment, which overrides ``get_db`` with
# an in-memory SQLite session and may not have the asyncpg driver installed.
_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return the shared async engine, creating it on first call.

    Returns:
        The application-wide ``AsyncEngine`` instance.
    """
    global _engine, _async_session_factory
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_pre_ping=True,
        )
        _async_session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an ``AsyncSession`` for use as a FastAPI dependency.

    Ensures the engine is initialised before yielding a session.

    Yields:
        An open ``AsyncSession`` that is automatically closed on exit.

    Example:
        >>> async def route(db: AsyncSession = Depends(get_db)):
        ...     result = await db.execute(select(Job))
    """
    get_engine()  # Ensure engine and factory are initialised.
    assert _async_session_factory is not None
    async with _async_session_factory() as session:
        yield session
