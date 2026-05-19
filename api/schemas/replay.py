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
    """Request body for Phase 2 Feedback replay processing.

    Attributes:
        kaizen_input: Path to the directory containing the Kaizen export source
            files (auto-resolved from ``replay/phase_2/feedback/kaizen``).
        incident_files: Path to the accuracy_testing templates directory used as
            incident reference files (auto-resolved from
            ``accuracy_testing/templates``).
        output_file: Path to the directory for processed output files
            (auto-resolved from ``replay/phase_2/feedback/output``).
        fiscal_year: Fiscal year string, e.g. ``"FY26"``.
        quarter: Quarter string, e.g. ``"Q1"``.
        log_level: Logging verbosity (default: ``"INFO"``)
        log_output: Directory for log files (default: ``"logs"``)
    """

    kaizen_input: str
    incident_files: str
    output_file: str
    fiscal_year: str
    quarter: str
    log_level: str = "INFO"
    log_output: str = "/app/data/logs"


class ReplayPhase2FinalRequest(_CamelModel):
    """Request body for Phase 2 Final Lookup processing.

    Attributes:
        replay_input_file: Path to the directory containing Phase 2 Feedback
            output CSV files (auto-resolved from
            ``replay/phase_2/feedback/output``).
        unavista_files: Path to the directory containing UnaVista reference
            files (auto-resolved from ``replay/phase_2/final_lookup/unavista``).
        incident_files: Path to the accuracy_testing templates directory used as
            incident reference files (auto-resolved from
            ``accuracy_testing/templates``).
        output_file: Path to the directory for annotated final lookup output
            files (auto-resolved from ``replay/phase_2/final_lookup/output``).
        fiscal_year: Fiscal year string, e.g. ``"FY26"``.
        quarter: Quarter string, e.g. ``"Q1"``.
        log_level: Logging verbosity (default: ``"INFO"``).
        log_output: Directory for log files (default: ``"logs"``)
    """

    replay_input_file: str
    unavista_files: str
    incident_files: str
    output_file: str
    fiscal_year: str
    quarter: str
    log_level: str = "INFO"
    log_output: str = "/app/data/logs"


class ReplayPhase3Request(_CamelModel):
    """Request body for Phase 3 Feedback replay processing.

    Attributes:
        input_file: Path to the directory containing Phase 3 Kaizen export
            source files (auto-resolved from ``replay/phase_3/feedback/kaizen``).
        incident_files: Path to the directory containing incident template CSV
            files (auto-resolved from ``accuracy_testing/templates``).
        output_file: Path to the directory for processed output files
            (auto-resolved from ``replay/phase_3/feedback/output``).
        fiscal_year: Fiscal year string, e.g. ``"FY26"``.
        quarter: Quarter string, e.g. ``"Q1"``.
        log_level: Logging verbosity (default: ``"INFO"``).
        log_output: Directory for log files (default: ``"logs"``)
    """

    input_file: str
    incident_files: str
    output_file: str
    fiscal_year: str
    quarter: str
    log_level: str = "INFO"
    log_output: str = "/app/data/logs"


class ReplayPhase3FinalRequest(_CamelModel):
    """Request body for Phase 3 final lookup processing.

    Attributes:
        input_file: Path to the Phase 3 Feedback output directory containing
            Inconsistent summary files (auto-resolved from
            ``replay/phase_3/feedback/output``).
        unavista_files: Path to the directory containing UnaVista reference
            files (auto-resolved from ``replay/phase_3/final_lookup/unavista``).
        incident_files: Path to the accuracy_testing/templates directory
            containing incident CSVs (auto-resolved from
            ``accuracy_testing/templates``).
        output_file: Path to the directory for final lookup output files
            (auto-resolved from ``replay/phase_3/final_lookup/output``).
        fiscal_year: Fiscal year string, e.g. ``"FY26"``.
        quarter: Quarter string, e.g. ``"Q1"``.
        log_level: Logging verbosity (default: ``"INFO"``).
        log_output: Directory for log files (default: ``"logs"``)
    """

    input_file: str
    unavista_files: str
    incident_files: str
    output_file: str
    fiscal_year: str
    quarter: str
    log_level: str = "INFO"
    log_output: str = "/app/data/logs"


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
    dry_run: bool = False
