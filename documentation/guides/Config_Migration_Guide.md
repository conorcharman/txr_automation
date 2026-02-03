# Configuration Migration Guide

**Version:** 1.0  
**Date:** 3 February 2026  
**Purpose:** Migrate existing config files to new mode-based architecture

---

## Overview

This guide provides step-by-step instructions for migrating existing accuracy testing configuration files to the new v2.0 format.

**Key Changes in v2.0:**
- Explicit `mode` field (no inferred mode)
- Configuration nested under `batch:` or `single:` keys
- Configurable `filename_patterns` with format strings
- Consistent structure across all scripts
- Auto-discovery for standard incidents

---

## Quick Migration Checklist

- [ ] Add `mode` field at top level
- [ ] Nest configuration under `batch:` or `single:`
- [ ] Add `filename_patterns` section
- [ ] Update `incidents` field (use `"auto"` or explicit list)
- [ ] Remove commented-out code
- [ ] Remove deprecated fields
- [ ] Test config with validation script
- [ ] Update script invocation (if needed)

---

## Migration by Script Type

### Buyer ID Validation

**Old Config (Pre-v2.0):**
```yaml
# Mode inferred from presence of these fields
incidents: ["7_37", "7_39"]
testing_period:
  fiscal_year: "2025"
  quarter: "Q1"

paths:
  extract_dir: "/data/extracts"
  template_dir: "/data/templates"
  output_dir: "/data/outputs"

# Filename patterns hardcoded in script:
# extract: {incident}_{fiscal_year}_{quarter}.csv
# template: template_FY{fiscal_year}_Q{quarter}_7_{incident}.csv
# output: validated_FY{fiscal_year}_Q{quarter}_{incident}.csv
```

**New Config (v2.0):**
```yaml
mode: "batch"

batch:
  incidents: ["7_37", "7_39"]  # Or use "auto" for [7_35, 7_37, 7_39]
  
  testing_period:
    fiscal_year: "2025"
    quarter: "Q1"
  
  paths:
    extract_dir: "/data/extracts"
    template_dir: "/data/templates"
    output_dir: "/data/outputs"
  
  filename_patterns:
    extract: "{incident}_{fiscal_year}_{quarter}.csv"
    template: "template_FY{fiscal_year}_Q{quarter}_7_{incident}.csv"
    output: "validated_FY{fiscal_year}_Q{quarter}_{incident}.csv"
```

**Changes:**
1. Added `mode: "batch"`
2. Nested everything under `batch:`
3. Added `filename_patterns` section with previous hardcoded patterns
4. Can now use `incidents: "auto"` for standard discovery

---

### Seller ID Validation

**Old Config:**
```yaml
incidents: ["16_19", "16_21", "16_23"]
testing_period:
  fiscal_year: "2025"
  quarter: "Q1"

paths:
  extract_dir: "/data/extracts"
  template_dir: "/data/templates"
  output_dir: "/data/outputs"
```

**New Config:**
```yaml
mode: "batch"

batch:
  incidents: "auto"  # Discovers 16_19, 16_21, 16_23
  
  testing_period:
    fiscal_year: "2025"
    quarter: "Q1"
  
  paths:
    extract_dir: "/data/extracts"
    template_dir: "/data/templates"
    output_dir: "/data/outputs"
  
  filename_patterns:
    extract: "{incident}_{fiscal_year}_{quarter}.csv"
    template: "template_FY{fiscal_year}_Q{quarter}_16_{incident}.csv"
    output: "validated_FY{fiscal_year}_Q{quarter}_{incident}.csv"
```

**Changes:**
1. Added `mode: "batch"`
2. Used `incidents: "auto"` for standard seller incidents
3. Nested under `batch:`
4. Added `filename_patterns` with seller-specific template pattern

---

### Pricing Validation

**Old Config:**
```yaml
incidents: ["35_3"]
testing_period:
  fiscal_year: "2025"
  quarter: "Q1"

paths:
  template_dir: "/data/templates"
  output_dir: "/data/outputs"
```

**New Config:**
```yaml
mode: "batch"

batch:
  incidents: "auto"  # Discovers 35_3
  
  testing_period:
    fiscal_year: "2025"
    quarter: "Q1"
  
  paths:
    template_dir: "/data/templates"
    output_dir: "/data/outputs"
  
  filename_patterns:
    template: "template_FY{fiscal_year}_Q{quarter}_35_3.csv"
    output: "validated_FY{fiscal_year}_Q{quarter}_{incident}.csv"
```

**Changes:**
1. Added `mode: "batch"`
2. Used `incidents: "auto"`
3. Added `filename_patterns` (note: no extract pattern for pricing)

---

### Inconsistent Buyer ID Validation

**Old Config:**
```yaml
incident_code: "7_66"

paths:
  extract_file: "/data/extracts/7_66_data.csv"
  template_file: "/data/templates/template_7_66.csv"
  output_file: "/data/outputs/validated_7_66.csv"
```

**New Config:**
```yaml
mode: "single"

single:
  incident_code: "7_66"
  
  paths:
    extract_file: "/data/extracts/7_66_data.csv"
    template_file: "/data/templates/template_7_66.csv"
    output_file: "/data/outputs/validated_7_66.csv"
```

**Changes:**
1. Added `mode: "single"`
2. Nested under `single:`
3. Structure otherwise unchanged (single mode uses explicit paths)

---

### SQL Extract Generator

**Old Config:**
```yaml
# incidents: all  # Commented out
auto_incidents: "all"  # Deprecated field

testing_period:
  fiscal_year: "2025"
  quarter: "Q1"

paths:
  validated_dir: "/data/validated"
  output_dir: "/data/extracts"

sql_template_mapping:
  7_37: "ExtractInconsistentBuyerID.sql"
  7_39: "ExtractBuyerID.sql"
```

**New Config:**
```yaml
mode: "batch"

batch:
  incidents: "all"  # All 11 automated incidents
  
  testing_period:
    fiscal_year: "2025"
    quarter: "Q1"
  
  paths:
    validated_dir: "/data/validated"
    output_dir: "/data/extracts"
  
  filename_patterns:
    validated: "validated_FY{fiscal_year}_Q{quarter}_{incident}.csv"
    output_sql: "SQL_{incident}.sql"
    output_sql_batch: "SQL_Batch_{incident}.sql"
    output_dtf: "dtf_{incident}.txt"
    output_dtf_batch: "dtf_Batch_{incident}.txt"
    output_csv: "{incident}.csv"
    output_csv_batch: "Batch_{incident}.csv"
  
  sql_template_mapping:
    7_35: "ExtractBuyerID.sql"
    7_37: "ExtractInconsistentBuyerID.sql"
    7_39: "ExtractBuyerID.sql"
    7_66: "ExtractInconsistentBuyerID.sql"
    12_17: "ExtractDecisionMaker.sql"
    16_19: "ExtractSellerID.sql"
    16_21: "ExtractInconsistentSellerID.sql"
    16_23: "ExtractSellerID.sql"
    16_20: "ExtractInconsistentSellerID.sql"
    21_17: "ExtractDecisionMaker.sql"
    35_3: "ExtractPricing.sql"
```

**Changes:**
1. Added `mode: "batch"`
2. Changed `auto_incidents: "all"` to `incidents: "all"`
3. Added comprehensive `filename_patterns` (6 output types)
4. Expanded `sql_template_mapping` for all 11 incidents
5. Removed commented code

---

### Data Push

**Old Config:**
```yaml
# This script didn't have YAML config before
# Used CLI flags only
```

**New Config:**
```yaml
mode: "batch"

batch:
  incidents: "all"  # All 11 incidents
  
  testing_period:
    fiscal_year: "2025"
    quarter: "Q1"
  
  paths:
    source_dir: "/data/validated"
    target_dir: "/data/templates"
    backup_dir: "/data/backups"
  
  filename_patterns:
    source: "validated_FY{fiscal_year}_Q{quarter}_{incident}.csv"
    target: "template_FY{fiscal_year}_Q{quarter}_{incident}.csv"
  
  push_logic:
    match_column: "Transaction_Reference"
    error_flag_column: "Error"
    
    rules:
      error_Y:
        description: "Push all columns when Error = Y"
        columns: "all"
      
      error_N:
        description: "Push Error column only when Error = N"
        columns: ["Error"]
      
      error_TBC:
        description: "Skip records when Error = TBC"
        action: "skip"
```

**Changes:**
1. Created full YAML config (previously CLI-only)
2. Used `mode: "batch"` with `incidents: "all"`
3. Added `filename_patterns` for source/target files
4. Added `push_logic` section with error handling rules

---

## Common Migration Patterns

### Pattern 1: Batch Mode with Auto-Discovery

**Before:**
```yaml
incidents: ["7_37", "7_39"]
# ... rest of config
```

**After:**
```yaml
mode: "batch"
batch:
  incidents: "auto"  # Auto-discovers standard incidents
  # ... rest of config nested under batch:
```

### Pattern 2: Custom Incident List

**Before:**
```yaml
incidents: ["7_37", "16_19"]
```

**After:**
```yaml
mode: "batch"
batch:
  incidents: ["7_37", "16_19"]
```

### Pattern 3: Single Mode (No Change Needed)

**Before:**
```yaml
incident_code: "7_66"
paths:
  extract_file: "..."
```

**After:**
```yaml
mode: "single"
single:
  incident_code: "7_66"
  paths:
    extract_file: "..."
```

### Pattern 4: Adding Filename Patterns

**Default patterns for validation scripts:**
```yaml
filename_patterns:
  extract: "{incident}_{fiscal_year}_{quarter}.csv"
  template: "template_FY{fiscal_year}_Q{quarter}_[FAMILY]_{incident}.csv"
  output: "validated_FY{fiscal_year}_Q{quarter}_{incident}.csv"
```

Replace `[FAMILY]` with:
- `7` for buyer validation
- `16` for seller validation
- Direct incident code for pricing (35_3)

---

## Step-by-Step Migration Process

### Step 1: Backup Existing Config

```bash
cp config/local/accuracy_testing/my_config.yaml \
   config/local/accuracy_testing/my_config.yaml.backup
```

### Step 2: Determine Mode

**Use batch mode if:**
- Processing multiple incidents
- Using `incidents` list or `auto_incidents`
- Want to use filename patterns

**Use single mode if:**
- Processing one incident at a time
- Need explicit control over file paths
- Doing ad-hoc validation

### Step 3: Add Mode Field

At the top of the config:
```yaml
mode: "batch"  # or "single"
```

### Step 4: Nest Configuration

**For batch mode:** Indent everything under `batch:`

**For single mode:** Indent everything under `single:`

### Step 5: Update Incidents Field

**For batch mode:**
```yaml
batch:
  incidents: "auto"  # Standard incident discovery
  # OR
  incidents: ["7_37", "7_39"]  # Explicit list
  # OR
  incidents: "all"  # SQL generator / data push only
```

**For single mode:**
```yaml
single:
  incident_code: "7_66"  # No change needed
```

### Step 6: Add Filename Patterns

Copy patterns from appropriate template file in `config/templates/accuracy_testing/`

```yaml
batch:
  filename_patterns:
    extract: "{incident}_{fiscal_year}_{quarter}.csv"
    template: "template_FY{fiscal_year}_Q{quarter}_7_{incident}.csv"
    output: "validated_FY{fiscal_year}_Q{quarter}_{incident}.csv"
```

### Step 7: Remove Deprecated Fields

Delete:
- Commented-out mode selection
- `auto_incidents` field (use `incidents: "auto"` instead)
- Any other commented code

### Step 8: Validate Config

```bash
python -c "
import yaml
from pathlib import Path

config_path = Path('config/local/accuracy_testing/my_config.yaml')
with open(config_path) as f:
    config = yaml.safe_load(f)

mode = config.get('mode')
print(f'Mode: {mode}')

if mode == 'batch':
    incidents = config['batch']['incidents']
    print(f'Incidents: {incidents}')
    patterns = config['batch'].get('filename_patterns', {})
    print(f'Patterns defined: {list(patterns.keys())}')
elif mode == 'single':
    incident = config['single']['incident_code']
    print(f'Incident: {incident}')
else:
    print('ERROR: Invalid mode')
"
```

### Step 9: Test with Script

```bash
# Dry run to check file discovery
python -m src.accuracy_testing.scripts.buyer_id_validation \
  --config config/local/accuracy_testing/my_config.yaml \
  --dry-run
```

### Step 10: Update Documentation

Add comment to config explaining migration:

```yaml
# Migrated to v2.0 config format on 2026-02-03
# Previous version backed up in my_config.yaml.backup
mode: "batch"
# ...
```

---

## Troubleshooting Migration Issues

### Issue: "KeyError: 'mode'"

**Cause:** Config missing `mode` field

**Fix:** Add `mode: "batch"` or `mode: "single"` at top level

### Issue: "KeyError: 'batch'"

**Cause:** Mode is `"batch"` but config not nested under `batch:`

**Fix:** Indent all config under `batch:` key

### Issue: "Invalid incidents value"

**Cause:** Using wrong auto-discovery keyword

**Fix:** 
- Use `"auto"` for validation scripts (buyer, seller, pricing)
- Use `"all"` for SQL generator and data push
- Or use explicit list: `["7_37", "7_39"]`

### Issue: "File not found with pattern"

**Cause:** Filename pattern doesn't match actual files

**Fix:** 
1. Check your actual file names
2. Update pattern to match: `{incident}_{fiscal_year}_{quarter}.csv`
3. Verify directory paths are correct

### Issue: "Script ignores filename_patterns"

**Cause:** Using old version of script

**Fix:** Ensure scripts are updated (Phase 2 updates required)

---

## Batch Migration Script

For migrating multiple configs at once:

```bash
#!/bin/bash
# migrate_configs.sh

CONFIG_DIR="config/local/accuracy_testing"

for config in "$CONFIG_DIR"/*.yaml; do
    echo "Checking $config..."
    
    # Check if already migrated
    if grep -q "^mode:" "$config"; then
        echo "  ✓ Already migrated"
        continue
    fi
    
    echo "  → Needs migration"
    echo "  Creating backup..."
    cp "$config" "${config}.backup"
    
    echo "  Manual migration required for: $config"
    echo "  Backup saved: ${config}.backup"
done

echo ""
echo "Migration check complete!"
echo "Manually update configs that need migration."
```

---

## Validation After Migration

### Checklist

- [ ] Config loads without errors (`yaml.safe_load()`)
- [ ] `mode` field present and valid (`"batch"` or `"single"`)
- [ ] Configuration nested under mode key
- [ ] `filename_patterns` section complete for mode type
- [ ] `incidents` field correct (auto/all/list)
- [ ] All file paths resolve correctly
- [ ] Script runs without errors
- [ ] Output files created with expected names
- [ ] Backup of old config exists

### Validation Script

```python
#!/usr/bin/env python3
"""Validate migrated config file."""

import yaml
import sys
from pathlib import Path

def validate_config(config_path):
    """Validate a migrated config file."""
    print(f"Validating: {config_path}")
    
    # Load config
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"  ✗ YAML parse error: {e}")
        return False
    
    # Check mode
    mode = config.get('mode')
    if not mode:
        print(f"  ✗ Missing 'mode' field")
        return False
    
    if mode not in ['batch', 'single']:
        print(f"  ✗ Invalid mode: {mode}")
        return False
    
    print(f"  ✓ Mode: {mode}")
    
    # Check structure
    if mode == 'batch':
        if 'batch' not in config:
            print(f"  ✗ Missing 'batch' section")
            return False
        
        batch = config['batch']
        
        # Check incidents
        incidents = batch.get('incidents')
        if not incidents:
            print(f"  ✗ Missing 'batch.incidents'")
            return False
        print(f"  ✓ Incidents: {incidents}")
        
        # Check filename_patterns
        patterns = batch.get('filename_patterns', {})
        if not patterns:
            print(f"  ⚠ Warning: No filename_patterns defined")
        else:
            print(f"  ✓ Patterns: {list(patterns.keys())}")
    
    elif mode == 'single':
        if 'single' not in config:
            print(f"  ✗ Missing 'single' section")
            return False
        
        single = config['single']
        incident = single.get('incident_code')
        if not incident:
            print(f"  ✗ Missing 'single.incident_code'")
            return False
        print(f"  ✓ Incident: {incident}")
    
    print(f"  ✓ Config valid!")
    return True

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: validate_config.py <config_file>")
        sys.exit(1)
    
    config_path = Path(sys.argv[1])
    if not config_path.exists():
        print(f"Config not found: {config_path}")
        sys.exit(1)
    
    if validate_config(config_path):
        sys.exit(0)
    else:
        sys.exit(1)
```

---

## Support

If you encounter issues during migration:

1. Check this guide for common issues
2. Consult [Accuracy Testing Configuration Guide](Accuracy_Testing_Configuration_Guide.md)
3. Refer to template files in `config/templates/accuracy_testing/`
4. Test with validation script above
5. Contact development team

---

**Document Version:**
- v1.0 (3 Feb 2026): Initial migration guide for v2.0 configs
