"""
Tests for NotificationManager (src.gui.tray.notifications).

All tests mock the plyer backend so no OS toast infrastructure is required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import src.gui.tray.notifications as notif_module
from src.gui.tray.notifications import NotificationManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_notifier(*, plyer_available: bool = True) -> tuple[NotificationManager, MagicMock]:
    """Construct a NotificationManager with a mocked plyer backend.

    Args:
        plyer_available: Whether to simulate plyer being installed.

    Returns:
        Tuple of ``(notifier_instance, mock_plyer_notification)``.
    """
    mock_plyer = MagicMock()
    with (
        patch.object(notif_module, "_plyer_notification", mock_plyer),
        patch.object(notif_module, "_PLYER_AVAILABLE", plyer_available),
    ):
        nm = NotificationManager()
    # Keep the patched _available flag consistent with what __init__ read.
    nm._available = plyer_available
    # Ensure _plyer_notification is reachable at call time via a module patch
    # that outlives __init__.  We re-apply below in each test instead.
    return nm, mock_plyer


# ---------------------------------------------------------------------------
# notify_success
# ---------------------------------------------------------------------------

class TestNotifySuccess:
    """Tests for NotificationManager.notify_success."""

    def test_notify_success_with_plyer_available(self) -> None:
        """notify_success should call plyer notify with a title containing the schedule name.

        The title format is 'Pipeline succeeded — <name>' so it contains
        both 'succeeded' and the schedule name.
        """
        mock_plyer = MagicMock()
        with (
            patch.object(notif_module, "_plyer_notification", mock_plyer),
            patch.object(notif_module, "_PLYER_AVAILABLE", True),
        ):
            nm = NotificationManager()
            nm.notify_success("Test Schedule", 45.0)

        mock_plyer.notify.assert_called_once()
        call_kwargs = mock_plyer.notify.call_args.kwargs
        assert "Test Schedule" in call_kwargs["title"]


# ---------------------------------------------------------------------------
# notify_failure
# ---------------------------------------------------------------------------

class TestNotifyFailure:
    """Tests for NotificationManager.notify_failure."""

    def test_notify_failure_with_plyer_available(self) -> None:
        """notify_failure should call plyer notify with the error message in the body.

        Args: none — mocks plyer internally.
        """
        mock_plyer = MagicMock()
        error_msg = "Connection refused to AS/400"
        with (
            patch.object(notif_module, "_plyer_notification", mock_plyer),
            patch.object(notif_module, "_PLYER_AVAILABLE", True),
        ):
            nm = NotificationManager()
            nm.notify_failure("Test Schedule", error_msg)

        mock_plyer.notify.assert_called_once()
        call_kwargs = mock_plyer.notify.call_args.kwargs
        assert error_msg in call_kwargs["message"]


# ---------------------------------------------------------------------------
# notify_started
# ---------------------------------------------------------------------------

class TestNotifyStarted:
    """Tests for NotificationManager.notify_started."""

    def test_notify_started_with_plyer_available(self) -> None:
        """notify_started should call plyer notify exactly once."""
        mock_plyer = MagicMock()
        with (
            patch.object(notif_module, "_plyer_notification", mock_plyer),
            patch.object(notif_module, "_PLYER_AVAILABLE", True),
        ):
            nm = NotificationManager()
            nm.notify_started("Test Schedule")

        mock_plyer.notify.assert_called_once()
        call_kwargs = mock_plyer.notify.call_args.kwargs
        assert "Test Schedule" in call_kwargs["title"]


# ---------------------------------------------------------------------------
# Graceful degradation when plyer is unavailable
# ---------------------------------------------------------------------------

class TestNotifyGracefulDegradation:
    """Verify that all notify methods are no-ops when plyer is not installed."""

    def test_notify_graceful_when_plyer_unavailable(self) -> None:
        """All notify methods should raise no exception when plyer is unavailable.

        Simulates a runtime environment where plyer is not installed by
        patching ``_PLYER_AVAILABLE`` to False before constructing the
        NotificationManager so that ``self._available`` is set to False.
        """
        with patch.object(notif_module, "_PLYER_AVAILABLE", False):
            nm = NotificationManager()

        # None of these should raise, even with plyer absent.
        nm.notify_started("Test Schedule")
        nm.notify_success("Test Schedule", 10.0)
        nm.notify_failure("Test Schedule", "some error")
