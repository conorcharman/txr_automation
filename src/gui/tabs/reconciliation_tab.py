#!/usr/bin/env python3
"""
Reconciliation Tab
==================

Seventh application tab — schedule-based reconciliation automation.

Panels (sidebar-driven):
1. **Schedules** — Table of reconciliation schedules with actions (Trigger,
   Enable/Disable, Edit, Delete).
2. **Editor** — Create/edit a reconciliation schedule with script selection,
   frequency, testing period, and stop-on-error.
3. **Run History** — Recent reconciliation jobs fetched from ``GET /api/jobs``.

All data comes from the API. No local state is maintained.

Version 1.0 Changes:
- Initial implementation for Phase 6 integration
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
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
    QSpinBox,
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
    SCHEDULE_FREQUENCIES,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_COLOUR_SUCCESS = "#2E7D32"

_SIDEBAR_PANELS = [
    "Schedules",
    "Editor",
    "Run History",
]

# Script checkboxes split into two groups
_TBT_SCRIPTS = [
    ("buyer_id_validation", "Buyer ID Validation"),
    ("seller_id_validation", "Seller ID Validation"),
    ("validate_ftbdm", "Fund Trade Buyer DM"),
    ("validate_ftsdm", "Fund Trade Seller DM"),
]

_INCONSISTENT_SCRIPTS = [
    ("inconsistent_buyer_id_validation", "Inconsistent Buyer ID"),
    ("inconsistent_seller_id_validation", "Inconsistent Seller ID"),
]

_STATUS_COLOURS: Dict[str, str] = {
    "success": _COLOUR_SUCCESS,
    "failed": COLOUR_RED,
    "running": "#F57C00",
    "pending": COLOUR_GREY,
    "waiting": "#FF8F00",
    "never_run": COLOUR_GREY,
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
    """Return a non-editable QTableWidgetItem, optionally coloured.

    Args:
        text: Display text for the cell.
        colour: Optional hex colour string for the foreground.

    Returns:
        Configured QTableWidgetItem.
    """
    from PySide6.QtGui import QBrush, QColor as _QColor

    item = QTableWidgetItem(text)
    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    if colour:
        item.setForeground(QBrush(_QColor(colour)))
    return item


def _format_dt(iso: Optional[str]) -> str:
    """Format an ISO datetime string to compact display, or '—'.

    Args:
        iso: ISO 8601 datetime string or None.

    Returns:
        Formatted string like ``2025-04-01 09:30``, or ``—``.
    """
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return str(iso)


def _freq_label(value: str) -> str:
    """Return a human-readable label for a frequency value.

    Args:
        value: Frequency key (e.g. ``"daily"``, ``"weekly"``).

    Returns:
        Human-readable label, or the raw value if not found.
    """
    for val, label in SCHEDULE_FREQUENCIES:
        if val == value:
            return label
    return value


# ---------------------------------------------------------------------------
# Panel 0 — Reconciliation List
# ---------------------------------------------------------------------------


class ReconciliationListPanel(QWidget):
    """Table of reconciliation schedules fetched from the API.

    Shows Name, Active, Frequency, Last Status, Next Run, Last Run.
    Provides Trigger Now, Enable/Disable, Edit, and Delete actions.

    Signals:
        edit_requested(dict): Emitted when Edit is clicked with the selected
            schedule dict.
    """

    edit_requested = Signal(object)

    def __init__(
        self,
        api_client: ApiClient,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialise the panel.

        Args:
            api_client: Shared API client instance.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._client = api_client

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        # Header row
        header_row = QHBoxLayout()
        header_row.addWidget(_header_label("Reconciliation Schedules"))
        header_row.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedWidth(80)
        refresh_btn.clicked.connect(self.refresh)
        header_row.addWidget(refresh_btn)
        outer.addLayout(header_row)

        # Table
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels([
            "Name", "Active", "Frequency", "Last Status", "Next Run", "Last Run",
        ])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setStyleSheet(
            f"QTableWidget {{ border: 1px solid {COLOUR_BORDER}; }}"
        )
        outer.addWidget(self._table)

        # Action buttons
        btn_row = QHBoxLayout()

        self._trigger_btn = QPushButton("Trigger Now")
        self._trigger_btn.clicked.connect(self._on_trigger)
        btn_row.addWidget(self._trigger_btn)

        self._toggle_btn = QPushButton("Enable / Disable")
        self._toggle_btn.clicked.connect(self._on_toggle)
        btn_row.addWidget(self._toggle_btn)

        self._edit_btn = QPushButton("Edit")
        self._edit_btn.clicked.connect(self._on_edit)
        btn_row.addWidget(self._edit_btn)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setStyleSheet(
            f"QPushButton:hover {{ background-color: {COLOUR_RED}; color: white; }}"
        )
        self._delete_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(self._delete_btn)

        btn_row.addStretch()
        outer.addLayout(btn_row)

        self.refresh()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Fetch reconciliation schedules from the API and repopulate the table."""
        try:
            from gui.api.reconciliation import list_reconciliations

            schedules = list_reconciliations(self._client)
        except Exception:
            schedules = []

        self._table.setRowCount(0)
        for rec in schedules:
            row = self._table.rowCount()
            self._table.insertRow(row)

            name_item = _table_item(rec.get("name", ""))
            name_item.setData(Qt.ItemDataRole.UserRole, rec)
            self._table.setItem(row, 0, name_item)

            active_text = "Yes" if rec.get("isActive", False) else "No"
            self._table.setItem(row, 1, _table_item(active_text))

            self._table.setItem(
                row, 2, _table_item(_freq_label(rec.get("frequency", "")))
            )

            status = rec.get("lastStatus") or "never_run"
            colour = _STATUS_COLOURS.get(status, COLOUR_GREY)
            self._table.setItem(
                row, 3, _table_item(status.replace("_", " ").title(), colour)
            )

            self._table.setItem(row, 4, _table_item(_format_dt(rec.get("nextRunAt"))))
            self._table.setItem(row, 5, _table_item(_format_dt(rec.get("lastRunAt"))))

        self._table.resizeColumnsToContents()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _selected_rec(self) -> Optional[Dict[str, Any]]:
        """Return the data dict for the currently selected row, or None."""
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_trigger(self) -> None:
        """Trigger the selected reconciliation immediately."""
        rec = self._selected_rec()
        if not rec:
            return
        try:
            from gui.api.reconciliation import trigger_reconciliation

            result = trigger_reconciliation(self._client, rec["id"])
            job_id = result.get("jobId", "")
            QMessageBox.information(
                self,
                "Reconciliation Triggered",
                f"Job {job_id} started for '{rec.get('name', '')}'.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to trigger: {exc}")

    def _on_toggle(self) -> None:
        """Toggle the active state of the selected reconciliation."""
        rec = self._selected_rec()
        if not rec:
            return
        try:
            from gui.api.reconciliation import toggle_reconciliation

            toggle_reconciliation(self._client, rec["id"])
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to toggle: {exc}")

    def _on_edit(self) -> None:
        """Emit edit_requested with the selected schedule dict."""
        rec = self._selected_rec()
        if rec:
            self.edit_requested.emit(rec)

    def _on_delete(self) -> None:
        """Delete the selected reconciliation after confirmation."""
        rec = self._selected_rec()
        if not rec:
            return
        reply = QMessageBox.question(
            self,
            "Delete Reconciliation",
            f"Permanently delete reconciliation '{rec.get('name', '')}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            from gui.api.reconciliation import delete_reconciliation

            delete_reconciliation(self._client, rec["id"])
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to delete: {exc}")


# ---------------------------------------------------------------------------
# Panel 1 — Reconciliation Editor
# ---------------------------------------------------------------------------


class ReconciliationEditorPanel(QWidget):
    """Create or edit a reconciliation schedule.

    Provides script selection (grouped checkboxes), frequency picker,
    testing period spinboxes, and stop-on-error control.

    Signals:
        saved(str): Emitted with the reconciliation ID on save, or ``""``
            when the user cancels.
    """

    saved = Signal(str)

    def __init__(
        self,
        api_client: ApiClient,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialise the editor panel.

        Args:
            api_client: Shared API client instance.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._client = api_client
        self._editing_id: Optional[str] = None

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        layout.addWidget(_header_label("Reconciliation Editor"))

        # Name
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Monthly Full Reconciliation")
        name_row.addWidget(self.name_edit)
        layout.addLayout(name_row)

        # Frequency
        freq_row = QHBoxLayout()
        freq_row.addWidget(QLabel("Frequency:"))
        self.freq_combo = QComboBox()
        for val, label in SCHEDULE_FREQUENCIES:
            self.freq_combo.addItem(label, val)
        self.freq_combo.currentIndexChanged.connect(self._on_freq_changed)
        freq_row.addWidget(self.freq_combo)
        freq_row.addStretch()
        layout.addLayout(freq_row)

        # Cron row (custom only)
        self.cron_row = QWidget()
        cron_h = QHBoxLayout(self.cron_row)
        cron_h.setContentsMargins(0, 0, 0, 0)
        cron_h.addWidget(QLabel("Cron:"))
        self.cron_edit = QLineEdit()
        self.cron_edit.setPlaceholderText("e.g. 0 6 * * 1")
        cron_h.addWidget(self.cron_edit)
        self.cron_row.setVisible(False)
        layout.addWidget(self.cron_row)

        # ── Trade-by-Trade Validation group ─────────────────────────
        tbt_group = QGroupBox("Trade-by-Trade Validation")
        tbt_v = QVBoxLayout(tbt_group)
        self._tbt_checkboxes: Dict[str, QCheckBox] = {}
        for key, label in _TBT_SCRIPTS:
            cb = QCheckBox(label)
            self._tbt_checkboxes[key] = cb
            tbt_v.addWidget(cb)
        layout.addWidget(tbt_group)

        # Rec Period (days) — applies to TBT scripts
        rec_period_row = QHBoxLayout()
        rec_period_row.addWidget(QLabel("Rec Period (days):"))
        self.rec_period_days = QSpinBox()
        self.rec_period_days.setRange(1, 3650)
        self.rec_period_days.setValue(90)
        self.rec_period_days.setFixedWidth(100)
        rec_period_row.addWidget(self.rec_period_days)
        rec_period_row.addStretch()
        layout.addLayout(rec_period_row)

        # ── Inconsistent ID group ────────────────────────────────────
        inc_group = QGroupBox("Inconsistent ID")
        inc_v = QVBoxLayout(inc_group)
        self._inc_checkboxes: Dict[str, QCheckBox] = {}
        for key, label in _INCONSISTENT_SCRIPTS:
            cb = QCheckBox(label)
            self._inc_checkboxes[key] = cb
            inc_v.addWidget(cb)
        layout.addWidget(inc_group)

        # Lookback (days) — applies to inconsistent ID scripts
        lookback_row = QHBoxLayout()
        lookback_row.addWidget(QLabel("Lookback (days):"))
        self.lookback_days = QSpinBox()
        self.lookback_days.setRange(1, 3650)
        self.lookback_days.setValue(365)
        self.lookback_days.setFixedWidth(100)
        lookback_row.addWidget(self.lookback_days)
        lookback_row.addStretch()
        layout.addLayout(lookback_row)

        # Stop on error
        self.stop_on_error = QCheckBox("Stop on first error")
        layout.addWidget(self.stop_on_error)

        # Active toggle
        self.active_cb = QCheckBox("Active (fires automatically on schedule)")
        self.active_cb.setChecked(True)
        layout.addWidget(self.active_cb)

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
        """Populate the form from an existing reconciliation schedule dict.

        Args:
            data: Schedule dict with camelCase keys: ``name``, ``frequency``,
                ``cronExpression``, ``selectedScripts``, ``recPeriodDays``,
                ``lookbackDays``, ``stopOnError``, ``isActive``.
        """
        self._editing_id = data.get("id")
        self.name_edit.setText(data.get("name", ""))

        freq = data.get("frequency", "monthly")
        idx = self.freq_combo.findData(freq)
        if idx >= 0:
            self.freq_combo.setCurrentIndex(idx)

        self.cron_edit.setText(data.get("cronExpression", ""))

        selected = set(data.get("selectedScripts", []))
        for key, cb in self._tbt_checkboxes.items():
            cb.setChecked(key in selected)
        for key, cb in self._inc_checkboxes.items():
            cb.setChecked(key in selected)

        self.rec_period_days.setValue(data.get("recPeriodDays", 90))
        self.lookback_days.setValue(data.get("lookbackDays", 365))
        self.stop_on_error.setChecked(data.get("stopOnError", False))
        self.active_cb.setChecked(data.get("isActive", True))

    def clear(self) -> None:
        """Reset the form to defaults for creating a new schedule."""
        self._editing_id = None
        self.name_edit.clear()
        self.freq_combo.setCurrentIndex(0)
        self.cron_edit.clear()
        for cb in self._tbt_checkboxes.values():
            cb.setChecked(False)
        for cb in self._inc_checkboxes.values():
            cb.setChecked(False)
        self.rec_period_days.setValue(90)
        self.lookback_days.setValue(365)
        self.stop_on_error.setChecked(False)
        self.active_cb.setChecked(True)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_freq_changed(self) -> None:
        """Show or hide the cron row based on the selected frequency."""
        self.cron_row.setVisible(self.freq_combo.currentData() == "custom")

    def _on_save(self) -> None:
        """Validate the form and save the reconciliation schedule via the API."""
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Schedule name is required.")
            return

        selected: List[str] = [
            key for key, cb in {**self._tbt_checkboxes, **self._inc_checkboxes}.items()
            if cb.isChecked()
        ]
        if not selected:
            QMessageBox.warning(
                self, "Validation", "Select at least one script checkbox."
            )
            return

        payload: Dict[str, Any] = {
            "name": name,
            "frequency": self.freq_combo.currentData(),
            "cronExpression": (
                self.cron_edit.text().strip()
                if self.freq_combo.currentData() == "custom"
                else ""
            ),
            "selectedScripts": selected,
            "recPeriodDays": self.rec_period_days.value(),
            "lookbackDays": self.lookback_days.value(),
            "stopOnError": self.stop_on_error.isChecked(),
            "isActive": self.active_cb.isChecked(),
        }

        try:
            if self._editing_id:
                from gui.api.reconciliation import update_reconciliation

                update_reconciliation(self._client, self._editing_id, payload)
                self.saved.emit(self._editing_id)
            else:
                from gui.api.reconciliation import create_reconciliation

                result = create_reconciliation(self._client, payload)
                self._editing_id = result.get("id", "")
                self.saved.emit(self._editing_id or "")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to save: {exc}")


# ---------------------------------------------------------------------------
# Panel 2 — Run History
# ---------------------------------------------------------------------------


class ReconciliationRunHistoryPanel(QWidget):
    """Recent reconciliation jobs fetched from ``GET /api/jobs``."""

    def __init__(
        self,
        api_client: ApiClient,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialise the run history panel.

        Args:
            api_client: Shared API client instance.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._client = api_client

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(8)

        # Header row
        header_row = QHBoxLayout()
        header_row.addWidget(_header_label("Run History"))
        header_row.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedWidth(80)
        refresh_btn.clicked.connect(self.refresh)
        header_row.addWidget(refresh_btn)
        outer.addLayout(header_row)

        # Splitter: table above, detail pane below
        splitter = QSplitter(Qt.Orientation.Vertical)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels([
            "Name", "Script", "Status", "Started", "Duration", "Job ID",
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

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Fetch recent jobs from the API and populate the table.

        Filters to reconciliation-related jobs by ``taskType`` or ``scriptName``.
        Falls back to showing all jobs if no reconciliation jobs are found.
        """
        try:
            from gui.api.jobs import list_jobs

            all_jobs: List[Dict[str, Any]] = list_jobs(self._client, limit=100)
        except Exception:
            all_jobs = []

        # Filter to reconciliation jobs
        rec_jobs = [
            j for j in all_jobs
            if j.get("taskType") == "reconciliation"
            or j.get("scriptName", "").startswith("reconcil")
        ]
        jobs = rec_jobs if rec_jobs else all_jobs

        self._table.setRowCount(0)
        for job in jobs:
            row = self._table.rowCount()
            self._table.insertRow(row)

            name_item = _table_item(job.get("name", job.get("taskName", "")))
            name_item.setData(Qt.ItemDataRole.UserRole, job)
            self._table.setItem(row, 0, name_item)

            self._table.setItem(
                row, 1, _table_item(job.get("scriptName", ""))
            )

            status = job.get("status", "")
            colour = _STATUS_COLOURS.get(status, COLOUR_GREY)
            self._table.setItem(row, 2, _table_item(status.title(), colour))

            self._table.setItem(row, 3, _table_item(_format_dt(job.get("startedAt"))))

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
            self._table.setItem(row, 4, _table_item(dur))

            self._table.setItem(row, 5, _table_item(job.get("id", "")[:8]))

        self._table.resizeColumnsToContents()
        self._detail_text.clear()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_row_selected(self) -> None:
        """Show job details in the detail pane when a row is selected."""
        row = self._table.currentRow()
        if row < 0:
            self._detail_text.clear()
            return

        item = self._table.item(row, 0)
        if not item:
            return
        job: Optional[Dict[str, Any]] = item.data(Qt.ItemDataRole.UserRole)
        if not job:
            return

        lines: List[str] = [
            f"Job ID:    {job.get('id', '')}",
            f"Name:      {job.get('name', job.get('taskName', ''))}",
            f"Script:    {job.get('scriptName', '')}",
            f"Status:    {job.get('status', '')}",
            f"Started:   {_format_dt(job.get('startedAt'))}",
            f"Completed: {_format_dt(job.get('completedAt'))}",
        ]
        if job.get("error"):
            lines.append(f"\nERROR: {job['error']}")
        self._detail_text.setPlainText("\n".join(lines))


# ---------------------------------------------------------------------------
# Main Reconciliation Tab
# ---------------------------------------------------------------------------


class ReconciliationTab(QWidget):
    """Seventh application tab — reconciliation schedule management.

    Contains three panels accessible via a sidebar:
    1. Schedules — list of reconciliation schedules from the API.
    2. Editor — create/edit a reconciliation schedule.
    3. Run History — recent reconciliation jobs from the API.
    """

    def __init__(
        self,
        api_client: Optional[ApiClient] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialise the reconciliation tab.

        Args:
            api_client: Shared API client instance. A new one is created if
                not provided.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._client = api_client or ApiClient()

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

        # "+ New Schedule" button
        new_btn = QPushButton("+ New Schedule")
        new_btn.clicked.connect(self._on_new_schedule)
        sidebar_layout.addWidget(new_btn)

        sidebar_layout.addStretch()
        outer.addWidget(sidebar_widget)

        # ── Stacked panels ───────────────────────────────────────────
        self._stack = QStackedWidget()
        outer.addWidget(self._stack, stretch=1)

        # Panel 0 — List
        self._list_panel = ReconciliationListPanel(self._client)
        self._list_panel.edit_requested.connect(self._on_edit_schedule)
        self._stack.addWidget(self._list_panel)

        # Panel 1 — Editor
        self._editor_panel = ReconciliationEditorPanel(self._client)
        self._editor_panel.saved.connect(self._on_schedule_saved)
        self._stack.addWidget(self._editor_panel)

        # Panel 2 — Run History
        self._history_panel = ReconciliationRunHistoryPanel(self._client)
        self._stack.addWidget(self._history_panel)

        # Select Schedules by default
        self._sidebar.setCurrentRow(0)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_sidebar_changed(self, index: int) -> None:
        """Switch the stacked widget to the panel matching *index*.

        Args:
            index: Sidebar row index (0=Schedules, 1=Editor, 2=Run History).
        """
        if index == 2:
            self._history_panel.refresh()
        self._stack.setCurrentIndex(index)

    def _on_new_schedule(self) -> None:
        """Open the editor in create mode."""
        self._editor_panel.clear()
        self._sidebar.setCurrentRow(1)

    def _on_edit_schedule(self, data: Dict[str, Any]) -> None:
        """Open the editor pre-populated with an existing schedule.

        Args:
            data: Reconciliation schedule dict from the API.
        """
        self._editor_panel.load_schedule(data)
        self._sidebar.setCurrentRow(1)

    def _on_schedule_saved(self, result: str) -> None:
        """Handle the editor save/cancel signal.

        Args:
            result: The reconciliation ID on success, or ``""`` on cancel.
        """
        if result:
            self._list_panel.refresh()
        self._sidebar.setCurrentRow(0)
