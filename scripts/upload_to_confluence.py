#!/usr/bin/env python3
"""
Confluence Page Uploader
========================

Uploads the HTML documentation suite to Confluence Cloud as a hierarchical
page tree using the REST API v1.

Prerequisites:
    pip install requests beautifulsoup4 premailer

Usage:
    python scripts/upload_to_confluence.py

    The script prompts for:
        - Confluence base URL  (e.g. https://yourorg.atlassian.net)
        - Email address        (your Atlassian account email)
        - API token            (generate at https://id.atlassian.com/manage-profile/security/api-tokens)

    These can also be set as environment variables:
        CONFLUENCE_BASE_URL
        CONFLUENCE_EMAIL
        CONFLUENCE_API_TOKEN
        CONFLUENCE_SPACE_KEY   (default: ~712020d9c9879a14a24caf9d4e4b5350a38d83)

Version: 1.0
Date: 25 March 2026
"""

import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import requests
except ImportError:
    sys.exit("ERROR: 'requests' is required.  Install with:  pip install requests")

try:
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("ERROR: 'beautifulsoup4' is required.  Install with:  pip install beautifulsoup4")

# Optional: premailer for CSS inlining (fallback if not installed)
try:
    from premailer import Premailer
    PREMAILER_AVAILABLE = True
except ImportError:
    PREMAILER_AVAILABLE = False


# ---------------------------------------------------------------------------
# Page tree definition
# ---------------------------------------------------------------------------

@dataclass
class PageDef:
    """Definition of a single Confluence page."""

    filename: str
    title: str
    children: List["PageDef"] = field(default_factory=list)


# The hierarchical page tree — mirrors the index table
PAGE_TREE: List[PageDef] = [
    PageDef(
        filename="00_index.html",
        title="TXR Automation Documentation",
        children=[
            PageDef(
                filename="01_project_overview.html",
                title="1. Project Overview",
            ),
            PageDef(
                filename="02a_system_architecture.html",
                title="2a. System Architecture",
                children=[
                    PageDef(
                        filename="02b_data_flow.html",
                        title="2b. Data Flow & Integration",
                    ),
                ],
            ),
            PageDef(
                filename="03a_migration_plan_and_status.html",
                title="3a. Migration Plan & Status",
                children=[
                    PageDef(
                        filename="03b_traceability_matrix.html",
                        title="3b. VBA-to-Python Traceability Matrix",
                    ),
                    PageDef(
                        filename="03c_changelog.html",
                        title="3c. Changelog",
                    ),
                ],
            ),
            PageDef(
                filename="04a_getting_started.html",
                title="4a. Getting Started",
                children=[
                    PageDef(
                        filename="04b_coding_standards.html",
                        title="4b. Coding Standards & Conventions",
                    ),
                    PageDef(
                        filename="04c_configuration_system.html",
                        title="4c. Configuration System",
                    ),
                    PageDef(
                        filename="04d_core_api_reference.html",
                        title="4d. Core Library API Reference",
                    ),
                    PageDef(
                        filename="04e_testing_guide.html",
                        title="4e. Testing Guide",
                    ),
                ],
            ),
            PageDef(
                filename="05_user_guides.html",
                title="5. User Guides",
                children=[
                    PageDef(
                        filename="05j_cli_command_reference.html",
                        title="5j. CLI Command Reference",
                    ),
                ],
            ),
            PageDef(
                filename="06a_business_logic_preservation.html",
                title="6a. Business Logic Preservation",
                children=[
                    PageDef(
                        filename="06b_test_coverage_report.html",
                        title="6b. Test Coverage & Validation Report",
                    ),
                ],
            ),
            PageDef(
                filename="07a_deployment_plan.html",
                title="7a. Deployment & Transition Plan",
                children=[
                    PageDef(
                        filename="07b_performance_benchmarks.html",
                        title="7b. Performance Benchmarks",
                    ),
                ],
            ),
        ],
    ),
]


# ---------------------------------------------------------------------------
# HTML → Confluence storage format converter
# ---------------------------------------------------------------------------

def extract_and_inline_body(html_path: Path) -> str:
    """
    Read an HTML file, inline its CSS, and return just the inner <body>
    content as Confluence storage-format XHTML.

    Args:
        html_path: Path to the HTML file.

    Returns:
        Confluence-compatible XHTML string (body contents only).
    """
    raw_html = html_path.read_text(encoding="utf-8")

    # --- CSS inlining ---
    if PREMAILER_AVAILABLE:
        # premailer converts <style> rules into inline style="" attributes
        inlined = Premailer(
            raw_html,
            remove_classes=True,
            strip_important=True,
            keep_style_tags=False,
            cssutils_logging_level="CRITICAL",
        ).transform()
    else:
        # Fallback: manual inline via regex + BeautifulSoup
        inlined = _manual_inline_css(raw_html)

    # --- Extract <body> inner content ---
    soup = BeautifulSoup(inlined, "html.parser")
    body = soup.find("body")
    if body is None:
        # No <body> tag — use entire content
        body_html = inlined
    else:
        body_html = body.decode_contents()

    # --- Clean up for Confluence storage format ---
    # Remove breadcrumb navigation (inter-file links don't work in Confluence)
    body_html = _strip_breadcrumbs_and_nav(body_html)

    # Convert heading id attributes to Confluence anchor macros so TOC links work
    body_html = _inject_confluence_anchors(body_html)

    # Convert local .html links to Confluence cross-page links
    body_html = _convert_cross_page_links(body_html)

    # Convert <pre> blocks to Confluence noformat/code macros
    body_html = _convert_pre_to_confluence_macros(body_html)

    return body_html


def _build_filename_title_map(pages: List[PageDef]) -> Dict[str, str]:
    """Build a flat mapping of filename → Confluence page title from the page tree."""
    mapping: Dict[str, str] = {}
    for page in pages:
        mapping[page.filename] = page.title
        if page.children:
            mapping.update(_build_filename_title_map(page.children))
    return mapping


# Cached filename→title mapping built from PAGE_TREE (populated lazily)
_FILENAME_TITLE_MAP: Optional[Dict[str, str]] = None


def _get_filename_title_map() -> Dict[str, str]:
    """Return the filename → title mapping, building it on first call."""
    global _FILENAME_TITLE_MAP
    if _FILENAME_TITLE_MAP is None:
        _FILENAME_TITLE_MAP = _build_filename_title_map(PAGE_TREE)
    return _FILENAME_TITLE_MAP


def _inject_confluence_anchors(html: str) -> str:
    """
    Convert heading id attributes to Confluence anchor macros.

    For every <h1>–<h4> with an id attribute, insert an
    ``<ac:structured-macro ac:name="anchor">`` element before the heading
    so that ``<a href="#id">`` TOC links resolve correctly in Confluence.
    """
    soup = BeautifulSoup(html, "html.parser")
    for heading in soup.find_all(re.compile(r"^h[1-4]$")):
        anchor_id = heading.get("id")
        if not anchor_id:
            continue
        # Build the Confluence anchor macro
        macro = soup.new_tag("ac:structured-macro", attrs={"ac:name": "anchor"})
        param = soup.new_tag("ac:parameter", attrs={"ac:name": ""})
        param.string = anchor_id
        macro.append(param)
        heading.insert_before(macro)
        del heading["id"]
    return str(soup)


def _convert_cross_page_links(html: str) -> str:
    """
    Replace local ``href="file.html"`` links with Confluence ``<ac:link>`` macros.

    Links whose target filename appears in PAGE_TREE are converted to
    Confluence page links; unknown targets are replaced with ``href="#"``.
    """
    title_map = _get_filename_title_map()
    soup = BeautifulSoup(html, "html.parser")

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if not href.endswith(".html") and ".html#" not in href:
            continue
        # Split href into filename and optional anchor
        if "#" in href:
            filename, _anchor = href.split("#", 1)
        else:
            filename = href
        title = title_map.get(filename)
        if title:
            # Build <ac:link><ri:page ri:content-title="Title"/><ac:plain-text-link-body>…</ac:plain-text-link-body></ac:link>
            link_text = a_tag.get_text()
            ac_link = soup.new_tag("ac:link")
            ri_page = soup.new_tag("ri:page", attrs={"ri:content-title": title})
            ac_link.append(ri_page)
            link_body = soup.new_tag("ac:plain-text-link-body")
            link_body.append(soup.new_string(f"<![CDATA[{link_text}]]>"))
            ac_link.append(link_body)
            a_tag.replace_with(ac_link)
        else:
            a_tag["href"] = "#"
    return str(soup)


# Box-drawing Unicode characters that indicate a diagram rather than code
_BOX_DRAWING_CHARS = frozenset("┌┐└┘─│├┤┬┴┼╔╗╚╝═║↓↑→←↔↕")

# Characters that render at inconsistent widths in some monospace fonts
# (notably Courier New, which Confluence may fall back to on Windows).
# We normalise these to pure ASCII equivalents in diagram text so alignment
# is preserved regardless of which monospace font Confluence renders with.
_DIAGRAM_CHAR_NORMALISATION: Dict[str, str] = {
    "•": "*",   # U+2022 BULLET — often wider than 1ch in Courier New
    "·": ".",   # U+00B7 MIDDLE DOT
    "→": ">",   # U+2192 RIGHTWARDS ARROW
    "←": "<",   # U+2190 LEFTWARDS ARROW
    "↓": "v",   # U+2193 DOWNWARDS ARROW
    "↑": "^",   # U+2191 UPWARDS ARROW
    "↔": "<>",  # U+2194 LEFT RIGHT ARROW
    "↕": "^v",  # U+2195 UP DOWN ARROW
}


def _normalise_diagram_text(text: str) -> str:
    """Replace non-ASCII chars that may render at inconsistent widths."""
    for src, dst in _DIAGRAM_CHAR_NORMALISATION.items():
        text = text.replace(src, dst)
    return text


def _convert_pre_to_confluence_macros(html: str) -> str:
    """
    Convert ``<pre>`` blocks to Confluence storage-format macros.

    ``<pre>`` blocks whose text contains box-drawing characters are converted
    to ``code`` macros with ``language="text"`` — this forces Confluence Cloud
    to use its high-quality monospace font stack (SFMono, Menlo, Consolas, …)
    rather than the system default (Courier New on Windows), ensuring that
    box-drawing characters render at consistent widths.  The bullet character
    ``•`` and arrow characters are also normalised to ASCII equivalents before
    insertion to prevent per-glyph width differences from breaking alignment.

    All other ``<pre>`` blocks are converted to ``code`` macros with the
    language inferred from a ``class="language-*"`` attribute on the ``<pre>``
    or its first child ``<code>`` element (defaulting to ``text``).

    ``ac:plain-text-body`` requires a raw XML CDATA section.  BeautifulSoup
    HTML-escapes any string it serialises, so we use plain-text placeholders
    during tree manipulation and perform a final string replacement to inject
    the unescaped ``<![CDATA[...]]>`` markers after serialisation.

    Args:
        html: Confluence storage-format XHTML string.

    Returns:
        XHTML string with ``<pre>`` blocks replaced by Confluence macros.
    """
    soup = BeautifulSoup(html, "html.parser")
    # Maps placeholder token → raw CDATA string to inject after serialisation.
    # Placeholders use only alphanumeric/underscore chars so BS4 won't escape them.
    cdata_map: Dict[str, str] = {}

    for index, pre in enumerate(soup.find_all("pre")):
        text = pre.get_text()
        is_diagram = any(ch in _BOX_DRAWING_CHARS for ch in text)

        if is_diagram:
            # Normalise potentially width-inconsistent characters before storing
            text = _normalise_diagram_text(text)

        placeholder = f"TXRCDATA{index}END"
        cdata_map[placeholder] = f"<![CDATA[{text}]]>"

        # Use the code macro for both diagrams and code blocks — it uses
        # Confluence Cloud's explicitly specified monospace font stack, giving
        # more consistent glyph widths than noformat's system-default fallback.
        lang = "text" if is_diagram else _detect_language(pre)
        macro = soup.new_tag("ac:structured-macro", attrs={"ac:name": "code"})
        lang_param = soup.new_tag("ac:parameter", attrs={"ac:name": "language"})
        lang_param.string = lang
        macro.append(lang_param)
        body = soup.new_tag("ac:plain-text-body")
        body.append(soup.new_string(placeholder))
        macro.append(body)

        pre.replace_with(macro)

    result = str(soup)
    for placeholder, cdata in cdata_map.items():
        result = result.replace(placeholder, cdata)
    return result


def _detect_language(pre_tag) -> str:
    """
    Infer a Confluence code-macro language from a ``<pre>`` tag.

    Checks:
    1. ``class="language-*"`` on the ``<pre>`` itself.
    2. ``class="language-*"`` on a child ``<code>`` element.
    3. Returns ``"text"`` as a safe default.

    Args:
        pre_tag: BeautifulSoup Tag for the ``<pre>`` element.

    Returns:
        Language string (e.g. ``"python"``, ``"bash"``, ``"yaml"``, ``"text"``).
    """
    candidates = [pre_tag]
    child_code = pre_tag.find("code")
    if child_code:
        candidates.append(child_code)

    for tag in candidates:
        for cls in tag.get("class", []):
            if cls.startswith("language-"):
                return cls[len("language-"):]

    return "text"


# CSS class → inline style mapping (fallback when premailer is unavailable)
_CLASS_STYLES: Dict[str, str] = {
    "info-panel": (
        "background: #DEEBFF; border-left: 4px solid #0052CC; "
        "padding: 12px 16px; margin: 16px 0; border-radius: 3px;"
    ),
    "success-panel": (
        "background: #E3FCEF; border-left: 4px solid #00875A; "
        "padding: 12px 16px; margin: 16px 0; border-radius: 3px;"
    ),
    "warning-panel": (
        "background: #FFFAE6; border-left: 4px solid #FF991F; "
        "padding: 12px 16px; margin: 16px 0; border-radius: 3px;"
    ),
    "breadcrumb": "color: #6B778C; font-size: 0.9em; margin-bottom: 8px;",
    "last-updated": "color: #6B778C; font-size: 0.85em; font-style: italic;",
    "metric": "font-size: 2em; font-weight: bold; color: #00875A;",
    "metric-label": "font-size: 0.85em; color: #6B778C;",
    "metrics-row": "display: flex; gap: 40px; margin: 20px 0;",
    "metric-box": "text-align: center;",
    "metrics-table": "border: none; margin: 20px 0;",
    "num": "text-align: right; font-variant-numeric: tabular-nums;",
}

_TAG_STYLES: Dict[str, str] = {
    "code": "background: #F4F5F7; padding: 2px 6px; border-radius: 3px; font-size: 0.9em;",
    "pre": "background: #F4F5F7; padding: 16px; border-radius: 3px; overflow-x: auto; font-size: 0.85em; font-family: 'Cascadia Mono', Consolas, 'Courier New', monospace;",
    "th": "background-color: #F4F5F7; font-weight: 600; border: 1px solid #DFE1E6; padding: 8px 12px; text-align: left;",
    "td": "border: 1px solid #DFE1E6; padding: 8px 12px; text-align: left; vertical-align: top;",
    "table": "border-collapse: collapse; width: 100%; margin: 16px 0;",
}


def _manual_inline_css(raw_html: str) -> str:
    """Fallback CSS inliner when premailer is not installed."""
    soup = BeautifulSoup(raw_html, "html.parser")

    # Inline class-based styles
    for class_name, style in _CLASS_STYLES.items():
        for el in soup.find_all(class_=class_name):
            existing = el.get("style", "")
            el["style"] = f"{existing} {style}".strip()
            # Remove class to keep output clean
            classes = el.get("class", [])
            if class_name in classes:
                classes.remove(class_name)
            if classes:
                el["class"] = classes
            else:
                del el["class"]

    # Inline tag-level styles
    for tag_name, style in _TAG_STYLES.items():
        for el in soup.find_all(tag_name):
            existing = el.get("style", "")
            if not existing:
                el["style"] = style

    # Remove <style> blocks
    for style_tag in soup.find_all("style"):
        style_tag.decompose()

    return str(soup)


def _strip_breadcrumbs_and_nav(html: str) -> str:
    """Remove breadcrumb paragraphs and bottom navigation links."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove breadcrumb paragraphs
    for p in soup.find_all("p", class_="breadcrumb"):
        p.decompose()
    # Also catch inlined breadcrumbs (after CSS inlining removed class)
    for p in soup.find_all("p"):
        style = p.get("style", "")
        if "0.9em" in style and "6B778C" in style and "margin-bottom" in style:
            text = p.get_text()
            if "Documentation" in text and "rsaquo" not in text and "›" not in text:
                continue
            if "›" in text or "rsaquo" in text or "»" in text:
                p.decompose()

    # Remove bottom navigation (« Previous | Index | Next »)
    for hr in soup.find_all("hr"):
        next_sib = hr.find_next_sibling()
        if next_sib and next_sib.name == "p":
            text = next_sib.get_text()
            if "Previous" in text or "Next" in text or "Documentation Index" in text:
                next_sib.decompose()
                hr.decompose()

    return str(soup)


# ---------------------------------------------------------------------------
# Confluence REST API client
# ---------------------------------------------------------------------------

class ConfluenceClient:
    """Minimal Confluence Cloud REST API v1 client."""

    def __init__(self, base_url: str, email: str, api_token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/wiki/rest/api"
        self.session = requests.Session()
        self.session.auth = (email, api_token)
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        # Track created page IDs for linking children
        self.created_pages: Dict[str, str] = {}  # title -> page_id

    def test_connection(self) -> bool:
        """Verify credentials and connectivity."""
        try:
            resp = self.session.get(f"{self.api_url}/space", params={"limit": 1})
            resp.raise_for_status()
            return True
        except requests.RequestException as e:
            print(f"  Connection failed: {e}")
            return False

    def page_exists(self, space_key: str, title: str) -> Optional[str]:
        """
        Check if a page with the given title exists in the space.

        Returns:
            Page ID if it exists, None otherwise.
        """
        resp = self.session.get(
            f"{self.api_url}/content",
            params={
                "spaceKey": space_key,
                "title": title,
                "type": "page",
            },
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if results:
            return results[0]["id"]
        return None

    def create_page(
        self,
        space_key: str,
        title: str,
        body_html: str,
        parent_id: Optional[str] = None,
    ) -> str:
        """
        Create a new Confluence page.

        Args:
            space_key: Confluence space key.
            title: Page title.
            body_html: XHTML body content (Confluence storage format).
            parent_id: Optional parent page ID for hierarchy.

        Returns:
            The ID of the created page.
        """
        payload: Dict = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "body": {
                "storage": {
                    "value": body_html,
                    "representation": "storage",
                },
            },
        }
        if parent_id:
            payload["ancestors"] = [{"id": parent_id}]

        resp = self.session.post(f"{self.api_url}/content", json=payload)

        if resp.status_code == 409:
            # Page already exists — find and update it
            print(f"    Page '{title}' already exists, updating...")
            page_id = self.page_exists(space_key, title)
            if page_id:
                return self.update_page(page_id, title, body_html)
            raise RuntimeError(f"Conflict but could not find page: {title}")

        resp.raise_for_status()
        page_id = resp.json()["id"]
        self.created_pages[title] = page_id
        return page_id

    def update_page(self, page_id: str, title: str, body_html: str) -> str:
        """
        Update an existing Confluence page (increments version).

        Args:
            page_id: Existing page ID.
            title: Page title.
            body_html: New XHTML body content.

        Returns:
            The page ID.
        """
        # Get current version number
        resp = self.session.get(f"{self.api_url}/content/{page_id}")
        resp.raise_for_status()
        current_version = resp.json()["version"]["number"]

        payload = {
            "id": page_id,
            "type": "page",
            "title": title,
            "version": {"number": current_version + 1},
            "body": {
                "storage": {
                    "value": body_html,
                    "representation": "storage",
                },
            },
        }

        resp = self.session.put(f"{self.api_url}/content/{page_id}", json=payload)
        resp.raise_for_status()
        self.created_pages[title] = page_id
        return page_id


# ---------------------------------------------------------------------------
# Upload orchestrator
# ---------------------------------------------------------------------------

def upload_page_tree(
    client: ConfluenceClient,
    space_key: str,
    html_dir: Path,
    pages: List[PageDef],
    parent_id: Optional[str] = None,
    depth: int = 0,
) -> int:
    """
    Recursively upload the page tree to Confluence.

    Args:
        client: Confluence API client.
        space_key: Target space key.
        html_dir: Directory containing HTML files.
        pages: List of PageDef nodes to upload.
        parent_id: Parent page ID (None for space root).
        depth: Current depth (for indentation in output).

    Returns:
        Number of pages uploaded.
    """
    count = 0
    indent = "  " * depth

    for page_def in pages:
        html_path = html_dir / page_def.filename
        if not html_path.exists():
            print(f"{indent}⚠  Skipping '{page_def.title}' — file not found: {page_def.filename}")
            continue

        print(f"{indent}📄 Uploading: {page_def.title}")

        # Convert HTML to storage format
        body_html = extract_and_inline_body(html_path)

        # Create/update page
        try:
            page_id = client.create_page(space_key, page_def.title, body_html, parent_id)
            print(f"{indent}   ✅ Created (ID: {page_id})")
            count += 1
        except requests.HTTPError as e:
            print(f"{indent}   ❌ Failed: {e}")
            print(f"{indent}      Response: {e.response.text[:300] if e.response else 'N/A'}")
            continue

        # Rate limiting — Confluence Cloud has limits
        time.sleep(0.5)

        # Upload children under this page
        if page_def.children:
            count += upload_page_tree(
                client, space_key, html_dir, page_def.children, page_id, depth + 1
            )

    return count


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Main entry point for the Confluence uploader."""
    print("=" * 60)
    print("  Confluence Documentation Uploader")
    print("  TXR Automation — 18 pages in hierarchical tree")
    print("=" * 60)
    print()

    # --- Gather credentials ---
    base_url = os.environ.get("CONFLUENCE_BASE_URL") or input(
        "Confluence base URL (e.g. https://yourorg.atlassian.net): "
    ).strip()
    email = os.environ.get("CONFLUENCE_EMAIL") or input(
        "Atlassian account email: "
    ).strip()
    api_token = os.environ.get("CONFLUENCE_API_TOKEN") or input(
        "API token (from https://id.atlassian.com/manage-profile/security/api-tokens): "
    ).strip()
    space_key = os.environ.get(
        "CONFLUENCE_SPACE_KEY",
        "~712020d9c9879a14a24caf9d4e4b5350a38d83",
    )

    if not all([base_url, email, api_token]):
        sys.exit("ERROR: Base URL, email, and API token are all required.")

    # --- Locate HTML files ---
    project_root = Path(__file__).resolve().parent.parent
    html_dir = project_root / "documentation" / "confluence"
    if not html_dir.is_dir():
        sys.exit(f"ERROR: HTML directory not found: {html_dir}")

    html_count = len(list(html_dir.glob("*.html")))
    print(f"Found {html_count} HTML files in {html_dir}")
    print(f"Target space: {space_key}")
    print()

    # --- Check optional dependencies ---
    if PREMAILER_AVAILABLE:
        print("✅ premailer available — CSS will be fully inlined")
    else:
        print("⚠  premailer not installed — using fallback CSS inliner")
        print("   For best results:  pip install premailer")
    print()

    # --- Connect and verify ---
    client = ConfluenceClient(base_url, email, api_token)
    print("Testing connection...")
    if not client.test_connection():
        sys.exit("ERROR: Could not connect to Confluence. Check URL and credentials.")
    print("✅ Connected successfully")
    print()

    # --- Confirm before uploading ---
    print("Ready to upload 18 pages to Confluence.")
    print("Pages will be created/updated as a hierarchical tree.")
    confirm = input("Proceed? [y/N]: ").strip().lower()
    if confirm not in ("y", "yes"):
        print("Aborted.")
        return

    print()
    print("-" * 60)

    # --- Upload ---
    start = time.time()
    total = upload_page_tree(client, space_key, html_dir, PAGE_TREE)
    elapsed = time.time() - start

    print("-" * 60)
    print()
    print(f"✅ Done! Uploaded {total} pages in {elapsed:.1f}s")
    print(f"   View at: {base_url}/wiki/spaces/{space_key}/pages")


if __name__ == "__main__":
    main()
