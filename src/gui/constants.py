#!/usr/bin/env python3
"""
GUI Constants
=============

Window titles, default sizes, style tokens, and shared constants
used across the GUI application.
"""

APP_NAME = "TXR Automation"
APP_VERSION = "1.0.0"
DEFAULT_WINDOW_SIZE = (1024, 720)
LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]

# File dialog filters
CSV_FILTER = "CSV Files (*.csv);;All Files (*)"
YAML_FILTER = "YAML Files (*.yaml *.yml);;All Files (*)"
SQL_FILTER = "SQL Files (*.sql);;All Files (*)"
SQLITE_FILTER = "SQLite Databases (*.db);;All Files (*)"
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
    ("buyer", "Buyer ID Validation (7_5, 7_6)"),
    ("seller", "Seller ID Validation (7_7, 7_8)"),
    ("inconsistent-buyer", "Inconsistent Buyer ID (7_37, 7_38)"),
    ("inconsistent-seller", "Inconsistent Seller ID (7_39, 7_40)"),
    ("ftbdm", "Field 27 Buyer Decision Maker"),
    ("ftsdm", "Field 28 Seller Decision Maker"),
    ("pricing", "Pricing Validation"),
    ("non-zero-qty", "Non-Zero Net Quantity"),
    ("non-zero-amt", "Non-Zero Net Amount"),
]

# Mapping of incident names to their known incident code patterns
# Used for autodiscovery of files in batch directories
INCIDENT_CODE_PATTERNS = {
    "buyer": ["7_5", "7_6"],
    "seller": ["7_7", "7_8"],
    "inconsistent-buyer": ["7_37", "7_38"],
    "inconsistent-seller": ["7_39", "7_40"],
    "ftbdm": ["7_27"],
    "ftsdm": ["7_28"],
    "pricing": ["7_33"],
    "non-zero-qty": ["7_6_qty"],
    "non-zero-amt": ["7_6_amt"],
}

# Mapping of incident names to their script module paths
INCIDENT_SCRIPT_MODULES = {
    "buyer": "accuracy_testing.scripts.buyer_id_validation",
    "seller": "accuracy_testing.scripts.seller_id_validation",
    "inconsistent-buyer": "accuracy_testing.scripts.inconsistent_buyer_id_validation",
    "inconsistent-seller": "accuracy_testing.scripts.inconsistent_seller_id_validation",
    "ftbdm": "accuracy_testing.scripts.validate_ftbdm",
    "ftsdm": "accuracy_testing.scripts.validate_ftsdm",
    "pricing": "accuracy_testing.scripts.pricing_validation",
    "non-zero-qty": "accuracy_testing.scripts.non_zero_net_quantity",
    "non-zero-amt": "accuracy_testing.scripts.non_zero_net_amount",
}