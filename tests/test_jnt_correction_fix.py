#!/usr/bin/env python3
"""
Test for JNT (Joint Account) False Positive Correction Bug Fix
==============================================================

This test verifies that joint account records that pass validation
do NOT have corrections generated.

Bug description:
- All JNT account records were having corrections generated
- The corrections were identical to the original IDs (false positives)
- This was because _aggregate_jnt_pair() always built correction_output
  even when both records passed validation

Expected behavior:
- If both JNT records pass validation: NO correction_output
- If one or both fail: correction_output shows corrected/original values
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from accuracy_testing.processor import IDValidationProcessor, ClientRecord


def test_jnt_both_pass_no_correction():
    """Test that JNT pair with both records passing has NO correction."""
    print("\n" + "="*70)
    print("TEST 1: JNT Pair - Both Pass Validation")
    print("="*70)
    
    # Create two valid UK records for a joint account
    rec1 = ClientRecord(
        row_index=1,
        transaction_ref="TXN001",
        account_id="ACC001",
        person_code="12345",
        account_type="JNT",
        id_value="AB123456C",  # Valid UK NINO
        id_type="NIDN",
        first_name="John",
        surname="Smith",
        date_of_birth="1980-05-15",
        gender="M",
        primary_nationality="GB"
    )
    
    rec2 = ClientRecord(
        row_index=2,
        transaction_ref="TXN001",  # Same transaction ref
        account_id="ACC001",
        person_code="67890",
        account_type="JNT",
        id_value="JK987654L",  # Valid UK NINO (no forbidden letters D,F,I,Q,U,V)
        id_type="NIDN",
        first_name="Jane",
        surname="Smith",
        date_of_birth="1982-03-20",
        gender="F",
        primary_nationality="GB"
    )
    
    processor = IDValidationProcessor(verbose=True)
    
    # Process both records individually first
    rec1 = processor.process_record(rec1)
    rec2 = processor.process_record(rec2)
    
    print(f"\nRecord 1 after processing:")
    print(f"  is_valid: {rec1.is_valid}")
    print(f"  correction_output: '{rec1.correction_output}'")
    
    print(f"\nRecord 2 after processing:")
    print(f"  is_valid: {rec2.is_valid}")
    print(f"  correction_output: '{rec2.correction_output}'")
    
    # Now aggregate the JNT pair
    aggregated = processor.aggregate_jnt_accounts([rec1, rec2])
    
    assert len(aggregated) == 1, f"Expected 1 record after aggregation, got {len(aggregated)}"
    
    result = aggregated[0]
    
    print(f"\nAggregated record:")
    print(f"  id_value: {result.id_value}")
    print(f"  id_type: {result.id_type}")
    print(f"  correction_output: '{result.correction_output}'")
    print(f"  correction_fields: '{result.correction_fields}'")
    
    # ASSERTION: correction_output should be EMPTY (not set)
    assert result.correction_output == "", \
        f"Expected no correction for passing JNT pair, but got: {result.correction_output}"
    
    assert result.correction_fields == "", \
        f"Expected no correction_fields for passing JNT pair, but got: {result.correction_fields}"
    
    print("\n✅ PASS: No false positive correction generated")
    return True


def test_jnt_one_fails_has_correction():
    """Test that JNT pair with one failing record HAS correction."""
    print("\n" + "="*70)
    print("TEST 2: JNT Pair - One Fails, One Passes")
    print("="*70)
    
    # Create one valid and one invalid record for a joint account
    rec1 = ClientRecord(
        row_index=1,
        transaction_ref="TXN002",
        account_id="ACC002",
        person_code="12345",
        account_type="JNT",
        id_value="AB123456C",  # Valid UK NINO
        id_type="NIDN",
        first_name="John",
        surname="Smith",
        date_of_birth="1980-05-15",
        gender="M",
        primary_nationality="GB"
    )
    
    rec2 = ClientRecord(
        row_index=2,
        transaction_ref="TXN002",  # Same transaction ref
        account_id="ACC002",
        person_code="67890",
        account_type="JNT",
        id_value="INVALID_ID",  # Invalid ID - should trigger correction
        id_type="NIDN",
        first_name="Jane",
        surname="Smith",
        date_of_birth="1982-03-20",
        gender="F",
        primary_nationality="GB"
    )
    
    processor = IDValidationProcessor(verbose=True)
    
    # Process both records individually first
    rec1 = processor.process_record(rec1)
    rec2 = processor.process_record(rec2)
    
    print(f"\nRecord 1 after processing:")
    print(f"  is_valid: {rec1.is_valid}")
    print(f"  correction_output: '{rec1.correction_output}'")
    
    print(f"\nRecord 2 after processing:")
    print(f"  is_valid: {rec2.is_valid}")
    print(f"  correction_output: '{rec2.correction_output}'")
    
    # Now aggregate the JNT pair
    aggregated = processor.aggregate_jnt_accounts([rec1, rec2])
    
    assert len(aggregated) == 1, f"Expected 1 record after aggregation, got {len(aggregated)}"
    
    result = aggregated[0]
    
    print(f"\nAggregated record:")
    print(f"  id_value: {result.id_value}")
    print(f"  id_type: {result.id_type}")
    print(f"  correction_output: '{result.correction_output}'")
    print(f"  correction_fields: '{result.correction_fields}'")
    
    # ASSERTION: correction_output should be SET (one record had correction)
    assert result.correction_output != "", \
        f"Expected correction for JNT pair with one failed record, but got empty"
    
    # Check that the valid ID and the correction for the invalid ID are both present
    assert "AB123456C" in result.correction_output or "JK987654L" in result.correction_output, \
        f"Expected valid ID in correction, got: {result.correction_output}"
    
    print("\n✅ PASS: Correction properly generated for mixed JNT pair")
    return True


def test_jnt_both_fail_has_correction():
    """Test that JNT pair with both failing records HAS correction."""
    print("\n" + "="*70)
    print("TEST 3: JNT Pair - Both Fail Validation")
    print("="*70)
    
    # Create two invalid records for a joint account
    rec1 = ClientRecord(
        row_index=1,
        transaction_ref="TXN003",
        account_id="ACC003",
        person_code="12345",
        account_type="JNT",
        id_value="INVALID_ID1",
        id_type="NIDN",
        first_name="John",
        surname="Smith",
        date_of_birth="1980-05-15",
        gender="M",
        primary_nationality="GB"
    )
    
    rec2 = ClientRecord(
        row_index=2,
        transaction_ref="TXN003",  # Same transaction ref
        account_id="ACC003",
        person_code="67890",
        account_type="JNT",
        id_value="INVALID_ID2",
        id_type="NIDN",
        first_name="Jane",
        surname="Smith",
        date_of_birth="1982-03-20",
        gender="F",
        primary_nationality="GB"
    )
    
    processor = IDValidationProcessor(verbose=True)
    
    # Process both records individually first
    rec1 = processor.process_record(rec1)
    rec2 = processor.process_record(rec2)
    
    print(f"\nRecord 1 after processing:")
    print(f"  is_valid: {rec1.is_valid}")
    print(f"  correction_output: '{rec1.correction_output}'")
    
    print(f"\nRecord 2 after processing:")
    print(f"  is_valid: {rec2.is_valid}")
    print(f"  correction_output: '{rec2.correction_output}'")
    
    # Now aggregate the JNT pair
    aggregated = processor.aggregate_jnt_accounts([rec1, rec2])
    
    assert len(aggregated) == 1, f"Expected 1 record after aggregation, got {len(aggregated)}"
    
    result = aggregated[0]
    
    print(f"\nAggregated record:")
    print(f"  id_value: {result.id_value}")
    print(f"  id_type: {result.id_type}")
    print(f"  correction_output: '{result.correction_output}'")
    print(f"  correction_fields: '{result.correction_fields}'")
    
    # ASSERTION: correction_output should be SET (both records had corrections)
    assert result.correction_output != "", \
        f"Expected correction for JNT pair with both failed records, but got empty"
    
    assert "|" in result.correction_output, \
        f"Expected pipe-delimited correction for JNT pair, got: {result.correction_output}"
    
    assert ":" in result.correction_output, \
        f"Expected colon-delimited correction for JNT pair, got: {result.correction_output}"
    
    print("\n✅ PASS: Correction properly generated for both failed JNT pair")
    return True


if __name__ == "__main__":
    try:
        # Run all tests
        test_jnt_both_pass_no_correction()
        test_jnt_one_fails_has_correction()
        test_jnt_both_fail_has_correction()
        
        print("\n" + "="*70)
        print("ALL TESTS PASSED ✅")
        print("="*70)
        print("\nThe JNT correction bug has been fixed!")
        print("Joint accounts that pass validation no longer generate false corrections.")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
