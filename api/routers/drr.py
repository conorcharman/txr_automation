"""DRR Router
===========

REST endpoints for MiFIR RTS 22 DRR compliance checking.

Endpoints:
    GET  /api/drr/rules                — Full RTS 22 rule catalogue with regulatory references
    POST /api/drr/compliance-check     — Validate a single transaction against DRR rules
    GET  /api/drr/submissions          — List past compliance check records
    GET  /api/drr/submissions/{id}     — Single submission detail with full rule results
    POST /api/drr/cdm-report           — CDM TransactionReportInstruction JSON + enrichment
"""

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.database import get_db
from api.models.drr_submission import DRRSubmission
from api.schemas.drr import (
    DRRCdmReportRequest,
    DRRCdmReportResponse,
    DRRComplianceCheckRequest,
    DRRComplianceCheckResponse,
    DRREnrichmentSummary,
    DRRRuleCatalogueEntry,
    DRRRuleResult,
    DRRSubmissionSummary,
    InstrumentEnrichment,
    LeiEnrichment,
)
from src.cdm.enricher import EnrichmentResult, enrich_transaction
from src.cdm.mapper import build_transaction_report
from src.drr.compliance_mapper import check_transaction
from src.drr.rule_catalogue import CATALOGUE

logger = logging.getLogger(__name__)

router = APIRouter(tags=["drr"])


@router.get("/drr/rules", response_model=list[DRRRuleCatalogueEntry])
async def list_rules() -> list[DRRRuleCatalogueEntry]:
    """Return the full MiFIR RTS 22 DRR rule catalogue.

    Each entry corresponds to a reporting rule in the ISDA DRR model
    (regulation-esma-mifir-rule.rosetta) with its regulatory reference,
    field number, and provision text from Commission Delegated Regulation
    (EU) 2017/590 Annex I Table 2.

    Returns:
        List of rule catalogue entries sorted by field number.
    """
    return sorted(
        [
            DRRRuleCatalogueEntry(
                rule_name=ref.rule_name,
                field_number=ref.field_number,
                field_name=ref.field_name,
                regulation=ref.regulation,
                provision=ref.provision,
            )
            for ref in CATALOGUE.values()
        ],
        key=lambda r: r.field_number.zfill(3),
    )


@router.post("/drr/compliance-check", response_model=DRRComplianceCheckResponse)
async def compliance_check(
    body: DRRComplianceCheckRequest,
    db: AsyncSession = Depends(get_db),
) -> DRRComplianceCheckResponse:
    """Validate a single transaction against MiFIR RTS 22 DRR rules.

    Runs field-level validation checks mapped to named DRR reporting rules.
    Each result includes the rule name, RTS 22 field number, regulatory
    provision text, and pass/fail/warning status.

    The check result is persisted to the ``drr_submissions`` table for
    audit and history purposes.

    Args:
        body: Transaction fields to validate.
        db: Async database session injected by FastAPI.

    Returns:
        Compliance report with per-rule results and aggregate status.
    """
    report = check_transaction(
        transaction_ref=body.transaction_ref,
        buyer_id=body.buyer_id,
        buyer_id_type=body.buyer_id_type,
        seller_id=body.seller_id,
        seller_id_type=body.seller_id_type,
        trading_date_time=body.trading_date_time,
        quantity=body.quantity,
        net_amount=body.net_amount,
        venue=body.venue,
        isin=body.isin,
        investment_decision_maker=body.investment_decision_maker,
    )

    rule_results = [
        DRRRuleResult(
            rule_name=r.rule_name,
            field_number=r.field_number,
            field_name=r.field_name,
            regulation=r.regulation,
            provision=r.provision,
            status=r.status.value,
            value=r.value,
            error=r.error,
        )
        for r in report.results
    ]

    submission = DRRSubmission(
        transaction_ref=report.transaction_ref,
        checked_at=report.checked_at,
        overall_status=report.overall_status.value,
        total_rules=len(report.results),
        passed=report.passed,
        failed=report.failed,
        warnings=report.warnings,
        results=[r.model_dump() for r in rule_results],
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)

    return DRRComplianceCheckResponse(
        submission_id=submission.id,
        transaction_ref=report.transaction_ref,
        checked_at=report.checked_at,
        overall_status=report.overall_status.value,
        results=rule_results,
        total_rules=len(report.results),
        passed=report.passed,
        failed=report.failed,
        warnings=report.warnings,
    )


@router.get("/drr/submissions", response_model=list[DRRSubmissionSummary])
async def list_submissions(
    db: AsyncSession = Depends(get_db),
) -> list[DRRSubmissionSummary]:
    """Return past DRR compliance check records, newest first.

    Returns:
        List of submission summaries (without full rule results).
    """
    result = await db.execute(
        select(DRRSubmission).order_by(DRRSubmission.checked_at.desc()).limit(200)
    )
    rows = result.scalars().all()
    return [
        DRRSubmissionSummary(
            submission_id=row.id,
            transaction_ref=row.transaction_ref,
            checked_at=row.checked_at,
            overall_status=row.overall_status,
            total_rules=row.total_rules,
            passed=row.passed,
            failed=row.failed,
            warnings=row.warnings,
        )
        for row in rows
    ]


@router.get("/drr/submissions/{submission_id}", response_model=DRRComplianceCheckResponse)
async def get_submission(
    submission_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> DRRComplianceCheckResponse:
    """Return a single DRR compliance check result with full rule results.

    Args:
        submission_id: UUID of the submission to retrieve.
        db: Async database session injected by FastAPI.

    Returns:
        Full compliance report including per-rule results.

    Raises:
        HTTPException: 404 if the submission is not found.
    """
    result = await db.execute(
        select(DRRSubmission).where(DRRSubmission.id == submission_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    rule_results = [DRRRuleResult(**r) for r in (row.results or [])]
    return DRRComplianceCheckResponse(
        submission_id=row.id,
        transaction_ref=row.transaction_ref,
        checked_at=row.checked_at,
        overall_status=row.overall_status,
        results=rule_results,
        total_rules=row.total_rules,
        passed=row.passed,
        failed=row.failed,
        warnings=row.warnings,
    )


def _enrichment_result_to_schema(enrichment: EnrichmentResult) -> DRREnrichmentSummary:
    """Convert a src.cdm EnrichmentResult to the API schema."""
    buyer_schema = None
    if enrichment.buyer is not None:
        b = enrichment.buyer
        buyer_schema = LeiEnrichment(
            lei=b.lei, found=b.found, is_valid=b.is_valid, reason=b.reason,
            legal_name=b.legal_name, entity_status=b.entity_status,
            registration_status=b.registration_status,
            legal_address_country=b.legal_address_country,
        )

    seller_schema = None
    if enrichment.seller is not None:
        s = enrichment.seller
        seller_schema = LeiEnrichment(
            lei=s.lei, found=s.found, is_valid=s.is_valid, reason=s.reason,
            legal_name=s.legal_name, entity_status=s.entity_status,
            registration_status=s.registration_status,
            legal_address_country=s.legal_address_country,
        )

    instrument_schema = None
    if enrichment.instrument is not None:
        i = enrichment.instrument
        instrument_schema = InstrumentEnrichment(
            isin=i.isin, found=i.found,
            full_name=i.full_name, cfi_code=i.cfi_code, mic=i.mic,
        )

    return DRREnrichmentSummary(
        buyer=buyer_schema,
        seller=seller_schema,
        instrument=instrument_schema,
    )


@router.post("/drr/cdm-report", response_model=DRRCdmReportResponse)
async def cdm_report(body: DRRCdmReportRequest) -> DRRCdmReportResponse:
    """Produce a CDM TransactionReportInstruction JSON with GLEIF/FIRDS enrichment.

    Runs the same compliance checks as /drr/compliance-check but does not
    persist to the database.  Additionally:

    - Looks up buyer and seller LEIs in the local GLEIF Golden Copy cache.
    - Looks up the instrument ISIN in the local FIRDS cache.
    - Assembles a CDM-shaped TransactionReportInstruction JSON embedding the
      enrichment data.

    Enrichment is best-effort — if the caches are not populated the response
    still contains the CDM JSON, with enrichment slots set to null.

    Args:
        body: Transaction fields to map and enrich.

    Returns:
        CDM report response with JSON, enrichment, and compliance summary.
    """
    # Compliance check (stateless, no DB write)
    report = check_transaction(
        transaction_ref=body.transaction_ref,
        buyer_id=body.buyer_id,
        buyer_id_type=body.buyer_id_type,
        seller_id=body.seller_id,
        seller_id_type=body.seller_id_type,
        trading_date_time=body.trading_date_time,
        quantity=body.quantity,
        net_amount=body.net_amount,
        venue=body.venue,
        isin=body.isin,
        investment_decision_maker=body.investment_decision_maker,
    )

    # Build enrichment — caches constructed from settings (best-effort)
    gleif_lookup = None
    firds_cache = None
    try:
        from src.gleif import GleifCacheManager, GleifLookup
        settings = get_settings()
        gleif_lookup = GleifLookup(cache=GleifCacheManager(Path(settings.gleif_db_path)))
    except Exception:
        logger.debug("GLEIF cache unavailable for CDM enrichment", exc_info=True)

    try:
        from src.firds import FirdsCacheManager
        settings = get_settings()
        firds_cache = FirdsCacheManager(db_path=Path(settings.firds_db_path))
    except Exception:
        logger.debug("FIRDS cache unavailable for CDM enrichment", exc_info=True)

    enrichment = enrich_transaction(
        buyer_id=body.buyer_id,
        buyer_id_type=body.buyer_id_type,
        seller_id=body.seller_id,
        seller_id_type=body.seller_id_type,
        isin=body.isin,
        venue=body.venue,
        gleif_lookup=gleif_lookup,
        firds_cache=firds_cache,
    )

    cdm_json = build_transaction_report(
        transaction_ref=body.transaction_ref,
        buyer_id=body.buyer_id,
        buyer_id_type=body.buyer_id_type,
        seller_id=body.seller_id,
        seller_id_type=body.seller_id_type,
        trading_date_time=body.trading_date_time,
        quantity=body.quantity,
        net_amount=body.net_amount,
        venue=body.venue,
        isin=body.isin,
        investment_decision_maker=body.investment_decision_maker,
        enrichment=enrichment,
    )

    return DRRCdmReportResponse(
        transaction_ref=body.transaction_ref,
        cdm_json=cdm_json,
        enrichment=_enrichment_result_to_schema(enrichment),
        compliance_status=report.overall_status.value,
        passed=report.passed,
        failed=report.failed,
        warnings=report.warnings,
    )
