"""
Replay Schemas
==============

Pydantic v2 schemas for the replay processing endpoints.

All schemas use camelCase aliases for JSON serialisation to match the
React frontend convention, whilst still accepting snake_case attribute
names in Python code.
"""

from api.schemas.common import _CamelModel


class ReplayPhase2Request(_CamelModel):
    """Request body for Phase 2 replay processing.

    Attributes:
        input_file: Path to the directory containing replay input CSV files.
        output_file: Path to the directory for processed output files.
        fiscal_year: Fiscal year string, e.g. ``"FY26"``.
        quarter: Quarter string, e.g. ``"Q1"``.
        log_level: Logging verbosity (default: ``"INFO"``).
    """

    input_file: str
    output_file: str
    fiscal_year: str
    quarter: str
    log_level: str = "INFO"


class ReplayPhase3Request(_CamelModel):
    """Request body for Phase 3 replay processing.

    Attributes:
        input_file: Path to the directory containing Phase 3 replay input CSV files.
        feedback_file: Path to the directory containing incident template CSV files.
        output_file: Path to the directory for processed output files.
        fiscal_year: Fiscal year string, e.g. ``"FY26"``.
        quarter: Quarter string, e.g. ``"Q1"``.
        log_level: Logging verbosity (default: ``"INFO"``).
    """

    input_file: str
    feedback_file: str
    output_file: str
    fiscal_year: str
    quarter: str
    log_level: str = "INFO"


class ReplayPhase3FinalRequest(_CamelModel):
    """Request body for Phase 3 final lookup processing.

    Attributes:
        input_file: Path to the Phase 3 output directory containing Inconsistent summary files.
        output_file: Path to the directory for final lookup output files.
        fiscal_year: Fiscal year string, e.g. ``"FY26"``.
        quarter: Quarter string, e.g. ``"Q1"``.
        log_level: Logging verbosity (default: ``"INFO"``).
    """

    input_file: str
    output_file: str
    fiscal_year: str
    quarter: str
    log_level: str = "INFO"


class ReplayMergeRequest(_CamelModel):
    """Request body for merging Phase 3 Inconsistent ID and Name summary files.

    Attributes:
        buyer_file: Path to the directory containing Inconsistent IDs Summary CSV files.
        seller_file: Path to the directory containing Inconsistent Names Summary CSV files.
        output_file: Path to the directory for merged output files.
        log_level: Logging verbosity (default: ``"INFO"``).
    """

    buyer_file: str
    seller_file: str
    output_file: str
    log_level: str = "INFO"
