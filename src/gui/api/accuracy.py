#!/usr/bin/env python3
"""
Accuracy Testing API
====================

Client methods for the accuracy testing endpoints.
"""

from typing import Any, Dict, List, Optional

from gui.api.client import ApiClient


def list_scripts(client: ApiClient) -> List[str]:
    """Fetch available accuracy validation script names."""
    return client.get("/api/accuracy/scripts")


def run_validation(client: ApiClient, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run a single validation script.

    Args:
        client: API client instance.
        payload: ``RunValidationRequest`` fields (camelCase keys).

    Returns:
        Job response dict with ``id``, ``status``, etc.
    """
    return client.post("/api/accuracy/run", payload)


def run_all_validations(client: ApiClient, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run all validation scripts in sequence.

    Args:
        client: API client instance.
        payload: ``RunAllRequest`` fields.

    Returns:
        Job response dict.
    """
    return client.post("/api/accuracy/run-all", payload)


def run_incidents(client: ApiClient, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run selected incident validations.

    Args:
        client: API client instance.
        payload: ``RunIncidentsRequest`` fields including ``incidents`` list.

    Returns:
        Job response dict.
    """
    return client.post("/api/accuracy/run-incidents", payload)


def discover_incidents(
    client: ApiClient, input_directory: str
) -> Dict[str, Any]:
    """Auto-discover incident files in a directory.

    Args:
        client: API client instance.
        input_directory: Path to scan for incident CSV files.

    Returns:
        Discovery response with ``results`` and ``totalFound``.
    """
    return client.post(
        "/api/accuracy/discover", {"inputDirectory": input_directory}
    )
