#!/usr/bin/env python3
"""
Flask Application Factory
==========================

Creates and configures the Flask application instance.

Usage:
    from webapp.app import create_app

    app = create_app()            # development (default)
    app = create_app("testing")   # testing
"""

from flask import Flask

from webapp.config import get_config
from webapp.routes import register_blueprints


def create_app(env: str | None = None) -> Flask:
    """Create and configure the Flask application.

    Args:
        env: Environment name passed to :func:`~webapp.config.get_config`.
            Defaults to the value of the ``TXR_ENV`` environment variable,
            or ``'default'`` (development) if unset.

    Returns:
        Configured :class:`flask.Flask` application instance.
    """
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    # Load configuration
    config_class = get_config(env)
    app.config.from_object(config_class)

    # Register all blueprints
    register_blueprints(app)

    return app
