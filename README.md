<!-- # txr_automation -->

## Overview

### Purpose

This project consolidates the automation of transaction reporting, migrating from VBA macros to Python.

### Problem Statement

The migration is happening for ease of:

- **Maintainability**: Many automations share common functions, and it is easier to apply changes when all code is written in the same language.
- **Scalability**: The medium-term plan is to build a simple application, a Transaction Reporting tool, which will allow the team to carry out all automated reporting tasks through one streamlined channel.

### Scope

The processes being automated are:

#### Quarterly Accuracy Testing

- **Extract Generation**: Generating SQL queries by inserting transaction references provided by the user into a preset query template.
- **Report Validation**: Testing reporting data against format and logic conditions, and generating any data corrections.
- **Result Outputs**: Creation of final testing results files to be sent to a third party for upload to the Approved Reporting Mechanism (ARM).

#### Quarterly Replay

- **Data Comparison**: Comparison of third-party upload files against quarterly accuracy testing results, with corrections made to the upload files where inconsistencies exist.

## Current Status

### Migration Progress

Currently, only the replay processes are Python-based, with all of the accuracy testing still to be migrated.

### Active Components

- **VBA Macros**: Legacy components to be deprecated.
- **Python Scripts**: Current state of the replay processes and target state of the accuracy testing processes.

## Project Structure

```markdown
txr_automation/
├── src/                          # All source code
│   ├── txr_replay_core/         # Shared core library
│   │   ├── data_structures.py   # Common dataclasses
│   │   ├── utils.py             # Utility functions
│   │   ├── config.py            # Configuration management
│   │   ├── logger.py            # Structured logging
│   │   └── README.md
│   ├── replay/                   # Replay processing scripts
│   │   ├── phase_2_processor.py
│   │   ├── phase_3_processor.py
│   │   └── phase_3_final_lookup.py
│   ├── accuracy_testing/         # Accuracy testing (VBA conversions)
│   │   ├── validation/          # ID validation scripts
│   │   ├── extracts/            # SQL extract generators
│   │   └── pricing/             # Pricing validation
│   └── utils/                    # Standalone utilities
│       └── xlsx_csv_converter.py
├── tests/                        # Test suite
│   ├── test_core/               # Core library tests (35 tests)
│   ├── test_replay/             # Replay script tests
│   └── test_accuracy_testing/   # Accuracy testing tests
├── config/                       # Configuration files
│   ├── templates/               # Template configurations
│   │   ├── phase2_template.yaml
│   │   ├── phase3_template.yaml
│   │   └── phase3_final_template.yaml
│   └── environments/            # Environment-specific configs
├── documentation/
│   ├── reference_data/          # CSV reference files
│   │   ├── country_codes.csv
│   │   ├── id_formats.csv
│   │   └── incident_fields.csv
│   ├── planning/                # Planning documents
│   │   ├── Python_Migration_Plan.md
│   │   ├── Existing_Python_Scripts_Refactoring_Plan.md
│   │   └── Phase_0_Progress.md
│   └── guides/                  # User guides
│       ├── Git_Branching_Guide.md
│       ├── Quick_Start_Guide.md
│       └── Git_Workflow_Summary.md
├── legacy/                      # Legacy code (archived)
│   └── vba/                    # VBA macros for reference
├── scripts/                     # Build/deployment scripts
│   ├── run_tests.sh
│   └── run_tests_with_coverage.sh
├── .gitignore
├── setup.py
├── requirements.txt
└── README.md
```

## Key Components

### VBA Modules (Legacy)

#### ID Validation

- **BuyerIDValidation5_6.vb**: Validates buyer identification codes against format and logic rules. Supports joint account aggregation, Swedish century logic for NIDN IDs, CONCAT generation, and template-based incident code lookups.
- **SellerIDValidation5_6.vb**: Validates seller identification codes with similar functionality to buyer validation. Includes template lookup enhancements for quarterly accuracy testing.

#### Inconsistent ID Handling

- **InconsistentBuyerIDValidation1_3.vb**: Identifies and corrects inconsistent buyer IDs across records with the same Person Code. Groups records chronologically and applies validation logic to detect invalid IDs that differ over time.
- **InconsistentSellerIDValidation1_3.vb**: Identifies and corrects inconsistent seller IDs using the same methodology as the buyer version.

#### SQL Extract Generators

- **ExtractBuyerID4_1.vb**: Generates SQL query files for extracting buyer identification data from the reporting database. Batches transaction references into groups of 900 for database optimization.
- **ExtractInconsistentBuyerID1_0.vb**: Generates SQL extracts specifically for inconsistent buyer ID testing scenarios.
- **SCR_extract_generator_v1_0.vb**: Generates SQL extracts for Securities Collateral Registry (SCR) pricing data validation.

#### Data Operations

- **DataPush1_0.vb**: Pushes validated data from current workbook to target validation workbooks, updating specific columns based on transaction reference matches.
- **IncidentLookup1_1.vb**: Performs transaction reference lookups in validation workbooks and returns specified columns based on incident codes.

#### Field-Specific Validation

- **ValidateFTBDM3_0.vb**: Validates First Time Buyer Decision Maker codes for compliance with regulatory requirements.
- **ValidateFTSDM3_0.vb**: Validates First Time Seller Decision Maker codes for compliance with regulatory requirements.
- **pricing_data_validation_v1.0.vb**: Validates pricing data by checking net amount, consideration amount, and interest amount calculations.

### Python Scripts (Current)

#### Accuracy Testing

**Buyer and Seller ID Validation** (Migrated from VBA v5.6):

- **buyer_id_validation.py**: Validates buyer identification codes against format and logic rules
- **seller_id_validation.py**: Validates seller identification codes with identical functionality

Features:

- **Format Validation**: Validates ID codes against country-specific regular expressions with detailed error messages
- **Logic Validation**: Checks date of birth and gender consistency for supported ID types
- **Italian Tracker Integration**: Compares IT NIDNs against confirmed fiscal codes from tracker CSV
- **Nationality Priority**: EEA nationalities prioritized over ROW, alphabetically sorted within groups
- **Joint Account Aggregation**: Automatically aggregates JNT account pairs
- **Swedish Century Logic**: Applies century markers for SE NIDN IDs based on date of birth
- **CONCAT Generation**: Creates CONCAT IDs when valid format unavailable
- **Template Lookups**: Incident code lookups for error flagging
- **Error Reporting**:
  - Detailed breakdowns by country, ID type, and failure reason
  - Automatic generation of errors-only CSV for easy review
  - Summary statistics including Italian tracker actions

Console Commands:

```bash
# Validate buyer IDs
validate-buyer --config config.yaml

# Validate seller IDs
validate-seller --config config.yaml

# Preview changes without writing output
validate-buyer --config config.yaml --dry-run

# Show progress bar during processing
validate-buyer --config config.yaml --progress
```

Output Files:

- Main output: `{output_file}.csv` - All records with validation results
- Errors only: `{output_file}_errors_only.csv` - Only invalid records for review

#### Phase 2 Processor

- **phase_2_processor_v3_1.py**: Ultra-optimized processor for Phase II replay files using transaction reference lookups. Features hash table indexing for O(1) lookup performance, character encoding handling, and batch processing capabilities.

#### Phase 3 Processors

- **phase_3_processor_v4_2.py**: Ultra-optimized Phase III processor with client record matching using first name, surname, date of birth, and ID value. Implements sophisticated fuzzy matching algorithms, date parsing with multiple format support, and comprehensive error flagging.
- **phase_3_final_lookup.py**: Validates client corrections in replay files against UnaVista transaction data. Performs final verification that proposed corrections match the source reporting data before submission.

#### Utilities

- **xlsx_csv_converter.py**: Converts Excel files to CSV format and handles multi-line cells by splitting them into separate rows.

### Core Library (NEW - Phase 0)

The `src/txr_replay_core` package provides shared functionality across all processing scripts:

- **data_structures.py**: Common dataclasses (ReplayRecord, LookupResult, UnaVistaTransaction, ProcessingStats)
- **utils.py**: Utility functions including DateParser (with caching), CharacterReplacement, and FileDiscovery
- **config.py**: Configuration management supporting YAML files and environment variables
- **logger.py**: Structured logging with file and console output

**Status**: ✅ Complete and tested (35 tests, 100% pass rate)

### Reference Data

Located in the `documentation/reference_data/` folder:

- **country_codes.csv**: ISO country code mappings for nationality validation.
- **id_formats.csv**: Regular expression patterns and validation rules for different ID types (NIDN, CCPT, CONCAT, etc.) across various countries.
- **incident_fields.csv**: Field definitions and incident code mappings for template-based lookups.

## Installation

### Prerequisites

- Python 3.10 or higher
- Conda (required for production environments)

### Setup with Conda (Recommended)

1. **Clone the repository**:

   ```bash
   cd /path/to/txr_automation
   ```

2. **Create and activate Conda environment**:

   ```bash
   conda env create -f environment.yml
   conda activate txr_automation
   ```

   Or use the setup script:

   ```bash
   ./scripts/setup_conda_env.sh
   conda activate txr_automation
   ```

3. **Run tests**:

   ```bash
   python -m pytest tests/test_core/ -v
   ```

### Alternative: Setup with pip/UV (Development Only)

For development on machines without SSL restrictions:

1. **Install with UV**:

   ```bash
   uv pip install -e .
   uv pip install pytest pytest-cov black flake8 mypy
   ```

   Or with pip:

   ```bash
   pip install -e .
   pip install pytest pytest-cov black flake8 mypy
   ```

2. **Run tests**:

   ```bash
   python -m pytest tests/test_core/ -v
   ```

### Configuration

1. **Copy and customize configuration templates**:

   ```bash
   # Ensure conda environment is activated
   conda activate txr_automation
   
   # Copy templates
   cp config/templates/phase2_template.yaml config/environments/phase2.yaml
   cp config/templates/phase3_template.yaml config/environments/phase3.yaml
   cp config/templates/phase3_final_template.yaml config/environments/phase3_final.yaml
   ```

2. **Edit the YAML files** with your specific paths, or use environment variables:

   ```bash
   export TXR_REPLAY_INPUT=/path/to/input
   export TXR_INCIDENT_FILES=/path/to/incident
   export TXR_REPLAY_OUTPUT=/path/to/output
   export TXR_LOG_OUTPUT=/path/to/logs
   export TXR_LOG_LEVEL=INFO
   ```

## Development Status

### Git Workflow

This project uses feature branches to organize work:

- **`main`**: Stable, production-ready code
- **`phase0-refactoring`**: All replay script refactoring work (current)
- **`vba-migration`**: VBA conversion work (created after Phase 0)

See [Git_Branching_Guide.md](documentation/guides/Git_Branching_Guide.md) for detailed workflow instructions.

**Quick Start:**

```bash
# Create Phase 0 branch (if not already created)
git checkout -b phase0-refactoring
git push -u origin phase0-refactoring
```

### Phase 0: Refactoring (In Progress)

**Week 1** ✅ Complete:

- Created `txr_replay_core` shared library
- Implemented configuration management
- Implemented structured logging
- Created 35 unit tests (100% pass rate)
- Documentation and templates

**Week 2-4** (Upcoming):

- Refactor Phase 2 Processor
- Refactor Phase 3 Processor
- Refactor Phase 3 Final Lookup
- Add CLI interfaces to all scripts

**Week 5-8** (Upcoming):

- Integration testing
- Performance benchmarking
- Documentation updates
- User acceptance testing

See [Phase_0_Progress.md](documentation/planning/Phase_0_Progress.md) for detailed progress.

### Phase 1-7: VBA Migration (Planned)

After Phase 0 completes, VBA macros will be migrated to Python. See [Python_Migration_Plan.md](documentation/planning/Python_Migration_Plan.md) for details.
