#!/usr/bin/env python3
"""
Test script to verify fallback ID and CONCAT generation fixes.

This script tests:
1. Fallback ID recognition and validation
2. CONCAT generation is skipped for countries that don't support it
3. Fallback ID generation when CONCAT is not supported
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from accuracy_testing.processor import ClientRecord, InconsistentIDProcessor, IDValidationProcessor
from accuracy_testing.core import id_format_manager

def test_fallback_id_detection():
    """Test that fallback IDs are correctly detected and validated."""
    print("\n" + "=" * 70)
    print("TEST 1: Fallback ID Detection and Validation")
    print("=" * 70)
    
    # Test case: Valid fallback ID (GB_12345 for GB nationality)
    record = ClientRecord(
        row_index=1,
        transaction_ref="TEST001",
        account_id="ACC001", 
        person_code="12345",
        account_type="C",
        id_value="GB_12345",
        id_type="NIDN",
        first_name="John",
        surname="Smith",
        date_of_birth="1990-01-01",
        gender="M",
        primary_nationality="GB",
        trade_date_time_raw="2024-01-01 10:00:00"
    )
    
    # Test with InconsistentIDProcessor
    processor = InconsistentIDProcessor(verbose=True)
    
    # Check if fallback ID pattern is detected
    is_fallback = processor.is_fallback_id_pattern("GB_12345", "12345", "GB")
    print(f"✓ Is 'GB_12345' a valid fallback ID for person '12345' in GB? {is_fallback}")
    assert is_fallback, "Failed to detect valid fallback ID"
    
    # Test invalid cases
    is_fallback_wrong_country = processor.is_fallback_id_pattern("FR_12345", "12345", "GB")
    print(f"✓ Is 'FR_12345' a valid fallback ID for person '12345' in GB? {is_fallback_wrong_country}")
    assert not is_fallback_wrong_country, "Should not accept fallback ID with wrong country"
    
    is_fallback_wrong_person = processor.is_fallback_id_pattern("GB_99999", "12345", "GB")
    print(f"✓ Is 'GB_99999' a valid fallback ID for person '12345' in GB? {is_fallback_wrong_person}")
    assert not is_fallback_wrong_person, "Should not accept fallback ID with wrong person code"
    
    print("\n✅ Fallback ID detection tests passed!")


def test_concat_support_detection():
    """Test that CONCAT support is correctly detected for countries."""
    print("\n" + "=" * 70)
    print("TEST 2: CONCAT Support Detection")
    print("=" * 70)
    
    processor = InconsistentIDProcessor()
    
    # Countries that support CONCAT
    concat_countries = ["GB", "FR", "DE", "SE", "NL", "BE", "DK", "FI"]
    for country in concat_countries:
        supports = processor.supports_concat(country)
        print(f"✓ Does {country} support CONCAT? {supports}")
        assert supports, f"{country} should support CONCAT"
    
    # Countries that do NOT support CONCAT (no pattern defined)
    non_concat_countries = ["ES", "IT"]  # Spain and Italy have NIDN but not CONCAT
    for country in non_concat_countries:
        supports = processor.supports_concat(country)
        print(f"✓ Does {country} support CONCAT? {supports}")
        assert not supports, f"{country} should NOT support CONCAT"
    
    print("\n✅ CONCAT support detection tests passed!")


def test_correction_generation_without_concat():
    """Test that fallback IDs are generated when CONCAT is not supported."""
    print("\n" + "=" * 70)
    print("TEST 3: Correction Generation for Non-CONCAT Countries")
    print("=" * 70)
    
    # Test case: ES client with invalid NIDN (should generate fallback, not CONCAT)
    record = ClientRecord(
        row_index=1,
        transaction_ref="TEST002",
        account_id="ACC002",
        person_code="98765",
        account_type="C",
        id_value="INVALID_ID",  # Invalid ID
        id_type="NIDN",
        first_name="Maria",
        surname="Garcia",
        date_of_birth="1985-05-15",
        gender="F",
        primary_nationality="ES"  # Spain doesn't support CONCAT
    )
    
    processor = IDValidationProcessor(verbose=True)
    
    # Generate correction
    correction = processor._generate_correction(record, "ES")
    
    if correction:
        correction_id, correction_type = correction
        print(f"✓ Generated correction: {correction_id} (type: {correction_type})")
        
        # Should be fallback ID (ES98765), not CONCAT
        assert correction_type == "NIDN", f"Expected NIDN fallback, got {correction_type}"
        assert correction_id == "ES98765", f"Expected ES98765, got {correction_id}"
        print("✓ Correctly generated fallback ID instead of CONCAT for non-CONCAT country")
    else:
        print("✗ Failed to generate correction")
        assert False, "Should have generated a fallback ID"
    
    print("\n✅ Correction generation test passed!")


def test_concat_generation_for_concat_countries():
    """Test that CONCAT is still generated for countries that support it."""
    print("\n" + "=" * 70)
    print("TEST 4: CONCAT Generation for CONCAT-Supporting Countries")
    print("=" * 70)
    
    # Test case: GB client with invalid NIDN (should try CONCAT first)
    record = ClientRecord(
        row_index=1,
        transaction_ref="TEST003",
        account_id="ACC003",
        person_code="54321",
        account_type="C",
        id_value="INVALID_ID",
        id_type="NIDN",
        first_name="James",
        surname="Brown",
        date_of_birth="1975-12-25",
        gender="M",
        primary_nationality="GB"  # GB supports CONCAT
    )
    
    processor = IDValidationProcessor(verbose=True)
    
    # Generate correction
    correction = processor._generate_correction(record, "GB")
    
    if correction:
        correction_id, correction_type = correction
        print(f"✓ Generated correction: {correction_id} (type: {correction_type})")
        
        # Should be CONCAT (GB19751225JAMESBROWN)
        assert correction_type == "CONCAT", f"Expected CONCAT, got {correction_type}"
        print("✓ Correctly generated CONCAT for CONCAT-supporting country")
    else:
        print("✗ Failed to generate correction")
        assert False, "Should have generated a CONCAT ID"
    
    print("\n✅ CONCAT generation test passed!")


def main():
    """Run all tests."""
    print("=" * 70)
    print("FALLBACK ID AND CONCAT GENERATION FIX - TEST SUITE")
    print("=" * 70)
    
    try:
        test_fallback_id_detection()
        test_concat_support_detection()
        test_correction_generation_without_concat()
        test_concat_generation_for_concat_countries()
        
        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)
        return 0
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
