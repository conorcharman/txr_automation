"""
Tests for AutoStartManager (src.gui.tray.autostart).

All tests mock the winreg module so no real registry operations are
performed and the tests run on any platform.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest

from src.gui.tray.autostart import AutoStartManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# The module-level winreg import path used by autostart.py.
_WINREG = "src.gui.tray.autostart.winreg"


# ---------------------------------------------------------------------------
# enable()
# ---------------------------------------------------------------------------

class TestAutoStartEnable:
    """Tests for AutoStartManager.enable."""

    def test_enable_writes_registry_key(self) -> None:
        """enable() should call winreg.SetValueEx with the expected app name and return True."""
        with patch(_WINREG) as mock_winreg:
            result = AutoStartManager.enable()

        assert result is True
        mock_winreg.SetValueEx.assert_called_once()
        _, args, _ = mock_winreg.SetValueEx.mock_calls[0]
        # args: (key_handle, value_name, reserved, type, data)
        assert args[1] == AutoStartManager._APP_NAME

    def test_enable_returns_false_on_os_error(self) -> None:
        """enable() should catch OSError and return False without propagating the exception."""
        with patch(_WINREG) as mock_winreg:
            mock_winreg.OpenKey.side_effect = OSError("Access is denied.")
            result = AutoStartManager.enable()

        assert result is False


# ---------------------------------------------------------------------------
# disable()
# ---------------------------------------------------------------------------

class TestAutoStartDisable:
    """Tests for AutoStartManager.disable."""

    def test_disable_removes_registry_key(self) -> None:
        """disable() should call winreg.DeleteValue with the expected app name and return True."""
        with patch(_WINREG) as mock_winreg:
            result = AutoStartManager.disable()

        assert result is True
        mock_winreg.DeleteValue.assert_called_once()
        _, args, _ = mock_winreg.DeleteValue.mock_calls[0]
        # args: (key_handle, value_name)
        assert args[1] == AutoStartManager._APP_NAME


# ---------------------------------------------------------------------------
# is_enabled()
# ---------------------------------------------------------------------------

class TestAutoStartIsEnabled:
    """Tests for AutoStartManager.is_enabled."""

    def test_is_enabled_returns_true_when_key_exists(self) -> None:
        """is_enabled() should return True when QueryValueEx succeeds."""
        with patch(_WINREG) as mock_winreg:
            mock_winreg.QueryValueEx.return_value = ("some_command", 1)
            result = AutoStartManager.is_enabled()

        assert result is True
        mock_winreg.QueryValueEx.assert_called_once()

    def test_is_enabled_returns_false_when_key_missing(self) -> None:
        """is_enabled() should return False when QueryValueEx raises FileNotFoundError."""
        with patch(_WINREG) as mock_winreg:
            mock_winreg.QueryValueEx.side_effect = FileNotFoundError
            result = AutoStartManager.is_enabled()

        assert result is False
