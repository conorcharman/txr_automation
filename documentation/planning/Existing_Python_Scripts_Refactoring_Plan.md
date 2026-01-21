# Existing Python Scripts Refactoring Plan

**Version:** 1.2  
**Date:** 19 January 2026  
**Purpose:** Analysis and plan to refactor existing Python replay scripts with consistent architecture

**Status Update (19 January 2026):**

- ✅ **Phase 0**: Completed - Core library refactoring and performance optimizations (merged to main)
- ✅ **Phase 1**: Completed - Accuracy testing core library created in `src/accuracy_testing/core/`
  - Country codes reference data (249 countries with EEA status)
  - ID format validation patterns (67 patterns across 40+ countries)
  - ID validation logic (NIDN, CONCAT, CCPT, LEI)
  - Core validators and CSV schema definitions
  - Comprehensive test suite and demo script

---

## Git Branch Strategy

**All Phase 0 refactoring work should be done on the `phase0-refactoring` branch.**

See [Git_Branching_Guide.md](Git_Branching_Guide.md) for detailed instructions on:

- Creating and working with branches
- Commit best practices
- Merging completed work

**Quick Start:**

```bash
# Create Phase 0 branch
git checkout -b phase0-refactoring
git push -u origin phase0-refactoring

# Work on refactoring, commit regularly
git add .
git commit -m "Descriptive message"
git push origin phase0-refactoring
```

---

## Executive Summary

The existing Python scripts (Phase 2, Phase 3, Phase 3 Final Lookup, and XLSX Converter) were written
independently and show significant architectural inconsistencies.
This plan outlines how to refactor them using shared core libraries and consistent patterns to
support the medium-term goal of building a unified Transaction Reporting tool.

### Key Findings

✅ **What Works Well:**

- Performance optimization (indexing, caching)
- Dataclass usage for data structures
- Logging and statistics tracking
- CSV-based approach

❌ **Major Inconsistencies:**

- Different configuration approaches
- Hardcoded file paths
- Inconsistent error handling patterns
- No shared code between scripts
- Different logging formats
- Duplicate functionality (DateParser, indexing)
- No input validation
- No CLI interfaces

---

## Detailed Analysis of Existing Scripts

### **1. phase_2_processor_v3_1.py (521 lines)**

**Purpose:** Transaction reference-based replay file processing

**Strengths:**

- ✅ O(1) transaction reference lookups with hash indexing
- ✅ Pre-loads and indexes all incident files
- ✅ Batch processing with progress reporting
- ✅ Good statistics tracking
- ✅ Handles single and combined incident files
- ✅ Character replacement handling (chr(172) for ¬)

**Weaknesses:**

- ❌ Hardcoded file paths (`C:\Users\ccharm\Desktop\...`)
- ❌ No CLI interface
- ❌ No configuration file
- ❌ Column mappings embedded in code
- ❌ No input validation
- ❌ `IncidentFileIndex` class duplicated in Phase 3
- ❌ Logging format differs from Phase 3

**Dependencies:** None (standalone)

**Lines of Code:** 521

---

### **2. phase_3_processor_v4_2.py (715 lines)**

**Purpose:** Client record matching using name/DOB/ID for replay processing

**Strengths:**

- ✅ Sophisticated multi-index system (ID, name, decision maker)
- ✅ Fuzzy matching with fallback strategies
- ✅ DateParser with caching
- ✅ Batch processing
- ✅ Comprehensive indexing for O(1) lookups
- ✅ Good debug logging

**Weaknesses:**

- ❌ Hardcoded file paths
- ❌ No CLI interface
- ❌ No configuration file
- ❌ `IncidentFileIndex` class duplicated from Phase 2
- ❌ `DateParser` duplicated in Phase 3 Final Lookup
- ❌ Column indices hardcoded (e.g., `row[21]`, `row[32]`)
- ❌ No schema validation
- ❌ Parsing logic tied to specific formats

**Dependencies:** None (standalone)

**Lines of Code:** 715

---

### **3. phase_3_final_lookup.py (1,242 lines)**

**Purpose:** Validates replay corrections against UnaVista transaction data

**Strengths:**

- ✅ File discovery with glob patterns
- ✅ Comprehensive field mapping system
- ✅ Sophisticated correction parsing (handles ampersand-combined fields)
- ✅ Incident code matrix for buyer/seller determination
- ✅ Duplicate record merging
- ✅ Field-level statistics
- ✅ Good data structures with dataclasses
- ✅ DateParser with timestamp handling

**Weaknesses:**

- ❌ Hardcoded base paths
- ❌ No CLI interface
- ❌ No configuration file
- ❌ `DateParser` duplicated from Phase 3
- ❌ Very long (1,242 lines) - needs modularization
- ❌ Field mappings hardcoded in `FieldMapper` class
- ❌ Column indices hardcoded throughout
- ❌ No input validation
- ❌ Complex logic in main class (needs extraction)

**Dependencies:** None (standalone)

**Lines of Code:** 1,242

---

### **4. xlsx_csv_converter.py (300 lines)**

**Purpose:** Convert Excel files to CSV with multi-line cell splitting

**Strengths:**

- ✅ Handles multi-line cells correctly
- ✅ Date formatting (DD/MM/YYYY)
- ✅ Good error handling per file
- ✅ Clear user feedback

**Weaknesses:**

- ❌ Hardcoded input/output paths
- ❌ Uses pandas for Excel (adds dependency) - but acceptable for converter
- ❌ No CLI interface
- ❌ Console input at end (`input()`) - bad for automation
- ❌ No logging to file
- ❌ Limited configuration options
- ❌ Windows-specific path format

**Dependencies:** pandas (acceptable for this utility)

**Lines of Code:** ~150 (actual code, rest is whitespace/comments)

---

## Architectural Inconsistencies Summary

### **Major Issues:**

| Issue | Impact | Affected Scripts |
| ------- | -------- | ------------------ |
| **Hardcoded file paths** | Cannot run on different machines/environments | All 4 scripts |
| **No configuration management** | Changes require code edits | All 4 scripts |
| **Duplicated classes** | Code maintenance nightmare | Phase 2, 3, 3 Final |
| **No CLI interfaces** | Poor usability, hard to automate | All 4 scripts |
| **Inconsistent logging** | Different formats, no structured logging | All 4 scripts |
| **No input validation** | Fails with cryptic errors on bad input | Phase 2, 3, 3 Final |
| **Column indices hardcoded** | Brittle to CSV format changes | Phase 2, 3, 3 Final |
| **No shared utilities** | Massive code duplication | All 4 scripts |

### **Duplicated Code:**

1. **`DateParser` class** (in Phase 3 and Phase 3 Final) - Identical functionality
2. **`IncidentFileIndex` class** (in Phase 2 and Phase 3) - Similar functionality, different
implementation details
3. **Logging setup** - Repeated in all scripts with variations
4. **Statistics tracking** - Similar patterns but different implementations
5. **File discovery** - Only Phase 3 Final has glob patterns, others hardcoded
6. **Dataclass definitions** - Similar classes with different names

### **Design Pattern Inconsistencies:**

| Pattern | Phase 2 | Phase 3 | Phase 3 Final | XLSX Converter |
| --------- | --------- | --------- | --------------- | ---------------- |
| **Main class** | `Phase2ProcessorOptimized` | `Phase3ProcessorUltraOptimized` | `Phase3FinalLookup` | Functions only |
| **Configuration** | Hardcoded | Hardcoded | Hardcoded | Hardcoded |
| **Logging setup** | Method in class | Method in class | Method in class | Not implemented |
| **Entry point** | `main()` function | `main()` function | `main()` function | `if __name__` block |
| **Error handling** | Try/except in main | Try/except in main | Try/except in run() | Try/except per file |

---

## Refactoring Plan

### **Phase 1: Extract Shared Core Library** ✅ **COMPLETED (19 January 2026)**

**Objective:** Create shared functionality for both replay and accuracy testing workflows

**Status:** Phase 1 focused on accuracy testing core library rather than replay-specific refactoring.
The accuracy testing foundation was successfully built in `src/accuracy_testing/core/`.

#### **1.1 Accuracy Testing Core Library** ✅ **IMPLEMENTED**

Located in `src/accuracy_testing/core/`:

- ✅ **`country_codes.py`**: ISO 3166-1 country codes with EEA status (249 countries)
  - `Country` dataclass, `CountryDataManager` singleton
  - O(1) lookups by Alpha-2/Alpha-3, EEA membership checks
  - No external CSV dependencies (embedded data)

- ✅ **`id_formats.py`**: ID format validation patterns
  - 67 regex patterns across 40+ countries
  - Supports NIDN, CONCAT, CCPT, LEI identification types
  - `IDFormatManager` singleton with pre-compiled patterns

- ✅ **`id_validation.py`**: High-level ID validation logic
  - Combines country codes, formats, and business rules
  - `validate_id()`, `validate_id_auto()`, `validate_lei()` functions
  - Comprehensive validation results with errors and warnings

- ✅ **`validators.py`**: Core validation functions
  - Date, string, numeric, choice, and country validators
  - Consistent `ValidationResult` API
  - Composable validators for complex rules

- ✅ **`schema.py`**: CSV schema definitions
  - `FieldSchema` and `CSVSchema` classes
  - Predefined schemas for accuracy testing workflows

- ✅ **`__init__.py`**: Clean public API with all exports

#### **1.2 Testing & Documentation** ✅ **COMPLETED**

- ✅ **Tests**: `tests/test_accuracy_testing/`
  - `test_country_codes.py` (265 lines, comprehensive coverage)
  - `test_id_formats.py` (295 lines, pattern validation)
  - `test_validators.py` (352 lines, all validator functions)

- ✅ **Demo**: `demo_phase1.py` (177 lines)
  - Demonstrates all Phase 1 functionality
  - Country lookups, ID validation, format matching

- ✅ **Documentation**: `src/accuracy_testing/README.md`
  - Complete module documentation
  - Usage examples for all components
  - Migration roadmap for VBA scripts

#### **1.3 Replay Core Library** (Deferred)

The original Phase 1 plan included creating common data structures for replay processing (see below).
This was partially completed in Phase 0 but needs further work:

**Original Phase 1 plan for replay (to be completed):**

#### **1.1 Core Data Structures** (`txr_replay_core/data_structures.py`)

```python
@dataclass
class ReplayRecord:
    """Universal replay record structure"""
    record_type: str  # 'phase2', 'phase3_ids', 'phase3_names'
    transaction_reference: Optional[str] = None
    client_id: Optional[str] = None
    first_name: Optional[str] = None
    surname: Optional[str] = None
    date_of_birth: Optional[str] = None
    incident_codes: List[str] = field(default_factory=list)
    corrections: Dict[str, str] = field(default_factory=dict)
    original_row: List[str] = field(default_factory=list)
    row_index: int = 0
    source_file: str = ""
    file_type: str = ""  # 'single', 'combined', etc.
    all_ids: List[str] = field(default_factory=list)

@dataclass
class LookupResult:
    """Universal lookup result structure"""
    found: bool
    correction: str = ""
    correction_field: str = ""
    error_flag: str = ""
    transaction_ref: str = ""
    match_type: str = ""

@dataclass
class UnaVistaTransaction:
    """UnaVista transaction record"""
    transaction_ref: str
    row_data: List[str]
    row_index: int

@dataclass
class ProcessingStats:
    """Standardized statistics tracking"""
    processed_files: int = 0
    processed_records: int = 0
    successful_matches: int = 0
    not_found: int = 0
    no_corrections: int = 0
    inconsistent_corrections: int = 0
    errors: int = 0
    custom_stats: Dict[str, Any] = field(default_factory=dict)
```

#### **1.2 Shared Utilities** (`txr_replay_core/utils.py`)

```python
class DateParser:
    """Unified date parser with caching (extracted from existing scripts)"""
    _date_cache = {}
    
    @classmethod
    def parse_date(cls, date_str: str) -> Optional[str]:
        # Unified implementation
        pass

class CharacterReplacement:
    """Handle special character replacements"""
    @staticmethod
    def colon_to_not_sign(value: str) -> str:
        """Replace : with ¬ (chr(172))"""
        return value.replace(':', chr(172)) if value else value

class FileDiscovery:
    """Unified file discovery with glob patterns"""
    @staticmethod
    def find_latest_file(directory: str, pattern: str) -> Optional[str]:
        """Find most recent file matching pattern"""
        matches = glob.glob(os.path.join(directory, pattern))
        return max(matches, key=os.path.getmtime) if matches else None
```

#### **1.3 Configuration Management** (`txr_replay_core/config.py`)

```python
from dataclasses import dataclass
from typing import Optional
import yaml
import os

@dataclass
class PathConfig:
    """Configuration for file paths"""
    replay_input: str
    incident_files: str
    replay_output: str
    log_output: str
    unavista_file: Optional[str] = None

@dataclass
class ProcessorConfig:
    """Configuration for processor behaviour"""
    batch_size: int = 50
    log_level: str = "INFO"
    enable_progress_reporting: bool = True
    encoding: str = "utf-8"

class ConfigManager:
    """Manages configuration from YAML files and environment variables"""
    
    @classmethod
    def load_from_yaml(cls, config_path: str) -> dict:
        """Load configuration from YAML file"""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    @classmethod
    def load_from_env(cls, prefix: str = "TXR_") -> dict:
        """Load configuration from environment variables"""
        config = {}
        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix):].lower()
                config[config_key] = value
        return config
    
    @classmethod
    def get_path_config(cls, config_dict: dict) -> PathConfig:
        """Create PathConfig from configuration dictionary"""
        return PathConfig(**config_dict.get('paths', {}))
```

#### **1.4 Logging Infrastructure** (`txr_replay_core/logger.py`)

```python
import logging
from datetime import datetime
from typing import Optional
import json

class StructuredLogger:
    """Unified structured logging for all processors"""
    
    def __init__(self, name: str, log_dir: str, log_level: str = "INFO"):
        self.name = name
        self.log_dir = log_dir
        self.setup_logging(log_level)
    
    def setup_logging(self, log_level: str):
        """Setup logging with consistent format"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"{self.name}_{timestamp}.log"
        log_filepath = os.path.join(self.log_dir, log_filename)
        
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Create custom formatter for structured logging
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # File handler
        file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
        file_handler.setFormatter(formatter)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # Configure logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        self.log_filepath = log_filepath
    
    def info(self, message: str, **kwargs):
        """Log info message with optional structured data"""
        self.logger.info(message, extra=kwargs)
    
    def log_stats(self, stats: ProcessingStats):
        """Log statistics in structured format"""
        stats_dict = {
            'processed_files': stats.processed_files,
            'processed_records': stats.processed_records,
            'successful_matches': stats.successful_matches,
            'not_found': stats.not_found,
            'errors': stats.errors
        }
        self.logger.info(f"Statistics: {json.dumps(stats_dict)}")
```

#### **1.5 Index Management** (`txr_replay_core/indexing.py`)

```python
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

class BaseIndex(ABC):
    """Base class for all index types"""
    
    def __init__(self, file_path: str, logger):
        self.file_path = file_path
        self.logger = logger
        self.data_rows = []
    
    @abstractmethod
    def load_and_index(self):
        """Load data and build indexes"""
        pass

class TransactionReferenceIndex(BaseIndex):
    """Optimized transaction reference index (from Phase 2)"""
    
    def __init__(self, file_path: str, logger):
        super().__init__(file_path, logger)
        self.transaction_ref_index = {}
        self.load_and_index()
    
    def load_and_index(self):
        """Load file and build transaction reference index"""
        # Implementation from phase_2_processor
        pass
    
    def lookup(self, transaction_ref: str) -> Optional[int]:
        """O(1) transaction reference lookup"""
        return self.transaction_ref_index.get(transaction_ref.strip())

class ClientRecordIndex(BaseIndex):
    """Multi-field client index (from Phase 3)"""
    
    def __init__(self, file_path: str, logger):
        super().__init__(file_path, logger)
        # Multiple indexes for different lookup strategies
        self.buyer_id_index = defaultdict(list)
        self.seller_id_index = defaultdict(list)
        self.buyer_name_index = defaultdict(list)
        self.seller_name_index = defaultdict(list)
        self.buyer_dm_id_index = defaultdict(list)
        self.seller_dm_id_index = defaultdict(list)
        self.buyer_dm_name_index = defaultdict(list)
        self.seller_dm_name_index = defaultdict(list)
        self.load_and_index()
    
    def load_and_index(self):
        """Load file and build all indexes"""
        # Implementation from phase_3_processor
        pass
    
    def lookup_by_id(self, client_ids: List[str]) -> Optional[Tuple[int, str]]:
        """O(1) ID lookup"""
        # Implementation from phase_3_processor
        pass
    
    def lookup_by_name(self, first_name: str, surname: str, dob: str) -> Optional[Tuple[int, str]]:
        """O(1) name lookup"""
        # Implementation from phase_3_processor
        pass
```

#### **1.6 CSV Schema Validation** (`txr_replay_core/schema.py`)

```python
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import csv

@dataclass
class ColumnDefinition:
    """Definition of a CSV column"""
    name: str
    index: int
    required: bool = False
    data_type: str = "string"  # string, int, float, date
    pattern: Optional[str] = None  # regex pattern for validation

@dataclass
class CSVSchema:
    """Schema definition for CSV files"""
    name: str
    columns: List[ColumnDefinition]
    min_columns: int
    allow_extra_columns: bool = True

class SchemaValidator:
    """Validates CSV files against schema definitions"""
    
    # Predefined schemas for each file type
    SCHEMAS = {
        'phase2_single': CSVSchema(
            name='Phase 2 Single Incident',
            columns=[
                ColumnDefinition('Incident Code', 0, required=True),
                # ... other columns
            ],
            min_columns=14
        ),
        'phase2_combined': CSVSchema(
            name='Phase 2 Combined Incident',
            columns=[
                ColumnDefinition('Incident Code', 0, required=True),
                # ... other columns
            ],
            min_columns=13
        ),
        # ... other schemas
    }
    
    @classmethod
    def validate_file(cls, file_path: str, schema_name: str) -> Tuple[bool, List[str]]:
        """
        Validate CSV file against schema
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        schema = cls.SCHEMAS.get(schema_name)
        if not schema:
            return False, [f"Unknown schema: {schema_name}"]
        
        errors = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader)
                
                # Check minimum columns
                if len(header) < schema.min_columns:
                    errors.append(f"Expected at least {schema.min_columns} columns, found {len(header)}")
                
                # Validate required columns
                for col_def in schema.columns:
                    if col_def.required and col_def.index >= len(header):
                        errors.append(f"Missing required column: {col_def.name} at index {col_def.index}")
                
                # Validate data rows (sample)
                for i, row in enumerate(reader):
                    if i >= 10:  # Validate first 10 rows
                        break
                    
                    if len(row) < schema.min_columns:
                        errors.append(f"Row {i+2} has only {len(row)} columns, expected {schema.min_columns}")
        
        except Exception as e:
            errors.append(f"Error reading file: {e}")
        
        return len(errors) == 0, errors
```

#### **1.7 CLI Framework** (`txr_replay_core/cli.py`)

```python
import click
from typing import Callable
from pathlib import Path

class BaseCLI:
    """Base class for CLI interfaces"""
    
    @staticmethod
    def common_options(func: Callable) -> Callable:
        """Decorator for common CLI options"""
        func = click.option(
            '--config', '-c',
            type=click.Path(exists=True),
            help='Path to configuration file'
        )(func)
        func = click.option(
            '--log-level', '-l',
            type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
            default='INFO',
            help='Logging level'
        )(func)
        func = click.option(
            '--dry-run',
            is_flag=True,
            help='Perform dry run without writing outputs'
        )(func)
        return func
    
    @staticmethod
    def path_options(func: Callable) -> Callable:
        """Decorator for path-related options"""
        func = click.option(
            '--input-dir', '-i',
            type=click.Path(exists=True, file_okay=False, dir_okay=True),
            help='Input directory path'
        )(func)
        func = click.option(
            '--output-dir', '-o',
            type=click.Path(file_okay=False, dir_okay=True),
            help='Output directory path'
        )(func)
        return func
```

---

### **Phase 2: Refactor Individual Scripts (Weeks 3-6)**

#### **Week 3: Phase 2 Processor Refactoring**

**New Structure:**

```python
# scripts/phase_2_processor.py
#!/usr/bin/env python3
"""
Phase 2 Processor - Refactored
Transaction reference-based replay file processing
"""

import click
from pathlib import Path
from txr_replay_core.config import ConfigManager, PathConfig
from txr_replay_core.logger import StructuredLogger
from txr_replay_core.indexing import TransactionReferenceIndex
from txr_replay_core.data_structures import ReplayRecord, LookupResult, ProcessingStats
from txr_replay_core.utils import CharacterReplacement
from txr_replay_core.schema import SchemaValidator
from txr_replay_core.cli import BaseCLI

class Phase2Processor:
    """Refactored Phase 2 processor with dependency injection"""
    
    def __init__(self, config: PathConfig, logger: StructuredLogger):
        self.config = config
        self.logger = logger
        self.stats = ProcessingStats()
        self.incident_indexes = {}
    
    def preload_incident_files(self):
        """Preload and index incident files"""
        # Use TransactionReferenceIndex from core
        pass
    
    def process_replay_file(self, filename: str):
        """Process single replay file"""
        # Validate schema first
        schema_name = 'phase2_single' if '+' not in filename else 'phase2_combined'
        is_valid, errors = SchemaValidator.validate_file(
            Path(self.config.replay_input) / filename,
            schema_name
        )
        if not is_valid:
            self.logger.logger.error(f"Schema validation failed: {errors}")
            return
        
        # Process file
        pass
    
    def run(self):
        """Main execution"""
        self.logger.info("Starting Phase 2 Processor (Refactored)")
        self.preload_incident_files()
        # ... rest of processing
        self.logger.log_stats(self.stats)

@click.command()
@BaseCLI.common_options
@BaseCLI.path_options
@click.option('--incident-dir', type=click.Path(exists=True), help='Incident files directory')
def main(config, log_level, dry_run, input_dir, output_dir, incident_dir):
    """Phase 2 Processor - Transaction reference based replay processing"""
    
    # Load configuration
    if config:
        config_dict = ConfigManager.load_from_yaml(config)
    else:
        config_dict = ConfigManager.load_from_env()
    
    # Override with CLI arguments
    if input_dir:
        config_dict['paths']['replay_input'] = input_dir
    if output_dir:
        config_dict['paths']['replay_output'] = output_dir
    if incident_dir:
        config_dict['paths']['incident_files'] = incident_dir
    
    path_config = ConfigManager.get_path_config(config_dict)
    
    # Setup logging
    logger = StructuredLogger('phase_2_processor', path_config.log_output, log_level)
    
    # Run processor
    processor = Phase2Processor(path_config, logger)
    if not dry_run:
        return processor.run()
    else:
        logger.info("Dry run mode - no files will be written")
        return 0

if __name__ == "__main__":
    exit(main())
```

**Configuration File Example:** (`config/phase_2_config.yaml`)

```yaml
paths:
  replay_input: /path/to/replay/input
  incident_files: /path/to/incident/files
  replay_output: /path/to/output
  log_output: /path/to/logs

processing:
  batch_size: 50
  encoding: utf-8

logging:
  level: INFO
  structured: true
```

**Benefits:**

- ✅ No hardcoded paths
- ✅ CLI interface with `--help`
- ✅ Configuration file support
- ✅ Environment variable overrides
- ✅ Schema validation before processing
- ✅ Shared utilities from core library
- ✅ Consistent logging
- ✅ Dry-run mode for testing

---

#### **Week 4: Phase 3 Processor Refactoring**

**New Structure:**

```python
# scripts/phase_3_processor.py
#!/usr/bin/env python3
"""
Phase 3 Processor - Refactored
Client record matching using name/DOB/ID
"""

import click
from pathlib import Path
from txr_replay_core.config import ConfigManager, PathConfig
from txr_replay_core.logger import StructuredLogger
from txr_replay_core.indexing import ClientRecordIndex
from txr_replay_core.data_structures import ReplayRecord, LookupResult, ProcessingStats
from txr_replay_core.utils import DateParser
from txr_replay_core.schema import SchemaValidator
from txr_replay_core.cli import BaseCLI

class Phase3Processor:
    """Refactored Phase 3 processor"""
    
    def __init__(self, config: PathConfig, logger: StructuredLogger):
        self.config = config
        self.logger = logger
        self.stats = ProcessingStats()
        self.incident_indexes = {}
    
    # ... implementation using shared ClientRecordIndex
```

***Similar CLI structure to Phase 2**

---

#### **Week 5: Phase 3 Final Lookup Refactoring**

**Challenge:** This script is 1,242 lines and needs significant modularization.

**Refactoring Strategy:**

1. **Extract Field Mapping to Configuration**

   ```yaml
   # config/field_mappings.yaml
   field_mappings:
     short_codes:
       DOB: "Date of Birth"
       FN: "First Name"
       SN: "Surname"
       ID: "ID"
       IDT: "ID Sub Type"
     
     unavista_indices:
       buyer:
         ID_Type: 6
         ID_Sub_Type: 7
         ID: 8
         # ... etc
   ```

2. **Extract Classes to Separate Modules**
   - `FieldMapper` → `txr_replay_core/field_mapping.py`
   - `ReplayRecordIndex` → Use shared indexing from core
   - `UnaVistaIndex` → `txr_replay_core/unavista.py`

3. **Break Down Long Methods**
   - Extract validation logic to separate validator class
   - Extract output generation to formatter class

**New Structure:**

```python
# scripts/phase_3_final_lookup.py
#!/usr/bin/env python3
"""
Phase 3 Final Lookup - Refactored
Validates replay corrections against UnaVista data
"""

import click
from txr_replay_core.config import ConfigManager
from txr_replay_core.logger import StructuredLogger
from txr_replay_core.field_mapping import FieldMapper
from txr_replay_core.unavista import UnaVistaIndex
from txr_replay_core.cli import BaseCLI

class Phase3FinalLookup:
    """Refactored Phase 3 Final Lookup processor"""
    
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.field_mapper = FieldMapper.from_yaml(config['field_mappings_file'])
    
    # ... modularized implementation
```

**Target:** Reduce from 1,242 lines to ~400 lines in main script, with logic distributed to core library

---

#### **Week 6: XLSX Converter Refactoring**

**New Structure:**

```python
# scripts/xlsx_csv_converter.py
#!/usr/bin/env python3
"""
XLSX to CSV Converter - Refactored
Converts Excel files to CSV with multi-line cell handling
"""

import click
import pandas as pd
from pathlib import Path
from txr_replay_core.logger import StructuredLogger
from txr_replay_core.cli import BaseCLI

class XLSXConverter:
    """XLSX to CSV converter"""
    
    def __init__(self, input_dir: Path, output_dir: Path, logger: StructuredLogger):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.logger = logger
    
    @staticmethod
    def split_multiline_rows(df: pd.DataFrame) -> pd.DataFrame:
        """Split rows with multi-line cells"""
        # Existing logic
        pass
    
    def convert_file(self, xlsx_file: Path) -> bool:
        """Convert single XLSX file to CSV"""
        try:
            self.logger.info(f"Converting: {xlsx_file.name}")
            df = pd.read_excel(xlsx_file)
            
            # Format dates
            for col in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[col]):
                    df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime('%d/%m/%Y')
            
            # Split multi-line cells
            df = self.split_multiline_rows(df)
            
            # Write CSV
            csv_file = self.output_dir / f"{xlsx_file.stem}.csv"
            df.to_csv(csv_file, index=False, encoding='utf-8-sig')
            
            self.logger.info(f"✓ Successfully converted to: {csv_file.name}")
            return True
            
        except Exception as e:
            self.logger.logger.error(f"✗ Error converting {xlsx_file.name}: {e}")
            return False
    
    def convert_all(self) -> tuple:
        """Convert all XLSX files in input directory"""
        xlsx_files = list(self.input_dir.glob("*.xlsx"))
        
        if not xlsx_files:
            self.logger.logger.warning(f"No XLSX files found in {self.input_dir}")
            return 0, 0
        
        self.logger.info(f"Found {len(xlsx_files)} XLSX file(s) to convert")
        
        successful = 0
        for xlsx_file in xlsx_files:
            if self.convert_file(xlsx_file):
                successful += 1
        
        return successful, len(xlsx_files)

@click.command()
@BaseCLI.common_options
@click.option(
    '--input-dir', '-i',
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    required=True,
    help='Directory containing XLSX files'
)
@click.option(
    '--output-dir', '-o',
    type=click.Path(file_okay=False, dir_okay=True),
    required=True,
    help='Directory for CSV output files'
)
def main(config, log_level, dry_run, input_dir, output_dir):
    """XLSX to CSV Converter with multi-line cell handling"""
    
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    # Create output directory
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Setup logging
    logger = StructuredLogger('xlsx_converter', str(output_path), log_level)
    
    logger.info("XLSX to CSV Converter (Refactored)")
    logger.info(f"Input:  {input_path}")
    logger.info(f"Output: {output_path}")
    
    # Run converter
    converter = XLSXConverter(input_path, output_path, logger)
    
    if not dry_run:
        successful, total = converter.convert_all()
        logger.info(f"Conversion complete! {successful}/{total} files converted successfully")
        return 0 if successful == total else 1
    else:
        logger.info("Dry run mode - no files will be written")
        return 0

if __name__ == "__main__":
    exit(main())
```

---

### **Phase 3: Integration & Testing (Week 7)**

#### **Testing Strategy:**

1. **Unit Tests for Core Library**

   ```python
   # tests/test_core/test_date_parser.py
   def test_date_parser_caching():
       DateParser._date_cache.clear()
       result1 = DateParser.parse_date("01/12/2023")
       result2 = DateParser.parse_date("01/12/2023")
       assert result1 == result2
       assert len(DateParser._date_cache) == 1
   ```

2. **Integration Tests for Each Script**
   - Test with sample data
   - Compare outputs with original scripts
   - Verify performance (should be same or better)

3. **Regression Testing**
   - Run both old and new versions on same data
   - Compare CSV outputs byte-by-byte
   - Document any intentional differences

#### **Migration Path:**

1. **Parallel Running (1 week)**
   - Keep old scripts as `*_legacy.py`
   - Run both versions side-by-side
   - Compare outputs
   - Fix any discrepancies

2. **Gradual Rollout**
   - Start with XLSX converter (simplest)
   - Then Phase 2 processor
   - Then Phase 3 processor
   - Finally Phase 3 Final Lookup (most complex)

3. **Deprecation**
   - After 2 weeks of successful parallel running
   - Archive old scripts to `legacy/` folder
   - Update documentation

---

### **Phase 4: Documentation & Training (Week 8)**

#### **Documentation Deliverables:**

1. **User Guides**
   - Getting started guide
   - Configuration guide
   - CLI usage examples
   - Troubleshooting guide

2. **Developer Documentation**
   - Core library API documentation
   - Adding new processors guide
   - Testing guide
   - Contributing guidelines

3. **Migration Documentation**
   - Differences from legacy scripts
   - Configuration migration guide
   - Known issues and workarounds

---

## Expected Benefits

### **Code Quality:**

| Metric | Before | After | Improvement |
| -------- | -------- | ------- | ------------- |
| **Total lines** | ~2,500 | ~1,200 | 52% reduction |
| **Duplicated code** | ~500 lines | 0 | 100% elimination |
| **Configuration** | 4 hardcoded | 1 unified | Centralized |
| **Test coverage** | 0% | >80% | Full testing |
| **Maintainability** | Poor | Excellent | Much better |

### **User Experience:**

✅ **CLI Interfaces:**

```bash
# Old way: Edit code, run script
python phase_2_processor_v3_1.py

# New way: Use CLI with options
python -m txr_replay.phase_2_processor \
    --config config/phase2.yaml \
    --input-dir ./data/input \
    --output-dir ./data/output \
    --log-level DEBUG
```

✅ **Configuration Files:**

```yaml
# config/phase2.yaml
paths:
  replay_input: ./data/replay/input
  incident_files: ./data/incident_files
  replay_output: ./data/replay/output
  log_output: ./logs

processing:
  batch_size: 100
  encoding: utf-8
```

✅ **Environment Variables:**

```bash
export TXR_REPLAY_INPUT=/data/input
export TXR_INCIDENT_FILES=/data/incident
export TXR_REPLAY_OUTPUT=/data/output
python -m txr_replay.phase_2_processor
```

### **Performance:**

- **Same or better** performance (indexing logic preserved)
- **Better memory management** (shared cache)
- **Faster startup** (precompiled regex patterns)

### **Maintenance:**

- **Single source of truth** for shared code
- **Easier to add features** (change core library)
- **Easier to fix bugs** (fix once, all scripts benefit)
- **Better testing** (unit tests for core library)

---

## Project Structure (Final State)

```markdown
txr_automation/
├── txr_replay_core/                    # NEW: Shared core library
│   ├── __init__.py
│   ├── config.py                       # Configuration management
│   ├── data_structures.py              # Shared dataclasses
│   ├── logger.py                       # Structured logging
│   ├── indexing.py                     # Index classes
│   ├── utils.py                        # DateParser, etc.
│   ├── schema.py                       # CSV schema validation
│   ├── field_mapping.py                # Field mapping utilities
│   ├── unavista.py                     # UnaVista-specific code
│   └── cli.py                          # CLI framework
│
├── scripts/                            # REFACTORED: Scripts using core
│   ├── phase_2_processor.py
│   ├── phase_3_processor.py
│   ├── phase_3_final_lookup.py
│   └── xlsx_csv_converter.py
│
├── config/                             # NEW: Configuration files
│   ├── phase_2_config.yaml
│   ├── phase_3_config.yaml
│   ├── phase_3_final_lookup_config.yaml
│   ├── field_mappings.yaml
│   └── logging_config.yaml
│
├── tests/                              # NEW: Comprehensive tests
│   ├── test_core/                      # Core library tests
│   │   ├── test_date_parser.py
│   │   ├── test_indexing.py
│   │   ├── test_config.py
│   │   └── test_schema.py
│   ├── test_integration/               # Integration tests
│   │   ├── test_phase_2.py
│   │   ├── test_phase_3.py
│   │   └── test_phase_3_final.py
│   └── fixtures/                       # Test data
│       ├── replay_files/
│       ├── incident_files/
│       └── unavista_files/
│
├── legacy/                             # OLD: Archived scripts
│   ├── phase_2_processor_v3_1.py
│   ├── phase_3_processor_v4_2.py
│   ├── phase_3_final_lookup.py
│   └── xlsx_csv_converter.py
│
├── documentation/                      # Enhanced documentation
│   ├── user_guides/
│   │   ├── getting_started.md
│   │   ├── configuration.md
│   │   ├── phase_2_usage.md
│   │   ├── phase_3_usage.md
│   │   └── troubleshooting.md
│   ├── developer_guides/
│   │   ├── core_library_api.md
│   │   ├── adding_processors.md
│   │   └── testing_guide.md
│   ├── migration/
│   │   ├── from_legacy.md
│   │   └── known_issues.md
│   ├── Python_Migration_Plan.md        # Main migration plan
│   └── Existing_Python_Scripts_Refactoring_Plan.md  # This document
│
├── requirements.txt                    # Python dependencies
├── setup.py                           # Package installation
├── pytest.ini                         # Pytest configuration
└── README.md                          # Updated readme
```

---

## Timeline & Milestones

| Week | Phase | Deliverables | Status |
| ------ | ------- | ------------- | -------- |
| **1-2** | Phase 1 | Core library created and tested | Not started |
| **3** | Phase 2 | Phase 2 Processor refactored | Not started |
| **4** | Phase 2 | Phase 3 Processor refactored | Not started |
| **5** | Phase 2 | Phase 3 Final Lookup refactored | Not started |
| **6** | Phase 2 | XLSX Converter refactored | Not started |
| **7** | Phase 3 | Integration testing & parallel running | Not started |
| **8** | Phase 4 | Documentation & training | Not started |

**Total Duration:** 8 weeks (2 months)

---

## Success Criteria

### **Functional Requirements:**

- ✅ All scripts produce **identical outputs** to legacy versions
- ✅ All scripts have **CLI interfaces** with help text
- ✅ All scripts support **configuration files**
- ✅ All scripts support **environment variables**
- ✅ All scripts validate input **before processing**
- ✅ All scripts use **shared core library**

### **Non-Functional Requirements:**

- ✅ **Performance:** Same or better than legacy (within 5%)
- ✅ **Test coverage:** >80% for core library
- ✅ **Code duplication:** <5% (down from ~20%)
- ✅ **Lines of code:** <50% of legacy total
- ✅ **Documentation:** Complete user and developer guides

### **Quality Metrics:**

- ✅ **Maintainability:** Easy to understand and modify
- ✅ **Reliability:** No regressions from legacy
- ✅ **Usability:** Clear CLI interfaces and error messages
- ✅ **Testability:** Comprehensive test suite

---

## Risks & Mitigation

| Risk | Impact | Probability | Mitigation |
| ------ | -------- | ------------- | ------------ |
| **Regression bugs** | High | Medium | Parallel running, byte-by-byte output comparison |
| **Performance degradation** | Medium | Low | Performance testing, profiling, optimization |
| **User resistance to change** | Medium | Medium | Good documentation, training, gradual rollout |
| **Breaking changes in workflow** | High | Low | Maintain backward compatibility, CLI mirrors old behaviour |
| **Timeline overrun** | Low | Medium | Prioritize core library, can defer some refactoring |

---

## Next Steps

### **Immediate Actions:**

1. ✅ Review and approve this refactoring plan
2. ⬜ Set up project tracking (GitHub issues/project board)
3. ⬜ Create feature branch: `refactor/replay-scripts`
4. ⬜ Initialize `txr_replay_core` package structure
5. ⬜ Extract `DateParser` from Phase 3 to core library
6. ⬜ Write unit tests for `DateParser`
7. ⬜ Extract indexing classes to core library
8. ⬜ Set up CI/CD for automated testing

### **Week 1 Deliverables:**

- `txr_replay_core` package initialized
- `DateParser` extracted and tested
- Basic configuration management working
- Structured logger implemented
- First unit tests passing

---

## Conclusion

The existing Python replay scripts, while functionally correct and performant, suffer from
significant architectural inconsistencies that will hinder the medium-term goal of building a unified
Transaction Reporting tool. This refactoring plan addresses these issues by:

1. **Creating a shared core library** to eliminate code duplication
2. **Implementing consistent CLI interfaces** for better usability
3. **Introducing configuration management** to eliminate hardcoded paths
4. **Adding comprehensive testing** to prevent regressions
5. **Improving documentation** for long-term maintainability

**Estimated effort:** 8 weeks (2 months) for complete refactoring

**Expected benefits:**

- 52% reduction in total lines of code
- 100% elimination of duplicated code
- Vastly improved maintainability
- Better user experience with CLI interfaces
- Foundation for future unified tool development

**This refactoring must be completed before starting the VBA migration,** as it will establish the
architectural patterns and shared libraries that the converted VBA scripts will also use.

---

**Document Version:** 1.0  
**Date:** 22 December 2025  
**Author:** GitHub Copilot  
**Status:** Ready for Review
