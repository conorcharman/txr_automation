#!/usr/bin/env python3
"""
Scheduler Tab
=============

Sixth application tab — schedule-based automation for accuracy testing
reconciliation pipelines.

Panels (sidebar-driven):
1. Dashboard   — Table of all schedules, status indicators, quick actions.
2. Create Schedule — Form to create or edit a single schedule.
3. Run History — Filterable log of past pipeline executions.
4. Pipeline Builder — Guided explanation of presets and custom steps.

Follows the sidebar + QStackedWidget layout established by AccuracyTab.
All form fields persist across sessions via SettingsManager (scheduler.*).

Version 1.0 Changes:
- Initial implementation for Phase 2 GUI milestone
"""

from __future__ import annotations

import os
import subprocess
import uuid
from datetime import date, datetime
from typing import Optional

from PySide6.QtCore import Qt, QDate, QTime, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from gui.constants import (
    COLOUR_BORDER,
    COLOUR_GREY,
    COLOUR_RED,
    COLOUR_SURFACE,
    FISCAL_YEARS,
    LOG_LEVELS,
    QUARTERS,
)
from gui.scheduler import (
    FREQUENCY_PERIOD_DEFAULTS,
    PIPELINE_PRESETS,
    PeriodType,
    PipelinePreset,
    PipelineStep,
    RunRecord,
    RunStatus,
    ScheduleConfig,
    ScheduleEngine,
    ScheduleFrequency,
    SchedulePeriod,
    ScheduleStore,
    ValidationType,
)
from gui.utils.settings import settings
from gui.widgets import FilePickerWidget

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_COLOUR_SUCCESS = "#2E7D32"
_COLOUR_FAILED = _COLOUR_RED = COLOUR_RED
_COLOUR_GREY = COLOUR_GREY

_FREQUENCY_LABELS = {
    ScheduleFrequency.HOURLY: "Hourly",
    ScheduleFrequency.DAILY: "Daily",
    ScheduleFrequency.WEEKLY: "Weekly",
    ScheduleFrequency.MONTHLY: "Monthly",
    ScheduleFrequency.CUSTOM: "Custom cron",
}

_WEEKDAY_LABELS = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
]

_STATUS_COLOUR = {
    RunStatus.SUCCESS: _COLOUR_SUCCESS,
    RunStatus.FAILED: COLOUR_RED,
    RunStatus.RUNNING: "#F57C00",
    RunStatus.PENDING: COLOUR_GREY,
    RunStatus.CANCELLED: COLOUR_GREY,
}

_SIDEBAR_PANELS = [
    "Dashboard",
    "Create Schedule",
    "Run History",
    "Pipeline Builder",
]


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


def _status_dot(colour: str, text: str) -> QLabel:
    """Return a coloured text label used as an inline status indicator."""
    lbl = QLabel(f"● {text}")
    lbl.setStyleSheet(f"color: {colour}; font-size: 10pt;")
    return lbl


def _action_button(label: str, danger: bool = False) -> QPushButton:
    """Create a standard action button, optionally red-on-hover."""
    btn = QPushButton(label)
    btn.setFixedHeight(28)
    disabled_style = "QPushButton:disabled { color: #A0A0A0; background-color: #E8E8E8; border: 1px solid #C8C8C8; }"
    if danger:
        btn.setStyleSheet(
            f"QPushButton:hover {{ background-color: {COLOUR_RED}; color: white; }} {disabled_style}"
        )
    else:
        btn.setStyleSheet(disabled_style)
    return btn


def _bold_header_item(text: str) -> QTableWidgetItem:
    """Return a non-editable, bold QTableWidgetItem for table headers."""
    item = QTableWidgetItem(text)
    font = QFont()
    font.setBold(True)
    item.setFont(font)
    item.setFlags(Qt.ItemFlag.ItemIsEnabled)
    return item


def _table_item(text: str, colour: Optional[str] = None) -> QTableWidgetItem:
    """Return a non-editable QTableWidgetItem, optionally coloured."""
    from PySide6.QtGui import QBrush, QColor

    item = QTableWidgetItem(text)
    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    if colour:
        item.setForeground(QBrush(QColor(colour)))
    return item


def _format_dt(dt: Optional[datetime]) -> str:
    """Format a datetime to a compact string, or return '—' if None."""
    if dt is None:
        return "—"
    return dt.strftime("%Y-%m-%d %H:%M")


def _format_duration(start: Optional[datetime], end: Optional[datetime]) -> str:
    """Return a human-readable duration string."""
    if start is None or end is None:
        return "—"
    delta = end - start
    secs = int(delta.total_seconds())
    if secs < 60:
        return f"{secs}s"
    mins, secs = divmod(secs, 60)
    return f"{mins}m {secs}s"


# ---------------------------------------------------------------------------
# Panel 1 — Dashboard
# ---------------------------------------------------------------------------

class SchedulerDashboardPanel(QWidget):
    """Dashboard panel showing all schedules and their current status.

    Provides quick-action buttons (Enable/Disable, Run Now, Edit, Delete)
    and updates in real time when the engine emits lifecycle signals.

    Signals:
        edit_requested: Emitted with a ScheduleConfig when the user wants
            to edit a schedule.
    """

    edit_requested = Signal(object)  # ScheduleConfig

    _COL_NAME = 0
    _COL_STATUS = 1
    _COL_FREQUENCY = 2
    _COL_NEXT_RUN = 3
    _COL_LAST_RUN = 4
    _COL_LAST_STATUS = 5

    def __init__(
        self,
        store: ScheduleStore,
        engine: ScheduleEngine,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialise the dashboard panel.

        Args:
            store: Shared schedule store.
            engine: Shared schedule engine.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._store = store
        self._engine = engine
        self._selected_schedule_id: Optional[str] = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(8)

        # Header row
        header_row = QHBoxLayout()
        header_row.addWidget(_header_label("Scheduler Dashboard"))
        header_row.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedWidth(80)
        refresh_btn.clicked.connect(self.refresh)
        header_row.addWidget(refresh_btn)
        outer.addLayout(header_row)

        # Queue status bar
        self._status_label = QLabel("Queue: Idle")
        self._status_label.setStyleSheet(f"color: {COLOUR_GREY}; font-style: italic;")
        outer.addWidget(self._status_label)

        # Table
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels([
            "Name", "Status", "Frequency", "Next Run", "Last Run", "Last Status",
        ])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setStyleSheet(
            f"QTableWidget {{ border: 1px solid {COLOUR_BORDER}; "
            f"gridline-color: {COLOUR_BORDER}; }}"
            "QHeaderView::section { font-weight: bold; padding: 4px; }"
        )
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.doubleClicked.connect(self._on_double_click)
        outer.addWidget(self._table, stretch=1)

        # Action buttons row
        btn_row = QHBoxLayout()
        self._enable_btn = _action_button("Enable / Disable")
        self._enable_btn.clicked.connect(self._on_toggle_enable)
        btn_row.addWidget(self._enable_btn)

        self._run_now_btn = _action_button("Run Now")
        self._run_now_btn.clicked.connect(self._on_run_now)
        btn_row.addWidget(self._run_now_btn)

        self._edit_btn = _action_button("Edit")
        self._edit_btn.clicked.connect(self._on_edit)
        btn_row.addWidget(self._edit_btn)

        self._delete_btn = _action_button("Delete", danger=True)
        self._delete_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(self._delete_btn)

        btn_row.addStretch()
        outer.addLayout(btn_row)

        self._set_buttons_enabled(False)

        # Wire engine signals
        engine.pipeline_started.connect(self._on_pipeline_started)
        engine.pipeline_completed.connect(self._on_pipeline_completed)
        engine.pipeline_failed.connect(self._on_pipeline_failed)
        engine.schedule_updated.connect(lambda _: self.refresh())

        self.refresh()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Reload all schedules from the store and repopulate the table."""
        schedules = self._store.list_schedules()
        self._table.setRowCount(0)
        for config in schedules:
            self._append_row(config)
        self._table.resizeColumnsToContents()
        self._set_buttons_enabled(False)
        self._selected_schedule_id = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _append_row(self, config: ScheduleConfig) -> None:
        """Insert one schedule row at the bottom of the table."""
        row = self._table.rowCount()
        self._table.insertRow(row)

        self._table.setItem(row, self._COL_NAME, _table_item(config.name))

        if config.enabled:
            status_item = _table_item("Enabled", _COLOUR_SUCCESS)
        else:
            status_item = _table_item("Disabled", COLOUR_GREY)
        self._table.setItem(row, self._COL_STATUS, status_item)

        self._table.setItem(
            row, self._COL_FREQUENCY,
            _table_item(_FREQUENCY_LABELS.get(config.frequency, config.frequency.value)),
        )
        self._table.setItem(row, self._COL_NEXT_RUN, _table_item(_format_dt(config.next_run)))
        self._table.setItem(row, self._COL_LAST_RUN, _table_item(_format_dt(config.last_run)))

        # Last run status from history
        history = self._store.get_run_history(config.schedule_id, limit=1)
        if history:
            last = history[0]
            colour = _STATUS_COLOUR.get(last.status, COLOUR_GREY)
            last_status_item = _table_item(last.status.value.title(), colour)
        else:
            last_status_item = _table_item("Never run", COLOUR_GREY)
        self._table.setItem(row, self._COL_LAST_STATUS, last_status_item)

        # Store schedule_id in the name item for later retrieval
        name_item = self._table.item(row, self._COL_NAME)
        if name_item is not None:
            name_item.setData(Qt.ItemDataRole.UserRole, config.schedule_id)

    def _selected_id(self) -> Optional[str]:
        """Return the schedule_id for the currently selected row, or None."""
        rows = self._table.selectedItems()
        if not rows:
            return None
        name_item = self._table.item(self._table.currentRow(), self._COL_NAME)
        if name_item is None:
            return None
        return name_item.data(Qt.ItemDataRole.UserRole)

    def _set_buttons_enabled(self, enabled: bool) -> None:
        """Enable or disable action buttons based on selection state."""
        for btn in (self._enable_btn, self._run_now_btn, self._edit_btn, self._delete_btn):
            btn.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_selection_changed(self) -> None:
        """Enable action buttons when a row is selected."""
        self._set_buttons_enabled(bool(self._table.selectedItems()))

    def _on_double_click(self) -> None:
        """Open the edit panel when the user double-clicks a row."""
        self._on_edit()

    def _on_toggle_enable(self) -> None:
        """Toggle the enabled state of the selected schedule."""
        sid = self._selected_id()
        if sid is None:
            return
        config = self._store.load_schedule(sid)
        if config is None:
            return
        config.enabled = not config.enabled
        self._store.save_schedule(config)
        self.refresh()

    def _on_run_now(self) -> None:
        """Trigger immediate execution of the selected schedule."""
        sid = self._selected_id()
        if sid is None:
            return
        success = self._engine.trigger_now(sid)
        if not success:
            QMessageBox.warning(self, "Run Now", "Could not enqueue schedule — check it exists.")

    def _on_edit(self) -> None:
        """Emit edit_requested with the selected schedule's config."""
        sid = self._selected_id()
        if sid is None:
            return
        config = self._store.load_schedule(sid)
        if config is not None:
            self.edit_requested.emit(config)

    def _on_delete(self) -> None:
        """Delete the selected schedule after confirmation."""
        sid = self._selected_id()
        if sid is None:
            return
        config = self._store.load_schedule(sid)
        name = config.name if config else sid
        reply = QMessageBox.question(
            self,
            "Delete Schedule",
            f"Permanently delete schedule '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._store.delete_schedule(sid)
            self.refresh()

    # ------------------------------------------------------------------
    # Engine signal handlers
    # ------------------------------------------------------------------

    def _on_pipeline_started(self, schedule_id: str, schedule_name: str) -> None:
        """Update status bar to show running pipeline."""
        self._status_label.setText(f"Running: {schedule_name}")
        self._status_label.setStyleSheet(f"color: #F57C00; font-style: italic;")
        self._refresh_row(schedule_id)

    def _on_pipeline_completed(self, schedule_id: str, schedule_name: str, success: bool) -> None:
        """Restore status bar and refresh the relevant row."""
        queued = self._engine._queue  # type: ignore[attr-defined]
        n = len(queued)
        if n:
            self._status_label.setText(f"{n} queued")
            self._status_label.setStyleSheet(f"color: #F57C00; font-style: italic;")
        else:
            self._status_label.setText("Queue: Idle")
            self._status_label.setStyleSheet(f"color: {COLOUR_GREY}; font-style: italic;")
        self._refresh_row(schedule_id)

    def _on_pipeline_failed(self, schedule_id: str, schedule_name: str, error: str) -> None:
        """Refresh the relevant row on failure."""
        self._on_pipeline_completed(schedule_id, schedule_name, False)

    def _refresh_row(self, schedule_id: str) -> None:
        """Reload a single row from the store without rebuilding the whole table."""
        config = self._store.load_schedule(schedule_id)
        if config is None:
            return
        for row in range(self._table.rowCount()):
            item = self._table.item(row, self._COL_NAME)
            if item and item.data(Qt.ItemDataRole.UserRole) == schedule_id:
                self._table.removeRow(row)
                self._table.insertRow(row)
                self._table.setItem(row, self._COL_NAME, _table_item(config.name))
                item = self._table.item(row, self._COL_NAME)
                if item is not None:
                    item.setData(Qt.ItemDataRole.UserRole, schedule_id)
                if config.enabled:
                    self._table.setItem(row, self._COL_STATUS, _table_item("Enabled", _COLOUR_SUCCESS))
                else:
                    self._table.setItem(row, self._COL_STATUS, _table_item("Disabled", COLOUR_GREY))
                self._table.setItem(
                    row, self._COL_FREQUENCY,
                    _table_item(_FREQUENCY_LABELS.get(config.frequency, config.frequency.value)),
                )
                self._table.setItem(row, self._COL_NEXT_RUN, _table_item(_format_dt(config.next_run)))
                self._table.setItem(row, self._COL_LAST_RUN, _table_item(_format_dt(config.last_run)))
                history = self._store.get_run_history(schedule_id, limit=1)
                if history:
                    last = history[0]
                    colour = _STATUS_COLOUR.get(last.status, COLOUR_GREY)
                    self._table.setItem(row, self._COL_LAST_STATUS, _table_item(last.status.value.title(), colour))
                else:
                    self._table.setItem(row, self._COL_LAST_STATUS, _table_item("Never run", COLOUR_GREY))
                break


# ---------------------------------------------------------------------------
# Panel 2 — Schedule Editor
# ---------------------------------------------------------------------------

class ScheduleEditorPanel(QWidget):
    """Form for creating or editing a schedule configuration.

    Emits ``schedule_saved(schedule_id)`` on successful save, or
    ``schedule_saved("")`` when the user cancels.

    Args:
        store: Shared schedule store.
        parent: Optional parent widget.
    """

    schedule_saved = Signal(str)  # emits schedule_id, or "" on cancel

    _PRESET_CUSTOM_KEY = "__custom__"

    def __init__(
        self,
        store: ScheduleStore,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialise the schedule editor panel."""
        super().__init__(parent)
        self._store = store
        self._editing_id: Optional[str] = None

        inner = QWidget()
        form_layout = QVBoxLayout(inner)
        form_layout.setContentsMargins(16, 16, 16, 16)
        form_layout.setSpacing(8)

        form_layout.addWidget(_header_label("Create / Edit Schedule"))

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # --- Name ---
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. Daily Buyer Validation")
        form.addRow("Name:", self._name_edit)

        # --- Enabled ---
        self._enabled_cb = QCheckBox("Active")
        self._enabled_cb.setChecked(True)
        form.addRow("Enabled:", self._enabled_cb)

        # --- Frequency ---
        self._freq_combo = QComboBox()
        for freq, label in _FREQUENCY_LABELS.items():
            self._freq_combo.addItem(label, freq)
        self._freq_combo.currentIndexChanged.connect(self._on_frequency_changed)
        form.addRow("Frequency:", self._freq_combo)

        # --- Time of day ---
        self._time_edit = QTimeEdit()
        self._time_edit.setDisplayFormat("HH:mm")
        self._time_edit.setTime(QTime(9, 0))
        self._time_row_label = QLabel("Time of day:")
        form.addRow(self._time_row_label, self._time_edit)

        # --- Day of week ---
        self._dow_combo = QComboBox()
        for day in _WEEKDAY_LABELS:
            self._dow_combo.addItem(day)
        self._dow_row_label = QLabel("Day of week:")
        form.addRow(self._dow_row_label, self._dow_combo)

        # --- Day of month ---
        self._dom_spin = QSpinBox()
        self._dom_spin.setRange(1, 28)
        self._dom_spin.setValue(1)
        self._dom_row_label = QLabel("Day of month:")
        form.addRow(self._dom_row_label, self._dom_spin)

        # --- Custom cron ---
        self._cron_edit = QLineEdit()
        self._cron_edit.setPlaceholderText("e.g. 0 9 * * 1")
        self._cron_row_label = QLabel("Cron expression:")
        form.addRow(self._cron_row_label, self._cron_edit)

        form_layout.addLayout(form)

        # --- Pipeline preset ---
        preset_group = QGroupBox("Pipeline Preset")
        preset_v = QVBoxLayout(preset_group)

        self._preset_combo = QComboBox()
        for preset in PIPELINE_PRESETS:
            self._preset_combo.addItem(preset.display_name, preset.key)
        self._preset_combo.addItem("Custom", self._PRESET_CUSTOM_KEY)
        self._preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        preset_v.addWidget(self._preset_combo)

        self._preset_desc = QLabel("")
        self._preset_desc.setStyleSheet(f"color: {COLOUR_GREY}; font-style: italic;")
        self._preset_desc.setWordWrap(True)
        preset_v.addWidget(self._preset_desc)

        form_layout.addWidget(preset_group)

        # --- Validation types ---
        self._vt_group = QGroupBox("Validation Types")
        vt_v = QVBoxLayout(self._vt_group)
        self._vt_checkboxes: dict[ValidationType, QCheckBox] = {}
        for vt in ValidationType:
            cb = QCheckBox(vt.display_name)
            self._vt_checkboxes[vt] = cb
            vt_v.addWidget(cb)
        form_layout.addWidget(self._vt_group)

        # --- Pipeline steps (custom only) ---
        self._steps_group = QGroupBox("Pipeline Steps (Custom)")
        steps_v = QVBoxLayout(self._steps_group)
        self._step_checkboxes: dict[PipelineStep, QCheckBox] = {}
        step_descriptions = {
            PipelineStep.EXTRACT: "Extract — pull data from source systems",
            PipelineStep.COLLATE: "Collate — merge and de-duplicate records",
            PipelineStep.VALIDATE: "Validate — run accuracy validation scripts",
            PipelineStep.PUSH: "Push — upload results to target location",
        }
        for step in PipelineStep:
            cb = QCheckBox(step_descriptions.get(step, step.value.title()))
            cb.setChecked(True)
            self._step_checkboxes[step] = cb
            steps_v.addWidget(cb)
        form_layout.addWidget(self._steps_group)

        # --- Data extraction period ---
        period_group = QGroupBox("Data Extraction Period")
        period_outer = QVBoxLayout(period_group)

        # Period type radio buttons
        period_type_row = QHBoxLayout()
        self._period_btn_group = QButtonGroup(self)
        self._rb_fiscal = QRadioButton("Fiscal Quarter")
        self._rb_relative = QRadioButton("Relative (last N days)")
        self._rb_date_range = QRadioButton("Date Range")
        for rb in (self._rb_fiscal, self._rb_relative, self._rb_date_range):
            self._period_btn_group.addButton(rb)
            period_type_row.addWidget(rb)
        period_type_row.addStretch()
        self._rb_fiscal.setChecked(True)
        period_outer.addLayout(period_type_row)

        # Fiscal quarter row (visible when rb_fiscal checked)
        self._fiscal_row = QWidget()
        fq_h = QHBoxLayout(self._fiscal_row)
        fq_h.setContentsMargins(0, 0, 0, 0)
        fq_h.addWidget(QLabel("Fiscal Year:"))
        self._fy_combo = QComboBox()
        for fy in FISCAL_YEARS:
            self._fy_combo.addItem(fy)
        fq_h.addWidget(self._fy_combo)
        fq_h.addWidget(QLabel("Quarter:"))
        self._q_combo = QComboBox()
        for q in QUARTERS:
            self._q_combo.addItem(q)
        fq_h.addWidget(self._q_combo)
        fq_h.addStretch()
        period_outer.addWidget(self._fiscal_row)

        # Relative row (visible when rb_relative checked)
        self._relative_row = QWidget()
        rel_h = QHBoxLayout(self._relative_row)
        rel_h.setContentsMargins(0, 0, 0, 0)
        rel_h.addWidget(QLabel("Last"))
        self._relative_spin = QSpinBox()
        self._relative_spin.setRange(1, 365)
        self._relative_spin.setValue(1)
        self._relative_spin.setSuffix(" day(s)")
        self._relative_spin.setFixedWidth(110)
        rel_h.addWidget(self._relative_spin)
        self._relative_hint = QLabel("")
        self._relative_hint.setStyleSheet(f"color: {COLOUR_GREY}; font-style: italic;")
        rel_h.addWidget(self._relative_hint)
        rel_h.addStretch()
        self._relative_row.hide()
        period_outer.addWidget(self._relative_row)

        # Date range row (visible when rb_date_range checked)
        self._date_range_row = QWidget()
        dr_h = QHBoxLayout(self._date_range_row)
        dr_h.setContentsMargins(0, 0, 0, 0)
        dr_h.addWidget(QLabel("From:"))
        self._date_start_edit = QDateEdit()
        self._date_start_edit.setCalendarPopup(True)
        self._date_start_edit.setDisplayFormat("dd/MM/yyyy")
        self._date_start_edit.setDate(QDate.currentDate().addDays(-30))
        dr_h.addWidget(self._date_start_edit)
        dr_h.addWidget(QLabel("To:"))
        self._date_end_edit = QDateEdit()
        self._date_end_edit.setCalendarPopup(True)
        self._date_end_edit.setDisplayFormat("dd/MM/yyyy")
        self._date_end_edit.setDate(QDate.currentDate().addDays(-1))
        dr_h.addWidget(self._date_end_edit)
        dr_h.addStretch()
        self._date_range_row.hide()
        period_outer.addWidget(self._date_range_row)

        # Wire radio buttons → show/hide sub-rows
        self._rb_fiscal.toggled.connect(lambda on: self._fiscal_row.setVisible(on))
        self._rb_relative.toggled.connect(lambda on: self._relative_row.setVisible(on))
        self._rb_relative.toggled.connect(self._update_relative_hint)
        self._rb_date_range.toggled.connect(lambda on: self._date_range_row.setVisible(on))
        self._relative_spin.valueChanged.connect(self._update_relative_hint)

        form_layout.addWidget(period_group)

        # --- Input directory (optional) ---
        self._input_picker = FilePickerWidget(
            "Input directory (optional):",
            mode="directory",
            placeholder="Leave blank to use default discovery",
            settings_key="scheduler.editor.input_dir",
        )
        form_layout.addWidget(self._input_picker)

        # --- Output directory (required) ---
        self._output_picker = FilePickerWidget(
            "Output directory:",
            mode="directory",
            placeholder="Required — select output folder",
            settings_key="scheduler.editor.output_dir",
        )
        form_layout.addWidget(self._output_picker)

        # --- Log level ---
        log_row = QHBoxLayout()
        log_row.addWidget(QLabel("Log level:"))
        self._log_combo = QComboBox()
        for level in LOG_LEVELS:
            self._log_combo.addItem(level)
        self._log_combo.setCurrentText(
            settings.load("scheduler.editor.log_level", "INFO")
        )
        self._log_combo.currentTextChanged.connect(
            lambda v: settings.save("scheduler.editor.log_level", v)
        )
        log_row.addWidget(self._log_combo)
        log_row.addStretch()
        form_layout.addLayout(log_row)

        form_layout.addStretch()

        # --- Action buttons ---
        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setProperty("primary", True)
        save_btn.setFixedWidth(100)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        save_run_btn = QPushButton("Save && Run Now")
        save_run_btn.setFixedWidth(130)
        save_run_btn.clicked.connect(self._on_save_and_run)
        btn_row.addWidget(save_run_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(80)
        cancel_btn.clicked.connect(lambda: self.schedule_saved.emit(""))
        btn_row.addWidget(cancel_btn)

        btn_row.addStretch()
        form_layout.addLayout(btn_row)

        # Wrap in scroll area
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(_scrollable(inner))

        # Initial visibility state
        self._on_frequency_changed()
        self._on_preset_changed()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_schedule(self, config: ScheduleConfig) -> None:
        """Populate all form fields from an existing ScheduleConfig.

        Args:
            config: Schedule to load for editing.
        """
        self._editing_id = config.schedule_id
        self._name_edit.setText(config.name)
        self._enabled_cb.setChecked(config.enabled)

        # Frequency
        idx = self._freq_combo.findData(config.frequency)
        if idx >= 0:
            self._freq_combo.setCurrentIndex(idx)

        # Time
        h, m = map(int, config.time_of_day.split(":"))
        self._time_edit.setTime(QTime(h, m))

        # Day of week / month / cron
        self._dow_combo.setCurrentIndex(config.day_of_week)
        self._dom_spin.setValue(config.day_of_month)
        self._cron_edit.setText(config.cron_expression)

        # Validation types
        for vt, cb in self._vt_checkboxes.items():
            cb.setChecked(vt in config.validation_types)

        # Pipeline steps
        for step, cb in self._step_checkboxes.items():
            cb.setChecked(step in config.pipeline_steps)

        # Preset: try to find matching preset by comparing validation types and steps
        matched_preset = False
        for preset in PIPELINE_PRESETS:
            if (set(preset.validation_types) == set(config.validation_types)
                    and set(preset.pipeline_steps) == set(config.pipeline_steps)):
                idx = self._preset_combo.findData(preset.key)
                if idx >= 0:
                    self._preset_combo.setCurrentIndex(idx)
                    matched_preset = True
                    break
        if not matched_preset:
            idx = self._preset_combo.findData(self._PRESET_CUSTOM_KEY)
            if idx >= 0:
                self._preset_combo.setCurrentIndex(idx)

        # Data extraction period
        sp = config.schedule_period
        if sp.period_type == PeriodType.FISCAL_QUARTER:
            self._rb_fiscal.setChecked(True)
            fy_idx = self._fy_combo.findText(sp.fiscal_year)
            if fy_idx >= 0:
                self._fy_combo.setCurrentIndex(fy_idx)
            q_idx = self._q_combo.findText(sp.quarter)
            if q_idx >= 0:
                self._q_combo.setCurrentIndex(q_idx)
        elif sp.period_type == PeriodType.RELATIVE:
            self._rb_relative.setChecked(True)
            self._relative_spin.setValue(sp.relative_days)
        else:
            self._rb_date_range.setChecked(True)
            if sp.date_range_start:
                d = sp.date_range_start
                self._date_start_edit.setDate(QDate(d.year, d.month, d.day))
            if sp.date_range_end:
                d = sp.date_range_end
                self._date_end_edit.setDate(QDate(d.year, d.month, d.day))

        # Directories
        self._input_picker.set_path(config.input_directory)
        self._output_picker.set_path(config.output_directory)

        # Log level
        ll_idx = self._log_combo.findText(config.log_level)
        if ll_idx >= 0:
            self._log_combo.setCurrentIndex(ll_idx)

    def clear(self) -> None:
        """Reset all fields to defaults for creating a new schedule."""
        self._editing_id = None
        self._name_edit.clear()
        self._enabled_cb.setChecked(True)
        self._freq_combo.setCurrentIndex(
            self._freq_combo.findData(ScheduleFrequency.DAILY)
        )
        self._time_edit.setTime(QTime(9, 0))
        self._dow_combo.setCurrentIndex(0)
        self._dom_spin.setValue(1)
        self._cron_edit.clear()
        for cb in self._vt_checkboxes.values():
            cb.setChecked(False)
        for cb in self._step_checkboxes.values():
            cb.setChecked(True)
        if self._preset_combo.count():
            self._preset_combo.setCurrentIndex(0)
        self._rb_fiscal.setChecked(True)
        if self._fy_combo.count():
            self._fy_combo.setCurrentIndex(0)
        if self._q_combo.count():
            self._q_combo.setCurrentIndex(0)
        self._relative_spin.setValue(1)
        self._date_start_edit.setDate(QDate.currentDate().addDays(-30))
        self._date_end_edit.setDate(QDate.currentDate().addDays(-1))
        self._input_picker.set_path("")
        self._output_picker.set_path("")
        self._log_combo.setCurrentText("INFO")

    def apply_preset_key(self, preset_key: str) -> None:
        """Pre-select a preset by key (called from Pipeline Builder).

        Args:
            preset_key: The ``PipelinePreset.key`` to select.
        """
        idx = self._preset_combo.findData(preset_key)
        if idx >= 0:
            self._preset_combo.setCurrentIndex(idx)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _current_frequency(self) -> ScheduleFrequency:
        """Return the currently selected ScheduleFrequency."""
        return self._freq_combo.currentData()

    def _build_config(self) -> Optional[ScheduleConfig]:
        """Build and return a ScheduleConfig from form values, or None on validation failure."""
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Schedule name is required.")
            return None

        output_dir = self._output_picker.get_path()
        if not output_dir:
            QMessageBox.warning(self, "Validation", "Output directory is required.")
            return None

        freq = self._current_frequency()
        time_str = self._time_edit.time().toString("HH:mm")
        dow = self._dow_combo.currentIndex()
        dom = self._dom_spin.value()
        cron = self._cron_edit.text().strip()

        validation_types = [
            vt for vt, cb in self._vt_checkboxes.items() if cb.isChecked()
        ]
        pipeline_steps = [
            step for step in PipelineStep
            if self._step_checkboxes[step].isChecked()
        ]

        if self._rb_fiscal.isChecked():
            schedule_period = SchedulePeriod(
                period_type=PeriodType.FISCAL_QUARTER,
                fiscal_year=self._fy_combo.currentText(),
                quarter=self._q_combo.currentText(),
            )
        elif self._rb_relative.isChecked():
            schedule_period = SchedulePeriod(
                period_type=PeriodType.RELATIVE,
                relative_days=self._relative_spin.value(),
            )
        else:
            qds = self._date_start_edit.date()
            qde = self._date_end_edit.date()
            schedule_period = SchedulePeriod(
                period_type=PeriodType.DATE_RANGE,
                date_range_start=date(qds.year(), qds.month(), qds.day()),
                date_range_end=date(qde.year(), qde.month(), qde.day()),
            )

        sched_id = self._editing_id or str(uuid.uuid4())

        return ScheduleConfig(
            schedule_id=sched_id,
            name=name,
            enabled=self._enabled_cb.isChecked(),
            frequency=freq,
            time_of_day=time_str,
            day_of_week=dow,
            day_of_month=dom,
            cron_expression=cron,
            validation_types=validation_types,
            pipeline_steps=pipeline_steps,
            schedule_period=schedule_period,
            input_directory=self._input_picker.get_path(),
            output_directory=output_dir,
            log_level=self._log_combo.currentText(),
            created_at=datetime.now() if self._editing_id is None else None,
        )

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_frequency_changed(self) -> None:
        """Show/hide time and day fields based on selected frequency."""
        freq = self._current_frequency()
        is_daily_plus = freq in (
            ScheduleFrequency.DAILY,
            ScheduleFrequency.WEEKLY,
            ScheduleFrequency.MONTHLY,
        )
        is_weekly = freq == ScheduleFrequency.WEEKLY
        is_monthly = freq == ScheduleFrequency.MONTHLY
        is_custom = freq == ScheduleFrequency.CUSTOM

        self._time_row_label.setVisible(is_daily_plus)
        self._time_edit.setVisible(is_daily_plus)
        self._dow_row_label.setVisible(is_weekly)
        self._dow_combo.setVisible(is_weekly)
        self._dom_row_label.setVisible(is_monthly)
        self._dom_spin.setVisible(is_monthly)
        self._cron_row_label.setVisible(is_custom)
        self._cron_edit.setVisible(is_custom)

        # Auto-suggest period type based on frequency
        suggested_type, suggested_days = FREQUENCY_PERIOD_DEFAULTS.get(
            freq.value, (PeriodType.FISCAL_QUARTER, 0)
        )
        if suggested_type == PeriodType.RELATIVE:
            self._rb_relative.setChecked(True)
            self._relative_spin.setValue(suggested_days)
        elif suggested_type == PeriodType.DATE_RANGE:
            self._rb_date_range.setChecked(True)
        else:
            self._rb_fiscal.setChecked(True)

    def _on_preset_changed(self) -> None:
        """Apply preset selection — update validation type and step checkboxes."""
        key = self._preset_combo.currentData()
        is_custom = key == self._PRESET_CUSTOM_KEY
        self._steps_group.setVisible(is_custom)

        if not is_custom:
            preset: Optional[PipelinePreset] = next(
                (p for p in PIPELINE_PRESETS if p.key == key), None
            )
            if preset is not None:
                # Apply preset validation types
                for vt, cb in self._vt_checkboxes.items():
                    cb.setChecked(vt in preset.validation_types)
                # Apply preset pipeline steps  
                for step, cb in self._step_checkboxes.items():
                    cb.setChecked(step in preset.pipeline_steps)
                self._preset_desc.setText(preset.description)
            else:
                self._preset_desc.setText("")
        else:
            self._preset_desc.setText("Manually choose validation types and pipeline steps below.")

    def _on_save(self) -> None:
        """Validate form and save schedule to store."""
        config = self._build_config()
        if config is None:
            return
        settings.save(
            "scheduler.editor.period_type",
            config.schedule_period.period_type.value,
        )
        settings.save(
            "scheduler.editor.relative_days",
            config.schedule_period.relative_days,
        )
        self._store.save_schedule(config)
        self.schedule_saved.emit(config.schedule_id)

    def _on_save_and_run(self) -> None:
        """Save the schedule, then emit with a special marker for the parent."""
        config = self._build_config()
        if config is None:
            return
        settings.save(
            "scheduler.editor.period_type",
            config.schedule_period.period_type.value,
        )
        settings.save(
            "scheduler.editor.relative_days",
            config.schedule_period.relative_days,
        )
        self._store.save_schedule(config)
        # Emit special marker so SchedulerTab knows to trigger_now
        self.schedule_saved.emit(f"run:{config.schedule_id}")

    def _update_relative_hint(self) -> None:
        """Update the label next to the relative days spinbox."""
        if not self._rb_relative.isChecked():
            self._relative_hint.setText("")
            return
        days = self._relative_spin.value()
        if days == 1:
            self._relative_hint.setText("(yesterday only)")
        else:
            self._relative_hint.setText(f"(the {days} calendar days up to and including yesterday)")


# ---------------------------------------------------------------------------
# Panel 3 — Run History
# ---------------------------------------------------------------------------

class RunHistoryPanel(QWidget):
    """Filterable log of past pipeline executions.

    Args:
        store: Shared schedule store.
        parent: Optional parent widget.
    """

    _COL_SCHEDULE = 0
    _COL_STARTED = 1
    _COL_DURATION = 2
    _COL_STATUS = 3
    _COL_STEPS = 4
    _COL_OUTPUT = 5

    def __init__(
        self,
        store: ScheduleStore,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialise the run history panel."""
        super().__init__(parent)
        self._store = store
        self._all_records: list[RunRecord] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(8)

        outer.addWidget(_header_label("Run History"))

        # Filter row
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Schedule:"))
        self._schedule_filter = QComboBox()
        self._schedule_filter.addItem("All Schedules", None)
        self._schedule_filter.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self._schedule_filter)

        filter_row.addWidget(QLabel("Status:"))
        self._status_filter = QComboBox()
        self._status_filter.addItem("All Statuses", None)
        for status in RunStatus:
            self._status_filter.addItem(status.value.title(), status)
        self._status_filter.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self._status_filter)

        filter_row.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedWidth(80)
        refresh_btn.clicked.connect(self.refresh)
        filter_row.addWidget(refresh_btn)

        outer.addLayout(filter_row)

        # Table + detail splitter
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Main table
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels([
            "Schedule", "Started", "Duration", "Status", "Steps", "Output Files",
        ])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setStyleSheet(
            f"QTableWidget {{ border: 1px solid {COLOUR_BORDER}; "
            f"gridline-color: {COLOUR_BORDER}; }}"
            "QHeaderView::section { font-weight: bold; padding: 4px; }"
        )
        self._table.itemSelectionChanged.connect(self._on_row_selected)
        splitter.addWidget(self._table)

        # Detail pane
        detail_widget = QWidget()
        detail_v = QVBoxLayout(detail_widget)
        detail_v.setContentsMargins(0, 4, 0, 0)
        detail_v.setSpacing(4)

        detail_label = QLabel("Step output:")
        detail_label.setStyleSheet("font-weight: bold;")
        detail_v.addWidget(detail_label)

        self._detail_text = QTextEdit()
        self._detail_text.setReadOnly(True)
        self._detail_text.setStyleSheet(
            f"background: {COLOUR_SURFACE}; font-family: Consolas, monospace; font-size: 9pt;"
        )
        detail_v.addWidget(self._detail_text, stretch=1)

        self._open_dir_btn = QPushButton("Open Output Directory")
        self._open_dir_btn.setEnabled(False)
        self._open_dir_btn.clicked.connect(self._on_open_output_dir)
        detail_v.addWidget(self._open_dir_btn)

        splitter.addWidget(detail_widget)
        splitter.setSizes([300, 150])
        outer.addWidget(splitter, stretch=1)

        self.refresh()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Reload run history from the store."""
        self._all_records = self._store.get_all_run_history(limit=200)

        # Rebuild schedule filter items (preserving current selection)
        current_sid = self._schedule_filter.currentData()
        self._schedule_filter.blockSignals(True)
        self._schedule_filter.clear()
        self._schedule_filter.addItem("All Schedules", None)
        seen: set[str] = set()
        for rec in self._all_records:
            if rec.schedule_id not in seen:
                self._schedule_filter.addItem(rec.schedule_name, rec.schedule_id)
                seen.add(rec.schedule_id)
        idx = self._schedule_filter.findData(current_sid)
        if idx >= 0:
            self._schedule_filter.setCurrentIndex(idx)
        self._schedule_filter.blockSignals(False)

        self._apply_filters()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _apply_filters(self) -> None:
        """Filter and repopulate the table based on current filter settings."""
        filter_sid = self._schedule_filter.currentData()
        filter_status = self._status_filter.currentData()

        records = self._all_records
        if filter_sid is not None:
            records = [r for r in records if r.schedule_id == filter_sid]
        if filter_status is not None:
            records = [r for r in records if r.status == filter_status]

        self._table.setRowCount(0)
        for rec in records:
            row = self._table.rowCount()
            self._table.insertRow(row)

            self._table.setItem(row, self._COL_SCHEDULE, _table_item(rec.schedule_name))
            self._table.setItem(row, self._COL_STARTED, _table_item(_format_dt(rec.started_at)))
            self._table.setItem(
                row, self._COL_DURATION,
                _table_item(_format_duration(rec.started_at, rec.completed_at)),
            )
            colour = _STATUS_COLOUR.get(rec.status, COLOUR_GREY)
            self._table.setItem(row, self._COL_STATUS, _table_item(rec.status.value.title(), colour))
            steps_str = ", ".join(sr.step.value for sr in rec.step_results)
            self._table.setItem(row, self._COL_STEPS, _table_item(steps_str or "—"))
            self._table.setItem(
                row, self._COL_OUTPUT,
                _table_item(str(len(rec.output_files))),
            )

            # Store full record in first item
            sched_item = self._table.item(row, self._COL_SCHEDULE)
            if sched_item is not None:
                sched_item.setData(Qt.ItemDataRole.UserRole, rec)

        self._table.resizeColumnsToContents()
        self._detail_text.clear()
        self._open_dir_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_row_selected(self) -> None:
        """Show step stdout/stderr for the selected run in the detail pane."""
        rows = self._table.selectedItems()
        if not rows:
            self._detail_text.clear()
            self._open_dir_btn.setEnabled(False)
            return

        item = self._table.item(self._table.currentRow(), self._COL_SCHEDULE)
        if item is None:
            return
        rec: RunRecord = item.data(Qt.ItemDataRole.UserRole)
        if rec is None:
            return

        lines: list[str] = []
        if rec.error_message:
            lines.append(f"ERROR: {rec.error_message}\n")
        for sr in rec.step_results:
            lines.append(f"=== {sr.step.value.upper()} ({sr.status.value}) ===")
            if sr.stdout:
                lines.append(sr.stdout)
            if sr.stderr:
                lines.append(f"[stderr]\n{sr.stderr}")
            lines.append("")
        self._detail_text.setPlainText("\n".join(lines))

        # Enable open-dir button if any output files exist
        if rec.output_files:
            self._open_dir_btn.setEnabled(True)
            self._open_dir_btn.setProperty("_output_files", rec.output_files)
        else:
            self._open_dir_btn.setEnabled(False)

    def _on_open_output_dir(self) -> None:
        """Open Windows Explorer at the directory of the first output file."""
        files = self._open_dir_btn.property("_output_files")
        if not files:
            return
        first_file = files[0]
        directory = os.path.dirname(first_file)
        if not directory or not os.path.isdir(directory):
            directory = first_file if os.path.isdir(first_file) else os.getcwd()
        try:
            subprocess.Popen(["explorer", directory])  # noqa: S603, S607
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Panel 4 — Pipeline Builder
# ---------------------------------------------------------------------------

class PipelineBuilderPanel(QWidget):
    """Educational panel explaining presets and custom pipeline steps.

    Allows the user to select a preset and jump straight to the editor
    with it pre-selected.

    Signals:
        use_preset_requested: Emitted with the preset key when the user
            clicks "Use Preset".
    """

    use_preset_requested = Signal(str)  # preset key

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialise the pipeline builder panel."""
        super().__init__(parent)

        inner = QWidget()
        outer = QVBoxLayout(inner)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        outer.addWidget(_header_label("Pipeline Builder"))

        intro = QLabel(
            "Use a <b>preset</b> for common validation workflows, or build a "
            "<b>custom</b> pipeline by selecting individual steps and validation types "
            "in the Schedule Editor."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("margin-bottom: 8px;")
        outer.addWidget(intro)

        # Presets group
        presets_group = QGroupBox("Available Presets")
        presets_v = QVBoxLayout(presets_group)

        self._preset_list = QListWidget()
        self._preset_list.setAlternatingRowColors(True)
        self._preset_list.setMinimumHeight(120)
        self._preset_list.setStyleSheet(
            f"QListWidget {{ border: 1px solid {COLOUR_BORDER}; }}"
        )
        for preset in PIPELINE_PRESETS:
            item = QListWidgetItem(
                f"{preset.display_name}  —  {preset.description}"
            )
            item.setData(Qt.ItemDataRole.UserRole, preset.key)
            self._preset_list.addItem(item)
        presets_v.addWidget(self._preset_list)

        use_btn = QPushButton("Use Preset in Editor")
        use_btn.setFixedWidth(160)
        use_btn.setProperty("primary", True)
        use_btn.clicked.connect(self._on_use_preset)
        presets_v.addWidget(use_btn)

        outer.addWidget(presets_group)

        # Custom pipeline steps group
        custom_group = QGroupBox("Custom Pipeline Steps")
        custom_v = QVBoxLayout(custom_group)

        flow_label = QLabel(
            "<b>Step order:</b>  EXTRACT → COLLATE → VALIDATE → PUSH"
        )
        flow_label.setStyleSheet("font-size: 11pt; margin-bottom: 8px;")
        custom_v.addWidget(flow_label)

        step_info = [
            (
                PipelineStep.EXTRACT,
                "Pulls source data from configured input directories or APIs. "
                "Produces raw CSV files for the Collate step.",
            ),
            (
                PipelineStep.COLLATE,
                "Merges and de-duplicates records from multiple sources. "
                "Handles field renaming, date normalisation, and encoding cleanup.",
            ),
            (
                PipelineStep.VALIDATE,
                "Runs the configured accuracy validation scripts "
                "(buyer, seller, FTBDM, FTSDM, etc.) and writes annotated output CSVs.",
            ),
            (
                PipelineStep.PUSH,
                "Uploads validated output files to the target location "
                "(shared drive, SharePoint, or a reporting database).",
            ),
        ]

        for step, desc in step_info:
            step_box = QGroupBox(step.value.upper())
            step_box.setCheckable(False)
            step_layout = QVBoxLayout(step_box)
            step_lbl = QLabel(desc)
            step_lbl.setWordWrap(True)
            step_lbl.setStyleSheet(f"color: {COLOUR_GREY};")
            step_layout.addWidget(step_lbl)
            custom_v.addWidget(step_box)

        outer.addWidget(custom_group)
        outer.addStretch()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(_scrollable(inner))

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_use_preset(self) -> None:
        """Emit use_preset_requested with the selected preset's key."""
        item = self._preset_list.currentItem()
        if item is None:
            QMessageBox.information(
                self, "Use Preset", "Please select a preset from the list first."
            )
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        self.use_preset_requested.emit(key)


# ---------------------------------------------------------------------------
# Main Scheduler Tab
# ---------------------------------------------------------------------------

class SchedulerTab(QWidget):
    """Sixth application tab — schedule-based automation.

    Contains four panels accessible via a sidebar:
    1. Dashboard — overview of all schedules and their status.
    2. Create Schedule — editor for creating / modifying schedules.
    3. Run History — log of past pipeline executions.
    4. Pipeline Builder — guided preset / custom pipeline selector.

    The ScheduleEngine is started on construction and stopped on close.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialise the Scheduler tab, engine, and all panels."""
        super().__init__(parent)

        self._store = ScheduleStore()
        self._engine = ScheduleEngine(self._store, parent=self)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Sidebar ──────────────────────────────────────────────────────
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
            item = QListWidgetItem(name)
            self._sidebar.addItem(item)

        self._sidebar.currentRowChanged.connect(self._on_sidebar_changed)
        sidebar_layout.addWidget(self._sidebar)
        sidebar_layout.addStretch()

        outer.addWidget(sidebar_widget)

        # ── Stacked panels ───────────────────────────────────────────────
        self._stack = QStackedWidget()
        outer.addWidget(self._stack, stretch=1)

        # Panel 0 — Dashboard
        self._dashboard = SchedulerDashboardPanel(self._store, self._engine)
        self._dashboard.edit_requested.connect(self._open_editor_with)
        self._stack.addWidget(self._dashboard)

        # Panel 1 — Editor
        self._editor = ScheduleEditorPanel(self._store)
        self._editor.schedule_saved.connect(self._on_schedule_saved)
        self._stack.addWidget(self._editor)

        # Panel 2 — Run History
        self._history = RunHistoryPanel(self._store)
        self._stack.addWidget(self._history)

        # Panel 3 — Pipeline Builder
        self._pipeline_builder = PipelineBuilderPanel()
        self._pipeline_builder.use_preset_requested.connect(self._on_use_preset)
        self._stack.addWidget(self._pipeline_builder)

        # Wire engine signals to history refresh
        self._engine.pipeline_completed.connect(lambda *_: self._history.refresh())
        self._engine.pipeline_failed.connect(lambda *_: self._history.refresh())

        # Select Dashboard by default
        self._sidebar.setCurrentRow(0)

        self._engine.start()

    def closeEvent(self, event) -> None:
        """Stop the engine cleanly before the widget is destroyed."""
        self._engine.stop()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_sidebar_changed(self, index: int) -> None:
        """Switch the stacked widget to the panel matching *index*."""
        if index == 2:
            self._history.refresh()
        self._stack.setCurrentIndex(index)

    def _open_editor_with(self, config: ScheduleConfig) -> None:
        """Open the editor pre-filled with *config* for editing."""
        self._editor.load_schedule(config)
        self._sidebar.setCurrentRow(1)

    def _on_schedule_saved(self, result: str) -> None:
        """Handle save / cancel from the editor panel.

        If *result* starts with ``"run:"`` the schedule is also triggered
        immediately.  An empty *result* means Cancel was clicked.

        Args:
            result: ``schedule_id``, ``"run:<schedule_id>"``, or ``""`` for cancel.
        """
        if result.startswith("run:"):
            schedule_id = result[4:]
            self._engine.trigger_now(schedule_id)
            self._dashboard.refresh()
            self._sidebar.setCurrentRow(0)
        elif result:
            self._dashboard.refresh()
            self._sidebar.setCurrentRow(0)
        else:
            # Cancel — return to Dashboard without saving
            self._sidebar.setCurrentRow(0)

    def _on_use_preset(self, preset_key: str) -> None:
        """Navigate to the editor with the given preset pre-selected."""
        self._editor.clear()
        self._editor.apply_preset_key(preset_key)
        self._sidebar.setCurrentRow(1)
