#!/usr/bin/env python3
"""
Replay API
==========

Client methods for the replay processing endpoints.
"""

from typing import Any, Dict, List

from gui.api.client import ApiClient


def list_scripts(client: ApiClient) -> List[str]:
    """Fetch available replay script names."""
    return client.get("/api/replay/scripts")


def run_phase2(client: ApiClient, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run Phase II replay processing.

    Args:
        client: API client instance.
        payload: Phase 2 request fields.

    Returns:
        Job response dict.
    """
    return client.post("/api/replay/phase2", payload)


def run_phase3(client: ApiClient, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run Phase III feedback replay processing.

    Args:
        client: API client instance.
        payload: Phase 3 request fields.

    Returns:
        Job response dict.
    """
    return client.post("/api/replay/phase3", payload)


def run_phase3_final(client: ApiClient, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run Phase III final lookup replay processing.

    Args:
        client: API client instance.
        payload: Phase 3 final request fields.

    Returns:
        Job response dict.
    """
    return client.post("/api/replay/phase3-final", payload)


def run_merge(client: ApiClient, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run replay merge inconsistent operation.

    Args:
        client: API client instance.
        payload: Merge request fields.

    Returns:
        Job response dict.
    """
    return client.post("/api/replay/merge", payload)
