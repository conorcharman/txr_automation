"""
GLEIF Schemas
=============

Pydantic v2 schemas for the GLEIF (Global Legal Entity Identifier Foundation)
LEI lookup endpoints.

All schemas use camelCase aliases for JSON serialisation to match the
React frontend convention, whilst still accepting snake_case attribute
names in Python code.
"""

from api.schemas.common import _CamelModel


class GleifRefreshRequest(_CamelModel):
    """Request body for refreshing the GLEIF local SQLite cache.

    Attributes:
        refresh_type: Type of refresh to perform — ``"full"`` (default) or ``"delta"``.
        delta_type: Delta interval for delta mode; one of ``"8h"``, ``"24h"``,
            ``"7d"``, or ``"31d"``.  Ignored unless ``refresh_type`` is ``"delta"``.
        log_level: Logging verbosity (default: ``"INFO"``).
    """

    refresh_type: str = "full"
    delta_type: str | None = None
    log_level: str = "INFO"


class GleifCheckRequest(_CamelModel):
    """Request body for looking up GLEIF LEI data.

    Attributes:
        mode: Processing mode — ``"single"`` (default), ``"name_search"``, or ``"batch"``.
        lei: LEI code to look up; used in ``"single"`` mode.
        name: Legal entity name to search; used in ``"name_search"`` mode.
        input_file: Path to a CSV file of LEIs to check; used in ``"batch"`` mode.
        output_file: Path for the batch results output CSV; used in ``"batch"`` mode.
        log_level: Logging verbosity (default: ``"INFO"``).
    """

    mode: str = "single"
    lei: str | None = None
    name: str | None = None
    input_file: str | None = None
    output_file: str | None = None
    log_level: str = "INFO"


class GleifBackfillRequest(_CamelModel):
    """Request body for backfilling GLEIF LEI data across a directory of files.

    Attributes:
        input_directory: Path to the directory containing input CSV files.
        output_directory: Path to the directory for annotated output files.
        log_level: Logging verbosity (default: ``"INFO"``).
    """

    input_directory: str
    output_directory: str
    log_level: str = "INFO"
