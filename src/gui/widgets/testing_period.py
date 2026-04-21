#!/usr/bin/env python3
"""
TestingPeriodWidget
===================

A reusable fiscal year + quarter selector with QSettings persistence
and a ``period_changed`` signal.

Extracted from the inline ``_TestingPeriodSelector`` in
``accuracy_tab.py`` so that every tab can share the same widget.

Usage:
    period = TestingPeriodWidget(settings_prefix="replay.phase2")
    period.period_changed.connect(self._on_period_changed)
    layout.addWidget(period)
"""

from datetime import datetime
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QWidget

from gui.utils.settings import settings


def _current_fy() -> str:
    """Return the current fiscal year string, e.g. ``'FY26'``."""
    return f"FY{datetime.now().year % 100}"


def _build_fy_list(window: int = 2) -> list[str]:
    """Return a list of fiscal years centred on the current year.

    Args:
        window: Number of years before and after the current FY.

    Returns:
        List of FY strings, oldest first, e.g. ``["FY24", "FY25", "FY26", "FY27", "FY28"]``.
    """
    current = datetime.now().year % 100
    return [f"FY{y % 100:02d}" for y in range(current - window, current + window + 1)]


class TestingPeriodWidget(QWidget):
    """Fiscal year + quarter selector with QSettings persistence.

    Emits :attr:`period_changed` whenever either dropdown changes.

    Args:
        settings_prefix: QSettings key prefix, e.g. ``"accuracy.validation"``.
            The widget stores ``{prefix}.fiscal_year`` and ``{prefix}.quarter``.
        parent: Parent widget.
    """

    period_changed = Signal(str, str)  # (fiscal_year, quarter)

    _QUARTERS = ["Q1", "Q2", "Q3", "Q4"]

    def __init__(
        self,
        settings_prefix: str = "accuracy",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._prefix = settings_prefix
        self._fy_key = f"{settings_prefix}.fiscal_year"
        self._q_key = f"{settings_prefix}.quarter"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Fiscal Year:"))
        self._fy = QComboBox()
        self._fy.addItems(_build_fy_list())
        self._restore_fy()
        self._fy.currentTextChanged.connect(self._on_fy_changed)
        layout.addWidget(self._fy)

        layout.addWidget(QLabel("Quarter:"))
        self._q = QComboBox()
        self._q.addItems(self._QUARTERS)
        self._restore_q()
        self._q.currentTextChanged.connect(self._on_q_changed)
        layout.addWidget(self._q)

        layout.addStretch()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def fiscal_year(self) -> str:
        """Currently selected fiscal year."""
        return self._fy.currentText()

    @property
    def quarter(self) -> str:
        """Currently selected quarter."""
        return self._q.currentText()

    def set_period(self, fiscal_year: str, quarter: str) -> None:
        """Set both dropdowns programmatically without emitting a signal.

        Args:
            fiscal_year: e.g. ``"FY26"``.
            quarter: e.g. ``"Q2"``.
        """
        self._fy.blockSignals(True)
        self._q.blockSignals(True)
        idx = self._fy.findText(fiscal_year)
        if idx >= 0:
            self._fy.setCurrentIndex(idx)
        idx = self._q.findText(quarter)
        if idx >= 0:
            self._q.setCurrentIndex(idx)
        self._fy.blockSignals(False)
        self._q.blockSignals(False)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_fy_changed(self, text: str) -> None:
        settings.save(self._fy_key, text)
        self.period_changed.emit(text, self._q.currentText())

    def _on_q_changed(self, text: str) -> None:
        settings.save(self._q_key, text)
        self.period_changed.emit(self._fy.currentText(), text)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _restore_fy(self) -> None:
        saved = settings.load(self._fy_key, _current_fy())
        idx = self._fy.findText(str(saved))
        # If saved FY is outside the dynamic list, append it
        if idx < 0 and saved:
            self._fy.addItem(str(saved))
            idx = self._fy.count() - 1
        if idx >= 0:
            self._fy.setCurrentIndex(idx)

    def _restore_q(self) -> None:
        saved = settings.load(self._q_key, "Q1")
        idx = self._q.findText(str(saved))
        if idx >= 0:
            self._q.setCurrentIndex(idx)
