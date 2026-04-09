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
        db_path: Optional path to the SQLite database file. When omitted the
            server-side default from ``FIRDS_DB_PATH`` is used.
        log_level: Logging verbosity (default: ``"INFO"``).
    """

    refresh_type: str = "full"
    publication_date: str | None = None
    db_path: str | None = None
    log_level: str = "INFO"


class FirdsCheckRequest(_CamelModel):
    """Request body for checking FIRDS reportability of one or more instruments.

    Attributes:
        mode: Processing mode — ``"single"`` (default) or ``"batch"``.
        isin: ISIN code to check; used in ``"single"`` mode.
        date: Trade date (``YYYY-MM-DD``); required in ``"single"`` mode.
        mic: Optional MIC code to narrow venue matching in ``"single"`` mode.
        input_file: Path to a CSV file of ISINs to check; used in ``"batch"`` mode.
        output_file: Path for the batch results output CSV; used in ``"batch"`` mode.
        log_level: Logging verbosity (default: ``"INFO"``).
    """

    mode: str = "single"
    isin: str | None = None
    date: str | None = None
    mic: str | None = None
    input_file: str | None = None
    output_file: str | None = None
    log_level: str = "INFO"


class FirdsBackfillRequest(_CamelModel):
    """Request body for backfilling FIRDS reportability data onto a CSV file.

    Attributes:
        input_file: Path to the input CSV file to annotate.
        output_file: Path for the annotated output CSV file.
        format: CSV format hint — ``"auto"`` (default), ``"incident"``, or ``"generic"``.
        db_path: Optional path to the SQLite database file. When omitted the
            server-side default from ``FIRDS_DB_PATH`` is used.
        skip_refresh: If ``True``, skip the automatic cache refresh before
            backfilling (default: ``False``).
        log_level: Logging verbosity (default: ``"INFO"``).
    """

    input_file: str
    output_file: str
    format: str = "auto"
    db_path: str | None = None
    skip_refresh: bool = False
    log_level: str = "INFO"


class FirdsLookupResponse(_CamelModel):
    """Response body for a synchronous FIRDS reportability lookup.

    Attributes:
        is_reportable: Whether the ISIN is reportable.
        reason: Human-readable reason for the reportability determination.
        isin: The ISIN that was checked.
        trade_date: The trade date used for the check.
        mic: The MIC code used, if any.
        matched_mics: List of MIC codes that matched in the FIRDS data.
    """

    is_reportable: bool
    reason: str
    isin: str
    trade_date: str
    mic: str | None = None
    matched_mics: list[str] = []
