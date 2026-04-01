#!/usr/bin/env python3
"""
XML to CSV Converter
====================

Converts XML files to CSV format. Works with any XML schema by
auto-detecting the repeating record element and flattening nested
elements into path-prefixed column names.

If the XML root element contains a schema link (``xsi:schemaLocation``
or ``xsi:noNamespaceSchemaLocation``), the converter attempts to fetch
the XSD document and use its element declaration order for column
ordering. If the schema is unreachable or unparseable, the converter
falls back to first-occurrence column ordering derived from the data.

Supports single-file and directory (optionally recursive) conversion.

Usage:
    python -m utils.xml_csv_converter --input path/to/file.xml
    python -m utils.xml_csv_converter --input path/to/dir --recursive
    python -m utils.xml_csv_converter --input file.xml --output-dir ./output
    python -m utils.xml_csv_converter --input file.xml --dry-run
"""

import argparse
import csv
import logging
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse


@dataclass
class ConversionResult:
    """Result of converting a single XML file."""

    xml_path: Path
    csv_path: Optional[Path]
    record_count: int = 0
    column_count: int = 0
    schema_url: Optional[str] = None
    schema_fetched: bool = False
    record_element: str = ""
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """Return True if conversion completed without error."""
        return self.error is None


@dataclass
class ConversionStats:
    """Aggregate statistics across all conversions in a run."""

    processed: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0

    def print_summary(self, logger=None) -> None:
        """Log or print a human-readable summary."""
        summary = (
            f"\nConversion Summary:\n"
            f"  Processed: {self.processed}\n"
            f"  Successful: {self.successful}\n"
            f"  Failed: {self.failed}\n"
            f"  Skipped: {self.skipped}\n"
        )
        if logger:
            logger.info(summary)
        else:
            print(summary)


class XMLToCSVConverter:
    """
    Universal XML to CSV converter.

    Attributes:
        logger: Structured logger instance.
    """

    # Characters illegal in XML 1.0 (excluding \t, \n, \r which are valid).
    _INVALID_XML_CHARS_RE: re.Pattern = re.compile(
        r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]"
    )
    # Bare & not already part of a character/entity reference.
    _BARE_AMP_RE: re.Pattern = re.compile(
        r"&(?!(?:[a-zA-Z][a-zA-Z0-9]*|#[0-9]+|#x[0-9a-fA-F]+);)"
    )

    # Namespaces commonly found in XSD documents.
    _XSD_NAMESPACES: Tuple[str, ...] = (
        "http://www.w3.org/2001/XMLSchema",
        "http://www.w3.org/XML/Schema",
    )
    _XSI_SCHEMA_LOCATION = (
        "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation"
    )
    _XSI_NO_NS_SCHEMA_LOCATION = (
        "{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation"
    )

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Resilient XML parsing
    # ------------------------------------------------------------------

    def _parse_xml_resilient(
        self, xml_path: Path
    ) -> Tuple[ET.Element, str]:
        """Parse an XML file using a cascade of recovery strategies.

        Tries four strategies in order, stopping at the first success:

        1. Standard ``ET.parse()`` — fastest, no overhead.
        2. BOM-aware decode — handles UTF-16 LE/BE and UTF-8-BOM files.
        3. Encoding fallback + control-character stripping — reads the
           file with ASCII-compatible encodings and strips characters
           illegal in XML 1.0 (\\x00-\\x08, \\x0B, \\x0C, \\x0E-\\x1F,
           \\x7F).
        4. Bare-ampersand escaping — additionally replaces ``&`` that are
           not already part of a valid entity or character reference with
           ``&amp;``. This commonly occurs in financial data where
           ``&`` appears literally in company or instrument names.

        Args:
            xml_path: Path to the XML file.

        Returns:
            Tuple of (root Element, description of strategy used).

        Raises:
            ET.ParseError: If all strategies fail.
        """
        # Strategy 1: standard parse
        try:
            return ET.parse(xml_path).getroot(), "standard"
        except ET.ParseError as err1:
            self.logger.warning(
                f"Standard parse failed ({err1}); trying recovery strategies."
            )

        raw_bytes: bytes = xml_path.read_bytes()

        # Strategy 2: BOM detection and explicit decode
        if raw_bytes.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
            # UTF-32 LE / BE
            enc = "utf-32"
        elif raw_bytes.startswith(b"\xff\xfe"):
            enc = "utf-16-le"
        elif raw_bytes.startswith(b"\xfe\xff"):
            enc = "utf-16-be"
        elif raw_bytes.startswith(b"\xef\xbb\xbf"):
            enc = "utf-8-sig"
        else:
            enc = None

        if enc is not None:
            try:
                text = raw_bytes.decode(enc)
                # Remove the XML declaration if it conflicts with the
                # encoding we just decoded to (avoids double-header issues).
                text = re.sub(
                    r"<\?xml[^?]*\?>", "", text, count=1
                ).lstrip()
                return ET.fromstring(text), f"BOM-decoded ({enc})"
            except ET.ParseError as err2:
                self.logger.warning(f"BOM-decode strategy failed ({err2}).")

        # Strategy 3: encoding fallback + strip illegal chars
        _FALLBACK_ENCODINGS = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]
        for encoding in _FALLBACK_ENCODINGS:
            try:
                text = raw_bytes.decode(encoding, errors="replace")
                text = self._INVALID_XML_CHARS_RE.sub("", text)
                return ET.fromstring(text), f"encoding-fallback ({encoding})"
            except ET.ParseError:
                continue

        # Strategy 4: encoding fallback + strip illegal chars + escape bare &
        for encoding in _FALLBACK_ENCODINGS:
            try:
                text = raw_bytes.decode(encoding, errors="replace")
                text = self._INVALID_XML_CHARS_RE.sub("", text)
                text = self._BARE_AMP_RE.sub("&amp;", text)
                return ET.fromstring(text), "bare-amp-escape"
            except ET.ParseError:
                continue

        # All strategies exhausted — re-raise original error
        try:
            ET.parse(xml_path)
        except ET.ParseError as original:
            raise original
        raise ET.ParseError("All parse strategies failed")  # pragma: no cover

    # ------------------------------------------------------------------
    # Schema utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_namespace(tag: str) -> str:
        """Remove ``{uri}`` namespace prefix from an XML tag or attribute name.

        Args:
            tag: Raw XML tag string, e.g. ``{http://example.com}RecordId``.

        Returns:
            Tag without namespace prefix.
        """
        if tag.startswith("{"):
            return tag.split("}", 1)[1]
        return tag

    def detect_schema_url(self, root: ET.Element) -> Optional[str]:
        """Extract the XSD schema URL from the root element's attributes.

        Checks both ``xsi:schemaLocation`` and
        ``xsi:noNamespaceSchemaLocation``.

        Args:
            root: The root XML element.

        Returns:
            The first HTTP/HTTPS URL found, or ``None``.
        """
        # xsi:noNamespaceSchemaLocation — direct URL
        no_ns = root.get(self._XSI_NO_NS_SCHEMA_LOCATION)
        if no_ns and no_ns.strip().startswith(("http://", "https://")):
            return no_ns.strip()

        # xsi:schemaLocation — alternating namespace/URL pairs
        schema_loc = root.get(self._XSI_SCHEMA_LOCATION)
        if schema_loc:
            parts = schema_loc.split()
            for part in parts:
                if part.startswith(("http://", "https://")):
                    # Skip namespace URIs that are not XSD files
                    parsed = urlparse(part)
                    if parsed.path.endswith(".xsd") or "schema" in parsed.path.lower():
                        return part
            # If no obvious .xsd URL found, return last URL-shaped token
            for part in reversed(parts):
                if part.startswith(("http://", "https://")):
                    return part

        return None

    def fetch_xsd_columns(self, url: str) -> Optional[List[str]]:
        """Attempt to fetch an XSD and return element names in declaration order.

        Args:
            url: URL of the XSD document.

        Returns:
            Ordered list of element/attribute names, or ``None`` if
            fetch or parse fails.
        """
        try:
            self.logger.info(f"Fetching schema from: {url}")
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "TXR-XML-Converter/1.0"},
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                xsd_content = response.read()

            xsd_root = ET.fromstring(xsd_content)
            names: List[str] = []
            seen: set = set()

            for ns in self._XSD_NAMESPACES:
                for elem in xsd_root.iter(f"{{{ns}}}element"):
                    name = elem.get("name")
                    if name and name not in seen:
                        seen.add(name)
                        names.append(name)
                for attr in xsd_root.iter(f"{{{ns}}}attribute"):
                    name = attr.get("name")
                    if name and name not in seen:
                        seen.add(name)
                        names.append(name)

            if names:
                self.logger.info(
                    f"Fetched {len(names)} column names from schema."
                )
                return names

            self.logger.warning("Schema fetched but contained no element declarations.")
            return None

        except Exception as exc:
            self.logger.warning(
                f"Could not fetch or parse schema (will use data order): {exc}"
            )
            return None

    # ------------------------------------------------------------------
    # Record-element detection
    # ------------------------------------------------------------------

    def detect_record_element(self, root: ET.Element) -> str:
        """Determine which element tag represents a single record (row).

        Strategy: count all tag occurrences across the entire tree. The
        record element is the most-frequent tag that (a) appears more
        than once and (b) has at least one child element (i.e. it is a
        container, not a leaf).

        Falls back to the tag of root's direct children if no qualifying
        element is found.

        Args:
            root: The root XML element.

        Returns:
            Local tag name of the detected record element.
        """
        tag_counts: Counter = Counter()
        tag_has_children: set = set()

        for elem in root.iter():
            local = self._strip_namespace(elem.tag)
            tag_counts[local] += 1
            for child in elem:
                tag_has_children.add(local)

        # Candidates: appear > 1 time AND have child elements
        candidates = {
            tag: count
            for tag, count in tag_counts.items()
            if count > 1 and tag in tag_has_children
        }

        if candidates:
            best = max(candidates, key=lambda t: candidates[t])
            self.logger.info(
                f"Detected record element: <{best}> "
                f"({candidates[best]} occurrences)"
            )
            return best

        # Fallback: use the direct children of root
        children = list(root)
        if children:
            fallback = self._strip_namespace(children[0].tag)
            self.logger.warning(
                f"No repeating record element found; "
                f"using root's direct child <{fallback}> as record element."
            )
            return fallback

        # Last resort: root itself
        return self._strip_namespace(root.tag)

    # ------------------------------------------------------------------
    # Element flattening
    # ------------------------------------------------------------------

    def flatten_element(
        self,
        element: ET.Element,
        prefix: str = "",
    ) -> Dict[str, str]:
        """Recursively flatten an XML element into a flat key/value dict.

        - Child element values are path-prefixed: ``Parent_Child_GrandChild``.
        - XML attributes become bare-name columns.
        - If an attribute name collides with a child element name, the
          attribute column is suffixed with ``_attr``.
        - Repeated sibling elements with the same tag are joined with
          ``|`` into a single column.

        Args:
            element: The XML element to flatten.
            prefix: Column name prefix accumulated during recursion.

        Returns:
            Ordered dict of column name → string value.
        """
        result: Dict[str, str] = OrderedDict()

        # Collect attributes
        for attr_name, attr_value in element.attrib.items():
            local_attr = self._strip_namespace(attr_name)
            result[local_attr] = attr_value

        # Collect text content (direct text of this element, no children)
        children = list(element)
        if not children:
            text = (element.text or "").strip()
            if prefix:
                existing = result.get(prefix, "")
                if existing:
                    result[prefix] = f"{existing}|{text}"
                else:
                    result[prefix] = text
            # If no prefix this is the root record; text is ignored (rare)
            # Rename attribute columns if they clash with the prefix column
            return result

        # Group children by local tag to handle repeating sub-elements
        child_groups: Dict[str, List[ET.Element]] = OrderedDict()
        for child in children:
            local_tag = self._strip_namespace(child.tag)
            child_groups.setdefault(local_tag, []).append(child)

        for local_tag, group in child_groups.items():
            col_name = f"{prefix}_{local_tag}" if prefix else local_tag

            if len(group) == 1:
                child_elem = group[0]
                child_children = list(child_elem)
                if not child_children:
                    # Leaf: just a value
                    text = (child_elem.text or "").strip()
                    result[col_name] = text
                    # Flatten child attributes
                    for attr_name, attr_value in child_elem.attrib.items():
                        local_attr = self._strip_namespace(attr_name)
                        attr_col = f"{col_name}_{local_attr}"
                        result[attr_col] = attr_value
                else:
                    # Non-leaf: recurse
                    child_flat = self.flatten_element(child_elem, col_name)
                    for k, v in child_flat.items():
                        result[k] = v
            else:
                # Multiple siblings with same tag — flatten each and join values
                all_values: List[str] = []
                for child_elem in group:
                    child_children = list(child_elem)
                    if not child_children:
                        all_values.append((child_elem.text or "").strip())
                    else:
                        child_flat = self.flatten_element(child_elem, col_name)
                        # Use first value column as representative
                        all_values.append(
                            next(iter(child_flat.values()), "")
                        )
                result[col_name] = "|".join(all_values)

        # Resolve attribute vs child element name collisions
        collision_keys = [
            k for k in list(result.keys())
            if k in result and not k.startswith(prefix + "_") and k in child_groups
        ]
        for key in collision_keys:
            if key in element.attrib or self._strip_namespace(key) in element.attrib:
                old_value = result.pop(key)
                result[f"{key}_attr"] = old_value

        return result

    # ------------------------------------------------------------------
    # Conversion pipeline
    # ------------------------------------------------------------------

    def convert_file(
        self,
        xml_path: Path,
        output_path: Path,
        dry_run: bool = False,
    ) -> ConversionResult:
        """Convert a single XML file to CSV.

        Args:
            xml_path: Path to the source XML file.
            output_path: Path where the CSV file will be written.
            dry_run: If ``True``, parse and report but do not write.

        Returns:
            A :class:`ConversionResult` describing the outcome.
        """
        result = ConversionResult(xml_path=xml_path, csv_path=output_path)

        try:
            self.logger.info(f"Parsing: {xml_path}")
            root, strategy = self._parse_xml_resilient(xml_path)
            if strategy != "standard":
                self.logger.info(f"Parsed using recovery strategy: {strategy}")
        except ET.ParseError as exc:
            result.error = f"XML parse error: {exc}"
            self.logger.error(result.error)
            return result

        # Schema detection
        schema_url = self.detect_schema_url(root)
        result.schema_url = schema_url
        xsd_columns: Optional[List[str]] = None
        if schema_url:
            self.logger.info(f"Schema link found: {schema_url}")
            xsd_columns = self.fetch_xsd_columns(schema_url)
            result.schema_fetched = xsd_columns is not None

        # Record element detection
        record_tag = self.detect_record_element(root)
        result.record_element = record_tag

        # Collect all matching record elements (anywhere in tree)
        ns_variants: List[str] = []
        for elem in root.iter():
            if self._strip_namespace(elem.tag) == record_tag:
                ns_variants.append(elem.tag)

        # Use the first namespace-qualified tag found for findall
        qualified_tag = ns_variants[0] if ns_variants else record_tag

        # Walk the full tree to find record elements at any depth
        records: List[ET.Element] = []
        for elem in root.iter():
            if self._strip_namespace(elem.tag) == record_tag:
                records.append(elem)

        if not records:
            result.error = f"No <{record_tag}> elements found in {xml_path.name}"
            self.logger.error(result.error)
            return result

        self.logger.info(f"Found {len(records)} record(s) to convert.")

        # Build column order: use XSD order if available, extend with
        # any extra columns encountered in the data.
        all_rows: List[Dict[str, str]] = []
        data_columns: List[str] = []
        seen_cols: set = set()

        for rec in records:
            flat = self.flatten_element(rec)
            all_rows.append(flat)
            for col in flat:
                if col not in seen_cols:
                    seen_cols.add(col)
                    data_columns.append(col)

        # Merge XSD order with data columns
        if xsd_columns:
            ordered_cols: List[str] = []
            xsd_set = set(xsd_columns)
            for col in xsd_columns:
                if col in seen_cols:
                    ordered_cols.append(col)
            for col in data_columns:
                if col not in xsd_set:
                    ordered_cols.append(col)
        else:
            ordered_cols = data_columns

        result.record_count = len(all_rows)
        result.column_count = len(ordered_cols)

        if dry_run:
            self.logger.info(
                f"[DRY RUN] Would write {len(all_rows)} rows × "
                f"{len(ordered_cols)} columns → {output_path}"
            )
            return result

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=ordered_cols,
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerows(all_rows)

        self.logger.info(
            f"Written: {output_path} "
            f"({len(all_rows)} rows, {len(ordered_cols)} columns)"
        )
        return result

    def convert_directory(
        self,
        input_dir: Path,
        output_dir: Path,
        recursive: bool = False,
        dry_run: bool = False,
    ) -> ConversionStats:
        """Convert all XML files in a directory.

        Args:
            input_dir: Directory containing ``.xml`` files.
            output_dir: Directory where converted ``.csv`` files are written.
                        Subdirectory structure is preserved when recursive.
            recursive: If ``True``, search subdirectories.
            dry_run: If ``True``, report without writing files.

        Returns:
            Aggregate :class:`ConversionStats`.
        """
        stats = ConversionStats()
        pattern = "**/*.xml" if recursive else "*.xml"
        xml_files = sorted(input_dir.glob(pattern))

        if not xml_files:
            self.logger.warning(f"No XML files found in {input_dir}")
            return stats

        self.logger.info(f"Found {len(xml_files)} XML file(s) to process.")

        for xml_path in xml_files:
            stats.processed += 1
            relative = xml_path.relative_to(input_dir)
            csv_path = output_dir / relative.with_suffix(".csv")

            result = self.convert_file(xml_path, csv_path, dry_run=dry_run)
            if result.success:
                stats.successful += 1
            else:
                stats.failed += 1
                self.logger.error(
                    f"Failed to convert {xml_path.name}: {result.error}"
                )

        return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_arguments(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Build and parse the command-line argument parser.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Parsed :class:`argparse.Namespace`.
    """
    parser = argparse.ArgumentParser(
        description="Convert XML file(s) to CSV. Works with any XML schema.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to an XML file or a directory of XML files.",
    )
    parser.add_argument(
        "--output-dir",
        help=(
            "Directory where converted CSV files will be written. "
            "Defaults to the same directory as each input XML file."
        ),
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        default=False,
        help="Recursively search subdirectories for XML files (directory mode only).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Parse and report without writing any CSV files.",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging verbosity (default: INFO).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    """Entry point for the XML to CSV converter.

    Args:
        argv: Optional list of arguments (defaults to ``sys.argv[1:]``).
    """
    args = parse_arguments(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    converter = XMLToCSVConverter()
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"ERROR: Input path does not exist: {input_path}", file=sys.stderr)
        sys.exit(1)

    if input_path.is_file():
        # Single-file mode
        if args.output_dir:
            output_dir = Path(args.output_dir)
            csv_path = output_dir / input_path.with_suffix(".csv").name
        else:
            csv_path = input_path.with_suffix(".csv")

        result = converter.convert_file(input_path, csv_path, dry_run=args.dry_run)

        if not result.success:
            print(f"ERROR: {result.error}", file=sys.stderr)
            sys.exit(1)

        if args.dry_run:
            print(
                f"[DRY RUN] {input_path.name} → {csv_path.name}  "
                f"({result.record_count} records, {result.column_count} columns)"
            )
        else:
            print(
                f"Converted: {input_path.name} → {csv_path.name}  "
                f"({result.record_count} records, {result.column_count} columns)"
            )
        sys.exit(0)

    if input_path.is_dir():
        # Directory mode
        output_dir = Path(args.output_dir) if args.output_dir else input_path

        stats = converter.convert_directory(
            input_dir=input_path,
            output_dir=output_dir,
            recursive=args.recursive,
            dry_run=args.dry_run,
        )
        stats.print_summary()
        sys.exit(0 if stats.failed == 0 else 1)

    print(f"ERROR: Input is neither a file nor a directory: {input_path}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
