"""
Job Schemas
===========

Pydantic v2 schemas for job creation and retrieval endpoints.

All schemas use camelCase aliases for JSON serialisation to match the
React frontend convention, whilst still accepting snake_case attribute
names in Python code.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import ConfigDict
from pydantic.alias_generators import to_camel

from api.models.job import Job
from api.schemas.common import JobStatus, _CamelModel


class JobCreate(_CamelModel):
    """Request body for creating a new background job.

    Attributes:
        script_name: Registered script identifier, e.g. ``"buyer_id_validation"``.
        config: Arbitrary configuration dict forwarded to the task and stored
            as a snapshot on the job row.
    """

    script_name: str
    config: dict


class JobResponse(_CamelModel):
    """Response body representing a single job record.

    All datetime fields are serialised as ISO 8601 strings so that the
    frontend can parse them uniformly.

    Attributes:
        id: UUID of the job as a plain string.
        script_name: Name of the script this job runs.
        status: Current lifecycle status of the job.
        created_at: ISO 8601 timestamp of when the job row was created.
        started_at: ISO 8601 timestamp of when the task began execution, or ``None``.
        completed_at: ISO 8601 timestamp of when the task finished, or ``None``.
        error_message: Human-readable error description when status is ``failed``, or ``None``.
        output_files: List of relative output file paths produced by the run, or ``None``.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    id: str
    script_name: str
    status: JobStatus
    created_at: str | None
    started_at: str | None
    completed_at: str | None
    error_message: str | None
    output_files: list[str] | None

    @classmethod
    def from_orm_job(cls, job: Job) -> "JobResponse":
        """Construct a ``JobResponse`` from a ``Job`` ORM instance.

        Handles UUID-to-string conversion and datetime-to-ISO-8601 conversion
        so that route handlers do not need to repeat this logic.

        Args:
            job: A ``Job`` ORM instance loaded from the database.

        Returns:
            A fully populated ``JobResponse``.
        """
        def _iso(dt: datetime | None) -> str | None:
            if dt is None:
                return None
            return dt.isoformat()

        return cls(
            id=str(job.id),
            script_name=job.script_name,
            status=JobStatus(job.status),
            created_at=_iso(job.created_at),
            started_at=_iso(job.started_at),
            completed_at=_iso(job.completed_at),
            error_message=job.error_message,
            output_files=job.output_files,
        )
