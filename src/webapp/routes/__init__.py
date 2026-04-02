#!/usr/bin/env python3
"""
Routes Package
==============

Registers all Flask blueprints with the application.
"""

from flask import Flask

from webapp.routes.dashboard import dashboard_bp
from webapp.routes.health import health_bp


def register_blueprints(app: Flask) -> None:
    """Register all application blueprints.

    Args:
        app: The Flask application instance.
    """
    app.register_blueprint(health_bp)
    app.register_blueprint(dashboard_bp)


__all__ = ["register_blueprints"]
