#!/usr/bin/env python3
"""
Utilities Tab
=============

Utility script panels:
- XLSX-to-CSV Converter (with conditional mode visibility)
"""

import importlib
from types import ModuleType
from typing import Any, Dict, List, Optional

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.constants import CSV_FILTER, LOG_LEVELS, XML_FILTER
from gui.widgets import (
    ConfigLoaderWidget,
    FilePickerWidget,
    FormFieldWidget,
    LogViewerWidget,
    RunControlsWidget,
)
from gui.utils.settings import settings
from gui.workers import ScriptRunnerWorker


def _import_script(module_path: str) -> Optional[ModuleType]:
    """Safely import a script module."""
    try:
        return importlib.import_module(module_path)
    except ImportError:
        return None


class XlsxConverterPanel(QWidget):
    """Panel for the XLSX-to-CSV converter script.

    Mode 1 (Recursive) shows parent-dir.
    Mode 2 (Single directory) shows input-dir and output-dir.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._worker: Optional[ScriptRunnerWorker] = None
        pfx = "utils.xlsx_converter"

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>XLSX to CSV Converter</b>"))

        self.config_loader = ConfigLoaderWidget()
        layout.addWidget(self.config_loader)

        self.mode = FormFieldWidget(
            "Mode:", field_type="dropdown",
            choices=["1 \u2014 Recursive", "2 \u2014 Single directory"],
            default="1 \u2014 Recursive",
            tooltip="Mode 1 recursively converts an entire directory tree.\nMode 2 converts a single directory.",
            settings_key=f"{pfx}.mode",
        )
        self.mode.value_changed.connect(self._on_mode_changed)
        layout.addWidget(self.mode)

        # Mode 1 fields
        self._mode1_widget = QWidget()
        m1_layout = QVBoxLayout(self._mode1_widget)
        m1_layout.setContentsMargins(0, 0, 0, 0)
        self.parent_dir = FilePickerWidget(
            "Parent Directory:", mode="directory",
            tooltip="Top-level directory to recursively search for .xlsx files.",
            settings_key=f"{pfx}.parent_dir",
        )
        m1_layout.addWidget(self.parent_dir)
        layout.addWidget(self._mode1_widget)

        # Mode 2 fields
        self._mode2_widget = QWidget()
        m2_layout = QVBoxLayout(self._mode2_widget)
        m2_layout.setContentsMargins(0, 0, 0, 0)
        self.input_dir = FilePickerWidget(
            "Input Directory:", mode="directory",
            tooltip="Directory containing .xlsx files to convert.",
            settings_key=f"{pfx}.input_dir",
        )
        m2_layout.addWidget(self.input_dir)
        self.output_dir = FilePickerWidget(
            "Output Directory:", mode="directory",
            tooltip="Directory where converted .csv files will be written.",
            settings_key=f"{pfx}.output_dir",
        )
        m2_layout.addWidget(self.output_dir)
        layout.addWidget(self._mode2_widget)
        self._mode2_widget.setVisible(False)

        # Common fields
        self.recursive = FormFieldWidget(
            "Recursive", field_type="checkbox",
            tooltip="Search subdirectories for .xlsx files.",
            settings_key=f"{pfx}.recursive",
        )
        layout.addWidget(self.recursive)

        self.filter_year = FormFieldWidget(
            "Filter Year:", field_type="text",
            tooltip="Only convert files matching this fiscal year.\nExample: 2025",
            placeholder="2025",
            settings_key=f"{pfx}.filter_year",
        )
        layout.addWidget(self.filter_year)

        self.filter_quarter = FormFieldWidget(
            "Filter Quarter:", field_type="text",
            tooltip="Only convert files matching this quarter.\nExample: Q4",
            placeholder="Q4",
            settings_key=f"{pfx}.filter_quarter",
        )
        layout.addWidget(self.filter_quarter)

        self.filter_phases = FormFieldWidget(
            "Filter Phases:", field_type="text",
            tooltip="Space-separated phase numbers to filter.\nExample: 2 3",
            placeholder="2 3",
            settings_key=f"{pfx}.filter_phases",
        )
        layout.addWidget(self.filter_phases)

        self.log_level = FormFieldWidget(
            "Log Level:", field_type="dropdown",
            choices=LOG_LEVELS, default="INFO",
            tooltip="Logging verbosity level.",
            settings_key=f"{pfx}.log_level",
        )
        layout.addWidget(self.log_level)

        self.dry_run = FormFieldWidget(
            "Dry Run", field_type="checkbox",
            tooltip="Preview which files would be converted without writing.",
            settings_key=f"{pfx}.dry_run",
        )
        layout.addWidget(self.dry_run)

        self.force = FormFieldWidget(
            "Force Overwrite", field_type="checkbox",
            tooltip="Overwrite existing CSV files without prompting.",
            settings_key=f"{pfx}.force",
        )
        layout.addWidget(self.force)

        self.run_controls = RunControlsWidget()
        self.run_controls.run_clicked.connect(self._on_run)
        self.run_controls.dry_run_clicked.connect(self._on_dry_run)
        self.run_controls.cancel_clicked.connect(self._on_cancel)
        layout.addWidget(self.run_controls)

        self.log_viewer = LogViewerWidget()
        layout.addWidget(self.log_viewer, stretch=1)

    def _on_mode_changed(self, value: object) -> None:
        """Toggle mode-specific fields."""
        mode_str = str(value)
        is_recursive = mode_str.startswith("1")
        self._mode1_widget.setVisible(is_recursive)
        self._mode2_widget.setVisible(not is_recursive)

    def build_argv(self) -> List[str]:
        argv: List[str] = []
        config_path = self.config_loader.get_last_path()
        if config_path:
            argv.extend(["--config", config_path])

        mode_str = self.mode.get_value()
        mode_num = "1" if mode_str.startswith("1") else "2"
        argv.extend(["--mode", mode_num])

        if mode_num == "1":
            parent = self.parent_dir.get_path()
            if parent:
                argv.extend(["--parent-dir", parent])
        else:
            inp = self.input_dir.get_path()
            if inp:
                argv.extend(["--input-dir", inp])
            out = self.output_dir.get_path()
            if out:
                argv.extend(["--output-dir", out])

        if self.recursive.get_value():
            argv.append("--recursive")

        year = self.filter_year.get_value()
        if year:
            argv.extend(["--filter-year", year])

        quarter = self.filter_quarter.get_value()
        if quarter:
            argv.extend(["--filter-quarter", quarter])

        phases = self.filter_phases.get_value()
        if phases:
            for phase in phases.split():
                argv.extend(["--filter-phase", phase])

        log_level = self.log_level.get_value()
        if log_level:
            argv.extend(["--log-level", log_level])

        if self.dry_run.get_value():
            argv.append("--dry-run")
        if self.force.get_value():
            argv.append("--force")
        return argv

    def _on_run(self) -> None:
        self._execute(dry_run=False)

    def _on_dry_run(self) -> None:
        self._execute(dry_run=True)

    def _execute(self, dry_run: bool = False) -> None:
        module = _import_script("utils.xlsx_csv_converter")
        if module is None:
            self.log_viewer.append_error(
                "Failed to import utils.xlsx_csv_converter"
            )
            return
        argv = self.build_argv()
        if dry_run and "--dry-run" not in argv:
            argv.append("--dry-run")
        self.log_viewer.clear()
        self.log_viewer.append_line(
            f"[GUI] Running: xlsx_csv_converter {' '.join(argv)}"
        )
        self.run_controls.set_running(True)
        self._worker = ScriptRunnerWorker(module, argv)
        self._worker.output_line.connect(self.log_viewer.append_line)
        self._worker.error.connect(self.log_viewer.append_error)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.start()

    def _on_cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.log_viewer.append_error("[GUI] Cancelled by user")

    def _on_finished(self, exit_code: int) -> None:
        self.run_controls.set_running(False)
        if exit_code == 0:
            self.log_viewer.append_line("[GUI] Completed successfully")
        else:
            self.log_viewer.append_error(
                f"[GUI] Finished with exit code {exit_code}"
            )
        self._worker = None


class XmlConverterPanel(QWidget):
    """Panel for the XML-to-CSV converter.

    Supports single-file and directory modes.  In directory mode the
    recursive checkbox is exposed.  The optional Output Directory field
    defaults to writing the CSV alongside each source XML file.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._worker: Optional[ScriptRunnerWorker] = None
        pfx = "utils.xml_converter"

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>XML to CSV Converter</b>"))

        self.mode = FormFieldWidget(
            "Mode:", field_type="dropdown",
            choices=["Single file", "Directory"],
            default="Single file",
            tooltip="Single file: convert one XML file.\nDirectory: convert all XML files in a folder.",
            settings_key=f"{pfx}.mode",
        )
        self.mode.value_changed.connect(self._on_mode_changed)
        layout.addWidget(self.mode)

        # Single-file mode widgets
        self._file_widget = QWidget()
        file_layout = QVBoxLayout(self._file_widget)
        file_layout.setContentsMargins(0, 0, 0, 0)
        self.input_file = FilePickerWidget(
            "Input XML File:", mode="file",
            file_filter=XML_FILTER,
            tooltip="Select the XML file to convert.",
            settings_key=f"{pfx}.input_file",
        )
        file_layout.addWidget(self.input_file)
        layout.addWidget(self._file_widget)

        # Directory mode widgets
        self._dir_widget = QWidget()
        dir_layout = QVBoxLayout(self._dir_widget)
        dir_layout.setContentsMargins(0, 0, 0, 0)
        self.input_dir = FilePickerWidget(
            "Input Directory:", mode="directory",
            tooltip="Directory containing XML files to convert.",
            settings_key=f"{pfx}.input_dir",
        )
        dir_layout.addWidget(self.input_dir)
        self.recursive = FormFieldWidget(
            "Recursive", field_type="checkbox",
            tooltip="Search subdirectories for XML files.",
            settings_key=f"{pfx}.recursive",
        )
        dir_layout.addWidget(self.recursive)
        layout.addWidget(self._dir_widget)
        self._dir_widget.setVisible(False)

        # Common widgets
        self.output_dir = FilePickerWidget(
            "Output Directory (optional):", mode="directory",
            tooltip="Leave empty to save each CSV alongside its XML file.",
            settings_key=f"{pfx}.output_dir",
        )
        layout.addWidget(self.output_dir)

        self.dry_run = FormFieldWidget(
            "Dry Run", field_type="checkbox",
            tooltip="Preview conversion without writing any CSV files.",
            settings_key=f"{pfx}.dry_run",
        )
        layout.addWidget(self.dry_run)

        self.log_level = FormFieldWidget(
            "Log Level:", field_type="dropdown",
            choices=LOG_LEVELS, default="INFO",
            tooltip="Logging verbosity level.",
            settings_key=f"{pfx}.log_level",
        )
        layout.addWidget(self.log_level)

        self.run_controls = RunControlsWidget()
        self.run_controls.run_clicked.connect(self._on_run)
        self.run_controls.dry_run_clicked.connect(self._on_dry_run)
        self.run_controls.cancel_clicked.connect(self._on_cancel)
        layout.addWidget(self.run_controls)

        self.log_viewer = LogViewerWidget()
        layout.addWidget(self.log_viewer, stretch=1)

    def _on_mode_changed(self, value: object) -> None:
        """Toggle between single-file and directory widgets."""
        is_file = str(value) == "Single file"
        self._file_widget.setVisible(is_file)
        self._dir_widget.setVisible(not is_file)

    def build_argv(self) -> List[str]:
        """Build the argument list for xml_csv_converter.main()."""
        argv: List[str] = []

        mode_str = str(self.mode.get_value())
        if mode_str == "Single file":
            path = self.input_file.get_path()
        else:
            path = self.input_dir.get_path()

        if path:
            argv.extend(["--input", path])

        out = self.output_dir.get_path()
        if out:
            argv.extend(["--output-dir", out])

        if mode_str == "Directory" and self.recursive.get_value():
            argv.append("--recursive")

        if self.dry_run.get_value():
            argv.append("--dry-run")

        log_level = self.log_level.get_value()
        if log_level:
            argv.extend(["--log-level", str(log_level)])

        return argv

    def _on_run(self) -> None:
        self._execute(force_dry_run=False)

    def _on_dry_run(self) -> None:
        self._execute(force_dry_run=True)

    def _execute(self, force_dry_run: bool = False) -> None:
        module = _import_script("utils.xml_csv_converter")
        if module is None:
            self.log_viewer.append_error(
                "Failed to import utils.xml_csv_converter"
            )
            return
        argv = self.build_argv()
        if force_dry_run and "--dry-run" not in argv:
            argv.append("--dry-run")
        self.log_viewer.clear()
        self.log_viewer.append_line(
            f"[GUI] Running: xml_csv_converter {' '.join(argv)}"
        )
        self.run_controls.set_running(True)
        self._worker = ScriptRunnerWorker(module, argv)
        self._worker.output_line.connect(self.log_viewer.append_line)
        self._worker.error.connect(self.log_viewer.append_error)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.start()

    def _on_cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.log_viewer.append_error("[GUI] Cancelled by user")

    def _on_finished(self, exit_code: int) -> None:
        self.run_controls.set_running(False)
        if exit_code == 0:
            self.log_viewer.append_line("[GUI] Completed successfully")
        else:
            self.log_viewer.append_error(
                f"[GUI] Finished with exit code {exit_code}"
            )
        self._worker = None


class _TermsListWidget(QWidget):
    """A dynamic list widget for managing multiple search terms.

    Provides a :class:`~PySide6.QtWidgets.QListWidget` displaying the
    current terms, a text input with an *Add* button (also triggered by
    pressing Enter), and a *Remove Selected* button.  The list is
    persisted to :class:`~gui.utils.settings.SettingsManager` as a
    JSON-encoded list when a ``settings_key`` is supplied.
    """

    def __init__(
        self,
        settings_key: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._settings_key = settings_key

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Search Terms:"))

        self._list = QListWidget()
        self._list.setMinimumHeight(80)
        layout.addWidget(self._list)

        input_row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText("Enter a search term and press Add…")
        self._input.returnPressed.connect(self._add_term)
        input_row.addWidget(self._input, stretch=1)

        add_btn = QPushButton("Add")
        add_btn.setFixedWidth(60)
        add_btn.clicked.connect(self._add_term)
        input_row.addWidget(add_btn)

        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_selected)
        input_row.addWidget(remove_btn)

        layout.addLayout(input_row)

        if self._settings_key:
            self.set_terms(settings.load_list(self._settings_key, []))

    def _add_term(self) -> None:
        """Add the current input text as a new term (ignores duplicates)."""
        term = self._input.text().strip()
        if term and term not in self.get_terms():
            self._list.addItem(term)
            self._input.clear()
            self._persist()

    def _remove_selected(self) -> None:
        """Remove all currently selected terms from the list."""
        for item in self._list.selectedItems():
            self._list.takeItem(self._list.row(item))
        self._persist()

    def get_terms(self) -> List[str]:
        """Return the current list of search terms.

        Returns:
            Ordered list of term strings.
        """
        return [self._list.item(i).text() for i in range(self._list.count())]

    def set_terms(self, terms: List[str]) -> None:
        """Replace the current list with *terms*.

        Args:
            terms: New list of search term strings.
        """
        self._list.clear()
        for term in terms:
            self._list.addItem(term)

    def _persist(self) -> None:
        """Save the current term list to QSettings."""
        if self._settings_key:
            settings.save(self._settings_key, self.get_terms())


class CsvRecordFinderPanel(QWidget):
    """Panel for the CSV / Excel / XML record finder script.

    Allows the user to specify a directory of files, a column to search,
    one or more search terms, file types to include, and other options.
    Matches are written to a single output CSV.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._worker: Optional[ScriptRunnerWorker] = None
        pfx = "utils.csv_record_finder"

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>CSV / Excel / XML Record Finder</b>"))

        self.input_dir = FilePickerWidget(
            "Input Directory:", mode="directory",
            tooltip="Directory containing the files to search.",
            settings_key=f"{pfx}.input_dir",
        )
        layout.addWidget(self.input_dir)

        self.output_file = FilePickerWidget(
            "Output CSV:", mode="save",
            file_filter=CSV_FILTER,
            tooltip="Destination CSV file for all matching records.",
            settings_key=f"{pfx}.output_file",
        )
        layout.addWidget(self.output_file)

        self.column = FormFieldWidget(
            "Lookup Column:", field_type="text",
            tooltip="Name of the column to search (exact column name, case-sensitive).",
            placeholder="e.g. TransactionDescription",
            settings_key=f"{pfx}.column",
        )
        layout.addWidget(self.column)

        self._terms_widget = _TermsListWidget(
            settings_key=f"{pfx}.terms",
        )
        layout.addWidget(self._terms_widget)

        # File-type checkboxes grouped in a QGroupBox
        types_group = QGroupBox("File Types")
        types_layout = QHBoxLayout(types_group)
        self.ft_csv = FormFieldWidget(
            "CSV", field_type="checkbox",
            default=True,
            tooltip="Search *.csv files.",
            settings_key=f"{pfx}.ft_csv",
        )
        types_layout.addWidget(self.ft_csv)
        self.ft_xlsx = FormFieldWidget(
            "Excel (xlsx / xls)", field_type="checkbox",
            tooltip="Search *.xlsx and *.xls files (all sheets).",
            settings_key=f"{pfx}.ft_xlsx",
        )
        types_layout.addWidget(self.ft_xlsx)
        self.ft_xml = FormFieldWidget(
            "XML", field_type="checkbox",
            tooltip="Search *.xml files.",
            settings_key=f"{pfx}.ft_xml",
        )
        types_layout.addWidget(self.ft_xml)
        types_layout.addStretch()
        layout.addWidget(types_group)

        self.recursive = FormFieldWidget(
            "Recursive", field_type="checkbox",
            tooltip="Search subdirectories recursively.",
            settings_key=f"{pfx}.recursive",
        )
        layout.addWidget(self.recursive)

        self.sort_by = FormFieldWidget(
            "Secondary Sort:", field_type="text",
            tooltip=(
                "Optional comma-separated column names to sort by after the "
                "lookup column. Date columns are detected automatically."
            ),
            placeholder="e.g. TransactionPostedDate",
            settings_key=f"{pfx}.sort_by",
        )
        layout.addWidget(self.sort_by)

        self.source_column = FormFieldWidget(
            "Source Column:", field_type="text",
            default="SourceFile",
            tooltip=(
                "Name of the extra column appended to each output row "
                "recording the source filename."
            ),
            settings_key=f"{pfx}.source_column",
        )
        layout.addWidget(self.source_column)

        self.match_mode = FormFieldWidget(
            "Match Mode:", field_type="dropdown",
            choices=["contains", "equals"],
            default="contains",
            tooltip=(
                "contains: rows where the column includes the term as a substring.\n"
                "equals: rows where the column value exactly matches the term."
            ),
            settings_key=f"{pfx}.match_mode",
        )
        layout.addWidget(self.match_mode)

        self.case_sensitive = FormFieldWidget(
            "Case Sensitive", field_type="checkbox",
            tooltip="Enable case-sensitive term matching (default: case-insensitive).",
            settings_key=f"{pfx}.case_sensitive",
        )
        layout.addWidget(self.case_sensitive)

        self.encoding = FormFieldWidget(
            "Encoding:", field_type="text",
            default="utf-8",
            tooltip="Character encoding for CSV and XML files.",
            settings_key=f"{pfx}.encoding",
        )
        layout.addWidget(self.encoding)

        self.log_level = FormFieldWidget(
            "Log Level:", field_type="dropdown",
            choices=LOG_LEVELS, default="INFO",
            tooltip="Logging verbosity level.",
            settings_key=f"{pfx}.log_level",
        )
        layout.addWidget(self.log_level)

        self.run_controls = RunControlsWidget()
        self.run_controls.run_clicked.connect(self._on_run)
        self.run_controls.dry_run_clicked.connect(self._on_run)
        self.run_controls.cancel_clicked.connect(self._on_cancel)
        layout.addWidget(self.run_controls)

        self.log_viewer = LogViewerWidget()
        layout.addWidget(self.log_viewer, stretch=1)

    def build_argv(self) -> List[str]:
        """Build the argument list for ``csv_record_finder.main()``.

        Returns:
            List of CLI argument strings, excluding the program name.
        """
        argv: List[str] = []

        inp = self.input_dir.get_path()
        if inp:
            argv.extend(["--input-dir", inp])

        out = self.output_file.get_path()
        if out:
            argv.extend(["--output", out])

        col = str(self.column.get_value() or "").strip()
        if col:
            argv.extend(["--column", col])

        terms = self._terms_widget.get_terms()
        if terms:
            argv.append("--terms")
            argv.extend(terms)

        file_types: List[str] = []
        if self.ft_csv.get_value():
            file_types.append("csv")
        if self.ft_xlsx.get_value():
            file_types.append("xlsx")
        if self.ft_xml.get_value():
            file_types.append("xml")
        if file_types:
            argv.extend(["--file-types"] + file_types)

        if self.recursive.get_value():
            argv.append("--recursive")

        sort_by_raw = str(self.sort_by.get_value() or "").strip()
        if sort_by_raw:
            tokens = [t.strip() for t in sort_by_raw.split(",") if t.strip()]
            if tokens:
                argv.extend(["--sort-by"] + tokens)

        source_col = str(self.source_column.get_value() or "SourceFile").strip()
        if source_col:
            argv.extend(["--source-column", source_col])

        match_mode = str(self.match_mode.get_value() or "contains")
        if match_mode != "contains":
            argv.extend(["--match-mode", match_mode])

        if self.case_sensitive.get_value():
            argv.append("--case-sensitive")

        enc = str(self.encoding.get_value() or "utf-8").strip()
        if enc:
            argv.extend(["--encoding", enc])

        log_level = self.log_level.get_value()
        if log_level:
            argv.extend(["--log-level", str(log_level)])

        return argv

    def _on_run(self) -> None:
        self._execute()

    def _execute(self) -> None:
        module = _import_script("utils.csv_record_finder")
        if module is None:
            self.log_viewer.append_error(
                "Failed to import utils.csv_record_finder"
            )
            return
        argv = self.build_argv()
        self.log_viewer.clear()
        self.log_viewer.append_line(
            f"[GUI] Running: csv_record_finder {' '.join(argv)}"
        )
        self.run_controls.set_running(True)
        self._worker = ScriptRunnerWorker(module, argv)
        self._worker.output_line.connect(self.log_viewer.append_line)
        self._worker.error.connect(self.log_viewer.append_error)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.start()

    def _on_cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.log_viewer.append_error("[GUI] Cancelled by user")

    def _on_finished(self, exit_code: int) -> None:
        self.run_controls.set_running(False)
        if exit_code == 0:
            self.log_viewer.append_line("[GUI] Completed successfully")
        else:
            self.log_viewer.append_error(
                f"[GUI] Finished with exit code {exit_code}"
            )
        self._worker = None


class UtilitiesTab(QWidget):
    """Utilities tab with sidebar navigation."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)

        self._sidebar = QListWidget()
        self._sidebar.setFixedWidth(180)
        self._sidebar.currentRowChanged.connect(self._on_sidebar_changed)
        layout.addWidget(self._sidebar)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack, stretch=1)

        panels = [
            ("XLSX to CSV", XlsxConverterPanel()),
            ("XML to CSV", XmlConverterPanel()),
            ("Bulk Record Finder", CsvRecordFinderPanel()),
        ]

        for label, panel in panels:
            self._sidebar.addItem(label)
            self._stack.addWidget(panel)

        self._sidebar.setCurrentRow(0)

    def _on_sidebar_changed(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
