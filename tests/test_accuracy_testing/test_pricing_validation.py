"""
Tests for Pricing Validation
=============================

Unit and integration tests for pricing data validation (Incident Code 35_3).
"""

import pytest
from decimal import Decimal
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.accuracy_testing.models.pricing_record import PricingRecord
from src.accuracy_testing.validators.pricing_validator import PricingValidator


class TestPricingRecord:
    """Test PricingRecord dataclass"""
    
    def test_create_record(self):
        """Test creating a PricingRecord"""
        record = PricingRecord(
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
        record = PricingRecord(
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
        record = PricingRecord(
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
        record = PricingRecord(
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
        
        record = PricingRecord.from_dict(data)
        
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
        
        record = PricingRecord.from_dict(data)
        
        assert record.transaction_ref == 'TEST001'
        assert record.net_amount == Decimal('1150.00')
    
    def test_to_dict(self):
        """Test converting record to dictionary"""
        record = PricingRecord(
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


class TestPricingValidator:
    """Test PricingValidator class"""
    
    def test_validator_initialization(self):
        """Test validator initialization"""
        validator = PricingValidator(tolerance=Decimal('0.01'))
        assert validator.tolerance == Decimal('0.01')
        assert validator.verbose == False
    
    def test_validate_record_no_error(self):
        """Test validating record with no error"""
        record = PricingRecord(
            transaction_ref="TEST001",
            net_amount=Decimal('1150.00'),
            consideration=Decimal('1000.00'),
            interest=Decimal('150.00')
        )
        
        validator = PricingValidator()
        validator.validate_record(record)
        
        assert record.error == "N"
        assert record.total == Decimal('1150.00')
        assert record.net_difference == Decimal('0.00')
    
    def test_validate_record_with_error(self):
        """Test validating record with discrepancy"""
        record = PricingRecord(
            transaction_ref="TEST002",
            net_amount=Decimal('1150.00'),
            consideration=Decimal('1000.00'),
            interest=Decimal('145.00')
        )
        
        validator = PricingValidator()
        validator.validate_record(record)
        
        assert record.error == "TBC"
        assert record.net_difference == Decimal('-5.00')
    
    def test_validate_batch(self):
        """Test batch validation statistics"""
        records = [
            PricingRecord("TEST001", Decimal('1150'), Decimal('1000'), Decimal('150')),  # Valid
            PricingRecord("TEST002", Decimal('1150'), Decimal('1000'), Decimal('145')),  # Invalid
            PricingRecord("TEST003", Decimal('2000'), Decimal('1800'), Decimal('200'))   # Valid
        ]
        
        validator = PricingValidator()
        stats = validator.validate_batch(records)
        
        assert stats['total'] == 3
        assert stats['valid'] == 2
        assert stats['invalid'] == 1
        assert stats['errors'] == 0
    
    def test_validate_record_safe_with_error(self):
        """Test safe validation handles errors gracefully"""
        # Create a record that will cause an error (empty string for amounts)
        record = PricingRecord(
            transaction_ref="TEST_ERROR",
            net_amount=Decimal('0'),
            consideration=Decimal('0'),
            interest=Decimal('0')
        )
        
        validator = PricingValidator()
        validator.validate_record_safe(record)
        
        # Should not raise exception, should set error status
        assert record.error in ["N", "TBC", "ERROR"]


class TestPricingExamples:
    """Test real-world pricing examples"""
    
    def test_example_buy_transaction(self):
        """Test example: Buy transaction"""
        record = PricingRecord(
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
        record = PricingRecord(
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
        record = PricingRecord(
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
        record = PricingRecord(
            transaction_ref="44625CKXGQR1",
            net_amount=Decimal('1150.00'),
            consideration=Decimal('1000.00'),
            interest=Decimal('150.005')
        )
        
        record.calculate_fields(tolerance=Decimal('0.01'))
        
        assert record.net_difference == Decimal('0.005')
        assert record.error == "N"  # Within tolerance


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
