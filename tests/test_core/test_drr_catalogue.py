"""Unit tests for src/drr/rule_catalogue.py."""

import pytest

from src.drr.rule_catalogue import (
    CATALOGUE,
    VALIDATOR_TO_RULES,
    RuleReference,
    get_rules_for_validator,
)


class TestCatalogue:
    def test_catalogue_has_expected_entry_count(self) -> None:
        assert len(CATALOGUE) == 24

    def test_required_rule_keys_present(self) -> None:
        required = {
            "BuyerSeller_Buyer",
            "BuyerSeller_Seller",
            "TradingDateTime",
            "Quantity",
            "Price",
            "VenueOfExecution",
            "InstrumentIdentificationCode",
            "InvestmentDecisionWithinFirm",
        }
        assert required <= set(CATALOGUE.keys())

    def test_catalogue_keys_match_rule_names(self) -> None:
        for key, ref in CATALOGUE.items():
            assert key == ref.rule_name

    def test_rule_reference_fields_non_empty(self) -> None:
        for ref in CATALOGUE.values():
            assert ref.rule_name, f"Empty rule_name for {ref}"
            assert ref.field_number, f"Empty field_number for {ref.rule_name}"
            assert ref.field_name, f"Empty field_name for {ref.rule_name}"
            assert ref.regulation, f"Empty regulation for {ref.rule_name}"
            assert ref.provision, f"Empty provision for {ref.rule_name}"

    def test_rule_reference_is_frozen(self) -> None:
        ref = CATALOGUE["TradingDateTime"]
        with pytest.raises((AttributeError, TypeError)):
            ref.rule_name = "other"  # type: ignore[misc]

    def test_buyer_seller_field_numbers(self) -> None:
        assert CATALOGUE["BuyerSeller_Buyer"].field_number == "7"
        assert CATALOGUE["BuyerSeller_Seller"].field_number == "16"

    def test_trading_datetime_field_number(self) -> None:
        assert CATALOGUE["TradingDateTime"].field_number == "28"

    def test_all_entries_are_rule_references(self) -> None:
        for ref in CATALOGUE.values():
            assert isinstance(ref, RuleReference)


class TestValidatorToRules:
    def test_buyer_validator_maps_to_buyer_rule(self) -> None:
        assert VALIDATOR_TO_RULES["validate-buyer"] == ["BuyerSeller_Buyer"]

    def test_seller_validator_maps_to_seller_rule(self) -> None:
        assert VALIDATOR_TO_RULES["validate-seller"] == ["BuyerSeller_Seller"]

    def test_time_validator_maps_to_datetime_rule(self) -> None:
        assert "TradingDateTime" in VALIDATOR_TO_RULES["validate-incorrect-time"]

    def test_net_amount_validator_maps_to_quantity_and_price(self) -> None:
        rules = VALIDATOR_TO_RULES["validate-incorrect-net-amount"]
        assert "Quantity" in rules
        assert "Price" in rules

    def test_get_rules_for_validator_returns_rule_references(self) -> None:
        refs = get_rules_for_validator("validate-buyer")
        assert len(refs) == 1
        assert refs[0].rule_name == "BuyerSeller_Buyer"
        assert isinstance(refs[0], RuleReference)

    def test_get_rules_for_validator_multi_rule(self) -> None:
        refs = get_rules_for_validator("validate-incorrect-net-amount")
        rule_names = {r.rule_name for r in refs}
        assert {"Quantity", "Price"} <= rule_names

    def test_get_rules_for_unknown_validator_returns_empty(self) -> None:
        assert get_rules_for_validator("nonexistent-validator") == []

    def test_all_mapped_rules_exist_in_catalogue(self) -> None:
        for validator, rule_names in VALIDATOR_TO_RULES.items():
            for name in rule_names:
                assert (
                    name in CATALOGUE
                ), f"{validator} references unknown rule '{name}'"
