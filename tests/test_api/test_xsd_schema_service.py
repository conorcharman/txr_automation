"""Tests for XSD schema parsing diagnostics service."""

from api.services.xsd_schema_service import xsd_schema_service


def test_parse_schema_extracts_constraints() -> None:
    """Restriction constraints should be surfaced for preview rendering."""
    xsd_content = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<xs:schema xmlns:xs=\"http://www.w3.org/2001/XMLSchema\">
  <xs:simpleType name=\"CodeType\">
    <xs:restriction base=\"xs:string\">
      <xs:pattern value=\"[A-Z]{4}\"/>
      <xs:enumeration value=\"ABCD\"/>
      <xs:enumeration value=\"WXYZ\"/>
    </xs:restriction>
  </xs:simpleType>
  <xs:element name=\"Root\">
    <xs:complexType>
      <xs:sequence>
        <xs:element name=\"Code\" type=\"CodeType\"/>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>
"""

    result = xsd_schema_service.parse_schema(xsd_content)

    assert result.errors == []
    assert result.stats["field_count"] == 1
    assert result.columns[0]["constraints"]["pattern"] == "[A-Z]{4}"
    assert result.columns[0]["constraints"]["enum_values"] == ["ABCD", "WXYZ"]


def test_parse_schema_collects_unsupported_constructs() -> None:
    """Unsupported constructs should be surfaced as warnings, not hard failures."""
    xsd_content = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<xs:schema xmlns:xs=\"http://www.w3.org/2001/XMLSchema\">
  <xs:element name=\"Root\">
    <xs:complexType>
      <xs:sequence>
        <xs:any minOccurs=\"0\" maxOccurs=\"unbounded\"/>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>
"""

    result = xsd_schema_service.parse_schema(xsd_content)

    assert "any" in result.unsupported_constructs
    assert len(result.warnings) >= 1
    assert result.errors == []


def test_parse_schema_invalid_xsd_raises_value_error() -> None:
    """Malformed XSD must raise ValueError for API to map to 422."""
    try:
        xsd_schema_service.parse_schema("not xml")
    except ValueError:
        return

    raise AssertionError("Expected ValueError for malformed XSD")
