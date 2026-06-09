# TXR Automation

**Transaction Reporting Automation Suite**

A modern full-stack web application for validating financial transaction data to UK MiFIR/RTS 22 regulatory standards. Built with React, FastAPI, PostgreSQL, and Redis.

**Version:** 3.0.0  
**Status:** Web app in active development (Phase 6). Core migration complete.

---

## Overview

TXR Automation provides a unified platform for transaction reporting validation, SQL extract generation, and replay processing. The system handles buyer/seller identification, decision maker validation, pricing checks, and comprehensive data reconciliation across 68 country-specific ID format patterns.

### Key Features

- **Accuracy Testing Dashboard** — Validate transactions against business rules with real-time feedback
- **ID Format & Logic Validation** — 68 regex patterns + 15 country-specific embedded logic checks
- **SQL Extract Generation** — Batch and single-mode query generation with AS/400 DTF support
- **Data Reconciliation** — Transaction reference matching (Phase 2) and fuzzy client record matching (Phase 3)
- **Regulatory Data Caching** — Local SQLite caches for FCA FIRDS reportability and GLEIF LEI lookup
- **Job Scheduler** — Scheduled batch processing with run history and monitoring
- **Real-time Monitoring** — WebSocket-powered dashboard with job status and progress tracking
- **RESTful API** — Complete API for integration with external systems
- **Command-line Tools** — 22 console scripts for batch processing and automation

### Project Metrics

| Component | Details |
|-----------|---------|
| **Frontend** | React 19 + TypeScript + Tailwind CSS + shadcn/ui |
| **Backend** | FastAPI with async PostgreSQL + Celery job queue |
| **Infrastructure** | Docker Compose with Redis, PostgreSQL, nginx |
| **Test Suite** | 466+ tests across frontend and backend |
| **Validation Patterns** | 68 ID format patterns across 27 countries |
| **Business Rules** | 15 country-specific ID logic validators |

---

## Architecture

### 3-Tier Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Web Frontend (React 19)                  │
│            TypeScript + Tailwind CSS + shadcn/ui            │
│          ✓ Dashboard  ✓ Job Monitor  ✓ Settings            │
└─────────────────────────────────────────────────────────────┘
                              ↕️
┌─────────────────────────────────────────────────────────────┐
│              API Layer (FastAPI + OpenAPI)                   │
│    Accuracy  │  Scheduler  │  DRR  │  FIRDS  │  GLEIF      │
│    Replay    │  Dashboard  │  FCA  │  Utils  │  Jobs       │
└─────────────────────────────────────────────────────────────┘
                              ↕️
┌─────────────────────────────────────────────────────────────┐
│              Data & Services Layer (Python)                 │
│   PostgreSQL  │  Redis (Celery)  │  SQLite Caches         │
│   Reference Data  │  Validators  │  Business Logic        │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```text
txr_automation/
├── web/                           # React frontend (TypeScript + Vite)
│   ├── src/
│   │   ├── components/            # Reusable UI components
│   │   ├── pages/                 # Page-level components
│   │   ├── hooks/                 # Custom React hooks
│   │   ├── services/              # API client and integrations
│   │   ├── stores/                # Zustand state management
│   │   ├── types/                 # TypeScript interfaces and types
│   │   └── utils/                 # Frontend utilities
│   ├── tests/                     # Vitest unit and component tests
│   ├── vite.config.ts             # Vite bundler configuration
│   └── package.json               # npm dependencies
│
├── api/                           # FastAPI backend
│   ├── main.py                    # Application entry point
│   ├── config.py                  # Configuration management
│   ├── database.py                # PostgreSQL async setup
│   ├── models/                    # SQLAlchemy ORM models
│   ├── schemas/                   # Pydantic request/response schemas
│   ├── routers/                   # API endpoint groups
│   │   ├── accuracy.py            # Accuracy testing endpoints
│   │   ├── scheduler.py           # Job scheduling endpoints
│   │   ├── dashboard.py           # Monitoring endpoints
│   │   ├── firds.py, gleif.py     # Regulatory data endpoints
│   │   └── ...                    # Other domain routers
│   ├── services/                  # Business logic and Celery tasks
│   ├── utils/                     # API utilities and helpers
│   ├── websocket/                 # WebSocket handlers for real-time updates
│   └── requirements.txt           # Python API dependencies
│
├── src/                           # Shared Python library (txr_core)
│   ├── core/                      # Foundation library
│   │   ├── config/                # YAML + environment variable config
│   │   ├── data/                  # Country codes, ID formats, constants
│   │   ├── logging/               # Structured JSON logging
│   │   ├── utils/                 # Date parsing, CSV, file utilities
│   │   └── validation/            # Core validation functions
│   ├── accuracy_testing/          # Validation engine
│   │   ├── processor.py           # Main ID validation processor
│   │   ├── id_logic_validator.py  # 15 country-specific logic checks
│   │   ├── validators/            # Decision maker, pricing, netting logic
│   │   ├── sql_templates/         # SQL query templates (12 templates)
│   │   └── models/                # Data models (dataclasses)
│   ├── replay/                    # Replay processing (Phase 2 & 3)
│   ├── firds/                     # FCA FIRDS (API + SQLite cache)
│   ├── gleif/                     # GLEIF LEI (API + SQLite cache)
│   └── gui/                       # PySide6 desktop application (optional)
│
├── tests/                         # Test suite (466+ tests)
│   ├── test_api/                  # API endpoint tests (pytest)
│   ├── test_accuracy_testing/     # Validation engine tests
│   ├── test_core/                 # Core library tests
│   ├── integration/               # End-to-end tests
│   └── conftest.py                # Pytest fixtures and configuration
│
├── config/                        # Configuration files
│   ├── templates/                 # Sample configuration templates
│   └── local/                     # User-specific configs (gitignored)
│
├── data/                          # Runtime data
│   ├── logs/                      # Application logs
│   ├── output/                    # Generated outputs
│   └── tmp/                       # Temporary files
│
├── documentation/                 # Project documentation
│   ├── confluence/                # HTML docs for Confluence import
│   ├── guides/                    # User and developer guides
│   └── reference_data/            # CSV reference files
│
├── docker-compose.yml             # Development environment
├── docker-compose.prod.yml        # Production environment
├── Dockerfile.api                 # API container image
├── Dockerfile.web                 # Web frontend container image
├── nginx.conf                     # Reverse proxy configuration
├── setup.py                       # Python package setup
├── environment.yml                # Conda environment spec
└── requirements.txt               # Top-level dependencies
```

---

## Quick Start

### Option 1: Docker Compose (Recommended)

The fastest way to get everything running locally:

```bash
# Clone the repository
git clone https://github.com/conorcharman/txr_automation.git
cd txr_automation

# Copy environment template and customize
cp config/templates/.env.example .env

# Start all services (API, web, database, Redis, nginx)
docker compose up

# Access the application
# Web UI:     http://localhost:3000
# API Docs:   http://localhost:8000/docs
# Health:     http://localhost:8000/health
```

### Option 2: Local Development

For active development on both frontend and backend:

```bash
# 1. Set up Python environment
conda env create -f environment.yml
conda activate txr_automation

# 2. Install packages
pip install -e .                # Python package + console scripts
cd web && npm install           # Frontend dependencies
cd ..

# 3. Create .env for services
cp config/templates/.env.example .env

# 4. Start services (PostgreSQL, Redis)
docker compose up db redis -d

# 5. Run database migrations (if needed)
alembic upgrade head

# 6. Start API server (terminal 1)
uvicorn api.main:app --reload

# 7. Start frontend dev server (terminal 2)
cd web && npm run dev

# Access:
# Web UI:     http://localhost:5173 (Vite dev server)
# API:        http://localhost:8000
# API Docs:   http://localhost:8000/docs
```

### Option 3: Production Deployment

```bash
# Build containers
docker compose -f docker-compose.prod.yml build

# Start services with nginx reverse proxy
docker compose -f docker-compose.prod.yml up

# Application available at http://localhost (port 80)
```

---

## Tech Stack

### Frontend

- **React 19** with TypeScript
- **Vite** — fast build tooling
- **React Router** — client-side navigation
- **React Query** — server state management
- **React Hook Form** — form handling with Zod validation
- **Zustand** — lightweight client state management
- **Tailwind CSS** — utility-first styling
- **shadcn/ui** — accessible component library
- **Lucide Icons** — modern icon set
- **Vitest** — unit testing framework
- **dark mode support** (next-themes)

### Backend

- **FastAPI** — async Python web framework
- **SQLAlchemy 2.0** — async ORM with PostgreSQL
- **Pydantic v2** — data validation
- **Celery** — async job queue for long-running tasks
- **Redis** — Celery broker + WebSocket pub/sub
- **pytest** — comprehensive test framework
- **Alembic** — database migrations

### Infrastructure

- **PostgreSQL 16** — primary database
- **Redis 7** — cache and job queue
- **Docker & Docker Compose** — containerization
- **nginx** — reverse proxy (production)
- **Uvicorn** — ASGI server

---

## API Endpoints

The FastAPI backend provides RESTful endpoints organized by domain. Full interactive documentation available at `/docs` (Swagger UI) and `/redoc` (ReDoc).

### Core Domains

| Router | Purpose | Key Endpoints |
|--------|---------|---------------|
| **accuracy** | ID validation | `/accuracy/validate-buyer`, `/accuracy/validate-seller`, `/accuracy/validate-batch` |
| **dashboard** | Job monitoring | `/dashboard/jobs`, `/dashboard/stats`, `/dashboard/job/{id}` |
| **scheduler** | Batch scheduling | `/scheduler/schedules`, `/scheduler/run`, `/scheduler/history` |
| **firds** | Regulatory data | `/firds/check`, `/firds/refresh`, `/firds/cache-status` |
| **gleif** | LEI lookup | `/gleif/check`, `/gleif/refresh`, `/gleif/search` |
| **reconciliation** | Data matching | `/reconciliation/phase2`, `/reconciliation/phase3` |
| **pipeline** | Workflow orchestration | `/pipeline/execute`, `/pipeline/status` |
| **health** | System status | `/health`, `/health/database`, `/health/redis` |

See [API Reference](ARCHITECTURE.md) for complete endpoint documentation and request/response schemas.

---

## Command-Line Tools

In addition to the web interface, 22 console scripts are available for batch processing and automation. These are useful for CI/CD pipelines, scheduled jobs, and headless environments.

```bash
# Accuracy testing
validate-buyer --config config/local/buyer_id.yaml
validate-seller --config config/local/seller_id.yaml
validate-inconsistent-buyer --config config/local/inconsistent_buyer.yaml
validate-all --config config/local/all_validations.yaml

# SQL extraction
generate-sql-extract --config config/local/sql_extract.yaml --mode batch
generate-sql-extract --config config/local/sql_extract.yaml --mode single

# Data management
collate-csv-extracts --input data/output --output data/collated
data-push --config config/local/data_push.yaml

# Replay processing
replay-phase2 --config config/local/replay_phase2.yaml
replay-phase3 --config config/local/replay_phase3.yaml
merge-inconsistent-summaries --input data/output

# Regulatory data
firds-refresh --config config/local/firds_config.yaml
firds-check --isin GB00B0SWJX34
gleif-refresh --config config/local/gleif_config.yaml
gleif-check --lei 549300EXAMPLE000LEI00

# Configuration
generate-accuracy-template
generate-accuracy-template --output custom_config.yaml
```

All commands support `--help` for usage information and `--log-level {DEBUG,INFO,WARNING,ERROR}` for logging control.

---

## Development

### Frontend Development

```bash
cd web

# Start dev server with hot reload
npm run dev

# Run tests
npm run test
npm run test:watch          # Watch mode
npm run test:ui             # UI-based test runner

# Lint and format
npm run lint
```

### Backend Development

```bash
# Start API with auto-reload
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Run tests with coverage
pytest tests/ -v
pytest tests/ --cov=src --cov=api --cov-report=term-missing

# Type checking
mypy src/ api/

# Code formatting
black src/ tests/ api/
flake8 src/ tests/ api/
```

### Testing

The project includes 466+ tests across frontend and backend:

```bash
# Full test suite
pytest tests/                               # Backend
cd web && npm run test                      # Frontend

# Specific test files
pytest tests/test_accuracy_testing/         # Accuracy module
pytest tests/test_api/routers/test_accuracy.py  # API routes

# With coverage
pytest tests/ --cov=src --cov=api --cov-report=html
# Open htmlcov/index.html

# Integration tests
pytest tests/integration/ -v
```

### Code Quality

#### Linux/macOS

```bash
# Run all checks (bash script)
python scripts/run_tests_with_coverage.sh

# Or run individual checks
black src/ tests/ api/
isort src/ tests/ api/
flake8 src/ tests/ api/
pylint src/ api/
mypy src/ api/
cd web && npm run lint
```

#### Windows (PowerShell)

```powershell
# Recommended: run all checks with env-safe wrapper
.\scripts\run_code_quality.ps1

# Optional flags
.\scripts\run_code_quality.ps1 -SkipFrontend
.\scripts\run_code_quality.ps1 -SkipBackend
.\scripts\run_code_quality.ps1 -AutoFormat

# Format all code
python -m black src/ tests/ api/
python -m isort --profile black src/ tests/ api/

# Check formatting only (no file changes)
python -m black --check src/ tests/ api/
python -m isort --profile black --check-only src/ tests/ api/

# Lint
python -m flake8 src/ tests/ api/
python -m pylint src/ api/

# Type checking
python -m mypy api/ --ignore-missing-imports --disable-error-code import-untyped --disable-error-code attr-defined --disable-error-code arg-type

# Tests with coverage
python -m pytest tests/ --cov=src --cov-report=html --cov-report=term

# Frontend lint
cd web
npm run lint
cd ..
```

Or run all checks in one line:

```powershell
python -m black --check src/ tests/ api/; python -m isort --profile black --check-only src/ tests/ api/; python -m flake8 src/ tests/ api/; python -m pylint src/ api/; python -m mypy api/ --ignore-missing-imports --disable-error-code import-untyped --disable-error-code attr-defined --disable-error-code arg-type; python -m pytest tests/ --cov=src --cov-report=html --cov-report=term; cd web; npm run lint; cd ..
```

---

## Documentation

### Main Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — System design, module structure, API patterns, deployment architecture
- **[guides/](documentation/guides/)** — User guides, configuration guides, developer setup

### Technical Reference

- **[confluence/](documentation/confluence/)** — Detailed technical documentation (HTML files for Confluence import)
- **[reference/](documentation/reference/)** — API reference, CLI command reference, architecture reviews
- **[reference_data/](documentation/reference_data/)** — CSV reference files (ID formats, country codes, incident types)

### Planning & History

- **[planning/](documentation/planning/)** — Project roadmaps, migration plans, phase documentation

---

## Configuration

The system uses environment variables, YAML files, and defaults in priority order:

**Environment Variables** (`TXR_*`) > **YAML Config** > **Code Defaults**

### Local Development

```bash
# Copy environment template
cp config/templates/.env.example .env

# Edit with your local settings
# POSTGRES_USER, POSTGRES_PASSWORD, DATABASE_URL, etc.
nano .env
```

### Configuration File Structure

```yaml
# config/local/app_config.yaml
database:
  url: "postgresql+asyncpg://user:pass@localhost/txr_automation"
  pool_size: 20

redis:
  url: "redis://localhost:6379"

logging:
  level: INFO
  format: json

accuracy_testing:
  country_manager_path: "src/core/data/countries.csv"
  id_format_patterns_path: "identifier_formats.yaml"
```

See [Configuration Guide](documentation/guides/Accuracy_Testing_Configuration_Guide.md) for full reference.

---

## Deployment

### Docker Compose (Production)

```bash
# Build images
docker compose -f docker-compose.prod.yml build

# Start services with persistent volumes
docker compose -f docker-compose.prod.yml up -d

# View logs
docker compose logs -f api
docker compose logs -f web

# Stop services
docker compose -f docker-compose.prod.yml down
```

### Environment Setup

Production deployments require these environment variables:

```env
# Database
POSTGRES_USER=txr_prod
POSTGRES_PASSWORD=<secure-password>
POSTGRES_DB=txr_automation
DATABASE_URL=postgresql+asyncpg://txr_prod:password@postgres-service/txr_automation

# Redis
REDIS_URL=redis://redis-service:6379

# FastAPI
API_HOST=0.0.0.0
API_PORT=8000
WORKERS=4

# React
VITE_API_URL=https://api.example.com
VITE_WS_URL=wss://api.example.com

# Security
SECRET_KEY=<secure-random-key>
ALLOWED_HOSTS=api.example.com,example.com
```

### Reverse Proxy (nginx)

The included `nginx.conf` provides a reverse proxy configuration:

```bash
# With docker compose
docker compose up -d  # Includes nginx automatically
```

Production deployments should customize `nginx.conf` for domain, SSL certificates, and security headers.

---

## Git Workflow

- **`main`** — Stable, production-ready code
- **`develop`** — Integration branch for next release
- **Feature branches** — `feat/feature-name` from `develop`
- **Bug fixes** — `fix/bug-name` from `main` (hot fixes) or `develop` (planned fixes)
- **Commit format:** `type(scope): description`
  - Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`
  - Example: `feat(accuracy): add seller ID async validation`

---

## Migration History

**Note:** This project completed a full migration from VBA (12 macros) to Python in 2024–2025. The current web application represents Phase 6 (Integration & Testing) of the migration plan. All core business logic has been preserved and enhanced with modern architecture.

For historical migration details, see [Python_Migration_Plan.md](documentation/planning/Python_Migration_Plan.md).

---

## Licence

Internal use only. All rights reserved.
