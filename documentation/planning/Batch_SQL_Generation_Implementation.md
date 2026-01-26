# Batch SQL Generation Implementation Summary

## Overview

Implemented batch mode for SQL extract generation, enabling automatic processing of multiple incidents with smart SQL template selection and FY/Q naming conventions.

## Key Features

### 1. Batch Mode Processing
- Process multiple incidents in one command
- Reads from validated CSV files: `validated_FY25_Q3_7_37.csv`
- Outputs with FY/Q naming: `7_37_FY25_Q3.sql`
- Automatically splits large datasets (>900 records) into multiple files

### 2. Automatic SQL Template Selection
The tool now intelligently selects the correct SQL template based on incident code:

| Incident Type | Codes | SQL Template |
|--------------|-------|--------------|
| Buyer ID | 7_*, 8_*, 9_*, 10_*, 11_*, 13_*, 14_*, 15_* | BuyerID.sql |
| Seller ID | 16_*, 17_*, 18_*, 19_*, 20_*, 22_*, 23_*, 24_*, 36_* | SellerID.sql |
| Pricing | 35_3 | SCR_pricing_data_v1.0.sql |
| Inconsistent Buyer | 7_66, 7_68 | InconsistentBuyerID.sql |
| Inconsistent Seller | 16_20, 16_64 | InconsistentSellerID.sql |
| Decision Maker Buyer | 12_* | FTBDM.sql |
| Decision Maker Seller | 21_* | FTSDM.sql |

### 3. Configuration-Driven
Batch mode uses YAML configuration matching validation scripts:

```yaml
testing_period:
  fiscal_year: "FY25"
  quarter: "Q3"
incidents: ["7_37", "16_21", "35_3"]
paths:
  template_dir: "data/validated"
  sql_template_dir: "src/accuracy_testing/sql_templates"
  output_directory: "data/sql_extracts"
processing:
  batch_size: 900
  transaction_column: "Transaction Ref"
```

## Implementation Details

### Code Changes

**Files Modified:**
1. `src/accuracy_testing/scripts/sql_extract_generator.py`
   - Added `get_sql_template_for_incident()` - Maps incident codes to SQL templates
   - Added `run_batch_sql_generation()` - Batch processing main function
   - Updated `main()` - Detects batch mode and routes appropriately

2. `config/templates/accuracy_testing/sql_extract_generator_template.yaml`
   - Complete rewrite with batch mode examples
   - Documented automatic template mapping
   - Added FY/Q configuration structure

3. `documentation/reference/Command_Reference.md`
   - Updated generate-sql-extract section with batch mode
   - Added configuration examples and template mapping table
   - Updated output naming conventions

4. `documentation/guides/SQL_Extract_Generator_Guide.md`
   - Restructured guide with batch mode as primary approach
   - Added automatic template selection documentation
   - Updated all examples with FY/Q naming

**Files Created:**
5. `tests/test_accuracy_testing/test_batch_sql_generation.py`
   - 15 integration tests covering all functionality
   - Tests SQL template mapping for all incident types
   - Tests batch processing, splitting, error handling, dry run

### Batch Mode Detection

The tool detects batch mode when config contains both:
```python
is_batch_mode = 'incidents' in config and 'testing_period' in config
```

This matches the pattern used in validation scripts for consistency.

### Output Naming

**Single batch (≤900 refs):**
- `{incident}_{fiscal_year}_{quarter}.sql`
- Example: `7_37_FY25_Q3.sql`

**Multiple batches (>900 refs):**
- `{incident}_{fiscal_year}_{quarter}_Extract{N}.sql`
- Example: `7_37_FY25_Q3_Extract1.sql`, `7_37_FY25_Q3_Extract2.sql`

## Usage Examples

### Batch Mode
```bash
# Process all incidents
generate-sql-extract --config config/local/accuracy_testing/sql_extract_generator.yaml

# Preview without generating
generate-sql-extract --config config.yaml --dry-run

# Verbose output
generate-sql-extract --config config.yaml --verbose
```

### Single Mode (Legacy)
```bash
# Process one incident manually
generate-sql-extract \
  --template src/accuracy_testing/sql_templates/BuyerID.sql \
  --input data/validated/validated_FY25_Q3_7_37.csv \
  --output data/sql_extracts
```

## Workflow Integration

The tool now integrates seamlessly with validation scripts:

1. **Generate Templates**: `generate-accuracy-template` → `FY25 Q3 7_37.csv`
2. **Validate Data**: `validate-buyer-ids` → `validated_FY25_Q3_7_37.csv`
3. **Generate SQL**: `generate-sql-extract` → `7_37_FY25_Q3.sql` ✨ NEW

All three steps now use consistent FY/Q naming and batch processing patterns.

## Test Coverage

**15 integration tests** verify:
- ✅ SQL template mapping for all 7 incident types
- ✅ Single incident processing
- ✅ Multiple incident processing
- ✅ Large dataset splitting (>900 records)
- ✅ Missing validated CSV handling
- ✅ Dry run mode
- ✅ Error handling (no incidents, unknown codes, missing templates)

All tests pass with 100% success rate.

## Benefits

1. **Consistency**: Matches validation script patterns (batch mode, FY/Q naming)
2. **Automation**: No manual SQL template selection required
3. **Scalability**: Handles any number of incidents in one run
4. **Safety**: Dry run mode for verification before execution
5. **Intelligence**: Automatic template selection based on incident codes
6. **Robustness**: Graceful error handling for missing files
7. **Transparency**: Clear output showing which templates were used

## Backward Compatibility

Single mode (legacy CLI arguments) remains fully functional for custom workflows:
- `--template`, `--input`, `--output` arguments still work
- Existing scripts and workflows unaffected
- Batch mode is opt-in via configuration

## Files Location

- **SQL Templates**: `src/accuracy_testing/sql_templates/`
- **Config Template**: `config/templates/accuracy_testing/sql_extract_generator_template.yaml`
- **Tests**: `tests/test_accuracy_testing/test_batch_sql_generation.py`
- **Documentation**: 
  - `documentation/reference/Command_Reference.md`
  - `documentation/guides/SQL_Extract_Generator_Guide.md`
