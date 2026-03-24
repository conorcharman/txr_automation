# TXR Automation: PySide6 Desktop GUI Plan

**Version:** 1.0
**Date:** 23 March 2026
**Status:** Planning
**Framework:** PySide6 (Qt for Python)
**Target Platform:** Windows 10/11

---

## Executive Summary

Build a PySide6 (Qt) desktop GUI that wraps the 22 existing CLI scripts
into a tabbed interface with file pickers, configuration editors, and
real-time log streaming. The GUI runs in the Conda environment during
development and packages as a standalone `.exe` via PyInstaller for
analyst distribution. GLEIF tools are deferred to a later phase.

### Key Benefits

- **No CLI Required**: Analysts configure and run scripts entirely through
  forms
- **Visual Configuration**: File pickers and dropdowns replace command-line
  flags
- **Real-Time Feedback**: Log output streams live into the GUI window
- **GDPR Compliant**: All data stays local; no external network calls from
  the GUI itself (FIRDS/GLEIF refresh scripts download public reference
  data only)
- **Distributable**: Packages as a self-contained `.exe` folder for
  machines without Python

### Relationship to Other Phases

- **Phase 8 (CLI Tool)**: The GUI is a visual companion to the unified CLI
  planned in `Phase_8_CLI_Tool_Plan.md`. Both call the same underlying
  `main()` functions; neither replaces the other.
- **Phases 0–7**: All migrated Python scripts must be complete and tested
  before wrapping them in the GUI.

---

## Architecture

### Package Structure

```text
src/gui/
├── __init__.py              # Public exports
├── __main__.py              # Entry point: python -m gui
├── app.py                   # QApplication + QMainWindow + QTabWidget
├── constants.py             # Window titles, default sizes, style tokens
├── widgets/                 # Reusable form components
│   ├── __init__.py
│   ├── file_picker.py       # FilePickerWidget
│   ├── config_loader.py     # ConfigLoaderWidget
│   ├── log_viewer.py        # LogViewerWidget
│   ├── run_controls.py      # RunControlsWidget
│   └── form_field.py        # FormFieldWidget
├── workers/                 # Background execution
│   ├── __init__.py
│   └── script_runner.py     # ScriptRunnerWorker (QThread)
└── tabs/                    # One module per top-level tab
    ├── __init__.py
    ├── accuracy_tab.py      # Accuracy Testing tab
    ├── replay_tab.py        # Replay Processing tab
    ├── firds_tab.py         # FIRDS Reference Data tab
    └── utilities_tab.py     # Utilities tab
```

### Execution Model

Each script exposes a `main()` function accepting `sys.argv`-style
arguments. The GUI constructs an argument list from form fields and
invokes `main()` inside a `QThread` worker, redirecting `stdout` and
`stderr` to Qt signals that feed the log viewer.

```text
GUI Form Fields
      │
      ▼
Build sys.argv list   (e.g. ["--config", "path.yaml", "--dry-run"])
      │
      ▼
ScriptRunnerWorker(QThread)
  ├── Redirects sys.stdout / sys.stderr to SignalStream
  ├── Calls script_module.main(argv)
  ├── Emits output_line(str) per line of output
  ├── Emits finished(exit_code) on completion
  └── Emits error(str) on unhandled exception
      │
      ▼
LogViewerWidget (QPlainTextEdit, read-only, monospace, auto-scroll)
```

### Configuration Integration

The GUI reads and writes the same YAML configuration files used by the
CLI scripts. When an analyst loads a YAML file via the GUI, all form
fields are populated from the parsed values. When they click **Save
Config**, the current form state is written back to YAML. This preserves
full interoperability between GUI and CLI workflows.

The existing configuration classes are reused:

- `src/core/config/config_manager.py` — `ConfigManager` (replay scripts)
- `src/accuracy_testing/processor.py` — `AccuracyConfigManager`,
  `AccuracyPathConfig`, `AccuracyProcessorConfig`

---

## Scope

### In Scope (Phase 1 Release) — 22 Scripts

| Group | Count | Scripts |
|-------|-------|---------|
| Accuracy Validation | 10 | buyer, seller, inconsistent-buyer, inconsistent-seller, FTBDM, FTSDM, pricing, non-zero-qty, non-zero-amt, run-all |
| Accuracy Orchestration | 4 | SQL extract generator, accuracy template generator, CSV collation, data push |
| Replay Processing | 4 | Phase 2, Phase 3, Phase 3 Final, merge inconsistent summaries |
| FIRDS Reference Data | 3 | cache refresh, reportability check, backfill |
| Utilities | 1 | XLSX-to-CSV converter |

### Excluded (Deferred to Phase 2)

| Group | Count | Scripts |
|-------|-------|---------|
| GLEIF Reference Data | 3 | cache refresh, LEI check, backfill |

The GLEIF tab follows the identical pattern as the FIRDS tab and can be
added later without architectural changes.

---

## Implementation Phases

### Phase 1: Foundation

**Goal:** Create the application shell, reusable widgets, and background
execution infrastructure. All subsequent phases depend on this.

#### 1.1 — Application Shell

**File:** `src/gui/app.py`

Create the main window with a `QTabWidget` containing four empty tabs:

```python
class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("TXR Automation")
        self.setMinimumSize(1024, 720)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Add tabs (populated in later phases)
        self.tabs.addTab(AccuracyTab(), "Accuracy Testing")
        self.tabs.addTab(ReplayTab(), "Replay Processing")
        self.tabs.addTab(FirdsTab(), "FIRDS Reference Data")
        self.tabs.addTab(UtilitiesTab(), "Utilities")

        self._create_menu_bar()
        self._create_status_bar()
```

**File:** `src/gui/__main__.py`

```python
#!/usr/bin/env python3
"""Launch the TXR Automation GUI."""
from gui.app import main

if __name__ == "__main__":
    main()
```

**File:** `src/gui/constants.py`

```python
APP_NAME = "TXR Automation"
APP_VERSION = "1.0.0"
DEFAULT_WINDOW_SIZE = (1024, 720)
LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]
```

#### 1.2 — Reusable Widgets

All widgets live in `src/gui/widgets/`.

##### FilePickerWidget (`file_picker.py`)

A horizontal layout: label + read-only `QLineEdit` + **Browse** button.

```python
class FilePickerWidget(QWidget):
    """File or directory selection widget with native dialog."""

    path_changed = Signal(str)

    def __init__(
        self,
        label: str,
        mode: str = "file",        # "file", "directory", "save"
        file_filter: str = "CSV Files (*.csv);;YAML Files (*.yaml *.yml);;All Files (*)",
        parent: Optional[QWidget] = None,
    ) -> None: ...

    def get_path(self) -> str: ...
    def set_path(self, path: str) -> None: ...
    def clear(self) -> None: ...
```

- `mode="file"` uses `QFileDialog.getOpenFileName`
- `mode="directory"` uses `QFileDialog.getExistingDirectory`
- `mode="save"` uses `QFileDialog.getSaveFileName`

##### ConfigLoaderWidget (`config_loader.py`)

A **Load Config** button that opens a YAML file dialog, parses the YAML,
and emits the parsed dictionary as a signal. A **Save Config** button
does the reverse.

```python
class ConfigLoaderWidget(QWidget):
    """Load and save YAML configuration files."""

    config_loaded = Signal(dict)   # Emitted when YAML is parsed
    config_saved = Signal(str)     # Emitted with save path

    def __init__(self, parent: Optional[QWidget] = None) -> None: ...

    def load_config(self) -> Optional[Dict[str, Any]]: ...
    def save_config(self, config: Dict[str, Any]) -> None: ...
    def get_last_path(self) -> str: ...
```

##### LogViewerWidget (`log_viewer.py`)

A read-only `QPlainTextEdit` with monospace font, auto-scrolling, and a
**Clear** button.

```python
class LogViewerWidget(QWidget):
    """Real-time log output display."""

    def __init__(self, parent: Optional[QWidget] = None) -> None: ...

    def append_line(self, text: str) -> None: ...
    def append_error(self, text: str) -> None:
        """Append text in red."""
        ...
    def clear(self) -> None: ...
    def get_text(self) -> str: ...
    def save_to_file(self, path: str) -> None: ...
```

##### RunControlsWidget (`run_controls.py`)

Run, Cancel, and Dry Run buttons with a progress indicator.

```python
class RunControlsWidget(QWidget):
    """Script execution controls."""

    run_clicked = Signal()
    dry_run_clicked = Signal()
    cancel_clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None: ...

    def set_running(self, running: bool) -> None:
        """Toggle button states for running/idle."""
        ...
    def set_progress(self, value: int, maximum: int = 0) -> None: ...
```

- When `set_running(True)`: disable Run/Dry Run, enable Cancel, show
  indeterminate progress bar
- When `set_running(False)`: enable Run/Dry Run, disable Cancel, hide
  progress bar

##### FormFieldWidget (`form_field.py`)

A single form field: label + input widget, with type determined by
constructor parameters.

```python
class FormFieldWidget(QWidget):
    """Generic labelled form field."""

    value_changed = Signal(object)

    def __init__(
        self,
        label: str,
        field_type: str = "text",    # "text", "dropdown", "checkbox", "spinbox"
        choices: Optional[List[str]] = None,
        default: Any = None,
        parent: Optional[QWidget] = None,
    ) -> None: ...

    def get_value(self) -> Any: ...
    def set_value(self, value: Any) -> None: ...
    def clear(self) -> None: ...
```

- `"text"` → `QLineEdit`
- `"dropdown"` → `QComboBox` with `choices`
- `"checkbox"` → `QCheckBox`
- `"spinbox"` → `QSpinBox`

#### 1.3 — Background Task Runner

**File:** `src/gui/workers/script_runner.py`

```python
class SignalStream(QObject):
    """Wraps a Qt signal as a file-like object for stdout/stderr."""

    text_written = Signal(str)

    def write(self, text: str) -> None:
        if text.strip():
            self.text_written.emit(text)

    def flush(self) -> None:
        pass


class ScriptRunnerWorker(QThread):
    """Runs a script main() function in a background thread."""

    output_line = Signal(str)    # Each line of stdout/stderr
    finished = Signal(int)       # Exit code (0 = success)
    error = Signal(str)          # Unhandled exception message

    def __init__(
        self,
        script_module: ModuleType,
        argv: List[str],
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._module = script_module
        self._argv = argv

    def run(self) -> None:
        """Execute script.main() with redirected stdout/stderr."""
        stream = SignalStream()
        stream.text_written.connect(self.output_line.emit)

        old_stdout, old_stderr = sys.stdout, sys.stderr
        old_argv = sys.argv
        try:
            sys.stdout = stream
            sys.stderr = stream
            sys.argv = [self._module.__name__] + self._argv
            self._module.main()
            self.finished.emit(0)
        except SystemExit as e:
            self.finished.emit(e.code if isinstance(e.code, int) else 1)
        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}")
            self.finished.emit(1)
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            sys.argv = old_argv
```

**Important:** Some scripts call `sys.exit()` on failure; the worker
catches `SystemExit` and converts it to a signal rather than terminating
the process.

#### 1.4 — Dependency and Entry Point Updates

**`environment.yml`** — add under `dependencies`:

```yaml
  - pyside6>=6.6
```

**`requirements.txt`** — add:

```text
pyside6>=6.6
```

**`setup.py`** — add to `console_scripts`:

```python
"txr-gui=gui.app:main",
```

---

### Phase 2: Accuracy Testing Tab

**Goal:** Build all accuracy testing form panels. This is the largest tab
with 14 scripts organised into two groups: validations and orchestration.

**File:** `src/gui/tabs/accuracy_tab.py`

The tab uses a `QSplitter` with a `QListWidget` sidebar on the left
(script selector) and a `QStackedWidget` on the right (form panels).
A shared `LogViewerWidget` sits at the bottom.

```text
┌──────────────────────────────────────────────────────────┐
│ Accuracy Testing                                         │
├────────────┬─────────────────────────────────────────────┤
│            │                                             │
│ Validations│  [Config File]  [Browse]  [Load] [Save]    │
│ ─────────  │                                             │
│ Buyer ID   │  [Input CSV]   [Browse]                    │
│ Seller ID  │  [Output CSV]  [Browse]                    │
│ Incon.Buy  │                                             │
│ Incon.Sell │  Log Level: [INFO ▼]                       │
│ FTBDM      │  ☐ Dry Run   ☐ Verbose   ☐ Progress       │
│ FTSDM      │                                             │
│ Pricing    │  [Run]  [Dry Run]  [Cancel]                │
│ NZ Qty     │                                             │
│ NZ Amt     ├─────────────────────────────────────────────┤
│ Run All    │                                             │
│            │  Log Output                                 │
│ Utilities  │  > Processing 50,000 records...             │
│ ─────────  │  > Batch 1/5 complete (10,000 records)     │
│ SQL Extract│  > Valid: 9,847  Invalid: 153               │
│ Templates  │  > Writing output to results.csv            │
│ Collation  │                                             │
│ Data Push  │                                             │
│            │                                             │
└────────────┴─────────────────────────────────────────────┘
```

#### 2.1 — Base Validation Panel

Create a `BaseValidationPanel` class that all validation panels inherit
from. This avoids duplicating the common form layout.

```python
class BaseValidationPanel(QWidget):
    """Base class for ID validation script panels."""

    def __init__(
        self,
        script_module: ModuleType,
        title: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._module = script_module

        # Standard fields (all validation scripts share these)
        self.config_loader = ConfigLoaderWidget()
        self.input_file = FilePickerWidget("Input CSV:", mode="file")
        self.output_file = FilePickerWidget("Output CSV:", mode="save")
        self.log_level = FormFieldWidget(
            "Log Level:", field_type="dropdown",
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            default="INFO",
        )
        self.dry_run = FormFieldWidget("Dry Run:", field_type="checkbox")
        self.verbose = FormFieldWidget("Verbose:", field_type="checkbox")
        self.progress = FormFieldWidget("Progress:", field_type="checkbox")
        self.run_controls = RunControlsWidget()
        self.log_viewer = LogViewerWidget()

    def build_argv(self) -> List[str]:
        """Build sys.argv from current form state."""
        argv = []
        config_path = self.config_loader.get_last_path()
        if config_path:
            argv.extend(["--config", config_path])
        else:
            # Use positional args
            input_path = self.input_file.get_path()
            output_path = self.output_file.get_path()
            if input_path:
                argv.append(input_path)
            if output_path:
                argv.append(output_path)

        log_level = self.log_level.get_value()
        if log_level:
            argv.extend(["--log-level", log_level])
        if self.dry_run.get_value():
            argv.append("--dry-run")
        if self.progress.get_value():
            argv.append("--progress")
        return argv

    def populate_from_config(self, config: Dict[str, Any]) -> None:
        """Fill form fields from parsed YAML config dict."""
        paths = config.get("paths", {})
        processor = config.get("processor", {})
        self.input_file.set_path(paths.get("input_file", ""))
        self.output_file.set_path(paths.get("output_file", ""))
        self.log_level.set_value(processor.get("log_level", "INFO"))
        self.verbose.set_value(processor.get("verbose", False))
```

#### 2.2 — Individual Validation Panels

Each panel inherits `BaseValidationPanel` and only adds script-specific
fields where needed.

| Panel Class | Script Module | Extra Fields |
|-------------|---------------|--------------|
| `BuyerValidationPanel` | `accuracy_testing.scripts.buyer_id_validation` | None |
| `SellerValidationPanel` | `accuracy_testing.scripts.seller_id_validation` | None |
| `InconsistentBuyerPanel` | `accuracy_testing.scripts.inconsistent_buyer_id_validation` | None |
| `InconsistentSellerPanel` | `accuracy_testing.scripts.inconsistent_seller_id_validation` | None |
| `FTBDMPanel` | `accuracy_testing.scripts.validate_ftbdm` | `lei_data_file` (FilePickerWidget), `id_formats_file` (FilePickerWidget) |
| `FTSDMPanel` | `accuracy_testing.scripts.validate_ftsdm` | `lei_data_file` (FilePickerWidget), `id_formats_file` (FilePickerWidget) |
| `PricingPanel` | `accuracy_testing.scripts.pricing_validation` | None |
| `NonZeroQtyPanel` | `accuracy_testing.scripts.non_zero_net_quantity` | None |
| `NonZeroAmtPanel` | `accuracy_testing.scripts.non_zero_net_amount` | None |

#### 2.3 — Run All Panel

| Field | Widget | Maps To |
|-------|--------|---------|
| Config file | FilePickerWidget(mode="file") | `--config` |
| Validations | Multi-select checkboxes | `--validations buyer seller ...` |
| Stop on error | FormFieldWidget(checkbox) | `--stop-on-error` |
| Log level | FormFieldWidget(dropdown) | `--log-level` |
| Verbose | FormFieldWidget(checkbox) | `--verbose` |
| List only | FormFieldWidget(checkbox) | `--list` |

#### 2.4 — SQL Extract Generator Panel

| Field | Widget | Maps To |
|-------|--------|---------|
| Config file | FilePickerWidget(mode="file") | `--config` |
| SQL template | FilePickerWidget(mode="file", filter="SQL (*.sql)") | `--template` |
| Input CSV | FilePickerWidget(mode="file") | `--input` |
| Output directory | FilePickerWidget(mode="directory") | `--output` |
| Batch size | FormFieldWidget(spinbox, default=900) | `--batch-size` |
| Placeholder | FormFieldWidget(text) | `--placeholder` |
| Column | FormFieldWidget(text) | `--column` |
| Output format | FormFieldWidget(dropdown, choices=["sql","dtf","both"]) | `--output-format` |
| Incident code | FormFieldWidget(text) | `--incident-code` |
| DTF template | FilePickerWidget(mode="file") | `--dtf-template` |
| Dry run | FormFieldWidget(checkbox) | `--dry-run` |
| Verbose | FormFieldWidget(checkbox) | `--verbose` |

#### 2.5 — Accuracy Template Generator Panel

| Field | Widget | Maps To |
|-------|--------|---------|
| Config file | FilePickerWidget(mode="file") | `--config` |
| Errors CSV | FilePickerWidget(mode="file") | `--errors` |
| Queries CSV | FilePickerWidget(mode="file") | `--queries` |
| Output directory | FilePickerWidget(mode="directory") | `--output` |
| Dry run | FormFieldWidget(checkbox) | `--dry-run` |

#### 2.6 — CSV Collation Panel

| Field | Widget | Maps To |
|-------|--------|---------|
| Config file | FilePickerWidget(mode="file") | `--config` |
| Input directory | FilePickerWidget(mode="directory") | `--input-dir` |
| Output directory | FilePickerWidget(mode="directory") | `--output-dir` |
| Output file | FilePickerWidget(mode="save") | `--output` |
| Incident code | FormFieldWidget(text) | `--incident` |
| Incidents (comma-sep) | FormFieldWidget(text) | `--incidents` |
| All incidents | FormFieldWidget(checkbox) | `--all-incidents` |
| Fiscal year | FormFieldWidget(text, e.g. "FY26") | `--fiscal-year` |
| Quarter | FormFieldWidget(text, e.g. "Q1") | `--quarter` |
| Dry run | FormFieldWidget(checkbox) | `--dry-run` |
| Force overwrite | FormFieldWidget(checkbox) | `--force` |
| Delete originals | FormFieldWidget(checkbox) | `--delete-originals` |
| Log level | FormFieldWidget(dropdown) | `--log-level` |
| Verbose | FormFieldWidget(checkbox) | `--verbose` |

#### 2.7 — Data Push Panel

| Field | Widget | Maps To |
|-------|--------|---------|
| Config file | FilePickerWidget(mode="file") | `--config` |
| Batch mode | FormFieldWidget(checkbox) | `--batch` |
| Source file | FilePickerWidget(mode="file") | `--source` |
| Target file | FilePickerWidget(mode="file") | `--target` |
| Output file | FilePickerWidget(mode="save") | `--output` |
| Incident code | FormFieldWidget(text) | `--incident` |
| Source directory | FilePickerWidget(mode="directory") | `--source-dir` |
| Target directory | FilePickerWidget(mode="directory") | `--target-dir` |
| Incidents (comma-sep) | FormFieldWidget(text) | `--incidents` |
| Fiscal year | FormFieldWidget(text) | `--fiscal-year` |
| Quarter | FormFieldWidget(text) | `--quarter` |
| Log level | FormFieldWidget(dropdown) | `--log-level` |
| Dry run | FormFieldWidget(checkbox) | `--dry-run` |
| No backup | FormFieldWidget(checkbox) | `--no-backup` |
| Verbose | FormFieldWidget(checkbox) | `--verbose` |

---

### Phase 3: Replay Tab

**Goal:** Build the four replay processing form panels.

**File:** `src/gui/tabs/replay_tab.py`

Layout: `QListWidget` sidebar (4 items) + `QStackedWidget` (4 panels)
+ shared `LogViewerWidget` at bottom.

#### 3.1 — Phase 2 Processor Panel

| Field | Widget | Maps To |
|-------|--------|---------|
| Config file | FilePickerWidget(mode="file") | `--config` |
| Use env vars | FormFieldWidget(checkbox) | `--use-env` |
| Log level | FormFieldWidget(dropdown) | `--log-level` |

Note: The Phase 2 processor reads all paths from the YAML config, so
the GUI primarily needs the config file path. Optionally, expand the
form to show and override individual YAML fields:

| Optional Override | Widget | YAML Key |
|-------------------|--------|----------|
| Replay input directory | FilePickerWidget(mode="directory") | `paths.replay_input` |
| Incident files directory | FilePickerWidget(mode="directory") | `paths.incident_files` |
| Output directory | FilePickerWidget(mode="directory") | `paths.replay_output` |
| Log output directory | FilePickerWidget(mode="directory") | `paths.log_output` |

#### 3.2 — Phase 3 Processor Panel

Identical structure to Phase 2.

| Field | Widget | Maps To |
|-------|--------|---------|
| Config file | FilePickerWidget(mode="file") | `--config` |
| Use env vars | FormFieldWidget(checkbox) | `--use-env` |
| Log level | FormFieldWidget(dropdown) | `--log-level` |

#### 3.3 — Phase 3 Final Lookup Panel

Same as Phase 3 but the YAML config includes an additional path:

| Optional Override | Widget | YAML Key |
|-------------------|--------|----------|
| UnaVista files directory | FilePickerWidget(mode="directory") | `paths.unavista_files` |

#### 3.4 — Merge Inconsistent Summaries Panel

| Field | Widget | Maps To |
|-------|--------|---------|
| Config file | FilePickerWidget(mode="file") | `--config` |
| Input directory | FilePickerWidget(mode="directory") | `--input-dir` |
| Log level | FormFieldWidget(dropdown) | `--log-level` |
| Dry run | FormFieldWidget(checkbox) | `--dry-run` |
| Verbose | FormFieldWidget(checkbox) | `--verbose` |

---

### Phase 4: FIRDS Tab

**Goal:** Build the three FIRDS reference data form panels.

**File:** `src/gui/tabs/firds_tab.py`

Layout: `QListWidget` sidebar (3 items) + `QStackedWidget` (3 panels)
+ shared `LogViewerWidget` at bottom.

#### 4.1 — FIRDS Cache Refresh Panel

| Field | Widget | Maps To |
|-------|--------|---------|
| Refresh type | FormFieldWidget(dropdown, choices=["full"]) | `--type` |
| Publication date | `QDateEdit` (Saturdays only) | `--date` |
| Database path | FilePickerWidget(mode="file", filter="SQLite (*.db)") | `--db` |
| Staging directory | FilePickerWidget(mode="directory") | `--staging-dir` |
| Config file | FilePickerWidget(mode="file") | `--config` |
| Log level | FormFieldWidget(dropdown) | `--log-level` |

**Business rule:** The `--date` field must be a Saturday. Validate in the
GUI with a visual warning if a non-Saturday is selected.

#### 4.2 — FIRDS Reportability Check Panel

This panel has two modes toggled by a radio button group.

**Single Instrument Mode:**

| Field | Widget | Maps To |
|-------|--------|---------|
| ISIN | FormFieldWidget(text) | `--isin` |
| MIC | FormFieldWidget(text, optional) | `--mic` |
| Trade date | `QDateEdit` | `--date` |

**Batch Mode:**

| Field | Widget | Maps To |
|-------|--------|---------|
| Input files | FilePickerWidget(mode="file", multi=True) | `--input` |
| Input directory | FilePickerWidget(mode="directory") | `--input-dir` |
| Glob pattern | FormFieldWidget(text, default="*.csv") | `--pattern` |
| Output file | FilePickerWidget(mode="save") | `--output` |

**Common:**

| Field | Widget | Maps To |
|-------|--------|---------|
| Database path | FilePickerWidget(mode="file") | `--db` |
| Config file | FilePickerWidget(mode="file") | `--config` |
| Log level | FormFieldWidget(dropdown) | `--log-level` |

#### 4.3 — FIRDS Backfill Panel

| Field | Widget | Maps To |
|-------|--------|---------|
| Input CSV | FilePickerWidget(mode="file") | `--input` (required) |
| Output CSV | FilePickerWidget(mode="save") | `--output` (required) |
| Format | FormFieldWidget(dropdown, choices=["auto","incident","generic"]) | `--format` |
| Database path | FilePickerWidget(mode="file") | `--db` |
| Skip refresh | FormFieldWidget(checkbox) | `--skip-refresh` |
| Log level | FormFieldWidget(dropdown) | `--log-level` |

---

### Phase 5: Utilities Tab

**Goal:** Build the XLSX-to-CSV converter form panel.

**File:** `src/gui/tabs/utilities_tab.py`

#### 5.1 — XLSX-to-CSV Converter Panel

| Field | Widget | Maps To |
|-------|--------|---------|
| Config file | FilePickerWidget(mode="file") | `--config` |
| Mode | FormFieldWidget(dropdown, choices=["1 — Recursive","2 — Single directory"]) | `--mode` |
| Parent directory | FilePickerWidget(mode="directory") | `--parent-dir` |
| Input directory | FilePickerWidget(mode="directory") | `--input-dir` |
| Output directory | FilePickerWidget(mode="directory") | `--output-dir` |
| Recursive | FormFieldWidget(checkbox) | `--recursive` |
| Filter year | FormFieldWidget(text, e.g. "FY25") | `--filter-year` |
| Filter quarter | FormFieldWidget(text, e.g. "Q3") | `--filter-quarter` |
| Filter phases | FormFieldWidget(text, e.g. "phase_ii phase_iii") | `--filter-phase` (split on spaces) |
| Dry run | FormFieldWidget(checkbox) | `--dry-run` |
| Force overwrite | FormFieldWidget(checkbox) | `--force` |
| Log level | FormFieldWidget(dropdown) | `--log-level` |

**Conditional visibility:** When mode is "1 — Recursive", show
`parent-dir`; when mode is "2 — Single directory", show `input-dir` and
`output-dir`.

---

### Phase 6: Polish and Integration

**Goal:** Add menu bar, status bar, and quality-of-life features.

#### 6.1 — Menu Bar

| Menu | Action | Behaviour |
|------|--------|-----------|
| File → Load Config | `Ctrl+O` | Opens YAML file dialog, populates active tab's form |
| File → Save Config | `Ctrl+S` | Saves active tab's form state to YAML |
| File → Save Config As | `Ctrl+Shift+S` | Save As dialog |
| File → Exit | `Ctrl+Q` | Close application (confirm if script running) |
| Help → About | — | Dialog showing app version, Python version, Qt version |
| Help → Documentation | — | Opens `documentation/guides/` in file explorer |

#### 6.2 — Status Bar

Bottom bar showing:

- **Left:** Current operation name (e.g. "Running: validate-buyer") or
  "Ready"
- **Centre:** Elapsed time during execution (HH:MM:SS)
- **Right:** Last run result ("Success" / "Failed — exit code 1")

#### 6.3 — Config Pre-Population

When a user selects a YAML config file via `ConfigLoaderWidget`:

1. Parse the YAML using `yaml.safe_load()`
2. Call the active panel's `populate_from_config(config_dict)` method
3. All file picker paths, dropdowns, and checkboxes update to match the
   config values
4. The user can then override individual fields before running

---

### Phase 7: PyInstaller Packaging

**Goal:** Package the GUI as a distributable `.exe` folder that runs on
Windows machines without Python or Conda.

#### 7.1 — PyInstaller Spec File

**File:** `packaging/txr_gui.spec`

Key configuration:

```python
# One-directory mode (faster startup than one-file)
a = Analysis(
    ['../src/gui/__main__.py'],
    pathex=['../src'],
    datas=[
        ('../config/templates', 'config/templates'),
        ('../documentation/reference_data', 'documentation/reference_data'),
    ],
    hiddenimports=[
        'accuracy_testing.scripts.buyer_id_validation',
        'accuracy_testing.scripts.seller_id_validation',
        # ... all 22 script modules
        'PySide6.QtWidgets',
        'PySide6.QtCore',
        'PySide6.QtGui',
    ],
)
```

#### 7.2 — Build Script

**File:** `scripts/build_exe.py`

```bash
conda activate txr_automation
pip install pyinstaller
pyinstaller packaging/txr_gui.spec --noconfirm
```

Output: `dist/txr_gui/txr_gui.exe`

#### 7.3 — Distribution

Distribute the `dist/txr_gui/` folder as a ZIP archive. Analysts unzip
to a local directory and run `txr_gui.exe` directly — no installation
required.

**Important:** The packaged app includes `config/templates/` so analysts
can copy templates to a local `config/local/` directory and customise
them.

---

## Complete CLI Argument Reference

This section documents the exact `argparse` arguments for every script.
The GUI must construct `sys.argv` lists that match these definitions
precisely.

### Accuracy Testing — ID Validation Scripts

**Scripts:** `buyer_id_validation`, `seller_id_validation`,
`pricing_validation`

```text
Positional:
  input_file        nargs='?', type=str          Input CSV (backward compat)
  output_file       nargs='?', type=str          Output CSV (backward compat)

Optional:
  --config          type=str                     YAML config file
  --use-env         action='store_true'          Load from TXR_* env vars
  --log-level       choices=[DEBUG,INFO,WARNING,ERROR]
  --dry-run         action='store_true'
  --progress        action='store_true'
```

**Scripts:** `inconsistent_buyer_id_validation`,
`inconsistent_seller_id_validation`

```text
Mutually Exclusive:
  --config, -c      type=str                     YAML config file
  --use-env         action='store_true'          Load from TXR_ACCURACY_* env vars

Positional:
  input_file        nargs='?'                    Input CSV (backward compat)
  output_file       nargs='?'                    Output CSV (backward compat)

Optional:
  --log-level, -l   choices=[DEBUG,INFO,WARNING,ERROR], default='INFO'
  --dry-run         action='store_true'
  --progress        action='store_true'
```

### Accuracy Testing — Decision Maker Scripts

**Scripts:** `validate_ftbdm`, `validate_ftsdm`

```text
Optional:
  --config          type=str                     YAML config file
  --input           type=str                     Input CSV
  --output          type=str                     Output CSV
  --lei-data        type=str                     LEI lookup CSV
  --id-formats      type=str                     ID formats CSV (optional)
  --log-dir         type=str                     Log directory
  --log-level       choices=[DEBUG,INFO,WARNING,ERROR], default='INFO'
  --dry-run         action='store_true'
  --verbose         action='store_true'
```

### Accuracy Testing — Net Validation Scripts

**Scripts:** `non_zero_net_quantity`, `non_zero_net_amount`

```text
Positional:
  input_file        nargs='?', type=str          Input CSV (backward compat)
  output_file       nargs='?', type=str          Output CSV (backward compat)

Optional:
  --config          type=str                     YAML config file
  --log-level       choices=[DEBUG,INFO,WARNING,ERROR], default=None
  --verbose         action='store_true'
  --dry-run         action='store_true'
```

### Accuracy Testing — Run All Validations

**Script:** `run_all_validations`

```text
Optional:
  --config          type=str                     YAML config file
  --validations     nargs="+"                    Whitelist (e.g., buyer seller)
  --stop-on-error   action='store_true'
  --log-level       choices=[DEBUG,INFO,WARNING,ERROR], default='INFO'
  --verbose         action='store_true'
  --list            action='store_true'          List validations and exit
```

### Accuracy Testing — SQL Extract Generator

**Script:** `sql_extract_generator`

```text
Optional:
  --config          type=str                     YAML config file
  --template        type=str                     SQL template file
  --input           type=str                     Input CSV
  --output          type=str                     Output directory
  --batch-size      type=int, default=900
  --placeholder     type=str, default=None
  --column          type=str, default=None       CSV column name/index
  --output-format   choices=[sql,dtf,both], default='both'
  --incident-code   type=str, default=None
  --dtf-template    type=str, default=None
  --dry-run         action='store_true'
  --verbose         action='store_true'
```

### Accuracy Testing — Template Generator

**Script:** `accuracy_template_generator`

```text
Optional:
  --config          type=str                     YAML config file
  --errors          type=str                     Errors CSV
  --queries         type=str                     Queries CSV
  --output          type=str                     Output directory
  --dry-run         action='store_true'
```

### Accuracy Testing — CSV Collation

**Script:** `collate_csv_extracts`

```text
Optional:
  --config          type=str                     YAML config file
  --input-dir       type=str                     Input directory
  --output-dir      type=str                     Output directory
  --output          type=str                     Single output file
  --incident        type=str                     Single incident code
  --incidents       type=str                     Comma-separated codes
  --all-incidents   action='store_true'
  --fiscal-year     type=str                     e.g., FY26
  --quarter         type=str                     e.g., Q1
  --dry-run         action='store_true'
  --force           action='store_true'
  --delete-originals action='store_true'
  --log-level       choices=[DEBUG,INFO,WARNING,ERROR], default='INFO'
  --verbose         action='store_true'
```

### Accuracy Testing — Data Push

**Script:** `data_push`

```text
Optional:
  --batch           action='store_true'
  --config          type=str, default='config/local/accuracy_testing/data_push.yaml'
  --source          type=str                     Source CSV (validation output)
  --target          type=str                     Target CSV (master tracker)
  --output          type=str                     Output file
  --incident        type=str                     Incident code
  --source-dir      type=str                     Source directory (batch)
  --target-dir      type=str                     Target directory (batch)
  --incidents       type=str                     Comma-separated codes (batch)
  --fiscal-year     type=str
  --quarter         type=str
  --log-level       choices=[DEBUG,INFO,WARNING,ERROR], default='INFO'
  --dry-run         action='store_true'
  --no-backup       action='store_true'
  --verbose         action='store_true'
```

### Replay Processing

**Scripts:** `phase_2_processor`, `phase_3_processor`,
`phase_3_final_lookup`

```text
Optional:
  --config          type=str                     YAML config file
  --use-env         action='store_true'          Load from TXR_* env vars
  --log-level       choices=[DEBUG,INFO,WARNING,ERROR]
```

**Script:** `merge_inconsistent_ids`

```text
Optional:
  --config          type=str                     YAML config file
  --input-dir       type=str                     Input directory
  --log-level       choices=[DEBUG,INFO,WARNING,ERROR], default=None
  --dry-run         action='store_true'
  --verbose         action='store_true'
```

### FIRDS Reference Data

**Script:** `firds refresh_cache`

```text
Required:
  --type            choices=['full']             Refresh type

Optional:
  --date            type=date (YYYY-MM-DD)       Publication date (Saturday)
  --db              type=Path, default=data/firds_cache.db
  --staging-dir     type=Path
  --config          type=Path                    YAML config file
  --log-level       choices=[DEBUG,INFO,WARNING,ERROR], default='INFO'
```

**Script:** `firds check_reportability`

```text
Single Mode:
  --isin            type=str
  --mic             type=str, optional
  --date            type=date (YYYY-MM-DD)

Batch Mode:
  --input           type=Path, nargs="+"         One or more CSVs
  --input-dir       type=Path                    Directory to scan
  --pattern         type=str, default="*.csv"
  --output          type=Path                    Merged output CSV

Common:
  --db              type=Path
  --config          type=Path
  --log-level       choices=[DEBUG,INFO,WARNING,ERROR], default='WARNING'
```

**Script:** `firds backfill`

```text
Required:
  --input           type=Path                    Input CSV
  --output          type=Path                    Output CSV

Optional:
  --format          choices=[auto,incident,generic], default='auto'
  --db              type=Path, default=data/firds_cache.db
  --skip-refresh    action='store_true'
  --log-level       choices=[DEBUG,INFO,WARNING,ERROR], default='INFO'
```

### Utilities

**Script:** `xlsx_csv_converter`

```text
Optional:
  --config          type=str                     YAML config file
  --mode            choices=[1,2]                1=Recursive, 2=Single dir
  --parent-dir      type=str                     Parent dir (mode 1)
  --input-dir       type=str                     Input dir (mode 2)
  --output-dir      type=str                     Output dir (mode 2)
  --recursive       action='store_true'
  --filter-year     type=str                     e.g., FY25
  --filter-quarter  type=str                     e.g., Q3
  --filter-phase    nargs="+"                    e.g., phase_ii phase_iii
  --dry-run         action='store_true'
  --force           action='store_true'
  --log-level       choices=[DEBUG,INFO,WARNING,ERROR], default='INFO'
```

---

## Existing Files to Integrate With

These files contain the `main()` functions the GUI will call. They must
not be modified by the GUI implementation.

| Console Command | Module | `main()` Location |
|----------------|--------|-------------------|
| `validate-buyer` | `accuracy_testing.scripts.buyer_id_validation` | `parse_args()` + `main()` |
| `validate-seller` | `accuracy_testing.scripts.seller_id_validation` | `parse_args()` + `main()` |
| `validate-inconsistent-buyer` | `accuracy_testing.scripts.inconsistent_buyer_id_validation` | `parse_args()` + `main()` |
| `validate-inconsistent-seller` | `accuracy_testing.scripts.inconsistent_seller_id_validation` | `parse_args()` + `main()` |
| `validate-ftbdm` | `accuracy_testing.scripts.validate_ftbdm` | `create_parser()` + `main()` |
| `validate-ftsdm` | `accuracy_testing.scripts.validate_ftsdm` | `create_parser()` + `main()` |
| `validate-pricing` | `accuracy_testing.scripts.pricing_validation` | `parse_args()` + `main()` |
| `validate-non-zero-net-qty` | `accuracy_testing.scripts.non_zero_net_quantity` | `parse_args()` + `main()` |
| `validate-non-zero-net-amt` | `accuracy_testing.scripts.non_zero_net_amount` | `parse_args()` + `main()` |
| `validate-all` | `accuracy_testing.scripts.run_all_validations` | `create_parser()` + `main()` |
| `generate-sql-extract` | `accuracy_testing.scripts.sql_extract_generator` | `parse_arguments()` + `main()` |
| `generate-accuracy-template` | `accuracy_testing.scripts.accuracy_template_generator` | `parse_args()` + `main()` |
| `collate-csv-extracts` | `accuracy_testing.scripts.collate_csv_extracts` | `create_argument_parser()` + `main()` |
| `data-push` | `accuracy_testing.scripts.data_push` | `create_parser()` + `main()` |
| `replay-phase2` | `replay.phase_2_processor` | `parse_args()` + `main()` |
| `replay-phase3` | `replay.phase_3_processor` | `parse_args()` + `main()` |
| `replay-phase3-final` | `replay.phase_3_final_lookup` | `parse_args()` + `main()` |
| `merge-inconsistent-summaries` | `replay.merge_inconsistent_ids` | `create_argument_parser()` + `main()` |
| `firds-refresh` | `firds.scripts.refresh_cache` | `_parse_args()` + `main()` |
| `firds-check` | `firds.scripts.check_reportability` | `_parse_args()` + `main()` |
| `firds-backfill` | `firds.scripts.backfill` | `_parse_args()` + `main()` |
| `replay-xlsx-converter` | `utils.xlsx_csv_converter` | `parse_arguments()` + `main()` |

---

## New Files to Create

```text
src/gui/
├── __init__.py
├── __main__.py
├── app.py
├── constants.py
├── widgets/
│   ├── __init__.py
│   ├── file_picker.py
│   ├── config_loader.py
│   ├── log_viewer.py
│   ├── run_controls.py
│   └── form_field.py
├── workers/
│   ├── __init__.py
│   └── script_runner.py
└── tabs/
    ├── __init__.py
    ├── accuracy_tab.py
    ├── replay_tab.py
    ├── firds_tab.py
    └── utilities_tab.py

packaging/
└── txr_gui.spec

tests/test_gui/
├── __init__.py
├── test_script_runner.py
├── test_file_picker.py
└── test_config_loader.py
```

---

## GDPR and Security Considerations

1. **No external data transmission from GUI** — The GUI only calls local
   Python functions. No telemetry, analytics, or crash reporting.
2. **FIRDS/GLEIF refresh scripts download public reference data** —
   Instrument and entity reference data from FCA and GLEIF APIs is
   publicly available. No client data is transmitted.
3. **All client data stays on local filesystem** — CSV files are read
   from and written to local paths only.
4. **No credentials stored** — The GUI does not manage or store
   credentials. API endpoints used are unauthenticated public APIs.
5. **PyInstaller bundle is self-contained** — No network calls during
   installation or startup.

---

## Verification Checklist

- [ ] All 22 scripts launch successfully from the GUI with correct
  arguments
- [ ] YAML config loading populates all form fields correctly
- [ ] YAML config saving produces valid files that work with CLI
- [ ] Log output streams in real time during script execution
- [ ] Dry Run mode works for all scripts that support it
- [ ] Error states (missing files, invalid input) display clearly in
  the log viewer
- [ ] GUI remains responsive during long-running scripts (QThread)
- [ ] Cancel button stops running scripts
- [ ] PyInstaller `.exe` launches on a clean Windows machine
- [ ] No client data leaves the local machine

---

## Technical Decisions Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| GUI framework | PySide6 (Qt) | Professional tabbed layout, native file dialogs, strong Windows support |
| Script invocation | Direct `main()` call in QThread | Avoids subprocess shell encoding issues; enables Python exception handling and log signal redirection |
| Configuration | YAML round-tripping via existing managers | Preserves analyst workflow of sharing configs between CLI and GUI |
| PyInstaller mode | One-directory | Faster startup, easier debugging than single-file mode |
| Script cancellation | Thread termination with user warning | Scripts lack cooperative cancellation; refine in later phase |
| GLEIF tools | Deferred to Phase 2 | Not selected for initial release; follows FIRDS tab pattern when ready |
| Theme/styling | System defaults (Qt Fusion) | Clean appearance on Windows without custom stylesheet overhead |
| Multi-script queuing | Deferred | `validate-all` orchestrator covers the main batch case |
