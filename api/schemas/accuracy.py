"""
Accuracy Testing Schemas
========================

Pydantic v2 schemas for the accuracy testing endpoints.

All schemas use camelCase aliases for JSON serialisation to match the
React frontend convention, whilst still accepting snake_case attribute
names in Python code.
"""

from api.schemas.common import _CamelModel


class TestingPeriod(_CamelModel):
    """Fiscal year and quarter for a testing period.

    Attributes:
        fiscal_year: Fiscal year string, e.g. ``"FY26"``.
        quarter: Quarter string, e.g. ``"Q1"``.
    """

    fiscal_year: str
    quarter: str


class BatchModeConfig(_CamelModel):
    """Batch mode configuration — matches files by incident code pattern in a directory.

    Attributes:
        input_directory: Path to the directory containing extract CSV files.
        output_directory: Path to the directory for validated output files.
        template_directory: Path to the directory containing Kaizen template files.
        log_output: Directory for log output (default: ``"logs"``).
        tracker_files: Optional list of tracker CSV file paths.
    """

    input_directory: str
    output_directory: str
    template_directory: str
    log_output: str = "logs"
    tracker_files: list[str] = []


class SingleModeConfig(_CamelModel):
    """Single mode configuration — explicit file paths for one incident.

    Attributes:
        incident_code: Incident code to validate, e.g. ``"7_37"``.
        input_file: Path to the extract CSV file.
        template_file: Path to the Kaizen template CSV file.
        output_file: Path for the validation results output file.
        template_id_column: Column name for the identification code in the template.
        template_type_column: Column name for the identification code type in the template.
        log_output: Directory for log output (default: ``"logs"``).
        tracker_files: Optional list of tracker CSV file paths.
    """

    incident_code: str
    input_file: str
    template_file: str
    output_file: str
    template_id_column: str = "Buyer identification code"
    template_type_column: str = "Type of buyer identification code"
    log_output: str = "logs"
    tracker_files: list[str] = []


class RunValidationRequest(_CamelModel):
    """Request body for running a single accuracy validation script.

    Attributes:
        script_name: Registered script identifier; must be a key returned by
            ``GET /api/accuracy/scripts``.
        testing_period: Fiscal year and quarter for the testing run.
        mode: Processing mode — ``"batch"`` (default) or ``"single"``.
        batch_config: Batch mode configuration; required when ``mode`` is ``"batch"``.
        single_config: Single mode configuration; required when ``mode`` is ``"single"``.
        log_level: Logging verbosity (default: ``"INFO"``).
        dry_run: If ``True``, validate the config without executing the script (default: ``False``).
    """

    script_name: str
    testing_period: TestingPeriod
    mode: str = "batch"
    batch_config: BatchModeConfig | None = None
    single_config: SingleModeConfig | None = None
    log_level: str = "INFO"
    dry_run: bool = False


class RunAllRequest(_CamelModel):
    """Request body for the ``run_all_validations`` orchestrator script.

    Attributes:
        testing_period: Fiscal year and quarter for the testing run.
        validation_types: List of registered script_name keys to include in the run.
        input_directory: Path to the directory containing extract CSV files.
        output_directory: Path to the directory for validated output files.
        template_directory: Path to the directory containing Kaizen template files.
        log_level: Logging verbosity (default: ``"INFO"``).
        dry_run: If ``True``, validate without executing the scripts (default: ``False``).
    """

    testing_period: TestingPeriod
    validation_types: list[str]
    input_directory: str
    output_directory: str
    template_directory: str
    log_level: str = "INFO"
    dry_run: bool = False
