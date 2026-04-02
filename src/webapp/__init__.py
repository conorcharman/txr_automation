#!/usr/bin/env python3
"""
TXR Automation Web Application
================================

Flask-based web interface for the TXR Automation suite, providing a
browser-accessible alternative to the desktop GUI.

Usage:
    python -m webapp
    flask --app webapp.app run
"""

from webapp.app import create_app

__all__ = ["create_app"]
