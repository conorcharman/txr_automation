#!/usr/bin/env python3
"""
Utilities API
=============

Client methods for the utility script endpoints.
"""

from typing import Any, Dict, List

from gui.api.client import ApiClient


def list_scripts(client: ApiClient) -> List[str]:
    """Fetch available utility script names."""
    return client.get("/api/utilities/scripts")


def xlsx_convert(client: ApiClient, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run XLSX-to-CSV conversion.

    Args:
        client: API client instance.
        payload: Conversion request fields.

    Returns:
        Job response dict.
    """
    return client.post("/api/utilities/xlsx-convert", payload)


def xml_convert(client: ApiClient, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run XML-to-CSV conversion.

    Args:
        client: API client instance.
        payload: Conversion request fields.

    Returns:
        Job response dict.
    """
    return client.post("/api/utilities/xml-convert", payload)


def dashboard_stats(client: ApiClient) -> Dict[str, Any]:
    """Fetch dashboard statistics.

    Args:
        client: API client instance.

    Returns:
        Stats dict with job counts, success rate, etc.
    """
    return client.get("/api/dashboard/stats")
