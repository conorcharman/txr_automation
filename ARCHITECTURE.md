# TXR Automation - System Architecture

**Version:** 3.0  
**Last Updated:** 25 March 2026  
**Status:** Post-VBA Migration — All 12 macros migrated, Phase 6 in progress

---

## Executive Summary

The Transaction Reporting (TXR) Automation system provides validation and processing capabilities for financial transaction data, specifically focused on buyer/seller identification and decision maker validation for regulatory reporting compliance.

**Key Facts:**
- **Migrated from:** 12 VBA macros (Excel-based) — all complete
- **Current stack:** Python 3.10+, pandas, PySide6, CSV-based processing, SQLite caching
- **Packages:** 7 (core, accuracy_testing, replay, firds, gleif, gui, utils)
- **Console scripts:** 22 registered entry points + 1 GUI entry point
- **Current scale:** 20,000 records quarterly
- **Target scale:** 1.5M records daily
- **Test coverage:** 466 passing tests (100% pass rate as of 2026-03-25)

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Module Architecture](#module-architecture)
3. [Configuration Management](#configuration-management)
4. [Data Flow](#data-flow)
5. [Deployment Architecture](#deployment-architecture)
6. [Testing Strategy](#testing-strategy)
7. [Performance Characteristics](#performance-characteristics)
8. [Design Principles](#design-principles)

---

## 1. System Overview

### 1.1 Purpose

The system validates and corrects transaction reporting data for regulatory compliance (ESMA/FCA requirements), focusing on:

- **Buyer/Seller ID Validation:** Ensures identification codes (LEI, NIDN, CONCAT, etc.) are correctly formatted and logically valid
- **Decision Maker Validation:** Validates that discretionary accounts have correct decision maker codes
- **Pricing Validation:** Validates transaction pricing calculations
- **Data Quality:** Automates error detection and correction suggestions

### 1.2 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   User Interface Layer                       │
│  • CLI Scripts (22 console commands)                         │
│  • PySide6 Desktop GUI (txr-gui)                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                  Processing Layer                            │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ accuracy_testing │  │     replay       │                 │
│  │  • ID validation │  │  • Phase 2/3     │                 │
│  │  • DM validation │  │  • Processing    │                 │
│  │  • Pricing       │  └──────────────────┘                 │
│  │  • Net amt/qty   │                                        │
│  │  • Data push     │  ┌──────────────────┐                │
│  │  • SQL extracts  │  │  firds / gleif   │                 │
│  └──────────────────┘  │  • API clients   │                 │
│                         │  • SQLite cache  │                 │
│                         │  • Lookup/check  │                 │
│                         └──────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   Core Library (txr_core)                    │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   config    │  │     data     │  │  validation  │        │
│  │  • YAML     │  │ • Countries  │  │  • ID rules  │        │
│  │  • Env vars │  │ • ID formats │  │  • Formats   │        │
│  └─────────────┘  │ • Incidents  │  └──────────────┘        │
│                    │ • Constants  │                           │
│  ┌─────────────┐  └──────────────┘                          │
│  │   logging   │  ┌──────────────┐                          │
│  │  • Struct.  │  │    utils     │                           │
│  │  • JSON     │  │  • CSV       │                           │
│  └─────────────┘  │  • Date      │                           │
│                    │  • Files     │                           │
│                    └──────────────┘                           │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                     Data Layer                               │
│  • CSV files (input/output)                                  │
│  • SQLite databases (FIRDS instruments, GLEIF LEI records)   │
│  • Reference data (country codes, ID formats, LEI lookups)   │
│  • YAML configuration files                                  │
│  • Logs (JSON structured logging)                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Module Architecture

### 2.1 Core Module (`src/core/`)

**Purpose:** Shared foundation library providing configuration, data management, and utilities.

**Key Components:**

```
core/
├── config/
│   └── config_manager.py      # Unified configuration management
├── data/
│   ├── country_codes.py        # ISO 3166-1 country reference data
│   └── id_formats.py           # ID format regex patterns (68 patterns)
├── logging/
│   └── structured_logger.py    # JSON structured logging
├── utils/
│   ├── csv_utils.py            # Safe CSV operations
│   ├── date_parser.py          # Date parsing/formatting
│   └── file_discovery.py       # File discovery utilities
└── validation/
    └── validators.py           # Core validation functions
```

**Design Patterns:**
- **Singleton:** `IDFormatManager`, `CountryDataManager` are singletons
- **Factory:** `create_logger()` factory for logger instances
- **Configuration Cascade:** Environment variables → YAML → defaults

### 2.2 Accuracy Testing Module (`src/accuracy_testing/`)

**Purpose:** Buyer/seller ID validation and decision maker validation workflows.

**Key Components:**

```
accuracy_testing/
├── processor.py                      # Main ID validation processor
├── id_logic_validator.py             # Business logic validation
├── core/                             # accuracy_testing-specific utilities
│   ├── country_codes.py              # Wrapper for core country data
│   ├── id_formats.py                 # Wrapper for core ID formats
│   └── validators.py                 # Accuracy-specific validators
├── models/
│   ├── decision_maker_record.py      # Decision maker data model
│   └── data_push_record.py           # Data push data model
├── validators/
│   ├── decision_maker_validator.py   # DM validation logic
│   └── data_push_processor.py        # Push validated data to templates
└── scripts/
    ├── buyer_id_validation.py        # Buyer ID validation CLI
    ├── seller_id_validation.py       # Seller ID validation CLI
    ├── validate_ftbdm.py              # Fund trade buyer DM validation
    ├── validate_ftsdm.py              # Fund trade seller DM validation
    └── ... (additional scripts)
```

**Key Classes:**

- **`ClientRecord`:** Dataclass for buyer/seller identification records
- **`IDValidationProcessor`:** Core processing engine for ID validation
- **`DecisionMakerValidator`:** Validates decision maker codes for discretionary accounts
- **`DataPushProcessor`:** Pushes validated corrections to master tracking files

### 2.3 Replay Module (`src/replay/`)

**Purpose:** Transaction replay processing workflows (Phase 2 and Phase 3).

**Key Scripts:**
- `phase_2_processor.py` (v4.2): Phase 2 transaction reference matching with hash table indexing
- `phase_3_processor.py` (v5.2): Phase 3 client record matching with fuzzy logic
- `phase_3_final_lookup.py`: UnaVista transaction validation
- `merge_inconsistent_ids.py`: Merge duplicate rows in inconsistent summaries

### 2.4 FIRDS Module (`src/firds/`)

**Purpose:** Local-cache-based access to FCA Financial Instruments Reference Data System (FIRDS) for automated reportability determination under UK MiFIR.

**Architecture:** API client → Downloader → XML parser → SQLite cache → Reportability checker

**Key Components:**

```
firds/
├── client.py              # FCA API client (FULINS/DLTINS/FULCAN files)
├── downloader.py          # File download with extraction
├── parser.py              # Streaming XML parser (memory-efficient iterparse)
├── cache.py               # SQLite cache (instruments table, sync log)
├── refresher.py           # Full + delta refresh orchestration
├── reportability.py       # Reportability determination logic
└── scripts/
    ├── refresh_cache.py   # CLI: firds-refresh
    ├── check_reportability.py  # CLI: firds-check
    └── backfill.py        # CLI: firds-backfill
```

**Key Classes:**
- **`FirdsApiClient`:** Queries FCA FIRDS API for instrument file listings
- **`FirdsCacheManager`:** SQLite database with upsert, termination, and cancellation support
- **`FirdsXmlParser`:** Streaming XML parser for FULINS/DLTINS/FULCAN files
- **`FirdsRefresher`:** Orchestrates full weekly rebuilds and daily delta refreshes
- **`FirdsReportabilityChecker`:** Determines whether an ISIN is reportable at a given trade date

### 2.5 GLEIF Module (`src/gleif/`)

**Purpose:** Local-cache-based access to GLEIF Golden Copy data for LEI validation, entity name lookup, and ISIN-to-LEI mapping.

**Architecture:** API client → Downloader → CSV parser → SQLite cache → Lookup (with FTS5 full-text search)

**Key Components:**

```
gleif/
├── client.py              # GLEIF API client (LEI lookup, ISIN mapping)
├── downloader.py          # Golden Copy download with extraction
├── parser.py              # Streaming CSV parser (3.2M records)
├── cache.py               # SQLite cache (lei_records, lei_isin_map, FTS5)
├── refresher.py           # Full + delta refresh (8h/24h/7d/31d cycles)
├── lookup.py              # LEI validation and entity lookup logic
└── scripts/
    ├── refresh_cache.py   # CLI: gleif-refresh
    ├── check_lei.py       # CLI: gleif-check
    └── backfill.py        # CLI: gleif-backfill
```

**Key Classes:**
- **`GleifApiClient`:** Queries GLEIF API v1 for LEI records, ISIN mappings, BIC lookups
- **`GleifCacheManager`:** SQLite with FTS5 full-text search over legal names
- **`GleifCsvParser`:** Streaming parser for 3.2M-record Golden Copy CSV
- **`GleifRefresher`:** Full rebuild + delta refresh (8h, 24h, 7d, 31d cycles)
- **`GleifLookup`:** LEI validation with registration status checking and trade-date awareness

### 2.6 GUI Module (`src/gui/`)

**Purpose:** PySide6 desktop application providing a graphical interface for all processing modules.

**Architecture:** `QMainWindow` → `QTabWidget` (5 tabs) → Background `QThread` workers

**Key Components:**

```
gui/
├── app.py                 # MainWindow entry point (txr-gui)
├── constants.py           # App metadata, incident mappings
├── tabs/                  # Tab implementations
│   ├── accuracy_tab.py    # Accuracy testing tab (9 incidents)
│   ├── replay_tab.py      # Replay processing tab
│   ├── firds_tab.py       # FIRDS management tab
│   ├── gleif_tab.py       # GLEIF management tab
│   └── utilities_tab.py   # Utilities tab
├── widgets/               # Reusable UI components
│   ├── file_picker.py     # File/directory browser
│   ├── config_loader.py   # YAML config loader
│   ├── log_viewer.py      # Real-time log viewer
│   ├── run_controls.py    # Start/stop/progress controls
│   └── form_field.py      # Form input widgets
└── workers/
    └── script_runner.py   # QThread background script execution
```

---

## 3. Configuration Management

### 3.1 Configuration Strategy

**Priority Order** (highest to lowest):
1. **Environment Variables** (`TXR_*` prefix)
2. **YAML Configuration Files**
3. **Default Values** (hardcoded)

### 3.2 Configuration Classes

```python
@dataclass
class PathConfig:
    """Standardized path configuration."""
    replay_input: str
    incident_files: str
    replay_output: str
    log_output: str
    unavista_file: Optional[str] = None

@dataclass
class ProcessorConfig:
    """Standardized processor configuration."""
    batch_size: int = 50
    log_level: str = "INFO"
    enable_progress_reporting: bool = True
    encoding: str = "utf-8"
```

### 3.3 Example YAML Configuration

```yaml
paths:
  replay_input: "/path/to/input"
  incident_files: "/path/to/incidents"
  replay_output: "/path/to/output"
  log_output: "logs/"

processing:
  batch_size: 100
  log_level: "INFO"
  enable_progress_reporting: true
  encoding: "utf-8"
```

### 3.4 Environment Variables

```bash
export TXR_REPLAY_INPUT="/path/to/input"
export TXR_LOG_LEVEL="DEBUG"
export TXR_BATCH_SIZE="200"
```

---

## 4. Data Flow

### 4.1 Buyer/Seller ID Validation Workflow

```
┌──────────────────┐
│  Input CSV       │
│  (Template)      │
└────────┬─────────┘
         │
         ↓
┌──────────────────┐
│ Load & Parse     │
│ • Read CSV       │
│ • Create records │
└────────┬─────────┘
         │
         ↓
┌──────────────────────────────────────┐
│ Phase 1: Inconsistent ID Handling    │
│ • Aggregate by Person Code           │
│ • Check for fallback IDs              │
│ • Replace with most recent valid ID  │
└────────┬─────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────┐
│ Phase 2: Format Validation           │
│ • Extract country from nationality   │
│ • Validate ID format with regex      │
│ • Generate CONCAT if needed          │
└────────┬─────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────┐
│ Phase 3: Logic Validation            │
│ • Checksums (UK NINO, IT Fiscal)     │
│ • Date logic (date of birth in ID)   │
│ • Gender validation                   │
│ • Italian tracker lookups             │
└────────┬─────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────┐
│ Phase 4: Template Validation         │
│ • Match against Kaizen template      │
│ • Populate Error/Match columns       │
└────────┬─────────────────────────────┘
         │
         ↓
┌──────────────────┐
│ Output CSV       │
│ (Validated)      │
└──────────────────┘
```

### 4.2 Decision Maker Validation Workflow

```
┌──────────────────┐
│  SQL Extract     │
│  (Raw data)      │
└────────┬─────────┘
         │
         ↓
┌──────────────────────────────────────┐
│ Load Records                          │
│ • Parse CSV                           │
│ • Create DecisionMakerRecord objects  │
└────────┬─────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────┐
│ Classify IDs                          │
│ • Determine party code type (LEI/etc) │
│ • Determine DM code type              │
└────────┬─────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────┐
│ Validation Rules                      │
│ IF service_level == "D":              │
│   • DM code must be populated         │
│   • DM code ≠ party code              │
│   • Correction: LEI from branch lookup│
│ ELSE: No validation required          │
└────────┬─────────────────────────────┘
         │
         ↓
┌──────────────────┐
│ Output CSV       │
│ (Validated)      │
└──────────────────┘
```

---

## 5. Deployment Architecture

### 5.1 Current Deployment (Manual)

```
Developer Machine
├── Conda Environment (txr_automation)
├── Python 3.13 runtime
├── Dependencies from requirements.txt
└── Run scripts manually via CLI
```

### 5.2 Package Installation

```bash
# Development mode (editable install)
pip install -e .

# This registers 22 console scripts + 1 GUI script:
# Accuracy: validate-buyer, validate-seller, validate-inconsistent-buyer,
#           validate-inconsistent-seller, validate-ftbdm, validate-ftsdm,
#           validate-pricing, validate-non-zero-net-qty, validate-non-zero-net-amt,
#           validate-all, generate-sql-extract, generate-accuracy-template,
#           collate-csv-extracts, data-push
# Replay:   replay-phase2, replay-phase3, replay-phase3-final,
#           merge-inconsistent-summaries
# FIRDS:    firds-refresh, firds-check, firds-backfill
# GLEIF:    gleif-refresh, gleif-check, gleif-backfill
# GUI:      txr-gui
```

---

## 6. Testing Strategy

### 6.1 Test Structure

```
tests/
├── test_core/                    # Core library tests
│   ├── test_config.py
│   ├── test_country_codes.py
│   ├── test_id_formats.py
│   └── test_validators.py
├── test_accuracy_testing/        # Accuracy testing module tests
│   ├── test_buyer_id_validation.py
│   ├── test_seller_id_validation.py
│   ├── test_decision_maker_validation.py
│   └── test_pricing_validation.py
├── test_replay/                  # Replay module tests
├── integration/                  # End-to-end workflow tests
│   ├── test_accuracy_workflow.py
│   └── test_cli_interfaces.py
└── fixtures/                     # Test data fixtures
```

### 6.2 Test Coverage (as of 2026-03-25)

- **Total Tests:** 466 collected
- **Passing:** 466 (100%)
- **Skipped:** 13 (require confidential sample data)
- **Failing:** 0 ✅

### 6.3 Test Categories

1. **Unit Tests:** Individual functions and classes
2. **Integration Tests:** Multi-component workflows
3. **CLI Tests:** Command-line interface validation
4. **Fixture-Based Tests:** Test with realistic data samples

---

## 7. Performance Characteristics

### 7.1 Current Performance (20K records)

- **Processing Time:** < 30 seconds
- **Memory Usage:** < 200 MB
- **Throughput:** ~700 records/second

### 7.2 Scalability Benchmarks

Use the scalability benchmarking tool:

```bash
python scripts/benchmark_scalability.py --sizes 100000 500000 1000000 1500000
```

Expected output metrics:
- Processing time (seconds)
- Peak memory usage (MB)
- Throughput (records/second)
- Memory per record (KB)

### 7.3 Optimization Opportunities

1. **Chunked CSV Processing:** Process large files in batches to reduce memory footprint
2. **Parallel Processing:** Utilize multiprocessing for independent records
3. **Caching:** Cache regex compilations and reference data lookups
4. **Lazy Loading:** Load reference data on-demand

---

## 8. Design Principles

### 8.1 Code Standards

1. **Type Hints:** All functions have type annotations
2. **Docstrings:** Google-style docstrings for all public functions/classes
3. **Dataclasses:** Used for data transfer objects
4. **Immutability:** Prefer immutable data structures where possible
5. **British English:** All documentation and variable names

### 8.2 Error Handling

1. **Fail Fast:** Validate inputs early, raise clear exceptions
2. **Structured Logging:** Log errors with context for debugging
3. **Graceful Degradation:** Continue processing other records when one fails
4. **User Feedback:** Provide clear error messages and suggestions

### 8.3 Dependency Management

**Philosophy:** Minimize external dependencies

**Core Dependencies:**
- `pyyaml`: Configuration file parsing
- `pandas`: CSV/DataFrame operations (may be replaced to reduce footprint)

**Development Dependencies:**
- `pytest`: Testing framework
- `pytest-cov`: Code coverage

---

## 9. Future Architecture

### 9.1 Short-Term (Q2 2026)

- **Chunked Processing:** Implement streaming CSV processing for 1.5M+ records
- **Environment Separation:** dev/test/prod configuration environments
- **GUI Prototype:** Streamlit web interface for non-technical users
- **Shell Script Automation:** Batch processing workflows

### 9.2 Medium-Term (Q3 2026)

- **PyQt6 Production GUI:** Desktop application with advanced features
- **CI/CD Pipeline:** Automated testing and deployment
- **Containerization:** Docker containers for consistent deployment
- **Monitoring:** Structured logging with log aggregation

### 9.3 Long-Term (Q4 2026+)

- **Workflow Orchestration:** Airflow/Prefect for daily automated runs
- **Cloud Deployment:** AWS/Azure for scalability
- **Distributed Processing:** Process 10M+ records across multiple nodes
- **Real-Time Validation:** API endpoint for on-demand validation

---

## 10. References

### 10.1 Key Documents

- **[Python_Migration_Plan.md](documentation/planning/Python_Migration_Plan.md):** Master migration roadmap
- **[Architectural_Review_Level_4.md](documentation/reference/Architectural_Review_Level_4.md):** Detailed architectural analysis
- **[Phase_8_CLI_Tool_Plan.md](documentation/planning/Phase_8_CLI_Tool_Plan.md):** CLI unification strategy

### 10.2 Code Standards

- **Style Guide:** PEP 8 compliance
- **Import Order:** stdlib → third-party → local
- **Line Length:** 100 characters maximum
- **British English:** All documentation and code comments

---

## Appendix A: Module Dependency Diagram

```
┌─────────────────────────────────────────────────────────┐
│                   accuracy_testing                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  processor   │  │  validators  │  │   scripts    │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                 │                  │          │
│         └─────────────────┴──────────────────┘          │
│                           ↓                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │               accuracy_testing/core              │  │
│  │         (wrappers for core library)              │  │
│  └─────────────────────┬────────────────────────────┘  │
└────────────────────────┼─────────────────────────────────┘
                         ↓
┌────────────────────────────────────────────────────────┐
│                       core                              │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐            │
│  │  config  │  │   data   │  │ validation│            │
│  └────┬─────┘  └────┬─────┘  └─────┬─────┘            │
│       └─────────────┴──────────────┴─────┐            │
│                  ↓                        ↓             │
│  ┌──────────────────────┐  ┌──────────────────────┐   │
│  │      logging         │  │       utils          │   │
│  └──────────────────────┘  └──────────────────────┘   │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│                      replay                             │
│  (uses core, independent of accuracy_testing)           │
└────────────────────────────────────────────────────────┘
```

---

**Document Control:**
- **Author:** AI Assistant (GitHub Copilot)  
- **Review Status:** Draft  
- **Next Review:** Q2 2026
