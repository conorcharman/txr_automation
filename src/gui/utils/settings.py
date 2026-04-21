#!/usr/bin/env python3
"""
SettingsManager
===============

Thin wrapper around QSettings for persisting GUI form values
(file paths, checkboxes, dropdowns, etc.) across sessions.

Values are stored locally per user via QSettings
(Windows registry / AppData).
"""

import json
from typing import Any, List, Optional

from PySide6.QtCore import QSettings


class SettingsManager:
    """Persist and restore GUI field values via QSettings."""

    def __init__(
        self,
        organisation: str = "TXRAutomation",
        application: str = "txr_automation",
    ) -> None:
        self._settings = QSettings(organisation, application)

    def save(self, key: str, value: Any) -> None:
        """Save a value under *key*."""
        if isinstance(value, (list, dict)):
            self._settings.setValue(key, json.dumps(value))
        else:
            self._settings.setValue(key, value)

    def load(self, key: str, default: Any = None) -> Any:
        """Load the value stored under *key*, returning *default* if absent."""
        val = self._settings.value(key)
        if val is None:
            return default
        return val

    def load_list(self, key: str, default: Optional[List[str]] = None) -> List[str]:
        """Load a JSON-encoded list stored under *key*."""
        raw = self._settings.value(key)
        if raw is None:
            return default if default is not None else []
        if isinstance(raw, list):
            return raw
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return default if default is not None else []

    def remove(self, key: str) -> None:
        """Remove a stored key."""
        self._settings.remove(key)

    def clear(self) -> None:
        """Remove all stored settings."""
        self._settings.clear()

    @property
    def api_url(self) -> str:
        """Return the stored API URL, defaulting to ``http://localhost:8000``."""
        from gui.constants import API_DEFAULT_URL

        return str(self.load("api/url", API_DEFAULT_URL))

    @api_url.setter
    def api_url(self, value: str) -> None:
        """Persist the API URL."""
        self.save("api/url", value)

    @property
    def data_root_dir(self) -> str:
        """Return the stored data root directory for smart path resolution."""
        return str(self.load("discovery/data_root_dir", ""))

    @data_root_dir.setter
    def data_root_dir(self, value: str) -> None:
        """Persist the data root directory."""
        self.save("discovery/data_root_dir", value)

    @property
    def default_fy(self) -> str:
        """Return the stored default fiscal year, e.g. ``'FY26'``."""
        from datetime import datetime

        fallback = f"FY{datetime.now().year % 100}"
        return str(self.load("discovery/default_fy", fallback))

    @default_fy.setter
    def default_fy(self, value: str) -> None:
        """Persist the default fiscal year."""
        self.save("discovery/default_fy", value)

    @property
    def default_quarter(self) -> str:
        """Return the stored default quarter, e.g. ``'Q1'``."""
        return str(self.load("discovery/default_quarter", "Q1"))

    @default_quarter.setter
    def default_quarter(self, value: str) -> None:
        """Persist the default quarter."""
        self.save("discovery/default_quarter", value)


# Module-level singleton used by all widgets
settings = SettingsManager()
