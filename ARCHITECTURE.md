# TXR Automation - System Architecture

**Version:** 2.0  
**Last Updated:** 17 February 2026  
**Status:** Post-VBA Migration

---

## Executive Summary

The Transaction Reporting (TXR) Automation system provides validation and processing capabilities for financial transaction data, specifically focused on buyer/seller identification and decision maker validation for regulatory reporting compliance.

**Key Facts:**
- **Migrated from:** VBA macros (Excel-based)
- **Current stack:** Python 3.10+, pandas, CSV-based processing
- **Current scale:** 20,000 records quarterly
- **Target scale:** 1.5M records daily
- **Test coverage:** 528 passing tests (100% pass rate as of 2026-02-17)

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
│  • CLI Scripts (current)                                     │
│  • Future: GUI (Streamlit prototype → PyQt6 production)      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                  Processing Layer                            │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ accuracy_testing │  │     replay       │                 │
│  │  • ID validation │  │  • Phase 2/3     │                 │
│  │  • DM validation │  │  • Processing    │                 │
│  │  • Pricing       │  └──────────────────┘                 │
│  └──────────────────┘                                        │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   Core Library (txr_core)                    │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   config    │  │     data     │  │  validation  │        │
│  │  • YAML     │  │ • Countries  │  │  • ID rules  │        │
│  │  • Env vars │  │ • ID formats │  │  • Formats   │        │
│  └─────────────┘  └──────────────┘  └──────────────┘        │
│  ┌─────────────┐  ┌──────────────┐                          │
│  │   logging   │  │    utils     │                           │
│  │  • Struct.  │  │  • CSV       │                           │
│  │  • JSON     │  │  • Date      │                           │
│  └─────────────┘  └──────────────┘                           │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                     Data Layer                               │
│  • CSV files (input/output)                                  │
│  • Reference data (country codes, ID formats, LEI lookups)   │
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
- `phase_2_processor.py`: Phase 2 processing
- `phase_3_processor.py`: Phase 3 matching and decisioning
- `phase_3_final_lookup.py`: Final Kaizen lookup

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

# This registers console scripts:
# - validate-buyer
# - validate-seller
# - validate-ftbdm
# - validate-ftsdm
# - etc.
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

### 6.2 Test Coverage (as of 2026-02-17)

- **Total Tests:** 541 collected
- **Passing:** 528 (97.6%)
- **Skipped:** 13
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
