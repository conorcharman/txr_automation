#!/usr/bin/env python3
"""
IncidentSelectorWidget
======================

A scrollable checklist of incidents with Select All / Deselect All
buttons. Used in RunAll, Collation, and DataPush panels so users
can tick which incidents to include in a batch run.
"""

from typing import List, Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.utils.settings import settings


class IncidentSelectorWidget(QWidget):
    """Scrollable checklist of incidents with persistence."""

    selection_changed = Signal()

    def __init__(
        self,
        incidents: List[Tuple[str, str]],
        settings_key: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        Initialise the incident selector.

        Args:
            incidents: List of ``(name, description)`` tuples.
            settings_key: QSettings key for persisting checked state.
            parent: Parent widget.
        """
        super().__init__(parent)
        self._incidents = incidents
        self._settings_key = settings_key

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header row with buttons
        header = QHBoxLayout()
        header.addWidget(QLabel("Incidents:"))
        header.addStretch()

        self._select_all_btn = QPushButton("Select All")
        self._select_all_btn.setFixedWidth(90)
        self._select_all_btn.clicked.connect(self.check_all)
        header.addWidget(self._select_all_btn)

        self._deselect_all_btn = QPushButton("Deselect All")
        self._deselect_all_btn.setFixedWidth(90)
        self._deselect_all_btn.clicked.connect(self.uncheck_all)
        header.addWidget(self._deselect_all_btn)

        layout.addLayout(header)

        # Checklist
        self._list = QListWidget()
        self._list.setMaximumHeight(200)
        for name, description in incidents:
            item = QListWidgetItem(f"{name}  —  {description}")
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setFlags(
                item.flags() | Qt.ItemFlag.ItemIsUserCheckable
            )
            item.setCheckState(Qt.CheckState.Checked)
            self._list.addItem(item)

        self._list.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self._list)

        # Restore persisted selection
        if self._settings_key:
            saved = settings.load_list(self._settings_key)
            if saved:
                self.set_selected(saved)

    def _on_item_changed(self, _item: QListWidgetItem) -> None:
        """Emit change signal and persist selection."""
        self.selection_changed.emit()
        if self._settings_key:
            settings.save(self._settings_key, self.get_selected())

    def get_selected(self) -> List[str]:
        """Return names of all checked incidents."""
        selected: List[str] = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.data(Qt.ItemDataRole.UserRole))
        return selected

    def set_selected(self, names: List[str]) -> None:
        """Check only the incidents whose names are in *names*."""
        self._list.blockSignals(True)
        for i in range(self._list.count()):
            item = self._list.item(i)
            name = item.data(Qt.ItemDataRole.UserRole)
            state = (
                Qt.CheckState.Checked
                if name in names
                else Qt.CheckState.Unchecked
            )
            item.setCheckState(state)
        self._list.blockSignals(False)
        self.selection_changed.emit()

    def check_all(self) -> None:
        """Check every incident."""
        self._list.blockSignals(True)
        for i in range(self._list.count()):
            self._list.item(i).setCheckState(Qt.CheckState.Checked)
        self._list.blockSignals(False)
        self._on_item_changed(self._list.item(0))

    def uncheck_all(self) -> None:
        """Uncheck every incident."""
        self._list.blockSignals(True)
        for i in range(self._list.count()):
            self._list.item(i).setCheckState(Qt.CheckState.Unchecked)
        self._list.blockSignals(False)
        self._on_item_changed(self._list.item(0))
