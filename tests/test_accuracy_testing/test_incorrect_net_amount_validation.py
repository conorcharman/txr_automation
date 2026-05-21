"""
Tests for Incorrect Net Amount Validation
==========================================

Unit and integration tests for incorrect net amount validation (Incident Code 35_3).
"""

import pytest
from decimal import Decimal
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.accuracy_testing.models.incorrect_net_amount_record import IncorrectNetAmountRecord
from src.accuracy_testing.validators.incorrect_net_amount_validator import (
    IncorrectNetAmountValidator,
    INSTRUMENT_TYPE_MAP,
)


class TestIncorrectNetAmountRecord:
    """Test IncorrectNetAmountRecord dataclass"""
    
    def test_create_record(self):
        """Test creating an IncorrectNetAmountRecord"""
        record = IncorrectNetAmountRecord(
            transaction_ref="TEST001",
            net_amount=Decimal('1150.00'),
            consideration=Decimal('1000.00'),
            interest=Decimal('150.00')
        )
        
        assert record.transaction_ref == "TEST001"
        assert record.net_amount == Decimal('1150.00')
        assert record.consideration == Decimal('1000.00')
        assert record.interest == Decimal('150.00')
        assert record.error == "N"  # Default
    
    def test_calculate_fields_perfect_match(self):
        """Test calculation when pricing is perfect"""
        record = IncorrectNetAmountRecord(
            transaction_ref="TEST001",
            net_amount=Decimal('1150.00'),
            consideration=Decimal('1000.00'),
            interest=Decimal('150.00')
        )
        
        record.calculate_fields()
        
        assert record.total == Decimal('1150.00')
        assert record.expected_interest == Decimal('-150.00')
        assert record.net_difference == Decimal('0.00')
        assert record.error == "N"
    
    def test_calculate_fields_with_discrepancy(self):
        """Test calculation when there's a pricing discrepancy"""
        record = IncorrectNetAmountRecord(
            transaction_ref="TEST002",
            net_amount=Decimal('1150.00'),
            consideration=Decimal('1000.00'),
            interest=Decimal('145.00')  # Wrong!
        )
        
        record.calculate_fields()
        
        assert record.total == Decimal('1145.00')
        assert record.expected_interest == Decimal('-150.00')
        assert record.net_difference == Decimal('-5.00')
        assert record.error == "TBC"
    
    def test_calculate_fields_with_tolerance(self):
        """Test tolerance handling for floating-point rounding"""
        record = IncorrectNetAmountRecord(
            transaction_ref="TEST003",
            net_amount=Decimal('1150.00'),
            consideration=Decimal('1000.00'),
            interest=Decimal('150.005')  # Rounding difference
        )
        
        record.calculate_fields(tolerance=Decimal('0.01'))
        
        assert record.net_difference == Decimal('0.005')
        assert record.error == "N"  # Within tolerance
    
    def test_from_dict_database_columns(self):
        """Test creating record from database column names"""
        data = {
            'REPORTREF': '44625CKTPC31',
            'NETAMT': '1150.00',
            'CLICSD': '1000.00',
            'INTRST': '150.00'
        }
        
        record = IncorrectNetAmountRecord.from_dict(data)
        
        assert record.transaction_ref == '44625CKTPC31'
        assert record.net_amount == Decimal('1150.00')
        assert record.consideration == Decimal('1000.00')
        assert record.interest == Decimal('150.00')
    
    def test_from_dict_python_fields(self):
        """Test creating record from Python field names"""
        data = {
            'transaction_ref': 'TEST001',
            'net_amount': '1150.00',
            'consideration': '1000.00',
            'interest': '150.00'
        }
        
        record = IncorrectNetAmountRecord.from_dict(data)
        
        assert record.transaction_ref == 'TEST001'
        assert record.net_amount == Decimal('1150.00')
    
    def test_to_dict(self):
        """Test converting record to dictionary"""
        record = IncorrectNetAmountRecord(
            transaction_ref="TEST001",
            net_amount=Decimal('1150.00'),
            consideration=Decimal('1000.00'),
            interest=Decimal('150.00')
        )
        record.calculate_fields()

        result = record.to_dict()

        assert result['Transaction Reference'] == 'TEST001'
        assert result['Error'] == 'N'
        assert result['Net Amount'] == 1150.00
        assert result['Total'] == 1150.00
        assert result['Net Difference'] == 0.00
        assert 'SEDOL' in result
        assert 'Instrument Classification' in result
        assert 'Instrument Type' in result

    def test_from_dict_with_asset_and_instrument(self):
        """Test creating record from database row that includes ASSET and INSTRUMENT"""
        data = {
            'REPORTREF': 'TEST_SEDOL',
            'NETAMT': '1000.00',
            'CLICSD': '900.00',
            'INTRST': '100.00',
            'ASSET': 'B1234567',
            'INSTRUMENT': 'DAFEQ',
        }

        record = IncorrectNetAmountRecord.from_dict(data)

        assert record.sedol == 'B1234567'
        assert record.instrument_classification == 'DAFEQ'
        assert record.instrument_type is None  # Not set until validator runs

    def test_from_dict_null_asset_and_instrument(self):
        """Test creating record from row with no ASSET or INSTRUMENT columns"""
        data = {
            'REPORTREF': 'TEST_NULL',
            'NETAMT': '500.00',
            'CLICSD': '450.00',
            'INTRST': '50.00',
        }

        record = IncorrectNetAmountRecord.from_dict(data)

        assert record.sedol is None
        assert record.instrument_classification is None


class TestIncorrectNetAmountValidator:
    """Test IncorrectNetAmountValidator class"""
    
    def test_validator_initialization(self):
        """Test validator initialization"""
        validator = IncorrectNetAmountValidator(tolerance=Decimal('0.01'))
        assert validator.tolerance == Decimal('0.01')
        assert validator.verbose == False
    
    def test_validate_record_no_error(self):
        """Test validating record with no error"""
        record = IncorrectNetAmountRecord(
            transaction_ref="TEST001",
            net_amount=Decimal('1150.00'),
            consideration=Decimal('1000.00'),
            interest=Decimal('150.00')
        )
        
        validator = IncorrectNetAmountValidator()
        validator.validate_record(record)
        
        assert record.error == "N"
        assert record.total == Decimal('1150.00')
        assert record.net_difference == Decimal('0.00')
    
    def test_validate_record_with_error(self):
        """Test validating record with discrepancy"""
        record = IncorrectNetAmountRecord(
            transaction_ref="TEST002",
            net_amount=Decimal('1150.00'),
            consideration=Decimal('1000.00'),
            interest=Decimal('145.00')
        )
        
        validator = IncorrectNetAmountValidator()
        validator.validate_record(record)
        
        assert record.error == "TBC"
        assert record.net_difference == Decimal('-5.00')
    
    def test_validate_batch(self):
        """Test batch validation statistics"""
        records = [
            IncorrectNetAmountRecord("TEST001", Decimal('1150'), Decimal('1000'), Decimal('150')),  # Valid
            IncorrectNetAmountRecord("TEST002", Decimal('1150'), Decimal('1000'), Decimal('145')),  # Invalid
            IncorrectNetAmountRecord("TEST003", Decimal('2000'), Decimal('1800'), Decimal('200'))   # Valid
        ]
        
        validator = IncorrectNetAmountValidator()
        stats = validator.validate_batch(records)
        
        assert stats['total'] == 3
        assert stats['valid'] == 2
        assert stats['invalid'] == 1
        assert stats['errors'] == 0
    
    def test_validate_record_safe_with_error(self):
        """Test safe validation handles errors gracefully"""
        # Create a record that will cause an error (empty string for amounts)
        record = IncorrectNetAmountRecord(
            transaction_ref="TEST_ERROR",
            net_amount=Decimal('0'),
            consideration=Decimal('0'),
            interest=Decimal('0')
        )
        
        validator = IncorrectNetAmountValidator()
        validator.validate_record_safe(record)
        
        # Should not raise exception, should set error status
        assert record.error in ["N", "TBC", "ERROR"]


class TestPricingExamples:
    """Test real-world pricing examples"""
    
    def test_example_buy_transaction(self):
        """Test example: Buy transaction"""
        record = IncorrectNetAmountRecord(
            transaction_ref="44625CKTPC31",
            net_amount=Decimal('10250.00'),
            consideration=Decimal('10000.00'),
            interest=Decimal('250.00')
        )
        
        record.calculate_fields()
        
        assert record.total == Decimal('10250.00')
        assert record.expected_interest == Decimal('-250.00')
        assert record.net_difference == Decimal('0.00')
        assert record.error == "N"
    
    def test_example_sell_transaction(self):
        """Test example: Sell transaction with negative interest"""
        record = IncorrectNetAmountRecord(
            transaction_ref="44625CKT72V1",
            net_amount=Decimal('14700.00'),
            consideration=Decimal('15000.00'),
            interest=Decimal('-300.00')
        )
        
        record.calculate_fields()
        
        assert record.total == Decimal('14700.00')
        assert record.expected_interest == Decimal('300.00')
        assert record.net_difference == Decimal('0.00')
        assert record.error == "N"
    
    def test_example_error_case(self):
        """Test example: Error case with discrepancy"""
        record = IncorrectNetAmountRecord(
            transaction_ref="44625CKVNVJ1",
            net_amount=Decimal('8680.00'),
            consideration=Decimal('8500.00'),
            interest=Decimal('200.00')  # Should be 180.00
        )
        
        record.calculate_fields()
        
        assert record.total == Decimal('8700.00')
        assert record.expected_interest == Decimal('-180.00')
        assert record.net_difference == Decimal('20.00')
        assert record.error == "TBC"
    
    def test_example_rounding_tolerance(self):
        """Test example: Rounding within tolerance"""
        record = IncorrectNetAmountRecord(
            transaction_ref="44625CKXGQR1",
            net_amount=Decimal('1150.00'),
            consideration=Decimal('1000.00'),
            interest=Decimal('150.005')
        )
        
        record.calculate_fields(tolerance=Decimal('0.01'))
        
        assert record.net_difference == Decimal('0.005')
        assert record.error == "N"  # Within tolerance


class TestClassifyInstrument:
    """Tests for IncorrectNetAmountValidator.classify_instrument()"""

    def test_three_char_match_daf_debt(self):
        """DAF is a 3-char Debt code and must take priority over any 2-char match"""
        assert IncorrectNetAmountValidator.classify_instrument("DAF") == "Debt"

    def test_three_char_match_on_longer_code(self):
        """3-char prefix extracted from a longer classification code"""
        assert IncorrectNetAmountValidator.classify_instrument("DAFEQ") == "Debt"

    def test_two_char_fallback_debt(self):
        """When 3-char prefix has no entry the validator falls back to 2-char"""
        for code in ("DB", "DC", "DW", "DT", "DG", "DN", "DD", "DY"):
            assert IncorrectNetAmountValidator.classify_instrument(code) == "Debt", code

    def test_two_char_fallback_equity(self):
        """2-char Equity codes are recognised via fallback"""
        for code in ("DA", "DE", "DS", "DM"):
            assert IncorrectNetAmountValidator.classify_instrument(code) == "Equity", code

    def test_two_char_equity_from_longer_code(self):
        """2-char Equity prefix extracted from a longer code (no 3-char match)"""
        assert IncorrectNetAmountValidator.classify_instrument("DA123") == "Equity"

    def test_no_match_returns_none(self):
        """Unknown classification codes return None"""
        assert IncorrectNetAmountValidator.classify_instrument("XYZ") is None
        assert IncorrectNetAmountValidator.classify_instrument("ZZ") is None

    def test_none_input_returns_none(self):
        """None classification returns None (null SEDOL / missing SECFIG row)"""
        assert IncorrectNetAmountValidator.classify_instrument(None) is None

    def test_empty_string_returns_none(self):
        """Blank string classification returns None"""
        assert IncorrectNetAmountValidator.classify_instrument("") is None

    def test_case_insensitive(self):
        """Classification lookup is case-insensitive"""
        assert IncorrectNetAmountValidator.classify_instrument("daf") == "Debt"
        assert IncorrectNetAmountValidator.classify_instrument("da") == "Equity"

    def test_instrument_type_map_contains_daf(self):
        """Verify the module-level constant includes the 3-char key"""
        assert "DAF" in INSTRUMENT_TYPE_MAP
        assert INSTRUMENT_TYPE_MAP["DAF"] == "Debt"


class TestApplyPreValidation:
    """Tests for IncorrectNetAmountValidator.apply_pre_validation()"""

    def _make_record(self, instrument_classification=None, net_amount="1000.00"):
        return IncorrectNetAmountRecord(
            transaction_ref="TEST",
            net_amount=Decimal(net_amount),
            consideration=Decimal("900.00"),
            interest=Decimal("100.00"),
            instrument_classification=instrument_classification,
        )

    def test_equity_sets_error_y(self):
        """Equity instrument type → Error = Y"""
        validator = IncorrectNetAmountValidator()
        record = self._make_record(instrument_classification="DA")

        validator.apply_pre_validation(record)

        assert record.instrument_type == "Equity"
        assert record.error == "Y"

    def test_debt_sets_error_n(self):
        """Debt instrument type → Error = N (passes through to 35_3 logic)"""
        validator = IncorrectNetAmountValidator()
        record = self._make_record(instrument_classification="DB")

        validator.apply_pre_validation(record)

        assert record.instrument_type == "Debt"
        assert record.error == "N"

    def test_daf_three_char_debt_sets_error_n(self):
        """3-char DAF code → Debt → Error = N"""
        validator = IncorrectNetAmountValidator()
        record = self._make_record(instrument_classification="DAF")

        validator.apply_pre_validation(record)

        assert record.instrument_type == "Debt"
        assert record.error == "N"

    def test_unmatched_code_passes_through(self):
        """Unrecognised classification code → instrument_type = None → Error = N"""
        validator = IncorrectNetAmountValidator()
        record = self._make_record(instrument_classification="XYZ")

        validator.apply_pre_validation(record)

        assert record.instrument_type is None
        assert record.error == "N"

    def test_null_sedol_passes_through(self):
        """No SEDOL / no classification → instrument_type = None → Error = N"""
        validator = IncorrectNetAmountValidator()
        record = self._make_record(instrument_classification=None)

        validator.apply_pre_validation(record)

        assert record.instrument_type is None
        assert record.error == "N"


class TestValidateRecordWithPreValidation:
    """Tests for validate_record() with the pre-validation stage integrated"""

    def test_equity_record_gets_error_y_and_no_arithmetic(self):
        """Equity records must be flagged Y; calculate_fields must not run"""
        validator = IncorrectNetAmountValidator()
        record = IncorrectNetAmountRecord(
            transaction_ref="EQ001",
            net_amount=Decimal("1000.00"),
            consideration=Decimal("900.00"),
            interest=Decimal("100.00"),
            instrument_classification="DA",
        )

        validator.validate_record(record)

        assert record.error == "Y"
        # Arithmetic fields should remain at default (0) — not calculated
        assert record.total == Decimal("0")
        assert record.net_difference == Decimal("0")

    def test_debt_record_runs_35_3_arithmetic(self):
        """Debt records → Error = N after passing pre-validation; 35_3 math applied"""
        validator = IncorrectNetAmountValidator()
        record = IncorrectNetAmountRecord(
            transaction_ref="DEBT001",
            net_amount=Decimal("1000.00"),
            consideration=Decimal("900.00"),
            interest=Decimal("100.00"),
            instrument_classification="DB",
        )

        validator.validate_record(record)

        assert record.error == "N"
        assert record.total == Decimal("1000.00")
        assert record.net_difference == Decimal("0.00")

    def test_debt_record_with_discrepancy_gets_tbc(self):
        """Debt record with net-amount mismatch → Error = TBC"""
        validator = IncorrectNetAmountValidator()
        record = IncorrectNetAmountRecord(
            transaction_ref="DEBT_ERR",
            net_amount=Decimal("1000.00"),
            consideration=Decimal("900.00"),
            interest=Decimal("50.00"),  # Total = 950, diff = -50
            instrument_classification="DC",
        )

        validator.validate_record(record)

        assert record.error == "TBC"
        assert record.net_difference == Decimal("-50.00")

    def test_validate_batch_counts_equity_as_invalid(self):
        """validate_batch() must count Error=Y records as 'invalid'"""
        validator = IncorrectNetAmountValidator()
        records = [
            IncorrectNetAmountRecord("DEBT", Decimal("1000"), Decimal("900"), Decimal("100"),
                                     instrument_classification="DB"),
            IncorrectNetAmountRecord("EQUITY", Decimal("1000"), Decimal("900"), Decimal("100"),
                                     instrument_classification="DA"),
        ]

        stats = validator.validate_batch(records)

        assert stats["total"] == 2
        assert stats["valid"] == 1
        assert stats["invalid"] == 1
        assert stats["errors"] == 0


class TestIncident35_10Registration:
    """Tests that 35_10 is properly registered across the configuration layer"""

    def test_35_10_in_incorrect_net_amount_incidents(self):
        """35_10 must be included in the template generator incident set"""
        from src.accuracy_testing.accuracy_template_generator import TemplateFormat
        assert "35_10" in TemplateFormat.INCORRECT_NET_AMOUNT_INCIDENTS

    def test_35_3_still_in_incorrect_net_amount_incidents(self):
        """Existing 35_3 must not be removed from the template generator incident set"""
        from src.accuracy_testing.accuracy_template_generator import TemplateFormat
        assert "35_3" in TemplateFormat.INCORRECT_NET_AMOUNT_INCIDENTS

    def test_35_10_resolves_to_incorrect_net_amount_template_type(self):
        """35_10 must resolve to 'incorrect_net_amount' template type"""
        from src.accuracy_testing.accuracy_template_generator import TemplateFormat
        assert TemplateFormat.get_template_type("35_10") == "incorrect_net_amount"

    def test_35_10_in_discovery_patterns(self):
        """35_10 must appear in the backend INCIDENT_CODE_PATTERNS"""
        from api.services.discovery import INCIDENT_CODE_PATTERNS
        assert "35_10" in INCIDENT_CODE_PATTERNS["incorrect_net_amount_validation"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
