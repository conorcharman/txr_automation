#!/usr/bin/env python3
"""
FCA FIRDS XML Parser
====================

Memory-efficient streaming parser for FCA FIRDS XML files.

Handles the three FIRDS file schemas:

- **FULINS** (``auth.017.001.01``) – Full instrument reference data files.
  Every record is a ``FinInstrmGnlAttrbts`` / ``TradgVnRltdAttrbts`` block
  wrapped in a ``RefData`` element.

- **DLTINS** (``auth.036.001.03``) – Delta files.  Each record is one of:
  - ``NewRcrd`` – instrument added to a trading venue
  - ``ModfdRcrd`` – modification to existing reference data
  - ``TermntdRcrd`` – instrument terminated on a trading venue
  - ``CancRcrd`` – instrument cancelled (available from Jan 2022 schema)

- **FULCAN** (``auth.102.001.01``) – Cancellation full files.

The parser uses ``xml.etree.ElementTree.iterparse`` to stream large files
without loading the whole document into memory.  Each record is yielded as an
:class:`InstrumentRecord` dataclass.

Usage:
    parser = FirdsXmlParser()
    for record in parser.parse(Path("FULINS_C_20260308_01of01.xml")):
        print(record.isin, record.mic, record.record_type)
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional

# ---------------------------------------------------------------------------
# XML namespace map
# The FIRDS XML files use a default namespace declared on the root element.
# iterparse returns tag names like "{urn:...}RefData", so we strip the
# namespace prefix during lookup by using the _tag() helper.
# ---------------------------------------------------------------------------

# Known FIRDS namespaces (we strip them during parsing)
_KNOWN_NAMESPACES = {
    "FullFile": "urn:iso:std:iso:20022:tech:xsd:auth.017.001.01",
    "DeltaFile": "urn:iso:std:iso:20022:tech:xsd:auth.036.001.03",
    "CancelFile": "urn:iso:std:iso:20022:tech:xsd:auth.102.001.01",
    "BAH": "urn:iso:std:iso:20022:tech:xsd:head.001.001.01",
}

# Record wrapper element local names present in the various file types
_RECORD_ELEMENTS = {"RefData", "NewRcrd", "ModfdRcrd", "TermntdRcrd", "CancRcrd"}

# Mapping from wrapper element local name to record_type string stored in cache
_RECORD_TYPE_MAP = {
    "RefData": "FULL",
    "NewRcrd": "NEW",
    "ModfdRcrd": "MOD",
    "TermntdRcrd": "TERM",
    "CancRcrd": "CANC",
}


@dataclass
class InstrumentRecord:
    """A single instrument reference data record parsed from a FIRDS XML file.

    Attributes:
        isin: ISO 6166 ISIN code.
        mic: ISO 10383 Market Identifier Code for the trading venue.
        record_type: One of ``FULL``, ``NEW``, ``MOD``, ``TERM``, ``CANC``.
        cfi_code: CFI classification code (6 chars).
        full_name: Full instrument name.
        short_name: Short instrument name.
        admission_date: Date the instrument was admitted to trading (YYYY-MM-DD).
        termination_date: Date trading was terminated; ``None`` if still active.
        rca: ISO country code of the Relevant Competent Authority.
    """

    isin: str
    mic: str
    record_type: str
    cfi_code: str = ""
    full_name: str = ""
    short_name: str = ""
    admission_date: str = ""
    termination_date: Optional[str] = None
    rca: str = ""


class FirdsXmlParser:
    """Streaming parser for FCA FIRDS XML files.

    Yields :class:`InstrumentRecord` objects without loading the entire file
    into memory, making it suitable for processing files containing hundreds of
    thousands of records.
    """

    def parse(self, xml_path: Path) -> Iterator[InstrumentRecord]:
        """Parse a FIRDS XML file and yield instrument records.

        Args:
            xml_path: Path to the extracted XML file.

        Yields:
            :class:`InstrumentRecord` for each instrument record found.

        Raises:
            ET.ParseError: If the XML is malformed.
            FileNotFoundError: If ``xml_path`` does not exist.
        """
        if not xml_path.exists():
            raise FileNotFoundError(f"FIRDS XML not found: {xml_path}")

        context = ET.iterparse(str(xml_path), events=("start", "end"))
        # Detect namespace from the first 'start' event
        ns_prefix = ""
        root_elem = None

        for event, elem in context:
            if event == "start" and root_elem is None:
                root_elem = elem
                # The tag will be "{namespace}RootElement" or just "RootElement"
                ns_prefix = _extract_namespace(elem.tag)
                continue

            if event == "end":
                local = _local_name(elem.tag)

                if local in _RECORD_ELEMENTS:
                    record = self._parse_record(elem, local, ns_prefix)
                    if record is not None:
                        yield record
                    # Free memory – we no longer need this subtree
                    elem.clear()
                    if root_elem is not None:
                        # Also clear from the root to keep memory flat
                        try:
                            root_elem.clear()
                        except Exception:  # noqa: BLE001
                            pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_record(
        self,
        elem: ET.Element,
        wrapper_local: str,
        ns_prefix: str,
    ) -> Optional[InstrumentRecord]:
        """Extract an :class:`InstrumentRecord` from a record wrapper element.

        Handles both auth.017.001.01 (plain document root) and auth.017.001.02
        (BAH-wrapped, ``head.003.001.01`` root) file variants.  The record
        element's own namespace is used for child lookups rather than the root
        namespace so that BAH-wrapped files resolve correctly.

        For delta files the ``TermntdRcrd`` and ``CancRcrd`` elements may only
        contain the ISIN and MIC (no full attributes), which is sufficient for
        caching purposes.

        Args:
            elem: The parsed XML element for the record wrapper.
            wrapper_local: Local name of the wrapper element (e.g. ``NewRcrd``).
            ns_prefix: XML namespace prefix from the document root (used as
                fallback only; the record element's own namespace takes priority).

        Returns:
            :class:`InstrumentRecord` if valid ISIN and MIC were found, else
            ``None``.
        """
        # BAH-wrapped files (head.003.001.01 root) have a different root
        # namespace from the actual data elements.  Always resolve ns_prefix
        # from the record element itself for reliable child lookups.
        elem_ns = _extract_namespace(elem.tag)
        if elem_ns:
            ns_prefix = elem_ns

        def find(path: str) -> str:
            """Find text of a descendant element, namespace-aware."""
            ns_path = "/".join(f"{ns_prefix}{part}" for part in path.split("/"))
            node = elem.find(ns_path)
            if node is None:
                # Fallback: try without namespace prefix
                node = elem.find(path)
            return (node.text or "").strip() if node is not None else ""

        def find_first(*paths: str) -> str:
            """Try each path in order and return the first non-empty value."""
            for path in paths:
                val = find(path)
                if val:
                    return val
            return ""

        record_type = _RECORD_TYPE_MAP.get(wrapper_local, "FULL")

        isin = find("FinInstrmGnlAttrbts/Id")
        mic = find("TradgVnRltdAttrbts/Id")

        # Cancellation records may not carry attribute blocks at all –
        # fall back to top-level Id / TradgVn elements used in FULCAN schema
        if not isin:
            isin = find("Id")
        if not mic:
            mic = find("TradgVn")

        if not isin or not mic:
            return None

        # auth.017.001.01 uses AdmssnApprvlDtByTheTradgVn
        # auth.017.001.02 uses AdmssnApprvlDtByIssr
        admission_date = _normalise_date(
            find_first(
                "TradgVnRltdAttrbts/AdmssnApprvlDtByTheTradgVn",
                "TradgVnRltdAttrbts/AdmssnApprvlDtByIssr",
                "TradgVnRltdAttrbts/FrstTradDt",
            )
        )

        # auth.017.001.01 nests RCA under TechRcrdId; auth.017.001.02 does not
        rca = find_first(
            "TechRcrdId/TechAttrbts/RlvntCmptntAuthrty",
            "TechAttrbts/RlvntCmptntAuthrty",
        )

        return InstrumentRecord(
            isin=isin,
            mic=mic,
            record_type=record_type,
            cfi_code=find("FinInstrmGnlAttrbts/ClssfctnTp"),
            full_name=find("FinInstrmGnlAttrbts/FullNm"),
            short_name=find("FinInstrmGnlAttrbts/ShrtNm"),
            admission_date=admission_date,
            termination_date=_normalise_date_optional(
                find("TradgVnRltdAttrbts/TermntnDt")
            ),
            rca=rca,
        )


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _extract_namespace(tag: str) -> str:
    """Return the ``{namespace}`` prefix from a Clark-notation tag, or ``''``.

    Args:
        tag: Element tag string, e.g. ``{urn:iso:...}Document``.

    Returns:
        Prefix string including braces, e.g. ``{urn:iso:...}``, or ``''``.
    """
    if tag.startswith("{"):
        return "{" + tag.split("}")[0][1:] + "}"
    return ""


def _local_name(tag: str) -> str:
    """Strip the namespace prefix from a Clark-notation tag.

    Args:
        tag: Element tag string, e.g. ``{urn:iso:...}RefData``.

    Returns:
        Local name portion, e.g. ``RefData``.
    """
    if "}" in tag:
        return tag.split("}")[1]
    return tag


def _normalise_date(value: str) -> str:
    """Return the YYYY-MM-DD portion of a date string, or ``''`` if empty.

    FIRDS date fields may be full ISO 8601 timestamps or plain dates.

    Args:
        value: Raw date string from XML.

    Returns:
        ``YYYY-MM-DD`` string or empty string.
    """
    if not value:
        return ""
    return value[:10]


def _normalise_date_optional(value: str) -> Optional[str]:
    """Like :func:`_normalise_date` but returns ``None`` instead of ``''``.

    Args:
        value: Raw date string from XML.

    Returns:
        ``YYYY-MM-DD`` string or ``None``.
    """
    normalised = _normalise_date(value)
    return normalised if normalised else None
