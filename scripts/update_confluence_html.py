#!/usr/bin/env python3
"""
Update local Confluence HTML files from space export.

Extracts main-content from each Confluence export file and wraps it in the
local clean HTML template, remapping cross-page links to local filenames.
"""
import os
import re

EXPORT_DIR = r"C:\Users\ccharm\Downloads\Confluence-space-export-101905.html\712020d9c9879a14a24caf9d4e4b5350a38d83"
LOCAL_DIR = r"C:\Users\ccharm\Documents\GitHub\txr_automation\documentation\confluence"

# (export_filename, local_filename, breadcrumb_title)
MAPPING = [
    ("TXR-Automation-Documentation_3436183786.html", "00_index.html", "TXR Automation Documentation"),
    ("1.-Project-Overview_3436085615.html", "01_project_overview.html", "Project Overview"),
    ("2a.-System-Architecture_3436151028.html", "02a_system_architecture.html", "System Architecture"),
    ("3436511611.html", "02b_data_flow.html", "Data Flow &amp; Integration"),
    ("3436642445.html", "03a_migration_plan_and_status.html", "Migration Plan &amp; Status"),
    ("3b.-VBA-to-Python-Traceability-Matrix_3436544240.html", "03b_traceability_matrix.html", "VBA-to-Python Traceability Matrix"),
    ("3c.-Changelog_3436183835.html", "03c_changelog.html", "Changelog"),
    ("4a.-Getting-Started_3436511627.html", "04a_getting_started.html", "Getting Started"),
    ("3436052854.html", "04b_coding_standards.html", "Coding Standards &amp; Conventions"),
    ("4c.-Configuration-System_3436282107.html", "04c_configuration_system.html", "Configuration System"),
    ("4d.-Core-Library-API-Reference_3436609707.html", "04d_core_api_reference.html", "Core Library API Reference"),
    ("4e.-Testing-Guide_3436544256.html", "04e_testing_guide.html", "Testing Guide"),
    ("5.-User-Guides_3436642461.html", "05_user_guides.html", "User Guides"),
    ("5j.-CLI-Command-Reference_3436314896.html", "05j_cli_command_reference.html", "CLI Command Reference"),
    ("6a.-Business-Logic-Preservation_3436675223.html", "06a_business_logic_preservation.html", "Business Logic Preservation"),
    ("3436642477.html", "06b_test_coverage_report.html", "Test Coverage &amp; Validation Report"),
    ("3436609723.html", "07a_deployment_plan.html", "Deployment &amp; Transition Plan"),
    ("7b.-Performance-Benchmarks_3436642493.html", "07b_performance_benchmarks.html", "Performance Benchmarks"),
]

# Map export hrefs -> local hrefs
LINK_MAP = {
    "TXR-Automation-Documentation_3436183786.html": "00_index.html",
    "index.html": "00_index.html",
    "1.-Project-Overview_3436085615.html": "01_project_overview.html",
    "2a.-System-Architecture_3436151028.html": "02a_system_architecture.html",
    "3436511611.html": "02b_data_flow.html",
    "3436642445.html": "03a_migration_plan_and_status.html",
    "3b.-VBA-to-Python-Traceability-Matrix_3436544240.html": "03b_traceability_matrix.html",
    "3c.-Changelog_3436183835.html": "03c_changelog.html",
    "4a.-Getting-Started_3436511627.html": "04a_getting_started.html",
    "3436052854.html": "04b_coding_standards.html",
    "4c.-Configuration-System_3436282107.html": "04c_configuration_system.html",
    "4d.-Core-Library-API-Reference_3436609707.html": "04d_core_api_reference.html",
    "4e.-Testing-Guide_3436544256.html": "04e_testing_guide.html",
    "5.-User-Guides_3436642461.html": "05_user_guides.html",
    "5j.-CLI-Command-Reference_3436314896.html": "05j_cli_command_reference.html",
    "6a.-Business-Logic-Preservation_3436675223.html": "06a_business_logic_preservation.html",
    "3436642477.html": "06b_test_coverage_report.html",
    "3436609723.html": "07a_deployment_plan.html",
    "7b.-Performance-Benchmarks_3436642493.html": "07b_performance_benchmarks.html",
}

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title} \u2014 TXR Automation</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 960px; margin: 0 auto; padding: 20px; color: #172B4D; }}
        h1, h2, h3, h4 {{ color: #172B4D; }}
        table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
        th, td {{ border: 1px solid #DFE1E6; padding: 8px 12px; text-align: left; vertical-align: top; }}
        th {{ background-color: #F4F5F7; font-weight: 600; }}
        a {{ color: #0052CC; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .breadcrumb {{ color: #6B778C; font-size: 0.9em; margin-bottom: 8px; }}
        .last-updated {{ color: #6B778C; font-size: 0.85em; font-style: italic; }}
        code {{ background: #F4F5F7; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }}
        pre {{ background: #F4F5F7; padding: 16px; border-radius: 3px; overflow-x: auto; font-family: Monaco, 'Courier New', monospace; font-size: 0.88em; white-space: pre; margin: 0; }}
        .confluence-anchor-link {{ display: none; }}
        .code.panel {{ border: 1px solid #DFE1E6; border-radius: 3px; margin: 16px 0; overflow: hidden; }}
        .codeContent {{ padding: 0; }}
        .syntaxhighlighter-pre {{ background: #F4F5F7; padding: 16px; margin: 0; overflow-x: auto; font-family: Monaco, 'Courier New', monospace; font-size: 0.88em; border: none; border-radius: 0; }}
        .table-wrap {{ overflow-x: auto; margin: 16px 0; }}
    </style>
</head>
<body>
{breadcrumb}
{content}

</body>
</html>
"""


def extract_main_content(html: str) -> str:
    """Extract content from the main-content wiki div."""
    marker = '<div id="main-content" class="wiki-content group">'
    start_idx = html.find(marker)
    if start_idx == -1:
        print("  WARNING: main-content div not found, using full body")
        body_start = html.find("<body")
        if body_start != -1:
            body_start = html.find(">", body_start) + 1
            body_end = html.rfind("</body>")
            return html[body_start:body_end].strip()
        return html

    content_start = start_idx + len(marker)

    # Walk forward counting div depth to find the matching closing </div>
    pos = content_start
    depth = 1
    end_pos = len(html)
    while depth > 0 and pos < len(html):
        next_open = html.find("<div", pos)
        next_close = html.find("</div>", pos)
        if next_close == -1:
            break
        if next_open != -1 and next_open < next_close:
            depth += 1
            pos = next_open + 4
        else:
            depth -= 1
            end_pos = next_close
            pos = next_close + 6

    return html[content_start:end_pos].strip()


def clean_last_updated(content: str) -> str:
    """Replace Confluence inline-colour date paragraph with a class-based one."""
    # Pattern: <p data-colorid="..." style="..."><style>...</style>Last updated: DATE</p>
    pattern = (
        r'<p\s[^>]*data-colorid="[^"]*"[^>]*>\s*'
        r'<style>[^<]*</style>\s*'
        r'(Last updated:[^<]*?)\s*</p>'
    )
    return re.sub(pattern, r'<p class="last-updated">\1</p>', content, count=1)


def remap_links(content: str) -> str:
    """Replace export file references with local filenames in href attributes."""
    for old, new in LINK_MAP.items():
        content = content.replace(f'href="{old}"', f'href="{new}"')
        content = content.replace(f'href="{old}#', f'href="{new}#')
    return content


def process_file(export_file: str, local_file: str, title: str) -> None:
    export_path = os.path.join(EXPORT_DIR, export_file)
    local_path = os.path.join(LOCAL_DIR, local_file)

    if not os.path.exists(export_path):
        print(f"  SKIP (missing): {export_file}")
        return

    with open(export_path, "r", encoding="utf-8") as f:
        html = f.read()

    content = extract_main_content(html)
    content = clean_last_updated(content)
    content = remap_links(content)

    if local_file == "00_index.html":
        breadcrumb = ""
    else:
        breadcrumb = (
            f'<p class="breadcrumb">'
            f'<a href="00_index.html">TXR Automation Documentation</a>'
            f" &rsaquo; {title}"
            f"</p>"
        )

    plain_title = title.replace("&amp;", "&")

    output = HTML_TEMPLATE.format(
        title=plain_title,
        breadcrumb=breadcrumb,
        content=content,
    )

    with open(local_path, "w", encoding="utf-8") as f:
        f.write(output)

    size_kb = len(output) // 1024
    print(f"  Updated: {local_file} ({size_kb} KB)")


if __name__ == "__main__":
    print(f"Processing {len(MAPPING)} files...\n")
    for export_file, local_file, title in MAPPING:
        process_file(export_file, local_file, title)
    print("\nDone.")
