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
    _INVALID_XML_CHARS_RE: re.Pattern = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
    # Bare & not already part of a character/entity reference.
    _BARE_AMP_RE: re.Pattern = re.compile(
        r"&(?!(?:[a-zA-Z][a-zA-Z0-9]*|#[0-9]+|#x[0-9a-fA-F]+);)"
    )
    _ISO_UTC_GT_MS_RE: re.Pattern = re.compile(
        r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3})\d+(Z)"
    )

    # Namespaces commonly found in XSD documents.
    _XSD_NAMESPACES: Tuple[str, ...] = (
        "http://www.w3.org/2001/XMLSchema",
        "http://www.w3.org/XML/Schema",
    )
    _XSI_SCHEMA_LOCATION = "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation"
    _XSI_NO_NS_SCHEMA_LOCATION = (
        "{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation"
    )

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Resilient XML parsing
    # ------------------------------------------------------------------

    def _parse_xml_resilient(self, xml_path: Path) -> Tuple[ET.Element, str]:
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
                text = re.sub(r"<\?xml[^?]*\?>", "", text, count=1).lstrip()
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

            names = self.parse_xsd_columns(xsd_content)
            if names:
                self.logger.info(f"Fetched {len(names)} column names from schema.")
                return names

            self.logger.warning("Schema fetched but contained no element declarations.")
            return None

        except Exception as exc:
            self.logger.warning(
                f"Could not fetch or parse schema (will use data order): {exc}"
            )
            return None

    @classmethod
    def _find_xsd_namespace(cls, xsd_root: ET.Element) -> str:
        """Return the XML Schema namespace URI used by an XSD root."""
        if xsd_root.tag.startswith("{"):
            root_ns = xsd_root.tag.split("}", 1)[0][1:]
            if root_ns in cls._XSD_NAMESPACES:
                return root_ns

        for ns in cls._XSD_NAMESPACES:
            if xsd_root.tag == f"{{{ns}}}schema":
                return ns

        for ns in cls._XSD_NAMESPACES:
            if xsd_root.find(f".//{{{ns}}}element") is not None:
                return ns

        raise ValueError("Unsupported XSD namespace.")

    @classmethod
    def _iter_xsd_child_elements(cls, node: ET.Element) -> List[ET.Element]:
        """Collect nested ``xs:element`` declarations in declaration order."""
        children: List[ET.Element] = []
        for child in list(node):
            local_tag = cls._strip_namespace(child.tag)
            if local_tag == "element":
                children.append(child)
                continue
            if local_tag in {"complexType", "sequence", "choice", "all"}:
                children.extend(cls._iter_xsd_child_elements(child))
        return children

    @classmethod
    def parse_xsd_structure(cls, xsd_content: str | bytes) -> List[Dict[str, object]]:
        """Parse an XSD and return flattened field structure metadata."""
        if isinstance(xsd_content, bytes):
            content = xsd_content.decode("utf-8", errors="replace")
        else:
            content = xsd_content

        if not content.strip():
            raise ValueError("XSD content is empty.")

        try:
            xsd_root = ET.fromstring(content)
        except ET.ParseError as exc:
            raise ValueError(f"XSD parse error: {exc}") from exc

        xsd_ns = cls._find_xsd_namespace(xsd_root)

        def qname(local: str) -> str:
            return f"{{{xsd_ns}}}{local}"

        global_elements: Dict[str, ET.Element] = {
            elem.get("name"): elem
            for elem in xsd_root.findall(qname("element"))
            if elem.get("name")
        }
        global_complex_types: Dict[str, ET.Element] = {
            elem.get("name"): elem
            for elem in xsd_root.findall(qname("complexType"))
            if elem.get("name")
        }
        global_simple_types: Dict[str, ET.Element] = {
            elem.get("name"): elem
            for elem in xsd_root.findall(qname("simpleType"))
            if elem.get("name")
        }

        structure: List[Dict[str, str]] = []
        seen_paths: set[str] = set()

        def _normalise_max_occurs(value: str | None) -> str:
            if not value:
                return "1"
            return value

        def _normalise_min_occurs(value: str | None) -> str:
            if not value:
                return "1"
            return value

        def _extract_constraints(simple_type: ET.Element | None) -> Dict[str, object]:
            if simple_type is None:
                return {}

            restriction = None
            for child in list(simple_type):
                if cls._strip_namespace(child.tag) == "restriction":
                    restriction = child
                    break

            if restriction is None:
                return {}

            constraints: Dict[str, object] = {}
            enum_values: List[str] = []

            for child in list(restriction):
                local = cls._strip_namespace(child.tag)
                value = child.get("value")
                if not value:
                    continue

                if local == "enumeration":
                    enum_values.append(value)
                    continue

                if local == "pattern":
                    constraints["pattern"] = value
                    continue

                if local == "minLength":
                    constraints["min_length"] = value
                    continue

                if local == "maxLength":
                    constraints["max_length"] = value
                    continue

                if local == "totalDigits":
                    constraints["total_digits"] = value
                    continue

                if local == "fractionDigits":
                    constraints["fraction_digits"] = value
                    continue

                if local == "minInclusive":
                    constraints["min_inclusive"] = value
                    continue

                if local == "maxInclusive":
                    constraints["max_inclusive"] = value
                    continue

            if enum_values:
                constraints["enum_values"] = enum_values

            return constraints

        def walk_element(elem: ET.Element, parent_path: str = "") -> None:
            raw_name = elem.get("name") or elem.get("ref")
            if not raw_name:
                return
            name = raw_name.split(":")[-1]
            path = f"{parent_path}_{name}" if parent_path else name

            min_occurs = _normalise_min_occurs(elem.get("minOccurs"))
            max_occurs = _normalise_max_occurs(elem.get("maxOccurs"))
            type_name = (elem.get("type") or "").split(":")[-1]
            simple_type_constraints: Dict[str, object] = {}

            inline_complex = elem.find(qname("complexType"))
            inline_simple = elem.find(qname("simpleType"))
            child_elements: List[ET.Element] = []
            if inline_complex is not None:
                child_elements = cls._iter_xsd_child_elements(inline_complex)
            elif type_name and type_name in global_complex_types:
                child_elements = cls._iter_xsd_child_elements(
                    global_complex_types[type_name]
                )
            elif elem.get("ref"):
                referenced = global_elements.get(name)
                if referenced is not None and referenced is not elem:
                    referenced_inline = referenced.find(qname("complexType"))
                    if referenced_inline is not None:
                        child_elements = cls._iter_xsd_child_elements(referenced_inline)

            if inline_simple is not None:
                simple_type_constraints = _extract_constraints(inline_simple)
            elif type_name and type_name in global_simple_types:
                simple_type_constraints = _extract_constraints(global_simple_types[type_name])

            if child_elements:
                for child in child_elements:
                    walk_element(child, path)
                return

            if path in seen_paths:
                return
            seen_paths.add(path)
            structure.append(
                {
                    "name": name,
                    "path": path,
                    "type_name": type_name,
                    "min_occurs": min_occurs,
                    "max_occurs": max_occurs,
                    "constraints": simple_type_constraints,
                }
            )

        top_level_elements = xsd_root.findall(qname("element"))
        for element in top_level_elements:
            walk_element(element)

        return structure

    @classmethod
    def parse_xsd_columns(cls, xsd_content: str | bytes) -> Optional[List[str]]:
        """Extract flattened column names from XSD content."""
        structure = cls.parse_xsd_structure(xsd_content)
        columns = [entry["path"] for entry in structure if entry.get("path")]
        if not columns:
            return None
        return columns

    # ------------------------------------------------------------------
    # Record-element detection
    # ------------------------------------------------------------------

    def detect_record_element(self, root: ET.Element) -> Tuple[str, str]:
        """Determine which element tag represents a single record (row).

        Strategy: for every parent element type, count the total number of
        its dominant child tag across the whole document AND the number of
        parent instances.  The ratio — dominant children per parent instance
        — discriminates genuine list containers from metadata wrappers.

        Example (FCA MiFIR XML):
          ``FinInstrmRptgTxRpt`` appears once and contains 500 000 ``Tx``
          children  -> avg 500 000 per instance  (list container)
          ``SchmeNm`` appears 844 000 times, each with one ``Cd`` child
          -> avg 1.0 per instance  (not a list)

        The record element is the dominant child of the parent with the
        highest average dominant-child count per instance, provided that
        average exceeds 1.0.

        Falls back to the most child-diverse repeating element when no
        qualifying container is found.

        Args:
            root: The root XML element.

        Returns:
            Tuple of (record tag, parent/container tag).
        """
        parent_instance_count: Counter = Counter()
        parent_child_counts: Dict[str, Counter] = {}
        tag_child_tags: Dict[str, set] = {}

        for elem in root.iter():
            local = self._strip_namespace(elem.tag)
            parent_instance_count[local] += 1
            if local not in parent_child_counts:
                parent_child_counts[local] = Counter()
            if local not in tag_child_tags:
                tag_child_tags[local] = set()
            for child in elem:
                child_local = self._strip_namespace(child.tag)
                parent_child_counts[local][child_local] += 1
                tag_child_tags[local].add(child_local)

        # Build candidates: parent tags whose children are >=80% one tag AND
        # whose average dominant-child count per parent instance exceeds 1.0.
        # Sorting by avg_per_instance descending finds the genuine list
        # wrapper rather than single-child metadata containers.
        list_candidates: List[tuple] = []

        for parent_tag, child_counter in parent_child_counts.items():
            total_children = sum(child_counter.values())
            if total_children == 0:
                continue
            most_common_child, most_common_count = child_counter.most_common(1)[0]
            dominance = most_common_count / total_children
            if dominance < 0.8:
                continue
            p_instances = parent_instance_count[parent_tag]
            avg_per_instance = most_common_count / p_instances
            if avg_per_instance > 1.0:
                list_candidates.append(
                    (avg_per_instance, most_common_child, parent_tag, most_common_count)
                )

        # Debug: log all qualifying candidates so detection failures are easy to diagnose.
        if list_candidates:
            self.logger.debug("Record element candidates (avg dominant children per parent instance):")
            for avg, child_tag, parent_tag, child_count in sorted(list_candidates, reverse=True):
                self.logger.debug(
                    f"  <{parent_tag}> -> <{child_tag}>  "
                    f"total={child_count}  "
                    f"parent_instances={parent_instance_count[parent_tag]}  "
                    f"avg={avg:.1f}"
                )

        if list_candidates:
            _, best_record_tag, best_parent, best_count = max(list_candidates)
            child_diversity = len(tag_child_tags.get(best_record_tag, set()))
            self.logger.info(
                f"Detected record element: <{best_record_tag}> "
                f"(child of <{best_parent}>, {best_count} occurrences, "
                f"{child_diversity} unique child tags)"
            )
            return best_record_tag, best_parent

        # Fallback: element with the most diverse direct children among
        # repeating elements.
        self.logger.debug(
            "No dominant list container found; falling back to child-diversity heuristic."
        )
        candidates = {
            tag: parent_instance_count[tag]
            for tag in parent_instance_count
            if parent_instance_count[tag] > 1 and len(tag_child_tags.get(tag, set())) > 0
        }

        if candidates:
            best = max(candidates, key=lambda t: len(tag_child_tags.get(t, set())))
            self.logger.info(
                f"Detected record element: <{best}> "
                f"({candidates[best]} occurrences, "
                f"{len(tag_child_tags[best])} unique child tags - fallback heuristic)"
            )
            return best, ""

        # Last resort: direct children of root
        children = list(root)
        if children:
            fallback = self._strip_namespace(children[0].tag)
            self.logger.warning(
                f"No repeating record element found; "
                f"using root's direct child <{fallback}> as record element."
            )
            return fallback, self._strip_namespace(root.tag)

        fallback = self._strip_namespace(root.tag)
        return fallback, ""

    def _collect_records(
        self,
        root: ET.Element,
        record_tag: str,
        container_tag: str,
    ) -> List[ET.Element]:
        """Collect record elements, preferring direct children of container.

        Args:
            root: Parsed XML root element.
            record_tag: Local-name tag to use as row records.
            container_tag: Expected parent/container local-name tag.

        Returns:
            List of record elements.
        """
        if container_tag:
            for elem in root.iter():
                if self._strip_namespace(elem.tag) == container_tag:
                    return [
                        child
                        for child in elem
                        if self._strip_namespace(child.tag) == record_tag
                    ]

        # Fallback for unknown container: keep only the shallowest matching
        # elements to avoid treating nested detail blocks as top-level records.
        depth_by_id: Dict[int, int] = {id(root): 0}
        matches: List[ET.Element] = []
        min_depth: Optional[int] = None

        for elem in root.iter():
            elem_depth = depth_by_id.get(id(elem), 0)
            for child in elem:
                depth_by_id[id(child)] = elem_depth + 1

            if self._strip_namespace(elem.tag) != record_tag:
                continue

            matches.append(elem)
            if min_depth is None or elem_depth < min_depth:
                min_depth = elem_depth

        if min_depth is None:
            return []

        return [elem for elem in matches if depth_by_id.get(id(elem), 0) == min_depth]

    @classmethod
    def _normalise_datetime(cls, value: str) -> str:
        """Normalise UTC datetimes to millisecond precision when needed."""
        return cls._ISO_UTC_GT_MS_RE.sub(r"\1\2", value)

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
            text = self._normalise_datetime(text)
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
                    text = self._normalise_datetime(text)
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
                        text = (child_elem.text or "").strip()
                        all_values.append(self._normalise_datetime(text))
                    else:
                        child_flat = self.flatten_element(child_elem, col_name)
                        # Use first value column as representative
                        all_values.append(next(iter(child_flat.values()), ""))
                result[col_name] = "|".join(all_values)

        # Resolve attribute vs child element name collisions
        collision_keys = [
            k
            for k in list(result.keys())
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
        xsd_content: Optional[str] = None,
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

        xsd_columns: Optional[List[str]] = None
        if xsd_content and xsd_content.strip():
            result.schema_url = "user-provided"
            try:
                xsd_columns = self.parse_xsd_columns(xsd_content)
                result.schema_fetched = xsd_columns is not None
                if not xsd_columns:
                    result.error = "Provided XSD did not produce any schema columns."
                    self.logger.error(result.error)
                    return result
            except ValueError as exc:
                result.error = f"Invalid provided XSD: {exc}"
                self.logger.error(result.error)
                return result
        else:
            # Schema detection from XML metadata
            schema_url = self.detect_schema_url(root)
            result.schema_url = schema_url
            if schema_url:
                self.logger.info(f"Schema link found: {schema_url}")
                xsd_columns = self.fetch_xsd_columns(schema_url)
                result.schema_fetched = xsd_columns is not None

        # Record element detection
        record_tag, container_tag = self.detect_record_element(root)
        result.record_element = record_tag

        records = self._collect_records(root, record_tag, container_tag)

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
        xsd_content: Optional[str] = None,
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

            if xsd_content is not None:
                result = self.convert_file(
                    xml_path,
                    csv_path,
                    dry_run=dry_run,
                    xsd_content=xsd_content,
                )
            else:
                result = self.convert_file(xml_path, csv_path, dry_run=dry_run)
            if result.success:
                stats.successful += 1
            else:
                stats.failed += 1
                self.logger.error(f"Failed to convert {xml_path.name}: {result.error}")

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
        "--xsd-file",
        help=(
            "Optional path to a user-provided XSD schema file. "
            "When set, this schema overrides any schema reference in the XML."
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
    xsd_content: Optional[str] = None

    if args.xsd_file:
        xsd_path = Path(args.xsd_file)
        if not xsd_path.exists() or not xsd_path.is_file():
            print(f"ERROR: XSD file does not exist: {xsd_path}", file=sys.stderr)
            sys.exit(1)
        xsd_content = xsd_path.read_text(encoding="utf-8")

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

        result = converter.convert_file(
            input_path,
            csv_path,
            dry_run=args.dry_run,
            xsd_content=xsd_content,
        )

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
            xsd_content=xsd_content,
        )
        stats.print_summary()
        sys.exit(0 if stats.failed == 0 else 1)

    print(
        f"ERROR: Input is neither a file nor a directory: {input_path}", file=sys.stderr
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
