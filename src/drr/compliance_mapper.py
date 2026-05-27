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
from datetime import datetime
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
        return False, f"'{value}' does not match LEI format (18 alphanumeric + 2 digits)"
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
        return False, f"'{value}' does not match CONCAT format (CC + ID + '#' + DOB + '#' + gender)"
    return True, None


# ---------------------------------------------------------------------------
# Per-field validators
# ---------------------------------------------------------------------------

_DATETIME_FORMATS = ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%f"]
_MIC_RE = re.compile(r"^[A-Z]{4}$")
_ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}\d$")


def _check_party_id(value: str | None, id_type: str | None, ref: RuleReference) -> RuleResult:
    """Validate a buyer or seller identification code."""
    if not value:
        return RuleResult.from_ref(ref, RuleStatus.FAIL, error="Identification code is missing")
    if not id_type:
        return RuleResult.from_ref(ref, RuleStatus.FAIL, value=value, error="Identification type is missing")

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
            return RuleResult.from_ref(ref, RuleStatus.FAIL, value=value, error=f"{id_type} value too short")
        return RuleResult.from_ref(ref, RuleStatus.PASS, value=value)

    return RuleResult.from_ref(
        ref, RuleStatus.WARNING, value=value,
        error=f"Unknown identification type '{id_type}'; format not validated"
    )


def _check_datetime(value: str | None, ref: RuleReference) -> RuleResult:
    if not value:
        return RuleResult.from_ref(ref, RuleStatus.FAIL, error="Trading date time is missing")
    for fmt in _DATETIME_FORMATS:
        try:
            datetime.strptime(value.rstrip("Z"), fmt.rstrip("Z"))
            return RuleResult.from_ref(ref, RuleStatus.PASS, value=value)
        except ValueError:
            continue
    return RuleResult.from_ref(
        ref, RuleStatus.FAIL, value=value,
        error=f"'{value}' is not a valid ISO 8601 datetime (expected YYYY-MM-DDTHH:MM:SS)"
    )


def _check_quantity(value: float | None, ref: RuleReference) -> RuleResult:
    if value is None:
        return RuleResult.from_ref(ref, RuleStatus.FAIL, error="Quantity is missing")
    if value == 0:
        return RuleResult.from_ref(ref, RuleStatus.FAIL, value=str(value), error="Quantity must not be zero")
    if value < 0:
        return RuleResult.from_ref(ref, RuleStatus.WARNING, value=str(value), error="Negative quantity — confirm this is intentional")
    return RuleResult.from_ref(ref, RuleStatus.PASS, value=str(value))


def _check_price(value: float | None, ref: RuleReference) -> RuleResult:
    if value is None:
        return RuleResult.from_ref(ref, RuleStatus.FAIL, error="Price is missing")
    return RuleResult.from_ref(ref, RuleStatus.PASS, value=str(value))


def _check_venue(value: str | None, ref: RuleReference) -> RuleResult:
    if not value:
        return RuleResult.from_ref(ref, RuleStatus.FAIL, error="Venue of execution is missing")
    if not _MIC_RE.match(value.strip().upper()):
        return RuleResult.from_ref(
            ref, RuleStatus.FAIL, value=value,
            error=f"'{value}' is not a valid 4-letter ISO 10383 MIC code"
        )
    return RuleResult.from_ref(ref, RuleStatus.PASS, value=value.strip().upper())


def _check_isin(value: str | None, ref: RuleReference) -> RuleResult:
    if not value:
        return RuleResult.from_ref(ref, RuleStatus.FAIL, error="Instrument identification code (ISIN) is missing")
    if not _ISIN_RE.match(value.strip().upper()):
        return RuleResult.from_ref(
            ref, RuleStatus.FAIL, value=value,
            error=f"'{value}' is not a valid ISIN (2-letter country + 9 alphanumeric + 1 check digit)"
        )
    return RuleResult.from_ref(ref, RuleStatus.PASS, value=value.strip().upper())


def _check_investment_decision(value: str | None, ref: RuleReference) -> RuleResult:
    if not value:
        return RuleResult.from_ref(
            ref, RuleStatus.WARNING,
            error="Investment decision maker is not populated — required for discretionary accounts"
        )
    return RuleResult.from_ref(ref, RuleStatus.PASS, value=value)


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
    venue: str | None = None,
    isin: str | None = None,
    investment_decision_maker: str | None = None,
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
        venue: ISO 10383 MIC code for the execution venue.
        isin: ISIN of the financial instrument.
        investment_decision_maker: Decision maker code (for discretionary accounts).

    Returns:
        ComplianceReport with a result entry per rule checked.
    """
    report = ComplianceReport(
        transaction_ref=transaction_ref,
        checked_at=datetime.utcnow(),
    )

    report.results.append(
        _check_party_id(buyer_id, buyer_id_type, CATALOGUE["BuyerSeller_Buyer"])
    )
    report.results.append(
        _check_party_id(seller_id, seller_id_type, CATALOGUE["BuyerSeller_Seller"])
    )
    report.results.append(
        _check_datetime(trading_date_time, CATALOGUE["TradingDateTime"])
    )
    report.results.append(
        _check_quantity(quantity if quantity is not None else net_amount, CATALOGUE["Quantity"])
    )
    if net_amount is not None:
        report.results.append(
            _check_price(net_amount, CATALOGUE["Price"])
        )
    if venue is not None:
        report.results.append(
            _check_venue(venue, CATALOGUE["VenueOfExecution"])
        )
    if isin is not None:
        report.results.append(
            _check_isin(isin, CATALOGUE["InstrumentIdentificationCode"])
        )
    report.results.append(
        _check_investment_decision(investment_decision_maker, CATALOGUE["InvestmentDecisionWithinFirm"])
    )

    return report
