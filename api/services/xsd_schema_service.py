"""XSD Schema Service
===================

Service-layer helpers for parsing user-provided XSD content into a
flattened, UI-friendly column structure.
"""

from __future__ import annotations

from dataclasses import dataclass
import xml.etree.ElementTree as ET

from src.utils.xml_csv_converter import XMLToCSVConverter


@dataclass
class XsdParseResult:
    """Result of parsing XSD schema content."""

    columns: list[dict[str, object]]
    errors: list[str]
    warnings: list[str]
    unsupported_constructs: list[str]
    stats: dict[str, int]


class XsdSchemaService:
    """Service for parsing and validating XSD content."""

    _UNSUPPORTED_TAGS: frozenset[str] = frozenset(
        {
            "any",
            "anyAttribute",
            "key",
            "keyref",
            "unique",
            "substitutionGroup",
        }
    )

    @staticmethod
    def _strip_namespace(tag: str) -> str:
        if tag.startswith("{"):
            return tag.split("}", 1)[1]
        return tag

    def _collect_unsupported_constructs(self, xsd_content: str) -> list[str]:
        """Collect unsupported XSD constructs as warnings."""
        try:
            root = ET.fromstring(xsd_content)
        except ET.ParseError:
            return []

        seen: set[str] = set()
        for elem in root.iter():
            local_tag = self._strip_namespace(elem.tag)
            if local_tag in self._UNSUPPORTED_TAGS:
                seen.add(local_tag)
            if "substitutionGroup" in elem.attrib:
                seen.add("substitutionGroup")
            if elem.get("abstract") == "true":
                seen.add("abstract")

        return sorted(seen)

    def parse_schema(self, xsd_content: str) -> XsdParseResult:
        """Parse XSD content into flattened field metadata.

        Args:
            xsd_content: Raw XSD text supplied by a user.

        Returns:
            Parsed schema structure and non-fatal warnings.

        Raises:
            ValueError: If the XSD is invalid or unsupported.
        """
        structure = XMLToCSVConverter.parse_xsd_structure(xsd_content)
        errors: list[str] = []
        warnings: list[str] = []
        unsupported_constructs = self._collect_unsupported_constructs(xsd_content)

        if not structure:
            warnings.append("No leaf fields were extracted from the provided XSD.")

        if unsupported_constructs:
            warnings.append(
                "Schema includes constructs that are only partially supported by preview parsing."
            )

        stats = {
            "field_count": len(structure),
            "unsupported_construct_count": len(unsupported_constructs),
        }

        return XsdParseResult(
            columns=structure,
            errors=errors,
            warnings=warnings,
            unsupported_constructs=unsupported_constructs,
            stats=stats,
        )


xsd_schema_service = XsdSchemaService()
