# ID Validation Guide

## Overview

The ID validation system validates buyer and seller identification codes against format and
logic rules, providing detailed error reporting and automatic correction generation.

## Features

### Format Validation

Validates ID codes against country-specific regular expressions with detailed error messages:

- **Pattern matching**: Checks ID structure against regex patterns
- **Length validation**: Verifies expected character count
- **Character validation**: Ensures valid characters for ID type
- **Detailed error messages**: Provides specific feedback like "Expected 16 characters, got 5"

### Logic Validation

Checks date of birth and gender consistency for supported ID types:

- **Swedish NIDN**: Validates date of birth encoding and gender digit
- **Italian NIDN**: Validates fiscal code structure and gender indicators
- **Estonian NIDN**: Validates date and gender consistency
- **Other types**: Validates logic rules per country specifications

### Italian Tracker Integration

Compares IT NIDNs against confirmed fiscal codes from tracker CSV:

- **Column F**: CS Confirmed Fiscal Code Correct (bare NIDN without ISO-2 prefix)
- **Column G**: Status field (used to skip certain records)
- **Comparison logic**: Prepends "IT" to tracker code and compares with record ID
- **Actions**:
  - `Checked Tracker - NIDN Confirmed`: Tracker matches record
  - `Checked Tracker - NIDN Updated`: Tracker has corrected NIDN
  - `Checked Tracker - Replaced With Fallback`: Record invalid, no tracker match

### Nationality Priority

EEA nationalities are prioritized over ROW (Rest of World), alphabetically sorted within groups:

- **EEA countries**: Austria, Belgium, Bulgaria, Croatia, Cyprus, Czech Republic, Denmark,
  Estonia, Finland, France, Germany, Greece, Hungary, Iceland, Ireland, Italy, Latvia,
  Liechtenstein, Lithuania, Luxembourg, Malta, Netherlands, Norway, Poland, Portugal, Romania,
  Slovakia, Slovenia, Spain, Sweden
- **Priority logic**:
  1. EEA countries sorted alphabetically
  2. ROW countries sorted alphabetically
- **CSV output**: Priority nationality appears in "Primary Nationality" column (swapped if needed)

### Joint Account Aggregation

Automatically aggregates JNT account pairs:

- Identifies records with `Account Type = "JNT"`
- Groups by transaction reference
- Aggregates into single record per transaction
- Reports count of aggregated records in summary

### Error Reporting

Comprehensive error tracking and reporting:

- **By country**: Error counts grouped by ISO-2 country code
- **By ID type**: Error counts grouped by ID type (NIDN, CCPT, CONCAT, etc.)
- **By failure reason**: Detailed breakdown of validation failures
- **Italian tracker actions**: Summary of tracker lookup results
- **Errors-only CSV**: Automatically generated file containing only invalid records

## Installation

### Prerequisites

- Python 3.10 or higher
- Conda environment (recommended)

### Setup

```bash
# Activate conda environment
conda activate txr_automation

# Install package (if not already installed)
pip install -e .

# Optional: Install progress bar support
pip install tqdm
```

## Usage

### Console Commands

#### Buyer ID Validation

```bash
# Basic usage
validate-buyer --config config/buyer_validation.yaml

# Preview without writing output
validate-buyer --config config/buyer_validation.yaml --dry-run

# Show progress bar (requires tqdm)
validate-buyer --config config/buyer_validation.yaml --progress

# Combine options
validate-buyer --config config/buyer_validation.yaml --progress --dry-run
```

#### Seller ID Validation

```bash
# Basic usage
validate-seller --config config/seller_validation.yaml

# With progress bar
validate-seller --config config/seller_validation.yaml --progress
```

### Configuration File

Create a YAML configuration file (e.g., `config/buyer_validation.yaml`):

```yaml
# Input/output paths
input_file: "data/input/buyer_ids.csv"
output_file: "data/output/buyer_ids_validated.csv"

# Italian tracker (optional)
italian_tracker_file: "data/trackers/italian_tracker.csv"

# Template lookup (optional)
template_file: "data/templates/incident_template.csv"

# Logging
log_output: "logs"
log_level: "INFO"
```

### Input CSV Format

The input CSV must contain these columns:

1. **Transaction Reference**: Unique transaction identifier
2. **Person Code**: Client person code
3. **Account Type**: Account type (IND, JNT, etc.)
4. **ID Value**: The identification code to validate
5. **ID Type**: Type of ID (NIDN, CCPT, CONCAT, etc.)
6. **First Name**: Client first name
7. **Surname**: Client surname
8. **Date of Birth**: Client date of birth (format: DD/MM/YYYY)
9. **Gender**: Client gender (M/F)
10. **Primary Nationality**: Primary nationality (ISO-2 code)
11. **Secondary Nationality**: Secondary nationality (ISO-2 code, optional)

### Output CSV Format

The output CSV contains all input columns plus:

- **Correction Output**: Corrected ID in format "ID:TYPE"
- **Correction Fields**: Fields that were corrected
- **Tracker Status**: Italian tracker lookup status (if applicable)
- **Pass/Fail**: Validation status (Format/Logic)
- **Failure Reason**: Specific reason for validation failure
- **Actions Taken**: Processing actions performed
- **Error**: Error flag (Y/N)
- **Kaizen Error**: Template lookup result
- **Match**: Match status (TRUE/FALSE)

### Errors-Only CSV

Automatically generated when errors exist:

- **Filename**: `{output_file}_errors_only.csv`
- **Content**: Only records that failed validation
- **Format**: Identical to main output CSV
- **Purpose**: Easy review of validation failures

## Error Messages

### Format Errors

Detailed error messages explain validation failures:

- `"Expected 16 characters, got 5"`: Length mismatch
- `"Expected format: XX followed by 10 digits"`: Pattern mismatch
- `"Invalid characters in position 3-5"`: Character validation failure
- `"Missing required prefix 'IT'"`: Prefix validation failure

### Logic Errors

Logic validation failures explain mismatches:

- `"Date of birth does not match encoded date in NIDN"`: DOB mismatch
- `"Gender indicator does not match client gender"`: Gender mismatch
- `"Invalid century marker for birth year"`: Century logic error
- `"Checksum validation failed"`: Checksum mismatch

## Italian Tracker

### File Format

The Italian tracker CSV must contain:

- **Column F**: CS Confirmed Fiscal Code Correct (bare fiscal code without "IT" prefix)
- **Column G**: Status (used to skip certain records)

### Lookup Logic

1. Read tracker CSV and build lookup dictionary
2. For each IT NIDN record:
   - Extract fiscal code from record ID (remove "IT" prefix)
   - Look up fiscal code in tracker
   - Compare tracker code with record code
3. Generate action message:
   - `Checked Tracker - NIDN Confirmed`: Match found
   - `Checked Tracker - NIDN Updated`: Corrected code found
   - `Checked Tracker - Replaced With Fallback`: No match, used fallback

### Status Field Handling

Records with certain status values are skipped during tracker lookup:

- Status field checked before comparison
- Prevents false corrections from stale tracker data

## Summary Statistics

The validation process outputs detailed statistics:

### Record Counts

- **Total records processed**: Count of all input records
- **Valid records**: Count passing all validations
- **Invalid records**: Count failing any validation
- **Invalid format**: Count failing format validation
- **Invalid logic**: Count failing logic validation
- **JNT aggregated**: Count of JNT pairs aggregated

### Error Breakdown

- **By country**: Error counts per ISO-2 code
- **By ID type**: Error counts per ID type
- **By failure reason**: Error counts per failure reason

### Italian Tracker Actions

- **NIDN Confirmed**: Count of tracker matches
- **NIDN Updated**: Count of tracker corrections
- **Replaced With Fallback**: Count of fallback replacements

## Performance

### Processing Speed

- **Small files** (< 1000 records): < 1 second
- **Medium files** (1000-10,000 records): 1-10 seconds
- **Large files** (10,000+ records): 10+ seconds

### Optimization Tips

1. Use `--progress` flag to monitor long-running processes
2. Use `--dry-run` to preview changes before processing
3. Process in batches if files are very large
4. Ensure Italian tracker is indexed for fast lookups

## Troubleshooting

### Common Issues

#### "No module named 'tqdm'"

Solution: Install tqdm for progress bar support:

```bash
pip install tqdm
```

Or run without `--progress` flag.

#### "Italian tracker file not found"

Solution: Ensure tracker file path in config is correct:

```yaml
italian_tracker_file: "data/trackers/italian_tracker.csv"
```

#### "Encoding error reading input CSV"

Solution: The system automatically detects encoding. If issues persist, convert file to UTF-8.

#### "Invalid YAML configuration"

Solution: Check YAML syntax, ensure proper indentation and quoting.

### Debug Mode

Enable debug logging for troubleshooting:

```yaml
log_level: "DEBUG"
```

Or use command-line override:

```bash
validate-buyer --config config.yaml --log-level DEBUG
```

## Examples

### Example 1: Basic Validation

```bash
validate-buyer --config config/buyer_validation.yaml
```

Output:

```text
========================================
BUYER ID VALIDATION v3.0
========================================
Input file: data/input/buyer_ids.csv
Output file: data/output/buyer_ids_validated.csv
Start time: 2024-01-15 10:30:00

========================================
PROCESSING RECORDS
========================================
Successfully read 1000 records
Processing records...

Writing errors-only CSV (45 error records)...

========================================
PROCESSING COMPLETE
========================================
End time: 2024-01-15 10:30:05
Duration: 0:00:05

Processing Statistics:
  Total records: 1000
  Valid records: 955 (95.5%)
  Invalid records: 45 (4.5%)
    Invalid format: 30
    Invalid logic: 15
  JNT aggregated: 20

Error Breakdown by Country:
  IT: 20 errors
  SE: 15 errors
  GB: 10 errors

Error Breakdown by Type:
  NIDN: 35 errors
  CCPT: 10 errors

Italian Tracker Actions:
  Checked Tracker - NIDN Confirmed: 150
  Checked Tracker - NIDN Updated: 30
  Checked Tracker - Replaced With Fallback: 5
```

### Example 2: Dry Run

```bash
validate-buyer --config config/buyer_validation.yaml --dry-run
```

Output:

```text
*** DRY RUN MODE - No output file will be written ***
...
Dry run mode - skipping output file write
Would have written 1000 records to: data/output/buyer_ids_validated.csv
Sample output (first record):
  ID: IT12345678901 (NIDN)
  Correction: None
  Actions: Checked Tracker - NIDN Confirmed
  Status: Format=Pass, Logic=Pass
```

### Example 3: With Progress Bar

```bash
validate-buyer --config config/buyer_validation.yaml --progress
```

Output:

```text
Processing records: 100%|████████████████████| 1000/1000 [00:05<00:00, 200rec/s]
```

## Best Practices

1. **Always use dry-run first**: Preview changes before processing
2. **Review errors-only CSV**: Focus on validation failures
3. **Monitor summary statistics**: Track validation rates over time
4. **Keep tracker updated**: Ensure Italian tracker is current
5. **Use progress bar for large files**: Monitor processing status
6. **Enable debug logging for troubleshooting**: Detailed diagnostic information
7. **Validate configuration before processing**: Test with small sample first

## Reference

### Supported ID Types

- **NIDN**: National Identification Number
- **CCPT**: Passport
- **CONCAT**: Concatenated ID (fallback)
- **ARNU**: Registration Number
- **TXID**: Tax ID
- **NRIN**: National Registration Number
- **LEIX**: Legal Entity Identifier

### Supported Countries

See [country_codes.csv](../reference_data/country_codes.csv) for full list of supported countries.

### ID Format Patterns

See [id_formats.csv](../reference_data/id_formats.csv) for regex patterns and validation rules per country.
