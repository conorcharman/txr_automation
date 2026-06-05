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
    report_status: str | None = Field(None, description="NEWT or CANC (Field 1)")
    executing_entity_id: str | None = Field(None, description="LEI of the executing firm (Field 4)")
    is_investment_firm: str | None = Field(None, description="true or false (Field 5)")
    buyer_id: str | None = Field(None, description="Buyer identification code (Field 7)")
    buyer_id_type: str | None = Field(None, description="Buyer ID type: LEI, CONCAT, NIDN, CCPT, INTC, BIC")
    seller_id: str | None = Field(None, description="Seller identification code (Field 16)")
    seller_id_type: str | None = Field(None, description="Seller ID type")
    transmission_of_order: str | None = Field(None, description="true or false (Field 25)")
    trading_date_time: str | None = Field(None, description="ISO 8601 trade datetime (Field 28)")
    trading_capacity: str | None = Field(None, description="DEAL, MTCH, or AOTC (Field 29)")
    quantity: float | None = Field(None, description="Number of units / notional (Field 30)")
    net_amount: float | None = Field(None, description="Net monetary amount (Field 33)")
    venue: str | None = Field(None, description="ISO 10383 MIC code (Field 36)")
    isin: str | None = Field(None, description="ISIN of the financial instrument (Field 41)")
    instrument_full_name: str | None = Field(None, description="Full instrument name (Field 42)")
    instrument_classification: str | None = Field(None, description="CFI code — 6 uppercase letters (Field 43)")
    notional_currency_1: str | None = Field(None, description="ISO 4217 currency code (Field 44)")
    price_multiplier: float | None = Field(None, description="Number of underlying units per contract (Field 46)")
    maturity_date: str | None = Field(None, description="YYYY-MM-DD maturity date for debt instruments (Field 54)")
    investment_decision_maker: str | None = Field(None, description="Decision maker code (Field 57)")
    investment_decision_country: str | None = Field(None, description="ISO 3166-1 alpha-2 country code (Field 58)")
    execution_within_firm: str | None = Field(None, description="Person or algorithm code responsible for execution (Field 59)")
    execution_country: str | None = Field(None, description="ISO 3166-1 alpha-2 country code for execution (Field 60)")
    sft_indicator: str | None = Field(None, description="true or false — SFT exemption indicator (Field 65)")


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
    report_status: str | None = Field(None, description="NEWT or CANC (Field 1)")
    executing_entity_id: str | None = Field(None, description="LEI of the executing firm (Field 4)")
    is_investment_firm: str | None = Field(None, description="true or false (Field 5)")
    buyer_id: str | None = Field(None, description="Buyer identification code (Field 7)")
    buyer_id_type: str | None = Field(None, description="Buyer ID type: LEI, CONCAT, NIDN, CCPT, INTC, BIC")
    seller_id: str | None = Field(None, description="Seller identification code (Field 16)")
    seller_id_type: str | None = Field(None, description="Seller ID type")
    transmission_of_order: str | None = Field(None, description="true or false (Field 25)")
    trading_date_time: str | None = Field(None, description="ISO 8601 trade datetime (Field 28)")
    trading_capacity: str | None = Field(None, description="DEAL, MTCH, or AOTC (Field 29)")
    quantity: float | None = Field(None, description="Number of units / notional (Field 30)")
    net_amount: float | None = Field(None, description="Net monetary amount (Field 33)")
    venue: str | None = Field(None, description="ISO 10383 MIC code (Field 36)")
    isin: str | None = Field(None, description="ISIN of the financial instrument (Field 41)")
    instrument_full_name: str | None = Field(None, description="Full instrument name (Field 42)")
    instrument_classification: str | None = Field(None, description="CFI code — 6 uppercase letters (Field 43)")
    notional_currency_1: str | None = Field(None, description="ISO 4217 currency code (Field 44)")
    price_multiplier: float | None = Field(None, description="Number of underlying units per contract (Field 46)")
    maturity_date: str | None = Field(None, description="YYYY-MM-DD maturity date for debt instruments (Field 54)")
    investment_decision_maker: str | None = Field(None, description="Decision maker code (Field 57)")
    investment_decision_country: str | None = Field(None, description="ISO 3166-1 alpha-2 country code (Field 58)")
    execution_within_firm: str | None = Field(None, description="Person or algorithm code responsible for execution (Field 59)")
    execution_country: str | None = Field(None, description="ISO 3166-1 alpha-2 country code for execution (Field 60)")
    sft_indicator: str | None = Field(None, description="true or false — SFT exemption indicator (Field 65)")


class DRRCdmReportResponse(_CamelModel):
    """Response body for POST /api/drr/cdm-report."""

    transaction_ref: str
    cdm_json: dict = Field(description="CDM TransactionReportInstruction JSON")
    enrichment: DRREnrichmentSummary
    compliance_status: str  # pass | fail | warning
    passed: int
    failed: int
    warnings: int


# ---------------------------------------------------------------------------
# Bulk CSV compliance check
# ---------------------------------------------------------------------------


class DRRBulkComplianceCheckResponse(_CamelModel):
    """Response body for POST /api/drr/compliance-check/bulk."""

    total_rows: int
    passed_rows: int
    failed_rows: int
    warning_rows: int
    results: list[DRRComplianceCheckResponse]
