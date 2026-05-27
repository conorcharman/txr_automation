"""CDM transaction report mapper.

Pure function that assembles a CDM-shaped TransactionReportInstruction JSON
dict from flat MiFIR RTS 22 transaction fields.

The output JSON follows the CDM TransactionReportInstruction structure
(originatingWorkflowStep → proposedEvent → instruction → before → trade)
and is intended as the future input to cdm-drr-service.  When ISDA delivers
working MiFIR DRR rules the JSON produced here will be passed to the service
unchanged.

Optional enrichment data (from src.cdm.enricher) is embedded where available:
  - Party ``name`` field populated with GLEIF legal entity name.
  - Security ``fullName`` and ``cfiCode`` from FIRDS instrument record.
"""

from __future__ import annotations

from src.cdm.enricher import EnrichmentResult


def _parse_event_date(trading_date_time: str | None) -> str:
    """Extract the date part from an ISO 8601 datetime string."""
    if not trading_date_time:
        return ""
    return trading_date_time[:10]  # "YYYY-MM-DD"


def _build_party_id(value: str, id_type: str) -> dict:
    return {
        "identifier": {"value": value},
        "identifierType": id_type.upper(),
    }


def build_transaction_report(
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
    enrichment: EnrichmentResult | None = None,
) -> dict:
    """Assemble a CDM TransactionReportInstruction JSON dict.

    The returned dict is serialisable to JSON and follows the CDM
    TransactionReportInstruction schema.  Optional fields are omitted rather
    than populated with null values.

    Args:
        transaction_ref: Unique transaction reference (RTS 22 Field 2).
        buyer_id: Buyer identification code (Field 7).
        buyer_id_type: Type of buyer ID.
        seller_id: Seller identification code (Field 16).
        seller_id_type: Type of seller ID.
        trading_date_time: ISO 8601 datetime of execution (Field 28).
        quantity: Number of units traded (Field 30).
        net_amount: Net monetary value (Field 33).
        venue: ISO 10383 MIC for the execution venue (Field 36).
        isin: Financial instrument ISIN (Field 41).
        investment_decision_maker: Decision maker code (Field 57).
        enrichment: Optional enrichment data from enrich_transaction().

    Returns:
        CDM-shaped dict ready for JSON serialisation.
    """
    # ── Parties ────────────────────────────────────────────────────────────
    parties: list[dict] = []

    if buyer_id and buyer_id_type:
        buyer_entry: dict = {
            "partyId": [_build_party_id(buyer_id, buyer_id_type)],
            "partyRole": "BUYER",
        }
        if enrichment and enrichment.buyer and enrichment.buyer.legal_name:
            buyer_entry["name"] = enrichment.buyer.legal_name
        parties.append(buyer_entry)

    if seller_id and seller_id_type:
        seller_entry: dict = {
            "partyId": [_build_party_id(seller_id, seller_id_type)],
            "partyRole": "SELLER",
        }
        if enrichment and enrichment.seller and enrichment.seller.legal_name:
            seller_entry["name"] = enrichment.seller.legal_name
        parties.append(seller_entry)

    # ── Product / security ─────────────────────────────────────────────────
    security: dict = {"primaryAssetClass": "EQUITY"}
    if isin:
        security["identifier"] = [_build_party_id(isin, "ISIN")]
        if enrichment and enrichment.instrument and enrichment.instrument.found:
            if enrichment.instrument.full_name:
                security["fullName"] = enrichment.instrument.full_name
            if enrichment.instrument.cfi_code:
                security["cfiCode"] = enrichment.instrument.cfi_code

    # ── Price / quantity ───────────────────────────────────────────────────
    price_quantity: dict = {}
    if quantity is not None:
        price_quantity["quantity"] = [
            {"value": quantity, "unitOfAmount": {"financialUnit": "SHARES"}}
        ]
    if net_amount is not None:
        price_quantity["price"] = [
            {"value": {"amount": net_amount, "currency": "GBP"}, "priceType": "NET_PRICE"}
        ]

    trade_lot: list[dict] = [{"priceQuantity": [price_quantity]}] if price_quantity else []

    # ── Execution details ──────────────────────────────────────────────────
    trade: dict = {
        "product": {"security": security},
        "party": parties,
        "tradeLot": trade_lot,
    }

    if venue or trading_date_time:
        execution_details: dict = {"executionType": "ON_VENUE"}
        if venue:
            execution_details["executionVenue"] = {"value": venue.upper()}
        if trading_date_time:
            execution_details["executionDateTime"] = trading_date_time
        trade["executionDetails"] = execution_details

    if investment_decision_maker:
        trade["investmentDecision"] = {"decisionMaker": investment_decision_maker}

    # ── Assemble ───────────────────────────────────────────────────────────
    return {
        "$type": "TransactionReportInstruction",
        "reportingRegime": "ESMA MiFIR RTS_22",
        "transactionReference": transaction_ref,
        "originatingWorkflowStep": {
            "proposedEvent": {
                "intent": "ContractFormation",
                "eventDate": _parse_event_date(trading_date_time),
                "instruction": [
                    {"before": {"trade": trade}}
                ],
            }
        },
        "reportingSide": {
            "partyRole": "EXECUTING_ENTITY",
        },
    }
