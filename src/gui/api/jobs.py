#!/usr/bin/env python3
"""
Jobs API
========

Client methods for the job management endpoints.
"""

from typing import Any, Dict, List, Optional

from gui.api.client import ApiClient


def list_jobs(
    client: ApiClient,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Fetch recent jobs.

    Args:
        client: API client instance.
        limit: Maximum number of jobs to return.
        offset: Pagination offset.

    Returns:
        List of job response dicts.
    """
    return client.get("/api/jobs", params={"limit": limit, "offset": offset})


def get_job(client: ApiClient, job_id: str) -> Dict[str, Any]:
    """Fetch a single job by ID.

    Args:
        client: API client instance.
        job_id: UUID string.

    Returns:
        Job response dict.
    """
    return client.get(f"/api/jobs/{job_id}")


def create_job(client: ApiClient, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new job.

    Args:
        client: API client instance.
        payload: ``CreateJobRequest`` fields.

    Returns:
        Job response dict.
    """
    return client.post("/api/jobs", payload)


def cancel_job(client: ApiClient, job_id: str) -> Dict[str, Any]:
    """Cancel a running or pending job.

    Args:
        client: API client instance.
        job_id: UUID string.

    Returns:
        Updated job response dict.
    """
    return client.post(f"/api/jobs/{job_id}/cancel")


def fetch_last_runs(client: ApiClient) -> Dict[str, Any]:
    """Fetch last-run info keyed by script name.

    Args:
        client: API client instance.

    Returns:
        Dict mapping script names to last-run details.
    """
    return client.get("/api/jobs/last-runs")
