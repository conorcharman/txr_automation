#!/usr/bin/env python3
"""
IncidentSelectorWidget
======================

A scrollable checklist of incidents with Select All / Deselect All
buttons.  Supports both flat mode (legacy) and hierarchical mode
where multi-incident scripts show as expandable parents with
indeterminate check state for partial selection.

Used in RunAll, Collation, DataPush, and the new unified Validation
Scripts panel.
"""

from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.utils.settings import settings


class IncidentSelectorWidget(QWidget):
    """Scrollable checklist of incidents with persistence.

    In *hierarchical* mode (``hierarchical=True``), incidents are grouped
    under their parent script.  Multi-code scripts show as expandable
    parents; single-code scripts show as flat rows.

    ``get_selected()`` returns a list of
    ``{"scriptKey": str, "incidentCode": str}`` dicts in hierarchical
    mode, or a flat list of name strings in legacy mode.
    """

    selection_changed = Signal()

    def __init__(
        self,
        incidents: List[Tuple[str, str]],
        settings_key: str = "",
        hierarchical: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialise the incident selector.

        Args:
            incidents: List of ``(name, description)`` tuples.
                In hierarchical mode, each tuple is
                ``(script_key, display_label)`` and a separate
                ``scripts`` list must be set via ``set_scripts()``.
            settings_key: QSettings key for persisting checked state.
            hierarchical: Use tree-based hierarchical display.
            parent: Parent widget.
        """
        super().__init__(parent)
        self._incidents = incidents
        self._settings_key = settings_key
        self._hierarchical = hierarchical

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

        if hierarchical:
            self._tree = QTreeWidget()
            self._tree.setHeaderHidden(True)
            self._tree.setMaximumHeight(280)
            self._tree.itemChanged.connect(self._on_tree_item_changed)
            layout.addWidget(self._tree)
            self._list = None
            self._script_defs: List[Dict] = []
        else:
            # Legacy flat list mode
            from PySide6.QtWidgets import QListWidget, QListWidgetItem

            self._list = QListWidget()
            self._list.setMaximumHeight(200)
            for name, description in incidents:
                item = QListWidgetItem(f"{name}  \u2014  {description}")
                item.setData(Qt.ItemDataRole.UserRole, name)
                item.setFlags(
                    item.flags() | Qt.ItemFlag.ItemIsUserCheckable
                )
                item.setCheckState(Qt.CheckState.Checked)
                self._list.addItem(item)

            self._list.itemChanged.connect(self._on_item_changed)
            layout.addWidget(self._list)
            self._tree = None

        # Restore persisted selection
        if self._settings_key:
            saved = settings.load_list(self._settings_key)
            if saved:
                self.set_selected(saved)

    # ------------------------------------------------------------------
    # Hierarchical mode: set_scripts
    # ------------------------------------------------------------------

    def set_scripts(self, scripts: List[Dict]) -> None:
        """Populate the tree with grouped scripts (hierarchical mode only).

        Args:
            scripts: List of dicts with keys ``scriptKey``, ``displayLabel``,
                ``incidents`` (list of ``{"code": str, "label": str}``).
        """
        if not self._hierarchical or self._tree is None:
            return

        self._tree.blockSignals(True)
        self._tree.clear()
        self._script_defs = scripts

        for script in scripts:
            key = script["scriptKey"]
            label = script["displayLabel"]
            codes = script["incidents"]

            if len(codes) == 1:
                # Single-incident script — flat row
                item = QTreeWidgetItem(self._tree)
                code_info = codes[0]
                item.setText(0, f"{label} ({code_info['code']})")
                item.setData(0, Qt.ItemDataRole.UserRole, {
                    "scriptKey": key,
                    "incidentCode": code_info["code"],
                })
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked)
            else:
                # Multi-incident script — parent with children
                parent = QTreeWidgetItem(self._tree)
                parent.setText(0, f"{label}")
                parent.setFlags(
                    parent.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsAutoTristate
                )
                parent.setCheckState(0, Qt.CheckState.Checked)
                parent.setExpanded(True)

                for code_info in codes:
                    child = QTreeWidgetItem(parent)
                    child.setText(0, f"{code_info['label']} ({code_info['code']})")
                    child.setData(0, Qt.ItemDataRole.UserRole, {
                        "scriptKey": key,
                        "incidentCode": code_info["code"],
                    })
                    child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    child.setCheckState(0, Qt.CheckState.Checked)

        self._tree.blockSignals(False)

        # Restore persisted selection
        if self._settings_key:
            saved = settings.load_list(self._settings_key)
            if saved:
                self._restore_tree_selection(saved)

    # ------------------------------------------------------------------
    # Flat list callbacks
    # ------------------------------------------------------------------

    def _on_item_changed(self, _item) -> None:
        """Emit change signal and persist selection (flat mode)."""
        self.selection_changed.emit()
        if self._settings_key:
            settings.save(self._settings_key, self.get_selected())

    # ------------------------------------------------------------------
    # Tree callbacks
    # ------------------------------------------------------------------

    def _on_tree_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle check state changes in the tree."""
        self.selection_changed.emit()
        if self._settings_key:
            self._persist_tree_selection()

    def _persist_tree_selection(self) -> None:
        """Save selected incident codes as a flat list to QSettings."""
        selected = self.get_selected_incidents()
        # Persist as list of "scriptKey:code" strings
        keys = [f"{s['scriptKey']}:{s['incidentCode']}" for s in selected]
        settings.save(self._settings_key, keys)

    def _restore_tree_selection(self, saved: List[str]) -> None:
        """Restore tree check state from a saved list of 'scriptKey:code' strings."""
        saved_set = set(saved)
        self._tree.blockSignals(True)

        def _walk(parent_item):
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                data = child.data(0, Qt.ItemDataRole.UserRole)
                if data:
                    key = f"{data['scriptKey']}:{data['incidentCode']}"
                    state = (
                        Qt.CheckState.Checked if key in saved_set
                        else Qt.CheckState.Unchecked
                    )
                    child.setCheckState(0, state)
                _walk(child)

        root = self._tree.invisibleRootItem()
        _walk(root)

        # Update parent states
        for i in range(root.childCount()):
            top = root.child(i)
            if top.childCount() > 0:
                self._update_parent_check_state(top)

        self._tree.blockSignals(False)

    @staticmethod
    def _update_parent_check_state(parent: QTreeWidgetItem) -> None:
        """Set parent to Checked/Unchecked/PartiallyChecked based on children."""
        checked = 0
        total = parent.childCount()
        for i in range(total):
            if parent.child(i).checkState(0) == Qt.CheckState.Checked:
                checked += 1
        if checked == total:
            parent.setCheckState(0, Qt.CheckState.Checked)
        elif checked == 0:
            parent.setCheckState(0, Qt.CheckState.Unchecked)
        else:
            parent.setCheckState(0, Qt.CheckState.PartiallyChecked)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_selected(self) -> List[str]:
        """Return names of all checked incidents (flat mode).

        For hierarchical mode, returns flat list of incident codes.
        Use ``get_selected_incidents()`` for structured data.
        """
        if self._hierarchical:
            return [s["incidentCode"] for s in self.get_selected_incidents()]

        selected: List[str] = []
        if self._list is not None:
            for i in range(self._list.count()):
                item = self._list.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    selected.append(item.data(Qt.ItemDataRole.UserRole))
        return selected

    def get_selected_incidents(self) -> List[Dict[str, str]]:
        """Return selected incidents as structured dicts (hierarchical mode).

        Returns:
            List of ``{"scriptKey": str, "incidentCode": str}`` dicts.
        """
        if not self._hierarchical or self._tree is None:
            return [
                {"scriptKey": name, "incidentCode": name}
                for name in self.get_selected()
            ]

        result: List[Dict[str, str]] = []

        def _walk(parent_item):
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                data = child.data(0, Qt.ItemDataRole.UserRole)
                if data and child.checkState(0) == Qt.CheckState.Checked:
                    result.append(data)
                elif child.childCount() > 0:
                    _walk(child)

        root = self._tree.invisibleRootItem()
        # Handle top-level items (single-incident scripts are leaf items)
        for i in range(root.childCount()):
            top = root.child(i)
            data = top.data(0, Qt.ItemDataRole.UserRole)
            if data and top.checkState(0) == Qt.CheckState.Checked:
                result.append(data)
            elif top.childCount() > 0:
                _walk(top)

        return result

    def set_selected(self, names: List[str]) -> None:
        """Check only the incidents whose names are in *names*."""
        if self._hierarchical:
            self._restore_tree_selection(names)
            return

        if self._list is not None:
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
        if self._hierarchical and self._tree is not None:
            self._tree.blockSignals(True)
            root = self._tree.invisibleRootItem()
            for i in range(root.childCount()):
                top = root.child(i)
                top.setCheckState(0, Qt.CheckState.Checked)
                for j in range(top.childCount()):
                    top.child(j).setCheckState(0, Qt.CheckState.Checked)
            self._tree.blockSignals(False)
            self._on_tree_item_changed(None, 0)
            return

        if self._list is not None:
            self._list.blockSignals(True)
            for i in range(self._list.count()):
                self._list.item(i).setCheckState(Qt.CheckState.Checked)
            self._list.blockSignals(False)
            self._on_item_changed(self._list.item(0))

    def uncheck_all(self) -> None:
        """Uncheck every incident."""
        if self._hierarchical and self._tree is not None:
            self._tree.blockSignals(True)
            root = self._tree.invisibleRootItem()
            for i in range(root.childCount()):
                top = root.child(i)
                top.setCheckState(0, Qt.CheckState.Unchecked)
                for j in range(top.childCount()):
                    top.child(j).setCheckState(0, Qt.CheckState.Unchecked)
            self._tree.blockSignals(False)
            self._on_tree_item_changed(None, 0)
            return

        if self._list is not None:
            self._list.blockSignals(True)
            for i in range(self._list.count()):
                self._list.item(i).setCheckState(Qt.CheckState.Unchecked)
            self._list.blockSignals(False)
            self._on_item_changed(self._list.item(0))
