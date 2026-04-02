#!/usr/bin/env python3
"""
Dashboard Routes
=================

Main dashboard and section landing pages for the web application.
Each section corresponds to a tab in the desktop GUI.
"""

from flask import Blueprint, render_template

from webapp.constants import APP_NAME, APP_VERSION, NAV_SECTIONS

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/")
def index() -> str:
    """Render the main dashboard page.

    Returns:
        Rendered HTML dashboard showing all available automation sections.
    """
    return render_template(
        "dashboard.html",
        app_name=APP_NAME,
        app_version=APP_VERSION,
        sections=NAV_SECTIONS,
        active_section=None,
    )


@dashboard_bp.get("/section/<section_id>")
def section(section_id: str) -> str | tuple[str, int]:
    """Render a section landing page.

    Args:
        section_id: The section identifier (accuracy, replay, firds, gleif,
            utilities).

    Returns:
        Rendered HTML for the section, or 404 if the section is unknown.
    """
    section_data = next(
        (s for s in NAV_SECTIONS if s["id"] == section_id), None
    )
    if section_data is None:
        return render_template(
            "404.html",
            app_name=APP_NAME,
            app_version=APP_VERSION,
            sections=NAV_SECTIONS,
        ), 404

    return render_template(
        "section.html",
        app_name=APP_NAME,
        app_version=APP_VERSION,
        sections=NAV_SECTIONS,
        active_section=section_data,
    )
