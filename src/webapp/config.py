#!/usr/bin/env python3
"""
Web Application Configuration
================================

Configuration classes for the TXR Automation web application.
Supports development and production environments.

Usage:
    from webapp.config import DevelopmentConfig, ProductionConfig
"""

import os
from pathlib import Path


class Config:
    """Base configuration for the web application."""

    #: Flask secret key — override via TXR_SECRET_KEY environment variable.
    SECRET_KEY: str = os.environ.get("TXR_SECRET_KEY", "dev-secret-change-in-production")

    #: Application root directory.
    APP_ROOT: Path = Path(__file__).parent

    #: Project root directory.
    PROJECT_ROOT: Path = APP_ROOT.parent.parent

    #: Default log level.
    LOG_LEVEL: str = os.environ.get("TXR_LOG_LEVEL", "INFO")

    #: Maximum content length for file uploads (16 MB).
    MAX_CONTENT_LENGTH: int = 16 * 1024 * 1024

    #: Enable JSON sorting (disabled for performance).
    JSON_SORT_KEYS: bool = False


class DevelopmentConfig(Config):
    """Development configuration with debug features enabled."""

    DEBUG: bool = True
    TESTING: bool = False
    LOG_LEVEL: str = "DEBUG"


class ProductionConfig(Config):
    """Production configuration with debug features disabled."""

    DEBUG: bool = False
    TESTING: bool = False
    LOG_LEVEL: str = "WARNING"


class TestingConfig(Config):
    """Testing configuration for automated tests."""

    DEBUG: bool = True
    TESTING: bool = True
    #: Use a fixed secret key for deterministic test behaviour.
    SECRET_KEY: str = "test-secret-key"


#: Mapping from environment name to configuration class.
config_by_name: dict[str, type[Config]] = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}


def get_config(env: str | None = None) -> type[Config]:
    """Return the configuration class for the given environment name.

    Args:
        env: Environment name (development, production, testing).
            Falls back to the TXR_ENV environment variable, then 'default'.

    Returns:
        Configuration class appropriate for the environment.
    """
    if env is None:
        env = os.environ.get("TXR_ENV", "default")
    return config_by_name.get(env, DevelopmentConfig)
