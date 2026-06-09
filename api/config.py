"""
API Configuration
=================

Pydantic Settings for the TXR Automation API. All values are read from
environment variables or a ``.env`` file at the project root.

Usage:
    from api.config import get_settings, Settings

    settings = get_settings()
    print(settings.database_url)
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or ``.env``.

    Attributes:
        database_url: Async-compatible PostgreSQL connection string.
        redis_url: Redis connection string used by Celery and pub/sub.
        upload_dir: Directory where uploaded files are stored.
        firds_db_path: Path to the FIRDS SQLite cache database.
        gleif_db_path: Path to the GLEIF SQLite cache database.
        fca_api_email: FCA Developer Portal signup email (API username).
        fca_api_key: FCA Developer Portal API key.
        secret_key: Secret key for signing tokens (must be overridden in production).
        version: API version string surfaced by the health endpoint.
        environment: Deployment environment (``dev`` or ``production``).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://txr:changeme@localhost/txr_automation"
    redis_url: str = "redis://localhost:6379/0"
    upload_dir: Path = Path("data/uploads")
    firds_db_path: Path = Path("data/firds_cache.db")
    gleif_db_path: Path = Path("data/gleif_cache.db")
    data_dir: Path = Path("data")
    fca_api_email: str = ""
    fca_api_key: str = ""
    secret_key: str = "dev-secret-key"
    version: str = "1.0.0"
    environment: str = "dev"

    def validate_production(self) -> None:
        """Raise if insecure defaults are still in use for production."""
        if self.environment == "production":
            if self.secret_key == "dev-secret-key":
                raise ValueError(
                    "SECRET_KEY must be overridden in production. "
                    "Set the SECRET_KEY environment variable."
                )
            if "changeme" in self.database_url:
                raise ValueError(
                    "DATABASE_URL still contains placeholder credentials. "
                    "Set the DATABASE_URL environment variable."
                )


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings instance.

    Returns:
        A ``Settings`` instance populated from the environment or ``.env``.
    """
    return Settings()
