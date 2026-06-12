# TXR Automation - System Architecture

**Version:** 3.1  
**Last Updated:** 9 June 2026  
**Status:** Phase 6 (Integration & Testing) — Web app + core engine complete

---

## Executive Summary

TXR Automation is a full-stack web application for validating financial transaction data against regulatory standards. It combines a React frontend, FastAPI backend, and Python validation engine to provide interactive validation, job scheduling, and real-time monitoring for transaction reporting compliance.

**Key Facts:**
- **Architecture:** React 19 (frontend) + FastAPI (backend) + PostgreSQL + Redis
- **Deployment:** Docker Compose with nginx reverse proxy
- **Backend packages:** 7 (core, accuracy_testing, replay, firds, gleif, gui, utils)
- **Console scripts:** 22 registered CLI entry points (batch processing)
- **API endpoints:** 12+ FastAPI routers with OpenAPI documentation
- **Real-time features:** WebSocket support for job status updates
- **Async processing:** Celery task queue with Redis broker
- **Test coverage:** 466+ tests across frontend and backend (100% passing)
- **Performance:** < 30 seconds for 20K records; targeting 1.5M daily volume

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
┌──────────────────────────────────────────────────────────┐
│                   Frontend Layer (React 19)              │
│  • Dashboard (job monitoring, results viewing)           │
│  • Accuracy Tester (interactive validation interface)    │
│  • Job Scheduler (schedule batch processing)             │
│  • Settings & Configuration                              │
│  • Real-time updates via WebSocket                       │
└────────────────────────────┬─────────────────────────────┘
                             │ REST API + WebSocket
                             ↓
┌──────────────────────────────────────────────────────────┐
│              API Layer (FastAPI + Uvicorn)               │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│   │   Routers    │  │  Services    │  │  Schemas     │   │
│   │ • accuracy   │  │ • Celery     │  │ • Validation │   │
│   │ • dashboard  │  │   tasks      │  │ • Response   │   │
│   │ • scheduler  │  │ • Config     │  │   models     │   │
│   │ • firds      │  │ • Database   │  │ • Job models │   │
│   │ • gleif      │  │   queries    │  └──────────────┘   │
│   │ • jobs       │  │ • Validation │                     │
│   │ • pipeline   │  │   logic      │                     │
│   └──────────────┘  └──────────────┘                     │
└────────────────────────────┬─────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────┐
│            Data & Processing Layer (Python)              │
│      ┌──────────────────┐      ┌──────────────────┐      │
│      │ accuracy_testing │      │  Job Queue &     │      │
│      │  • Processor     │      │  Result Store    │      │
│      │  • Validators    │      │  • Celery tasks  │      │
│      │  • Logic checks  │      │  • Redis broker  │      │
│      └────────┬─────────┘      └────────┬─────────┘      │
│               │                         │                │
│      ┌────────┴─────────────────────────┴─────────┐      │
│      │          Core Engine (txr_core)            │      │
│      │  ┌──────────────────────────────────────┐  │      │
│      │  │ ID Validation     | Regulatory Data  │  │      │
│      │  │ • Format checking | • FIRDS caching  │  │      │
│      │  │ • Logic validators| • GLEIF caching  │  │      │
│      │  │ • DM validation   | • API clients    │  │      │
│      │  │ • Pricing logic   │                  │  │      │
│      │  └──────────────────────────────────────┘  │      │
│      └────────────────────────────────────────────┘      │
└─────────────────────────────┬────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────┐
│              Infrastructure & Persistence                │
│  • PostgreSQL (job history, saved configs, audit trail)  │
│  • Redis (Celery broker, WebSocket pub/sub)              │
│  • SQLite (FIRDS cache, GLEIF cache)                     │
│  • CSV files (input/output, reference data)              │
│  • Logs (JSON structured logging)                        │
└──────────────────────────────────────────────────────────┘
```

---

## 2. Module Architecture

### 2.0 API Layer (`api/`)

**Purpose:** FastAPI application serving RESTful endpoints and WebSocket connections for the React frontend.

**Key Components:**

```
api/
├── main.py                    # FastAPI app initialization + lifespan
├── config.py                  # Configuration management + settings
├── database.py                # SQLAlchemy async setup + PostgreSQL
├── models/                    # SQLAlchemy ORM models
│   ├── job.py                 # Job history and status tracking
│   ├── schedule.py            # Scheduled job definitions
│   ├── pipeline.py            # Pipeline execution records
│   └── ...                    # Other domain models
├── schemas/                   # Pydantic request/response models
├── routers/                   # API endpoint groups (organized by domain)
│   ├── accuracy.py            # POST /accuracy/validate-*, GET /accuracy/*
│   ├── dashboard.py           # GET /dashboard/jobs, /dashboard/stats
│   ├── scheduler.py           # POST/GET /scheduler/schedules, /run
│   ├── jobs.py                # GET/DELETE /jobs/{id}, /jobs/history
│   ├── firds.py               # GET /firds/check, POST /firds/refresh
│   ├── gleif.py               # GET /gleif/check, POST /gleif/refresh
│   ├── pipeline.py            # POST /pipeline/execute
│   ├── health.py              # GET /health, /health/database, /health/redis
│   └── ...                    # Other routers
├── services/                  # Business logic and Celery task integration
│   ├── accuracy_service.py    # Validation orchestration
│   ├── job_service.py         # Job lifecycle management
│   ├── scheduler_service.py   # Schedule persistence + trigger
│   └── ...                    # Other services
├── tasks/                     # Celery async tasks
│   ├── validation_tasks.py    # Long-running validation jobs
│   ├── scheduling_tasks.py    # Scheduled job execution
│   └── ...                    # Other tasks
├── utils/                     # API utilities (decorators, middleware)
└── websocket/                 # WebSocket handlers for real-time updates
    └── job_monitor.py         # Job status streaming
```

**Key Classes:**
- **`APISettings`:** Configuration dataclass with environment variable overrides
- **`JobModel`:** SQLAlchemy ORM for job history persistence
- **`ValidationRequest`:** Pydantic schema for accuracy validation requests
- **`JobResponse`:** Pydantic schema for job status responses

**Architecture Patterns:**
- **Dependency Injection:** FastAPI `Depends()` for database sessions, config
- **Async/Await:** All endpoints and services are async
- **Celery Integration:** Long-running validations offloaded to task queue
- **WebSocket Pub/Sub:** Redis channels for real-time job status updates

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

### 2.6 Frontend Module (`web/`)

**Purpose:** React 19 single-page application providing the primary user interface for TXR Automation.

**Architecture:** React Router → Page components → Service layer → API client

**Key Components:**

```
web/src/
├── App.tsx                    # Root component + routing
├── components/                # Reusable UI components
│   ├── dashboard/             # Dashboard widgets
│   ├── accuracy-tester/       # Validation interface
│   ├── job-monitor/           # Job status display
│   ├── common/                # Shared components (buttons, cards, etc.)
│   └── ...                    # Other components
├── pages/                     # Page-level components
│   ├── dashboard.tsx          # Main dashboard page
│   ├── accuracy.tsx           # Accuracy tester page
│   ├── scheduler.tsx          # Job scheduling page
│   └── settings.tsx           # Configuration page
├── hooks/                     # Custom React hooks
│   ├── useQuery.ts            # Data fetching with caching
│   ├── useWebSocket.ts        # WebSocket connection management
│   └── ...                    # Other hooks
├── services/                  # API client and integrations
│   ├── api.ts                 # HTTP client (axios/fetch wrapper)
│   ├── websocket.ts           # WebSocket client
│   └── accuracy.ts            # Accuracy API service
├── stores/                    # Zustand state management
│   ├── jobStore.ts            # Job state
│   ├── uiStore.ts             # UI state (theme, layout)
│   └── ...                    # Other stores
├── types/                     # TypeScript interfaces
│   ├── api.ts                 # API response types
│   ├── domain.ts              # Domain types (Job, ValidationResult, etc.)
│   └── ...                    # Other types
└── utils/                     # Frontend utilities
    ├── formatters.ts          # Date, number formatting
    └── validators.ts          # Client-side validation
```

**Key Libraries:**
- **React Router:** Client-side navigation (v7)
- **React Query:** Server state management (caching, sync)
- **Zustand:** Lightweight client state (theme, UI state)
- **React Hook Form:** Form validation with Zod
- **Tailwind CSS:** Utility-first styling
- **shadcn/ui:** Accessible component library
- **Vitest:** Unit testing framework

**Architecture Patterns:**
- **Custom Hooks:** Encapsulate API calls and WebSocket logic
- **Service Layer:** API calls isolated in service files
- **State Management:** Zustand for simple state, React Query for server state
- **Component Composition:** Small, reusable components

### 2.7 GUI Module (`src/gui/`) — Optional/Legacy

**Purpose:** PySide6 desktop application (alternative to web UI, maintained for backward compatibility).

**Status:** Optional; primary interface is now the React web application.

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

### 4.1 Web App Validation Workflow (Interactive)

```
┌──────────────────────────────────────────┐
│  React Frontend (Accuracy Tester Page)   │
│  • Upload CSV file or paste data         │
│  • Select validation type                │
│  • Trigger validation                    │
└────────┬─────────────────────────────────┘
         │ POST /accuracy/validate-batch
         ↓
┌──────────────────────────────────────────┐
│  FastAPI Router (accuracy.py)            │
│  • Receive CSV/JSON data                 │
│  • Validate request schema               │
│  • Dispatch to Celery task               │
└────────┬─────────────────────────────────┘
         │ celery.send_task()
         ↓
┌──────────────────────────────────────────┐
│  Celery Task (validation_tasks.py)       │
│  • Async job execution                   │
│  • Store job_id in PostgreSQL            │
│  • Emit WebSocket status updates         │
└────────┬─────────────────────────────────┘
         │ async: call validation engine
         ↓
┌──────────────────────────────────────────┐
│  Python Validation Engine                │
│  (accuracy_testing/processor.py)         │
│  • Parse & load records                  │
│  • Phase 1: Inconsistent ID handling     │
│  • Phase 2: Format validation            │
│  • Phase 3: Logic validation             │
│  • Phase 4: Template matching            │
│  • Return results                        │
└────────┬─────────────────────────────────┘
         │ task.result = results
         ↓
┌──────────────────────────────────────────┐
│  WebSocket Pub/Sub (Redis)               │
│  • Broadcast job completion event        │
│  • Notify frontend of results            │
└────────┬─────────────────────────────────┘
         │ ws.send(job_complete)
         ↓
┌──────────────────────────────────────────┐
│  React Frontend                          │
│  • Receive WebSocket update              │
│  • Display validation results            │
│  • Allow download/export                 │
└──────────────────────────────────────────┘
```

### 4.2 Batch Processing Workflow (CLI/Scheduled)

```
┌──────────────────────────────────────────┐
│  Console Script or Scheduled Job         │
│  $ validate-buyer --config config.yaml   │
│  or                                      │
│  POST /scheduler/schedules               │
└────────┬─────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────────┐
│  Validation Service                      │
│  • Load configuration                    │
│  • Read input CSV from filesystem        │
│  • Initialize processor                  │
└────────┬─────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────────┐
│ Phase 1: Inconsistent ID Handling        │
│ • Aggregate by Person Code               │
│ • Check for fallback IDs                 │
│ • Replace with most recent valid ID      │
└────────┬─────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────────┐
│ Phase 2: Format Validation               │
│ • Extract country from nationality       │
│ • Validate ID format with regex          │
│ • Generate CONCAT if needed              │
└────────┬─────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────────┐
│ Phase 3: Logic Validation                │
│ • Checksums (UK NINO, IT Fiscal)         │
│ • Date logic (date of birth in ID)       │
│ • Gender validation                      │
│ • Italian tracker lookups                │
└────────┬─────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────────┐
│ Phase 4: Template Validation             │
│ • Match against Kaizen template          │
│ • Populate Error/Match columns           │
└────────┬─────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────────┐
│ Write Results                            │
│ • Output CSV to filesystem               │
│ • Log summary statistics                 │
│ • (Optional) Store in PostgreSQL         │
└──────────────────────────────────────────┘
```

### 4.2 Decision Maker Validation Workflow

```
┌──────────────────┐
│  SQL Extract     │
│  (Raw data)      │
└────────┬─────────┘
         │
         ↓
┌────────────────────────────────────────┐
│ Load Records                           │
│ • Parse CSV                            │
│ • Create DecisionMakerRecord objects   │
└────────┬───────────────────────────────┘
         │
         ↓
┌────────────────────────────────────────┐
│ Classify IDs                           │
│ • Determine party code type (LEI/etc)  │
│ • Determine DM code type               │
└────────┬───────────────────────────────┘
         │
         ↓
┌────────────────────────────────────────┐
│ Validation Rules                       │
│ IF service_level == "D":               │
│   • DM code must be populated          │
│   • DM code ≠ party code               │
│   • Correction: LEI from branch lookup │
│ ELSE: No validation required           │
└────────┬───────────────────────────────┘
         │
         ↓
┌──────────────────┐
│ Output CSV       │
│ (Validated)      │
└──────────────────┘
```

---

## 5. Deployment Architecture

### 5.1 Docker Compose (Development & Production)

```yaml
# docker-compose.yml (development)
services:
  db:               # PostgreSQL 16 (async driver: asyncpg)
  redis:            # Redis 7 (Celery broker + WebSocket pub/sub)
  api:              # FastAPI + Uvicorn (hot-reload in dev)
  web:              # React dev server (Vite) or nginx (prod)
  celery:           # Celery worker (async job processing)
  nginx:            # Reverse proxy (development)

# docker-compose.prod.yml (production)
services:
  db:               # PostgreSQL 16 (persistent volume)
  redis:            # Redis 7 (persistent volume)
  api:              # FastAPI + Uvicorn (gunicorn in prod)
  web:              # React built assets served by nginx
  celery:           # Celery worker (production scaling)
  nginx:            # nginx reverse proxy (SSL, compression)
```

**Networking:**
```
Client Browser
  ↓ (http://localhost:3000)
  ├→ nginx (port 80/443)
      ├→ /api/* → api:8000 (FastAPI)
      ├→ /ws/* → api:8000 (WebSocket)
      └→ /* → Static React assets
```

### 5.2 Service Configuration

**PostgreSQL:**
- Async connection pooling (asyncpg driver)
- SQLAlchemy 2.0 ORM
- Alembic migrations for schema management

**Redis:**
- Celery task broker
- WebSocket pub/sub for real-time updates
- Session storage (future)

**Celery:**
- Async task queue for long-running validations
- Result backend: PostgreSQL
- Worker auto-scaling (via Docker Compose replicas)

**FastAPI:**
- Uvicorn ASGI server (4+ workers)
- CORS middleware for React frontend
- OpenAPI documentation at `/docs` and `/redoc`

**React:**
- Vite bundler (dev server with HMR)
- Production build to static assets
- Served by nginx with gzip compression

### 5.3 Local Development Setup

```bash
# 1. Conda environment
conda env create -f environment.yml
conda activate txr_automation

# 2. Install packages
pip install -e .                  # Backend + console scripts
cd web && npm install             # Frontend dependencies

# 3. Start services (PostgreSQL, Redis)
docker compose up db redis -d

# 4. Run database migrations
alembic upgrade head

# 5. Start API (terminal 1)
uvicorn api.main:app --reload

# 6. Start frontend dev server (terminal 2)
cd web && npm run dev

# Access:
# Web UI:     http://localhost:5173
# API:        http://localhost:8000
# API Docs:   http://localhost:8000/docs
```

### 5.4 Console Scripts (Batch Processing)

For headless/CI environments, 22 console scripts remain available:

```bash
# Installed by: pip install -e .
# Usage: command-name --config config.yaml [--options]

Accuracy:    validate-buyer, validate-seller, validate-all, etc.
Replay:      replay-phase2, replay-phase3, etc.
FIRDS:       firds-refresh, firds-check, etc.
GLEIF:       gleif-refresh, gleif-check, etc.
```

**When to use CLI scripts:**
- CI/CD pipelines (automated batch processing)
- Scheduled cron jobs
- Headless servers
- Backward compatibility with existing workflows

**When to use web app:**
- Interactive validation with immediate feedback
- Job monitoring and history
- Configuration management
- Real-time progress tracking

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

## 9. Roadmap & Future Enhancements

### 9.1 Completed (Q1-Q2 2026) ✅

- **React Frontend:** Modern web UI with real-time updates via WebSocket
- **FastAPI Backend:** Async REST API with OpenAPI documentation
- **Docker Compose:** Multi-container orchestration for dev/prod
- **PostgreSQL:** Persistent storage for job history and configurations
- **Redis:** Celery broker and WebSocket pub/sub
- **Async Job Queue:** Celery for long-running validations
- **WebSocket Support:** Real-time job status updates to frontend

### 9.2 Short-Term (Q3 2026)

- **Job Scheduling UI:** Schedule recurring batch jobs from web interface
- **Advanced Filtering:** Filter and search job history
- **Export Functionality:** Export validation results to CSV/Excel
- **Audit Trail:** Track all validation changes and corrections
- **Performance Dashboard:** Real-time metrics and throughput monitoring

### 9.3 Medium-Term (Q4 2026)

- **Distributed Processing:** Scale to 1M+ records/day across multiple workers
- **Enhanced FIRDS/GLEIF:** Real-time regulatory data caching
- **User Roles:** Admin, validator, viewer access control
- **Notification System:** Email/Slack alerts for failed validations
- **Batch API:** Endpoint for bulk validation requests

### 9.4 Long-Term (2027+)

- **Cloud Deployment:** AWS/Azure managed services (RDS, ElastiCache, ECS)
- **Multi-tenant Support:** Isolated configurations per client
- **Advanced Analytics:** Machine learning for anomaly detection
- **Integration Hub:** Webhooks and message queue support (Kafka, RabbitMQ)
- **Custom Validation Rules:** User-defined business logic engine

---

## 10. Technology Stack Summary

### Backend Stack
| Layer | Technology | Purpose |
|-------|-----------|---------|
| **API Framework** | FastAPI 0.100+ | async REST API with OpenAPI |
| **ORM** | SQLAlchemy 2.0 | async ORM for PostgreSQL |
| **Validation** | Pydantic v2 | request/response data validation |
| **Async Broker** | Redis 7 | Celery task broker + pub/sub |
| **Job Queue** | Celery 5.3+ | async background task processing |
| **Web Server** | Uvicorn | ASGI application server |
| **Reverse Proxy** | nginx 1.25+ | production reverse proxy |

### Frontend Stack
| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Framework** | React 19 | modern UI framework |
| **Language** | TypeScript 5+ | static type checking |
| **Build Tool** | Vite 5+ | fast development + optimized builds |
| **Router** | React Router v7 | client-side navigation |
| **Data Fetching** | React Query v5 | server state management + caching |
| **State Management** | Zustand 4+ | lightweight client state |
| **Form Handling** | React Hook Form | efficient form validation |
| **Validation** | Zod | schema validation |
| **Styling** | Tailwind CSS 3 | utility-first CSS framework |
| **Components** | shadcn/ui | accessible component library |
| **Icons** | Lucide React | modern icon set |
| **Testing** | Vitest | unit test framework |

### Infrastructure
| Service | Technology | Purpose |
|---------|-----------|---------|
| **Database** | PostgreSQL 16 | primary data store (async asyncpg driver) |
| **Cache/Broker** | Redis 7 | Celery broker, WebSocket pub/sub |
| **Containerization** | Docker + Compose | multi-container orchestration |
| **Logging** | Python logging + JSON | structured JSON logging |

---

## 11. References

### 11.1 Project Documentation

- **[README.md](README.md):** Project overview, quick start, command reference
- **[Python_Migration_Plan.md](documentation/planning/Python_Migration_Plan.md):** Historical migration roadmap (now complete)
- **[API Documentation](http://localhost:8000/docs):** Interactive Swagger UI (at /docs)
- **[Frontend README](web/README.md):** React-specific development guide

### 11.2 Code Standards

**Backend (Python):**
- PEP 8 compliance (black, flake8)
- Type hints on all functions (mypy)
- Google-style docstrings
- British English in documentation

**Frontend (TypeScript/React):**
- ESLint + Prettier for formatting
- TypeScript strict mode
- Component-driven development
- Tailwind CSS conventions

**General:**
- Commit format: `type(scope): description`
- Line length: 100 characters (Python), 88 characters (frontend)
- British English throughout

---

## Appendix A: Component Dependency Diagram

```
Frontend (web/)
  ├── React Components
  │   ├── Pages (dashboard, accuracy, scheduler, settings)
  │   └── Components (reusable UI widgets)
  ├── Hooks (custom React logic)
  ├── Services (API client, WebSocket)
  └── Stores (Zustand state)
       ↓
  API Client (axios/fetch)
       ↓
Backend (api/)
  ├── Routers (FastAPI endpoints)
  ├── Services (business logic)
  ├── Schemas (Pydantic models)
  ├── Models (SQLAlchemy ORM)
  ├── Tasks (Celery async tasks)
  └── WebSocket handlers
       ↓
Core Engine (src/*)
  ├── accuracy_testing (ID validation)
  ├── replay (transaction matching)
  ├── firds (regulatory data)
  ├── gleif (LEI lookup)
  └── core (shared utilities)
       ↓
Infrastructure
  ├── PostgreSQL (persistence)
  ├── Redis (broker + pub/sub)
  ├── Celery Workers (async processing)
  └── SQLite (FIRDS/GLEIF caches)
```

---

**Document Control:**
- **Author:** AI Assistant (GitHub Copilot)  
- **Last Updated:** 9 June 2026
- **Status:** Current (Phase 6)
- **Next Review:** Q3 2026
