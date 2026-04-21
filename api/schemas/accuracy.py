"""
Accuracy Testing Schemas
========================

Pydantic v2 schemas for the accuracy testing endpoints.

All schemas use camelCase aliases for JSON serialisation to match the
React frontend convention, whilst still accepting snake_case attribute
names in Python code.
"""

from typing import Literal

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

    """

    input_directory: str
    output_directory: str
    template_directory: str
    log_output: str = "/app/data/logs"


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

    """

    incident_code: str
    input_file: str
    template_file: str
    output_file: str
    template_id_column: str = "Buyer ID Code"
    template_type_column: str = "Type of Buyer ID Code"
    log_output: str = "/app/data/logs"


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
        log_output: Directory for log files (default: ``"logs"``).
        dry_run: If ``True``, validate without executing the scripts (default: ``False``).
        stop_on_error: If ``True``, stop execution on first validation failure
            (default: ``False``).
        selected_scripts: Optional subset of ``validation_types`` to execute.
            When provided, only these scripts are included in the run; the
            order is preserved from ``validation_types``.  When ``None`` or
            empty, all ``validation_types`` are executed.
    """

    testing_period: TestingPeriod
    validation_types: list[str]
    input_directory: str
    output_directory: str
    template_directory: str
    log_level: str = "INFO"
    log_output: str = "/app/data/logs"
    dry_run: bool = False
    stop_on_error: bool = False
    selected_scripts: list[str] | None = None


class DiscoveryRequest(_CamelModel):
    """Request body for discovering incident CSV files in a directory.

    Attributes:
        input_directory: Path to the directory to scan for incident CSV files.
    """

    input_directory: str


class DiscoveryResult(_CamelModel):
    """Discovery result for a single validation script.

    Attributes:
        script_name: The validation script identifier.
        codes: The incident codes associated with this validation.
        found_files: List of CSV file paths matching the incident codes.
    """

    script_name: str
    codes: list[str]
    found_files: list[str]


class DiscoveryResponse(_CamelModel):
    """Response body for the file discovery endpoint.

    Attributes:
        results: Per-script discovery results.
        total_found: Total number of unique files found across all scripts.
    """

    results: list[DiscoveryResult]
    total_found: int


class IncidentRunConfig(_CamelModel):
    """Configuration for running a single incident through a validation script.

    Attributes:
        script_name: Registered script identifier, e.g. ``"buyer_id_validation"``.
        incident_code: Incident code, e.g. ``"7_35"``.
        input_file: Path to the extract CSV file for this incident.
        template_file: Path to the Kaizen template CSV file.
        output_file: Path for the validation results output file.
        template_id_column: Column name for the identification code in the template.
            When ``None`` the script uses its own default (e.g. ``"Buyer identification
            code"``).  Override when the template uses a non-standard header such as
            ``"Buyer ID Code"``.
        template_type_column: Column name for the identification code type in the
            template.  When ``None`` the script uses its own default.
    """

    script_name: str
    incident_code: str
    input_file: str
    template_file: str
    output_file: str
    template_id_column: str | None = None
    template_type_column: str | None = None


class RunIncidentsRequest(_CamelModel):
    """Request body for running multiple incidents through their validation scripts.

    Each incident is run sequentially in single mode. Execution stops on the
    first failure when ``stop_on_error`` is ``True``.

    Attributes:
        testing_period: Fiscal year and quarter for the testing run.
        incidents: List of per-incident configurations to execute.
        log_level: Logging verbosity (default: ``"INFO"``).
        dry_run: If ``True``, validate without executing (default: ``False``).
        stop_on_error: If ``True``, stop on first failure (default: ``False``).
    """

    testing_period: TestingPeriod
    incidents: list[IncidentRunConfig]
    log_level: str = "INFO"
    dry_run: bool = False
    stop_on_error: bool = False


class ExtractGeneratorConfig(_CamelModel):
    """Extended configuration for the SQL/DTF Extract Generator.

    Attributes:
        batch_size: Number of transaction references per SQL batch (default: 900).
        column: Column name containing transaction references.
        output_format: Output format — ``"sql"``, ``"dtf"``, or ``"both"``
            (default: ``"both"``).
        dtf_template: Optional path to a custom DTF template file.
        csv_output_dir: Directory path embedded in DTF files where System i
            will write CSV output.  Auto-filled from SmartPathConfig extracts dir.
    """

    batch_size: int = 900
    column: str | None = None
    output_format: Literal["sql", "dtf", "both"] = "both"
    dtf_template: str | None = None
    csv_output_dir: str | None = None
