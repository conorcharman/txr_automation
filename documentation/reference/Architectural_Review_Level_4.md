# Level 4: Architectural Review

## Transaction Reporting Automation System

**Review Date:** 16 February 2026  
**Review Type:** Level 4 - Architectural Review  
**Reviewer:** AI Code Review Assistant  
**System Version:** 1.0.0 (Post VBA Migration)

---

## Executive Summary

This architectural review assesses the Transaction Reporting Automation system following the complete migration from VBA macros to Python. The system is well-architected for its current scale (20,000 transactions, 11 incidents) but requires strategic enhancements to handle the planned scale-up to 1.5M transactions across 129 incidents, transition to daily processing, and support future GUI requirements.

### Key Findings

**Strengths:**

- ✅ Clean separation of concerns (core library, accuracy_testing, replay)
- ✅ CSV-first approach eliminates Excel dependencies
- ✅ Comprehensive test suite (45 test files, 307/322 tests passing)
- ✅ Flexible configuration management (YAML + environment variables)
- ✅ Strong foundation for scaling (batch processing patterns in place)

**Areas Requiring Attention:**

- ⚠️ Configuration architecture has duplication between core and accuracy_testing
- ⚠️ No environment separation (dev/test/prod)
- ⚠️ Deployment strategy is manual (Git clone + conda setup)
- ⚠️ 100x scale-up (20K → 1.5M transactions) needs architectural planning
- ⚠️ No automation framework for scheduled/unattended execution

**Strategic Recommendations:**

1. Implement environment-based configuration strategy
2. Design distributed/parallel processing architecture for scale
3. Create containerised deployment pipeline
4. Build automation orchestration layer
5. Design decoupled GUI architecture with API layer

---

## 1. System Architecture Overview

### 1.1 Current Architecture

```md
┌─────────────────────────────────────────────────────────────────┐
│                     User Interface Layer                        │
│                      (CLI Scripts)                              │
│  • validate-buyer, validate-seller                              │
│  • generate-sql-extract, data-push                              │
│  • replay-phase2, replay-phase3                                 │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────────────────┐
│                  Application Logic Layer                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌────────────────────┐  ┌─────────────────┐  ┌──────────────┐  │
│  │  accuracy_testing  │  │     replay      │  │    utils     │  │
│  ├────────────────────┤  ├─────────────────┤  ├──────────────┤  │
│  │ • Validation       │  │ • Phase 2       │  │ • XLSX Conv  │  │
│  │ • SQL Generation   │  │ • Phase 3       │  │              │  │
│  │ • Template Gen     │  │ • Lookup        │  │              │  │
│  │ • Data Push        │  │                 │  │              │  │
│  └────────┬───────────┘  └────────┬────────┘  └──────┬───────┘  │
│           │                       │                  │          │
│           └───────────────────────┴──────────────────┘          │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────────────────┐
│                    Core Library Layer                           │
├─────────────────────────────────────────────────────────────────┤
│  ┌────────┐ ┌──────────┐ ┌────────┐ ┌──────────┐ ┌────────────┐ │
│  │ Config │ │  Data    │ │Logging │ │  Utils   │ │ Validation │ │
│  │  Mgmt  │ │Structures│ │        │ │          │ │   Logic    │ │
│  └────────┘ └──────────┘ └────────┘ └──────────┘ └────────────┘ │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────────────────┐
│                  Data/Integration Layer                         │
├─────────────────────────────────────────────────────────────────┤
│  • CSV Files (Input/Output)                                     │
│  • YAML Configuration Files                                     │
│  • Reference Data (country_codes.csv, id_formats.csv)           │
│  • Log Files (Structured JSON logs)                             │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Data Flow Pipeline

```md
Database (SQL Server)
      │
      ├─── SQL Extract Scripts ───→ CSV Extracts
      │                                   │
      └─────────────────────────┬─────────┘
                                │
                        ┌───────▼────────┐
                        │ Template Files │
                        │  (Generated)   │
                        └───────┬────────┘
                                │
                        ┌───────▼────────┐
                        │  Validation    │
                        │    Scripts     │
                        └───────┬────────┘
                                │
                        ┌───────▼────────┐
                        │  Validated     │
                        │  CSV Files     │
                        └───────┬────────┘
                                │
                        ┌───────▼────────┐
                        │   Data Push    │
                        │  (Merge Back)  │
                        └───────┬────────┘
                                │
                        ┌───────▼────────┐
                        │ Final Output   │
                        │  (ARM Upload)  │
                        └────────────────┘
```

**Processing Frequency:**

- Current: Quarterly
- Near-term: Monthly
- Target: Daily

**Volume:**

- Current: ~20,000 transactions (11 incidents)
- Target: ~1.5M transactions (129 incidents)
- Scale Factor: **75x increase**

---

## 2. Module Boundary Analysis

### 2.1 Core Library (`src/core/`)

**Purpose:** Shared foundation for all automation modules

**Structure:**

```md
core/
├── config/              # Configuration management
│   └── config_manager.py
├── data/                # Reference data & structures
│   ├── constants.py
│   ├── country_codes.py
│   ├── id_formats.py
│   ├── incident_codes.py
│   └── structures.py
├── logging/             # Structured logging
│   └── logger.py
├── utils/               # General utilities
│   ├── csv_utils.py
│   ├── date_parser.py
│   └── file_discovery.py
└── validation/          # Core validation functions
```

**Assessment:**

- ✅ **Well-defined boundaries:** Clear separation of concerns
- ✅ **Reusability:** Successfully shared between replay and accuracy_testing
- ✅ **Version control:** Version 1.1.0 with clear exports
- ⚠️ **Documentation:** Could benefit from architecture decision records (ADRs)

**Recommendations:**

1. Add `ARCHITECTURE.md` explaining design decisions
2. Create dependency graph showing what depends on what
3. Consider extracting `core` to separate package for formal versioning

### 2.2 Accuracy Testing Module (`src/accuracy_testing/`)

**Purpose:** Quarterly accuracy testing workflows (VBA migration)

**Structure:**

```md
accuracy_testing/
├── core/                # Accuracy-specific core library
│   ├── country_codes.py
│   ├── id_formats.py
│   ├── id_validation.py
│   └── validators.py
├── models/              # Data models
│   ├── client_record.py
│   └── data_push_record.py
├── scripts/             # CLI scripts (15 entry points)
│   ├── buyer_id_validation.py
│   ├── seller_id_validation.py
│   ├── inconsistent_*.py
│   ├── validate_ft*.py
│   ├── sql_extract_generator.py
│   ├── accuracy_template_generator.py
│   ├── collate_csv_extracts.py
│   ├── data_push.py
│   ├── pricing_validation.py
│   └── run_all_validations.py
├── validators/          # Business validation logic
│   ├── id_validators.py
│   └── format_validators.py
├── processor.py         # Core processing engine
├── id_logic_validator.py
└── sql_templates/       # SQL query templates
```

**Assessment:**

- ✅ **Clean separation:** Scripts vs core logic vs validators
- ✅ **Console scripts:** Well-integrated with `setup.py`
- ⚠️ **Configuration duplication:** Has its own `AccuracyConfigManager` separate from `core.config`
- ⚠️ **Core duplication:** `accuracy_testing.core` re-implements some `core` functionality

***Critical Issue: Configuration Architecture Duplication***

There are **two separate configuration systems:**

1. **`core.config.ConfigManager`** - Used by replay scripts
2. **`accuracy_testing.processor.AccuracyConfigManager`** - Used by accuracy testing scripts

This creates:

- Code duplication
- Maintenance burden
- Inconsistent behaviour between modules
- Confusion for new developers

**Recommendations:**

1. **Consolidate configuration management:**
   - Extend `core.config.ConfigManager` to support both replay and accuracy testing
   - Add `mode: single|batch` support to `PathConfig`
   - Create `AccuracyPathConfig` as subclass of `PathConfig`
   - Deprecate `AccuracyConfigManager` in favour of unified approach

2. **Merge reference data:**
   - Move `accuracy_testing.core` reference data to `core.data`
   - Keep accuracy-specific validation logic in `accuracy_testing.validators`
   - Share country codes and ID formats from single source of truth

3. **Create configuration validation:**
   - JSON Schema validation for YAML configs
   - Runtime validation of required/optional fields
   - Clear error messages for misconfigurations

### 2.3 Replay Module (`src/replay/`)

**Purpose:** Quarterly replay comparison workflows

**Structure:**

```md
replay/
├── phase_2_processor.py  # Single/combined mode
├── phase_3_processor.py  # Main replay comparison
└── phase_3_final_lookup.py
```

**Assessment:**

- ✅ **Mature implementation:** Batch processing, indexing, performance optimised
- ✅ **Clean CLI:** `replay-phase2`, `replay-phase3`, `replay-phase3-final`
- ✅ **Uses core library:** Good integration with `core.config`, `core.logging`
- ⚠️ **Duplicated patterns:** Performance patterns (indexing, batching) not shared with accuracy_testing

**Recommendations:**

1. Extract batch processing patterns to `core.processing.BatchProcessor`
2. Extract indexing patterns to `core.processing.RecordIndex`
3. Share these patterns with accuracy_testing for consistent performance

### 2.4 Utils Module (`src/utils/`)

**Purpose:** Standalone utilities

**Structure:**

```md
utils/
└── xlsx_csv_converter.py
```

**Assessment:**

- ✅ **Simple and focused:** Does one thing well
- ⚠️ **Placement:** Consider moving to `core.utils` or keeping separate?

**Recommendation:**

- Keep separate for now (it's a standalone tool)
- If more utilities accumulate, establish criteria for core vs utils

---

## 3. Configuration Management Architecture

### 3.1 Current State

**Configuration Locations:**

```md

config/
├── templates/                    # Template configs for each script
│   ├── accuracy_testing/        # 15 templates
│   ├── replay/                  # 3 templates
│   ├── environments/            # 1 template
│   └── utils/                   # 1 template
├── local/                       # User-specific configs (gitignored)
│   ├── accuracy_testing/
│   ├── replay/
│   └── environments/
└── environments/                # Shared environment configs
```

**Configuration Formats:**

```yaml
# Single mode (accuracy_testing)
mode: "single"
single:
  incident_code: "7_37"
  paths:
    input_file: "..."
    output_file: "..."
    template_file: "..."
    log_output: "logs"

# Batch mode (accuracy_testing)
mode: "batch"
batch:
  incidents: ["7_35", "7_37", "7_39"]
  paths:
    extract_dir: "..."
    template_dir: "..."
    output_dir: "..."
  filename_patterns:
    extract: "{incident}_FY{fiscal_year}_{quarter}.csv"

# Replay mode (existing)
paths:
  replay_file: "..."
  validation_file: "..."
  output_file: "..."
processor:
  log_level: "INFO"
  batch_size: 1000
```

### 3.2 Assessment

**Strengths:**

- ✅ YAML format is human-readable and version-controllable
- ✅ Template pattern helps users get started
- ✅ Supports environment variables via `load_from_env()`
- ✅ Batch mode enables multi-incident processing

**Weaknesses:**

- ⚠️ **Duplication:** Two separate config manager implementations
- ⚠️ **No validation:** No schema validation for YAML files
- ⚠️ **No environment separation:** No dev/test/prod distinction
- ⚠️ **Path handling:** Absolute paths make configs non-portable
- ⚠️ **Secrets:** No secure credential management

### 3.3 Recommended Architecture

**Unified Configuration Hierarchy:**

```md

┌─────────────────────────────────────────────────┐
│           Environment Variables                  │  (Highest priority)
│  TXR_ENV=production                             │
│  TXR_LOG_LEVEL=INFO                             │
└────────────────┬────────────────────────────────┘
                 │ Overrides
┌────────────────┴────────────────────────────────┐
│        User Config (CLI args + local YAML)      │  (Medium priority)
│  --config config/local/buyer_validation.yaml    │
└────────────────┬────────────────────────────────┘
                 │ Overrides
┌────────────────┴────────────────────────────────┐
│      Environment Config (dev/test/prod)         │  (Low priority)
│  config/environments/{TXR_ENV}/defaults.yaml    │
└────────────────┬────────────────────────────────┘
                 │ Overrides
┌────────────────┴────────────────────────────────┐
│           Application Defaults                   │  (Lowest priority)
│  Hardcoded in code                              │
└─────────────────────────────────────────────────┘
```

**Implementation Plan:**

1. **Create environment structure:**

```md

config/
├── environments/
│   ├── development/
│   │   ├── defaults.yaml
│   │   └── credentials.yaml  (gitignored)
│   ├── test/
│   │   ├── defaults.yaml
│   │   └── credentials.yaml  (gitignored)
│   ├── production/
│   │   ├── defaults.yaml
│   │   └── credentials.yaml  (gitignored)
│   └── local/                (gitignored)
│       └── overrides.yaml
├── schemas/                  # JSON schemas for validation
│   ├── accuracy_testing.schema.json
│   └── replay.schema.json
└── templates/                # Unchanged
```

1. **Unified ConfigManager:**

```python

class ConfigManager:
    """Unified configuration management for all modules."""
    
    @classmethod
    def load(cls, 
             config_path: Optional[str] = None,
             environment: Optional[str] = None,
             validate_schema: bool = True) -> Dict[str, Any]:
        """
        Load configuration with hierarchical merging.
        
        Priority order (highest to lowest):
        1. CLI arguments (config_path)
        2. Environment variables (TXR_*)
        3. Environment defaults (config/environments/{env}/)
        4. Application defaults
        
        Args:
            config_path: Path to user config file
            environment: Environment name (dev/test/prod) or from TXR_ENV
            validate_schema: Validate against JSON schema
            
        Returns:
            Merged configuration dictionary
        """
```

1. **Schema validation:**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Accuracy Testing Configuration",
  "type": "object",
  "required": ["mode"],
  "properties": {
    "mode": {
      "type": "string",
      "enum": ["single", "batch"]
    },
    "single": {
      "type": "object",
      "required": ["incident_code", "paths"],
      ...
    },
    "batch": {
      "type": "object",
      "required": ["incidents", "paths"],
      ...
    }
  }
}
```

1. **Path resolution:**

```python
class PathResolver:
    """Resolve relative paths based on environment."""
    
    BASE_PATHS = {
        "development": "/Users/user/Documents/GitHub/txr_automation",
        "test": "/Users/user/Documents/GitHub/txr_automation",
        "production": "/mnt/network/txr_automation"
    }
    
    @classmethod
    def resolve(cls, path: str, environment: str) -> Path:
        """
        Resolve relative paths to absolute based on environment.
        Supports:
        - Absolute paths (passed through)
        - Relative paths (resolved against BASE_PATH)
        - Network paths (\\server\share on Windows)
        - Environment variables ($DATA_DIR/...)
        """
```

---

## 4. Scalability Assessment

### 4.1 Current Scale vs Target Scale

| Metric | Current | Target | Scale Factor |
| -------- | --------- | -------- | -------------- |
| **Transactions** | 20,000 | 1,500,000 | 75x |
| **Incidents** | 11 | 129 | 11.7x |
| **Frequency** | Quarterly | Daily | 90x |
| **Processing Window** | ~8 hours | <2 hours | 4x faster required |
| **Data per Run** | ~5 MB | ~375 MB | 75x |

### 4.2 Performance Bottlenecks

**Critical Path Analysis:**

1. **CSV I/O:**
   - Current: `pd.read_csv()` for entire file
   - Issue: 375 MB CSV files may cause memory pressure
   - Solution: Chunked reading or streaming parsing

2. **Validation Logic:**
   - Current: Row-by-row Python loops
   - Issue: Pure Python is slow for 1.5M iterations
   - Solution: Vectorised pandas operations where possible

3. **Joint Account Aggregation:**
   - Current: O(n) scan through records
   - Issue: Quadratic complexity if not indexed
   - Solution: Pre-built hash index (already implemented in replay)

4. **CONCAT Generation:**
   - Current: String concatenation in Python
   - Issue: CPU-intensive for 1.5M records
   - Solution: Vectorised string operations

5. **Regex Validation:**
   - Current: Compiled patterns (good!)
   - Issue: Still CPU-intensive at scale
   - Solution: Parallel processing or Cython/Numba optimisation

### 4.3 Memory Profile

**Current Memory Usage (estimated):**

- CSV file: 5 MB
- DataFrame in memory: ~15 MB (3x file size)
- Working memory: ~10 MB
- **Total:** ~30 MB per process

**Target Memory Usage (estimated):**

- CSV file: 375 MB
- DataFrame in memory: ~1.1 GB (3x file size)
- Working memory: ~400 MB
- **Total:** ~1.5 GB per process

**Assessment:** Single-threaded processing is feasible but risky. Need chunking or multiprocessing.

### 4.4 Scalability Recommendations

#### 4.4.1 Short-Term (Current Architecture)

**Goal:** Handle 1.5M transactions on single machine

1. **Implement chunked CSV processing:**

```python
class ChunkedProcessor:
    """Process large CSV files in chunks to limit memory usage."""

    def process_file(self,
                     input_path: str,
                     output_path: str,
                     chunk_size: int = 50000) -> ProcessingStats:
        """
        Process CSV in chunks of chunk_size rows.

        Memory usage: chunk_size * row_size * 3
        Example: 50K rows * 1KB * 3 = 150 MB
        """
        chunks = []
        for chunk_df in pd.read_csv(input_path, chunksize=chunk_size):
            processed_chunk = self.process_chunk(chunk_df)
            chunks.append(processed_chunk)

        # Concatenate and write
        result_df = pd.concat(chunks, ignore_index=True)
        result_df.to_csv(output_path, index=False)
```

1. **Vectorise operations where possible:**

```python
# Before (row-by-row):
for idx, row in df.iterrows():
    if is_eea_country(row['Nationality_1']):
        df.at[idx, 'EEA_Priority'] = 1

# After (vectorised):
df['EEA_Priority'] = df['Nationality_1'].apply(
    lambda x: 1 if is_eea_country(x) else 0
)

# Even better (pandas built-in):
eea_countries = set(['GB', 'DE', 'FR', ...])
df['EEA_Priority'] = df['Nationality_1'].isin(eea_countries).astype(int)
```

1. **Add progress reporting:**

```python
from tqdm import tqdm

for chunk in tqdm(chunks, desc="Processing"):
    process_chunk(chunk)
```

1. **Implement batch mode for all scripts:**
   - Already done for validation scripts ✅
   - Extend to SQL generation, data push
   - Enable processing all 129 incidents in one command

#### 4.4.2 Medium-Term (Parallel Architecture)

**Goal:** Process 1.5M transactions in <2 hours

1. **Multiprocessing for CPU-bound tasks:**

```python
from multiprocessing import Pool
from functools import partial

def process_record_batch(records: List[ClientRecord],
                         config: ProcessorConfig) -> List[ClientRecord]:
    """Process batch of records (CPU-bound validation)."""
    processor = IDValidationProcessor(config)
    return [processor.validate_record(r) for r in records]

def process_file_parallel(input_path: str,
                         output_path: str,
                         num_workers: int = 4) -> ProcessingStats:
    """Process file using multiple CPU cores."""

    # Split into batches
    df = pd.read_csv(input_path)
    batch_size = len(df) // num_workers
    batches = [df.iloc[i:i+batch_size] for i in range(0, len(df), batch_size)]

    # Process in parallel
    with Pool(num_workers) as pool:
        process_func = partial(process_record_batch, config=config)
        results = pool.map(process_func, batches)

    # Combine results
    result_df = pd.concat(results, ignore_index=True)
    result_df.to_csv(output_path, index=False)
```

1. **Distributed processing for 129 incidents:**

```python
# Celery task queue
from celery import Celery

app = Celery('txr_automation', broker='redis://localhost:6379')

@app.task
def process_incident(incident_code: str, config: dict) -> dict:
    """Process single incident as async task."""
    processor = AccuracyTestingProcessor(config)
    return processor.process_incident(incident_code)

# Submit all incidents
from celery import group

job = group(
    process_incident.s(incident, config)
    for incident in all_incident_codes
)
result = job.apply_async()
```

1. **Database-backed intermediate storage:**

```python
# Instead of passing 1.5M records between processes,
# write to SQLite or PostgreSQL

import sqlite3

def process_with_database(input_csv: str, output_csv: str):
    """Use SQLite for intermediate storage."""
    
    # Load CSV to database
    conn = sqlite3.connect(':memory:')  # or temp file
    df = pd.read_csv(input_csv)
    df.to_sql('records', conn, index=False)
    
    # Process with SQL
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE records
        SET Error_Flag = 'Y'
        WHERE ID_Code IS NULL OR ID_Code = ''
    """)
    
    # Export to CSV
    result = pd.read_sql('SELECT * FROM records', conn)
    result.to_csv(output_csv, index=False)
```

#### 4.4.3 Long-Term (Cloud Architecture)

**Goal:** Handle daily processing with auto-scaling

```md
┌─────────────────────────────────────────────────┐
│              Orchestration Layer                │
│         (Airflow / Prefect / Dagster)           │
│                                                 │
│  DAG: Daily Accuracy Testing                    │
│    1. Generate SQL extracts (parallel)          │
│    2. Run database queries (parallel)           │
│    3. Validate incidents (parallel, 129 tasks)  │
│    4. Aggregate results                         │
│    5. Notify on completion                      │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────┴──────────────────────────────┐
│              Compute Layer                      │
│                                                 │
│   Container Pool (Docker/Kubernetes)            │
│   ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐           │
│   │Worker│ │Worker│ │Worker│ │Worker│  ...      │
│   │  1   │ │  2   │ │  3   │ │  N   │           │
│   └──────┘ └──────┘ └──────┘ └──────┘           │
│   Auto-scaling based on queue depth             │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────┴──────────────────────────────┐
│              Storage Layer                      │
│                                                 │
│  ┌──────────────┐  ┌──────────────────────┐     │
│  │  SQL Server  │  │  Object Storage      │     │
│  │  (Source DB) │  │  (S3/Azure Blob)     │     │
│  └──────────────┘  └──────────────────────┘     │
│                                                 │
│  ┌──────────────────────────────────────────┐   │
│  │  Results Database (PostgreSQL)           │   │
│  │  - Validation results                    │   │
│  │  - Audit logs                            │   │
│  │  - Processing metrics                    │   │ 
│  └──────────────────────────────────────────┘   │ 
└─────────────────────────────────────────────────┘
```

**Implementation:**

- Docker containers for each worker
- Kubernetes for orchestration and auto-scaling
- Message queue (RabbitMQ/Redis) for task distribution
- Shared storage (NFS/S3) for CSV files
- PostgreSQL for results aggregation
- Prometheus + Grafana for monitoring

---

## 5. Deployment Architecture

### 5.1 Current Deployment Process

**Manual Process:**

1. Clone Git repository
2. Create conda environment from `environment.yml`
3. Install package in editable mode (`pip install -e .`)
4. Copy config templates to `config/local/`
5. Edit config files manually with absolute paths
6. Run scripts via console scripts

**Assessment:**

- ⚠️ **Manual and error-prone:** Easy to miss steps
- ⚠️ **No versioning:** No guarantee of consistent environments
- ⚠️ **No rollback:** Can't easily revert to previous version
- ⚠️ **No isolation:** All users share same network paths
- ⚠️ **No monitoring:** No way to track deployments or failures

### 5.2 Recommended Deployment Strategy

#### 5.2.1 Environment Separation

**Development Environment:**

- **Purpose:** Active development and testing
- **Location:** Developer laptops
- **Data:** Small sample datasets (1000 records)
- **Configuration:** `TXR_ENV=development`
- **Deployment:** Git clone + conda env

**Test Environment:**

- **Purpose:** Integration testing and UAT
- **Location:** Shared test server or developer laptop
- **Data:** Realistic test data (10,000 records)
- **Configuration:** `TXR_ENV=test`
- **Deployment:** Git clone + conda env

**Production Environment:**

- **Purpose:** Live processing for regulatory reporting
- **Location:** Production server or analyst workstations
- **Data:** Full dataset (1.5M records)
- **Configuration:** `TXR_ENV=production`
- **Deployment:** Docker container or conda env

**Environment Configuration:**

```yaml
# config/environments/development/defaults.yaml
data:
  base_path: "./data"
  extract_dir: "./data/extracts"
  template_dir: "./data/templates"
  output_dir: "./data/output"
  
processing:
  batch_size: 1000
  num_workers: 1
  
logging:
  level: "DEBUG"
  output: "./logs"

# config/environments/production/defaults.yaml
data:
  base_path: "/mnt/txr_data"
  extract_dir: "/mnt/txr_data/extracts"
  template_dir: "/mnt/txr_data/templates"
  output_dir: "/mnt/txr_data/output"
  
processing:
  batch_size: 50000
  num_workers: 4
  
logging:
  level: "INFO"
  output: "/var/log/txr_automation"
```

#### 5.2.2 Containerised Deployment (Docker)

**Benefits:**

- ✅ Consistent environment across all machines
- ✅ Easy rollback to previous versions
- ✅ Isolated dependencies
- ✅ Portable (runs on Windows, macOS, Linux)
- ✅ Can be orchestrated (Docker Compose, Kubernetes)

**Dockerfile:**

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy only requirements first (for caching)
COPY requirements.txt environment.yml ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY config/ ./config/
COPY documentation/ ./documentation/
COPY setup.py README.md ./

# Install package
RUN pip install -e .

# Create non-root user
RUN useradd -m -u 1000 txr_user && chown -R txr_user:txr_user /app
USER txr_user

# Default command
CMD ["bash"]
```

**Docker Compose (for local testing):**

```yaml
version: '3.8'

services:
  txr_automation:
    build: .
    image: txr_automation:1.0.0
    environment:
      TXR_ENV: development
      TXR_LOG_LEVEL: INFO
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./config/local:/app/config/local
    command: validate-buyer --config /app/config/local/accuracy_testing/buyer_validation.yaml
```

**Usage:**

```bash
# Build image
docker build -t txr_automation:1.0.0 .

# Run validation
docker run -v $(pwd)/data:/app/data \
           -v $(pwd)/logs:/app/logs \
           -e TXR_ENV=development \
           txr_automation:1.0.0 \
           validate-buyer --config /app/config/local/buyer_validation.yaml

# Or use Docker Compose
docker-compose up txr_automation
```

#### 5.2.3 Package Distribution

**Options:**

1. **Private PyPI Repository (Recommended for Production):**

   ```bash
   # Build wheel
   python setup.py sdist bdist_wheel

   # Upload to private PyPI
   twine upload --repository-url https://pypi.company.com/simple dist/*

   # Install on user machines
   pip install --index-url https://pypi.company.com/simple txr-automation==1.0.0
   ```

2. **Git + Conda (Current approach, good for development):**

   ```bash
   git clone https://github.com/company/txr_automation.git
   cd txr_automation
   conda env create -f environment.yml
   conda activate txr_automation
   pip install -e .
   ```

3. **Executable Bundle (easiest for analysts):**

```bash
# Use PyInstaller to create standalone executable
pyinstaller --onefile \
            --name txr-automation \
            --add-data "documentation:documentation" \
            --add-data "config:config" \
            src/accuracy_testing/scripts/run_all_validations.py

# Distribute as single .exe file (Windows) or binary (macOS/Linux)
```

#### 5.2.4 CI/CD Pipeline

**Recommended Pipeline (GitHub Actions / GitLab CI):**

```yaml
# .github/workflows/main.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, vba-migration]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install -e .
      
      - name: Run tests
        run: |
          pytest tests/ --cov=src --cov-report=xml
      
      - name: Run static analysis
        run: |
          pylint src/
          mypy src/
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
  
  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3
      
      - name: Build Docker image
        run: |
          docker build -t txr_automation:${{ github.sha }} .
          docker tag txr_automation:${{ github.sha }} txr_automation:latest
      
      - name: Push to registry
        run: |
          echo "${{ secrets.DOCKER_PASSWORD }}" | docker login -u "${{ secrets.DOCKER_USERNAME }}" --password-stdin
          docker push txr_automation:latest
  
  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Deploy to production
        run: |
          # SSH to production server and pull new image
          ssh user@prod-server "docker pull txr_automation:latest && docker-compose up -d"
```

---

## 6. Automation & Orchestration

### 6.1 Current State

**Manual Execution:**

- User runs each script sequentially
- Manual checking of outputs between steps
- Manual selection of files and directories
- No error recovery or retry logic

**Issues:**

- ⚠️ Error-prone (easy to skip steps or use wrong files)
- ⚠️ Time-consuming (user must monitor all steps)
- ⚠️ No auditability (no record of what was run when)
- ⚠️ Can't scale to daily processing

### 6.2 Recommended Automation Architecture

#### 6.2.1 Workflow Engine (Short-Term Solution)

***Option 1: Simple Shell Scripts***

Good for quarterly processing with manual triggers.

```bash
#!/bin/bash
# run_quarterly_accuracy_testing.sh

set -e  # Exit on error
set -u  # Exit on undefined variable

# Configuration
FISCAL_YEAR="FY26"
QUARTER="Q3"
BASE_DIR="/mnt/txr_data"
LOG_DIR="$BASE_DIR/logs/$(date +%Y%m%d_%H%M%S)"

# Create log directory
mkdir -p "$LOG_DIR"

# Step 1: Generate templates
echo "Step 1: Generating templates..."
generate-accuracy-template \
    --config config/local/accuracy_testing/template_generator.yaml \
    --fiscal-year "$FISCAL_YEAR" \
    --quarter "$QUARTER" \
    2>&1 | tee "$LOG_DIR/01_template_generation.log"

# Step 2: Generate SQL extracts
echo "Step 2: Generating SQL extracts..."
generate-sql-extract \
    --config config/local/accuracy_testing/sql_generator.yaml \
    --fiscal-year "$FISCAL_YEAR" \
    --quarter "$QUARTER" \
    2>&1 | tee "$LOG_DIR/02_sql_generation.log"

# Step 3: Run validations (parallel)
echo "Step 3: Running validations..."
validate-all \
    --config config/local/accuracy_testing/run_all_validations.yaml \
    --fiscal-year "$FISCAL_YEAR" \
    --quarter "$QUARTER" \
    --parallel \
    --num-workers 4 \
    2>&1 | tee "$LOG_DIR/03_validations.log"

# Step 4: Data push
echo "Step 4: Pushing validated data..."
data-push \
    --config config/local/accuracy_testing/data_push.yaml \
    --fiscal-year "$FISCAL_YEAR" \
    --quarter "$QUARTER" \
    2>&1 | tee "$LOG_DIR/04_data_push.log"

# Step 5: Generate summary report
echo "Step 5: Generating summary report..."
python -m src.accuracy_testing.scripts.generate_summary_report \
    --log-dir "$LOG_DIR" \
    --output "$LOG_DIR/summary_report.html" \
    2>&1 | tee "$LOG_DIR/05_summary.log"

echo "✅ Quarterly accuracy testing complete!"
echo "📊 Summary report: $LOG_DIR/summary_report.html"
```

***Option 2: Python Workflow Manager***

Better for daily processing with dependencies and error handling.

```python
# src/automation/workflow_manager.py

from dataclasses import dataclass
from typing import List, Callable, Optional
from enum import Enum
import logging

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class Task:
    """Workflow task definition."""
    name: str
    function: Callable
    dependencies: List[str] = None
    retry_count: int = 3
    timeout: Optional[int] = None

class WorkflowManager:
    """Manage workflow execution with dependency resolution."""

    def __init__(self):
        self.tasks = {}
        self.results = {}
        self.logger = logging.getLogger(__name__)

    def add_task(self, task: Task):
        """Add task to workflow."""
        self.tasks[task.name] = task
        self.results[task.name] = TaskStatus.PENDING

    def run(self):
        """Execute workflow with dependency resolution."""
        for task_name in self._topological_sort():
            task = self.tasks[task_name]

            # Check dependencies
            if not self._dependencies_met(task):
                self.logger.warning(f"Skipping {task_name} - dependencies not met")
                self.results[task_name] = TaskStatus.SKIPPED
                continue

            # Execute with retry
            self.results[task_name] = TaskStatus.RUNNING
            success = self._execute_with_retry(task)

            if success:
                self.results[task_name] = TaskStatus.SUCCESS
            else:
                self.results[task_name] = TaskStatus.FAILED
                if task.critical:
                    raise RuntimeError(f"Critical task {task_name} failed")

    def _execute_with_retry(self, task: Task) -> bool:
        """Execute task with retry logic."""
        for attempt in range(task.retry_count):
            try:
                self.logger.info(f"Running {task.name} (attempt {attempt+1}/{task.retry_count})")
                task.function()
                return True
            except Exception as e:
                self.logger.error(f"Task {task.name} failed: {e}")
                if attempt == task.retry_count - 1:
                    return False
        return False

# Usage:
workflow = WorkflowManager()

workflow.add_task(Task(
    name="generate_templates",
    function=lambda: generate_accuracy_template(config),
    dependencies=[],
))

workflow.add_task(Task(
    name="generate_sql",
    function=lambda: generate_sql_extract(config),
    dependencies=["generate_templates"],
))

workflow.add_task(Task(
    name="run_validations",
    function=lambda: validate_all(config),
    dependencies=["generate_sql"],
))

workflow.run()
```

#### 6.2.2 Enterprise Workflow Orchestration (Long-Term)

***Recommended: Apache Airflow***

Benefits:

- ✅ Industry-standard workflow orchestration
- ✅ Web UI for monitoring
- ✅ Built-in scheduling (cron-like)
- ✅ Retry and error handling
- ✅ Parallel task execution
- ✅ Extensive logging and alerting

```python
# dags/quarterly_accuracy_testing.py

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'txr_team',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'email': ['txr_team@company.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'quarterly_accuracy_testing',
    default_args=default_args,
    description='Quarterly accuracy testing workflow',
    schedule_interval='0 0 1 */3 *',  # Run on first day of quarter
    catchup=False,
)

# Task 1: Generate templates
generate_templates = PythonOperator(
    task_id='generate_templates',
    python_callable=run_template_generation,
    op_kwargs={'fiscal_year': '{{ ds }}', 'quarter': '{{ execution_date.quarter }}'},
    dag=dag,
)

# Task 2: Generate SQL extracts (depends on templates)
generate_sql = PythonOperator(
    task_id='generate_sql',
    python_callable=run_sql_generation,
    op_kwargs={'fiscal_year': '{{ ds }}', 'quarter': '{{ execution_date.quarter }}'},
    dag=dag,
)

# Task 3: Run validations (parallel)
validation_tasks = []
for incident in ['7_35', '7_37', '7_39', ...]:  # All 129 incidents
    task = PythonOperator(
        task_id=f'validate_{incident}',
        python_callable=run_validation,
        op_kwargs={'incident_code': incident},
        dag=dag,
    )
    validation_tasks.append(task)

# Task 4: Aggregate results
aggregate = PythonOperator(
    task_id='aggregate_results',
    python_callable=aggregate_validation_results,
    dag=dag,
)

# Task 5: Data push
data_push_task = PythonOperator(
    task_id='data_push',
    python_callable=run_data_push,
    dag=dag,
)

# Task 6: Generate report
generate_report = PythonOperator(
    task_id='generate_report',
    python_callable=generate_summary_report,
    dag=dag,
)

# Define dependencies
generate_templates >> generate_sql >> validation_tasks >> aggregate >> data_push_task >> generate_report
```

***Alternative: Prefect (Modern, Python-native)***

```python
from prefect import flow, task
from prefect.task_runners import DaskTaskRunner

@task
def generate_templates(fiscal_year: str, quarter: str):
    # Template generation logic
    pass

@task
def validate_incident(incident_code: str):
    # Validation logic
    pass

@flow(task_runner=DaskTaskRunner())
def quarterly_accuracy_testing(fiscal_year: str, quarter: str):
    """Run quarterly accuracy testing workflow."""

    # Step 1
    generate_templates(fiscal_year, quarter)

    # Step 2: Validate all incidents in parallel
    incident_codes = get_all_incident_codes()
    validation_results = validate_incident.map(incident_codes)

    # Step 3: Aggregate
    aggregate_results(validation_results)

# Deploy to Prefect Cloud for scheduling
if __name__ == "__main__":
    quarterly_accuracy_testing.deploy(
        name="quarterly-accuracy-testing",
        work_pool_name="txr-processing",
        cron="0 0 1 */3 *",  # Quarterly
    )
```

### 6.3 Scheduling Recommendations

| Frequency | Mechanism | Rationale |
| ----------- | ----------- | ----------- |
| **Quarterly** | Manual trigger with shell script | Current workflow, user needs control |
| **Monthly** | Cron job + shell script | Simple, reliable for monthly tasks |
| **Daily** | Airflow/Prefect with monitoring | Complex dependencies, need error handling |

**Implementation Priority:**

1. **Now:** Shell script for quarterly automation
2. **Q2 2026:** Python workflow manager for monthly processing
3. **Q4 2026:** Airflow/Prefect for daily processing

---

## 7. GUI Architecture Options

### 7.1 Requirements Analysis

Based on user needs:

- ✅ Select which script to run
- ✅ Select files/directories without editing config
- ✅ View progress and logs in real-time
- ✅ Review validation results
- ✅ Archive and audit trail

**Users:** Oversight analysts (non-developers)  
**Deployment:** Desktop application on Windows/macOS  
**Integration:** Must work with existing Python scripts

### 7.2 Architecture Pattern

***Recommended: Decoupled Architecture***

```md

┌─────────────────────────────────────────────────┐
│            Presentation Layer (GUI)             │
│              (Electron / PyQt / Web)            │
│                                                 │
│  - File pickers                                 │
│  - Script selection                             │
│  - Progress bars                                │
│  - Log viewer                                   │
│  - Results dashboard                            │
└────────────────┬────────────────────────────────┘
                 │ HTTP REST API or Message Queue
┌────────────────┴────────────────────────────────┐
│              Application Layer (API)            │
│                  (FastAPI / Flask)              │
│                                                 │
│  - /api/scripts/list                            │
│  - /api/scripts/run                             │
│  - /api/scripts/status                          │
│  - /api/files/browse                            │
│  - /api/results/view                            │
└────────────────┬────────────────────────────────┘
                 │ Python function calls
┌────────────────┴────────────────────────────────┐
│          Business Logic Layer                   │
│      (Existing Python Scripts/Modules)          │
│                                                 │
│  - accuracy_testing.scripts.*                   │
│  - replay.*                                     │
│  - core.*                                       │
└─────────────────────────────────────────────────┘
```

**Key Principles:**

1. **Keep existing CLI scripts:** GUI is a wrapper, not a replacement
2. **API layer:** Enables future web interface or integration
3. **Loose coupling:** GUI can be replaced without changing business logic

### 7.3 Technology Options

#### Option 1: Electron + React (Web Technologies)

**Architecture:**

```md

┌──────────────────────────────────────────┐
│         Electron Application             │
├──────────────────────────────────────────┤
│  Frontend: React + TypeScript            │
│  - Material-UI components                │
│  - Redux for state management            │
│  - Axios for API calls                   │
├──────────────────────────────────────────┤
│  Backend: FastAPI (Python)               │
│  - Runs as subprocess or separate server │
│  - REST API endpoints                    │
│  - WebSocket for real-time logs          │
└──────────────────────────────────────────┘
```

**Pros:**

- ✅ Modern, polished UI
- ✅ Cross-platform (Windows, macOS, Linux)
- ✅ Easy to iterate and prototype
- ✅ Large developer community
- ✅ Can become web app later

**Cons:**

- ⚠️ Larger bundle size (~150 MB)
- ⚠️ Requires JavaScript/TypeScript knowledge
- ⚠️ Two-language project (Python + JS)

**Code Example:**

```typescript
// frontend/src/components/ScriptRunner.tsx
import React, { useState } from 'react';
import { Button, Select, TextField, LinearProgress } from '@mui/material';

const ScriptRunner: React.FC = () => {
  const [script, setScript] = useState('validate-buyer');
  const [status, setStatus] = useState('idle');
  
  const runScript = async () => {
    setStatus('running');
    const response = await fetch('http://localhost:8000/api/scripts/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        script_name: script,
        config: selectedConfig,
      }),
    });
    const result = await response.json();
    setStatus('complete');
  };
  
  return (
    <div>
      <Select value={script} onChange={e => setScript(e.target.value)}>
        <option value="validate-buyer">Buyer ID Validation</option>
        <option value="validate-seller">Seller ID Validation</option>
      </Select>
      <Button onClick={runScript}>Run Script</Button>
      {status === 'running' && <LinearProgress />}
    </div>
  );
};
```

```python
# backend/api.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import subprocess

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"])

@app.post("/api/scripts/run")
async def run_script(request: ScriptRequest):
    """Execute script as subprocess and return results."""
    process = subprocess.Popen(
        [request.script_name, "--config", request.config_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = process.communicate()
    return {
        "status": "success" if process.returncode == 0 else "error",
        "stdout": stdout.decode(),
        "stderr": stderr.decode(),
    }
```

#### Option 2: PyQt6 (Native Python)

**Architecture:**

```md

┌──────────────────────────────────────────┐
│        PyQt6 Desktop Application         │
├──────────────────────────────────────────┤
│  UI: Qt Widgets + Qt Designer            │
│  - QTableWidget for data views           │
│  - QComboBox for dropdowns               │
│  - QFileDialog for file pickers          │
│  - QTextEdit for logs                    │
├──────────────────────────────────────────┤
│  Logic: Direct Python imports            │
│  - Import accuracy_testing.*             │
│  - Import replay.*                       │
│  - Run in QThread for async              │
└──────────────────────────────────────────┘
```

**Pros:**

- ✅ Pure Python (no JavaScript)
- ✅ Native look and feel
- ✅ Smaller bundle size (~50 MB)
- ✅ Direct access to Python modules
- ✅ Faster performance

**Cons:**

- ⚠️ Steeper learning curve (Qt framework)
- ⚠️ Less modern-looking UI
- ⚠️ Platform-specific packaging

**Code Example:**

```python
# gui/main_window.py
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QComboBox, 
    QPushButton, QTextEdit, QFileDialog, QProgressBar
)
from PyQt6.QtCore import QThread, pyqtSignal
from src.accuracy_testing.scripts import buyer_id_validation

class ScriptRunnerThread(QThread):
    """Run script in background thread."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    
    def __init__(self, script_name, config):
        super().__init__()
        self.script_name = script_name
        self.config = config
    
    def run(self):
        """Execute script."""
        if self.script_name == "buyer_validation":
            result = buyer_id_validation.main(self.config)
            self.finished.emit(result)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        """Build UI."""
        central_widget = QWidget()
        layout = QVBoxLayout()
        
        # Script selector
        self.script_combo = QComboBox()
        self.script_combo.addItems([
            "Buyer ID Validation",
            "Seller ID Validation",
            "Inconsistent Buyer ID",
            "Pricing Validation",
        ])
        layout.addWidget(self.script_combo)
        
        # File picker
        self.file_button = QPushButton("Select Input File")
        self.file_button.clicked.connect(self.select_file)
        layout.addWidget(self.file_button)
        
        # Run button
        self.run_button = QPushButton("Run Script")
        self.run_button.clicked.connect(self.run_script)
        layout.addWidget(self.run_button)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        # Log viewer
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        layout.addWidget(self.log_viewer)
        
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
    
    def select_file(self):
        """Open file picker."""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select Input CSV",
            "",
            "CSV Files (*.csv)"
        )
        if filename:
            self.log_viewer.append(f"Selected: {filename}")
    
    def run_script(self):
        """Execute selected script."""
        self.run_button.setEnabled(False)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        
        # Run in background thread
        self.thread = ScriptRunnerThread(
            self.script_combo.currentText(),
            self.config
        )
        self.thread.progress.connect(self.log_viewer.append)
        self.thread.finished.connect(self.on_finished)
        self.thread.start()
    
    def on_finished(self, result):
        """Handle completion."""
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.run_button.setEnabled(True)
        self.log_viewer.append(f"✅ Complete: {result}")
```

#### Option 3: Streamlit (Rapid Prototyping)

**Architecture:**

```md

┌──────────────────────────────────────────┐
│       Streamlit Web Application          │
│   (Runs local web server, opens browser) │
├──────────────────────────────────────────┤
│  UI: Streamlit components                │
│  - st.selectbox() for dropdowns          │
│  - st.file_uploader() for files          │
│  - st.progress() for progress            │
│  - st.dataframe() for results            │
├──────────────────────────────────────────┤
│  Logic: Direct Python imports            │
│  - Import and call scripts directly      │
└──────────────────────────────────────────┘
```

**Pros:**

- ✅ Fastest to develop (can build in hours)
- ✅ Pure Python (no HTML/CSS/JS)
- ✅ Beautiful, modern UI
- ✅ Great for prototyping

**Cons:**

- ⚠️ Not a true desktop app (runs in browser)
- ⚠️ Limited customisation
- ⚠️ Not suitable for production GUI

**Code Example:**

```python
# gui/streamlit_app.py
import streamlit as st
from src.accuracy_testing.scripts import buyer_id_validation

st.title("Transaction Reporting Automation")

# Script selection
script = st.selectbox(
    "Select Script",
    ["Buyer ID Validation", "Seller ID Validation", "Pricing Validation"]
)

# File upload
input_file = st.file_uploader("Upload Input CSV", type=["csv"])

# Configuration
with st.expander("Configuration"):
    log_level = st.selectbox("Log Level", ["DEBUG", "INFO", "WARNING", "ERROR"])
    batch_size = st.number_input("Batch Size", value=1000)

# Run button
if st.button("Run Script"):
    if input_file is not None:
        with st.spinner("Processing..."):
            # Save uploaded file
            with open("temp_input.csv", "wb") as f:
                f.write(input_file.getbuffer())
            
            # Run validation
            result = buyer_id_validation.main({
                'input_file': 'temp_input.csv',
                'output_file': 'temp_output.csv',
                'log_level': log_level,
            })
            
            st.success(f"✅ Complete! Processed {result.total_records} records")
            
            # Display results
            st.subheader("Results")
            st.dataframe(result.stats)
            
            # Download button
            with open("temp_output.csv", "rb") as f:
                st.download_button(
                    "Download Results",
                    f,
                    file_name="validation_results.csv",
                    mime="text/csv"
                )
    else:
        st.error("Please upload a file first")
```

### 7.4 Recommendation

***Phase 1 (Q2 2026): Streamlit Prototype***

- Build working GUI in 2-3 days
- Get user feedback quickly
- Iterate on design

***Phase 2 (Q3 2026): PyQt6 Production GUI***

- Build polished desktop application
- Package as standalone executable
- Deploy to analyst workstations

***Phase 3 (2027+): Optional Web Interface***

- If needed, build web version with FastAPI + React
- Enable remote access and multi-user scenarios

**Rationale:**

- PyQt6 is best fit for desktop application for analysts
- Easier to deploy (single executable)
- Better performance
- No browser dependency
- Can still add web interface later via API layer

---

## 8. Technical Debt & Risks

### 8.1 Current Technical Debt

| Item | Severity | Impact | Effort to Fix |
| ------ | ---------- | -------- | --------------- |
| **Configuration duplication** (core vs accuracy_testing) | High | Maintenance burden, inconsistent behavior | Medium (2 weeks) |
| **15 failing tests** (v2.0 config format) | High | Can't trust test suite | Low (1 week) |
| **No environment separation** | Medium | Risky deployments | Medium (2 weeks) |
| **Manual deployment** | Medium | Error-prone, time-consuming | Medium (2 weeks) |
| **No automated workflows** | High | Can't scale to daily processing | High (1 month) |
| **No monitoring/observability** | Medium | Can't diagnose production issues | Medium (2 weeks) |
| **Performance not tested at scale** | High | Unknown if can handle 1.5M records | Medium (1 week benchmarking) |

### 8.2 Architectural Risks

| Risk | Likelihood | Impact | Mitigation |
| ------ | ------------ | -------- | ------------ |
| **Memory exhaustion at 1.5M scale** | Medium | High | Implement chunked processing |
| **Network drive latency** | Medium | Medium | Cache locally, batch I/O |
| **Configuration complexity** | High | Medium | Unify config management |
| **Deployment failures** | Medium | High | Containerize + CI/CD |
| **User adoption of CLI** | High | High | Build GUI quickly |
| **Data corruption** | Low | Critical | Add validation + checksums |

### 8.3 Remediation Roadmap

**Critical (Do First):**

1. Fix 15 failing tests
2. Unify configuration management
3. Benchmark performance with 1.5M records
4. Implement chunked CSV processing

**High Priority (Q2 2026):**

1. Set up dev/test/prod environments
2. Build Streamlit prototype GUI
3. Create shell script automation
4. Implement CI/CD pipeline

**Medium Priority (Q3 2026):**

1. Build PyQt6 production GUI
2. Containerize deployment
3. Add monitoring/logging infrastructure
4. Implement parallel processing

**Low Priority (Q4 2026):**

1. Orchestration with Airflow/Prefect
2. Performance optimization (Cython/Numba)
3. Distributed processing architecture

---

## 9. Strategic Recommendations Summary

### 9.1 Immediate Actions (Next 2 Weeks)

1. ✅ **Fix failing tests and config duplication**
   - Goal: Get test suite to 100% passing
   - Merge `AccuracyConfigManager` into `core.config.ConfigManager`
   - Update all scripts to use unified config

2. ✅ **Performance benchmarking**
   - Goal: Understand current performance limits
   - Create test dataset with 100K, 500K, 1M rows
   - Measure memory usage and processing time
   - Identify bottlenecks

3. ✅ **Document architectural decisions**
   - Goal: Create knowledge base for team
   - Write `ARCHITECTURE.md` with system overview
   - Document configuration patterns
   - Create module dependency diagram

### 9.2 Short-Term (Q2 2026)

1. ✅ **Implement chunked CSV processing**
   - Goal: Handle 1.5M records without memory issues
   - Add `ChunkedProcessor` to `core.processing`
   - Update all validation scripts to use chunking
   - Test with full scale dataset

2. ✅ **Set up environment separation**
   - Goal: Enable safe testing and deployment
   - Create `config/environments/{dev,test,prod}/`
   - Implement environment-aware path resolution
   - Add `TXR_ENV` environment variable

3. ✅ **Build Streamlit GUI prototype**
   - Goal: Get user feedback on GUI approach
   - Create basic file selection + script execution
   - Add progress monitoring and log viewing
   - User testing with Oversight team

4. ✅ **Automate workflow with shell scripts**
   - Goal: Reduce manual execution errors
   - Create `run_quarterly_accuracy_testing.sh`
   - Add error handling and logging
   - Document usage

### 9.3 Medium-Term (Q3-Q4 2026)

1. ✅ **Containerize with Docker**
   - Goal: Consistent deployment across machines
   - Create Dockerfile and docker-compose.yml
   - Test on Windows, macOS, Linux
   - Document deployment process

2. ✅ **Build PyQt6 production GUI**
   - Goal: Replace CLI for analyst users
   - Implement file pickers, script selection, progress monitoring
   - Package as standalone executable
   - Deploy to Oversight team workstations

3. ✅ **Implement CI/CD pipeline**
    - Goal: Automate testing and deployment
    - Set up GitHub Actions or GitLab CI
    - Run tests on every commit
    - Auto-deploy to test environment

4. ✅ **Parallel processing for incidents**
    - Goal: Process 129 incidents efficiently
    - Implement multiprocessing for validation
    - Add progress reporting and error handling
    - Test with full incident load

### 9.4 Long-Term (2027+)

1. ✅ **Orchestration with Airflow/Prefect**
    - Goal: Enable daily automated processing
    - Set up orchestration platform
    - Define DAGs for all workflows
    - Implement scheduling and monitoring

2. ✅ **Distributed architecture**
    - Goal: Cloud-scale processing
    - Kubernetes deployment
    - Message queue for task distribution
    - Auto-scaling based on load

3. ✅ **Web interface (optional)**
    - Goal: Enable remote access
    - FastAPI backend
    - React frontend
    - Multi-user authentication

---

## 10. Conclusion

The Transaction Reporting Automation system is architecturally sound for its current scale but requires strategic enhancements to meet future requirements. The VBA migration has been successfully completed, providing a clean foundation for scaling.

### Key Strengths to Preserve

1. **Clean module boundaries** - Keep separation between core, accuracy_testing, and replay
2. **CSV-first approach** - No Excel dependencies is a major win
3. **Comprehensive testing** - Maintain and expand test coverage
4. **Flexible configuration** - Build on YAML-based approach

### Critical Path Forward

1. **Fix configuration duplication** - This is the highest-leverage improvement
2. **Implement chunked processing** - Essential for 75x scale-up
3. **Build GUI** - Critical for user adoption
4. **Automate workflows** - Required for daily processing

### Success Metrics

- ✅ **Performance:** Process 1.5M transactions in <2 hours
- ✅ **Reliability:** 99.9% success rate for automated runs
- ✅ **Usability:** GUI enables non-technical users to run scripts
- ✅ **Scalability:** Can handle 129 incidents in parallel
- ✅ **Maintainability:** <1 hour to onboard new developer

### Final Thoughts

The architecture is well-positioned for the transition from quarterly manual processing to daily automated operation. The recommendations in this review provide a clear roadmap from the current state (20K transactions, quarterly, manual) to the target state (1.5M transactions, daily, automated).

The key is to take an incremental approach: fix immediate issues, implement short-term scalability improvements, and build toward the long-term vision of a fully automated, cloud-scale processing platform.

---

## Appendices

### Appendix A: Architecture Decision Records

Create `documentation/architecture/decisions/` folder with ADRs:

- `ADR-001-csv-first-architecture.md`
- `ADR-002-unified-configuration-management.md`
- `ADR-003-pyqt6-gui-selection.md`
- `ADR-004-chunked-csv-processing.md`

Template:

```markdown
# ADR-XXX: Title

**Status:** Proposed | Accepted | Deprecated | Superseded  
**Date:** YYYY-MM-DD  
**Decision Makers:** Names

## Context

What is the issue that we're seeing that is motivating this decision or change?

## Decision

What is the change that we're proposing and/or doing?

## Consequences

What becomes easier or more difficult to do because of this change?

### Positive

### Negative

### Neutral

## Alternatives Considered

What other options were evaluated?
```

### Appendix B: Dependency Graph

```md

core/
├── config/ ───────────┐
├── data/ ─────────────┤
├── logging/ ──────────┤
├── utils/ ────────────┤
└── validation/ ───────┤
                       │
                       ├──→ accuracy_testing/
                       │    ├── core/
                       │    ├── models/
                       │    ├── validators/
                       │    ├── processor.py
                       │    └── scripts/
                       │
                       └──→ replay/
                            ├── phase_2_processor.py
                            ├── phase_3_processor.py
                            └── phase_3_final_lookup.py
```

### Appendix C: Network Drive Considerations

**Issue:** Windows network drives (\\\\server\\share) may have high latency.

**Solutions:**

1. **Local caching:**

   ```python
   from pathlib import Path
   import shutil

   def cache_network_file(network_path: Path, cache_dir: Path) -> Path:
       """Copy network file to local cache."""
       cache_path = cache_dir / network_path.name
       if not cache_path.exists():
           shutil.copy2(network_path, cache_path)
       return cache_path
   ```

2. **Batch I/O:**

   ```python
   # Instead of many small reads:
   for file in files:
       df = pd.read_csv(network_path / file)  # ❌ Slow

   # Do one large read:
   df = pd.read_csv(network_path / "data.csv")  # ✅ Fast
   ```

3. **Compression:**

   ```python
   # Use compressed CSV for network transfer
   import gzip
   with gzip.open(network_path / "data.csv.gz", "rt") as f:
       df = pd.read_csv(f)  # Faster transfer, more CPU
   ```

---

***End of Architectural Review***
