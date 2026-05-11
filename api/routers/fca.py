"""
FCA Router
==========

REST endpoints for FCA Financial Services Register firm lookups.

Endpoints:
    GET  /api/fca/lookup?frn=...    — Look up a firm by FRN (synchronous)
    GET  /api/fca/search?name=...   — Search firms by name (synchronous)
    POST /api/fca/check             — Batch CSV check via Celery background job
"""

import difflib
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.schemas.fca import (
    FcaCheckRequest,
    FcaLeiSearchResponse,
    FcaLookupResponse,
    FcaPermissionResponse,
    FcaSearchResponse,
    FcaSearchResult,
)
from api.schemas.jobs import JobResponse
from api.services.fca_service import fca_lookup_service
from api.services.job_service import job_service
from api.services.lookup import gleif_lookup_service
from api.services.script_runner import script_runner_service
from api.tasks.script_tasks import run_script

logger = logging.getLogger(__name__)

router = APIRouter(tags=["fca"])

_FCA_SCRIPTS: list[str] = ["fca_check"]


@router.get("/fca/scripts", response_model=list[str])
async def list_fca_scripts() -> list[str]:
    """Return a sorted list of registered FCA script names.

    Returns:
        List of FCA script name strings.
    """
    return _FCA_SCRIPTS


@router.get("/fca/lookup", response_model=FcaLookupResponse)
async def fca_lookup(frn: str) -> FcaLookupResponse:
    """Look up a single firm by FRN from the FCA Register (synchronous).

    Makes two live API requests (firm details + permissions) and returns
    the result immediately without queuing a background job.

    Args:
        frn: Firm Reference Number to look up.

    Returns:
        An ``FcaLookupResponse`` with the firm's authorisation status and
        regulated activity permissions.
    """
    raw = fca_lookup_service.lookup_by_frn(frn)
    permissions = [FcaPermissionResponse(**p) for p in raw.pop("permissions", [])]
    return FcaLookupResponse(**raw, permissions=permissions)


@router.get("/fca/search", response_model=FcaSearchResponse)
async def fca_search(name: str) -> FcaSearchResponse:
    """Search for firms by name in the FCA Register (synchronous).

    Makes one live API request and returns all matching firms immediately.

    Args:
        name: Firm name or name substring to search for.

    Returns:
        An ``FcaSearchResponse`` containing all matching firm records.
    """
    raw = fca_lookup_service.search_by_name(name)
    results = [FcaSearchResult(**r) for r in raw.get("results", [])]
    return FcaSearchResponse(results=results, count=raw.get("count", len(results)))


@router.get("/fca/lookup-by-lei", response_model=FcaLeiSearchResponse)
async def fca_lookup_by_lei(lei: str) -> FcaLeiSearchResponse:
    """Look up a firm on the FCA register using an LEI (synchronous).

    Resolves the LEI to a legal entity name via the local GLEIF database,
    then searches the FCA register by that name.  The single closest-matching
    firm (scored by name similarity using :mod:`difflib`) is returned.

    Args:
        lei: The 20-character Legal Entity Identifier to resolve.

    Returns:
        An ``FcaLeiSearchResponse`` containing the resolved GLEIF name and
        the closest-matching FCA firm record, or ``None`` if no match found.

    Raises:
        HTTPException: 404 if the LEI is not present in the local GLEIF
            database.
    """
    gleif_result = gleif_lookup_service.lookup_lei(lei.strip().upper())
    if gleif_result["reason"] == "NOT_IN_GLEIF":
        raise HTTPException(
            status_code=404,
            detail=f"LEI '{lei}' not found in the local GLEIF database.",
        )

    resolved_name: str = gleif_result["legal_name"]
    fca_raw = fca_lookup_service.search_by_name(resolved_name)
    candidates = fca_raw.get("results", [])

    if not candidates:
        return FcaLeiSearchResponse(lei=lei, resolved_name=resolved_name, result=None)

    best = max(
        candidates,
        key=lambda c: difflib.SequenceMatcher(
            None,
            c["organisation_name"].lower(),
            resolved_name.lower(),
        ).ratio(),
    )
    return FcaLeiSearchResponse(
        lei=lei,
        resolved_name=resolved_name,
        result=FcaSearchResult(**best),
    )


@router.post("/fca/check", response_model=JobResponse)
async def fca_check(
    body: FcaCheckRequest,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Run a batch FCA firm check as a background Celery job.

    Accepts a single FRN, name search, or batch CSV file path.  The job
    result is retrievable via ``GET /api/jobs/{job_id}``.

    Args:
        body: Validated ``FcaCheckRequest`` from the request body.
        db: Async database session injected by FastAPI.

    Returns:
        A ``JobResponse`` for the newly created pending job.
    """
    module_path, argv, snapshot = script_runner_service.build_fca_argv(body)
    job = await job_service.create_job(db, "fca_check", snapshot)
    run_script.delay(str(job.id), module_path, argv, snapshot)
    return JobResponse.model_validate(job)
