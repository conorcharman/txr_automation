#!/usr/bin/env python3
"""
AutoStartManager
================

Manages auto-start of the TXR Automation tray service on Windows login via
the ``HKEY_CURRENT_USER`` registry Run key.  No administrator privileges are
required because only the current user's hive is modified.

Version 1.0 Changes:
- Initial implementation for Phase 3 tray service
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

try:
    import winreg  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - exercised in Linux containers
    winreg = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class AutoStartManager:
    """Manages auto-start of the tray service on Windows login.

    Reads and writes the ``HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\
    CurrentVersion\\Run`` registry key so the tray is launched automatically
    when the current user logs in.  No admin rights are required.

    Example:
        >>> AutoStartManager.enable()
        True
        >>> AutoStartManager.is_enabled()
        True
        >>> AutoStartManager.disable()
        True
        >>> AutoStartManager.is_enabled()
        False
    """

    _REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    _APP_NAME = "TXRAutomationTray"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def enable(cls) -> bool:
        """Register the tray service to start on login via registry Run key.

        Writes the path to the ``txr-tray`` executable (or a ``python -m``
        command when running in a development environment) under the current
        user's ``Run`` key.

        Returns:
            ``True`` on success, ``False`` if the registry could not be
            written (e.g. the key is locked by another process).
        """
        if winreg is None:
            logger.debug("AutoStart is only supported on Windows.")
            return False

        command = cls._get_exe_path()
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                cls._REG_KEY,
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                winreg.SetValueEx(key, cls._APP_NAME, 0, winreg.REG_SZ, command)
                logger.info("AutoStart enabled: %s -> %s", cls._APP_NAME, command)
                return True
        except (FileNotFoundError, OSError, PermissionError) as exc:
            logger.error("Failed to enable auto-start: %s", exc)
            return False

    @classmethod
    def disable(cls) -> bool:
        """Remove the auto-start registry entry.

        Returns:
            ``True`` on success or if the entry did not exist, ``False`` on
            unexpected error.
        """
        if winreg is None:
            logger.debug("AutoStart is only supported on Windows.")
            return False

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                cls._REG_KEY,
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                try:
                    winreg.DeleteValue(key, cls._APP_NAME)
                    logger.info("AutoStart disabled: %s", cls._APP_NAME)
                except FileNotFoundError:
                    # Entry was not present — that is fine.
                    logger.debug("AutoStart entry not found, nothing to remove.")
                return True
        except (OSError, PermissionError) as exc:
            logger.error("Failed to disable auto-start: %s", exc)
            return False

    @classmethod
    def is_enabled(cls) -> bool:
        """Return ``True`` if the auto-start entry exists in the registry.

        Returns:
            ``True`` when the ``TXRAutomationTray`` value is present under
            the Run key, ``False`` otherwise.
        """
        if winreg is None:
            return False

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                cls._REG_KEY,
                0,
                winreg.KEY_READ,
            ) as key:
                try:
                    winreg.QueryValueEx(key, cls._APP_NAME)
                    return True
                except FileNotFoundError:
                    return False
        except (OSError, PermissionError):
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @classmethod
    def _get_exe_path(cls) -> str:
        """Return the command used to launch the tray service.

        When running as a frozen executable (e.g. packaged with PyInstaller)
        ``sys.frozen`` is set and ``sys.executable`` points to the ``.exe``.
        In a development or conda environment the scripts directory is
        searched for a ``txr-tray`` wrapper; if not found a ``python -m``
        fallback is constructed.

        Returns:
            Full command string suitable for the registry Run value.
        """
        # Frozen executable (PyInstaller / cx_Freeze)
        if getattr(sys, "frozen", False):
            return sys.executable

        # Look for a txr-tray console-script wrapper installed in the Scripts dir.
        scripts_dir = Path(sys.executable).parent
        for candidate in ("txr-tray.exe", "txr-tray"):
            script_path = scripts_dir / candidate
            if script_path.exists():
                return str(script_path)

        # Development fallback: invoke module directly.
        return f'"{sys.executable}" -m src.gui.tray.tray_app'
