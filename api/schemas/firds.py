"""
FIRDS Schemas
=============

Pydantic v2 schemas for the FIRDS (Financial Instruments Reference Data System)
reportability check endpoints.

All schemas use camelCase aliases for JSON serialisation to match the
React frontend convention, whilst still accepting snake_case attribute
names in Python code.
"""

from api.schemas.common import _CamelModel


class FirdsRefreshRequest(_CamelModel):
    """Request body for refreshing the FIRDS local SQLite cache.

    Attributes:
        refresh_type: Type of refresh to perform (default: ``"full"``).
        publication_date: Optional ISO date string for a targeted publication
            date refresh, e.g. ``"2026-01-04"``.
        log_level: Logging verbosity (default: ``"INFO"``).
    """

    refresh_type: str = "full"
    publication_date: str | None = None
    log_level: str = "INFO"


class FirdsCheckRequest(_CamelModel):
    """Request body for checking FIRDS reportability of one or more instruments.

    Attributes:
        mode: Processing mode — ``"single"`` (default) or ``"batch"``.
        isin: ISIN code to check; used in ``"single"`` mode.
        input_file: Path to a CSV file of ISINs to check; used in ``"batch"`` mode.
        output_file: Path for the batch results output CSV; used in ``"batch"`` mode.
        log_level: Logging verbosity (default: ``"INFO"``).
    """

    mode: str = "single"
    isin: str | None = None
    input_file: str | None = None
    output_file: str | None = None
    log_level: str = "INFO"


class FirdsBackfillRequest(_CamelModel):
    """Request body for backfilling FIRDS reportability data across a directory of files.

    Attributes:
        input_directory: Path to the directory containing input CSV files.
        output_directory: Path to the directory for annotated output files.
        log_level: Logging verbosity (default: ``"INFO"``).
    """

    input_directory: str
    output_directory: str
    log_level: str = "INFO"
