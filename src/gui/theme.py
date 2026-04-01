#!/usr/bin/env python3
"""
GUI Theme
=========

Windows 11 Fluent-inspired theme for the TXR Automation desktop application.
Uses AJ Bell brand colours (#D50032 red, #6A737B grey, #FFFFFF white) with
Segoe UI typography and Fluent design tokens:

- Primary buttons:   filled #D50032 (AJ Bell red)
- Selected nav item: left accent bar #D50032
- Secondary text:    #6A737B (AJ Bell grey)
- Borders:           #E0E0E0 (subtle)
- Surface:           #F3F3F3 (off-white panel bg)
- Focus indicator:   2px bottom border #D50032

No external dependencies — pure QSS + optional ctypes Mica effect.

Usage:
    from gui.theme import apply_theme
    apply_theme(app)       # call once after QApplication is created
    apply_mica(window)     # call after window.show() on Windows 11
"""

import ctypes
import sys
from typing import TYPE_CHECKING

from PySide6.QtGui import QFont

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication, QMainWindow

from gui.constants import (
    COLOUR_BORDER,
    COLOUR_GREY,
    COLOUR_RED,
    COLOUR_RED_HOVER,
    COLOUR_RED_PRESSED,
    COLOUR_SURFACE,
    COLOUR_WHITE,
    FONT_FAMILY,
)

# ---------------------------------------------------------------------------
# QSS stylesheet
# ---------------------------------------------------------------------------

GLOBAL_QSS = f"""
/* ── Global reset ──────────────────────────────────────────────────────── */
* {{
    font-family: "{FONT_FAMILY}", "Segoe UI", sans-serif;
    font-size: 10pt;
    outline: none;
}}

QMainWindow, QDialog, QWidget {{
    background-color: {COLOUR_WHITE};
    color: #1A1A1A;
}}

/* ── Menu bar ───────────────────────────────────────────────────────────── */
QMenuBar {{
    background-color: {COLOUR_WHITE};
    border-bottom: 1px solid {COLOUR_BORDER};
    padding: 2px 4px;
}}

QMenuBar::item {{
    padding: 4px 10px;
    border-radius: 4px;
}}

QMenuBar::item:selected {{
    background-color: {COLOUR_SURFACE};
    color: {COLOUR_RED};
}}

QMenu {{
    background-color: {COLOUR_WHITE};
    border: 1px solid {COLOUR_BORDER};
    border-radius: 6px;
    padding: 4px 0px;
}}

QMenu::item {{
    padding: 6px 20px;
    border-radius: 4px;
}}

QMenu::item:selected {{
    background-color: {COLOUR_SURFACE};
    color: {COLOUR_RED};
}}

QMenu::separator {{
    height: 1px;
    background-color: {COLOUR_BORDER};
    margin: 4px 8px;
}}

/* ── Push buttons ───────────────────────────────────────────────────────── */
QPushButton {{
    background-color: {COLOUR_WHITE};
    color: #1A1A1A;
    border: 1px solid {COLOUR_BORDER};
    border-radius: 4px;
    padding: 5px 14px;
    min-height: 22px;
}}

QPushButton:hover {{
    background-color: {COLOUR_SURFACE};
    border-color: {COLOUR_GREY};
}}

QPushButton:pressed {{
    background-color: {COLOUR_BORDER};
}}

QPushButton:disabled {{
    background-color: {COLOUR_SURFACE};
    color: #ABABAB;
    border-color: {COLOUR_BORDER};
}}

/* Primary button — set via setProperty("primary", True) */
QPushButton[primary="true"] {{
    background-color: {COLOUR_RED};
    color: {COLOUR_WHITE};
    border: 1px solid {COLOUR_RED};
    border-radius: 4px;
    padding: 5px 14px;
    font-weight: 600;
}}

QPushButton[primary="true"]:hover {{
    background-color: {COLOUR_RED_HOVER};
    border-color: {COLOUR_RED_HOVER};
}}

QPushButton[primary="true"]:pressed {{
    background-color: {COLOUR_RED_PRESSED};
    border-color: {COLOUR_RED_PRESSED};
}}

QPushButton[primary="true"]:disabled {{
    background-color: #E8A0AE;
    color: {COLOUR_WHITE};
    border-color: #E8A0AE;
}}

/* Flat buttons (Advanced expand, etc.) */
QPushButton:flat {{
    background-color: transparent;
    border: none;
    color: {COLOUR_GREY};
    padding: 2px 4px;
}}

QPushButton:flat:hover {{
    color: {COLOUR_RED};
    background-color: transparent;
}}

/* ── Tab widget ─────────────────────────────────────────────────────────── */
QTabWidget::pane {{
    border-top: 2px solid {COLOUR_RED};
    border-left: 1px solid {COLOUR_BORDER};
    border-right: 1px solid {COLOUR_BORDER};
    border-bottom: 1px solid {COLOUR_BORDER};
    border-radius: 0px 0px 4px 4px;
    background-color: {COLOUR_WHITE};
}}

QTabBar::tab {{
    background-color: {COLOUR_SURFACE};
    color: {COLOUR_GREY};
    border: 1px solid {COLOUR_BORDER};
    border-bottom: none;
    border-radius: 4px 4px 0px 0px;
    padding: 6px 16px;
    margin-right: 2px;
    min-width: 80px;
}}

QTabBar::tab:selected {{
    background-color: {COLOUR_WHITE};
    color: {COLOUR_RED};
    border-color: {COLOUR_BORDER};
    border-bottom: 2px solid {COLOUR_WHITE};
    font-weight: 600;
}}

QTabBar::tab:hover:!selected {{
    background-color: {COLOUR_WHITE};
    color: #1A1A1A;
}}

/* ── Group boxes ────────────────────────────────────────────────────────── */
QGroupBox {{
    border: 1px solid {COLOUR_BORDER};
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 6px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0px 6px;
    left: 10px;
    color: {COLOUR_GREY};
    font-size: 9pt;
    font-weight: 600;
}}

/* ── Line edits ─────────────────────────────────────────────────────────── */
QLineEdit {{
    background-color: {COLOUR_WHITE};
    border: 1px solid {COLOUR_BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 20px;
    selection-background-color: {COLOUR_RED};
    selection-color: {COLOUR_WHITE};
}}

QLineEdit:focus {{
    border: 1px solid {COLOUR_BORDER};
    border-bottom: 2px solid {COLOUR_RED};
    border-radius: 4px 4px 0px 0px;
}}

QLineEdit:disabled {{
    background-color: {COLOUR_SURFACE};
    color: #ABABAB;
    border-color: {COLOUR_BORDER};
}}

QLineEdit[readOnly="true"] {{
    background-color: {COLOUR_SURFACE};
}}

/* ── Combo boxes ────────────────────────────────────────────────────────── */
QComboBox {{
    background-color: {COLOUR_WHITE};
    border: 1px solid {COLOUR_BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 20px;
    selection-background-color: {COLOUR_RED};
}}

QComboBox:focus {{
    border-bottom: 2px solid {COLOUR_RED};
    border-radius: 4px 4px 0px 0px;
}}

QComboBox:disabled {{
    background-color: {COLOUR_SURFACE};
    color: #ABABAB;
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {COLOUR_GREY};
    width: 0px;
    height: 0px;
    margin-right: 6px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLOUR_WHITE};
    border: 1px solid {COLOUR_BORDER};
    border-radius: 4px;
    selection-background-color: {COLOUR_SURFACE};
    selection-color: {COLOUR_RED};
    outline: none;
    padding: 2px;
}}

/* ── Spin boxes ─────────────────────────────────────────────────────────── */
QSpinBox {{
    background-color: {COLOUR_WHITE};
    border: 1px solid {COLOUR_BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 20px;
    selection-background-color: {COLOUR_RED};
}}

QSpinBox:focus {{
    border-bottom: 2px solid {COLOUR_RED};
    border-radius: 4px 4px 0px 0px;
}}

QSpinBox::up-button, QSpinBox::down-button {{
    border: none;
    background-color: transparent;
    width: 16px;
}}

/* ── Check boxes ────────────────────────────────────────────────────────── */
QCheckBox {{
    spacing: 6px;
    color: #1A1A1A;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1.5px solid {COLOUR_BORDER};
    border-radius: 3px;
    background-color: {COLOUR_WHITE};
}}

QCheckBox::indicator:hover {{
    border-color: {COLOUR_GREY};
}}

QCheckBox::indicator:checked {{
    background-color: {COLOUR_RED};
    border-color: {COLOUR_RED};
    image: none;
}}

QCheckBox::indicator:checked:hover {{
    background-color: {COLOUR_RED_HOVER};
    border-color: {COLOUR_RED_HOVER};
}}

QCheckBox:disabled {{
    color: #ABABAB;
}}

QCheckBox::indicator:disabled {{
    border-color: {COLOUR_BORDER};
    background-color: {COLOUR_SURFACE};
}}

/* ── Radio buttons ──────────────────────────────────────────────────────── */
QRadioButton {{
    spacing: 6px;
    color: #1A1A1A;
}}

QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1.5px solid {COLOUR_BORDER};
    border-radius: 8px;
    background-color: {COLOUR_WHITE};
}}

QRadioButton::indicator:checked {{
    background-color: {COLOUR_RED};
    border-color: {COLOUR_RED};
}}

QRadioButton::indicator:hover {{
    border-color: {COLOUR_GREY};
}}

/* ── Progress bar ───────────────────────────────────────────────────────── */
QProgressBar {{
    background-color: {COLOUR_BORDER};
    border: none;
    border-radius: 3px;
    height: 6px;
    text-align: center;
    color: transparent;
}}

QProgressBar::chunk {{
    background-color: {COLOUR_RED};
    border-radius: 3px;
}}

/* ── List widgets (sidebar navigation + incident selector) ──────────────── */
QListWidget {{
    border: none;
    background-color: {COLOUR_SURFACE};
    outline: none;
    padding: 4px 0px;
}}

QListWidget::item {{
    padding: 8px 12px;
    border-radius: 0px;
    color: #1A1A1A;
    border-left: 3px solid transparent;
}}

QListWidget::item:hover {{
    background-color: #E8E8E8;
}}

QListWidget::item:selected {{
    background-color: #EAEAEA;
    color: {COLOUR_RED};
    border-left: 3px solid {COLOUR_RED};
    font-weight: 600;
}}

/* Section header items (non-selectable, grey background) */
QListWidget::item:disabled {{
    color: {COLOUR_GREY};
    background-color: #DEDEDE;
    font-weight: 600;
    font-size: 9pt;
    border-left: 3px solid transparent;
}}

/* ── Plain text edit (log viewer) ───────────────────────────────────────── */
QPlainTextEdit {{
    background-color: #FAFAFA;
    border: 1px solid {COLOUR_BORDER};
    border-radius: 4px;
    color: #1A1A1A;
    selection-background-color: {COLOUR_RED};
    selection-color: {COLOUR_WHITE};
}}

/* ── Scroll bars ────────────────────────────────────────────────────────── */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background-color: {COLOUR_BORDER};
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {COLOUR_GREY};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 0px;
}}

QScrollBar::handle:horizontal {{
    background-color: {COLOUR_BORDER};
    border-radius: 4px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {COLOUR_GREY};
}}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* ── Scroll areas ───────────────────────────────────────────────────────── */
QScrollArea {{
    border: none;
    background-color: transparent;
}}

QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}

/* ── Status bar ─────────────────────────────────────────────────────────── */
QStatusBar {{
    background-color: {COLOUR_WHITE};
    border-top: 1px solid {COLOUR_BORDER};
    font-size: 9pt;
    color: {COLOUR_GREY};
    padding: 2px 6px;
}}

/* ── Labels ─────────────────────────────────────────────────────────────── */
QLabel[subtitle="true"] {{
    color: {COLOUR_GREY};
    font-style: italic;
    margin-bottom: 4px;
}}

QLabel[lastrun="true"] {{
    color: {COLOUR_GREY};
    font-size: 9pt;
}}

/* ── Tool tips ──────────────────────────────────────────────────────────── */
QToolTip {{
    background-color: #1A1A1A;
    color: {COLOUR_WHITE};
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 9pt;
}}

/* ── Message box ────────────────────────────────────────────────────────── */
QMessageBox {{
    background-color: {COLOUR_WHITE};
}}

QMessageBox QPushButton {{
    min-width: 80px;
}}
"""


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def apply_theme(app: "QApplication") -> None:
    """Apply the Fluent QSS stylesheet and Segoe UI font to *app*."""
    app.setStyleSheet(GLOBAL_QSS)
    app.setFont(QFont(FONT_FAMILY, 10))


def apply_mica(window: "QMainWindow") -> None:
    """Enable Windows 11 Mica background effect on *window*.

    Silently no-ops on Windows 10 and non-Windows platforms.
    Requires the window to already be visible (call after ``window.show()``).
    """
    if sys.platform != "win32":
        return
    try:
        from ctypes import byref, c_int
        hwnd = int(window.winId())
        # DWMWA_SYSTEMBACKDROP_TYPE = 38; value 2 = Mica
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 38, byref(c_int(2)), ctypes.sizeof(c_int)
        )
    except (AttributeError, OSError):
        pass
