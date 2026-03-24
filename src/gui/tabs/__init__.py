#!/usr/bin/env python3
"""
GUI Tabs
========

Tab panels for the main application window.
Each module corresponds to a top-level tab.
"""

from gui.tabs.accuracy_tab import AccuracyTab
from gui.tabs.replay_tab import ReplayTab
from gui.tabs.firds_tab import FirdsTab
from gui.tabs.gleif_tab import GleifTab
from gui.tabs.utilities_tab import UtilitiesTab

__all__ = [
    "AccuracyTab",
    "ReplayTab",
    "FirdsTab",
    "GleifTab",
    "UtilitiesTab",
]
