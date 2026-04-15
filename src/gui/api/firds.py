#!/usr/bin/env python3
"""
FIRDS API
=========

Client methods for the FIRDS reportability endpoints.
"""

from typing import Any, Dict, List, Optional

from gui.api.client import ApiClient


def list_scripts(client: ApiClient) -> List[str]:
    """Fetch available FIRDS script names."""
    return client.get("/api/firds/scripts")


def lookup(
    client: ApiClient,
    isin: str,
    trade_date: Optional[str] = None,
    mic: Optional[str] = None,
) -> Dict[str, Any]:
    """Look up a single ISIN for reportability.

    Args:
        client: API client instance.
        isin: ISIN code.
        trade_date: Optional trade date (ISO format).
        mic: Optional MIC code.

    Returns:
        Lookup response with ``isReportable``, ``reason``, etc.
    """
    params: Dict[str, str] = {"isin": isin}
    if trade_date:
        params["trade_date"] = trade_date
    if mic:
        params["mic"] = mic
    return client.get("/api/firds/lookup", params=params)


def refresh(client: ApiClient, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Trigger a FIRDS cache refresh.

    Args:
        client: API client instance.
        payload: Refresh configuration.

    Returns:
        Job response dict.
    """
    return client.post("/api/firds/refresh", payload)


def check(client: ApiClient, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run a FIRDS reportability check (single or batch).

    Args:
        client: API client instance.
        payload: Check request fields.

    Returns:
        Job response dict.
    """
    return client.post("/api/firds/check", payload)


def backfill(client: ApiClient, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run FIRDS backfill on a CSV file.

    Args:
        client: API client instance.
        payload: Backfill request fields.

    Returns:
        Job response dict.
    """
    return client.post("/api/firds/backfill", payload)
