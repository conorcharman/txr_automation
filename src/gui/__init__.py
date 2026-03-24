#!/usr/bin/env python3
"""
TXR Automation GUI
==================

PySide6 desktop GUI for configuring and running TXR automation scripts.

Provides a tabbed interface with file pickers, configuration editors,
and real-time log streaming. Wraps the existing CLI scripts so analysts
can run them without command-line knowledge.

Usage:
    python -m gui
"""

from gui.constants import APP_NAME, APP_VERSION

__all__ = ["APP_NAME", "APP_VERSION"]
