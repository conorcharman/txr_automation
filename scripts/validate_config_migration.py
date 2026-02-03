#!/usr/bin/env python3
"""
Config Migration Validator
==========================

Validates accuracy testing config files to check if they're using the new v2.0 format
or need migration from the old format.

Usage:
    python scripts/validate_config_migration.py <config_file>
    python scripts/validate_config_migration.py config/local/accuracy_testing/*.yaml
    python scripts/validate_config_migration.py --scan config/local/accuracy_testing/

Version 2.0 Format Requirements:
- Explicit 'mode' field at top level
- Configuration nested under 'batch' or 'single' key
- 'filename_patterns' section for batch mode
- No commented-out mode selection
- 'incidents' field (not 'auto_incidents')
"""

import argparse
import sys
from pathlib import Path
from typing import List, Tuple
import yaml


class ConfigValidator:
    """Validates config files for v2.0 format."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.issues = []
    
    def validate_file(self, config_path: Path) -> Tuple[bool, List[str]]:
        """
        Validate a config file.
        
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        self.issues = []
        
        if not config_path.exists():
            self.issues.append(f"File not found: {config_path}")
            return False, self.issues
        
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
        except Exception as e:
            self.issues.append(f"YAML parse error: {e}")
            return False, self.issues
        
        if config is None:
            self.issues.append("Empty config file")
            return False, self.issues
        
        # Check for v2.0 format
        is_valid = self._check_v2_format(config)
        
        return is_valid, self.issues
    
    def _check_v2_format(self, config: dict) -> bool:
        """Check if config uses v2.0 format."""
        all_valid = True
        
        # 1. Check for explicit 'mode' field
        if 'mode' not in config:
            self.issues.append("❌ Missing 'mode' field (required in v2.0)")
            self.issues.append("   Add: mode: \"batch\" or mode: \"single\"")
            all_valid = False
        else:
            mode = config['mode']
            if mode not in ['batch', 'single']:
                self.issues.append(f"❌ Invalid mode: '{mode}' (must be 'batch' or 'single')")
                all_valid = False
            else:
                if self.verbose:
                    self.issues.append(f"✓ Mode: {mode}")
        
        # 2. Check configuration nesting
        mode = config.get('mode')
        if mode == 'batch':
            if 'batch' not in config:
                self.issues.append("❌ Mode is 'batch' but no 'batch:' section found")
                self.issues.append("   Nest configuration under 'batch:' key")
                all_valid = False
            else:
                batch_config = config['batch']
                
                # Check incidents field
                if 'incidents' not in batch_config:
                    self.issues.append("❌ Missing 'batch.incidents' field")
                    self.issues.append("   Add: incidents: \"auto\" or explicit list")
                    all_valid = False
                else:
                    incidents = batch_config['incidents']
                    if self.verbose:
                        self.issues.append(f"✓ Incidents: {incidents}")
                
                # Check filename_patterns
                if 'filename_patterns' not in batch_config:
                    self.issues.append("⚠️  Warning: No 'batch.filename_patterns' section")
                    self.issues.append("   Consider adding filename patterns for clarity")
                else:
                    patterns = batch_config['filename_patterns']
                    if self.verbose:
                        self.issues.append(f"✓ Filename patterns: {list(patterns.keys())}")
        
        elif mode == 'single':
            if 'single' not in config:
                self.issues.append("❌ Mode is 'single' but no 'single:' section found")
                self.issues.append("   Nest configuration under 'single:' key")
                all_valid = False
            else:
                single_config = config['single']
                
                # Check incident_code field
                if 'incident_code' not in single_config:
                    self.issues.append("❌ Missing 'single.incident_code' field")
                    all_valid = False
                else:
                    if self.verbose:
                        self.issues.append(f"✓ Incident code: {single_config['incident_code']}")
        
        # 3. Check for deprecated fields at top level
        # Note: testing_period at top level is allowed (shared between modes)
        deprecated_top_level = ['incidents', 'auto_incidents', 'paths']
        for field in deprecated_top_level:
            if field in config and field not in ['mode', 'testing_period']:
                self.issues.append(f"⚠️  Warning: '{field}' at top level (should be under 'batch' or 'single')")
        
        # 4. Check for deprecated 'auto_incidents' field
        if mode == 'batch' and 'batch' in config:
            if 'auto_incidents' in config['batch']:
                self.issues.append("⚠️  Warning: 'auto_incidents' is deprecated")
                self.issues.append("   Use 'incidents: \"auto\"' or 'incidents: \"all\"' instead")
        
        return all_valid
    
    def suggest_migration(self, config_path: Path):
        """Suggest migration steps for an old config."""
        print(f"\n{'='*60}")
        print("Migration Suggestions")
        print('='*60)
        print("\n1. Add explicit mode field at top level:")
        print("   mode: \"batch\"  # or \"single\"")
        print("\n2. Nest configuration under mode key:")
        print("   batch:")
        print("     incidents: \"auto\"")
        print("     testing_period:")
        print("       fiscal_year: \"2025\"")
        print("       quarter: \"Q1\"")
        print("     # ... rest of config")
        print("\n3. Add filename_patterns section (for batch mode):")
        print("   batch:")
        print("     filename_patterns:")
        print("       extract: \"{incident}_{fiscal_year}_{quarter}.csv\"")
        print("       template: \"template_FY{fiscal_year}_Q{quarter}_7_{incident}.csv\"")
        print("       output: \"validated_FY{fiscal_year}_Q{quarter}_{incident}.csv\"")
        print("\n4. Update 'auto_incidents' to 'incidents':")
        print("   OLD: auto_incidents: \"all\"")
        print("   NEW: incidents: \"all\"")
        print("\n5. See documentation/guides/Config_Migration_Guide.md for details")
        print('='*60)


def validate_single_file(validator: ConfigValidator, config_path: Path) -> bool:
    """Validate a single config file and print results."""
    print(f"\nValidating: {config_path}")
    print('-' * 60)
    
    is_valid, issues = validator.validate_file(config_path)
    
    if not issues:
        print("✓ Config is valid v2.0 format!")
        return True
    
    for issue in issues:
        print(issue)
    
    if not is_valid:
        print("\n❌ Config needs migration to v2.0 format")
        if not validator.verbose:
            validator.suggest_migration(config_path)
        return False
    else:
        print("\n⚠️  Config is valid but has warnings")
        return True


def scan_directory(validator: ConfigValidator, directory: Path) -> Tuple[int, int, int]:
    """
    Scan directory for config files.
    
    Returns:
        Tuple of (valid_count, invalid_count, total_count)
    """
    yaml_files = list(directory.glob("*.yaml")) + list(directory.glob("*.yml"))
    
    if not yaml_files:
        print(f"No YAML files found in {directory}")
        return 0, 0, 0
    
    valid_count = 0
    invalid_count = 0
    
    for config_file in yaml_files:
        is_valid = validate_single_file(validator, config_file)
        if is_valid:
            valid_count += 1
        else:
            invalid_count += 1
    
    return valid_count, invalid_count, len(yaml_files)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate accuracy testing config files for v2.0 format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate a single config
  python scripts/validate_config_migration.py config/local/accuracy_testing/buyer.yaml
  
  # Validate multiple configs
  python scripts/validate_config_migration.py config/local/accuracy_testing/*.yaml
  
  # Scan directory
  python scripts/validate_config_migration.py --scan config/local/accuracy_testing/
  
  # Verbose output
  python scripts/validate_config_migration.py --verbose config/local/accuracy_testing/buyer.yaml
        """
    )
    
    parser.add_argument(
        'configs',
        nargs='*',
        type=Path,
        help='Config file(s) to validate'
    )
    
    parser.add_argument(
        '--scan',
        type=Path,
        help='Scan directory for YAML files'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show verbose output including valid checks'
    )
    
    args = parser.parse_args()
    
    if not args.configs and not args.scan:
        parser.print_help()
        sys.exit(1)
    
    validator = ConfigValidator(verbose=args.verbose)
    
    all_valid = True
    
    # Scan directory if requested
    if args.scan:
        print(f"\nScanning directory: {args.scan}")
        print('='*60)
        valid, invalid, total = scan_directory(validator, args.scan)
        
        print(f"\n{'='*60}")
        print("Scan Summary")
        print('='*60)
        print(f"Total configs: {total}")
        print(f"Valid v2.0:    {valid}")
        print(f"Need migration: {invalid}")
        
        if invalid > 0:
            all_valid = False
    
    # Validate individual files
    if args.configs:
        for config_path in args.configs:
            is_valid = validate_single_file(validator, config_path)
            if not is_valid:
                all_valid = False
    
    # Exit with appropriate code
    if all_valid:
        print("\n✓ All configs validated successfully!")
        sys.exit(0)
    else:
        print("\n❌ Some configs need migration")
        print("See documentation/guides/Config_Migration_Guide.md for help")
        sys.exit(1)


if __name__ == '__main__':
    main()
