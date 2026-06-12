"""
Utilities Router
================

REST endpoints for triggering file conversion utility scripts as background jobs.

Endpoints:
    GET  /api/utilities/scripts       — List registered utility script names
    POST /api/utilities/xlsx-convert  — Convert XLSX files to CSV
    POST /api/utilities/xml-convert   — Convert an XML file to CSV
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.schemas.jobs import JobResponse
from api.schemas.utilities import (
    SetupDirectoriesRequest,
    XsdColumnEntry,
    XsdParseRequest,
    XsdParseResponse,
    XlsxConverterRequest,
    XmlConverterRequest,
)
from api.services.job_service import job_service
from api.services.script_runner import script_runner_service
from api.services.xsd_schema_service import xsd_schema_service
from api.tasks.script_tasks import run_script

logger = logging.getLogger(__name__)

router = APIRouter(tags=["utilities"])

_UTILITY_SCRIPTS: list[str] = sorted(
    [
        "setup_directories",
        "xlsx_csv_converter",
        "xml_csv_converter",
    ]
)


@router.get("/utilities/scripts", response_model=list[str])
async def list_utility_scripts() -> list[str]:
    """Return a sorted list of all registered utility script names.

    Returns:
        Alphabetically sorted list of utility script name strings.
    """
    return _UTILITY_SCRIPTS


@router.post("/utilities/xlsx-convert", response_model=JobResponse)
async def xlsx_convert(
    body: XlsxConverterRequest,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Convert XLSX files to CSV format as a background Celery job.

    Supports recursive scanning of a parent directory or single-directory mode.

    Args:
        body: Validated ``XlsxConverterRequest`` from the request body.
        db: Async database session injected by FastAPI.

    Returns:
        A ``JobResponse`` for the newly created pending job.
    """
    module_path, argv, config_snapshot = script_runner_service.build_utilities_argv(
        body, "xlsx_csv_converter"
    )
    job = await job_service.create_job(db, "xlsx_csv_converter", config_snapshot)

    run_script.delay(str(job.id), module_path, argv, config_snapshot)
    logger.info("Dispatched XLSX converter task for job %s.", job.id)

    return JobResponse.from_orm_job(job)


@router.post("/utilities/xml-convert", response_model=JobResponse)
async def xml_convert(
    body: XmlConverterRequest,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Convert a single XML file to CSV format as a background Celery job.

    Args:
        body: Validated ``XmlConverterRequest`` from the request body.
        db: Async database session injected by FastAPI.

    Returns:
        A ``JobResponse`` for the newly created pending job.
    """
    module_path, argv, config_snapshot = script_runner_service.build_utilities_argv(
        body, "xml_csv_converter"
    )
    job = await job_service.create_job(db, "xml_csv_converter", config_snapshot)

    run_script.delay(str(job.id), module_path, argv, config_snapshot)
    logger.info("Dispatched XML converter task for job %s.", job.id)

    return JobResponse.from_orm_job(job)


@router.post("/utilities/xsd-parse", response_model=XsdParseResponse)
async def parse_xsd_schema(body: XsdParseRequest) -> XsdParseResponse:
    """Parse user-supplied XSD and return flattened column metadata.

    Args:
        body: Request containing raw XSD text.

    Returns:
        Flattened field metadata suitable for preview in the frontend.

    Raises:
        HTTPException: 422 when the supplied XSD cannot be parsed.
    """
    try:
        parsed = xsd_schema_service.parse_schema(body.xsd_content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return XsdParseResponse(
        columns=[XsdColumnEntry(**entry) for entry in parsed.columns],
        column_count=len(parsed.columns),
        warnings=parsed.warnings,
        errors=parsed.errors,
        unsupported_constructs=parsed.unsupported_constructs,
        stats=parsed.stats,
    )


@router.post("/utilities/setup-directories", response_model=JobResponse)
async def setup_directories(
    body: SetupDirectoriesRequest,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Create the standard FY/Q directory hierarchy as a background Celery job.

    Creates all ``accuracy_testing/`` and ``replay/`` subdirectories under
    ``{data_dir}/{fiscal_year}/{quarter}/``.  The operation is idempotent —
    existing directories are skipped without error.

    Args:
        body: Validated ``SetupDirectoriesRequest`` from the request body.
        db: Async database session injected by FastAPI.

    Returns:
        A ``JobResponse`` for the newly created pending job.
    """
    module_path, argv, config_snapshot = script_runner_service.build_utilities_argv(
        body, "setup_directories"
    )
    job = await job_service.create_job(db, "setup_directories", config_snapshot)

    run_script.delay(str(job.id), module_path, argv, config_snapshot)
    logger.info("Dispatched setup-directories task for job %s.", job.id)

    return JobResponse.from_orm_job(job)
