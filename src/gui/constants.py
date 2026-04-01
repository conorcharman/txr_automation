#!/usr/bin/env python3
"""
GUI Constants
=============

Window titles, default sizes, style tokens, and shared constants
used across the GUI application.
"""

APP_NAME = "TXR Automation"
APP_VERSION = "1.0.0"

# ── AJ Bell brand colours ──────────────────────────────────────────────────
COLOUR_RED = "#D50032"
COLOUR_RED_HOVER = "#B8002B"
COLOUR_RED_PRESSED = "#9E0025"
COLOUR_GREY = "#6A737B"
COLOUR_WHITE = "#FFFFFF"
COLOUR_SURFACE = "#F3F3F3"
COLOUR_BORDER = "#E0E0E0"

# ── Fluent design font ─────────────────────────────────────────────────────
FONT_FAMILY = "Segoe UI"
DEFAULT_WINDOW_SIZE = (1024, 720)
LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]

# File dialog filters
CSV_FILTER = "CSV Files (*.csv);;All Files (*)"
YAML_FILTER = "YAML Files (*.yaml *.yml);;All Files (*)"
SQL_FILTER = "SQL Files (*.sql);;All Files (*)"
SQLITE_FILTER = "SQLite Databases (*.db);;All Files (*)"
XML_FILTER = "XML Files (*.xml);;All Files (*)"
ALL_CONFIG_FILTER = (
    "Config Files (*.yaml *.yml);;CSV Files (*.csv);;All Files (*)"
)

# Monospace font for log viewer
LOG_FONT_FAMILY = "Consolas"
LOG_FONT_SIZE = 9

# Status bar messages
STATUS_READY = "Ready"
STATUS_RUNNING = "Running: {}"
STATUS_SUCCESS = "Success"
STATUS_FAILED = "Failed — exit code {}"
# Accuracy testing incidents (name, description)
ACCURACY_INCIDENTS = [
    ("buyer", "Buyer ID Validation (7_35, 7_37, 7_39)"),
    ("seller", "Seller ID Validation (16_19, 16_21, 16_23)"),
    ("inconsistent-buyer", "Inconsistent Buyer ID (7_66)"),
    ("inconsistent-seller", "Inconsistent Seller ID (16_20)"),
    ("ftbdm", "Field 27 Buyer Decision Maker (12_17)"),
    ("ftsdm", "Field 28 Seller Decision Maker (21_17)"),
    ("incorrect_net_amount", "Incorrect Net Amount Validation (35_3)"),
    ("non-zero-qty", "Non-Zero Net Quantity (7_6)"),
    ("non-zero-amt", "Non-Zero Net Amount (7_42)"),
]

# Mapping of incident names to their known incident code patterns
# Used for autodiscovery of files in batch directories
INCIDENT_CODE_PATTERNS = {
    "buyer": ["7_35", "7_37", "7_39"],
    "seller": ["16_19", "16_21", "16_23"],
    "inconsistent-buyer": ["7_66"],
    "inconsistent-seller": ["16_20"],
    "ftbdm": ["12_17"],
    "ftsdm": ["21_17"],
    "incorrect_net_amount": ["35_3"],
    "non-zero-qty": ["7_6"],
    "non-zero-amt": ["7_42"],
}

# Mapping of incident names to their script module paths
INCIDENT_SCRIPT_MODULES = {
    "buyer": "accuracy_testing.scripts.buyer_id_validation",
    "seller": "accuracy_testing.scripts.seller_id_validation",
    "inconsistent-buyer": "accuracy_testing.scripts.inconsistent_buyer_id_validation",
    "inconsistent-seller": "accuracy_testing.scripts.inconsistent_seller_id_validation",
    "ftbdm": "accuracy_testing.scripts.validate_ftbdm",
    "ftsdm": "accuracy_testing.scripts.validate_ftsdm",
    "incorrect_net_amount": "accuracy_testing.scripts.incorrect_net_amount_validation",
    "non-zero-qty": "accuracy_testing.scripts.non_zero_net_quantity",
    "non-zero-amt": "accuracy_testing.scripts.non_zero_net_amount",
}

# Testing period choices
FISCAL_YEARS = ["FY24", "FY25", "FY26", "FY27"]
QUARTERS = ["Q1", "Q2", "Q3", "Q4"]

# Mapping of incident selector names to their per-panel QSettings prefix.
# Used by Run All to read cached field values from individual tiles.
INCIDENT_SETTINGS_PREFIX = {
    "buyer": "accuracy.buyer_id",
    "seller": "accuracy.seller_id",
    "inconsistent-buyer": "accuracy.inconsistent_buyer",
    "inconsistent-seller": "accuracy.inconsistent_seller",
    "ftbdm": "accuracy.ftbdm",
    "ftsdm": "accuracy.ftsdm",
    "incorrect_net_amount": "accuracy.incorrect_net_amount",
    "non-zero-qty": "accuracy.non_zero_qty",
    "non-zero-amt": "accuracy.non_zero_amt",
}