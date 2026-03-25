# TXR Automation

**Transaction Reporting Automation Suite — VBA to Python Migration**

**Version:** 3.0.0
**Last Updated:** 25 March 2026
**Status:** All VBA migration complete (Phases 0–5). Phase 6 (Integration & Testing) in progress.

---

## Overview

TXR Automation consolidates transaction reporting processes into a unified Python suite, replacing 12 legacy VBA macros. The system validates financial transaction data for UK MiFIR/RTS 22 regulatory compliance, covering buyer/seller identification, decision maker validation, pricing checks, and replay processing.

### Key Capabilities

- **Accuracy Testing** — Validate ID formats/logic across 68 country-specific patterns, decision maker codes, pricing formulae, and net amount/quantity netting
- **SQL Extract Generation** — Batch and single-mode SQL query generation with AS/400 DTF support
- **Data Push** — Push validated corrections to master tracking files
- **Replay Processing** — Phase 2 (transaction reference matching) and Phase 3 (client record matching with fuzzy logic)
- **FIRDS Reportability** — Local SQLite cache of FCA FIRDS data for MiFIR reportability determination
- **GLEIF LEI Lookup** — Local SQLite cache of GLEIF Golden Copy for LEI validation and entity lookup
- **Desktop GUI** — PySide6 application with tabbed interface for all modules

### Migration Summary

All 12 VBA macros have been successfully migrated to Python. See the [full documentation](documentation/confluence/00_index.html) for comprehensive project details.

| Metric | Value |
|--------|-------|
| VBA macros migrated | 12/12 (100%) |
| Python packages | 7 (core, accuracy_testing, replay, firds, gleif, gui, utils) |
| Console scripts | 22 registered entry points |
| Test suite | 466 tests, 100% pass rate |
| ID format patterns | 68 regex patterns across 27 countries |
| ID logic validators | 15 country-specific embedded logic checks |

---

## Project Structure

```text
txr_automation/
├── src/
│   ├── core/                      # Shared foundation library
│   │   ├── config/                # YAML + env var configuration management
│   │   ├── data/                  # Country codes, ID formats, incident codes, constants
│   │   ├── logging/               # Structured JSON logging
│   │   ├── utils/                 # Date parsing, CSV utilities, file discovery
│   │   └── validation/            # Core validation functions
│   ├── accuracy_testing/          # Accuracy testing validation suite
│   │   ├── core/                  # Wrappers for core library exports
│   │   ├── models/                # Dataclasses (ClientRecord, PricingRecord, etc.)
│   │   ├── scripts/               # 15 CLI entry points
│   │   ├── validators/            # Validation logic (DM, pricing, net amt/qty, data push)
│   │   ├── sql_templates/         # 11 SQL templates + 1 DTF template
│   │   ├── processor.py           # Main ID validation processor (2,600 LOC)
│   │   └── id_logic_validator.py  # Embedded ID logic validation (15 countries)
│   ├── replay/                    # Replay processing (Phase 2, Phase 3)
│   ├── firds/                     # FCA FIRDS reportability (API + SQLite cache)
│   ├── gleif/                     # GLEIF LEI lookup (API + SQLite cache)
│   ├── gui/                       # PySide6 desktop application
│   └── utils/                     # Standalone utilities (XLSX→CSV converter)
├── tests/                         # 466 tests across 7 test directories
│   ├── test_accuracy_testing/     # Accuracy testing tests (20 files)
│   ├── test_core/                 # Core library tests (5 files)
│   ├── test_replay/               # Replay processor tests
│   ├── test_firds/                # FIRDS module tests (5 files)
│   ├── test_gleif/                # GLEIF module tests (5 files)
│   └── integration/               # End-to-end workflow tests (6 files)
├── config/
│   ├── templates/                 # YAML config templates (version-controlled)
│   └── local/                     # User-specific configs (gitignored)
├── legacy/vba/                    # Original 12 VBA macros (read-only reference)
├── documentation/
│   ├── confluence/                # Comprehensive HTML documentation suite
│   ├── guides/                    # User guides (Markdown)
│   ├── planning/                  # Migration planning documents
│   ├── reference/                 # Architecture reviews, command references
│   └── reference_data/            # ESMA CID patterns, incident fields, UK MiFIR fields
├── scripts/                       # Build, test, and benchmark scripts
├── setup.py                       # Package setup with 22 console script entry points
├── environment.yml                # Conda environment specification
└── requirements.txt               # pip dependency reference
```

---

## Quick Start

### Prerequisites

- Python 3.10+
- Conda (recommended) or pip

### Installation

```bash
# Clone and set up environment
conda env create -f environment.yml
conda activate txr_automation

# Install in editable mode (registers all 22 console scripts)
pip install -e .

# Verify installation
python -m pytest tests/ -v
```

### Running Scripts

```bash
# Accuracy testing — validate buyer IDs
validate-buyer --config config/templates/accuracy_testing/buyer_id_template.yaml

# Generate SQL extracts in batch mode
generate-sql-extract --config config/templates/accuracy_testing/sql_extract_batch_template.yaml

# Push results to master tracking files
data-push --config config/templates/accuracy_testing/data_push_template.yaml

# Replay processing
replay-phase2 --config config/templates/replay/phase2_template.yaml

# FIRDS — refresh cache and check reportability
firds-refresh --config config/local/firds_config.yaml
firds-check --isin GB00B0SWJX34

# GLEIF — refresh cache and look up LEI
gleif-refresh --config config/local/gleif_config.yaml
gleif-check --lei 549300EXAMPLE000LEI00

# Launch desktop GUI
txr-gui
```

### Configuration

The system uses a priority cascade: **Environment variables** (`TXR_*`) → **YAML files** → **Defaults**.

Config templates are in `config/templates/`. Copy to `config/local/` and customise for your environment:

```bash
cp config/templates/accuracy_testing/buyer_id_template.yaml config/local/accuracy_testing/buyer_id.yaml
```

See the [Configuration Guide](documentation/guides/Accuracy_Testing_Configuration_Guide.md) for full details.

---

## Console Scripts

| Category | Command | Description |
|----------|---------|-------------|
| **Accuracy** | `validate-buyer` | Buyer ID format & logic validation |
| | `validate-seller` | Seller ID format & logic validation |
| | `validate-inconsistent-buyer` | Inconsistent buyer ID detection |
| | `validate-inconsistent-seller` | Inconsistent seller ID detection |
| | `validate-ftbdm` | Buyer decision maker validation |
| | `validate-ftsdm` | Seller decision maker validation |
| | `validate-pricing` | Pricing formula validation |
| | `validate-non-zero-net-qty` | Net quantity netting validation |
| | `validate-non-zero-net-amt` | Net amount netting validation |
| | `validate-all` | Run all validations in sequence |
| | `generate-sql-extract` | SQL extract generation (batch/single) |
| | `generate-accuracy-template` | Accuracy testing template generation |
| | `collate-csv-extracts` | Collate CSV extract files |
| | `data-push` | Push corrections to tracking files |
| **Replay** | `replay-phase2` | Phase 2 transaction reference matching |
| | `replay-phase3` | Phase 3 client record matching |
| | `replay-phase3-final` | Phase 3 final lookup validation |
| | `merge-inconsistent-summaries` | Merge inconsistent ID summaries |
| **FIRDS** | `firds-refresh` | Refresh FIRDS SQLite cache |
| | `firds-check` | Check instrument reportability |
| | `firds-backfill` | Backfill historical FIRDS data |
| **GLEIF** | `gleif-refresh` | Refresh GLEIF SQLite cache |
| | `gleif-check` | Look up LEI details |
| | `gleif-backfill` | Backfill GLEIF data |
| **GUI** | `txr-gui` | Launch desktop application |

---

## Documentation

Comprehensive documentation is available in the `documentation/confluence/` directory as HTML files structured for Confluence import. Key documents:

- **[Project Overview](documentation/confluence/01_project_overview.html)** — Executive summary, scope, and status
- **[System Architecture](documentation/confluence/02a_system_architecture.html)** — Layered architecture, module design, patterns
- **[Migration Traceability](documentation/confluence/03b_traceability_matrix.html)** — VBA-to-Python function mapping for audit
- **[Developer Guide](documentation/confluence/04a_getting_started.html)** — Environment setup, coding standards, testing
- **[CLI Reference](documentation/confluence/05j_cli_command_reference.html)** — Complete command-line reference

See also: [Quick Start Guide](documentation/guides/Quick_Start_Guide.md) | [Configuration Guide](documentation/guides/Accuracy_Testing_Configuration_Guide.md) | [Command Reference](documentation/reference/Command_Reference.md)

---

## Development

### Testing

```bash
# Full test suite
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ --cov=src --cov-report=term-missing

# Specific module
python -m pytest tests/test_accuracy_testing/ -v
```

### Code Quality

```bash
# Formatting
black src/ tests/

# Linting
flake8 src/ tests/

# Type checking
mypy src/
```

### Git Workflow

- **`main`** — Stable, production-ready code
- **`vba-migration`** — Active migration work
- **Commit format:** `type(scope): description` (e.g., `feat(accuracy): add seller ID validation`)

---

## Licence

Internal use only. All rights reserved.
