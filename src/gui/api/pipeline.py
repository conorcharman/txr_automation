#!/usr/bin/env python3
"""
Pipeline API
============

Client methods for the accuracy testing pipeline endpoints.
"""

from typing import Any, Dict, List

from gui.api.client import ApiClient


def list_pipelines(client: ApiClient) -> List[Dict[str, Any]]:
    """Fetch all pipelines."""
    return client.get("/api/pipelines")


def get_pipeline(client: ApiClient, pipeline_id: str) -> Dict[str, Any]:
    """Fetch a single pipeline by ID."""
    return client.get(f"/api/pipelines/{pipeline_id}")


def create_pipeline(client: ApiClient, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new accuracy testing pipeline.

    Args:
        client: API client instance.
        payload: ``PipelineCreate`` fields (camelCase keys).

    Returns:
        Pipeline response dict.
    """
    return client.post("/api/pipelines", payload)


def update_pipeline(
    client: ApiClient, pipeline_id: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Update an existing pipeline.

    Args:
        client: API client instance.
        pipeline_id: UUID string.
        payload: ``PipelineUpdate`` fields.

    Returns:
        Updated pipeline response dict.
    """
    return client.put(f"/api/pipelines/{pipeline_id}", payload)


def delete_pipeline(client: ApiClient, pipeline_id: str) -> None:
    """Delete a pipeline."""
    client.delete(f"/api/pipelines/{pipeline_id}")


def trigger_pipeline(client: ApiClient, pipeline_id: str) -> Dict[str, Any]:
    """Manually trigger a pipeline to run now.

    Args:
        client: API client instance.
        pipeline_id: UUID string.

    Returns:
        Trigger response with ``jobId``.
    """
    return client.post(f"/api/pipelines/{pipeline_id}/trigger")


def toggle_pipeline(client: ApiClient, pipeline_id: str) -> Dict[str, Any]:
    """Toggle a pipeline's active state.

    Args:
        client: API client instance.
        pipeline_id: UUID string.

    Returns:
        Updated pipeline response dict.
    """
    return client.post(f"/api/pipelines/{pipeline_id}/toggle")
