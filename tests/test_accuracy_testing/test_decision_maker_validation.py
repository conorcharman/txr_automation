"""
Decision Maker Validation Tests
================================

Comprehensive test suite for Fund Trade Decision Maker validation.

Tests cover:
    - DecisionMakerRecord model
    - LEI lookup functionality
    - ID format validation
    - Decision Maker validation logic
    - Edge cases and error handling

Incident Codes:
    - 12_17: Buyer Decision Maker
    - 21_17: Seller Decision Maker
"""

from pathlib import Path
from typing import Dict

import pytest

from src.accuracy_testing.models.decision_maker_record import (
    DecisionMakerRecord,
    Product,
    ServiceLevel,
    determine_product,
)
from src.accuracy_testing.validators.decision_maker_validator import (
    DecisionMakerProcessor,
    DecisionMakerValidator,
    IDFormatValidator,
    LEILookupManager,
    ValidationStats,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_lei_lookup() -> Dict[str, str]:
    """Sample LEI lookup data."""
    return {
        "ABC001": "549300FUNDMANAGER0001",
        "XYZ002": "549300FUNDMANAGER0002",
        "DEF003": "549300CORRECTLEI12345",
        "EMPTY": "",  # Branch with empty LEI
    }


@pytest.fixture
def lei_manager(sample_lei_lookup) -> LEILookupManager:
    """LEI lookup manager with sample data."""
    return LEILookupManager.from_dict(sample_lei_lookup)


@pytest.fixture
def id_validator() -> IDFormatValidator:
    """ID format validator backed by core library."""
    return IDFormatValidator()


@pytest.fixture
def buyer_validator(lei_manager, id_validator) -> DecisionMakerValidator:
    """Buyer Decision Maker validator."""
    return DecisionMakerValidator(
        lei_lookup=lei_manager,
        id_validator=id_validator,
        party_type="Buyer",
    )


@pytest.fixture
def seller_validator(lei_manager, id_validator) -> DecisionMakerValidator:
    """Seller Decision Maker validator."""
    return DecisionMakerValidator(
        lei_lookup=lei_manager,
        id_validator=id_validator,
        party_type="Seller",
    )


# =============================================================================
# Test: DecisionMakerRecord Model
# =============================================================================


class TestDecisionMakerRecord:
    """Tests for DecisionMakerRecord dataclass."""

    def test_create_basic_record(self):
        """Test creating a basic record."""
        record = DecisionMakerRecord(
            transaction_ref="TXN001",
            account_id="A12345678",
            party_code="549300CLIENT00000001",
            dm_code="549300MANAGER0000001",
            account_type="General",
            service_level="D",
            branch_code="ABC001",
        )

        assert record.transaction_ref == "TXN001"
        assert record.account_id == "A12345678"
        assert record.party_type == "Buyer"  # Default
        assert record.error == "N"  # Default

    def test_from_dict_buyer(self):
        """Test creating record from dictionary for buyer."""
        data = {
            "Transaction Reference": "TXN002",
            "Account ID": "B98765432",
            "Buyer ID Code": "549300BUYER0000000001",
            "Buyer DM ID Code": "549300MANAGER0000001",
            "Account Type": "ISA",
            "Service Level": "D",
            "Branch Code": "XYZ002",
        }

        record = DecisionMakerRecord.from_dict(data, party_type="Buyer")

        assert record.transaction_ref == "TXN002"
        assert record.party_code == "549300BUYER0000000001"
        assert record.dm_code == "549300MANAGER0000001"
        assert record.party_type == "Buyer"

    def test_from_dict_seller(self):
        """Test creating record from dictionary for seller."""
        data = {
            "Transaction Reference": "TXN003",
            "Account ID": "A11111111",
            "Seller ID Code": "549300SELLER000000001",
            "Seller DM ID Code": "549300MANAGER0000002",
            "Account Type": "Trading",
            "Service Level": "A",
            "Branch Code": "DEF003",
        }

        record = DecisionMakerRecord.from_dict(data, party_type="Seller")

        assert record.party_code == "549300SELLER000000001"
        assert record.party_type == "Seller"

    def test_from_row(self):
        """Test creating record from CSV row list."""
        row = [
            "TXN004",  # 0: Transaction Reference
            "X22222222",  # 1: Account ID
            "549300PARTY000001",  # 2: Party Code
            "549300DM000000001",  # 3: DM Code
            "Managed",  # 4: Account Type
            "E",  # 5: Service Level
            "ABC001",  # 6: Branch Code
        ]

        record = DecisionMakerRecord.from_row(row, party_type="Buyer", row_index=5)

        assert record.transaction_ref == "TXN004"
        assert record.account_id == "X22222222"
        assert record.service_level == "E"
        assert record.row_index == 5

    def test_is_sipp_property(self):
        """Test SIPP detection."""
        sipp_record = DecisionMakerRecord(
            transaction_ref="TXN",
            account_id="A1",
            party_code="",
            dm_code="",
            account_type="SIPP",
            service_level="D",
            branch_code="",
        )

        non_sipp_record = DecisionMakerRecord(
            transaction_ref="TXN",
            account_id="A1",
            party_code="",
            dm_code="",
            account_type="ISA",
            service_level="D",
            branch_code="",
        )

        assert sipp_record.is_sipp is True
        assert non_sipp_record.is_sipp is False

    def test_is_discretionary_property(self):
        """Test discretionary detection."""
        discretionary = DecisionMakerRecord(
            transaction_ref="TXN",
            account_id="A1",
            party_code="",
            dm_code="",
            account_type="General",
            service_level="D",
            branch_code="",
        )

        advisory = DecisionMakerRecord(
            transaction_ref="TXN",
            account_id="A1",
            party_code="",
            dm_code="",
            account_type="General",
            service_level="A",
            branch_code="",
        )

        execution = DecisionMakerRecord(
            transaction_ref="TXN",
            account_id="A1",
            party_code="",
            dm_code="",
            account_type="General",
            service_level="E",
            branch_code="",
        )

        assert discretionary.is_discretionary is True
        assert advisory.is_discretionary is False
        assert execution.is_discretionary is False

    def test_dm_equals_party_code_property(self):
        """Test DM equals party code detection."""
        same_code = DecisionMakerRecord(
            transaction_ref="TXN",
            account_id="A1",
            party_code="549300SAME0000000001",
            dm_code="549300SAME0000000001",
            account_type="General",
            service_level="D",
            branch_code="",
        )

        different_code = DecisionMakerRecord(
            transaction_ref="TXN",
            account_id="A1",
            party_code="549300PARTY000000001",
            dm_code="549300DM00000000001",
            account_type="General",
            service_level="D",
            branch_code="",
        )

        assert same_code.dm_equals_party_code is True
        assert different_code.dm_equals_party_code is False

    def test_correction_field_template(self):
        """Test correction field template by party type."""
        buyer_record = DecisionMakerRecord(
            transaction_ref="TXN",
            account_id="A1",
            party_code="",
            dm_code="",
            account_type="",
            service_level="",
            branch_code="",
            party_type="Buyer",
        )

        seller_record = DecisionMakerRecord(
            transaction_ref="TXN",
            account_id="A1",
            party_code="",
            dm_code="",
            account_type="",
            service_level="",
            branch_code="",
            party_type="Seller",
        )

        assert "Buyer decision maker" in buyer_record.correction_field_template
        assert "Seller decision maker" in seller_record.correction_field_template

    def test_to_output_row(self):
        """Test converting record to output row."""
        record = DecisionMakerRecord(
            transaction_ref="TXN001",
            account_id="A12345678",
            party_code="549300CLIENT00000001",
            dm_code="549300MANAGER0000001",
            account_type="General",
            service_level="D",
            branch_code="ABC001",
            party_code_type="LEI",
            dm_code_type="LEI",
            product="AJB",
            error="N",
            correction="",
            correction_field="",
        )

        row = record.to_output_row()

        assert len(row) == 13
        assert row[0] == "TXN001"
        assert row[3] == "LEI"  # party_code_type
        assert row[6] == "AJB"  # product
        assert row[10] == "N"  # error


# =============================================================================
# Test: Product Determination
# =============================================================================


class TestDetermineProduct:
    """Tests for product determination from account ID."""

    def test_ajb_prefix(self):
        """Test AJB product for 'A' prefix."""
        assert determine_product("A12345678") == "AJB"
        assert determine_product("a12345678") == "AJB"

    def test_ajbic_prefix(self):
        """Test AJBIC product for 'B' prefix."""
        assert determine_product("B98765432") == "AJBIC"
        assert determine_product("b98765432") == "AJBIC"

    def test_dodl_prefix(self):
        """Test DODL product for 'X' prefix."""
        assert determine_product("X11111111") == "DODL"
        assert determine_product("x11111111") == "DODL"

    def test_custody_solutions_default(self):
        """Test Custody Solutions for other prefixes."""
        assert determine_product("C12345678") == "Custody Solutions"
        assert determine_product("D12345678") == "Custody Solutions"
        assert determine_product("123456789") == "Custody Solutions"

    def test_empty_account_id(self):
        """Test empty account ID returns Custody Solutions."""
        assert determine_product("") == "Custody Solutions"
        assert determine_product(None) == "Custody Solutions"


# =============================================================================
# Test: LEI Lookup Manager
# =============================================================================


class TestLEILookupManager:
    """Tests for LEI lookup functionality."""

    def test_lookup_existing_branch(self, lei_manager):
        """Test lookup for existing branch."""
        exists, lei = lei_manager.lookup("ABC001")

        assert exists is True
        assert lei == "549300FUNDMANAGER0001"

    def test_lookup_nonexistent_branch(self, lei_manager):
        """Test lookup for non-existent branch."""
        exists, lei = lei_manager.lookup("UNKNOWN")

        assert exists is False
        assert lei == ""

    def test_lookup_empty_lei(self, lei_manager):
        """Test lookup for branch with empty LEI."""
        exists, lei = lei_manager.lookup("EMPTY")

        assert exists is True
        assert lei == ""

    def test_lookup_strips_whitespace(self, lei_manager):
        """Test that whitespace is stripped from branch code."""
        exists, lei = lei_manager.lookup("  ABC001  ")

        assert exists is True
        assert lei == "549300FUNDMANAGER0001"

    def test_len_method(self, lei_manager):
        """Test __len__ method."""
        assert len(lei_manager) == 4


# =============================================================================
# Test: ID Format Validator
# =============================================================================


class TestIDFormatValidator:
    """Tests for ID format validation."""

    def test_lei_format(self, id_validator):
        """Test LEI format detection."""
        assert id_validator.validate("549300ABCDEFGHIJ1234") == "LEI"
        assert (
            id_validator.validate("213800VALID00000000XX") == ""
        )  # Invalid checksum format

    def test_empty_id(self, id_validator):
        """Test empty ID returns empty string."""
        assert id_validator.validate("") == ""
        assert id_validator.validate("   ") == ""
        assert id_validator.validate(None) == ""

    def test_unknown_id_returns_empty(self, id_validator):
        """Test that an unrecognised code returns empty string."""
        assert id_validator.validate("XXXXXXXXXX") == ""


# =============================================================================
# Test: Decision Maker Validation Logic
# =============================================================================


class TestDecisionMakerValidator:
    """Tests for Decision Maker validation logic."""

    def test_sipp_account_no_error(self, buyer_validator):
        """SIPP accounts should always pass validation."""
        record = DecisionMakerRecord(
            transaction_ref="TEST001",
            account_id="A12345678",
            party_code="549300CLIENT00000001",
            dm_code="549300CLIENT00000001",  # Same value - normally error
            account_type="SIPP",
            service_level="D",  # Discretionary
            branch_code="ABC001",
        )

        buyer_validator.validate_record(record)

        assert record.error == "N"
        assert record.correction == ""

    def test_non_discretionary_no_error(self, buyer_validator):
        """Non-discretionary accounts should always pass."""
        record = DecisionMakerRecord(
            transaction_ref="TEST002",
            account_id="A12345678",
            party_code="549300CLIENT00000001",
            dm_code="",  # Empty - normally error for discretionary
            account_type="ISA",
            service_level="E",  # Execution only
            branch_code="ABC001",
        )

        buyer_validator.validate_record(record)

        assert record.error == "N"

    def test_discretionary_empty_dm_with_valid_lei(self, buyer_validator):
        """Empty DM code with valid LEI lookup should error with correction."""
        record = DecisionMakerRecord(
            transaction_ref="TEST003",
            account_id="A12345678",
            party_code="549300CLIENT00000001",
            dm_code="",
            account_type="General",
            service_level="D",
            branch_code="ABC001",
        )

        buyer_validator.validate_record(record)

        assert record.error == "Y"
        assert record.correction == "549300FUNDMANAGER0001:L"
        assert "decision maker code" in record.correction_field

    def test_discretionary_same_value_with_different_lei(self, buyer_validator):
        """DM code same as party code with different LEI available."""
        record = DecisionMakerRecord(
            transaction_ref="TEST004",
            account_id="A12345678",
            party_code="549300CLIENT00000001",
            dm_code="549300CLIENT00000001",  # Same as party code
            account_type="General",
            service_level="D",
            branch_code="ABC001",
        )

        buyer_validator.validate_record(record)

        assert record.error == "Y"
        assert record.correction == "549300FUNDMANAGER0001:L"

    def test_discretionary_different_values_no_error(self, buyer_validator):
        """Different DM code should be valid."""
        record = DecisionMakerRecord(
            transaction_ref="TEST005",
            account_id="A12345678",
            party_code="549300CLIENT00000001",
            dm_code="549300MANAGER0000001",  # Different
            account_type="General",
            service_level="D",
            branch_code="ABC001",
        )

        buyer_validator.validate_record(record)

        assert record.error == "N"
        assert record.correction == ""

    def test_unknown_branch_tbc(self, buyer_validator):
        """Unknown branch should result in TBC."""
        record = DecisionMakerRecord(
            transaction_ref="TEST006",
            account_id="A12345678",
            party_code="549300CLIENT00000001",
            dm_code="",
            account_type="General",
            service_level="D",
            branch_code="UNKNOWN",  # Not in lookup
        )

        buyer_validator.validate_record(record)

        assert "TBC" in record.error
        assert "branch" in record.error.lower()

    def test_empty_lei_in_lookup_error(self, buyer_validator):
        """Branch with empty LEI should be error without correction."""
        record = DecisionMakerRecord(
            transaction_ref="TEST007",
            account_id="A12345678",
            party_code="549300CLIENT00000001",
            dm_code="",
            account_type="General",
            service_level="D",
            branch_code="EMPTY",  # Has empty LEI
        )

        buyer_validator.validate_record(record)

        assert record.error == "Y"
        assert record.correction == ""  # No correction possible

    def test_same_value_lei_matches_dm(self, buyer_validator):
        """Same value where LEI matches DM should be TBC."""
        record = DecisionMakerRecord(
            transaction_ref="TEST008",
            account_id="A12345678",
            party_code="549300FUNDMANAGER0001",  # Same as LEI lookup
            dm_code="549300FUNDMANAGER0001",
            account_type="General",
            service_level="D",
            branch_code="ABC001",
        )

        buyer_validator.validate_record(record)

        # LEI lookup returns same value as current DM - investigate
        assert "TBC" in record.error

    def test_custody_solutions_discretionary(self, buyer_validator):
        """Custody Solutions with discretionary should validate."""
        record = DecisionMakerRecord(
            transaction_ref="TEST009",
            account_id="C12345678",  # Custody Solutions prefix
            party_code="549300CLIENT00000001",
            dm_code="",
            account_type="Custody Solutions",
            service_level="D",
            branch_code="XYZ002",
        )

        buyer_validator.validate_record(record)

        assert record.error == "Y"
        assert record.correction == "549300FUNDMANAGER0002:L"

    def test_product_determination_in_validation(self, buyer_validator):
        """Validation should set product field."""
        record = DecisionMakerRecord(
            transaction_ref="TEST010",
            account_id="A12345678",
            party_code="549300CLIENT00000001",
            dm_code="549300MANAGER0000001",
            account_type="General",
            service_level="D",
            branch_code="ABC001",
        )

        buyer_validator.validate_record(record)

        assert record.product == "AJB"

    def test_id_type_classification(self, buyer_validator):
        """Validation should classify ID types."""
        record = DecisionMakerRecord(
            transaction_ref="TEST011",
            account_id="A12345678",
            party_code="549300CLIENT0000001X",  # LEI-like
            dm_code="549300MANAGER000001XY",  # LEI-like
            account_type="General",
            service_level="D",
            branch_code="ABC001",
        )

        buyer_validator.validate_record(record)

        # Should attempt to classify ID types
        # (actual results depend on patterns)
        assert record.party_code_type is not None
        assert record.dm_code_type is not None


# =============================================================================
# Test: Seller Variant
# =============================================================================


class TestSellerDecisionMakerValidator:
    """Tests specific to Seller Decision Maker validation."""

    def test_seller_correction_field(self, seller_validator):
        """Seller validation should use seller-specific field names."""
        record = DecisionMakerRecord(
            transaction_ref="SELLER001",
            account_id="A12345678",
            party_code="549300CLIENT00000001",
            dm_code="",
            account_type="General",
            service_level="D",
            branch_code="ABC001",
            party_type="Seller",
        )

        seller_validator.validate_record(record)

        assert record.error == "Y"
        assert "Seller decision maker" in record.correction_field


# =============================================================================
# Test: Batch Processing
# =============================================================================


class TestBatchProcessing:
    """Tests for batch validation processing."""

    def test_validate_batch_statistics(self, buyer_validator):
        """Test batch validation returns correct statistics."""
        records = [
            # No error - SIPP
            DecisionMakerRecord(
                transaction_ref="BATCH001",
                account_id="A1",
                party_code="549300C1",
                dm_code="549300C1",
                account_type="SIPP",
                service_level="D",
                branch_code="ABC001",
            ),
            # No error - different values
            DecisionMakerRecord(
                transaction_ref="BATCH002",
                account_id="A2",
                party_code="549300C2",
                dm_code="549300M2",
                account_type="General",
                service_level="D",
                branch_code="ABC001",
            ),
            # Error - empty DM
            DecisionMakerRecord(
                transaction_ref="BATCH003",
                account_id="A3",
                party_code="549300C3",
                dm_code="",
                account_type="General",
                service_level="D",
                branch_code="ABC001",
            ),
            # TBC - unknown branch
            DecisionMakerRecord(
                transaction_ref="BATCH004",
                account_id="A4",
                party_code="549300C4",
                dm_code="",
                account_type="General",
                service_level="D",
                branch_code="UNKNOWN",
            ),
            # No error - non-discretionary
            DecisionMakerRecord(
                transaction_ref="BATCH005",
                account_id="A5",
                party_code="549300C5",
                dm_code="",
                account_type="General",
                service_level="E",
                branch_code="ABC001",
            ),
        ]

        stats = buyer_validator.validate_batch(records)

        assert stats.total == 5
        assert stats.no_error == 3  # SIPP, different values, non-discretionary
        assert stats.error == 1  # Empty DM
        assert stats.tbc == 1  # Unknown branch
        assert stats.skipped_sipp == 1
        assert stats.skipped_non_discretionary == 1


# =============================================================================
# Test: Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_whitespace_handling(self, buyer_validator):
        """Test that whitespace is properly handled."""
        record = DecisionMakerRecord(
            transaction_ref="  SPACE001  ",
            account_id="  A12345678  ",
            party_code="  549300CLIENT00000001  ",
            dm_code="  549300MANAGER0000001  ",
            account_type="  General  ",
            service_level="  D  ",
            branch_code="  ABC001  ",
        )

        buyer_validator.validate_record(record)

        # Should still work with whitespace
        assert record.error == "N"

    def test_case_insensitive_account_type(self, buyer_validator):
        """Test case-insensitive account type matching."""
        for account_type in ["SIPP", "sipp", "Sipp", "SiPp"]:
            record = DecisionMakerRecord(
                transaction_ref="CASE001",
                account_id="A1",
                party_code="549300C1",
                dm_code="549300C1",  # Same - normally error
                account_type=account_type,
                service_level="D",
                branch_code="ABC001",
            )

            buyer_validator.validate_record(record)

            assert record.error == "N", f"Failed for account_type='{account_type}'"

    def test_case_insensitive_service_level(self, buyer_validator):
        """Test case-insensitive service level matching."""
        for service_level in ["D", "d"]:
            record = DecisionMakerRecord(
                transaction_ref="CASE002",
                account_id="A1",
                party_code="549300C1",
                dm_code="",
                account_type="General",
                service_level=service_level,
                branch_code="ABC001",
            )

            buyer_validator.validate_record(record)

            assert record.error == "Y", f"Failed for service_level='{service_level}'"

    def test_empty_all_fields(self, buyer_validator):
        """Test handling of record with all empty fields."""
        record = DecisionMakerRecord(
            transaction_ref="",
            account_id="",
            party_code="",
            dm_code="",
            account_type="",
            service_level="",
            branch_code="",
        )

        # Should not raise exception
        buyer_validator.validate_record(record)

        # Empty service level is not "D", so no error
        assert record.error == "N"

    def test_from_row_insufficient_columns(self):
        """Test from_row raises error for insufficient columns."""
        row = ["TXN", "ACCT", "CODE"]  # Only 3 columns

        with pytest.raises(ValueError, match="at least 7 columns"):
            DecisionMakerRecord.from_row(row)
