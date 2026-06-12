"""
Utilities Schemas
=================

Pydantic v2 schemas for the file conversion utility endpoints.

All schemas use camelCase aliases for JSON serialisation to match the
React frontend convention, whilst still accepting snake_case attribute
names in Python code.
"""

from pydantic import Field

from api.schemas.common import _CamelModel


class XlsxConverterRequest(_CamelModel):
    """Request body for converting XLSX files to CSV format.

    Attributes:
        mode: Processing mode — ``"recursive"`` (default) or ``"single"``.
        parent_dir: Parent directory to scan recursively for XLSX files;
            used in ``"recursive"`` mode.
        input_dir: Directory containing XLSX files to convert; used in ``"single"`` mode.
        output_dir: Directory for converted CSV output files; used in ``"single"`` mode.
        filter_year: Filter by fiscal year, e.g. ``"FY25"``.
        filter_quarter: Filter by quarter, e.g. ``"Q3"``.
        filter_phase: Filter by phase names, e.g. ``["phase_ii", "phase_iii"]``.
        dry_run: If ``True``, list what would be converted without writing files.
        force: If ``True``, force overwrite existing output files.
        log_level: Logging verbosity (default: ``"INFO"``).
    """

    mode: str = "recursive"
    parent_dir: str | None = None
    input_dir: str | None = None
    output_dir: str | None = None
    filter_year: str | None = None
    filter_quarter: str | None = None
    filter_phase: list[str] | None = None
    dry_run: bool = False
    force: bool = False
    log_level: str = "INFO"


class XmlConverterRequest(_CamelModel):
    """Request body for converting a single XML file to CSV format.

    Attributes:
        input_file: Path to the input XML file.
        output_file: Path for the output CSV file.
        xsd_content: Optional user-supplied XSD content. When present, this
            overrides any schema declaration in the XML.
        log_level: Logging verbosity (default: ``"INFO"``).
    """

    input_file: str
    output_file: str
    xsd_content: str | None = Field(default=None, max_length=5_000_000)
    log_level: str = "INFO"


class XsdParseRequest(_CamelModel):
    """Request body for parsing user-provided XSD content."""

    xsd_content: str = Field(min_length=1, max_length=5_000_000)


class XsdColumnEntry(_CamelModel):
    """Flattened schema field metadata used by the UI preview."""

    name: str
    path: str
    type_name: str = ""
    min_occurs: str = "1"
    max_occurs: str = "1"
    constraints: dict[str, str | list[str]] = Field(default_factory=dict)
    source_kind: str = "element"
    field_warnings: list[str] = Field(default_factory=list)


class XsdParseResponse(_CamelModel):
    """Response body returned by the XSD parsing endpoint."""

    columns: list[XsdColumnEntry]
    column_count: int
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    unsupported_constructs: list[str] = Field(default_factory=list)
    stats: dict[str, int] = Field(default_factory=dict)


class SetupDirectoriesRequest(_CamelModel):
    """Request body for creating the standard FY/Q directory hierarchy.

    Attributes:
        fiscal_year: Fiscal year identifier, e.g. ``"FY26"``.
        quarter: Quarter identifier, e.g. ``"Q1"``.
        log_level: Logging verbosity (default: ``"INFO"``).
    """

    fiscal_year: str
    quarter: str
    log_level: str = "INFO"
