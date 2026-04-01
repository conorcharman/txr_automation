#!/usr/bin/env python3
"""
Demo: Incorrect Net Amount Validation
======================================

Demonstrates the incorrect net amount validation functionality.
"""

from pathlib import Path
from decimal import Decimal
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.accuracy_testing.models.incorrect_net_amount_record import IncorrectNetAmountRecord
from src.accuracy_testing.validators.incorrect_net_amount_validator import IncorrectNetAmountValidator


def demo_pricing_validation():
    """Demonstrate pricing validation with various scenarios."""
    
    print("=" * 70)
    print("INCORRECT NET AMOUNT VALIDATION DEMO")
    print("=" * 70)
    print()
    
    # Create validator
    validator = IncorrectNetAmountValidator(tolerance=Decimal('0.01'), verbose=False)
    
    # Test Case 1: Perfect Match (Buy Transaction)
    print("Test Case 1: Perfect Match (Buy Transaction)")
    print("-" * 70)
    record1 = IncorrectNetAmountRecord(
        transaction_ref="44625CKTPC31",
        net_amount=Decimal('10250.00'),
        consideration=Decimal('10000.00'),
        interest=Decimal('250.00')
    )
    validator.validate_record(record1)
    print(f"Transaction Ref: {record1.transaction_ref}")
    print(f"Net Amount:      {record1.net_amount}")
    print(f"Consideration:   {record1.consideration}")
    print(f"Interest:        {record1.interest}")
    print(f"Total:           {record1.total}")
    print(f"Expected Int:    {record1.expected_interest}")
    print(f"Net Difference:  {record1.net_difference}")
    print(f"Error Status:    {record1.error} ✓")
    print()
    
    # Test Case 2: Perfect Match (Sell Transaction with negative interest)
    print("Test Case 2: Perfect Match (Sell Transaction)")
    print("-" * 70)
    record2 = IncorrectNetAmountRecord(
        transaction_ref="44625CKT72V1",
        net_amount=Decimal('14700.00'),
        consideration=Decimal('15000.00'),
        interest=Decimal('-300.00')
    )
    validator.validate_record(record2)
    print(f"Transaction Ref: {record2.transaction_ref}")
    print(f"Net Amount:      {record2.net_amount}")
    print(f"Consideration:   {record2.consideration}")
    print(f"Interest:        {record2.interest}")
    print(f"Total:           {record2.total}")
    print(f"Expected Int:    {record2.expected_interest}")
    print(f"Net Difference:  {record2.net_difference}")
    print(f"Error Status:    {record2.error} ✓")
    print()
    
    # Test Case 3: Error Detected (Discrepancy)
    print("Test Case 3: Error Detected (Discrepancy)")
    print("-" * 70)
    record3 = IncorrectNetAmountRecord(
        transaction_ref="44625CKVNVJ1",
        net_amount=Decimal('8680.00'),
        consideration=Decimal('8500.00'),
        interest=Decimal('200.00')  # Should be 180.00
    )
    validator.validate_record(record3)
    print(f"Transaction Ref: {record3.transaction_ref}")
    print(f"Net Amount:      {record3.net_amount}")
    print(f"Consideration:   {record3.consideration}")
    print(f"Interest:        {record3.interest} (INCORRECT!)")
    print(f"Total:           {record3.total}")
    print(f"Expected Int:    {record3.expected_interest}")
    print(f"Net Difference:  {record3.net_difference} (DISCREPANCY!)")
    print(f"Error Status:    {record3.error} ⚠️ (To Be Confirmed)")
    print()
    
    # Test Case 4: Tolerance Handling
    print("Test Case 4: Within Tolerance (Rounding)")
    print("-" * 70)
    record4 = IncorrectNetAmountRecord(
        transaction_ref="44625CKXGQR1",
        net_amount=Decimal('1150.00'),
        consideration=Decimal('1000.00'),
        interest=Decimal('150.005')  # Small rounding difference
    )
    validator.validate_record(record4)
    print(f"Transaction Ref: {record4.transaction_ref}")
    print(f"Net Amount:      {record4.net_amount}")
    print(f"Consideration:   {record4.consideration}")
    print(f"Interest:        {record4.interest}")
    print(f"Total:           {record4.total}")
    print(f"Expected Int:    {record4.expected_interest}")
    print(f"Net Difference:  {record4.net_difference} (within 0.01 tolerance)")
    print(f"Error Status:    {record4.error} ✓")
    print()
    
    # Batch Validation Statistics
    print("=" * 70)
    print("BATCH VALIDATION STATISTICS")
    print("=" * 70)
    all_records = [record1, record2, record3, record4]
    stats = validator.validate_batch(all_records)
    print(f"Total records:   {stats['total']}")
    print(f"Valid records:   {stats['valid']}")
    print(f"Invalid records: {stats['invalid']}")
    print(f"Errors:          {stats['errors']}")
    print()
    
    print("=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)
    print()
    print("Key Insights:")
    print("  • Validation formula: Net Amount = Consideration + Interest")
    print("  • Error status 'N' means no error (within tolerance)")
    print("  • Error status 'TBC' means discrepancy detected (To Be Confirmed)")
    print("  • Tolerance of 0.01 handles floating-point rounding")
    print("  • Negative interest is valid (common in sell transactions)")
    print()


if __name__ == "__main__":
    demo_pricing_validation()
