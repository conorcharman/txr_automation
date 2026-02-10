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
# Using config file (default: config/templates/accuracy_template_generator_template.yaml)
generate-accuracy-template --config config/my_config.yaml

# Using command-line arguments (overrides config)
generate-accuracy-template \
  --errors data/input/consolidated_errors.csv \
  --queries data/input/consolidated_queries.csv \
  --output data/output/templates

# Mix config and CLI (CLI overrides config values)
generate-accuracy-template \
  --config config/my_config.yaml \
  --output data/output/templates

# Preview without generating files
generate-accuracy-template \
  --config config/environments/local.yaml \
  --dry-run
```

**Options:**

- `--config PATH` - Configuration YAML file
  (optional, default: config/templates/accuracy_template_generator_template.yaml)
- `--errors PATH` - Consolidated errors CSV file (overrides config)
- `--queries PATH` - Consolidated queries CSV file (overrides config)
- `--output PATH` - Output directory for template files (overrides config)
- `--dry-run` - Preview generation without creating files

**Output:**

- One CSV template file per unique incident code
- Template structure: [Validation Columns | Comparison Columns | Consolidated Data]

**Related:**

- See [Accuracy Testing Workflow Guide](../guides/Accuracy_Testing_Workflow.md)
  for complete workflow

---

### generate-sql-extract

Generate SQL extract files from transaction references in validated data.
Supports both **batch mode** (multiple incidents) and **single mode** (one incident).

**Batch Mode (Recommended):**

```bash
# Process multiple incidents automatically
# Reads validated CSV files, auto-selects SQL templates, generates extracts
generate-sql-extract --config config/local/accuracy_testing/sql_extract_generator.yaml

# Preview batch processing
generate-sql-extract --config config/batch.yaml --dry-run

# Verbose output
generate-sql-extract --config config/batch.yaml --verbose
```

**Batch Configuration Example:**

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

**Automatic SQL Template Selection:**

- Buyer ID incidents (7_*, 8_*, 9_*, etc.) → `BuyerID.sql`
- Seller ID incidents (16_*, 17_*, etc.) → `SellerID.sql`
- Pricing incidents (35_3) → `SCR_pricing_data_v1.0.sql`
- Inconsistent Buyer (7_66, 7_68) → `InconsistentBuyerID.sql`
- Inconsistent Seller (16_20, 16_64) → `InconsistentSellerID.sql`
- Decision Maker Buyer (12_*) → `FTBDM.sql`
- Decision Maker Seller (21_*) → `FTSDM.sql`

**Single Mode (Legacy):**

```bash
# Process one incident manually
generate-sql-extract \
  --template src/accuracy_testing/sql_templates/BuyerID.sql \
  --input data/validated/validated_FY25_Q3_7_37.csv \
  --output data/sql_extracts

# Custom batch size
generate-sql-extract \
  --template src/accuracy_testing/sql_templates/SCR_pricing_data_v1.0.sql \
  --input data/validated/validated_FY25_Q3_35_3.csv \
  --output data/sql_extracts \
  --batch-size 500

# Specify transaction column
generate-sql-extract \
  --template src/accuracy_testing/sql_templates/SellerID.sql \
  --input data/custom_transactions.csv \
  --output data/sql_extracts \
  --column "Transaction reference number"
```

**Options:**

- `--config PATH` - Configuration YAML file
  (enables batch mode if contains `incidents` and `testing_period`)
- `--template PATH` - SQL template file (single mode, required unless in config)
- `--input PATH` - CSV file with transaction references
  (single mode, required unless in config)
- `--output PATH` - Output directory for SQL files (required unless in config)
- `--batch-size N` - Number of transactions per file (default: 900)
- `--column NAME` - CSV column name for transaction refs (default: "Transaction Ref")
- `--placeholder TEXT` - Custom SQL placeholder (default: "-- TRANSACTION REFERENCES --")
- `--dry-run` - Preview without generating files
- `--verbose` - Enable detailed output

**SQL Template Requirements:**

- Must contain placeholder: `-- TRANSACTION REFERENCES --`

**Output Naming:**

- **Batch mode:** `{incident}_{fiscal_year}_{quarter}.sql`
  or `{incident}_{fiscal_year}_{quarter}_Extract{N}.sql`
  - Example: `7_37_FY25_Q3.sql`, `35_3_FY25_Q3_Extract1.sql`
- **Single mode:** `{template_name}.sql` or `{template_name}_Extract{N}.sql`
  - Example: `BuyerID.sql`, `BuyerID_Extract1.sql`

**Batch Splitting:**

- Datasets > `batch_size` are automatically split into multiple files
- Example: 2000 refs with batch_size=900 → Extract1 (900), Extract2 (900), Extract3 (200)

---

### validate-all

Run all validation scripts in sequence with unified progress tracking and reporting.

**Usage:**

```bash
# Run all validations with default configurations
validate-all

# Run specific validations
validate-all --validations buyer seller

# Use custom config file
validate-all --config config/local/accuracy_testing/run_all_validations.yaml

# Stop on first failure
validate-all --stop-on-error

# List available validations
validate-all --list

# Verbose output
validate-all --verbose
```

**Included Validations:**

1. **buyer** - Buyer ID Validation (7_5, 7_6)
2. **seller** - Seller ID Validation (7_7, 7_8)
3. **inconsistent-buyer** - Inconsistent Buyer ID Validation (7_37, 7_38)
4. **inconsistent-seller** - Inconsistent Seller ID Validation (7_39, 7_40)
5. **ftbdm** - Field 27 Buyer Decision Maker Validation
6. **ftsdm** - Field 28 Seller Decision Maker Validation
7. **pricing** - Pricing Validation

**Options:**

- `--config PATH` - Configuration YAML file (optional)
- `--validations NAME [NAME ...]` - Specific validations to run
- `--stop-on-error` - Stop execution on first validation failure
- `--list` - List available validations and exit
- `--log-level LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)
- `--verbose` - Enable verbose output

**Configuration File Format:**

```yaml
validations:
  - name: "buyer"
    script_module: "src.accuracy_testing.scripts.buyer_id_validation"
    config_file: "config/local/accuracy_testing/buyer_validation.yaml"
    enabled: true
    description: "Buyer ID Validation (7_5, 7_6)"
  
  - name: "seller"
    script_module: "src.accuracy_testing.scripts.seller_id_validation"
    config_file: "config/local/accuracy_testing/seller_validation.yaml"
    enabled: true
    description: "Seller ID Validation (7_7, 7_8)"
  
  # ... more validations
```

**Output:**

- Execution plan with all validations to run
- Real-time progress for each validation
- Summary table with results and duration
- Overall success/failure status

**Related:**

- Individual validation commands: `validate-buyer`, `validate-seller`, etc.
- Config template: `config/templates/accuracy_testing/run_all_validations_template.yaml`

---

### validate-buyer

Validate buyer identification codes in transaction data.
Supports both **batch mode** (multiple incidents) and **single mode** (one incident).

**Batch Mode (Recommended):**

```bash
# Auto-discover and process ALL buyer incidents (7_*, 8_*, 9_*, 10_*, etc.)
validate-buyer --config config/local/accuracy_testing/buyer_validation.yaml

# Preview batch processing
validate-buyer --config config/batch.yaml --dry-run

# Show progress bars
validate-buyer --config config/batch.yaml --progress
```

**Batch Configuration with Auto-Discovery:**

```yaml
testing_period:
  fiscal_year: "FY25"
  quarter: "Q3"

# Auto-discover all buyer incidents (RECOMMENDED)
# Processes all 40 buyer incidents
# Automatically detects and skips decision maker incidents (7_66, 7_68)
auto_incidents: "all"

# Alternative: Specify incidents manually
# incidents:
#   - "7_35"
#   - "7_37"
#   - "7_39"

paths:
  template_dir: "data/output/accuracy_testing/templates"
  output_dir: "data/output/accuracy_testing/validated"
```

**What Auto-Discovery Processes:**

- **40 buyer incidents**: 7_*, 8_*, 9_*, 10_*, 11_*, 12_*, 13_*, 14_*, 15_*, 21_2
- **Smart Detection**: Decision maker incidents (7_66, 7_68) are auto-detected and
  skipped with clear warnings
- Automatically reads: `FY25 Q3 7_37.csv`, `FY25 Q3 8_1.csv`, etc.
- Automatically writes: `validated_FY25_Q3_7_37.csv`, `validated_FY25_Q3_8_1.csv`, etc.

**Inconsistent ID Incidents:**

Incidents 7_66 and 7_68 are "inconsistent buyer ID" codes requiring different
validation logic:

- Grouping records by Person Code
- Chronological analysis (sorting by Trade_Date_Time)
- Correcting invalid IDs using prior valid IDs

These incidents are **not processed by validate-buyer**. Use the dedicated
`validate-inconsistent-buyer` command instead. See the validate-inconsistent-buyer
section for details.

**Single File Mode:**

```bash
# Process one incident with explicit file paths
validate-buyer \
  --reference data/output/templates/template_7_37.csv \
  --extract data/database/buyer_extract.csv \
  --output data/output/validated
```

**Options:**

- `--config PATH` - Configuration YAML file
- `--reference PATH` - Reference CSV (template file, overrides config)
- `--extract PATH` - Database extract CSV (overrides config)
- `--output PATH` - Output directory (overrides config)
- `--verbose` - Enable detailed logging
- `--log-level LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)
- `--dry-run` - Preview without writing files
- `--progress` - Show progress bars (batch mode only)

**Validation Logic:**

- Extracts Account ID from Transaction Reference
- Determines account type (NIDN, CONCAT, CCPT)
- Validates Buyer ID format matches account type
- Generates CONCAT ID if invalid or missing
- Populates validation columns in template

**Output (Single Mode):**

- `{output}_validated.csv` - All records with validation results
- `{output}_errors_only.csv` - Only records with validation errors
- Log file in configured log directory

**Output (Batch Mode):**

- `validated_FY25_Q3_7_37.csv` - One file per incident
- Summary report with success/failure counts
- Consolidated logs

**Common Buyer Incident Codes:**

- 7_35 - Invalid buyer ID format
- 7_37 - Buyer ID missing (standard txr)
- 7_39 - Buyer ID type mismatch
- 7_66 - Inconsistent buyer ID (⚠️ use `validate-inconsistent-buyer` command)
- 7_68 - Inconsistent buyer decision maker ID (⚠️ use `validate-inconsistent-buyer`)
- 8_*, 9_*, 10_*, 11_*, 12_*, 13_*, 14_*, 15_* - Other buyer ID issues

---

### validate-seller

Validate seller identification codes in transaction data.
Supports both **batch mode** (multiple incidents) and **single mode** (one incident).

**Batch Mode (Recommended):**

```bash
# Auto-discover and process ALL seller incidents (16_*, 17_*, 18_*, etc.)
validate-seller --config config/local/accuracy_testing/seller_validation.yaml

# Preview batch processing
validate-seller --config config/batch.yaml --dry-run

# Show progress bars
validate-seller --config config/batch.yaml --progress
```

**Batch Configuration with Auto-Discovery:**

```yaml
testing_period:
  fiscal_year: "FY25"
  quarter: "Q3"

# Auto-discover all seller incidents (RECOMMENDED)
# Processes all 41 seller incidents
# Automatically detects and skips decision maker incidents (16_20, 16_64)
auto_incidents: "all"

# Alternative: Specify incidents manually
# incidents:
#   - "16_19"
#   - "16_21"
#   - "16_23"

paths:
  template_dir: "data/output/accuracy_testing/templates"
  output_dir: "data/output/accuracy_testing/validated"
```

**What Auto-Discovery Processes:**

- **41 seller incidents**: 16_*, 17_*, 18_*, 19_*, 20_*, 21_*, 22_*, 23_*, 24_*, 36_23
- **Smart Detection**: Decision maker incidents (16_20, 16_64) are auto-detected and
  skipped with clear warnings
- Automatically reads: `FY25 Q3 16_21.csv`, `FY25 Q3 17_2.csv`, etc.
- Automatically writes: `validated_FY25_Q3_16_21.csv`, `validated_FY25_Q3_17_2.csv`, etc.

**Inconsistent ID Incidents:**

Incidents 16_20 and 16_64 are "inconsistent seller ID" codes requiring different
validation logic:

- Grouping records by Person Code
- Chronological analysis (sorting by Trade_Date_Time)
- Correcting invalid IDs using prior valid IDs

These incidents are **not processed by validate-seller**. Use the dedicated
`validate-inconsistent-seller` command instead. See the validate-inconsistent-seller
section for details.

**Single File Mode:**

```bash
# Process one incident with explicit file paths
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

- Same structure as buyer validation (single and batch modes)

**Common Seller Incident Codes:**

- 16_19 - Invalid seller ID format
- 16_21 - Seller ID missing
- 16_23 - Seller ID type mismatch
- 16_20 - Inconsistent seller ID (⚠️ use `validate-inconsistent-seller` command)
- 16_64 - Inconsistent seller decision maker ID (⚠️ use `validate-inconsistent-seller`)
- 17_*, 18_*, 19_*, 20_*, 21_*, 22_*, 23_*, 24_* - Other seller ID issues

---

### validate-inconsistent-buyer

Validate buyer identification codes for inconsistent ID scenarios.

**Purpose:**

This script handles cases where the same person (identified by Person Code) has
different IDs across multiple trades. It uses a specialized chronological validation
algorithm that only corrects invalid IDs using the most recent prior valid ID.

**Usage:**

```bash
# Using config file
validate-inconsistent-buyer --config config/local/accuracy_testing/inconsistent_buyer.yaml

# Using command-line arguments
validate-inconsistent-buyer \
  --input data/extracts/7_66_FY26_Q1.csv \
  --output data/validated/validated_FY26_Q1_7_66.csv

# With environment variables
export TXR_PATHS_INPUT_FILE="data/buyer_input.csv"
export TXR_PATHS_OUTPUT_FILE="data/buyer_output.csv"
validate-inconsistent-buyer --use-env

# Verbose output
validate-inconsistent-buyer \
  --input data/extracts/7_66_FY26_Q1.csv \
  --output data/validated/validated_FY26_Q1_7_66.csv \
  --log-level DEBUG
```

**Options:**

- `--config PATH` - Configuration YAML file
- `--input PATH` - Input extract CSV file (overrides config)
- `--output PATH` - Output CSV file (overrides config)
- `--use-env` - Load configuration from environment variables
- `--log-level LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)
- `--verbose` - Enable verbose output

**Validation Algorithm:**

1. **Group by Person Code** - Records are grouped by Person Code
2. **Chronological Sort** - Each group sorted by Trade_Date_Time
3. **Sequential Validation** - Each ID validated using standard format + logic rules
4. **Prior Valid ID Correction** - Invalid IDs corrected using most recent prior valid ID
5. **Fallback ID Detection** - Detects CC_PersonCode pattern fallback IDs

**Key Differences from Standard Validation:**

- Groups records by Person Code (not individual validation)
- Requires Trade_Date_Time column for chronological ordering
- Only corrects invalid IDs - valid-to-valid changes are preserved
- Uses prior valid ID as correction source (not generated CONCAT)

**Input CSV Columns (Minimum Required):**

- Transaction Reference
- Account ID
- Trade_Date_Time (format: YYYY-MM-DD-HH-MM-SS-MSMS)
- Person Code
- Account Type
- Buyer ID Code
- Type of Buyer ID Code
- First Name
- Surname
- Date of Birth
- Gender
- Primary Nationality
- Secondary Nationality (optional)

**Output CSV Adds:**

- Correction Output (ID:TYPE format from prior valid)
- Correction Fields
- Correction Source (where the correction came from)
- Tracker Status
- Pass/Fail
- Failure Reason
- Actions Taken
- Error
- Kaizen Error
- Match

**Incident Codes:**

- 7_66 - Inconsistent Buyer ID (standard transactions)
- 7_68 - Inconsistent Buyer Decision Maker ID

**Configuration Template:**

- `config/templates/accuracy_testing/inconsistent_buyer_validation_template.yaml`

---

### validate-inconsistent-seller

Validate seller identification codes for inconsistent ID scenarios.

**Purpose:**

Same as inconsistent buyer validation but for seller IDs.

**Usage:**

```bash
# Using config file
validate-inconsistent-seller --config config/local/accuracy_testing/inconsistent_seller.yaml

# Using command-line arguments
validate-inconsistent-seller \
  --input data/extracts/16_20_FY26_Q1.csv \
  --output data/validated/validated_FY26_Q1_16_20.csv

# With environment variables
export TXR_PATHS_INPUT_FILE="data/seller_input.csv"
export TXR_PATHS_OUTPUT_FILE="data/seller_output.csv"
validate-inconsistent-seller --use-env
```

**Options:**

- Same as `validate-inconsistent-buyer`

**Validation Algorithm:**

- Same as inconsistent buyer validation but for seller records
- Output columns use "Seller" instead of "Buyer"

**Input CSV Columns:**

- Same as inconsistent buyer but with "Seller ID Code" and "Type of Seller ID Code"

**Incident Codes:**

- 16_20 - Inconsistent Seller ID (standard transactions)
- 16_64 - Inconsistent Seller Decision Maker ID

**Configuration Template:**

- `config/templates/accuracy_testing/inconsistent_seller_validation_template.yaml`

---

### collate-csv-extracts

Merge split CSV extract files back into single files for validation.

**Purpose:**

When the SQL extract generator splits large datasets into multiple batches
(e.g., `7_37_Extract1.csv`, `7_37_Extract2.csv`, `7_37_Extract3.csv`), this tool
collates them back into a single file ready for validation.

**Usage:**

```bash
# Single incident
collate-csv-extracts \
  --input-dir data/csv \
  --incident 7_37 \
  --output data/collated/7_37.csv

# Batch mode with config
collate-csv-extracts --config config/local/collate_extracts.yaml

# Batch mode - all incidents
collate-csv-extracts \
  --input-dir data/csv \
  --output-dir data/collated \
  --all-incidents

# Specific incidents
collate-csv-extracts \
  --input-dir data/csv \
  --output-dir data/collated \
  --incidents "7_37,16_21,35_3"

# Delete source files after collation
collate-csv-extracts \
  --input-dir data/csv \
  --output-dir data/collated \
  --incidents "7_37" \
  --delete-source
```

**Options:**

- `--config PATH` - Configuration YAML file
- `--input-dir PATH` - Directory containing split CSV files (overrides config)
- `--output-dir PATH` - Directory for collated output files (overrides config)
- `--output PATH` - Output file path (single incident mode)
- `--incident CODE` - Single incident code to process (e.g., 7_37)
- `--incidents CODES` - Comma-separated incident codes (batch mode)
- `--all-incidents` - Process all incidents found in input directory
- `--delete-source` - Delete source files after successful collation
- `--dry-run` - Preview without creating files
- `--log-level LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)
- `--verbose` - Enable verbose output

**Features:**

- Auto-discovers split files by pattern (e.g., `7_37_Extract*.csv`)
- Removes duplicate headers from split files
- Validates row counts against expected totals
- Supports batch processing of multiple incidents
- Optional deletion of source files after successful collation

**File Pattern Detection:**

Automatically finds files matching patterns:
- `{incident}_Extract1.csv`, `{incident}_Extract2.csv`, etc.
- `{incident}_{fiscal_year}_{quarter}_Extract1.csv`, etc.

**Output:**

- Single collated CSV file per incident
- Processing statistics (files merged, rows collated, etc.)
- Log file with detailed operations

**Example Workflow:**

```bash
# 1. Generate SQL extracts (may create split files)
generate-sql-extract --config config/sql_generator.yaml

# 2. Execute SQL and get results (creates Extract1, Extract2, etc.)
# ... manual SQL execution ...

# 3. Collate split files back together
collate-csv-extracts --input-dir data/sql_results --output-dir data/ready_for_validation

# 4. Run validation on collated file
validate-buyer --reference data/templates/template_7_37.csv \
               --extract data/ready_for_validation/7_37.csv
```

**Configuration Template:**

- `config/templates/accuracy_testing/collate_extracts_template.yaml`

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

### validate-ftbdm

Validate buyer decision maker identification codes (incident 12_17).

**Usage:**

```bash
# Using config file
validate-ftbdm --config config/local/accuracy_testing/ftbdm_validation.yaml

# Using command-line arguments
validate-ftbdm \
  --input data/extracts/12_17_FY26_Q1.csv \
  --output data/validated/validated_FY26_Q1_12_17.csv \
  --lei-data data/reference/lei_lookup.csv

# Preview without writing files
validate-ftbdm --config config/ftbdm.yaml --dry-run

# Verbose output
validate-ftbdm --config config/ftbdm.yaml --verbose
```

**Options:**

- `--config PATH` - Configuration YAML file
- `--input PATH` - Input extract CSV file (overrides config)
- `--output PATH` - Output CSV file (overrides config)
- `--lei-data PATH` - LEI lookup CSV file (Branch Code → LEI mapping)
- `--id-formats PATH` - ID formats CSV file (optional)
- `--log-dir PATH` - Directory for log files
- `--log-level LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)
- `--dry-run` - Preview without writing output
- `--verbose` - Enable verbose output

**Validation Logic:**

- Determines product type from Account ID prefix (AJB, AJBIC, DODL, Custody Solutions)
- Checks if account is SIPP (exempt from validation)
- Validates discretionary accounts (Service Level = "D")
- Looks up LEI from Branch Code
- Validates Decision Maker ID format and type
- Generates corrections in format `{LEI}:L`

**Output (13 columns):**

| Col | Column Name |
|-----|-------------|
| 1 | Transaction Reference |
| 2 | Account ID |
| 3 | Buyer Code |
| 4 | Type of Buyer ID |
| 5 | Buyer DM Code |
| 6 | Type of Buyer DM ID |
| 7 | Product |
| 8 | Account Type |
| 9 | Service Level |
| 10 | Branch Code |
| 11 | Error |
| 12 | Correction |
| 13 | Correction Field |

**Incident Code:**

- 12_17 - Incorrect ID of Buyer Decision Maker

**Configuration Template:**

- `config/templates/accuracy_testing/ftbdm_validation_template.yaml`

---

### validate-ftsdm

Validate seller decision maker identification codes (incident 21_17).

**Usage:**

```bash
# Using config file
validate-ftsdm --config config/local/accuracy_testing/ftsdm_validation.yaml

# Using command-line arguments
validate-ftsdm \
  --input data/extracts/21_17_FY26_Q1.csv \
  --output data/validated/validated_FY26_Q1_21_17.csv \
  --lei-data data/reference/lei_lookup.csv

# Preview without writing files
validate-ftsdm --config config/ftsdm.yaml --dry-run

# Verbose output
validate-ftsdm --config config/ftsdm.yaml --verbose
```

**Options:**

- Same as `validate-ftbdm`

**Validation Logic:**

- Same as buyer decision maker but for seller records
- Output columns use "Seller" instead of "Buyer"

**Output (13 columns):**

| Col | Column Name |
|-----|-------------|
| 1 | Transaction Reference |
| 2 | Account ID |
| 3 | Seller Code |
| 4 | Type of Seller ID |
| 5 | Seller DM Code |
| 6 | Type of Seller DM ID |
| 7 | Product |
| 8 | Account Type |
| 9 | Service Level |
| 10 | Branch Code |
| 11 | Error |
| 12 | Correction |
| 13 | Correction Field |

**Incident Code:**

- 21_17 - Incorrect ID of Seller Decision Maker

**Configuration Template:**

- `config/templates/accuracy_testing/ftsdm_validation_template.yaml`

---

### data-push

Push validated corrections from source files to target template files.
Supports both **single mode** (one file) and **batch mode** (multiple incidents).

**Single Mode:**

```bash
# Using config file
data-push --config config/local/accuracy_testing/data_push.yaml

# Using command-line arguments
data-push \
  --source data/validated/validated_FY26_Q1_7_37.csv \
  --target data/templates/FY26_Q1_7_37.csv \
  --incident 7_37

# Preview changes without modifying files
data-push \
  --source data/validated/validated.csv \
  --target data/templates/template.csv \
  --dry-run

# Skip backup creation
data-push \
  --source data/validated/validated.csv \
  --target data/templates/template.csv \
  --no-backup
```

**Batch Mode:**

```bash
# Process multiple incidents
data-push --batch \
  --source-dir data/validated \
  --target-dir data/templates \
  --fiscal-year FY26 \
  --quarter Q1

# Process specific incidents only
data-push --batch \
  --source-dir data/validated \
  --target-dir data/templates \
  --fiscal-year FY26 \
  --quarter Q1 \
  --incidents "7_37,7_39,16_21"

# Batch mode with dry run
data-push --batch \
  --source-dir data/validated \
  --target-dir data/templates \
  --fiscal-year FY26 \
  --quarter Q1 \
  --dry-run
```

**Options:**

- `--config PATH` - Configuration YAML file
- `--source PATH` - Source CSV file (validated data)
- `--target PATH` - Target CSV file (template to update)
- `--output PATH` - Output file path (defaults to target, overwriting)
- `--incident CODE` - Incident code (e.g., 7_37)
- `--batch` - Enable batch mode
- `--source-dir PATH` - Base directory for source files (batch mode)
- `--target-dir PATH` - Base directory for target files (batch mode)
- `--incidents CODES` - Comma-separated incident codes (batch mode, optional)
- `--fiscal-year YEAR` - Fiscal year (e.g., FY26)
- `--quarter Q` - Quarter (e.g., Q1)
- `--log-level LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)
- `--dry-run` - Preview changes without writing to files
- `--no-backup` - Don't create backup of target file before modifying
- `--verbose` - Enable verbose output

**Push Logic:**

- Matches records by Transaction Reference
- Checks Error flag in source:
  - `Y` = Push all correction columns to target
  - `N` = Push Error flag only (no correction needed)
  - `TBC` = Skip record (needs manual review)
- Creates backup of target file before modification (unless `--no-backup`)

**Configuration Template:**

- `config/templates/accuracy_testing/data_push_template.yaml`

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

Convert XLSX files to CSV format with enhanced features including recursive directory
scanning, filtering by fiscal year/quarter/phase, and robust handling of multi-line
cells.

**Usage:**

```bash
# Using config file (default: config/templates/xlsx_converter_template.yaml)
replay-xlsx-converter --config config/my_config.yaml

# Recursive mode - scan parent directory structure
replay-xlsx-converter \
  --parent-dir /path/to/txr_replay_automation \
  --recursive

# Filter by fiscal year and quarter
replay-xlsx-converter \
  --parent-dir /path/to/txr_replay_automation \
  --filter-year FY25 \
  --filter-quarter Q3

# Filter specific phases
replay-xlsx-converter \
  --parent-dir /path/to/txr_replay_automation \
  --filter-phase phase_ii phase_iii

# Dry run to preview what would be converted
replay-xlsx-converter \
  --parent-dir /path/to/txr_replay_automation \
  --dry-run

# Single directory mode (original behavior)
replay-xlsx-converter \
  --input-dir data/input/xlsx \
  --output-dir data/output/csv
```

**Options:**

- `--config PATH` - Configuration YAML file
  (optional, default: config/templates/xlsx_converter_template.yaml)
- `--mode {1,2}` - Conversion mode: 1=Recursive parent directory, 2=Single directory
- `--parent-dir PATH` - Parent directory to scan recursively (mode 1)
- `--input-dir PATH` - Single directory with XLSX files (mode 2)
- `--output-dir PATH` - Output directory for CSV files (mode 2)
- `--recursive` - Enable recursive scanning of subdirectories
- `--filter-year YEAR` - Filter by fiscal year (e.g., FY25)
- `--filter-quarter Q` - Filter by quarter (e.g., Q3)
- `--filter-phase PHASES` - Filter by phase names (e.g., phase_ii phase_iii reference)
- `--dry-run` - Preview mode - show what would be converted without converting
- `--force` - Overwrite existing CSV files without prompting
- `--log-level LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)

**Features:**

- Recursive directory scanning with filtering
- Handles multi-line cells correctly
- Preserves original file structure when using parent-dir mode
- Fiscal year/quarter/phase filtering for organized processing
- Dry-run mode for previewing conversions
- Detailed logging with progress tracking

**Related:**

- Configuration template: `config/templates/xlsx_converter_template.yaml`

---

## Configuration Files

All commands support configuration files in YAML format. Configuration files allow
you to:

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
- `config/templates/accuracy_template_generator_template.yaml` - Template generator
- `config/templates/sql_extract_generator_template.yaml` - SQL extract generator
- `config/templates/buyer_validation_template.yaml` - Buyer validation config
- `config/templates/seller_validation_template.yaml` - Seller validation config
- `config/templates/pricing_validation_template.yaml` - Pricing validation config
- `config/templates/phase2_template.yaml` - Phase 2 replay config
- `config/templates/phase3_template.yaml` - Phase 3 replay config
- `config/templates/phase3_final_template.yaml` - Phase 3 final config
- `config/templates/xlsx_converter_template.yaml` - XLSX converter config

**Default Configuration Behavior:**

All commands support the `--config` option, but it's optional. If not specified:

- Commands look for default config in `config/templates/[command]_template.yaml`
- Validation/replay commands fall back to `config/local/[category]/[script].yaml`
- You can always override config values with command-line arguments

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
replay-xlsx-converter \
  --input-dir data/input/xlsx \
  --output-dir data/input/csv

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

**Last Updated:** February 3, 2026
**Version:** 1.3
