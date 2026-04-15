#!/usr/bin/env python3
"""
GUI API Client
==============

HTTP client layer for communicating with the FastAPI backend.
All script execution flows through the API rather than calling
modules directly.
"""

from gui.api.client import ApiClient, ApiError

__all__ = ["ApiClient", "ApiError"]
