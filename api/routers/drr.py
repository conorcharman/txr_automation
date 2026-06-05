"""DRR Router
===========

REST endpoints for MiFIR RTS 22 DRR compliance checking.

Endpoints:
    GET  /api/drr/rules                     — Full RTS 22 rule catalogue with regulatory references
    POST /api/drr/compliance-check          — Validate a single transaction against DRR rules
    POST /api/drr/compliance-check/bulk     — Validate many transactions from a CSV upload
    GET  /api/drr/submissions               — List past compliance check records
    GET  /api/drr/submissions/{id}          — Single submission detail with full rule results
    POST /api/drr/cdm-report                — CDM TransactionReportInstruction JSON + enrichment
"""

import csv
import io
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.database import get_db
from api.models.drr_submission import DRRSubmission
from api.schemas.drr import (
    DRRBulkComplianceCheckResponse,
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
        report_status=body.report_status,
        executing_entity_id=body.executing_entity_id,
        is_investment_firm=body.is_investment_firm,
        buyer_id=body.buyer_id,
        buyer_id_type=body.buyer_id_type,
        seller_id=body.seller_id,
        seller_id_type=body.seller_id_type,
        transmission_of_order=body.transmission_of_order,
        trading_date_time=body.trading_date_time,
        trading_capacity=body.trading_capacity,
        quantity=body.quantity,
        net_amount=body.net_amount,
        venue=body.venue,
        isin=body.isin,
        instrument_full_name=body.instrument_full_name,
        instrument_classification=body.instrument_classification,
        notional_currency_1=body.notional_currency_1,
        price_multiplier=body.price_multiplier,
        investment_decision_maker=body.investment_decision_maker,
        investment_decision_country=body.investment_decision_country,
        execution_within_firm=body.execution_within_firm,
        execution_country=body.execution_country,
        maturity_date=body.maturity_date,
        sft_indicator=body.sft_indicator,
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


# ---------------------------------------------------------------------------
# Bulk CSV compliance check
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# UnaVista column name to internal field mapping
# ---------------------------------------------------------------------------

_UNAVISTA_TO_INTERNAL: dict[str, str] = {
    "Report Status": "report_status",
    "Transaction Reference Number": "transaction_ref",
    "Executing Entity ID": "executing_entity_id",
    "Investment Firm Indicator": "is_investment_firm",
    "Buyer ID Type": "buyer_id_type",
    "Buyer ID": "buyer_id",
    "Seller ID Type": "seller_id_type",
    "Seller ID": "seller_id",
    "Order Transmission Indicator": "transmission_of_order",
    "Trading Date Time": "trading_date_time",
    "Trading Capacity": "trading_capacity",
    "Quantity": "quantity",
    "Net Amount": "net_amount",
    "Venue": "venue",
    "Instrument ID": "isin",
    "Instrument Name": "instrument_full_name",
    "Instrument Classification": "instrument_classification",
    "Notional Currency 1": "notional_currency_1",
    "Price Multiplier": "price_multiplier",
    "Investment Decision ID": "investment_decision_maker",
    "Investment Decision Country of Branch": "investment_decision_country",
    "Firm Execution ID": "execution_within_firm",
    "Firm Execution Country of Branch": "execution_country",
    "Maturity Date": "maturity_date",
    "SFT Indicator": "sft_indicator",
}

_FLOAT_FIELDS = {"quantity", "net_amount", "price_multiplier"}


def _normalize_row(row: dict[str, str]) -> dict[str, str]:
    """Map UnaVista column names to internal field names."""
    normalized = {}
    for unavista_col, value in row.items():
        internal_name = _UNAVISTA_TO_INTERNAL.get(unavista_col.strip())
        if internal_name:
            normalized[internal_name] = value
    return normalized


def _row_to_report(row: dict[str, str], row_num: int) -> DRRComplianceCheckResponse:
    """Parse one CSV row and run compliance check.  Returns a response object."""
    # Normalise column names from UnaVista format to internal field names
    normalized = _normalize_row(row)
    txn_ref = normalized.get("transaction_ref", "").strip() or f"ROW-{row_num}"

    def _str(key: str) -> str | None:
        v = normalized.get(key, "").strip()
        return v if v else None

    def _float(key: str) -> float | None:
        v = normalized.get(key, "").strip()
        if not v:
            return None
        try:
            return float(v)
        except ValueError:
            return None

    report = check_transaction(
        transaction_ref=txn_ref,
        report_status=_str("report_status"),
        executing_entity_id=_str("executing_entity_id"),
        is_investment_firm=_str("is_investment_firm"),
        buyer_id=_str("buyer_id"),
        buyer_id_type=_str("buyer_id_type"),
        seller_id=_str("seller_id"),
        seller_id_type=_str("seller_id_type"),
        transmission_of_order=_str("transmission_of_order"),
        trading_date_time=_str("trading_date_time"),
        trading_capacity=_str("trading_capacity"),
        quantity=_float("quantity"),
        net_amount=_float("net_amount"),
        venue=_str("venue"),
        isin=_str("isin"),
        instrument_full_name=_str("instrument_full_name"),
        instrument_classification=_str("instrument_classification"),
        notional_currency_1=_str("notional_currency_1"),
        price_multiplier=_float("price_multiplier"),
        investment_decision_maker=_str("investment_decision_maker"),
        investment_decision_country=_str("investment_decision_country"),
        execution_within_firm=_str("execution_within_firm"),
        execution_country=_str("execution_country"),
        maturity_date=_str("maturity_date"),
        sft_indicator=_str("sft_indicator"),
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

    # Bulk checks are not persisted to avoid flooding the submissions table.
    return DRRComplianceCheckResponse(
        submission_id=uuid.uuid4(),
        transaction_ref=report.transaction_ref,
        checked_at=report.checked_at,
        overall_status=report.overall_status.value,
        results=rule_results,
        total_rules=len(report.results),
        passed=report.passed,
        failed=report.failed,
        warnings=report.warnings,
    )


@router.post("/drr/compliance-check/bulk", response_model=DRRBulkComplianceCheckResponse)
async def bulk_compliance_check(
    file: UploadFile = File(...),
) -> DRRBulkComplianceCheckResponse:
    """Validate many transactions from a CSV upload against MiFIR RTS 22 DRR rules.

    The CSV must have a header row with UnaVista column names.  Any columns not present
    are treated as missing/empty.

    Supported UnaVista columns:
        Report Status, Transaction Reference Number, Executing Entity ID,
        Investment Firm Indicator, Buyer ID Type, Buyer ID, Seller ID Type, Seller ID,
        Order Transmission Indicator, Trading Date Time, Trading Capacity, Quantity,
        Net Amount, Venue, Instrument ID, Instrument Name, Instrument Classification,
        Notional Currency 1, Price Multiplier, Investment Decision ID,
        Investment Decision Country of Branch, Firm Execution ID,
        Firm Execution Country of Branch, Maturity Date, SFT Indicator.

    Bulk submissions are not persisted to the submissions table.

    Args:
        file: Uploaded CSV file (multipart/form-data) with UnaVista column headers.

    Returns:
        Aggregate summary and per-transaction compliance results.

    Raises:
        HTTPException: 400 if the file is not valid UTF-8 CSV or has no rows.
    """
    try:
        content = await file.read()
        text = content.decode("utf-8-sig")  # strip BOM if present
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"File is not valid UTF-8: {exc}") from exc

    reader = csv.DictReader(io.StringIO(text))
    results: list[DRRComplianceCheckResponse] = []

    try:
        for row_num, row in enumerate(reader, start=2):  # row 1 is header
            results.append(_row_to_report(row, row_num))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Error parsing row {row_num}: {exc}") from exc

    if not results:
        raise HTTPException(status_code=400, detail="CSV file contains no data rows")

    passed_rows = sum(1 for r in results if r.overall_status == "pass")
    failed_rows = sum(1 for r in results if r.overall_status == "fail")
    warning_rows = sum(1 for r in results if r.overall_status == "warning")

    return DRRBulkComplianceCheckResponse(
        total_rows=len(results),
        passed_rows=passed_rows,
        failed_rows=failed_rows,
        warning_rows=warning_rows,
        results=results,
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
        report_status=body.report_status,
        executing_entity_id=body.executing_entity_id,
        is_investment_firm=body.is_investment_firm,
        buyer_id=body.buyer_id,
        buyer_id_type=body.buyer_id_type,
        seller_id=body.seller_id,
        seller_id_type=body.seller_id_type,
        transmission_of_order=body.transmission_of_order,
        trading_date_time=body.trading_date_time,
        trading_capacity=body.trading_capacity,
        quantity=body.quantity,
        net_amount=body.net_amount,
        venue=body.venue,
        isin=body.isin,
        instrument_full_name=body.instrument_full_name,
        instrument_classification=body.instrument_classification,
        notional_currency_1=body.notional_currency_1,
        price_multiplier=body.price_multiplier,
        investment_decision_maker=body.investment_decision_maker,
        investment_decision_country=body.investment_decision_country,
        execution_within_firm=body.execution_within_firm,
        execution_country=body.execution_country,
        maturity_date=body.maturity_date,
        sft_indicator=body.sft_indicator,
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
