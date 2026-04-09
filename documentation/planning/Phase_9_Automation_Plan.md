# Phase 9: Automation & Scheduling Plan

## Overview

Add an automation layer to the TXR Automation GUI that enables users to
schedule accuracy testing reconciliations at flexible frequencies (hourly
to monthly, or custom cron). The system comprises three main components:

1. A new **Scheduler tab** in the GUI for managing schedules
2. A **system tray service** that executes schedules when the GUI is closed
3. New **period-based SQL extraction** for in-house reconciliations without
   transaction reference lists

The architecture is designed for future **Power Automate** integration.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Validation naming | Validation logic types, not incident codes | Moving away from third-party incident numbering |
| Pipeline scope | Extract → Collate → Validate → Push | Full end-to-end automation |
| Background service | System tray app (PySide6) | No admin required, starts on login |
| Schedule storage | QSettings (Windows registry) | Consistent with existing GUI persistence |
| Execution model | Sequential queue, one pipeline at a time | Memory-constrained environment |
| Frequency options | Hourly, daily, weekly, monthly, custom cron | User chooses per schedule |
| File naming | `{type}_{fiscal_year}_{quarter}_{YYYYMMDD_HHMM}.csv` | Deterministic, sortable, unique |
| Notifications | Log + GUI dashboard + Windows toast | Complete visibility into automated runs |
| Power Automate | Design CLI/API layer now, integrate later | Clean separation of concerns |
| Pipeline presets | Both presets and custom step selection | Accessible for new users, flexible for advanced |
| Input data | Pre-staged directory + DTF output (future) | Supports both manual and automated data flow |

---

## Phase 1: Core Scheduling Infrastructure

### 1.1 Schedule Data Model

**File:** `src/gui/scheduler/models.py`

Enums:

- `ScheduleFrequency`: HOURLY, DAILY, WEEKLY, MONTHLY, CUSTOM
- `PipelineStep`: EXTRACT, COLLATE, VALIDATE, PUSH
- `ValidationType`: Maps to script modules (replaces incident codes)
  - BUYER_ID, SELLER_ID, INCONSISTENT_BUYER_ID, INCONSISTENT_SELLER_ID
  - FUND_TRADE_BUYER_DM, FUND_TRADE_SELLER_DM
  - NON_ZERO_NET_QTY, NON_ZERO_NET_AMT, INCORRECT_NET_AMOUNT
- `RunStatus`: PENDING, RUNNING, SUCCESS, FAILED, CANCELLED

Dataclasses:

- `TestingPeriod`: fiscal_year (str), quarter (str)
- `ScheduleConfig`: schedule_id (UUID), name, enabled, frequency,
  cron_expression, time_of_day, day_of_week, day_of_month,
  validation_types, pipeline_steps, testing_period, input_directory,
  output_directory, log_level, created_at, last_run, next_run
- `PipelinePreset`: name, description, validation_types, pipeline_steps
  - Pre-defined: FULL_BUYER, FULL_SELLER, ALL_VALIDATIONS,
    DECISION_MAKER_ONLY, NET_AMOUNT_QTY
- `StepResult`: step, status, started_at, completed_at, output_files,
  stdout, stderr, error_message
- `RunRecord`: run_id, schedule_id, started_at, completed_at, status,
  step_results, output_files, error_message

### 1.2 Schedule Persistence

**File:** `src/gui/scheduler/store.py`

`ScheduleStore` class wrapping QSettings:

- `save_schedule(config)` → JSON serialisation under
  `scheduler/schedules/{id}`
- `load_schedule(schedule_id) -> ScheduleConfig`
- `list_schedules() -> list[ScheduleConfig]`
- `delete_schedule(schedule_id)`
- `update_last_run(schedule_id, timestamp)`
- `save_run_record(record)` → under `scheduler/history/{id}`
- `get_run_history(schedule_id, limit) -> list[RunRecord]`
- History trimming: keep last 100 runs per schedule

### 1.3 Schedule Engine

**File:** `src/gui/scheduler/engine.py`

`ScheduleEngine` class:

- `start()` / `stop()` — lifecycle management
- `_check_due_schedules()` — called every 30s by timer
- `_calculate_next_run(config) -> datetime` — from frequency + cron
- `_execute_pipeline(config)` — runs pipeline steps sequentially
- Uses `QTimer` in GUI, `threading.Timer` in tray service
- Queue: `collections.deque`, processes one pipeline at a time
- Emits Qt signals: `pipeline_started`, `pipeline_completed`,
  `pipeline_failed`

### 1.4 Automated File Naming

**File:** `src/gui/scheduler/file_naming.py`

`AutoFileNamer` class:

- `generate_output_path(validation_type, testing_period, output_dir,
  timestamp) -> Path`
- Pattern: `{validation_type}_{fiscal_year}_{quarter}_{YYYYMMDD_HHMM}.csv`
- Example: `buyer_id_FY26_Q2_20260401_0900.csv`
- `generate_log_path(...)` — matching log file names
- `generate_extract_path(...)` — for SQL extract output
- Creates output directories if they do not exist

### 1.5 Pipeline Executor

**File:** `src/gui/scheduler/pipeline.py`

`PipelineExecutor` class:

- `execute(config: ScheduleConfig) -> RunRecord`
- Steps in order based on `config.pipeline_steps`:
  1. EXTRACT — Generate SQL + DTF, or use pre-staged input
  2. COLLATE — Run collation if multi-file extract
  3. VALIDATE — Run selected validation scripts sequentially
  4. PUSH — Push results to tracking files
- Each step produces a `StepResult` with timing and output files
- Uses subprocess execution with timeout (reuses
  `ValidationOrchestrator` pattern)
- Captures stdout/stderr per step for history

---

## Phase 2: GUI — Scheduler Tab

### 2.1 Scheduler Tab Shell

**File:** `src/gui/tabs/scheduler_tab.py`

`SchedulerTab(QWidget)` — new 6th tab in MainWindow. Uses sidebar +
QStackedWidget layout (consistent with existing tabs). Four panels:

1. Dashboard
2. Create/Edit Schedule
3. Run History
4. Pipeline Builder

### 2.2 Dashboard Panel

`SchedulerDashboardPanel(QWidget)`:

- Table of all schedules: Name, Status, Frequency, Next Run, Last Run,
  Last Status
- Colour-coded status indicators (green/red/grey)
- Quick actions: Enable/Disable toggle, Run Now, Edit, Delete
- "Next Scheduled Run" countdown at top
- Queue status indicator (idle / running / N queued)

### 2.3 Schedule Editor Panel

`ScheduleEditorPanel(QWidget)`:

- Name (text), Frequency (dropdown), Time/Day pickers (context-dependent)
- Custom cron (text, visible when Custom selected)
- Pipeline preset dropdown or custom step checkboxes
- Validation type multi-select (adapted from `IncidentSelectorWidget`)
- Testing period: Fiscal Year + Quarter dropdowns
- Input/Output directories (FilePickerWidget, directory mode)
- Log level dropdown
- Save / Save & Run Now / Cancel buttons

### 2.4 Run History Panel

`RunHistoryPanel(QWidget)`:

- Filterable table: Schedule, Start time, Duration, Status, Steps
- Expandable rows: Full log output, output file paths, error details
- Status and date range filters
- "Open output directory" button
- Export history to CSV

### 2.5 Register in MainWindow

Modify `src/gui/app.py`:

- Add `SchedulerTab` as 6th tab
- Wire `ScheduleEngine` lifecycle to MainWindow open/close
- Check for tray service; connect to its engine if running

---

## Phase 3: System Tray Service

### 3.1 Tray Application

**File:** `src/gui/tray/tray_app.py`

`TrayApplication(QApplication)`:

- System tray icon with context menu: Open GUI, Next Run, Pause/Resume,
  Recent Runs, Quit
- Runs `ScheduleEngine` on startup
- Shared QSettings store with GUI
- Icon colour changes: grey (idle), green (running), red (last failed)
- Named mutex for single-instance detection

### 3.2 Windows Toast Notifications

**File:** `src/gui/tray/notifications.py`

`NotificationManager` using `plyer`:

- `notify_success(schedule_name, duration, summary)`
- `notify_failure(schedule_name, error_message)`
- `notify_started(schedule_name)`
- Per-schedule notification preferences

### 3.3 Auto-Start on Login

**File:** `src/gui/tray/autostart.py`

`AutoStartManager`:

- `enable()` — creates shortcut in `shell:startup` (no admin required)
- `disable()` — removes shortcut
- `is_enabled() -> bool`
- Entry point: `txr-tray` console script in setup.py

### 3.4 GUI ↔ Tray Communication

- GUI detects tray via named mutex
- If tray running: reads shared engine state from QSettings
- If tray not running: GUI runs its own `ScheduleEngine`
- On GUI close with enabled schedules: prompt to start tray

---

## Phase 4: Period-Based SQL Extraction

### 4.1 New SQL Templates

**Directory:** `src/accuracy_testing/sql_templates/`

Nine new period-based templates (query by date range, no reference list):

- `BuyerID_period.sql`, `SellerID_period.sql`
- `InconsistentBuyerID_period.sql`, `InconsistentSellerID_period.sql`
- `FTBDM_period.sql`, `FTSDM_period.sql`
- `NonZeroNetQuantity_period.sql`, `NonZeroNetAmount_period.sql`
- `IncorrectNetAmount_period.sql`

Template variables: `{START_DATE}`, `{END_DATE}` (YYYY-MM-DD format)

### 4.2 Period-Based Extract Generator

**File:** `src/accuracy_testing/scripts/period_extract_generator.py`

- CLI: `--validation-type buyer_id --fiscal-year FY26 --quarter Q2`
- Calculates date range from fiscal year + quarter
- Fiscal year calendar: FY26 starts April 2025
  - Q1 = Apr–Jun, Q2 = Jul–Sep, Q3 = Oct–Dec, Q4 = Jan–Mar
- Selects correct period SQL template
- Generates DTF with `{SQL_QUERY}` and `{OUTPUT_PATH}` populated
- Output naming follows `AutoFileNamer` convention

### 4.3 DTF Execution Wrapper

**File:** `src/accuracy_testing/core/dtf_runner.py`

`DTFRunner` class:

- `generate_dtf(sql_template, output_path, parameters) -> Path`
- `execute_dtf(dtf_path) -> bool` — stub for future Power Automate
- `wait_for_output(output_path, timeout) -> bool`
- For now: generates DTF only; execution is manual or via Power Automate

---

## Phase 5: Power Automate Integration Layer

### 5.1 CLI Entry Points

**File:** `src/automation/cli.py`

- `run-pipeline`: `--validation-types`, `--fiscal-year`, `--quarter`,
  `--steps`, `--output-dir` — returns JSON status on stdout
- `list-schedules`: JSON output of all schedules
- `trigger-schedule`: `--schedule-id {uuid}` to trigger manually

### 5.2 Status/Result API

Pipeline writes `{output_dir}/_run_status.json`:

- Run metadata, step results, file paths
- Exit code, duration, record counts, error messages
- Power Automate can poll this file for completion

---

## Agent Teams

Six custom agents are defined in `.github/agents/` to build this feature:

| Agent | Scope | Key Files |
|-------|-------|-----------|
| `scheduler-engine` | Data models, persistence, engine, pipeline, file naming | `src/gui/scheduler/` |
| `gui-scheduler` | Scheduler tab UI, dashboard, editor, history panels | `src/gui/tabs/scheduler_tab.py` |
| `tray-service` | System tray app, notifications, auto-start | `src/gui/tray/` |
| `sql-period-extract` | Period SQL templates, DTF runner, automation CLI | SQL templates, `src/automation/` |
| `scheduler-tester` | Unit tests, integration tests, regression | `tests/test_scheduler/` |
| `scheduler-orchestrator` | Coordinates all agents, manages dependencies | Delegates to above agents |

### Dependency Graph

```text
Phase 1 (scheduler-engine)
    ├── Phase 2 (gui-scheduler) ─── depends on models, store, engine
    ├── Phase 3 (tray-service) ──── depends on engine, store
    └── Phase 4 (sql-period-extract) ─── parallel, used by pipeline
Phase 5 (automation CLI) ─── depends on models, pipeline
Testing (scheduler-tester) ─── incremental after each phase
```

---

## Files Summary

### Existing files to modify

- `src/gui/app.py` — Add Scheduler tab and tray lifecycle
- `src/gui/constants.py` — Add ValidationType display names
- `setup.py` — Add `txr-tray` and `run-pipeline` entry points

### New files to create

- `src/gui/scheduler/__init__.py`
- `src/gui/scheduler/models.py`
- `src/gui/scheduler/store.py`
- `src/gui/scheduler/engine.py`
- `src/gui/scheduler/pipeline.py`
- `src/gui/scheduler/file_naming.py`
- `src/gui/tabs/scheduler_tab.py`
- `src/gui/tray/__init__.py`
- `src/gui/tray/tray_app.py`
- `src/gui/tray/notifications.py`
- `src/gui/tray/autostart.py`
- `src/accuracy_testing/sql_templates/*_period.sql` (9 files)
- `src/accuracy_testing/scripts/period_extract_generator.py`
- `src/accuracy_testing/core/dtf_runner.py`
- `src/automation/__init__.py`
- `src/automation/cli.py`
- `tests/test_scheduler/conftest.py`
- `tests/test_scheduler/test_models.py`
- `tests/test_scheduler/test_store.py`
- `tests/test_scheduler/test_engine.py`
- `tests/test_scheduler/test_pipeline.py`
- `tests/test_scheduler/test_file_naming.py`
- `tests/test_tray/test_notifications.py`
- `tests/test_tray/test_autostart.py`
- `tests/test_period_extract/test_period_extract.py`
- `tests/test_automation/test_automation_cli.py`

---

## Verification

1. ScheduleConfig serialisation round-trip (save → load → compare)
2. AutoFileNamer output path generation
3. Cron expression parsing and next-run calculation
4. PipelineExecutor step sequencing (mocked)
5. Integration: create schedule → engine executes → history recorded
6. GUI: create schedule → dashboard → run now → history
7. Tray: close GUI → tray runs schedule → toast notification
8. Period SQL: generate DTF with date range → verify SQL
9. CLI: `run-pipeline --dry-run` returns JSON
10. Regression: `python -m pytest tests/` — all 466+ tests pass

---

## New Dependencies

- `croniter` — cron expression parsing and next-run calculation
- `plyer` — cross-platform notifications (targets Windows toast)

No admin-level dependencies required.

---

## Scope Boundaries

**Included:** Schedule CRUD, pipeline execution, system tray, toast
notifications, run history, period-based SQL templates, CLI for Power
Automate, automated file naming, preset and custom pipelines.

**Excluded (future):** Power Automate flow creation, actual DTF
execution via System i Data Transfer, file watcher auto-trigger, email
notifications, parallel pipeline execution, multi-user deployment.
