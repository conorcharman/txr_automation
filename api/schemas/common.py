"""
Common Schemas
==============

Shared Pydantic v2 schemas used across multiple routers.

All schemas use camelCase aliases for JSON serialisation to match the
React frontend convention, whilst still accepting snake_case attribute
names in Python code.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    """Base model with camelCase JSON aliases."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class JobStatus(str, Enum):
    """Valid status values for a background job.

    Attributes:
        PENDING: Job has been created but not yet started.
        RUNNING: Job is currently executing.
        SUCCESS: Job completed successfully.
        FAILED: Job encountered an unrecoverable error.
        CANCELLED: Job was cancelled by the user.
    """

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class HealthResponse(_CamelModel):
    """Response body returned by ``GET /api/health``.

    Attributes:
        status: Short status string, typically ``"ok"``.
        version: API version string from application settings.
    """

    status: str
    version: str


class ErrorResponse(_CamelModel):
    """Standard error response body returned on 4xx/5xx responses.

    Attributes:
        error: Short machine-readable error label.
        detail: Optional human-readable description of the error.
    """

    error: str
    detail: str | None = None
