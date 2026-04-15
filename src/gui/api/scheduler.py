#!/usr/bin/env python3
"""
Scheduler API
=============

Client methods for the schedule management endpoints.
"""

from typing import Any, Dict, List

from gui.api.client import ApiClient


def list_schedules(client: ApiClient) -> List[Dict[str, Any]]:
    """Fetch all schedules."""
    return client.get("/api/schedules")


def get_schedule(client: ApiClient, schedule_id: str) -> Dict[str, Any]:
    """Fetch a single schedule by ID."""
    return client.get(f"/api/schedules/{schedule_id}")


def create_schedule(client: ApiClient, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new schedule.

    Args:
        client: API client instance.
        payload: ``ScheduleCreate`` fields (camelCase keys).

    Returns:
        Schedule response dict.
    """
    return client.post("/api/schedules", payload)


def update_schedule(
    client: ApiClient, schedule_id: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Update an existing schedule.

    Args:
        client: API client instance.
        schedule_id: UUID string.
        payload: ``ScheduleUpdate`` fields.

    Returns:
        Updated schedule response dict.
    """
    return client.put(f"/api/schedules/{schedule_id}", payload)


def delete_schedule(client: ApiClient, schedule_id: str) -> None:
    """Delete a schedule."""
    client.delete(f"/api/schedules/{schedule_id}")


def trigger_schedule(client: ApiClient, schedule_id: str) -> Dict[str, Any]:
    """Manually trigger a schedule to run now.

    Args:
        client: API client instance.
        schedule_id: UUID string.

    Returns:
        Trigger response with job ID.
    """
    return client.post(f"/api/schedules/{schedule_id}/trigger")


def toggle_schedule(client: ApiClient, schedule_id: str) -> Dict[str, Any]:
    """Toggle a schedule's active state.

    Args:
        client: API client instance.
        schedule_id: UUID string.

    Returns:
        Updated schedule response dict.
    """
    return client.post(f"/api/schedules/{schedule_id}/toggle")
