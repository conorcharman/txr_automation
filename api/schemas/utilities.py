"""
Utilities Schemas
=================

Pydantic v2 schemas for the file conversion utility endpoints.

All schemas use camelCase aliases for JSON serialisation to match the
React frontend convention, whilst still accepting snake_case attribute
names in Python code.
"""

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
        log_level: Logging verbosity (default: ``"INFO"``).
    """

    input_file: str
    output_file: str
    log_level: str = "INFO"


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
