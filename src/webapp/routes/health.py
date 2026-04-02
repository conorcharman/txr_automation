#!/usr/bin/env python3
"""
Health Check Routes
====================

Provides a ``/health`` endpoint for liveness and readiness probes.
"""

from flask import Blueprint, jsonify, Response
from typing import Any

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health_check() -> tuple[Response, int]:
    """Return application health status.

    Returns:
        JSON response with status ``ok`` and HTTP 200.

    Example response::

        {"status": "ok", "app": "TXR Automation", "version": "1.0.0"}
    """
    from webapp.constants import APP_NAME, APP_VERSION

    return jsonify({"status": "ok", "app": APP_NAME, "version": APP_VERSION}), 200
