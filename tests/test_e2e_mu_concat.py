"""
End-to-end test of MU CONCAT processing including auto-detection and validation.
"""

import sys
from pathlib import Path
import csv
import tempfile

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from accuracy_testing.processor import IDValidationProcessor, ClientRecord

def test_e2e_mu_concat():
    """Test complete end-to-end processing of MU CONCAT records."""
    
    print("=" * 80)
    print("End-to-End MU CONCAT Processing Test")
    print("=" * 80)
    print()
    
    # Create test records from user's CSV
    test_records = [
        {
            "transaction_ref": "44625CH6XLW1",
            "account_id": "ADDBMBI",
            "person_code": "ADDBMB",
            "account_type": "",
            "id_value": "MU19900720SHABNIBRAH",
            "id_type": "",  # Empty - should be auto-detected
            "first_name": "SHABNEEZ,BIBI",
            "surname": "IBRAHIM",
            "date_of_birth": "20/07/1990",
            "gender": "F",
            "primary_nationality": "MU",
            "row_index": 1
        },
        {
            "transaction_ref": "44625CH6W1P1",
            "account_id": "ADDBMBI",
            "person_code": "ADDBMB",
            "account_type": "",
            "id_value": "MU19900720SHABNIBRAH",
            "id_type": "",  # Empty - should be auto-detected
            "first_name": "SHABNEEZ,BIBI",
            "surname": "IBRAHIM",
            "date_of_birth": "20/07/1990",
            "gender": "F",
            "primary_nationality": "MU",
            "row_index": 2
        },
    ]
    
    # Create processor
    processor = IDValidationProcessor(client_type="buyer", verbose=True)
    
    # Process each record
    for i, rec_data in enumerate(test_records, 1):
        print(f"Test Case {i}: {rec_data['transaction_ref']}")
        print("─" * 80)
        
        # Create ClientRecord
        record = ClientRecord(
            row_index=rec_data["row_index"],
            transaction_ref=rec_data["transaction_ref"],
            account_id=rec_data["account_id"],
            person_code=rec_data["person_code"],
            account_type=rec_data["account_type"],
            id_value=rec_data["id_value"],
            id_type=rec_data["id_type"],
            first_name=rec_data["first_name"],
            surname=rec_data["surname"],
            date_of_birth=rec_data["date_of_birth"],
            gender=rec_data["gender"],
            primary_nationality=rec_data["primary_nationality"]
        )
        
        print(f"Input:")
        print(f"  ID Value:             {record.id_value}")
        print(f"  ID Type (before):     '{record.id_type}' (empty={not record.id_type})")
        print(f"  Prefixed Nationality: '{record.prefixed_nationality}'")
        print(f"  Primary Nationality:  {record.primary_nationality}")
        print()
        
        # Process record
        result = processor.process_record(record)
        
        print(f"After Processing:")
        print(f"  ID Type (after):      {result.id_type}")
        print(f"  Prefixed Nationality: {result.prefixed_nationality}")
        print(f"  Validation Error:     {result.validation_error if result.validation_error else 'None'}")
        print(f"  Correction:           {result.correction if result.correction else 'None'}")
        print(f"  Is Valid:             {result.is_valid}")
        print()
        
        # Check results
        if result.id_type == "CONCAT":
            print(f"  ✓ ID Type correctly detected as CONCAT")
        else:
            print(f"  ✗ ID Type NOT detected as CONCAT (got: {result.id_type})")
        
        if result.prefixed_nationality == "MU":
            print(f"  ✓ Prefixed Nationality correctly set to MU")
        else:
            print(f"  ✗ Prefixed Nationality NOT set to MU (got: {result.prefixed_nationality})")
        
        if not result.correction:
            print(f"  ✓ No correction generated (ID already valid)")
        else:
            print(f"  ✗ Correction generated (shouldn't be): {result.correction}")
        
        if result.is_valid:
            print(f"  ✓ Record marked as valid")
        else:
            print(f"  ✗ Record NOT marked as valid")
        
        if result.actions_taken:
            print(f"\n  Actions Taken:")
            for action in result.actions_taken:
                print(f"    - {action}")
        
        print()
    
    print("=" * 80)
    print("Summary:")
    print("  Both records should:")
    print("    1. Auto-detect ID Type as CONCAT")
    print("    2. Set prefixed_nationality to MU")
    print("    3. Not generate any correction (already valid)")
    print("    4. Be marked as is_valid=True")
    print("=" * 80)

if __name__ == "__main__":
    test_e2e_mu_concat()
