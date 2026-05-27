"""DRR Schemas
============

Pydantic v2 schemas for the DRR compliance endpoints.

All schemas use camelCase aliases for JSON serialisation to match the
React frontend convention.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from api.schemas.common import _CamelModel


class DRRRegulatoryReference(_CamelModel):
    """Regulatory reference for a single DRR rule."""

    rule_name: str
    field_number: str
    field_name: str
    regulation: str
    provision: str


class DRRRuleResult(_CamelModel):
    """Result of evaluating one DRR rule against a transaction field."""

    rule_name: str
    field_number: str
    field_name: str
    regulation: str
    provision: str
    status: str  # pass | fail | warning | not_checked
    value: str | None = None
    error: str | None = None


class DRRComplianceCheckRequest(_CamelModel):
    """Request body for POST /api/drr/compliance-check."""

    transaction_ref: str = Field(..., description="Unique reference for this transaction")
    buyer_id: str | None = Field(None, description="Buyer identification code")
    buyer_id_type: str | None = Field(None, description="Buyer ID type (LEI, CONCAT, NIDN, etc.)")
    seller_id: str | None = Field(None, description="Seller identification code")
    seller_id_type: str | None = Field(None, description="Seller ID type")
    trading_date_time: str | None = Field(None, description="ISO 8601 trade datetime")
    quantity: float | None = Field(None, description="Number of units / notional")
    net_amount: float | None = Field(None, description="Net monetary amount")
    venue: str | None = Field(None, description="ISO 10383 MIC code")
    isin: str | None = Field(None, description="ISIN of the financial instrument")
    investment_decision_maker: str | None = Field(None, description="Decision maker code")


class DRRComplianceCheckResponse(_CamelModel):
    """Response body for POST /api/drr/compliance-check."""

    submission_id: uuid.UUID
    transaction_ref: str
    checked_at: datetime
    overall_status: str  # pass | fail | warning
    results: list[DRRRuleResult]
    total_rules: int
    passed: int
    failed: int
    warnings: int


class DRRSubmissionSummary(_CamelModel):
    """Summary row for GET /api/drr/submissions list."""

    submission_id: uuid.UUID
    transaction_ref: str
    checked_at: datetime
    overall_status: str
    total_rules: int
    passed: int
    failed: int
    warnings: int


class DRRRuleCatalogueEntry(_CamelModel):
    """One entry in the RTS 22 rule catalogue."""

    rule_name: str
    field_number: str
    field_name: str
    regulation: str
    provision: str


# ---------------------------------------------------------------------------
# CDM report schemas
# ---------------------------------------------------------------------------


class LeiEnrichment(_CamelModel):
    """GLEIF enrichment result for a single LEI."""

    lei: str
    found: bool
    is_valid: bool
    reason: str
    legal_name: str | None = None
    entity_status: str | None = None
    registration_status: str | None = None
    legal_address_country: str | None = None


class InstrumentEnrichment(_CamelModel):
    """FIRDS enrichment result for a single ISIN."""

    isin: str
    found: bool
    full_name: str | None = None
    cfi_code: str | None = None
    mic: str | None = None


class DRREnrichmentSummary(_CamelModel):
    """Aggregated enrichment for a single transaction."""

    buyer: LeiEnrichment | None = None
    seller: LeiEnrichment | None = None
    instrument: InstrumentEnrichment | None = None


class DRRCdmReportRequest(_CamelModel):
    """Request body for POST /api/drr/cdm-report (same fields as compliance-check)."""

    transaction_ref: str = Field(..., description="Unique reference for this transaction")
    buyer_id: str | None = Field(None, description="Buyer identification code")
    buyer_id_type: str | None = Field(None, description="Buyer ID type (LEI, CONCAT, NIDN, etc.)")
    seller_id: str | None = Field(None, description="Seller identification code")
    seller_id_type: str | None = Field(None, description="Seller ID type")
    trading_date_time: str | None = Field(None, description="ISO 8601 trade datetime")
    quantity: float | None = Field(None, description="Number of units / notional")
    net_amount: float | None = Field(None, description="Net monetary amount")
    venue: str | None = Field(None, description="ISO 10383 MIC code")
    isin: str | None = Field(None, description="ISIN of the financial instrument")
    investment_decision_maker: str | None = Field(None, description="Decision maker code")


class DRRCdmReportResponse(_CamelModel):
    """Response body for POST /api/drr/cdm-report."""

    transaction_ref: str
    cdm_json: dict = Field(description="CDM TransactionReportInstruction JSON")
    enrichment: DRREnrichmentSummary
    compliance_status: str  # pass | fail | warning
    passed: int
    failed: int
    warnings: int
