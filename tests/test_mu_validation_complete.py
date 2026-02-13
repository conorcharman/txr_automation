"""
Test complete validation flow for MU CONCAT including validate_with_details.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.data.id_formats import id_format_manager
from core import country_manager

def test_mu_concat_validation():
    """Test MU CONCAT validation through the complete flow."""
    
    print("=" * 80)
    print("Testing Complete MU CONCAT Validation Flow")
    print("=" * 80)
    
    test_id = "MU19900720SHABNIBRAH"
    country_code = "MU"
    id_type = "CONCAT"
    
    print(f"\nTest Data:")
    print(f"  ID Value:    {test_id}")
    print(f"  Country:     {country_code}")
    print(f"  ID Type:     {id_type}")
    print()
    
    # Verify country exists
    country = country_manager.get_by_alpha2(country_code)
    print(f"Country Check:")
    print(f"  Valid:       {country is not None}")
    if country:
        print(f"  Name:        {country.name}")
        print(f"  Is EEA:      {country.is_eea}")
    print()
    
    # Test the basic validate method
    print("Step 1: Testing id_format_manager.validate()")
    is_valid_basic = id_format_manager.validate(country_code, id_type, test_id)
    print(f"  Result:      {is_valid_basic}")
    print(f"  Status:      {'✓ PASS' if is_valid_basic else '✗ FAIL'}")
    print()
    
    # Test the validate_with_details method (this is what was failing)
    print("Step 2: Testing id_format_manager.validate_with_details()")
    is_valid, error_message = id_format_manager.validate_with_details(country_code, id_type, test_id)
    print(f"  Valid:       {is_valid}")
    print(f"  Error:       {error_message if error_message else 'None'}")
    print(f"  Status:      {'✓ PASS' if is_valid and not error_message else '✗ FAIL'}")
    print()
    
    # Test other rest-of-world examples
    print("=" * 80)
    print("Testing Other Rest-of-World CONCATs")
    print("=" * 80)
    
    test_cases = [
        ("MU19900720SHABNIBRAH", "MU", "Mauritius"),
        ("BD19970130SHABIHOSSA", "BD", "Bangladesh"),
        ("US19920722SMITHJOHNS", "US", "United States"),
        ("JP19850615TANAKAYAMAS", "JP", "Japan (19 chars - should fail)"),
        ("XX19900720SHABNIBRAH", "XX", "Invalid country code"),
    ]
    
    print()
    for test_id, cc, description in test_cases:
        is_valid, error = id_format_manager.validate_with_details(cc, "CONCAT", test_id)
        status = "✓ PASS" if is_valid else "✗ FAIL"
        print(f"{status} | {test_id:20} | {description:30} | {error if error else 'Valid'}")
    
    print()
    print("=" * 80)

if __name__ == "__main__":
    test_mu_concat_validation()
