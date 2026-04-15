#!/usr/bin/env python3
"""
Reconciliation API
==================

Client methods for the reconciliation schedule endpoints.
"""

from typing import Any, Dict, List

from gui.api.client import ApiClient


def list_reconciliations(client: ApiClient) -> List[Dict[str, Any]]:
    """Fetch all reconciliation schedules."""
    return client.get("/api/reconciliations")


def get_reconciliation(client: ApiClient, rec_id: str) -> Dict[str, Any]:
    """Fetch a single reconciliation schedule by ID."""
    return client.get(f"/api/reconciliations/{rec_id}")


def create_reconciliation(
    client: ApiClient, payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Create a new reconciliation schedule.

    Args:
        client: API client instance.
        payload: ``ReconciliationCreate`` fields (camelCase keys).

    Returns:
        Reconciliation response dict.
    """
    return client.post("/api/reconciliations", payload)


def update_reconciliation(
    client: ApiClient, rec_id: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Update an existing reconciliation schedule.

    Args:
        client: API client instance.
        rec_id: UUID string.
        payload: ``ReconciliationUpdate`` fields.

    Returns:
        Updated reconciliation response dict.
    """
    return client.put(f"/api/reconciliations/{rec_id}", payload)


def delete_reconciliation(client: ApiClient, rec_id: str) -> None:
    """Delete a reconciliation schedule."""
    client.delete(f"/api/reconciliations/{rec_id}")


def trigger_reconciliation(client: ApiClient, rec_id: str) -> Dict[str, Any]:
    """Manually trigger a reconciliation to run now.

    Args:
        client: API client instance.
        rec_id: UUID string.

    Returns:
        Trigger response with ``jobId``.
    """
    return client.post(f"/api/reconciliations/{rec_id}/trigger")


def toggle_reconciliation(client: ApiClient, rec_id: str) -> Dict[str, Any]:
    """Toggle a reconciliation schedule's active state.

    Args:
        client: API client instance.
        rec_id: UUID string.

    Returns:
        Updated reconciliation response dict.
    """
    return client.post(f"/api/reconciliations/{rec_id}/toggle")
