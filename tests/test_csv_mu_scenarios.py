"""
Test the actual MU CONCAT case from user's CSV to verify fix.
"""

import sys
from pathlib import Path
from dataclasses import dataclass

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from accuracy_testing.processor import (
    ClientRecord, 
    IDValidationProcessor,
    is_valid_concat_format,
    extract_id_prefix
)
from core import create_logger

@dataclass
class CsvScenarioCase:
    transaction_ref: str
    id_value: str
    id_type: str
    nationality: str
    expected_result: str

def test_csv_scenarios():
    """Test the three scenarios from user's CSV."""
    
    test_cases = [
        CsvScenarioCase(
            transaction_ref="44625CH6XLW1",
            id_value="MU19900720SHABNIBRAH",
            id_type="",  # Empty - should be auto-detected
            nationality="MU",
            expected_result="Should detect as CONCAT with prefixed_nationality=MU"
        ),
        CsvScenarioCase(
            transaction_ref="44625CH6W1P1",
            id_value="MU19900720SHABNIBRAH",
            id_type="",  # Empty - should be auto-detected
            nationality="MU",
            expected_result="Should detect as CONCAT with prefixed_nationality=MU"
        ),
        CsvScenarioCase(
            transaction_ref="44625CKBJ1Q1",
            id_value="MU2055321",
            id_type="CCPT",  # Already has type
            nationality="MU",
            expected_result="Should keep as CCPT (already has type)"
        ),
    ]
    
    print("=" * 80)
    print("Testing User's CSV Scenarios - MU CONCAT Detection")
    print("=" * 80)
    
    for i, test in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test.transaction_ref}")
        print(f"{'─' * 80}")
        print(f"ID Value:    {test.id_value}")
        print(f"ID Type:     '{test.id_type}' (empty={not test.id_type})")
        print(f"Nationality: {test.nationality}")
        print()
        
        # Step 1: Check if it's a valid CONCAT format
        if not test.id_type:  # Only check if ID type is empty
            is_concat = is_valid_concat_format(test.id_value)
            prefix = extract_id_prefix(test.id_value, "CONCAT")
            
            print(f"Analysis:")
            print(f"  - Prefix extracted: {prefix}")
            print(f"  - Valid CONCAT format: {is_concat}")
            
            if is_concat and prefix:
                print(f"  ✓ RESULT: Would be detected as CONCAT with prefix={prefix}")
                print(f"  ✓ prefixed_nationality would be set to: {prefix}")
                print(f"  ✓ No correction needed (ID is already valid CONCAT)")
            else:
                print(f"  ✗ RESULT: Would NOT be detected as CONCAT")
                print(f"  ✗ Would generate correction (incorrectly)")
        else:
            print(f"Analysis:")
            print(f"  - ID type already set to: {test.id_type}")
            print(f"  - No auto-detection needed")
        
        print(f"\nExpected: {test.expected_result}")
    
    print()
    print("=" * 80)

if __name__ == "__main__":
    test_csv_scenarios()
