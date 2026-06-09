"""DRR compliance mapper.

Validates individual MiFIR transaction fields and returns results annotated
with DRR regulatory references from the RTS 22 rule catalogue.

This module implements lightweight inline validation that mirrors the checks
performed by the txr_automation accuracy validators, expressed in terms of
DRR rule identifiers so that output carries regulatory traceability.

When the ISDA DRR MiFIR rules are implemented in a future distribution, the
validation logic here will be replaced by calls to the cdm-drr-service, while
the rule identifiers and field structure remain unchanged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from src.drr.rule_catalogue import CATALOGUE, RuleReference


class RuleStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    NOT_CHECKED = "not_checked"


@dataclass
class RuleResult:
    """Result of evaluating one DRR rule against a transaction field."""

    rule_name: str
    field_number: str
    field_name: str
    regulation: str
    provision: str
    status: RuleStatus
    value: str | None = None
    error: str | None = None

    @classmethod
    def from_ref(
        cls,
        ref: RuleReference,
        status: RuleStatus,
        value: str | None = None,
        error: str | None = None,
    ) -> "RuleResult":
        return cls(
            rule_name=ref.rule_name,
            field_number=ref.field_number,
            field_name=ref.field_name,
            regulation=ref.regulation,
            provision=ref.provision,
            status=status,
            value=value,
            error=error,
        )


@dataclass
class ComplianceReport:
    """Aggregated DRR compliance check result for one transaction."""

    transaction_ref: str
    checked_at: datetime
    results: list[RuleResult] = field(default_factory=list)

    @property
    def overall_status(self) -> RuleStatus:
        if any(r.status == RuleStatus.FAIL for r in self.results):
            return RuleStatus.FAIL
        if any(r.status == RuleStatus.WARNING for r in self.results):
            return RuleStatus.WARNING
        return RuleStatus.PASS

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == RuleStatus.PASS)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == RuleStatus.FAIL)

    @property
    def warnings(self) -> int:
        return sum(1 for r in self.results if r.status == RuleStatus.WARNING)


# ---------------------------------------------------------------------------
# LEI validation (ISO 17442)
# ---------------------------------------------------------------------------

_LEI_RE = re.compile(r"^[A-Z0-9]{18}\d{2}$")
_LEI_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _lei_checksum_valid(lei: str) -> bool:
    """Validate LEI check digits using ISO 17442 mod-97 algorithm."""
    digits = "".join(str(_LEI_CHARS.index(c)) for c in lei)
    return int(digits) % 97 == 1


def validate_lei(value: str) -> tuple[bool, str | None]:
    """Return (valid, error_message). error_message is None when valid."""
    v = value.strip().upper()
    if not _LEI_RE.match(v):
        return (
            False,
            f"'{value}' does not match LEI format (18 alphanumeric + 2 digits)",
        )
    if not _lei_checksum_valid(v):
        return False, f"'{value}' has invalid LEI check digits"
    return True, None


# ---------------------------------------------------------------------------
# CONCAT validation (MiFIR Article 6)
# ---------------------------------------------------------------------------

_CONCAT_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{1,50}#\d{4}-\d{2}-\d{2}#[MF]$")


def validate_concat(value: str) -> tuple[bool, str | None]:
    v = value.strip().upper()
    if not _CONCAT_RE.match(v):
        return (
            False,
            f"'{value}' does not match CONCAT format (CC + ID + '#' + DOB + '#' + gender)",
        )
    return True, None


# ---------------------------------------------------------------------------
# Per-field validators
# ---------------------------------------------------------------------------

_DATETIME_FORMATS = ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%f"]
_MIC_RE = re.compile(r"^[A-Z]{4}$")
_ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}\d$")


def _check_party_id(
    value: str | None, id_type: str | None, ref: RuleReference
) -> RuleResult:
    """Validate a buyer or seller identification code."""
    if not value:
        return RuleResult.from_ref(
            ref, RuleStatus.FAIL, error="Identification code is missing"
        )
    if not id_type:
        return RuleResult.from_ref(
            ref, RuleStatus.FAIL, value=value, error="Identification type is missing"
        )

    id_type_upper = id_type.strip().upper()

    if id_type_upper == "LEI":
        ok, err = validate_lei(value)
        status = RuleStatus.PASS if ok else RuleStatus.FAIL
        return RuleResult.from_ref(ref, status, value=value, error=err)

    if id_type_upper == "CONCAT":
        ok, err = validate_concat(value)
        status = RuleStatus.PASS if ok else RuleStatus.FAIL
        return RuleResult.from_ref(ref, status, value=value, error=err)

    # NIDN, CCPT, INTC — presence check only (format rules are country-specific)
    if id_type_upper in {"NIDN", "CCPT", "INTC", "BIC"}:
        if len(value.strip()) < 3:
            return RuleResult.from_ref(
                ref, RuleStatus.FAIL, value=value, error=f"{id_type} value too short"
            )
        return RuleResult.from_ref(ref, RuleStatus.PASS, value=value)

    return RuleResult.from_ref(
        ref,
        RuleStatus.WARNING,
        value=value,
        error=f"Unknown identification type '{id_type}'; format not validated",
    )


def _check_datetime(value: str | None, ref: RuleReference) -> RuleResult:
    if not value:
        return RuleResult.from_ref(
            ref, RuleStatus.FAIL, error="Trading date time is missing"
        )
    for fmt in _DATETIME_FORMATS:
        try:
            datetime.strptime(value.rstrip("Z"), fmt.rstrip("Z"))
            return RuleResult.from_ref(ref, RuleStatus.PASS, value=value)
        except ValueError:
            continue
    return RuleResult.from_ref(
        ref,
        RuleStatus.FAIL,
        value=value,
        error=f"'{value}' is not a valid ISO 8601 datetime (expected YYYY-MM-DDTHH:MM:SS)",
    )


def _check_report_status(value: str | None, ref: RuleReference) -> RuleResult:
    if not value:
        return RuleResult.from_ref(
            ref, RuleStatus.FAIL, error="Report status is missing"
        )
    v = value.strip().upper()
    if v not in {"NEWT", "CANC"}:
        return RuleResult.from_ref(
            ref,
            RuleStatus.FAIL,
            value=value,
            error=f"'{value}' is not a valid report status — expected NEWT or CANC",
        )
    return RuleResult.from_ref(ref, RuleStatus.PASS, value=v)


def _check_transaction_ref(value: str | None, ref: RuleReference) -> RuleResult:
    if not value:
        return RuleResult.from_ref(
            ref, RuleStatus.FAIL, error="Transaction reference number is missing"
        )
    if len(value) > 52:
        return RuleResult.from_ref(
            ref,
            RuleStatus.FAIL,
            value=value,
            error=f"Transaction reference exceeds 52-character limit (length={len(value)})",
        )
    return RuleResult.from_ref(ref, RuleStatus.PASS, value=value)


def _check_tvtic(value: str | None, ref: RuleReference) -> RuleResult:
    """Trading venue transaction identification code — optional field."""
    if not value:
        return RuleResult.from_ref(
            ref, RuleStatus.NOT_CHECKED, error="Not provided (optional for OTC trades)"
        )
    if len(value.strip()) > 52:
        return RuleResult.from_ref(
            ref,
            RuleStatus.FAIL,
            value=value,
            error=f"TVTIC exceeds 52-character limit (length={len(value.strip())})",
        )
    return RuleResult.from_ref(ref, RuleStatus.PASS, value=value.strip())


def _check_executing_entity(value: str | None, ref: RuleReference) -> RuleResult:
    if not value:
        return RuleResult.from_ref(
            ref,
            RuleStatus.FAIL,
            error="Executing entity identification code (LEI) is missing",
        )
    ok, err = validate_lei(value)
    status = RuleStatus.PASS if ok else RuleStatus.FAIL
    return RuleResult.from_ref(ref, status, value=value, error=err)


def _check_boolean_field(
    value: str | None, ref: RuleReference, field_label: str
) -> RuleResult:
    """Validate a field that must be 'true' or 'false'."""
    if not value:
        return RuleResult.from_ref(
            ref, RuleStatus.FAIL, error=f"{field_label} is missing"
        )
    v = value.strip().lower()
    if v not in {"true", "false"}:
        return RuleResult.from_ref(
            ref,
            RuleStatus.FAIL,
            value=value,
            error=f"'{value}' is not valid for {field_label} — expected true or false",
        )
    return RuleResult.from_ref(ref, RuleStatus.PASS, value=v)


def _check_trading_capacity(value: str | None, ref: RuleReference) -> RuleResult:
    if not value:
        return RuleResult.from_ref(
            ref, RuleStatus.FAIL, error="Trading capacity is missing"
        )
    v = value.strip().upper()
    if v not in {"DEAL", "MTCH", "AOTC"}:
        return RuleResult.from_ref(
            ref,
            RuleStatus.FAIL,
            value=value,
            error=f"'{value}' is not a valid trading capacity — expected DEAL, MTCH, or AOTC",
        )
    return RuleResult.from_ref(ref, RuleStatus.PASS, value=v)


_CFI_RE = re.compile(r"^[A-Z]{6}$")
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_COUNTRY_RE = re.compile(r"^[A-Z]{2}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _check_instrument_full_name(value: str | None, ref: RuleReference) -> RuleResult:
    if not value:
        return RuleResult.from_ref(
            ref,
            RuleStatus.NOT_CHECKED,
            error="Not provided — typically sourced from FIRDS",
        )
    if len(value) > 350:
        return RuleResult.from_ref(
            ref,
            RuleStatus.FAIL,
            value=value[:50] + "…",
            error=f"Instrument full name exceeds 350-character limit (length={len(value)})",
        )
    return RuleResult.from_ref(ref, RuleStatus.PASS, value=value)


def _check_instrument_classification(
    value: str | None, ref: RuleReference
) -> RuleResult:
    if not value:
        return RuleResult.from_ref(
            ref,
            RuleStatus.FAIL,
            error="Instrument classification (CFI code) is missing",
        )
    v = value.strip().upper()
    if not _CFI_RE.match(v):
        return RuleResult.from_ref(
            ref,
            RuleStatus.FAIL,
            value=value,
            error=f"'{value}' is not a valid CFI code (must be exactly 6 uppercase letters)",
        )
    return RuleResult.from_ref(ref, RuleStatus.PASS, value=v)


def _check_notional_currency(value: str | None, ref: RuleReference) -> RuleResult:
    if not value:
        return RuleResult.from_ref(
            ref, RuleStatus.FAIL, error="Notional currency 1 is missing"
        )
    v = value.strip().upper()
    if not _CURRENCY_RE.match(v):
        return RuleResult.from_ref(
            ref,
            RuleStatus.FAIL,
            value=value,
            error=f"'{value}' is not a valid ISO 4217 currency code (must be 3 uppercase letters)",
        )
    return RuleResult.from_ref(ref, RuleStatus.PASS, value=v)


def _check_price_multiplier(value: float | None, ref: RuleReference) -> RuleResult:
    if value is None:
        return RuleResult.from_ref(
            ref, RuleStatus.FAIL, error="Price multiplier is missing"
        )
    if value <= 0:
        return RuleResult.from_ref(
            ref,
            RuleStatus.FAIL,
            value=str(value),
            error=f"Price multiplier must be positive (got {value})",
        )
    return RuleResult.from_ref(ref, RuleStatus.PASS, value=str(value))


def _check_maturity_date(value: str | None, ref: RuleReference) -> RuleResult:
    """Maturity date — optional, only applies to debt instruments."""
    if not value:
        return RuleResult.from_ref(
            ref,
            RuleStatus.NOT_CHECKED,
            error="Not provided (only required for debt instruments)",
        )
    if not _DATE_RE.match(value.strip()):
        return RuleResult.from_ref(
            ref,
            RuleStatus.FAIL,
            value=value,
            error=f"'{value}' is not a valid date (expected YYYY-MM-DD)",
        )
    try:
        datetime.strptime(value.strip(), "%Y-%m-%d")
    except ValueError:
        return RuleResult.from_ref(
            ref,
            RuleStatus.FAIL,
            value=value,
            error=f"'{value}' is not a valid calendar date",
        )
    return RuleResult.from_ref(ref, RuleStatus.PASS, value=value.strip())


def _check_country_code(
    value: str | None, ref: RuleReference, field_label: str
) -> RuleResult:
    if not value:
        return RuleResult.from_ref(
            ref,
            RuleStatus.WARNING,
            error=f"{field_label} not provided — required where applicable",
        )
    v = value.strip().upper()
    if not _COUNTRY_RE.match(v):
        return RuleResult.from_ref(
            ref,
            RuleStatus.FAIL,
            value=value,
            error=f"'{value}' is not a valid ISO 3166-1 alpha-2 country code (must be 2 uppercase letters)",
        )
    return RuleResult.from_ref(ref, RuleStatus.PASS, value=v)


def _check_execution_within_firm(value: str | None, ref: RuleReference) -> RuleResult:
    if not value:
        return RuleResult.from_ref(
            ref, RuleStatus.FAIL, error="Execution within firm is missing"
        )
    return RuleResult.from_ref(ref, RuleStatus.PASS, value=value.strip())


def _check_quantity(value: float | None, ref: RuleReference) -> RuleResult:
    if value is None:
        return RuleResult.from_ref(ref, RuleStatus.FAIL, error="Quantity is missing")
    if value == 0:
        return RuleResult.from_ref(
            ref, RuleStatus.FAIL, value=str(value), error="Quantity must not be zero"
        )
    if value < 0:
        return RuleResult.from_ref(
            ref,
            RuleStatus.WARNING,
            value=str(value),
            error="Negative quantity — confirm this is intentional",
        )
    return RuleResult.from_ref(ref, RuleStatus.PASS, value=str(value))


def _check_price(value: float | None, ref: RuleReference) -> RuleResult:
    if value is None:
        return RuleResult.from_ref(ref, RuleStatus.FAIL, error="Price is missing")
    return RuleResult.from_ref(ref, RuleStatus.PASS, value=str(value))


def _check_venue(value: str | None, ref: RuleReference) -> RuleResult:
    if not value:
        return RuleResult.from_ref(
            ref, RuleStatus.FAIL, error="Venue of execution is missing"
        )
    if not _MIC_RE.match(value.strip().upper()):
        return RuleResult.from_ref(
            ref,
            RuleStatus.FAIL,
            value=value,
            error=f"'{value}' is not a valid 4-letter ISO 10383 MIC code",
        )
    return RuleResult.from_ref(ref, RuleStatus.PASS, value=value.strip().upper())


def _check_isin(value: str | None, ref: RuleReference) -> RuleResult:
    if not value:
        return RuleResult.from_ref(
            ref,
            RuleStatus.FAIL,
            error="Instrument identification code (ISIN) is missing",
        )
    if not _ISIN_RE.match(value.strip().upper()):
        return RuleResult.from_ref(
            ref,
            RuleStatus.FAIL,
            value=value,
            error=f"'{value}' is not a valid ISIN (2-letter country + 9 alphanumeric + 1 check digit)",
        )
    return RuleResult.from_ref(ref, RuleStatus.PASS, value=value.strip().upper())


def _check_investment_decision(value: str | None, ref: RuleReference) -> RuleResult:
    if not value:
        return RuleResult.from_ref(
            ref,
            RuleStatus.WARNING,
            error="Investment decision maker is not populated — required for discretionary accounts",
        )
    return RuleResult.from_ref(ref, RuleStatus.PASS, value=value)


def _has_text(value: str | None) -> bool:
    """Return True when a string value is present and non-blank."""
    return value is not None and value.strip() != ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_transaction(
    transaction_ref: str,
    buyer_id: str | None,
    buyer_id_type: str | None,
    seller_id: str | None,
    seller_id_type: str | None,
    trading_date_time: str | None,
    quantity: float | None,
    net_amount: float | None,
    report_status: str | None = None,
    executing_entity_id: str | None = None,
    is_investment_firm: str | None = None,
    transmission_of_order: str | None = None,
    trading_capacity: str | None = None,
    venue: str | None = None,
    isin: str | None = None,
    instrument_full_name: str | None = None,
    instrument_classification: str | None = None,
    notional_currency_1: str | None = None,
    price_multiplier: float | None = None,
    investment_decision_maker: str | None = None,
    investment_decision_country: str | None = None,
    execution_within_firm: str | None = None,
    execution_country: str | None = None,
    maturity_date: str | None = None,
    sft_indicator: str | None = None,
) -> ComplianceReport:
    """Run DRR-referenced field validation against a single transaction.

    Each check maps to a named DRR reporting rule and its RTS 22 regulatory
    reference.  Results include rule name, field number, provision text, and
    pass/fail status.

    Args:
        transaction_ref: Unique reference for this transaction (for the report).
        buyer_id: Buyer identification code (LEI, CONCAT, NIDN, etc.).
        buyer_id_type: Type of buyer ID (LEI, CONCAT, NIDN, CCPT, INTC, BIC).
        seller_id: Seller identification code.
        seller_id_type: Type of seller ID.
        trading_date_time: ISO 8601 datetime string.
        quantity: Number of units or notional.
        net_amount: Net monetary amount.
        report_status: "NEWT" or "CANC" (Field 1).
        executing_entity_id: LEI of the executing firm (Field 4).
        is_investment_firm: "true" or "false" (Field 5).
        transmission_of_order: "true" or "false" (Field 25).
        trading_capacity: "DEAL", "MTCH", or "AOTC" (Field 29).
        venue: ISO 10383 MIC code for the execution venue (Field 36).
        isin: ISIN of the financial instrument (Field 41).
        instrument_full_name: Full name of the instrument (Field 42).
        instrument_classification: CFI code — 6 uppercase letters (Field 43).
        notional_currency_1: ISO 4217 currency code (Field 44).
        price_multiplier: Number of underlying units per contract (Field 46).
        investment_decision_maker: Decision maker code (Field 57).
        investment_decision_country: ISO 3166-1 alpha-2 country code (Field 58).
        execution_within_firm: Person or algorithm code responsible for execution (Field 59).
        execution_country: ISO 3166-1 alpha-2 country code for execution (Field 60).
        maturity_date: YYYY-MM-DD maturity date (Field 54, debt instruments only).
        sft_indicator: "true" or "false" — SFT exemption indicator (Field 65).

    Returns:
        ComplianceReport with a result entry per rule checked.
    """
    report = ComplianceReport(
        transaction_ref=transaction_ref,
        checked_at=datetime.now(UTC),
    )

    # Field 2 — Transaction reference number
    report.results.append(
        _check_transaction_ref(transaction_ref, CATALOGUE["TransactionReferenceNumber"])
    )

    # Field 1 — Report status (optional in lightweight mode)
    if _has_text(report_status):
        report.results.append(
            _check_report_status(report_status, CATALOGUE["ReportStatus"])
        )

    # Field 3 — Trading venue transaction identification code (optional)
    report.results.append(
        _check_tvtic(None, CATALOGUE["TradingVenueTransactionIdentificationCode"])
    )

    # Field 4 — Executing entity identification code (LEI)
    if _has_text(executing_entity_id):
        report.results.append(
            _check_executing_entity(
                executing_entity_id, CATALOGUE["ExecutingEntityIdentificationCode"]
            )
        )

    # Field 5 — Investment firm indicator
    if _has_text(is_investment_firm):
        report.results.append(
            _check_boolean_field(
                is_investment_firm,
                CATALOGUE["IsInvestmentFirm"],
                "Investment firm indicator",
            )
        )

    # Field 7 — Buyer identification code
    report.results.append(
        _check_party_id(buyer_id, buyer_id_type, CATALOGUE["BuyerSeller_Buyer"])
    )
    # Field 16 — Seller identification code
    report.results.append(
        _check_party_id(seller_id, seller_id_type, CATALOGUE["BuyerSeller_Seller"])
    )

    # Field 25 — Transmission of order indicator
    if _has_text(transmission_of_order):
        report.results.append(
            _check_boolean_field(
                transmission_of_order,
                CATALOGUE["TransmissionOfOrderIndicator"],
                "Transmission of order indicator",
            )
        )

    # Field 28 — Trading date time
    report.results.append(
        _check_datetime(trading_date_time, CATALOGUE["TradingDateTime"])
    )

    # Field 29 — Trading capacity
    if _has_text(trading_capacity):
        report.results.append(
            _check_trading_capacity(trading_capacity, CATALOGUE["TradingCapacity"])
        )

    # Field 30 — Quantity
    report.results.append(
        _check_quantity(
            quantity if quantity is not None else net_amount, CATALOGUE["Quantity"]
        )
    )

    # Field 33 — Price
    if net_amount is not None:
        report.results.append(_check_price(net_amount, CATALOGUE["Price"]))

    # Field 36 — Venue of execution
    if _has_text(venue):
        report.results.append(_check_venue(venue, CATALOGUE["VenueOfExecution"]))

    # Field 41 — Instrument identification code (ISIN)
    if _has_text(isin):
        report.results.append(
            _check_isin(isin, CATALOGUE["InstrumentIdentificationCode"])
        )

    # Field 42 — Instrument full name
    if _has_text(instrument_full_name):
        report.results.append(
            _check_instrument_full_name(
                instrument_full_name, CATALOGUE["InstrumentFullName"]
            )
        )

    # Field 43 — Instrument classification (CFI code)
    if _has_text(instrument_classification):
        report.results.append(
            _check_instrument_classification(
                instrument_classification, CATALOGUE["InstrumentClassification"]
            )
        )

    # Field 44 — Notional currency 1
    if _has_text(notional_currency_1):
        report.results.append(
            _check_notional_currency(
                notional_currency_1, CATALOGUE["NotionalCurrency1"]
            )
        )

    # Field 46 — Price multiplier
    if price_multiplier is not None:
        report.results.append(
            _check_price_multiplier(price_multiplier, CATALOGUE["PriceMultiplier"])
        )

    # Field 54 — Maturity date (debt instruments only)
    if _has_text(maturity_date):
        report.results.append(
            _check_maturity_date(maturity_date, CATALOGUE["MaturityDate"])
        )

    # Field 57 — Investment decision within firm
    report.results.append(
        _check_investment_decision(
            investment_decision_maker, CATALOGUE["InvestmentDecisionWithinFirm"]
        )
    )

    # Field 58 — Country of branch supervising investment decision
    if _has_text(investment_decision_country):
        report.results.append(
            _check_country_code(
                investment_decision_country,
                CATALOGUE["PersonResponsibleForInvestmentDecisionCountry"],
                "Investment decision country",
            )
        )

    # Field 59 — Execution within firm
    if _has_text(execution_within_firm):
        report.results.append(
            _check_execution_within_firm(
                execution_within_firm, CATALOGUE["ExecutionWithinFirm"]
            )
        )

    # Field 60 — Country of branch supervising execution
    if _has_text(execution_country):
        report.results.append(
            _check_country_code(
                execution_country,
                CATALOGUE["PersonResponsibleForExecutionCountry"],
                "Execution country",
            )
        )

    # Field 65 — Securities financing transaction indicator
    if _has_text(sft_indicator):
        report.results.append(
            _check_boolean_field(
                sft_indicator,
                CATALOGUE["SecuritiesFinancingTransactionIndicator"],
                "SFT indicator",
            )
        )

    return report
