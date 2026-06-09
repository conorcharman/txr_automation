"""Unit tests for src/drr/compliance_mapper.py."""

from datetime import UTC, datetime

import pytest

from src.drr.compliance_mapper import (
    ComplianceReport,
    RuleResult,
    RuleStatus,
    check_transaction,
    validate_concat,
    validate_lei,
)
from src.drr.rule_catalogue import CATALOGUE

# ISO 17442 mod-97 verified valid LEI (ISDA)
VALID_LEI = "529900T8BM49AURSDO55"
# Same format, wrong check digits
INVALID_LEI_BAD_CHECK = "529900T8BM49AURSDO99"


def _base_params(**overrides: object) -> dict:
    params: dict = dict(
        transaction_ref="TXN-UNIT-001",
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
    return params


class TestValidateLei:
    def test_valid_lei(self) -> None:
        ok, err = validate_lei(VALID_LEI)
        assert ok is True
        assert err is None

    def test_valid_lei_lowercase_normalised(self) -> None:
        ok, err = validate_lei(VALID_LEI.lower())
        assert ok is True

    def test_valid_lei_with_surrounding_whitespace(self) -> None:
        ok, err = validate_lei(f"  {VALID_LEI}  ")
        assert ok is True

    def test_invalid_format_too_short(self) -> None:
        ok, err = validate_lei("TOOSHORT")
        assert ok is False
        assert err is not None

    def test_invalid_format_non_digit_suffix(self) -> None:
        ok, err = validate_lei("529900T8BM49AURSDOAB")
        assert ok is False

    def test_bad_check_digits(self) -> None:
        ok, err = validate_lei(INVALID_LEI_BAD_CHECK)
        assert ok is False
        assert err is not None
        assert "check digits" in err.lower()

    def test_empty_string(self) -> None:
        ok, err = validate_lei("")
        assert ok is False


class TestValidateConcat:
    def test_valid_concat_male(self) -> None:
        ok, err = validate_concat("GBNJSMITH#1980-01-01#M")
        assert ok is True
        assert err is None

    def test_valid_concat_female(self) -> None:
        ok, err = validate_concat("DEJANEMULLER#1975-06-15#F")
        assert ok is True

    def test_invalid_no_separators(self) -> None:
        ok, err = validate_concat("GBNATIONALID19800101M")
        assert ok is False
        assert err is not None

    def test_invalid_wrong_gender_char(self) -> None:
        ok, err = validate_concat("GBNJSMITH#1980-01-01#X")
        assert ok is False

    def test_invalid_bad_dob_format(self) -> None:
        ok, err = validate_concat("GBNJSMITH#01/01/1980#M")
        assert ok is False

    def test_invalid_missing_id(self) -> None:
        ok, err = validate_concat("GB#1980-01-01#M")
        assert ok is False

    def test_valid_concat_lowercase_normalised(self) -> None:
        ok, err = validate_concat("gbnjsmith#1980-01-01#m")
        assert ok is True


class TestCheckTransaction:
    def test_all_pass(self) -> None:
        report = check_transaction(**_base_params())
        assert report.overall_status == RuleStatus.PASS
        assert report.failed == 0
        assert report.warnings == 0
        assert report.passed > 0

    def test_transaction_ref_in_report(self) -> None:
        report = check_transaction(**_base_params(transaction_ref="MY-REF-123"))
        assert report.transaction_ref == "MY-REF-123"

    def test_checked_at_is_datetime(self) -> None:
        report = check_transaction(**_base_params())
        assert isinstance(report.checked_at, datetime)

    def test_missing_buyer_id_fails(self) -> None:
        report = check_transaction(**_base_params(buyer_id=None))
        buyer = next(r for r in report.results if r.rule_name == "BuyerSeller_Buyer")
        assert buyer.status == RuleStatus.FAIL
        assert report.overall_status == RuleStatus.FAIL

    def test_invalid_buyer_lei_fails(self) -> None:
        report = check_transaction(**_base_params(buyer_id=INVALID_LEI_BAD_CHECK))
        buyer = next(r for r in report.results if r.rule_name == "BuyerSeller_Buyer")
        assert buyer.status == RuleStatus.FAIL
        assert report.overall_status == RuleStatus.FAIL

    def test_valid_concat_buyer_passes(self) -> None:
        report = check_transaction(
            **_base_params(
                buyer_id="GBNJSMITH#1980-01-01#M",
                buyer_id_type="CONCAT",
            )
        )
        buyer = next(r for r in report.results if r.rule_name == "BuyerSeller_Buyer")
        assert buyer.status == RuleStatus.PASS

    def test_unknown_id_type_is_warning(self) -> None:
        report = check_transaction(**_base_params(buyer_id_type="UNKNOWN"))
        buyer = next(r for r in report.results if r.rule_name == "BuyerSeller_Buyer")
        assert buyer.status == RuleStatus.WARNING

    def test_nidn_id_type_presence_check(self) -> None:
        report = check_transaction(
            **_base_params(buyer_id="GB1234567", buyer_id_type="NIDN")
        )
        buyer = next(r for r in report.results if r.rule_name == "BuyerSeller_Buyer")
        assert buyer.status == RuleStatus.PASS

    def test_invalid_datetime_format_fails(self) -> None:
        report = check_transaction(**_base_params(trading_date_time="15/01/2024 09:30"))
        dt = next(r for r in report.results if r.rule_name == "TradingDateTime")
        assert dt.status == RuleStatus.FAIL

    def test_missing_datetime_fails(self) -> None:
        report = check_transaction(**_base_params(trading_date_time=None))
        dt = next(r for r in report.results if r.rule_name == "TradingDateTime")
        assert dt.status == RuleStatus.FAIL

    def test_datetime_with_z_suffix_passes(self) -> None:
        report = check_transaction(
            **_base_params(trading_date_time="2024-01-15T09:30:00Z")
        )
        dt = next(r for r in report.results if r.rule_name == "TradingDateTime")
        assert dt.status == RuleStatus.PASS

    def test_zero_quantity_fails(self) -> None:
        report = check_transaction(**_base_params(quantity=0.0, net_amount=None))
        qty = next(r for r in report.results if r.rule_name == "Quantity")
        assert qty.status == RuleStatus.FAIL

    def test_negative_quantity_is_warning(self) -> None:
        report = check_transaction(**_base_params(quantity=-100.0, net_amount=None))
        qty = next(r for r in report.results if r.rule_name == "Quantity")
        assert qty.status == RuleStatus.WARNING

    def test_positive_quantity_passes(self) -> None:
        report = check_transaction(**_base_params(quantity=500.0, net_amount=None))
        qty = next(r for r in report.results if r.rule_name == "Quantity")
        assert qty.status == RuleStatus.PASS

    def test_invalid_venue_mic_fails(self) -> None:
        report = check_transaction(**_base_params(venue="NOTAMIC"))
        venue = next(r for r in report.results if r.rule_name == "VenueOfExecution")
        assert venue.status == RuleStatus.FAIL

    def test_valid_venue_mic_passes(self) -> None:
        report = check_transaction(**_base_params(venue="XLON"))
        venue = next(r for r in report.results if r.rule_name == "VenueOfExecution")
        assert venue.status == RuleStatus.PASS

    def test_venue_none_excluded_from_results(self) -> None:
        report = check_transaction(**_base_params(venue=None))
        rule_names = [r.rule_name for r in report.results]
        assert "VenueOfExecution" not in rule_names

    def test_invalid_isin_fails(self) -> None:
        report = check_transaction(**_base_params(isin="NOTANISIN"))
        isin = next(
            r for r in report.results if r.rule_name == "InstrumentIdentificationCode"
        )
        assert isin.status == RuleStatus.FAIL

    def test_valid_isin_passes(self) -> None:
        report = check_transaction(**_base_params(isin="GB0001234567"))
        isin = next(
            r for r in report.results if r.rule_name == "InstrumentIdentificationCode"
        )
        assert isin.status == RuleStatus.PASS

    def test_isin_none_excluded_from_results(self) -> None:
        report = check_transaction(**_base_params(isin=None))
        rule_names = [r.rule_name for r in report.results]
        assert "InstrumentIdentificationCode" not in rule_names

    def test_missing_investment_decision_maker_is_warning(self) -> None:
        report = check_transaction(**_base_params(investment_decision_maker=None))
        idm = next(
            r for r in report.results if r.rule_name == "InvestmentDecisionWithinFirm"
        )
        assert idm.status == RuleStatus.WARNING

    def test_net_amount_none_excludes_price_rule(self) -> None:
        report = check_transaction(**_base_params(net_amount=None))
        rule_names = [r.rule_name for r in report.results]
        assert "Price" not in rule_names

    def test_net_amount_present_includes_price_rule(self) -> None:
        report = check_transaction(**_base_params(net_amount=10500.0))
        rule_names = [r.rule_name for r in report.results]
        assert "Price" in rule_names

    def test_rule_results_carry_regulatory_references(self) -> None:
        report = check_transaction(**_base_params())
        for result in report.results:
            assert result.field_number
            assert result.field_name
            assert result.regulation
            assert result.provision


class TestComplianceReportAggregation:
    def _make_report(self, statuses: list[RuleStatus]) -> ComplianceReport:
        ref = CATALOGUE["TradingDateTime"]
        report = ComplianceReport(transaction_ref="TEST", checked_at=datetime.now(UTC))
        for s in statuses:
            report.results.append(RuleResult.from_ref(ref, s))
        return report

    def test_all_pass_status(self) -> None:
        report = self._make_report([RuleStatus.PASS, RuleStatus.PASS])
        assert report.overall_status == RuleStatus.PASS

    def test_fail_dominates_warning(self) -> None:
        report = self._make_report(
            [RuleStatus.FAIL, RuleStatus.WARNING, RuleStatus.PASS]
        )
        assert report.overall_status == RuleStatus.FAIL

    def test_warning_dominates_pass(self) -> None:
        report = self._make_report([RuleStatus.WARNING, RuleStatus.PASS])
        assert report.overall_status == RuleStatus.WARNING

    def test_counts_are_correct(self) -> None:
        report = self._make_report(
            [RuleStatus.PASS, RuleStatus.FAIL, RuleStatus.WARNING, RuleStatus.PASS]
        )
        assert report.passed == 2
        assert report.failed == 1
        assert report.warnings == 1

    def test_empty_results_is_pass(self) -> None:
        report = ComplianceReport(transaction_ref="EMPTY", checked_at=datetime.now(UTC))
        assert report.overall_status == RuleStatus.PASS
        assert report.passed == 0
