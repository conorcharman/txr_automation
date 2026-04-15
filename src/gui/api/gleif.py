#!/usr/bin/env python3
"""
GLEIF API
=========

Client methods for the GLEIF LEI endpoints.
"""

from typing import Any, Dict, List, Optional

from gui.api.client import ApiClient


def list_scripts(client: ApiClient) -> List[str]:
    """Fetch available GLEIF script names."""
    return client.get("/api/gleif/scripts")


def lookup(
    client: ApiClient,
    lei: str,
    trade_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Look up a single LEI.

    Args:
        client: API client instance.
        lei: LEI code (20 chars).
        trade_date: Optional trade date (ISO format).

    Returns:
        Lookup response with ``lei``, ``isValid``, ``legalName``, etc.
    """
    params: Dict[str, str] = {"lei": lei}
    if trade_date:
        params["trade_date"] = trade_date
    return client.get("/api/gleif/lookup", params=params)


def search(
    client: ApiClient,
    name: str,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Search for entities by name.

    Args:
        client: API client instance.
        name: Entity name query.
        limit: Maximum results (1–100).

    Returns:
        List of search result dicts.
    """
    return client.get("/api/gleif/search", params={"name": name, "limit": limit})


def refresh(client: ApiClient, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Trigger a GLEIF cache refresh.

    Args:
        client: API client instance.
        payload: Refresh configuration.

    Returns:
        Job response dict.
    """
    return client.post("/api/gleif/refresh", payload)


def check(client: ApiClient, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run a GLEIF LEI check (single or batch).

    Args:
        client: API client instance.
        payload: Check request fields.

    Returns:
        Job response dict.
    """
    return client.post("/api/gleif/check", payload)


def backfill(client: ApiClient, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run GLEIF backfill on a CSV file.

    Args:
        client: API client instance.
        payload: Backfill request fields.

    Returns:
        Job response dict.
    """
    return client.post("/api/gleif/backfill", payload)
