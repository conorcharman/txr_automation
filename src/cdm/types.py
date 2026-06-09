"""CDM JSON type definitions.

TypedDicts representing the CDM TransactionReportInstruction JSON shape used
for MiFIR RTS 22 equity transaction reporting.  These match the structure that
cdm-drr-service will accept when ISDA delivers working MiFIR rules.

All field names follow CDM camelCase conventions.
"""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class CdmValue(TypedDict):
    value: str


class CdmIdentifier(TypedDict):
    identifier: CdmValue
    identifierType: str  # "LEI", "ISIN", "CONCAT", etc.


class CdmParty(TypedDict):
    partyId: list[CdmIdentifier]
    partyRole: str  # "BUYER" | "SELLER"
    name: NotRequired[str]  # legal entity name from GLEIF enrichment


class CdmSecurity(TypedDict):
    identifier: list[CdmIdentifier]
    primaryAssetClass: str  # "EQUITY"
    fullName: NotRequired[str]  # from FIRDS enrichment
    cfiCode: NotRequired[str]  # from FIRDS enrichment


class CdmProduct(TypedDict):
    security: CdmSecurity


class CdmQuantityUnit(TypedDict):
    financialUnit: str  # "SHARES"


class CdmQuantityEntry(TypedDict):
    value: float
    unitOfAmount: CdmQuantityUnit


class CdmPriceAmount(TypedDict):
    amount: float
    currency: str  # ISO 4217, e.g. "GBP"


class CdmPriceEntry(TypedDict):
    value: CdmPriceAmount
    priceType: str  # "NET_PRICE"


class CdmPriceQuantity(TypedDict):
    quantity: list[CdmQuantityEntry]
    price: NotRequired[list[CdmPriceEntry]]


class CdmTradeLot(TypedDict):
    priceQuantity: list[CdmPriceQuantity]


class CdmExecutionDetails(TypedDict):
    executionVenue: CdmValue
    executionDateTime: str  # ISO 8601
    executionType: str  # "ON_VENUE"


class CdmInvestmentDecision(TypedDict):
    decisionMaker: str  # LEI / CONCAT / "ALGO"


class CdmTrade(TypedDict):
    product: CdmProduct
    party: list[CdmParty]
    tradeLot: list[CdmTradeLot]
    executionDetails: NotRequired[CdmExecutionDetails]
    investmentDecision: NotRequired[CdmInvestmentDecision]


class CdmBeforeState(TypedDict):
    trade: CdmTrade


class CdmInstruction(TypedDict):
    before: CdmBeforeState


class CdmProposedEvent(TypedDict):
    intent: str  # "ContractFormation"
    eventDate: str  # "YYYY-MM-DD"
    instruction: list[CdmInstruction]


class CdmWorkflowStep(TypedDict):
    proposedEvent: CdmProposedEvent


class CdmReportingSide(TypedDict):
    partyRole: str  # "EXECUTING_ENTITY"


class CdmTransactionReport(TypedDict):
    """Top-level CDM TransactionReportInstruction JSON."""

    _type: str  # "TransactionReportInstruction"  (key stored as "$type" at runtime)
    reportingRegime: str  # "ESMA MiFIR RTS_22"
    transactionReference: str
    originatingWorkflowStep: CdmWorkflowStep
    reportingSide: CdmReportingSide
