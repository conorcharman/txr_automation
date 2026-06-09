"""Unit tests for src/cdm/mapper.py — build_transaction_report()."""

from src.cdm.enricher import EnrichmentResult, InstrumentEnrichment, LeiEnrichment
from src.cdm.mapper import build_transaction_report

VALID_LEI = "529900T8BM49AURSDO55"


def _base_report(**overrides: object) -> dict:
    params: dict = dict(
        transaction_ref="TXN-CDM-001",
        buyer_id=VALID_LEI,
        buyer_id_type="LEI",
        seller_id=VALID_LEI,
        seller_id_type="LEI",
        trading_date_time="2024-01-15T09:30:00",
        quantity=1000.0,
        net_amount=10500.0,
        venue="XLON",
        isin="GB0001234567",
        investment_decision_maker="ALGO",
    )
    params.update(overrides)
    return build_transaction_report(**params)


class TestTopLevelStructure:
    def test_type_field(self) -> None:
        result = _base_report()
        assert result["$type"] == "TransactionReportInstruction"

    def test_reporting_regime(self) -> None:
        result = _base_report()
        assert result["reportingRegime"] == "ESMA MiFIR RTS_22"

    def test_transaction_reference(self) -> None:
        result = _base_report()
        assert result["transactionReference"] == "TXN-CDM-001"

    def test_originating_workflow_step_present(self) -> None:
        result = _base_report()
        assert "originatingWorkflowStep" in result

    def test_reporting_side_present(self) -> None:
        result = _base_report()
        assert result["reportingSide"]["partyRole"] == "EXECUTING_ENTITY"


class TestProposedEvent:
    def test_intent_is_contract_formation(self) -> None:
        result = _base_report()
        event = result["originatingWorkflowStep"]["proposedEvent"]
        assert event["intent"] == "ContractFormation"

    def test_event_date_extracted_from_datetime(self) -> None:
        result = _base_report()
        event = result["originatingWorkflowStep"]["proposedEvent"]
        assert event["eventDate"] == "2024-01-15"

    def test_event_date_empty_when_no_datetime(self) -> None:
        result = _base_report(trading_date_time=None)
        event = result["originatingWorkflowStep"]["proposedEvent"]
        assert event["eventDate"] == ""

    def test_instruction_list_present(self) -> None:
        result = _base_report()
        instructions = result["originatingWorkflowStep"]["proposedEvent"]["instruction"]
        assert isinstance(instructions, list)
        assert len(instructions) == 1


class TestTradeParties:
    def _trade(self, **overrides: object) -> dict:
        result = _base_report(**overrides)
        return result["originatingWorkflowStep"]["proposedEvent"]["instruction"][0][
            "before"
        ]["trade"]

    def test_buyer_party_present(self) -> None:
        trade = self._trade()
        buyer = next(p for p in trade["party"] if p["partyRole"] == "BUYER")
        assert buyer["partyId"][0]["identifier"]["value"] == VALID_LEI
        assert buyer["partyId"][0]["identifierType"] == "LEI"

    def test_seller_party_present(self) -> None:
        trade = self._trade()
        seller = next(p for p in trade["party"] if p["partyRole"] == "SELLER")
        assert seller["partyId"][0]["identifierType"] == "LEI"

    def test_buyer_absent_when_id_is_none(self) -> None:
        trade = self._trade(buyer_id=None)
        roles = [p["partyRole"] for p in trade["party"]]
        assert "BUYER" not in roles

    def test_enrichment_populates_party_name(self) -> None:
        enrichment = EnrichmentResult(
            buyer=LeiEnrichment(
                lei=VALID_LEI,
                found=True,
                is_valid=True,
                reason="ISSUED",
                legal_name="ACME INVESTMENT FIRM LTD",
            )
        )
        result = build_transaction_report(
            transaction_ref="TXN-001",
            buyer_id=VALID_LEI,
            buyer_id_type="LEI",
            seller_id=None,
            seller_id_type=None,
            trading_date_time="2024-01-15T09:30:00",
            quantity=100.0,
            net_amount=None,
            enrichment=enrichment,
        )
        trade = result["originatingWorkflowStep"]["proposedEvent"]["instruction"][0][
            "before"
        ]["trade"]
        buyer = next(p for p in trade["party"] if p["partyRole"] == "BUYER")
        assert buyer["name"] == "ACME INVESTMENT FIRM LTD"

    def test_no_name_when_enrichment_is_none(self) -> None:
        trade = self._trade()
        buyer = next(p for p in trade["party"] if p["partyRole"] == "BUYER")
        assert "name" not in buyer


class TestProduct:
    def _security(self, **overrides: object) -> dict:
        result = _base_report(**overrides)
        return result["originatingWorkflowStep"]["proposedEvent"]["instruction"][0][
            "before"
        ]["trade"]["product"]["security"]

    def test_primary_asset_class_equity(self) -> None:
        security = self._security()
        assert security["primaryAssetClass"] == "EQUITY"

    def test_isin_identifier_present(self) -> None:
        security = self._security()
        isin_entry = next(
            i for i in security["identifier"] if i["identifierType"] == "ISIN"
        )
        assert isin_entry["identifier"]["value"] == "GB0001234567"

    def test_isin_absent_when_none(self) -> None:
        security = self._security(isin=None)
        assert "identifier" not in security

    def test_firds_enrichment_populates_full_name(self) -> None:
        enrichment = EnrichmentResult(
            instrument=InstrumentEnrichment(
                isin="GB0001234567",
                found=True,
                full_name="VODAFONE GROUP PLC ORD USD0.2",
                cfi_code="ESVUFR",
                mic="XLON",
            )
        )
        result = build_transaction_report(
            transaction_ref="TXN-001",
            buyer_id=None,
            buyer_id_type=None,
            seller_id=None,
            seller_id_type=None,
            trading_date_time=None,
            quantity=100.0,
            net_amount=None,
            isin="GB0001234567",
            enrichment=enrichment,
        )
        trade = result["originatingWorkflowStep"]["proposedEvent"]["instruction"][0][
            "before"
        ]["trade"]
        security = trade["product"]["security"]
        assert security["fullName"] == "VODAFONE GROUP PLC ORD USD0.2"
        assert security["cfiCode"] == "ESVUFR"

    def test_firds_not_found_omits_full_name(self) -> None:
        enrichment = EnrichmentResult(
            instrument=InstrumentEnrichment(isin="GB0001234567", found=False)
        )
        result = build_transaction_report(
            transaction_ref="TXN-001",
            buyer_id=None,
            buyer_id_type=None,
            seller_id=None,
            seller_id_type=None,
            trading_date_time=None,
            quantity=100.0,
            net_amount=None,
            isin="GB0001234567",
            enrichment=enrichment,
        )
        trade = result["originatingWorkflowStep"]["proposedEvent"]["instruction"][0][
            "before"
        ]["trade"]
        security = trade["product"]["security"]
        assert "fullName" not in security


class TestTradeLot:
    def _price_quantity(self, **overrides: object) -> dict:
        result = _base_report(**overrides)
        trade = result["originatingWorkflowStep"]["proposedEvent"]["instruction"][0][
            "before"
        ]["trade"]
        return trade["tradeLot"][0]["priceQuantity"][0]

    def test_quantity_value(self) -> None:
        pq = self._price_quantity()
        assert pq["quantity"][0]["value"] == 1000.0

    def test_quantity_unit_shares(self) -> None:
        pq = self._price_quantity()
        assert pq["quantity"][0]["unitOfAmount"]["financialUnit"] == "SHARES"

    def test_price_present(self) -> None:
        pq = self._price_quantity()
        assert pq["price"][0]["value"]["amount"] == 10500.0

    def test_price_absent_when_net_amount_none(self) -> None:
        pq = self._price_quantity(net_amount=None)
        assert "price" not in pq


class TestExecutionDetails:
    def _execution(self, **overrides: object) -> dict:
        result = _base_report(**overrides)
        return result["originatingWorkflowStep"]["proposedEvent"]["instruction"][0][
            "before"
        ]["trade"]["executionDetails"]

    def test_venue_mic_present(self) -> None:
        execution = self._execution()
        assert execution["executionVenue"]["value"] == "XLON"

    def test_execution_datetime(self) -> None:
        execution = self._execution()
        assert execution["executionDateTime"] == "2024-01-15T09:30:00"

    def test_execution_type_on_venue(self) -> None:
        execution = self._execution()
        assert execution["executionType"] == "ON_VENUE"

    def test_execution_details_absent_when_venue_and_datetime_none(self) -> None:
        result = _base_report(venue=None, trading_date_time=None)
        trade = result["originatingWorkflowStep"]["proposedEvent"]["instruction"][0][
            "before"
        ]["trade"]
        assert "executionDetails" not in trade


class TestInvestmentDecision:
    def test_investment_decision_present(self) -> None:
        result = _base_report(investment_decision_maker="ALGO")
        trade = result["originatingWorkflowStep"]["proposedEvent"]["instruction"][0][
            "before"
        ]["trade"]
        assert trade["investmentDecision"]["decisionMaker"] == "ALGO"

    def test_investment_decision_absent_when_none(self) -> None:
        result = _base_report(investment_decision_maker=None)
        trade = result["originatingWorkflowStep"]["proposedEvent"]["instruction"][0][
            "before"
        ]["trade"]
        assert "investmentDecision" not in trade
