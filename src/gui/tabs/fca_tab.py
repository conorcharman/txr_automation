#!/usr/bin/env python3
"""
FCA Register Tab
================

Two FCA Financial Services Register panels:
- Firm Lookup (single FRN, name search, or LEI → name → FCA)
- Batch Check (process a CSV of FRNs or firm names)

Architecture mirrors the GLEIF tab.
"""

import re
from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.constants import LOG_LEVELS, CSV_FILTER
from gui.widgets import (
    ConfigLoaderWidget,
    FilePickerWidget,
    FormFieldWidget,
    LogViewerWidget,
    RunControlsWidget,
)
from gui.workers import ScriptRunnerWorker

# Matches the standard 20-character LEI format: 18 alphanumeric + 2 check digits.
_LEI_REGEX = re.compile(r"^[A-Z0-9]{18}\d{2}$", re.IGNORECASE)

# Common FCA regulated activity names for the permission dropdown.
_KNOWN_PERMISSIONS: List[str] = [
    "Accepting deposits",
    "Advising on investments (except pension transfers)",
    "Advising on P2P agreements",
    "Advising on pension transfers and pension opt-outs",
    "Advising on regulated mortgage contracts",
    "Advising on syndicate participation at Lloyd's",
    "Arranging (bringing about) deals in investments",
    "Arranging (bringing about) regulated mortgage contracts",
    "Arranging safeguarding and administration of assets",
    "Communicating financial promotions",
    "Dealing in investments as agent",
    "Dealing in investments as principal",
    "Effecting contracts of insurance",
    "Establishing, operating or winding up a collective investment scheme",
    "Insurance distribution activity",
    "Issuing electronic money",
    "Making arrangements with a view to transactions in investments",
    "Managing a UCITS",
    "Managing an AIF",
    "Managing investments",
    "Operating a multilateral trading facility",
    "Operating an organised trading facility",
    "Safeguarding and administering investments",
    "Sending dematerialised instructions",
    "Undertaking activities in relation to a regulated benchmark",
]


# ---------------------------------------------------------------------------
# Firm Lookup panel (single FRN or name search)
# ---------------------------------------------------------------------------

class FcaLookupPanel(QWidget):
    """Panel for FCA firm lookup: single FRN or name search (auto-detected)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._worker: Optional[ScriptRunnerWorker] = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>FCA Firm Lookup</b>"))

        self.config_loader = ConfigLoaderWidget()
        layout.addWidget(self.config_loader)

        # Unified query field (numeric → FRN lookup; text → name search)
        self.query = FormFieldWidget(
            "FRN, Name, or LEI:",
            field_type="text",
            tooltip=(
                "Enter a firm reference number (numeric) for an exact FRN lookup, "
                "a 20-character LEI to resolve via GLEIF then match on the FCA register, "
                "or a firm name for a name search."
            ),
            placeholder="e.g. 122702 or Barclays or 5493001KJTIIGC8Y1R12",
            settings_key="fca.lookup.query",
        )
        layout.addWidget(self.query)

        # Permission combo (editable — pick from list or type custom value)
        perm_label = QLabel("Permission to verify:")
        layout.addWidget(perm_label)
        self._permission_combo = QComboBox()
        self._permission_combo.setEditable(True)
        self._permission_combo.addItem("")  # blank = no filter
        self._permission_combo.addItems(_KNOWN_PERMISSIONS)
        self._permission_combo.setCurrentIndex(0)
        self._permission_combo.setToolTip(
            "Optional. Select or type a regulated activity name to highlight in results."
        )
        layout.addWidget(self._permission_combo)

        # GLEIF database path (needed only when the query is an LEI)
        self.gleif_db = FilePickerWidget(
            "GLEIF Database:",
            mode="file",
            tooltip=(
                "Path to the local GLEIF SQLite database.  Only required when looking "
                "up a firm by LEI — leave blank for FRN or name lookups."
            ),
            settings_key="fca.lookup.gleif_db_path",
        )
        layout.addWidget(self.gleif_db)

        # --- Common fields ---
        self.log_level = FormFieldWidget(
            "Log Level:", field_type="dropdown",
            choices=LOG_LEVELS, default="INFO",
            tooltip="Logging verbosity",
            settings_key="fca.lookup.log_level",
        )
        layout.addWidget(self.log_level)

        self.run_controls = RunControlsWidget()
        self.run_controls.run_clicked.connect(self._on_run)
        self.run_controls.cancel_clicked.connect(self._on_cancel)
        self.run_controls._dry_run_btn.setVisible(False)
        layout.addWidget(self.run_controls)

        self.log_viewer = LogViewerWidget()
        layout.addWidget(self.log_viewer, stretch=1)

    def _on_mode_changed(self, button_id: int, checked: bool) -> None:  # noqa: D102 — unused legacy stub
        pass

    def build_argv(self, query_override: Optional[str] = None) -> List[str]:
        """Build argv for fca-check.

        Args:
            query_override: When provided, use this string as the name
                query instead of the widget value (used for LEI resolution).
        """
        argv: List[str] = []

        query = query_override if query_override is not None else self.query.get_value().strip()
        if query:
            # Numeric → FRN lookup; anything else → name search.
            if query.isdigit():
                argv.extend(["--frn", query])
            else:
                argv.extend(["--name", query])

        permission = self._permission_combo.currentText().strip()
        if permission:
            argv.extend(["--permission", permission])

        config_path = self.config_loader.get_last_path()
        if config_path:
            argv.extend(["--config", config_path])

        log_level = self.log_level.get_value()
        if log_level:
            argv.extend(["--log-level", log_level])

        return argv

    def _on_run(self) -> None:
        import importlib
        raw_query = self.query.get_value().strip()

        # --- LEI resolution step ---
        if _LEI_REGEX.match(raw_query):
            self.log_viewer.clear()
            self.log_viewer.append_line(f"[GUI] Detected LEI: {raw_query}")
            self.log_viewer.append_line("[GUI] Resolving via GLEIF database…")

            db_path_str = self.gleif_db.get_path()
            if not db_path_str:
                self.log_viewer.append_error(
                    "[GUI] GLEIF database path not set. "
                    "Please configure it to resolve LEIs."
                )
                return

            db_path = Path(db_path_str)
            if not db_path.exists():
                self.log_viewer.append_error(
                    f"[GUI] GLEIF database not found: {db_path}"
                )
                return

            try:
                from gleif.cache import GleifCacheManager
                from gleif.lookup import GleifLookup

                cache = GleifCacheManager(db_path=db_path)
                cache.initialise_db()
                lookup = GleifLookup(cache=cache)
                lei_result = lookup.lookup_lei(raw_query.upper())
            except Exception as exc:  # noqa: BLE001
                self.log_viewer.append_error(
                    f"[GUI] GLEIF lookup failed: {exc}"
                )
                return

            if lei_result.reason == "NOT_IN_GLEIF":
                self.log_viewer.append_error(
                    f"[GUI] LEI '{raw_query}' not found in the GLEIF database."
                )
                return

            resolved_name = lei_result.legal_name
            self.log_viewer.append_line(
                f"[GUI] Resolved LEI {raw_query} to: {resolved_name}"
            )
            self.log_viewer.append_line(
                "[GUI] Running: fca-check (name search for closest match)"
            )
            self.run_controls.set_running(True)
            argv = self.build_argv(query_override=resolved_name)
        else:
            self.log_viewer.clear()
            self.log_viewer.append_line("[GUI] Running: fca-check")
            self.run_controls.set_running(True)
            argv = self.build_argv()

        module = importlib.import_module("src.fca.scripts.check_firm")
        self._worker = ScriptRunnerWorker(module, argv)
        self._worker.output_line.connect(self.log_viewer.append_line)
        self._worker.error.connect(self.log_viewer.append_error)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.start()

    def _on_cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self.log_viewer.append_error("[GUI] Cancelled by user")

    def _on_finished(self, exit_code: int) -> None:
        self.run_controls.set_running(False)
        if exit_code == 0:
            self.log_viewer.append_line("[GUI] Completed successfully")
        else:
            self.log_viewer.append_error(f"[GUI] Finished with exit code {exit_code}")
        self._worker = None


# ---------------------------------------------------------------------------
# Batch Check panel
# ---------------------------------------------------------------------------

class FcaBatchPanel(QWidget):
    """Panel for batch FCA check against a CSV of FRNs or firm names."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._worker: Optional[ScriptRunnerWorker] = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>FCA Batch Check</b>"))

        self.config_loader = ConfigLoaderWidget()
        layout.addWidget(self.config_loader)

        self.input_csv = FilePickerWidget(
            "Input CSV:", mode="file", file_filter=CSV_FILTER,
            tooltip=(
                "CSV file containing firm FRNs or names.\n"
                "FRN columns accepted: frn, fca_number, fca_ref, reference_number,\n"
                "  firm_reference_number, firm_ref, ref_no, and space-separated variants.\n"
                "Name columns accepted: name, firm_name, organisation_name,\n"
                "  company_name, counterparty_name, entity_name, legal_name, and variants."
            ),
            settings_key="fca.batch.input_csv",
        )
        layout.addWidget(self.input_csv)

        self.output_csv = FilePickerWidget(
            "Output CSV:", mode="save", file_filter=CSV_FILTER,
            tooltip="Output CSV with fca_frn, fca_status, fca_authorised, fca_permissions columns added.",
            settings_key="fca.batch.output_csv",
        )
        layout.addWidget(self.output_csv)

        # Permission combo (editable — pick from list or type custom value)
        perm_label = QLabel("Permission to verify:")
        layout.addWidget(perm_label)
        self._permission_combo = QComboBox()
        self._permission_combo.setEditable(True)
        self._permission_combo.addItem("")  # blank = no filter
        self._permission_combo.addItems(_KNOWN_PERMISSIONS)
        self._permission_combo.setCurrentIndex(0)
        self._permission_combo.setToolTip(
            "Optional. When set, adds a column named after the permission ("
            "Y/N) to the output CSV."
        )
        layout.addWidget(self._permission_combo)

        self.log_level = FormFieldWidget(
            "Log Level:", field_type="dropdown",
            choices=LOG_LEVELS, default="INFO",
            tooltip="Logging verbosity",
            settings_key="fca.batch.log_level",
        )
        layout.addWidget(self.log_level)

        self.run_controls = RunControlsWidget()
        self.run_controls.run_clicked.connect(self._on_run)
        self.run_controls.cancel_clicked.connect(self._on_cancel)
        self.run_controls._dry_run_btn.setVisible(False)
        layout.addWidget(self.run_controls)

        self.log_viewer = LogViewerWidget()
        layout.addWidget(self.log_viewer, stretch=1)

    def build_argv(self) -> List[str]:
        """Build argv for fca-check batch mode."""
        argv: List[str] = []

        input_path = self.input_csv.get_path()
        if input_path:
            argv.extend(["--input", input_path])

        output_path = self.output_csv.get_path()
        if output_path:
            argv.extend(["--output", output_path])

        permission = self._permission_combo.currentText().strip()
        if permission:
            argv.extend(["--permission", permission])

        config_path = self.config_loader.get_last_path()
        if config_path:
            argv.extend(["--config", config_path])

        log_level = self.log_level.get_value()
        if log_level:
            argv.extend(["--log-level", log_level])

        return argv

    def _on_run(self) -> None:
        import importlib
        module = importlib.import_module("src.fca.scripts.check_firm")
        argv = self.build_argv()
        self.log_viewer.clear()
        self.log_viewer.append_line("[GUI] Running: fca-check (batch)")
        self.run_controls.set_running(True)
        self._worker = ScriptRunnerWorker(module, argv)
        self._worker.output_line.connect(self.log_viewer.append_line)
        self._worker.error.connect(self.log_viewer.append_error)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.start()

    def _on_cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self.log_viewer.append_error("[GUI] Cancelled by user")

    def _on_finished(self, exit_code: int) -> None:
        self.run_controls.set_running(False)
        if exit_code == 0:
            self.log_viewer.append_line("[GUI] Completed successfully")
        else:
            self.log_viewer.append_error(f"[GUI] Finished with exit code {exit_code}")
        self._worker = None


# ---------------------------------------------------------------------------
# Main FCA Tab
# ---------------------------------------------------------------------------

class FcaTab(QWidget):
    """FCA Financial Services Register tab with sidebar navigation."""

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
            ("Lookup Firm", FcaLookupPanel()),
            ("Batch Check", FcaBatchPanel()),
        ]

        for label, panel in panels:
            self._sidebar.addItem(label)
            self._stack.addWidget(panel)

        self._sidebar.setCurrentRow(0)

    def _on_sidebar_changed(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
