# Command Reference

Complete reference for all command-line tools in the TXR Automation suite.

## Installation

Before using any commands, ensure the package is installed:

```bash
# Install in development mode (recommended for active development)
pip install -e .

# Or install normally
pip install .
```

---

## Accuracy Testing Commands

### generate-accuracy-template

Generate accuracy testing template files from consolidated errors/queries data.

**Usage:**
```bash
# Using config file
generate-accuracy-template --config config/environments/local.yaml

# Using command-line arguments
generate-accuracy-template \
  --errors data/input/consolidated_errors.csv \
  --queries data/input/consolidated_queries.csv \
  --output data/output/templates

# Preview without generating files
generate-accuracy-template \
  --config config/environments/local.yaml \
  --dry-run
```

**Options:**
- `--config PATH` - Configuration YAML file
- `--errors PATH` - Consolidated errors CSV file (overrides config)
- `--queries PATH` - Consolidated queries CSV file (overrides config)
- `--output PATH` - Output directory for template files (overrides config)
- `--dry-run` - Preview generation without creating files

**Output:**
- One CSV template file per unique incident code
- Template structure: [Validation Columns | Comparison Columns | Consolidated Data]

**Related:**
- See [Accuracy Testing Workflow Guide](../guides/Accuracy_Testing_Workflow.md) for complete workflow

---

### generate-sql-extract

Generate SQL extract files from transaction references in template files.

**Usage:**
```bash
# Basic usage
generate-sql-extract \
  --template sql/ExtractBuyerID.sql \
  --input data/output/templates/template_7_37.csv \
  --output data/output/sql

# With custom batch size
generate-sql-extract \
  --template sql/PricingData.sql \
  --input data/output/templates/template_35_3.csv \
  --output data/output/sql \
  --batch-size 500

# Specify transaction column by name
generate-sql-extract \
  --template sql/ExtractSellerID.sql \
  --input data/output/templates/template_16_21.csv \
  --output data/output/sql \
  --column "Transaction reference number"

# Preview without generating
generate-sql-extract \
  --template sql/ExtractBuyerID.sql \
  --input data/output/templates/template_7_37.csv \
  --output data/output/sql \
  --dry-run
```

**Options:**
- `--template PATH` - SQL template file (required)
- `--input PATH` - CSV file with transaction references (required)
- `--output PATH` - Output directory for SQL files (required)
- `--batch-size N` - Number of transactions per file (default: 900)
- `--column NAME` - CSV column name for transaction refs (default: auto-detect "Transaction reference number")
- `--placeholder TEXT` - Custom SQL placeholder (default: auto-detect)
- `--dry-run` - Preview without generating files
- `--verbose` - Enable detailed output

**SQL Template Requirements:**
- Must contain placeholder: `-- TRANSACTION REFERENCES --`
- Legacy formats also supported: `--<<TRANSACTION REFERENCES>>`, `--<TRADE REFERENCES>--`

**Output:**
- Single SQL file if ≤ batch_size transactions
- Multiple numbered files if > batch_size: `template_Extract1.sql`, `template_Extract2.sql`, etc.

---

### validate-buyer

Validate buyer identification codes in transaction data.

**Usage:**
```bash
# Using config file
validate-buyer --config config/environments/local.yaml

# Using command-line arguments
validate-buyer \
  --reference data/output/templates/template_7_37.csv \
  --extract data/database/buyer_extract.csv \
  --output data/output/validated

# With verbose logging
validate-buyer \
  --reference data/output/templates/template_7_37.csv \
  --extract data/database/buyer_extract.csv \
  --output data/output/validated \
  --verbose
```

**Options:**
- `--config PATH` - Configuration YAML file
- `--reference PATH` - Reference CSV (template file, overrides config)
- `--extract PATH` - Database extract CSV (overrides config)
- `--output PATH` - Output directory (overrides config)
- `--verbose` - Enable detailed logging
- `--log-level LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)

**Validation Logic:**
- Extracts Account ID from Transaction Reference
- Determines account type (NIDN, CONCAT, CCPT)
- Validates Buyer ID format matches account type
- Generates CONCAT ID if invalid or missing
- Populates validation columns in template

**Output:**
- `{output}_validated.csv` - All records with validation results
- `{output}_errors_only.csv` - Only records with validation errors
- Log file in configured log directory

**Incident Codes:**
- 7_35 - Invalid buyer ID format
- 7_37 - Buyer ID missing
- 7_39 - Buyer ID type mismatch
- 7_66 - Buyer decision maker ID issues

---

### validate-seller

Validate seller identification codes in transaction data.

**Usage:**
```bash
# Using config file
validate-seller --config config/environments/local.yaml

# Using command-line arguments
validate-seller \
  --reference data/output/templates/template_16_21.csv \
  --extract data/database/seller_extract.csv \
  --output data/output/validated
```

**Options:**
- Same as `validate-buyer`

**Validation Logic:**
- Similar to buyer validation but for seller IDs
- Account type determination (NIDN, CONCAT, CCPT)
- Format validation and CONCAT generation

**Output:**
- Same structure as buyer validation

**Incident Codes:**
- 16_19 - Invalid seller ID format
- 16_21 - Seller ID missing
- 16_23 - Seller ID type mismatch
- 16_20 - Seller decision maker ID issues

---

### validate-pricing

Validate pricing data in transaction records.

**Usage:**
```bash
# Using config file
validate-pricing --config config/environments/local.yaml

# Using command-line arguments
validate-pricing \
  --reference data/output/templates/template_35_3.csv \
  --extract data/database/pricing_extract.csv \
  --output data/output/validated
```

**Options:**
- `--config PATH` - Configuration YAML file
- `--reference PATH` - Reference CSV (template file)
- `--extract PATH` - Database extract CSV
- `--output PATH` - Output directory
- `--verbose` - Enable detailed logging
- `--log-level LEVEL` - Logging level

**Validation Logic:**
- Validates Price field presence
- Validates Price Currency
- Checks Net Amount calculations
- Verifies Interest and Consideration fields

**Output:**
- Validated template file with pricing corrections
- Log file with processing summary

**Incident Code:**
- 35_3 - Price missing or invalid

---

## Replay Commands

### replay-phase2

Process Phase 2 replay data (incident lookup and validation).

**Usage:**
```bash
# Using config file
replay-phase2 --config config/environments/local.yaml

# With custom paths
replay-phase2 \
  --config config/environments/local.yaml \
  --input data/input/phase2_data.csv \
  --output data/output/phase2_results.csv
```

**Options:**
- `--config PATH` - Configuration YAML file (required)
- `--input PATH` - Input CSV file (overrides config)
- `--output PATH` - Output CSV file (overrides config)
- `--verbose` - Enable detailed logging

**Related:**
- Configuration template: `config/templates/phase2_template.yaml`

---

### replay-phase3

Process Phase 3 replay data (incident code matrix application).

**Usage:**
```bash
replay-phase3 --config config/environments/local.yaml
```

**Options:**
- `--config PATH` - Configuration YAML file (required)
- `--input PATH` - Input CSV file (overrides config)
- `--output PATH` - Output CSV file (overrides config)
- `--matrix PATH` - Incident code matrix file (overrides config)

**Related:**
- Configuration template: `config/templates/phase3_template.yaml`
- Incident code matrix: `data/archive/incident_code_matrix.csv`

---

### replay-phase3-final

Process Phase 3 final lookup (consolidated error/query assignment).

**Usage:**
```bash
replay-phase3-final --config config/environments/local.yaml
```

**Options:**
- `--config PATH` - Configuration YAML file (required)
- `--input PATH` - Input CSV file (overrides config)
- `--output PATH` - Output CSV file (overrides config)

**Related:**
- Configuration template: `config/templates/phase3_final_template.yaml`

---

## Utility Commands

### replay-xlsx-converter

Convert XLSX files to CSV format (original version).

**Usage:**
```bash
replay-xlsx-converter \
  --input data/input/report.xlsx \
  --output data/output/report.csv
```

**Options:**
- `--input PATH` - Input XLSX file (required)
- `--output PATH` - Output CSV file (required)
- `--sheet NAME` - Sheet name to convert (default: first sheet)

---

### replay-xlsx-converter-v2

Convert XLSX files to CSV format with enhanced features (v2).

**Usage:**
```bash
replay-xlsx-converter-v2 \
  --input data/input/report.xlsx \
  --output data/output/report.csv
```

**Options:**
- `--input PATH` - Input XLSX file (required)
- `--output PATH` - Output CSV file (required)
- `--sheet NAME` - Sheet name to convert (default: first sheet)
- `--encoding NAME` - Output encoding (default: utf-8)

**Related:**
- Configuration template: `config/templates/xlsx_converter_v2_template.yaml`

---

## Configuration Files

All commands support configuration files in YAML format. Configuration files allow you to:
- Set default input/output paths
- Configure logging levels and output
- Define processing options
- Maintain environment-specific settings

**Configuration Structure:**
```yaml
paths:
  input:
    # Input file paths
  output:
    # Output directory paths
  reference:
    # Reference data paths

logging:
  level: INFO  # DEBUG, INFO, WARNING, ERROR
  log_file: "logs/automation.log"

processing:
  # Processing-specific options
```

**Configuration Templates:**
- `config/templates/local_template.yaml` - General template
- `config/templates/accuracy_template_generator_template.yaml` - Template generator config
- `config/templates/sql_extract_generator_template.yaml` - SQL extract generator config
- `config/templates/buyer_validation_template.yaml` - Buyer validation config
- `config/templates/seller_validation_template.yaml` - Seller validation config
- `config/templates/pricing_validation_template.yaml` - Pricing validation config
- `config/templates/phase2_template.yaml` - Phase 2 replay config
- `config/templates/phase3_template.yaml` - Phase 3 replay config
- `config/templates/phase3_final_template.yaml` - Phase 3 final config

**Creating Local Configuration:**
```bash
# Copy template and customize
cp config/templates/local_template.yaml config/environments/local.yaml

# Edit with your paths
vim config/environments/local.yaml
```

**Note:** `config/environments/local.yaml` is in `.gitignore` and won't be committed.

---

## Common Workflows

### Complete Accuracy Testing Workflow

```bash
# 1. Generate templates from consolidated data
generate-accuracy-template \
  --errors data/input/consolidated_errors.csv \
  --queries data/input/consolidated_queries.csv \
  --output data/output/templates

# 2. Generate SQL extracts for buyer validation (7_37)
generate-sql-extract \
  --template sql/ExtractBuyerID.sql \
  --input data/output/templates/template_7_37.csv \
  --output data/output/sql

# 3. (Execute SQL in database and export results)

# 4. Run buyer validation
validate-buyer \
  --reference data/output/templates/template_7_37.csv \
  --extract data/database/buyer_extract.csv \
  --output data/output/validated

# 5. Repeat steps 2-4 for seller and pricing incidents
```

### Replay Processing Workflow

```bash
# 1. Convert XLSX to CSV
replay-xlsx-converter-v2 \
  --input data/input/raw_data.xlsx \
  --output data/input/raw_data.csv

# 2. Run Phase 2 processing
replay-phase2 --config config/environments/local.yaml

# 3. Run Phase 3 processing
replay-phase3 --config config/environments/local.yaml

# 4. Run Phase 3 final lookup
replay-phase3-final --config config/environments/local.yaml
```

---

## Environment Variables

Some commands support environment variables for common settings:

- `TXR_CONFIG` - Default config file path
- `TXR_LOG_LEVEL` - Default logging level
- `TXR_OUTPUT_DIR` - Default output directory

Example:
```bash
export TXR_CONFIG=config/environments/local.yaml
export TXR_LOG_LEVEL=DEBUG

# Now commands will use these defaults
validate-buyer --reference data/templates/template_7_37.csv \
               --extract data/database/buyer_extract.csv
```

---

## Troubleshooting

### Command Not Found

If you get "command not found" errors:

```bash
# Reinstall the package
pip install -e .

# Or check if it's installed
pip show txr-automation

# Verify commands are available
pip show -f txr-automation | grep console_scripts
```

### Import Errors

If you get import errors when running commands:

```bash
# Ensure you're in the project root
cd /path/to/txr_automation

# Reinstall with dependencies
pip install -e .
```

### Permission Errors

If you get permission errors:

```bash
# Check file permissions
ls -l data/output/

# Create output directories
mkdir -p data/output/{templates,sql,validated,logs}

# Check write permissions
chmod u+w data/output/
```

---

## Getting Help

All commands support `--help` for detailed usage information:

```bash
generate-accuracy-template --help
validate-buyer --help
replay-phase2 --help
```

For more information, see:
- [Accuracy Testing Workflow Guide](../guides/Accuracy_Testing_Workflow.md)
- [Quick Start Guide](../guides/Quick_Start_Guide.md)
- [Git Workflow Summary](../guides/Git_Workflow_Summary.md)

---

**Last Updated:** January 23, 2026  
**Version:** 1.0
