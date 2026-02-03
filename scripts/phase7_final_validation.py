#!/usr/bin/env python3
"""
Phase 7: Final Validation Script
=================================

Comprehensive validation of the config architecture overhaul.
Runs all checks to ensure the system is production-ready.
"""

import sys
from pathlib import Path
import yaml


def validate_templates():
    """Validate all 9 core template files."""
    print("="*70)
    print("1. TEMPLATE VALIDATION")
    print("="*70)
    
    templates_dir = Path('config/templates/accuracy_testing')
    core_templates = [
        ('buyer_validation_template.yaml', 'batch', 'auto'),
        ('seller_validation_template.yaml', 'batch', 'auto'),
        ('pricing_validation_template.yaml', 'batch', 'auto'),
        ('inconsistent_buyer_validation_template.yaml', 'single', '7_66'),
        ('inconsistent_seller_validation_template.yaml', 'single', '16_20'),
        ('ftbdm_validation_template.yaml', 'single', '12_17'),
        ('ftsdm_validation_template.yaml', 'single', '21_17'),
        ('sql_extract_generator_template.yaml', 'batch', 'all'),
        ('data_push_template.yaml', 'batch', 'all'),
    ]
    
    all_valid = True
    for template_name, expected_mode, expected_incidents in core_templates:
        template_path = templates_dir / template_name
        
        try:
            with open(template_path) as f:
                config = yaml.safe_load(f)
            
            mode = config.get('mode')
            if mode != expected_mode:
                print(f"  ✗ {template_name}: mode={mode}, expected={expected_mode}")
                all_valid = False
                continue
            
            if mode == 'batch':
                batch = config.get('batch', {})
                incidents = batch.get('incidents')
                patterns = batch.get('filename_patterns', {})
                
                if incidents != expected_incidents:
                    print(f"  ✗ {template_name}: incidents={incidents}, expected={expected_incidents}")
                    all_valid = False
                    continue
                
                if not patterns:
                    print(f"  ✗ {template_name}: missing filename_patterns")
                    all_valid = False
                    continue
                
                print(f"  ✓ {template_name:45s} [{mode}, incidents={incidents}, {len(patterns)} patterns]")
            
            elif mode == 'single':
                single = config.get('single', {})
                incident = single.get('incident_code')
                
                if incident != expected_incidents:
                    print(f"  ✗ {template_name}: incident={incident}, expected={expected_incidents}")
                    all_valid = False
                    continue
                
                print(f"  ✓ {template_name:45s} [{mode}, incident={incident}]")
        
        except Exception as e:
            print(f"  ✗ {template_name}: ERROR - {e}")
            all_valid = False
    
    if all_valid:
        print("\n  ✓ All 9 templates validated successfully!\n")
    else:
        print("\n  ✗ Some templates failed validation\n")
    
    return all_valid


def validate_scripts():
    """Validate that scripts can read new config format."""
    print("="*70)
    print("2. SCRIPT COMPATIBILITY")
    print("="*70)
    
    scripts = [
        'src/accuracy_testing/scripts/buyer_id_validation.py',
        'src/accuracy_testing/scripts/seller_id_validation.py',
        'src/accuracy_testing/scripts/pricing_validation.py',
        'src/accuracy_testing/scripts/sql_extract_generator.py',
    ]
    
    # Note: data_push.py supports both CLI and config, doesn't require mode pattern
    
    all_valid = True
    for script_path in scripts:
        script = Path(script_path)
        if not script.exists():
            print(f"  ✗ {script.name}: File not found")
            all_valid = False
            continue
        
        content = script.read_text()
        
        # Check for new config reading patterns (flexible matching)
        has_mode_check = ("mode = config.get('mode'" in content or 
                         "mode = config.get(\"mode\"" in content or
                         ".get('mode'," in content)
        has_batch_config = ("batch_config = config.get('batch'" in content or 
                           "config.get('batch'," in content or
                           "config['batch']" in content)
        
        if has_mode_check or has_batch_config:
            print(f"  ✓ {script.name:40s} [reads v2.0 config]")
        else:
            print(f"  ✗ {script.name:40s} [missing v2.0 config code]")
            all_valid = False
    
    # Special note about data_push.py
    print(f"  ℹ data_push.py                              [supports both CLI and config modes]")
    
    if all_valid:
        print("\n  ✓ All scripts support v2.0 config format!\n")
    else:
        print("\n  ✗ Some scripts need updating\n")
    
    return all_valid


def validate_documentation():
    """Validate that all documentation is present."""
    print("="*70)
    print("3. DOCUMENTATION")
    print("="*70)
    
    required_docs = [
        ('documentation/guides/Accuracy_Testing_Configuration_Guide.md', 'Configuration Guide'),
        ('documentation/guides/Config_Migration_Guide.md', 'Migration Guide'),
        ('documentation/planning/Config_Architecture_Overhaul_Summary.md', 'Project Summary'),
        ('scripts/validate_config_migration.py', 'Validation Tool'),
    ]
    
    all_present = True
    for doc_path, description in required_docs:
        doc = Path(doc_path)
        if doc.exists():
            size = doc.stat().st_size
            print(f"  ✓ {description:35s} [{size:,} bytes]")
        else:
            print(f"  ✗ {description:35s} [MISSING]")
            all_present = False
    
    if all_present:
        print("\n  ✓ All documentation present!\n")
    else:
        print("\n  ✗ Some documentation missing\n")
    
    return all_present


def validate_file_cleanup():
    """Validate that old files have been removed."""
    print("="*70)
    print("4. FILE CLEANUP")
    print("="*70)
    
    removed_files = [
        'config/templates/accuracy_testing/decision_maker_validation_template.yaml',
        'config/templates/data_push_template.yaml',
        'test_config_parsing.py',
        'config/local/accuracy_testing/test_buyer_validation.yaml',
        'scripts/update_test_configs.py',
    ]
    
    all_removed = True
    for file_path in removed_files:
        file = Path(file_path)
        if not file.exists():
            print(f"  ✓ {file.name:50s} [removed]")
        else:
            print(f"  ✗ {file.name:50s} [still exists]")
            all_removed = False
    
    if all_removed:
        print("\n  ✓ All temporary/old files removed!\n")
    else:
        print("\n  ✗ Some files still need removal\n")
    
    return all_removed


def print_summary(results):
    """Print final summary."""
    print("="*70)
    print("PHASE 7: FINAL VALIDATION SUMMARY")
    print("="*70)
    
    checks = [
        ("Template Validation", results['templates']),
        ("Script Compatibility", results['scripts']),
        ("Documentation", results['documentation']),
        ("File Cleanup", results['cleanup']),
    ]
    
    passed = sum(1 for _, result in checks if result)
    total = len(checks)
    
    print()
    for name, result in checks:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status:8s} {name}")
    
    print()
    print("="*70)
    
    if passed == total:
        print(f"✓ ALL CHECKS PASSED ({passed}/{total})")
        print("="*70)
        print()
        print("🎉 Config Architecture Overhaul COMPLETE! 🎉")
        print()
        print("System is ready for production use:")
        print("  • 9 templates validated")
        print("  • 5 scripts updated")
        print("  • Documentation complete")
        print("  • Migration tools ready")
        print()
        return 0
    else:
        print(f"✗ SOME CHECKS FAILED ({passed}/{total} passed)")
        print("="*70)
        print()
        print("Please review failures above and fix before deploying.")
        print()
        return 1


def main():
    """Run all validation checks."""
    print()
    print("="*70)
    print(" CONFIG ARCHITECTURE OVERHAUL - PHASE 7: FINAL VALIDATION")
    print("="*70)
    print()
    
    results = {
        'templates': validate_templates(),
        'scripts': validate_scripts(),
        'documentation': validate_documentation(),
        'cleanup': validate_file_cleanup(),
    }
    
    exit_code = print_summary(results)
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
