# Accuracy Testing Configuration Guide

**Version:** 2.0  
**Date:** 3 February 2026  
**Status:** Current

---

## Overview

This guide explains the configuration system for accuracy testing validation scripts. The system uses a mode-based architecture with configurable filename patterns to support both single-incident and batch processing workflows.

---

## Configuration Structure

All accuracy testing configs use a consistent structure:

```yaml
mode: "batch"  # or "single"

# For batch mode processing
batch:
  incidents: ["7_37", "7_39"]  # or "auto" for standard incidents
  testing_period:
    fiscal_year: "2025"
    quarter: "Q1"
  
  paths:
    extract_dir: "path/to/extracts"
    template_dir: "path/to/templates"
    output_dir: "path/to/outputs"
  
  filename_patterns:
    extract: "{incident}_{fiscal_year}_{quarter}.csv"
    template: "template_FY{fiscal_year}_Q{quarter}_7_{incident}.csv"
    output: "validated_FY{fiscal_year}_Q{quarter}_{incident}.csv"

# For single mode processing
single:
  incident_code: "7_66"
  
  paths:
    extract_file: "path/to/extract.csv"
    template_file: "path/to/template.csv"
    output_file: "path/to/output.csv"
```

---

## Mode Selection

### Batch Mode

Use `mode: "batch"` when processing multiple incidents in a single run:

- **Buyer ID Validation**: Multiple buyer incidents (7_35, 7_37, 7_39)
- **Seller ID Validation**: Multiple seller incidents (16_19, 16_21, 16_23)
- **Pricing Validation**: Multiple pricing incidents (35_3)
- **SQL Extract Generator**: All 11 automated incidents
- **Data Push**: All 11 automated incidents

**Benefits:**
- Process entire quarter's incidents in one command
- Consistent file naming across incidents
- Automated file discovery with patterns
- Reduced manual configuration

### Single Mode

Use `mode: "single"` when processing one incident at a time:

- **Inconsistent Buyer ID**: One-off validation (7_66)
- **Inconsistent Seller ID**: One-off validation (16_20)
- **FTBDM Validation**: Decision maker validation (12_17)
- **FTSDM Validation**: Decision maker validation (21_17)

**Benefits:**
- Explicit control over file paths
- Suitable for ad-hoc validations
- No file pattern requirements

---

## Incident Auto-Discovery

For batch mode, the `incidents` field supports auto-discovery:

```yaml
batch:
  incidents: "auto"  # Automatically discovers standard incidents
```

**Auto-Discovery by Script:**

| Script | `incidents: "auto"` Discovers |
|--------|-------------------------------|
| buyer_id_validation.py | `["7_35", "7_37", "7_39"]` |
| seller_id_validation.py | `["16_19", "16_21", "16_23"]` |
| pricing_validation.py | `["35_3"]` |
| sql_extract_generator.py | N/A (use `"all"` for 11 incidents) |
| data_push.py | N/A (use `"all"` for 11 incidents) |

**SQL Generator & Data Push:**

These scripts support ALL 11 automated incidents:

```yaml
batch:
  incidents: "all"  # Processes all 11: 7_35, 7_37, 7_39, 7_66, 12_17, 16_19, 16_21, 16_23, 16_20, 21_17, 35_3
```

Or specify explicitly:

```yaml
batch:
  incidents: ["7_37", "7_39", "16_19", "35_3"]
```

---

## Filename Pattern System

Batch mode uses Python format strings for dynamic filename generation:

### Available Variables

- `{incident}` - Incident code (e.g., `7_37`, `16_19`, `35_3`)
- `{fiscal_year}` - Fiscal year (e.g., `2025`)
- `{quarter}` - Quarter (e.g., `Q1`, `Q2`, `Q3`, `Q4`)

### Pattern Types by Script

**Buyer/Seller ID Validation:**
```yaml
filename_patterns:
  extract: "{incident}_{fiscal_year}_{quarter}.csv"
  template: "template_FY{fiscal_year}_Q{quarter}_7_{incident}.csv"
  output: "validated_FY{fiscal_year}_Q{quarter}_{incident}.csv"
```

**Pricing Validation:**
```yaml
filename_patterns:
  template: "template_FY{fiscal_year}_Q{quarter}_35_3.csv"
  output: "validated_FY{fiscal_year}_Q{quarter}_{incident}.csv"
```
*Note: Pricing has no extract file (uses template only)*

**SQL Extract Generator:**
```yaml
filename_patterns:
  output_sql: "SQL_{incident}.sql"
  output_sql_batch: "SQL_Batch_{incident}.sql"
  output_dtf: "dtf_{incident}.txt"
  output_dtf_batch: "dtf_Batch_{incident}.txt"
  output_csv: "{incident}.csv"
  output_csv_batch: "Batch_{incident}.csv"
```

**Data Push:**
```yaml
filename_patterns:
  source: "validated_FY{fiscal_year}_Q{quarter}_{incident}.csv"
  target: "template_FY{fiscal_year}_Q{quarter}_{incident}.csv"
```

### Pattern Substitution Examples

Given config:
```yaml
batch:
  testing_period:
    fiscal_year: "2025"
    quarter: "Q1"
  filename_patterns:
    extract: "{incident}_{fiscal_year}_{quarter}.csv"
```

**Substitution for incident 7_37:**
- Pattern: `{incident}_{fiscal_year}_{quarter}.csv`
- Result: `7_37_2025_Q1.csv`

**Substitution for incident 16_19:**
- Pattern: `{incident}_{fiscal_year}_{quarter}.csv`
- Result: `16_19_2025_Q1.csv`

---

## Template Files

Pre-configured templates are available in `config/templates/accuracy_testing/`:

### Batch Mode Templates

1. **buyer_validation_template.yaml**
   - Mode: `batch`
   - Incidents: `auto` (discovers 7_35, 7_37, 7_39)
   - Patterns: extract, template, output

2. **seller_validation_template.yaml**
   - Mode: `batch`
   - Incidents: `auto` (discovers 16_19, 16_21, 16_23)
   - Patterns: extract, template, output

3. **pricing_validation_template.yaml**
   - Mode: `batch`
   - Incidents: `auto` (discovers 35_3)
   - Patterns: template, output (no extract)

4. **sql_extract_generator_template.yaml**
   - Mode: `batch`
   - Incidents: `all` (all 11 incidents)
   - Patterns: 6 output patterns (SQL, DTF, CSV variants)

5. **data_push_template.yaml**
   - Mode: `batch`
   - Incidents: `all` (all 11 incidents)
   - Patterns: source, target
   - Includes push logic rules

### Single Mode Templates

6. **inconsistent_buyer_validation_template.yaml**
   - Mode: `single`
   - Incident: 7_66
   - Explicit file paths

7. **inconsistent_seller_validation_template.yaml**
   - Mode: `single`
   - Incident: 16_20
   - Explicit file paths

8. **ftbdm_validation_template.yaml**
   - Mode: `single`
   - Incident: 12_17
   - Explicit file paths

9. **ftsdm_validation_template.yaml**
   - Mode: `single`
   - Incident: 21_17
   - Explicit file paths

---

## Usage Examples

### Example 1: Batch Process All Buyer Incidents for Q1 2025

**Config file:** `config/local/accuracy_testing/buyer_q1_2025.yaml`

```yaml
mode: "batch"

batch:
  incidents: "auto"  # Discovers 7_35, 7_37, 7_39
  
  testing_period:
    fiscal_year: "2025"
    quarter: "Q1"
  
  paths:
    extract_dir: "/data/accuracy_testing/extracts/FY2025_Q1"
    template_dir: "/data/accuracy_testing/templates/FY2025_Q1"
    output_dir: "/data/accuracy_testing/outputs/FY2025_Q1"
  
  filename_patterns:
    extract: "{incident}_{fiscal_year}_{quarter}.csv"
    template: "template_FY{fiscal_year}_Q{quarter}_7_{incident}.csv"
    output: "validated_FY{fiscal_year}_Q{quarter}_{incident}.csv"
```

**Run:**
```bash
python -m src.accuracy_testing.scripts.buyer_id_validation \
  --config config/local/accuracy_testing/buyer_q1_2025.yaml
```

**Files processed:**
- Extract: `7_35_2025_Q1.csv`, `7_37_2025_Q1.csv`, `7_39_2025_Q1.csv`
- Template: `template_FY2025_Q1_7_35.csv`, etc.
- Output: `validated_FY2025_Q1_7_35.csv`, etc.

### Example 2: Single Inconsistent Buyer Validation

**Config file:** `config/local/accuracy_testing/inconsistent_buyer.yaml`

```yaml
mode: "single"

single:
  incident_code: "7_66"
  
  paths:
    extract_file: "/data/accuracy_testing/extracts/7_66_special.csv"
    template_file: "/data/accuracy_testing/templates/template_7_66.csv"
    output_file: "/data/accuracy_testing/outputs/validated_7_66.csv"
```

**Run:**
```bash
python -m src.accuracy_testing.scripts.inconsistent_buyer_id_validation \
  --config config/local/accuracy_testing/inconsistent_buyer.yaml
```

### Example 3: SQL Generator for Specific Incidents

**Config file:** `config/local/accuracy_testing/sql_generator.yaml`

```yaml
mode: "batch"

batch:
  incidents: ["7_37", "7_39", "16_19", "35_3"]
  
  testing_period:
    fiscal_year: "2025"
    quarter: "Q1"
  
  paths:
    validated_dir: "/data/accuracy_testing/outputs/FY2025_Q1"
    output_dir: "/data/extracts/FY2025_Q1"
  
  filename_patterns:
    validated: "validated_FY{fiscal_year}_Q{quarter}_{incident}.csv"
    output_sql: "SQL_{incident}.sql"
    output_dtf: "dtf_{incident}.txt"
    output_csv: "{incident}.csv"
  
  sql_template_mapping:
    7_37: "ExtractInconsistentBuyerID.sql"
    7_39: "ExtractBuyerID.sql"
    16_19: "ExtractSellerID.sql"
    35_3: "ExtractPricing.sql"
```

**Run:**
```bash
python -m src.accuracy_testing.scripts.sql_extract_generator \
  --config config/local/accuracy_testing/sql_generator.yaml
```

---

## Migration from Old Configs

### Old Config Format (Pre-v2.0)

```yaml
# Mode was inferred from presence of fields
incidents: ["7_37", "7_39"]
auto_incidents: "all"
testing_period:
  fiscal_year: "2025"
  quarter: "Q1"

paths:
  extract_dir: "..."
  # Hardcoded filename patterns in script
```

### New Config Format (v2.0+)

```yaml
mode: "batch"  # Explicit mode declaration

batch:
  incidents: "auto"  # Or explicit list
  testing_period:
    fiscal_year: "2025"
    quarter: "Q1"
  
  paths:
    extract_dir: "..."
  
  filename_patterns:
    extract: "{incident}_{fiscal_year}_{quarter}.csv"
    template: "template_FY{fiscal_year}_Q{quarter}_7_{incident}.csv"
    output: "validated_FY{fiscal_year}_Q{quarter}_{incident}.csv"
```

### Migration Steps

1. **Add explicit `mode` field** at top level:
   ```yaml
   mode: "batch"  # or "single"
   ```

2. **Nest configuration under mode key:**
   - Batch mode: Nest under `batch:`
   - Single mode: Nest under `single:`

3. **Add `filename_patterns` section** with appropriate patterns

4. **Update `incidents` field:**
   - Use `"auto"` for standard incident discovery
   - Use `"all"` for SQL generator / data push
   - Use explicit list `["7_37", "7_39"]` for custom sets

5. **Remove commented code** and deprecated fields

6. **Test with validation script:**
   ```bash
   python -c "import yaml; print(yaml.safe_load(open('your_config.yaml'))['mode'])"
   ```

---

## Common Patterns

### Pattern: Quarter-Based Processing

Process all incidents for a specific quarter:

```yaml
mode: "batch"
batch:
  incidents: "auto"
  testing_period:
    fiscal_year: "2025"
    quarter: "Q2"
```

### Pattern: Selective Incident Processing

Process only specific incidents:

```yaml
mode: "batch"
batch:
  incidents: ["7_37", "16_19"]  # Just these two
```

### Pattern: Custom Filename Conventions

Override default patterns:

```yaml
batch:
  filename_patterns:
    extract: "extract_{incident}_{quarter}_{fiscal_year}.csv"
    output: "{incident}_validated_{fiscal_year}{quarter}.csv"
```

### Pattern: Shared Directories

All incidents share same directories:

```yaml
batch:
  paths:
    extract_dir: "/data/quarterly/FY2025_Q1/extracts"
    template_dir: "/data/quarterly/FY2025_Q1/templates"
    output_dir: "/data/quarterly/FY2025_Q1/validated"
```

---

## Troubleshooting

### Error: "mode field is required"

**Cause:** Config missing `mode` field

**Solution:** Add `mode: "batch"` or `mode: "single"` at top level

### Error: "Cannot find file matching pattern"

**Cause:** Filename pattern doesn't match actual files

**Solution:** 
1. Check pattern variables are correct: `{incident}`, `{fiscal_year}`, `{quarter}`
2. Verify files exist with expected naming
3. Check directory paths are correct

### Error: "incidents field is required for batch mode"

**Cause:** Batch mode missing `batch.incidents` field

**Solution:** Add incidents list or use auto-discovery:
```yaml
batch:
  incidents: "auto"
```

### Warning: "Using default pattern"

**Cause:** `filename_patterns` section missing or incomplete

**Solution:** Add all required patterns for the script type (see Pattern Types above)

### Script Processes Wrong Incidents

**Cause:** Using `"auto"` with wrong script type

**Solution:** Check auto-discovery rules or use explicit list:
```yaml
batch:
  incidents: ["7_37", "7_39"]  # Explicit control
```

---

## Best Practices

1. **Use templates as starting point**: Copy from `config/templates/accuracy_testing/`

2. **Use auto-discovery for standard workflows**: `incidents: "auto"` reduces configuration

3. **Use explicit lists for custom workflows**: Specify incidents when needed

4. **Keep patterns consistent**: Use same naming convention across all configs

5. **Document custom patterns**: Add comments explaining non-standard patterns

6. **Version control configs**: Store in `config/local/` and commit to git

7. **Test configs before batch runs**: Use single incident first to verify patterns

8. **Use descriptive config names**: `buyer_validation_FY2025_Q1.yaml` not `config1.yaml`

---

## Script-Specific Notes

### Buyer ID Validation
- Requires `extract`, `template`, `output` patterns
- Auto-discovers incidents: 7_35, 7_37, 7_39
- Template files must include incident code in name

### Seller ID Validation
- Same pattern structure as buyer validation
- Auto-discovers incidents: 16_19, 16_21, 16_23
- Uses incident family "16" in template pattern

### Pricing Validation
- **No extract file** - uses template only
- Only requires `template` and `output` patterns
- Auto-discovers incident: 35_3
- Template naming uses "35_3" directly

### Inconsistent ID Validation
- Single mode only (7_66 buyer, 16_20 seller)
- Processes chronologically by person code
- Requires explicit file paths

### Decision Maker Validation
- Single mode only (12_17 FTBDM, 21_17 FTSDM)
- Requires LEI lookup file
- Uses explicit file paths

### SQL Extract Generator
- Supports all 11 incidents with `"all"`
- Requires 6 output patterns (SQL, DTF, CSV × 2 variants each)
- Uses `sql_template_mapping` to specify SQL template per incident

### Data Push
- Supports all 11 incidents with `"all"`
- Uses `source` and `target` patterns
- Includes `push_logic.rules` for error flag handling

---

## Reference

### Complete Incident List

| Code | Name | Script | Mode |
|------|------|--------|------|
| 7_35 | Buyer ID (Template) | buyer_id_validation.py | batch |
| 7_37 | Inconsistent Buyer ID (Auto) | buyer_id_validation.py | batch |
| 7_39 | Buyer ID (Extract) | buyer_id_validation.py | batch |
| 7_66 | Inconsistent Buyer ID (Chronological) | inconsistent_buyer_id_validation.py | single |
| 12_17 | Buyer Decision Maker | validate_ftbdm.py | single |
| 16_19 | Seller ID (Template) | seller_id_validation.py | batch |
| 16_21 | Inconsistent Seller ID (Auto) | seller_id_validation.py | batch |
| 16_23 | Seller ID (Extract) | seller_id_validation.py | batch |
| 16_20 | Inconsistent Seller ID (Chronological) | inconsistent_seller_id_validation.py | single |
| 21_17 | Seller Decision Maker | validate_ftsdm.py | single |
| 35_3 | Pricing Data | pricing_validation.py | batch |

### All 11 Automated Incidents

For SQL generator and data push (`incidents: "all"`):

7_35, 7_37, 7_39, 7_66, 12_17, 16_19, 16_21, 16_23, 16_20, 21_17, 35_3

---

## See Also

- [Quick Start Guide](Quick_Start_Guide.md) - Getting started with accuracy testing
- [Git Branching Guide](Git_Branching_Guide.md) - Version control for configs
- Script-specific documentation in `src/accuracy_testing/scripts/`

---

**Document Version History:**

- v2.0 (3 Feb 2026): New mode-based configuration with filename patterns
- v1.0 (Prior): Legacy configuration format (deprecated)
