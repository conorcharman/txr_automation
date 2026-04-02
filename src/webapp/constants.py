#!/usr/bin/env python3
"""
Web Application Constants
==========================

Shared constants used across the TXR Automation web application,
mirroring the capabilities exposed by the desktop GUI.
"""

APP_NAME = "TXR Automation"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "Transaction Reporting Automation Suite"

# Navigation sections (id, title, description, icon_class)
NAV_SECTIONS = [
    {
        "id": "accuracy",
        "title": "Accuracy Testing",
        "description": (
            "Run ID validation scripts for buyer, seller, inconsistent ID, "
            "decision maker, pricing, and non-zero quantity/amount incidents."
        ),
        "icon": "bi-check2-circle",
        "colour": "primary",
    },
    {
        "id": "replay",
        "title": "Replay Processing",
        "description": (
            "Process replay files through Phase 2 and Phase 3 pipelines, "
            "merging inconsistent ID summaries and converting XLSX to CSV."
        ),
        "icon": "bi-arrow-repeat",
        "colour": "success",
    },
    {
        "id": "firds",
        "title": "FIRDS Reference Data",
        "description": (
            "Manage the FCA FIRDS reportability cache: refresh, check "
            "reportability for individual instruments, and backfill historical data."
        ),
        "icon": "bi-database",
        "colour": "info",
    },
    {
        "id": "gleif",
        "title": "GLEIF Reference Data",
        "description": (
            "Manage the GLEIF LEI lookup cache: refresh, check individual "
            "LEIs, and backfill historical entity data."
        ),
        "icon": "bi-building",
        "colour": "warning",
    },
    {
        "id": "utilities",
        "title": "Utilities",
        "description": (
            "Miscellaneous utility tools: XLSX to CSV conversion, "
            "CSV collation, and other data preparation tasks."
        ),
        "icon": "bi-tools",
        "colour": "secondary",
    },
]

# Bootstrap colour classes for status badges.
# Reserved for future phases when script run status is displayed.
STATUS_COLOURS = {
    "success": "success",
    "error": "danger",
    "warning": "warning",
    "running": "primary",
    "idle": "secondary",
}
