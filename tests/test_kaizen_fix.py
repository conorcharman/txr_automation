#!/usr/bin/env python3
"""
Demonstrate Kaizen Lookup Fix for Inconsistent ID Preprocessing
================================================================

Shows that Kaizen template validation now works correctly for records
that are corrected during inconsistent ID preprocessing.
"""

import sys
from pathlib import Path

# Ensure proper path setup
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Change to project root to ensure imports work
import os

os.chdir(project_root)

from datetime import datetime

from src.accuracy_testing.processor import ClientRecord, IDValidationProcessor


def demonstrate_fix():
    """Demonstrate that Kaizen validation works for preprocessed records."""

    print("=" * 70)
    print("DEMONSTRATING KAIZEN LOOKUP FIX")
    print("=" * 70)

    # Create a test record that would have been corrected by preprocessing
    record = ClientRecord(
        row_index=1,
        transaction_ref="TXN001",
        account_id="ACC001",
        person_code="12345",
        account_type="IND",
        id_value="GBNZ283821B",  # Original (valid but not most recent)
        id_type="NIDN",
        first_name="John",
        surname="Smith",
        date_of_birth="1982-08-28",
        gender="M",
        primary_nationality="GB",
        secondary_nationality="",
        trade_date_time_raw="2024-01-01-10-00-00-000000",
        prefixed_nationality="GB",
    )

    # Simulate what inconsistent ID preprocessing does:
    # It corrects the ID to the most recent valid one
    record.correction = "GBNZ283821A"
    record.correction_type = "NIDN"
    record.correction_output = "GBNZ283821A:NIDN"
    record.requires_standard_validation = False

    print("\n1. RECORD AFTER INCONSISTENT ID PREPROCESSING:")
    print(f"   Original ID: {record.id_value}")
    print(f"   Corrected to: {record.correction}")
    print(f"   correction_output: {record.correction_output}")
    print(f"   requires_standard_validation: {record.requires_standard_validation}")

    # Create processor with mock template data
    processor = IDValidationProcessor(client_type="buyer", verbose=False)
    processor.template_data = {
        "TXN001": {"id": "GBNZ283821A", "type": "NIDN"},
    }

    print("\n2. TEMPLATE DATA:")
    print(f"   TXN001 -> GBNZ283821A:NIDN")

    # Now perform Kaizen validation (this is what the fix adds)
    print("\n3. PERFORMING KAIZEN VALIDATION...")
    processor._perform_template_validation(record)

    print("\n4. RESULTS AFTER KAIZEN VALIDATION:")
    print(f"   kaizen_error: '{record.kaizen_error}'")
    print(f"   match: '{record.match}'")
    print(f"   error: '{record.error}'")

    # Verify the fix worked
    if record.kaizen_error == "GBNZ283821A:NIDN":
        print("\n✅ SUCCESS: Template lookup populated!")
    else:
        print(
            f"\n❌ FAILED: kaizen_error should be 'GBNZ283821A:NIDN', got '{record.kaizen_error}'"
        )
        return False

    if record.match == "TRUE":
        print("✅ SUCCESS: Correction matches template!")
    else:
        print(f"❌ FAILED: match should be 'TRUE', got '{record.match}'")
        return False

    if record.error == "N":
        print("✅ SUCCESS: No error flag!")
    else:
        print(f"❌ FAILED: error should be 'N', got '{record.error}'")
        return False

    print("\n" + "=" * 70)
    print("🎉 KAIZEN LOOKUP FIX VERIFIED - ALL CHECKS PASSED!")
    print("=" * 70)

    print("\nEXPLANATION:")
    print("- Before fix: Records corrected in preprocessing skipped Kaizen validation")
    print("- After fix: All preprocessed records now get Kaizen validation in Phase 3")
    print("- This ensures template matching works correctly for all records")

    return True


if __name__ == "__main__":
    try:
        success = demonstrate_fix()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
