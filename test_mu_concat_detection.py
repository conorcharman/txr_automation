"""
Test script to verify MU CONCAT detection with the enhanced logic.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from accuracy_testing.processor import is_valid_concat_format, extract_id_prefix
from core import country_manager

def test_mu_concat():
    """Test MU CONCAT detection from user's CSV."""
    
    # Test data from user's CSV
    id_value = "MU19900720SHABNIBRAH"
    
    print("=" * 60)
    print("Testing MU CONCAT Detection")
    print("=" * 60)
    print(f"ID Value: {id_value}")
    print()
    
    # Step 1: Extract prefix
    prefix = extract_id_prefix(id_value, "CONCAT")
    print(f"Step 1 - Extract prefix: {prefix}")
    
    # Step 2: Validate country code
    is_valid_country = country_manager.validate_code(prefix) if prefix else False
    country = country_manager.get_by_alpha2(prefix) if prefix else None
    print(f"Step 2 - Valid country code: {is_valid_country}")
    if country:
        print(f"         Country: {country.name} ({country.alpha2})")
        print(f"         Is EEA: {country.is_eea}")
    
    # Step 3: Check generic CONCAT format
    is_valid = is_valid_concat_format(id_value)
    print(f"Step 3 - Matches CONCAT format: {is_valid}")
    print()
    
    # Test other rest-of-world examples
    print("=" * 60)
    print("Testing Other Rest-of-World CONCATs")
    print("=" * 60)
    
    test_cases = [
        ("BD19970130SHABIHOSSA", "Bangladesh"),
        ("JP19850615TANAKAYAMAS", "Japan"),
        ("US19920722SMITHJOHNS", "United States"),
        ("XX19900720SHABNIBRAH", "Invalid country code"),
        ("MU1990072SHABNIBRAH", "Wrong length (19 chars)"),
    ]
    
    for test_id, description in test_cases:
        prefix = extract_id_prefix(test_id, "CONCAT")
        is_valid = is_valid_concat_format(test_id)
        status = "✓ PASS" if is_valid else "✗ FAIL"
        print(f"{status} | {test_id} | {description}")
    
    print()
    print("=" * 60)

if __name__ == "__main__":
    test_mu_concat()
