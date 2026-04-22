#!/usr/bin/env python3
"""
Scheduler Tab (API-Backed)
==========================

Sixth application tab — schedule-based automation for accuracy testing
pipelines and individual script schedules.

Panels (sidebar-driven):
1. **Dashboard** — Two tables: Pipelines (13-step accuracy pipelines) and
   Script Schedules (individual script schedules). Actions: Trigger, Toggle,
   Edit, Delete.
2. **Pipeline Editor** — Create/edit a 13-step accuracy testing pipeline
   with step checklist grouped by Utilities / Validation / Push, testing
   period, frequency, and stop-on-error.
3. **Schedule Editor** — Create/edit a single-script schedule with script
   selector, frequency, cron expression, and config JSON.
4. **Run History** — Recent jobs fetched from ``GET /api/jobs``.

All data comes from the API. The ``ScheduleEngine`` polls every 30s.

Version 2.0 Changes:
- Replaced local ScheduleStore with API calls
- Replaced local PipelineExecutor with ApiWorker
- Added 13-step pipeline editor matching web app
- Added separate Pipeline and Script Schedule sections
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui.api.client import ApiClient
from gui.constants import (
    COLOUR_BORDER,
    COLOUR_GREY,
    COLOUR_RED,
    COLOUR_SURFACE,
    FISCAL_YEARS,
    LOG_LEVELS,
    PIPELINE_STEPS,
    PIPELINE_UTILITY_STEPS,
    PIPELINE_VALIDATION_STEPS,
    PIPELINE_PUSH_STEPS,
    QUARTERS,
    SCHEDULE_FREQUENCIES,
)
from gui.scheduler.engine import ScheduleEngine
from gui.utils.settings import settings
from gui.widgets.status_badge import StatusBadgeWidget
from gui.workers import ApiWorker


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_COLOUR_SUCCESS = "#2E7D32"

_SIDEBAR_PANELS = [
    "Dashboard",
    "Pipeline Editor",
    "Schedule Editor",
    "Run History",
]

# All pipeline script keys with labels, used in the ScheduleEditor script picker
_ALL_SCRIPTS = [
    ("buyer_id_validation", "Buyer ID Validation"),
    ("seller_id_validation", "Seller ID Validation"),
    ("inconsistent_buyer_id_validation", "Inconsistent Buyer ID"),
    ("inconsistent_seller_id_validation", "Inconsistent Seller ID"),
    ("validate_ftbdm", "Fund Trade Buyer DM"),
    ("validate_ftsdm", "Fund Trade Seller DM"),
    ("incorrect_net_amount_validation", "Incorrect Net Amount"),
    ("non_zero_net_quantity", "Non-Zero Net Quantity"),
    ("non_zero_net_amount", "Non-Zero Net Amount"),
    ("run_all_validations", "Run All Validations"),
    ("sql_extract_generator", "SQL Extract Generator"),
    ("accuracy_template_generator", "Accuracy Template Generator"),
    ("collate_csv_extracts", "Collate CSV Extracts"),
    ("data_push", "Data Push"),
    ("replay_phase2", "Replay Phase 2"),
    ("replay_phase3", "Replay Phase 3"),
    ("replay_phase3_final", "Replay Phase 3 Final Lookup"),
    ("replay_merge_inconsistent", "Replay Merge Inconsistent"),
    ("firds_refresh", "FIRDS Refresh Cache"),
    ("firds_check", "FIRDS Check Reportability"),
    ("firds_backfill", "FIRDS Backfill"),
    ("gleif_refresh", "GLEIF Refresh Cache"),
    ("gleif_check", "GLEIF Check LEI"),
    ("gleif_backfill", "GLEIF Backfill"),
    ("xlsx_csv_converter", "XLSX → CSV Converter"),
    ("xml_csv_converter", "XML → CSV Converter"),
]

_STATUS_COLOURS = {
    "success": _COLOUR_SUCCESS,
    "failed": COLOUR_RED,
    "running": "#F57C00",
    "pending": COLOUR_GREY,
    "waiting": "#FF8F00",
    "cancelled": COLOUR_GREY,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scrollable(inner: QWidget) -> QScrollArea:
    """Wrap *inner* in a frameless, resizable QScrollArea."""
    scroll = QScrollArea()
    scroll.setWidget(inner)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    return scroll


def _header_label(text: str) -> QLabel:
    """Return a bold 11pt section header label."""
    lbl = QLabel(text)
    font = QFont()
    font.setPointSize(11)
    font.setBold(True)
    lbl.setFont(font)
    return lbl


def _table_item(text: str, colour: Optional[str] = None) -> QTableWidgetItem:
    """Return a non-editable QTableWidgetItem, optionally coloured."""
    from PySide6.QtGui import QBrush, QColor as _QColor

    item = QTableWidgetItem(text)
    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    if colour:
        item.setForeground(QBrush(_QColor(colour)))
    return item


def _format_dt(iso: Optional[str]) -> str:
    """Format an ISO datetime string to compact display, or '—'."""
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return str(iso)


def _freq_label(value: str) -> str:
    """Return a human-readable label for a frequency value."""
    for val, label in SCHEDULE_FREQUENCIES:
        if val == value:
            return label
    return value


def _step_label(key: str) -> str:
    """Return a display name for a pipeline step key."""
    for k, label in PIPELINE_STEPS:
        if k == key:
            return label
    return key


def _script_label(key: str) -> str:
    """Return a display name for a script key."""
    for k, label in _ALL_SCRIPTS:
        if k == key:
            return label
    return key


# ---------------------------------------------------------------------------
# Panel 1 — Dashboard
# ---------------------------------------------------------------------------


class SchedulerDashboardPanel(QWidget):
    """Dashboard showing pipelines and script schedules from the API.

    Signals:
        edit_pipeline_requested(dict): Emitted when editing a pipeline.
        edit_schedule_requested(dict): Emitted when editing a schedule.
    """

    edit_pipeline_requested = Signal(object)
    edit_schedule_requested = Signal(object)

    def __init__(
        self,
        engine: ScheduleEngine,
        api_client: ApiClient,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._engine = engine
        self._client = api_client

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        # Header
        header_row = QHBoxLayout()
        header_row.addWidget(_header_label("Scheduler Dashboard"))
        header_row.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedWidth(80)
        refresh_btn.clicked.connect(self.refresh)
        header_row.addWidget(refresh_btn)
        outer.addLayout(header_row)

        # ── Pipelines section ────────────────────────────────────────
        outer.addWidget(_header_label("Accuracy Testing Pipelines"))

        self._pipeline_table = QTableWidget(0, 5)
        self._pipeline_table.setHorizontalHeaderLabels([
            "Name", "Frequency", "Steps", "Last Status", "Next Run",
        ])
        self._pipeline_table.horizontalHeader().setStretchLastSection(True)
        self._pipeline_table.verticalHeader().setVisible(False)
        self._pipeline_table.setAlternatingRowColors(True)
        self._pipeline_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._pipeline_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._pipeline_table.setStyleSheet(
            f"QTableWidget {{ border: 1px solid {COLOUR_BORDER}; }}"
        )
        outer.addWidget(self._pipeline_table)

        # Pipeline action buttons
        p_btn_row = QHBoxLayout()
        self._p_trigger_btn = QPushButton("Trigger Now")
        self._p_trigger_btn.clicked.connect(self._on_trigger_pipeline)
        p_btn_row.addWidget(self._p_trigger_btn)

        self._p_toggle_btn = QPushButton("Enable / Disable")
        self._p_toggle_btn.clicked.connect(self._on_toggle_pipeline)
        p_btn_row.addWidget(self._p_toggle_btn)

        self._p_edit_btn = QPushButton("Edit")
        self._p_edit_btn.clicked.connect(self._on_edit_pipeline)
        p_btn_row.addWidget(self._p_edit_btn)

        self._p_delete_btn = QPushButton("Delete")
        self._p_delete_btn.setStyleSheet(
            f"QPushButton:hover {{ background-color: {COLOUR_RED}; color: white; }}"
        )
        self._p_delete_btn.clicked.connect(self._on_delete_pipeline)
        p_btn_row.addWidget(self._p_delete_btn)
        p_btn_row.addStretch()
        outer.addLayout(p_btn_row)

        # ── Script Schedules section ─────────────────────────────────
        outer.addWidget(_header_label("Script Schedules"))

        self._schedule_table = QTableWidget(0, 5)
        self._schedule_table.setHorizontalHeaderLabels([
            "Name", "Script", "Frequency", "Last Status", "Next Run",
        ])
        self._schedule_table.horizontalHeader().setStretchLastSection(True)
        self._schedule_table.verticalHeader().setVisible(False)
        self._schedule_table.setAlternatingRowColors(True)
        self._schedule_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._schedule_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._schedule_table.setStyleSheet(
            f"QTableWidget {{ border: 1px solid {COLOUR_BORDER}; }}"
        )
        outer.addWidget(self._schedule_table)

        # Schedule action buttons
        s_btn_row = QHBoxLayout()
        self._s_trigger_btn = QPushButton("Trigger Now")
        self._s_trigger_btn.clicked.connect(self._on_trigger_schedule)
        s_btn_row.addWidget(self._s_trigger_btn)

        self._s_toggle_btn = QPushButton("Enable / Disable")
        self._s_toggle_btn.clicked.connect(self._on_toggle_schedule)
        s_btn_row.addWidget(self._s_toggle_btn)

        self._s_edit_btn = QPushButton("Edit")
        self._s_edit_btn.clicked.connect(self._on_edit_schedule)
        s_btn_row.addWidget(self._s_edit_btn)

        self._s_delete_btn = QPushButton("Delete")
        self._s_delete_btn.setStyleSheet(
            f"QPushButton:hover {{ background-color: {COLOUR_RED}; color: white; }}"
        )
        self._s_delete_btn.clicked.connect(self._on_delete_schedule)
        s_btn_row.addWidget(self._s_delete_btn)
        s_btn_row.addStretch()
        outer.addLayout(s_btn_row)

        # Wire engine refresh
        engine.data_refreshed.connect(self.refresh)
        self.refresh()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Repopulate both tables from the engine's cached data."""
        self._populate_pipeline_table()
        self._populate_schedule_table()

    # ------------------------------------------------------------------
    # Pipeline table
    # ------------------------------------------------------------------

    def _populate_pipeline_table(self) -> None:
        """Fill the pipeline table from engine data."""
        self._pipeline_table.setRowCount(0)
        for p in self._engine.pipelines:
            row = self._pipeline_table.rowCount()
            self._pipeline_table.insertRow(row)

            name_item = _table_item(p.get("name", ""))
            name_item.setData(Qt.ItemDataRole.UserRole, p)
            self._pipeline_table.setItem(row, 0, name_item)

            self._pipeline_table.setItem(
                row, 1, _table_item(_freq_label(p.get("frequency", "")))
            )

            # Steps count
            scripts = p.get("selectedScripts", [])
            self._pipeline_table.setItem(
                row, 2, _table_item(f"{len(scripts)} of 13")
            )

            # Last status
            status = p.get("lastStatus") or "never_run"
            colour = _STATUS_COLOURS.get(status, COLOUR_GREY)
            self._pipeline_table.setItem(
                row, 3, _table_item(status.replace("_", " ").title(), colour)
            )

            self._pipeline_table.setItem(
                row, 4, _table_item(_format_dt(p.get("nextRunAt")))
            )

        self._pipeline_table.resizeColumnsToContents()

    def _selected_pipeline(self) -> Optional[Dict[str, Any]]:
        """Return the data dict for the selected pipeline row."""
        row = self._pipeline_table.currentRow()
        if row < 0:
            return None
        item = self._pipeline_table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    # ------------------------------------------------------------------
    # Schedule table
    # ------------------------------------------------------------------

    def _populate_schedule_table(self) -> None:
        """Fill the schedule table from engine data."""
        self._schedule_table.setRowCount(0)
        for s in self._engine.schedules:
            row = self._schedule_table.rowCount()
            self._schedule_table.insertRow(row)

            name_item = _table_item(s.get("name", ""))
            name_item.setData(Qt.ItemDataRole.UserRole, s)
            self._schedule_table.setItem(row, 0, name_item)

            self._schedule_table.setItem(
                row, 1, _table_item(_script_label(s.get("scriptName", "")))
            )
            self._schedule_table.setItem(
                row, 2, _table_item(_freq_label(s.get("frequency", "")))
            )

            status = s.get("lastStatus") or "never_run"
            colour = _STATUS_COLOURS.get(status, COLOUR_GREY)
            self._schedule_table.setItem(
                row, 3, _table_item(status.replace("_", " ").title(), colour)
            )

            self._schedule_table.setItem(
                row, 4, _table_item(_format_dt(s.get("nextRunAt")))
            )

        self._schedule_table.resizeColumnsToContents()

    def _selected_schedule(self) -> Optional[Dict[str, Any]]:
        """Return the data dict for the selected schedule row."""
        row = self._schedule_table.currentRow()
        if row < 0:
            return None
        item = self._schedule_table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    # ------------------------------------------------------------------
    # Pipeline actions
    # ------------------------------------------------------------------

    def _on_trigger_pipeline(self) -> None:
        """Trigger the selected pipeline."""
        p = self._selected_pipeline()
        if not p:
            return
        job_id = self._engine.trigger_pipeline(p["id"])
        if job_id:
            QMessageBox.information(
                self, "Pipeline Triggered",
                f"Job {job_id} started for '{p.get('name', '')}'.",
            )

    def _on_toggle_pipeline(self) -> None:
        """Toggle the selected pipeline's active state."""
        p = self._selected_pipeline()
        if p:
            self._engine.toggle_pipeline(p["id"])

    def _on_edit_pipeline(self) -> None:
        """Open the pipeline editor with the selected pipeline."""
        p = self._selected_pipeline()
        if p:
            self.edit_pipeline_requested.emit(p)

    def _on_delete_pipeline(self) -> None:
        """Delete the selected pipeline after confirmation."""
        p = self._selected_pipeline()
        if not p:
            return
        reply = QMessageBox.question(
            self, "Delete Pipeline",
            f"Permanently delete pipeline '{p.get('name', '')}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._engine.delete_pipeline(p["id"])

    # ------------------------------------------------------------------
    # Schedule actions
    # ------------------------------------------------------------------

    def _on_trigger_schedule(self) -> None:
        """Trigger the selected schedule."""
        s = self._selected_schedule()
        if not s:
            return
        job_id = self._engine.trigger_schedule(s["id"])
        if job_id:
            QMessageBox.information(
                self, "Schedule Triggered",
                f"Job {job_id} started for '{s.get('name', '')}'.",
            )

    def _on_toggle_schedule(self) -> None:
        """Toggle the selected schedule's active state."""
        s = self._selected_schedule()
        if s:
            self._engine.toggle_schedule(s["id"])

    def _on_edit_schedule(self) -> None:
        """Open the schedule editor with the selected schedule."""
        s = self._selected_schedule()
        if s:
            self.edit_schedule_requested.emit(s)

    def _on_delete_schedule(self) -> None:
        """Delete the selected schedule after confirmation."""
        s = self._selected_schedule()
        if not s:
            return
        reply = QMessageBox.question(
            self, "Delete Schedule",
            f"Permanently delete schedule '{s.get('name', '')}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._engine.delete_schedule(s["id"])


# ---------------------------------------------------------------------------
# Panel 2 — Pipeline Editor (13-step)
# ---------------------------------------------------------------------------


class PipelineEditorPanel(QWidget):
    """Create or edit a 13-step accuracy testing pipeline.

    Shows step checkboxes grouped by Utilities / Validation / Push,
    testing period, frequency, and stop-on-error. Saves via API.

    Signals:
        saved(str): Emitted with pipeline ID on save.
    """

    saved = Signal(str)

    def __init__(
        self,
        api_client: ApiClient,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._client = api_client
        self._editing_id: Optional[str] = None

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        layout.addWidget(_header_label("Pipeline Editor"))

        # Name
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Name:"))
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. FY26 Q1 Full Run")
        name_row.addWidget(self._name_edit)
        layout.addLayout(name_row)

        # Testing period
        period_row = QHBoxLayout()
        period_row.addWidget(QLabel("Fiscal Year:"))
        self._fy_combo = QComboBox()
        self._fy_combo.addItems(FISCAL_YEARS)
        period_row.addWidget(self._fy_combo)
        period_row.addWidget(QLabel("Quarter:"))
        self._q_combo = QComboBox()
        self._q_combo.addItems(QUARTERS)
        period_row.addWidget(self._q_combo)
        period_row.addStretch()
        layout.addLayout(period_row)

        # Frequency
        freq_row = QHBoxLayout()
        freq_row.addWidget(QLabel("Frequency:"))
        self._freq_combo = QComboBox()
        for val, label in SCHEDULE_FREQUENCIES:
            self._freq_combo.addItem(label, val)
        self._freq_combo.currentIndexChanged.connect(self._on_freq_changed)
        freq_row.addWidget(self._freq_combo)
        freq_row.addStretch()
        layout.addLayout(freq_row)

        # Cron (shown for custom only)
        self._cron_row = QWidget()
        cron_h = QHBoxLayout(self._cron_row)
        cron_h.setContentsMargins(0, 0, 0, 0)
        cron_h.addWidget(QLabel("Cron:"))
        self._cron_edit = QLineEdit()
        self._cron_edit.setPlaceholderText("e.g. 0 6 * * 1")
        cron_h.addWidget(self._cron_edit)
        self._cron_row.setVisible(False)
        layout.addWidget(self._cron_row)

        # ── Step checklist ───────────────────────────────────────────
        # Step strip (visual indicator)
        self._step_strip = QHBoxLayout()
        self._step_strip_labels: List[QLabel] = []
        for i, (key, label) in enumerate(PIPELINE_STEPS):
            if i > 0:
                arrow = QLabel("→")
                arrow.setStyleSheet("color: grey; font-size: 8px;")
                self._step_strip.addWidget(arrow)
            lbl = QLabel(str(i + 1))
            lbl.setFixedSize(22, 22)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                "border-radius: 11px; font-size: 10px; font-weight: bold; "
                "background: #E3F2FD; color: #1976D2; border: 1px solid #90CAF9;"
            )
            lbl.setToolTip(f"Step {i + 1}: {label}")
            self._step_strip_labels.append(lbl)
            self._step_strip.addWidget(lbl)
        self._step_strip.addStretch()
        layout.addLayout(self._step_strip)

        # Grouped checkboxes
        self._step_checkboxes: Dict[str, QCheckBox] = {}

        # Utilities group
        util_group = QGroupBox("Utilities")
        util_v = QVBoxLayout(util_group)
        for key in PIPELINE_UTILITY_STEPS:
            cb = QCheckBox(_step_label(key))
            cb.setChecked(True)
            cb.stateChanged.connect(self._update_strip)
            self._step_checkboxes[key] = cb
            util_v.addWidget(cb)
        layout.addWidget(util_group)

        # "Wait for extracts" note
        wait_note = QLabel(
            "\u23f3 After Extract Generator, the pipeline pauses until "
            "extract CSVs are available (manual DTF execution or wait)."
        )
        wait_note.setWordWrap(True)
        wait_note.setStyleSheet(
            "color: #FF8F00; font-style: italic; padding: 4px 8px; "
            "background: #FFF8E1; border: 1px solid #FFE082; border-radius: 4px;"
        )
        layout.addWidget(wait_note)

        # Validation group
        val_group = QGroupBox("Validation Scripts")
        val_v = QVBoxLayout(val_group)
        for key in PIPELINE_VALIDATION_STEPS:
            cb = QCheckBox(_step_label(key))
            cb.setChecked(True)
            cb.stateChanged.connect(self._update_strip)
            self._step_checkboxes[key] = cb
            val_v.addWidget(cb)
        layout.addWidget(val_group)

        # Push group
        push_group = QGroupBox("Data Push")
        push_v = QVBoxLayout(push_group)
        for key in PIPELINE_PUSH_STEPS:
            cb = QCheckBox(_step_label(key))
            cb.setChecked(True)
            cb.stateChanged.connect(self._update_strip)
            self._step_checkboxes[key] = cb
            push_v.addWidget(cb)
        layout.addWidget(push_group)

        # Select all / deselect all
        sel_row = QHBoxLayout()
        sel_all_btn = QPushButton("Select All")
        sel_all_btn.setFixedWidth(100)
        sel_all_btn.clicked.connect(
            lambda: [cb.setChecked(True) for cb in self._step_checkboxes.values()]
        )
        sel_row.addWidget(sel_all_btn)
        desel_all_btn = QPushButton("Deselect All")
        desel_all_btn.setFixedWidth(100)
        desel_all_btn.clicked.connect(
            lambda: [cb.setChecked(False) for cb in self._step_checkboxes.values()]
        )
        sel_row.addWidget(desel_all_btn)
        sel_row.addStretch()
        layout.addLayout(sel_row)

        # Stop on error
        self._stop_on_error = QCheckBox("Stop on first error")
        layout.addWidget(self._stop_on_error)

        # Active toggle
        self._active_cb = QCheckBox("Active (fires automatically on schedule)")
        self._active_cb.setChecked(True)
        layout.addWidget(self._active_cb)

        layout.addStretch()

        # Action buttons
        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save Pipeline")
        save_btn.setProperty("primary", True)
        save_btn.setFixedWidth(120)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(80)
        cancel_btn.clicked.connect(lambda: self.saved.emit(""))
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(_scrollable(inner))

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def load_pipeline(self, data: Dict[str, Any]) -> None:
        """Populate the form from an existing pipeline dict."""
        self._editing_id = data.get("id")
        self._name_edit.setText(data.get("name", ""))
        self._fy_combo.setCurrentText(data.get("fiscalYear", "FY26"))
        self._q_combo.setCurrentText(data.get("quarter", "Q1"))

        freq = data.get("frequency", "daily")
        idx = self._freq_combo.findData(freq)
        if idx >= 0:
            self._freq_combo.setCurrentIndex(idx)
        self._cron_edit.setText(data.get("cronExpression", ""))

        selected = set(data.get("selectedScripts", []))
        for key, cb in self._step_checkboxes.items():
            cb.setChecked(key in selected)

        self._stop_on_error.setChecked(data.get("stopOnError", False))
        self._active_cb.setChecked(data.get("isActive", True))
        self._update_strip()

    def clear(self) -> None:
        """Reset to defaults for creating a new pipeline."""
        self._editing_id = None
        self._name_edit.clear()
        self._fy_combo.setCurrentIndex(0)
        self._q_combo.setCurrentIndex(0)
        self._freq_combo.setCurrentIndex(0)
        self._cron_edit.clear()
        for cb in self._step_checkboxes.values():
            cb.setChecked(True)
        self._stop_on_error.setChecked(False)
        self._active_cb.setChecked(True)
        self._update_strip()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_freq_changed(self) -> None:
        """Show/hide cron row based on frequency."""
        self._cron_row.setVisible(self._freq_combo.currentData() == "custom")

    def _update_strip(self) -> None:
        """Update the visual step strip to reflect checkbox state."""
        for i, (key, _label) in enumerate(PIPELINE_STEPS):
            lbl = self._step_strip_labels[i]
            checked = self._step_checkboxes.get(key, None)
            if checked and checked.isChecked():
                lbl.setStyleSheet(
                    "border-radius: 11px; font-size: 10px; font-weight: bold; "
                    "background: #E3F2FD; color: #1976D2; border: 1px solid #90CAF9;"
                )
            else:
                lbl.setStyleSheet(
                    "border-radius: 11px; font-size: 10px; "
                    "background: #f5f5f5; color: #ccc; border: 1px solid #e0e0e0;"
                )

    def _on_save(self) -> None:
        """Validate and save the pipeline to the API."""
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Pipeline name is required.")
            return

        selected = [
            key for key, cb in self._step_checkboxes.items() if cb.isChecked()
        ]
        if not selected:
            QMessageBox.warning(self, "Validation", "Select at least one step.")
            return

        payload = {
            "name": name,
            "fiscalYear": self._fy_combo.currentText(),
            "quarter": self._q_combo.currentText(),
            "selectedScripts": selected,
            "frequency": self._freq_combo.currentData(),
            "cronExpression": self._cron_edit.text().strip() if self._freq_combo.currentData() == "custom" else "",
            "stopOnError": self._stop_on_error.isChecked(),
            "isActive": self._active_cb.isChecked(),
        }

        try:
            if self._editing_id:
                from gui.api.pipeline import update_pipeline

                update_pipeline(self._client, self._editing_id, payload)
            else:
                from gui.api.pipeline import create_pipeline

                result = create_pipeline(self._client, payload)
                self._editing_id = result.get("id")

            self.saved.emit(self._editing_id or "")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to save: {exc}")


# ---------------------------------------------------------------------------
# Panel 3 — Schedule Editor
# ---------------------------------------------------------------------------


class ScheduleEditorPanel(QWidget):
    """Create or edit a single-script schedule.

    Signals:
        saved(str): Emitted with schedule ID on save, or "" on cancel.
    """

    saved = Signal(str)

    def __init__(
        self,
        api_client: ApiClient,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._client = api_client
        self._editing_id: Optional[str] = None

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        layout.addWidget(_header_label("Schedule Editor"))

        # Name
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Name:"))
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. Daily Buyer Validation")
        name_row.addWidget(self._name_edit)
        layout.addLayout(name_row)

        # Script
        script_row = QHBoxLayout()
        script_row.addWidget(QLabel("Script:"))
        self._script_combo = QComboBox()
        for key, label in _ALL_SCRIPTS:
            self._script_combo.addItem(label, key)
        script_row.addWidget(self._script_combo)
        script_row.addStretch()
        layout.addLayout(script_row)

        # Frequency
        freq_row = QHBoxLayout()
        freq_row.addWidget(QLabel("Frequency:"))
        self._freq_combo = QComboBox()
        for val, label in SCHEDULE_FREQUENCIES:
            self._freq_combo.addItem(label, val)
        self._freq_combo.currentIndexChanged.connect(self._on_freq_changed)
        freq_row.addWidget(self._freq_combo)
        freq_row.addStretch()
        layout.addLayout(freq_row)

        # Cron
        self._cron_row = QWidget()
        cron_h = QHBoxLayout(self._cron_row)
        cron_h.setContentsMargins(0, 0, 0, 0)
        cron_h.addWidget(QLabel("Cron:"))
        self._cron_edit = QLineEdit()
        self._cron_edit.setPlaceholderText("e.g. 0 6 * * 1")
        cron_h.addWidget(self._cron_edit)
        self._cron_row.setVisible(False)
        layout.addWidget(self._cron_row)

        # Config JSON
        layout.addWidget(QLabel("Configuration (JSON):"))
        self._config_edit = QTextEdit()
        self._config_edit.setMaximumHeight(150)
        self._config_edit.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 9pt;"
        )
        self._config_edit.setPlainText("{}")
        layout.addWidget(self._config_edit)

        # Active
        self._active_cb = QCheckBox("Active (fires automatically on schedule)")
        self._active_cb.setChecked(True)
        layout.addWidget(self._active_cb)

        layout.addStretch()

        # Action buttons
        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save Schedule")
        save_btn.setProperty("primary", True)
        save_btn.setFixedWidth(120)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(80)
        cancel_btn.clicked.connect(lambda: self.saved.emit(""))
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(_scrollable(inner))

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def load_schedule(self, data: Dict[str, Any]) -> None:
        """Populate the form from an existing schedule dict."""
        self._editing_id = data.get("id")
        self._name_edit.setText(data.get("name", ""))

        script = data.get("scriptName", "")
        idx = self._script_combo.findData(script)
        if idx >= 0:
            self._script_combo.setCurrentIndex(idx)

        freq = data.get("frequency", "daily")
        idx = self._freq_combo.findData(freq)
        if idx >= 0:
            self._freq_combo.setCurrentIndex(idx)

        self._cron_edit.setText(data.get("cronExpression", ""))

        config_data = data.get("configData", {})
        self._config_edit.setPlainText(
            json.dumps(config_data, indent=2) if config_data else "{}"
        )
        self._active_cb.setChecked(data.get("isActive", True))

    def clear(self) -> None:
        """Reset to defaults for creating a new schedule."""
        self._editing_id = None
        self._name_edit.clear()
        self._script_combo.setCurrentIndex(0)
        self._freq_combo.setCurrentIndex(0)
        self._cron_edit.clear()
        self._config_edit.setPlainText("{}")
        self._active_cb.setChecked(True)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_freq_changed(self) -> None:
        """Show/hide cron row based on frequency."""
        self._cron_row.setVisible(self._freq_combo.currentData() == "custom")

    def _on_save(self) -> None:
        """Validate and save the schedule to the API."""
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Schedule name is required.")
            return

        try:
            config_data = json.loads(self._config_edit.toPlainText() or "{}")
        except json.JSONDecodeError as exc:
            QMessageBox.warning(self, "Validation", f"Invalid JSON: {exc}")
            return

        payload = {
            "name": name,
            "scriptName": self._script_combo.currentData(),
            "frequency": self._freq_combo.currentData(),
            "cronExpression": self._cron_edit.text().strip() if self._freq_combo.currentData() == "custom" else "",
            "configData": config_data,
            "isActive": self._active_cb.isChecked(),
        }

        try:
            if self._editing_id:
                from gui.api.scheduler import update_schedule

                update_schedule(self._client, self._editing_id, payload)
            else:
                from gui.api.scheduler import create_schedule

                result = create_schedule(self._client, payload)
                self._editing_id = result.get("id")

            self.saved.emit(self._editing_id or "")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to save: {exc}")


# ---------------------------------------------------------------------------
# Panel 4 — Run History
# ---------------------------------------------------------------------------


class RunHistoryPanel(QWidget):
    """Recent jobs fetched from ``GET /api/jobs``."""

    def __init__(
        self,
        api_client: ApiClient,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._client = api_client

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(8)

        # Header
        header_row = QHBoxLayout()
        header_row.addWidget(_header_label("Run History"))
        header_row.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedWidth(80)
        refresh_btn.clicked.connect(self.refresh)
        header_row.addWidget(refresh_btn)
        outer.addLayout(header_row)

        # Splitter: table + detail pane
        splitter = QSplitter(Qt.Orientation.Vertical)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels([
            "Script", "Status", "Started", "Duration", "Job ID",
        ])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setStyleSheet(
            f"QTableWidget {{ border: 1px solid {COLOUR_BORDER}; }}"
        )
        self._table.itemSelectionChanged.connect(self._on_row_selected)
        splitter.addWidget(self._table)

        # Detail pane
        detail = QWidget()
        detail_v = QVBoxLayout(detail)
        detail_v.setContentsMargins(0, 4, 0, 0)

        detail_v.addWidget(QLabel("Job output:"))
        self._detail_text = QTextEdit()
        self._detail_text.setReadOnly(True)
        self._detail_text.setStyleSheet(
            f"background: {COLOUR_SURFACE}; font-family: Consolas, monospace; font-size: 9pt;"
        )
        detail_v.addWidget(self._detail_text, stretch=1)

        splitter.addWidget(detail)
        splitter.setSizes([300, 150])
        outer.addWidget(splitter, stretch=1)

        # Defer the first load so the widget tree is built before any network call.
        QTimer.singleShot(0, self.refresh)

    def refresh(self) -> None:
        """Fetch recent jobs from the API and populate the table."""
        try:
            from gui.api.jobs import list_jobs

            jobs = list_jobs(self._client, limit=100)
        except Exception:
            jobs = []

        self._table.setRowCount(0)
        for job in jobs:
            row = self._table.rowCount()
            self._table.insertRow(row)

            script_item = _table_item(
                _script_label(job.get("scriptName", job.get("taskName", "")))
            )
            script_item.setData(Qt.ItemDataRole.UserRole, job)
            self._table.setItem(row, 0, script_item)

            status = job.get("status", "")
            colour = _STATUS_COLOURS.get(status, COLOUR_GREY)
            self._table.setItem(row, 1, _table_item(status.title(), colour))

            self._table.setItem(row, 2, _table_item(_format_dt(job.get("startedAt"))))

            # Duration
            started = job.get("startedAt")
            completed = job.get("completedAt")
            if started and completed:
                try:
                    s = datetime.fromisoformat(started)
                    e = datetime.fromisoformat(completed)
                    secs = int((e - s).total_seconds())
                    dur = f"{secs // 60}m {secs % 60}s" if secs >= 60 else f"{secs}s"
                except (ValueError, TypeError):
                    dur = "—"
            else:
                dur = "—"
            self._table.setItem(row, 3, _table_item(dur))

            self._table.setItem(
                row, 4, _table_item(job.get("id", "")[:8])
            )

        self._table.resizeColumnsToContents()
        self._detail_text.clear()

    def _on_row_selected(self) -> None:
        """Show job logs in the detail pane."""
        row = self._table.currentRow()
        if row < 0:
            self._detail_text.clear()
            return

        item = self._table.item(row, 0)
        if not item:
            return
        job = item.data(Qt.ItemDataRole.UserRole)
        if not job:
            return

        lines: List[str] = []
        lines.append(f"Job ID: {job.get('id', '')}")
        lines.append(f"Script: {job.get('scriptName', job.get('taskName', ''))}")
        lines.append(f"Status: {job.get('status', '')}")
        lines.append(f"Started: {_format_dt(job.get('startedAt'))}")
        lines.append(f"Completed: {_format_dt(job.get('completedAt'))}")
        if job.get("error"):
            lines.append(f"\nERROR: {job['error']}")
        self._detail_text.setPlainText("\n".join(lines))


# ---------------------------------------------------------------------------
# Main Scheduler Tab
# ---------------------------------------------------------------------------


class SchedulerTab(QWidget):
    """Sixth application tab — schedule-based automation.

    Contains four panels accessible via a sidebar:
    1. Dashboard — pipelines + script schedules from the API.
    2. Pipeline Editor — 13-step pipeline CRUD.
    3. Schedule Editor — single-script schedule CRUD.
    4. Run History — recent jobs from the API.
    """

    def __init__(
        self,
        api_client: Optional[ApiClient] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._client = api_client or ApiClient()
        self._engine = ScheduleEngine(self._client, parent=self)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Sidebar ──────────────────────────────────────────────────
        sidebar_widget = QWidget()
        sidebar_widget.setFixedWidth(170)
        sidebar_widget.setStyleSheet(
            f"background-color: {COLOUR_SURFACE}; "
            f"border-right: 1px solid {COLOUR_BORDER};"
        )
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(0, 8, 0, 8)
        sidebar_layout.setSpacing(0)

        self._sidebar = QListWidget()
        self._sidebar.setStyleSheet(
            f"""
            QListWidget {{
                background-color: {COLOUR_SURFACE};
                border: none;
                font-size: 10pt;
            }}
            QListWidget::item {{
                padding: 10px 16px;
                border-radius: 0px;
            }}
            QListWidget::item:selected {{
                background-color: {COLOUR_SURFACE};
                color: {COLOUR_RED};
                border-left: 3px solid {COLOUR_RED};
                font-weight: bold;
            }}
            QListWidget::item:hover {{
                background-color: #E8E8E8;
            }}
            """
        )
        for name in _SIDEBAR_PANELS:
            self._sidebar.addItem(QListWidgetItem(name))

        self._sidebar.currentRowChanged.connect(self._on_sidebar_changed)
        sidebar_layout.addWidget(self._sidebar)

        # New Pipeline / New Schedule buttons
        new_pipeline_btn = QPushButton("+ New Pipeline")
        new_pipeline_btn.clicked.connect(self._on_new_pipeline)
        sidebar_layout.addWidget(new_pipeline_btn)

        new_schedule_btn = QPushButton("+ New Schedule")
        new_schedule_btn.clicked.connect(self._on_new_schedule)
        sidebar_layout.addWidget(new_schedule_btn)

        sidebar_layout.addStretch()
        outer.addWidget(sidebar_widget)

        # ── Stacked panels ───────────────────────────────────────────
        self._stack = QStackedWidget()
        outer.addWidget(self._stack, stretch=1)

        # Panel 0 — Dashboard
        self._dashboard = SchedulerDashboardPanel(self._engine, self._client)
        self._dashboard.edit_pipeline_requested.connect(self._on_edit_pipeline)
        self._dashboard.edit_schedule_requested.connect(self._on_edit_schedule)
        self._stack.addWidget(self._dashboard)

        # Panel 1 — Pipeline Editor
        self._pipeline_editor = PipelineEditorPanel(self._client)
        self._pipeline_editor.saved.connect(self._on_pipeline_saved)
        self._stack.addWidget(self._pipeline_editor)

        # Panel 2 — Schedule Editor
        self._schedule_editor = ScheduleEditorPanel(self._client)
        self._schedule_editor.saved.connect(self._on_schedule_saved)
        self._stack.addWidget(self._schedule_editor)

        # Panel 3 — Run History
        self._history = RunHistoryPanel(self._client)
        self._stack.addWidget(self._history)

        # Select Dashboard by default
        self._sidebar.setCurrentRow(0)

        # Defer engine start so the window can paint before the first network poll.
        QTimer.singleShot(500, self._engine.start)

    def closeEvent(self, event) -> None:
        """Stop the engine cleanly before the widget is destroyed."""
        self._engine.stop()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_sidebar_changed(self, index: int) -> None:
        """Switch the stacked widget to the panel matching *index*."""
        if index == 3:
            self._history.refresh()
        self._stack.setCurrentIndex(index)

    def _on_new_pipeline(self) -> None:
        """Open the pipeline editor in create mode."""
        self._pipeline_editor.clear()
        self._sidebar.setCurrentRow(1)

    def _on_new_schedule(self) -> None:
        """Open the schedule editor in create mode."""
        self._schedule_editor.clear()
        self._sidebar.setCurrentRow(2)

    def _on_edit_pipeline(self, data: Dict[str, Any]) -> None:
        """Open the pipeline editor with existing data."""
        self._pipeline_editor.load_pipeline(data)
        self._sidebar.setCurrentRow(1)

    def _on_edit_schedule(self, data: Dict[str, Any]) -> None:
        """Open the schedule editor with existing data."""
        self._schedule_editor.load_schedule(data)
        self._sidebar.setCurrentRow(2)

    def _on_pipeline_saved(self, result: str) -> None:
        """Handle pipeline editor save/cancel."""
        if result:
            self._engine._tick()
            self._dashboard.refresh()
        self._sidebar.setCurrentRow(0)

    def _on_schedule_saved(self, result: str) -> None:
        """Handle schedule editor save/cancel."""
        if result:
            self._engine._tick()
            self._dashboard.refresh()
        self._sidebar.setCurrentRow(0)
