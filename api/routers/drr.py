"""DRR Router
===========

REST endpoints for MiFIR RTS 22 DRR compliance checking.

Endpoints:
    GET  /api/drr/rules                — Full RTS 22 rule catalogue with regulatory references
    POST /api/drr/compliance-check     — Validate a single transaction against DRR rules
    GET  /api/drr/submissions          — List past compliance check records
    GET  /api/drr/submissions/{id}     — Single submission detail with full rule results
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.drr_submission import DRRSubmission
from api.schemas.drr import (
    DRRComplianceCheckRequest,
    DRRComplianceCheckResponse,
    DRRRuleCatalogueEntry,
    DRRRuleResult,
    DRRSubmissionSummary,
)
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
