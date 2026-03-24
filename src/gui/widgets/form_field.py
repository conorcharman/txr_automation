#!/usr/bin/env python3
"""
FormFieldWidget
===============

A generic labelled form field supporting text, dropdown, checkbox,
and spinbox types. Used to build script parameter forms.
"""

from typing import Any, List, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from gui.utils.settings import settings


class FormFieldWidget(QWidget):
    """Generic labelled form field."""

    value_changed = Signal(object)

    def __init__(
        self,
        label: str,
        field_type: str = "text",
        choices: Optional[List[str]] = None,
        default: Any = None,
        tooltip: str = "",
        placeholder: str = "",
        settings_key: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        Initialise the form field.

        Args:
            label: Display label.
            field_type: One of "text", "dropdown", "checkbox", "spinbox".
            choices: List of choices for dropdown fields.
            default: Default value.
            tooltip: Hover tooltip text.
            placeholder: Placeholder text for text fields.
            settings_key: QSettings key for persisting the value.
            parent: Parent widget.
        """
        super().__init__(parent)
        self._field_type = field_type
        self._settings_key = settings_key

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel(label)
        self._label.setFixedWidth(140)

        if field_type == "checkbox":
            # For checkboxes, the label is part of the checkbox itself
            self._input: QWidget = QCheckBox(label)
            if default:
                self._input.setChecked(bool(default))
            self._input.stateChanged.connect(
                lambda _: self._emit_and_persist()
            )
            layout.addWidget(self._input)
        else:
            layout.addWidget(self._label)

            if field_type == "dropdown":
                combo = QComboBox()
                if choices:
                    combo.addItems(choices)
                if default and choices and default in choices:
                    combo.setCurrentText(str(default))
                combo.currentTextChanged.connect(
                    lambda _: self._emit_and_persist()
                )
                self._input = combo
            elif field_type == "spinbox":
                spin = QSpinBox()
                spin.setMinimum(0)
                spin.setMaximum(999999)
                if default is not None:
                    spin.setValue(int(default))
                spin.valueChanged.connect(
                    lambda _: self._emit_and_persist()
                )
                self._input = spin
            else:
                line = QLineEdit()
                if default is not None:
                    line.setText(str(default))
                if placeholder:
                    line.setPlaceholderText(placeholder)
                line.textChanged.connect(
                    lambda _: self._emit_and_persist()
                )
                self._input = line

            layout.addWidget(self._input, stretch=1)

        if tooltip:
            self._label.setToolTip(tooltip)
            self._input.setToolTip(tooltip)

        # Restore persisted value (after widget is fully built)
        if self._settings_key:
            saved = settings.load(self._settings_key)
            if saved is not None:
                self.set_value(saved)

    def get_value(self) -> Any:
        """Return the current field value."""
        if self._field_type == "checkbox":
            return self._input.isChecked()
        elif self._field_type == "dropdown":
            return self._input.currentText()
        elif self._field_type == "spinbox":
            return self._input.value()
        else:
            return self._input.text()

    def set_value(self, value: Any) -> None:
        """Set the field value programmatically."""
        if self._field_type == "checkbox":
            self._input.setChecked(
                value if isinstance(value, bool)
                else str(value).lower() == "true"
            )
        elif self._field_type == "dropdown":
            self._input.setCurrentText(str(value))
        elif self._field_type == "spinbox":
            self._input.setValue(int(value) if value else 0)
        else:
            self._input.setText(str(value) if value is not None else "")

    def _emit_and_persist(self) -> None:
        """Emit value_changed and save to QSettings if configured."""
        value = self.get_value()
        self.value_changed.emit(value)
        if self._settings_key:
            settings.save(self._settings_key, value)

    def clear(self) -> None:
        """Reset the field to its default state."""
        if self._field_type == "checkbox":
            self._input.setChecked(False)
        elif self._field_type == "dropdown":
            self._input.setCurrentIndex(0)
        elif self._field_type == "spinbox":
            self._input.setValue(0)
        else:
            self._input.clear()
