#!/usr/bin/env python3
"""
Scheduler Models
================

Enumerations and dataclasses for the TXR Automation scheduler subsystem.

Contains all data-transfer objects used across store, engine, and pipeline
components — enums for frequency/step/status/type, and dataclasses for
schedule configuration, run records, and pipeline presets.

Version 2.0 Changes:
- Added QUARTERLY to ScheduleFrequency
- PipelineStep kept for backwards compatibility but is now legacy;
  the 13-step pipeline list lives in gui.constants.PIPELINE_STEPS
- Removed PIPELINE_PRESETS (replaced by API pipeline concept)

Version 1.0 Changes:
- Initial implementation for Phase 1 scheduler foundation
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ScheduleFrequency(enum.Enum):
    """How often a scheduled pipeline should run."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    CUSTOM = "custom"


class PipelineStep(enum.Enum):
    """Ordered steps that make up a pipeline execution."""

    EXTRACT = "extract"
    COLLATE = "collate"
    VALIDATE = "validate"
    PUSH = "push"


class RunStatus(enum.Enum):
    """Lifecycle status of a pipeline run or individual step."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Human-readable display names for each ValidationType value.
_DISPLAY_NAMES: dict[str, str] = {
    "buyer": "Buyer ID Validation",
    "seller": "Seller ID Validation",
    "inconsistent-buyer": "Inconsistent Buyer ID Validation",
    "inconsistent-seller": "Inconsistent Seller ID Validation",
    "ftbdm": "Fund Trade Buyer Decision Maker Validation",
    "ftsdm": "Fund Trade Seller Decision Maker Validation",
    "non-zero-qty": "Non-Zero Net Quantity Validation",
    "non-zero-amt": "Non-Zero Net Amount Validation",
    "incorrect-time": "Incorrect Time Validation",
    "incorrect_net_amount": "Incorrect Net Amount Validation",
}


class PeriodType(enum.Enum):
    """How the data extraction period is specified for a schedule.

    Attributes:
        FISCAL_QUARTER: Full fiscal-year quarter (e.g. FY26 Q2).
            Suitable for quarterly or monthly schedules.
        RELATIVE: A rolling window of N calendar days ending at midnight
            before each run.  Suitable for hourly, daily, or weekly runs.
        DATE_RANGE: An explicit fixed start/end date pair.
            Useful for ad-hoc or backfill schedules.
    """

    FISCAL_QUARTER = "fiscal_quarter"
    RELATIVE = "relative"
    DATE_RANGE = "date_range"


#: Default relative-day windows suggested per frequency.
FREQUENCY_PERIOD_DEFAULTS: dict[str, tuple[PeriodType, int]] = {
    "hourly":    (PeriodType.RELATIVE, 1),
    "daily":     (PeriodType.RELATIVE, 1),
    "weekly":    (PeriodType.RELATIVE, 7),
    "monthly":   (PeriodType.RELATIVE, 30),
    "quarterly": (PeriodType.FISCAL_QUARTER, 0),
    "custom":    (PeriodType.FISCAL_QUARTER, 0),
}


class ValidationType(enum.Enum):
    """Validation script types corresponding to INCIDENT_SCRIPT_MODULES keys."""

    BUYER_ID = "buyer"
    SELLER_ID = "seller"
    INCONSISTENT_BUYER_ID = "inconsistent-buyer"
    INCONSISTENT_SELLER_ID = "inconsistent-seller"
    FUND_TRADE_BUYER_DM = "ftbdm"
    FUND_TRADE_SELLER_DM = "ftsdm"
    NON_ZERO_NET_QTY = "non-zero-qty"
    NON_ZERO_NET_AMT = "non-zero-amt"
    INCORRECT_TIME = "incorrect-time"
    INCORRECT_NET_AMOUNT = "incorrect_net_amount"

    @property
    def script_module(self) -> str:
        """Return the Python module path for this validation type.

        Returns:
            Dotted module path string (e.g. ``accuracy_testing.scripts.buyer_id_validation``).
        """
        from src.gui.constants import INCIDENT_SCRIPT_MODULES  # noqa: PLC0415

        return INCIDENT_SCRIPT_MODULES[self.value]

    @property
    def display_name(self) -> str:
        """Return a human-readable display name for the validation type.

        Returns:
            Display name string (e.g. ``"Buyer ID Validation"``).
        """
        return _DISPLAY_NAMES.get(self.value, self.name.replace("_", " ").title())


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class TestingPeriod:
    """Fiscal year and quarter pairing for a testing cycle.

    Attributes:
        fiscal_year: Fiscal year label (e.g. ``"FY26"``).
        quarter: Quarter label (e.g. ``"Q2"``).
    """

    fiscal_year: str
    quarter: str

    def to_dict(self) -> dict[str, str]:
        """Serialise to a plain dictionary.

        Returns:
            Dictionary with ``fiscal_year`` and ``quarter`` keys.
        """
        return {"fiscal_year": self.fiscal_year, "quarter": self.quarter}

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> TestingPeriod:
        """Deserialise from a plain dictionary.

        Args:
            data: Dictionary with ``fiscal_year`` and ``quarter`` keys.

        Returns:
            Populated :class:`TestingPeriod` instance.
        """
        return cls(
            fiscal_year=data.get("fiscal_year", "FY26"),
            quarter=data.get("quarter", "Q1"),
        )


@dataclass
class SchedulePeriod:
    """Flexible period specification for a scheduled pipeline run.

    A schedule period can be a full fiscal quarter, a rolling window of
    calendar days, or an explicit date range.  The :attr:`period_type`
    field governs which of the other fields are meaningful.

    Attributes:
        period_type: How the period is expressed.
        fiscal_year: Fiscal year label (e.g. ``"FY26"``).  Used when
            ``period_type`` is ``FISCAL_QUARTER``.
        quarter: Quarter label (e.g. ``"Q2"``).  Used when
            ``period_type`` is ``FISCAL_QUARTER``.
        relative_days: Number of calendar days ending yesterday.  Used
            when ``period_type`` is ``RELATIVE``; e.g. ``7`` means
            "the 7 days up to and including yesterday".
        date_range_start: Explicit start date (inclusive).  Used when
            ``period_type`` is ``DATE_RANGE``.
        date_range_end: Explicit end date (inclusive).  Used when
            ``period_type`` is ``DATE_RANGE``.
    """

    period_type: PeriodType = PeriodType.FISCAL_QUARTER
    fiscal_year: str = "FY26"
    quarter: str = "Q1"
    relative_days: int = 1
    date_range_start: date | None = None
    date_range_end: date | None = None

    def to_date_range(self) -> tuple[date, date]:
        """Resolve the period to a concrete (start_date, end_date) pair.

        For RELATIVE periods the window ends on *yesterday* at the time of
        calling, so repeated calls on different days will return different
        values — this is the desired behaviour for rolling automated runs.

        Returns:
            Tuple of ``(start_date, end_date)``, both inclusive.

        Raises:
            ValueError: If ``period_type`` is DATE_RANGE but either bound
                is ``None``, or if the fiscal quarter string is invalid.
        """
        from datetime import timedelta

        today = date.today()

        if self.period_type == PeriodType.RELATIVE:
            end = today - timedelta(days=1)
            start = end - timedelta(days=self.relative_days - 1)
            return start, end

        if self.period_type == PeriodType.DATE_RANGE:
            if self.date_range_start is None or self.date_range_end is None:
                raise ValueError("date_range_start and date_range_end must be set for DATE_RANGE period")
            return self.date_range_start, self.date_range_end

        # FISCAL_QUARTER
        try:
            fy_num = int(self.fiscal_year.lstrip("FYfy"))
        except ValueError as exc:
            raise ValueError(f"Invalid fiscal year: {self.fiscal_year!r}") from exc
        fy_start_year = 2000 + fy_num - 1  # FY26 → calendar 2025
        quarter_map: dict[str, tuple[date, date]] = {
            "Q1": (date(fy_start_year, 4, 1),     date(fy_start_year, 6, 30)),
            "Q2": (date(fy_start_year, 7, 1),     date(fy_start_year, 9, 30)),
            "Q3": (date(fy_start_year, 10, 1),    date(fy_start_year, 12, 31)),
            "Q4": (date(fy_start_year + 1, 1, 1), date(fy_start_year + 1, 3, 31)),
        }
        key = self.quarter.upper()
        if key not in quarter_map:
            raise ValueError(f"Invalid quarter: {self.quarter!r}")
        return quarter_map[key]

    def label(self) -> str:
        """Return a short human-readable label for display and file naming.

        Examples:
            - FISCAL_QUARTER → ``"FY26_Q2"``
            - RELATIVE (1 day) → ``"last1d"``
            - RELATIVE (7 days) → ``"last7d"``
            - DATE_RANGE → ``"20260101_20260331"``

        Returns:
            Compact slug suitable for embedding in a filename.
        """
        if self.period_type == PeriodType.FISCAL_QUARTER:
            return f"{self.fiscal_year}_{self.quarter}"
        if self.period_type == PeriodType.RELATIVE:
            return f"last{self.relative_days}d"
        # DATE_RANGE
        start = self.date_range_start
        end = self.date_range_end
        if start and end:
            return f"{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}"
        return "custom_range"

    def to_dict(self) -> dict:
        """Serialise to a JSON-compatible dictionary.

        Returns:
            Dictionary suitable for QSettings storage.
        """
        return {
            "period_type": self.period_type.value,
            "fiscal_year": self.fiscal_year,
            "quarter": self.quarter,
            "relative_days": self.relative_days,
            "date_range_start": self.date_range_start.isoformat() if self.date_range_start else None,
            "date_range_end": self.date_range_end.isoformat() if self.date_range_end else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SchedulePeriod:
        """Deserialise from a plain dictionary.

        Args:
            data: Dictionary as produced by :meth:`to_dict`.

        Returns:
            Populated :class:`SchedulePeriod` instance.
        """
        raw_start = data.get("date_range_start")
        raw_end = data.get("date_range_end")
        return cls(
            period_type=PeriodType(data.get("period_type", PeriodType.FISCAL_QUARTER.value)),
            fiscal_year=data.get("fiscal_year", "FY26"),
            quarter=data.get("quarter", "Q1"),
            relative_days=int(data.get("relative_days", 1)),
            date_range_start=date.fromisoformat(raw_start) if raw_start else None,
            date_range_end=date.fromisoformat(raw_end) if raw_end else None,
        )

    @classmethod
    def for_frequency(cls, frequency: ScheduleFrequency) -> SchedulePeriod:
        """Return the recommended default period for a given schedule frequency.

        Args:
            frequency: The applicable :class:`ScheduleFrequency`.

        Returns:
            A :class:`SchedulePeriod` with sensible defaults for that frequency.
        """
        period_type, relative_days = FREQUENCY_PERIOD_DEFAULTS.get(
            frequency.value if isinstance(frequency, ScheduleFrequency) else frequency,
            (PeriodType.FISCAL_QUARTER, 0),
        )
        return cls(period_type=period_type, relative_days=relative_days)


@dataclass
class ScheduleConfig:
    """Full configuration for a recurring pipeline schedule.

    Attributes:
        schedule_id: UUID string uniquely identifying this schedule.
        name: Human-readable schedule name.
        enabled: Whether the schedule is active.
        frequency: How often the schedule runs.
        cron_expression: Cron string used when ``frequency`` is ``CUSTOM``.
        time_of_day: ``HH:MM`` string for daily/weekly/monthly triggers.
        day_of_week: Weekday index (0=Monday … 6=Sunday) for weekly schedules.
        day_of_month: Day of month (1-28) for monthly schedules.
        validation_types: Which validation scripts to run.
        pipeline_steps: Which pipeline steps to execute (in declaration order).
        testing_period: Fiscal year and quarter for output file naming.
        input_directory: Path to input data directory.
        output_directory: Path to output directory for generated CSVs.
        log_level: Python logging level string.
        created_at: When this schedule was first created.
        last_run: When this schedule last ran successfully.
        next_run: Pre-calculated next scheduled run time.
    """

    schedule_id: str
    name: str
    enabled: bool = True
    frequency: ScheduleFrequency = ScheduleFrequency.DAILY
    cron_expression: str = ""
    time_of_day: str = "09:00"
    day_of_week: int = 0
    day_of_month: int = 1
    validation_types: list[ValidationType] = field(default_factory=list)
    pipeline_steps: list[PipelineStep] = field(
        default_factory=lambda: list(PipelineStep)
    )
    schedule_period: SchedulePeriod = field(
        default_factory=SchedulePeriod
    )
    input_directory: str = ""
    output_directory: str = ""
    log_level: str = "INFO"
    created_at: datetime | None = None
    last_run: datetime | None = None
    next_run: datetime | None = None

    def to_dict(self) -> dict:
        """Serialise the schedule configuration to a JSON-compatible dictionary.

        Returns:
            Dictionary suitable for ``json.dumps`` and QSettings storage.
        """
        return {
            "schedule_id": self.schedule_id,
            "name": self.name,
            "enabled": self.enabled,
            "frequency": self.frequency.value,
            "cron_expression": self.cron_expression,
            "time_of_day": self.time_of_day,
            "day_of_week": self.day_of_week,
            "day_of_month": self.day_of_month,
            "validation_types": [vt.value for vt in self.validation_types],
            "pipeline_steps": [ps.value for ps in self.pipeline_steps],
            "schedule_period": self.schedule_period.to_dict(),
            "input_directory": self.input_directory,
            "output_directory": self.output_directory,
            "log_level": self.log_level,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ScheduleConfig:
        """Deserialise a schedule configuration from a plain dictionary.

        Args:
            data: Dictionary as produced by :meth:`to_dict`.

        Returns:
            Populated :class:`ScheduleConfig` instance.

        Raises:
            KeyError: If required fields ``schedule_id`` or ``name`` are missing.
        """
        return cls(
            schedule_id=data["schedule_id"],
            name=data["name"],
            enabled=data.get("enabled", True),
            frequency=ScheduleFrequency(data.get("frequency", "daily")),
            cron_expression=data.get("cron_expression", ""),
            time_of_day=data.get("time_of_day", "09:00"),
            day_of_week=int(data.get("day_of_week", 0)),
            day_of_month=int(data.get("day_of_month", 1)),
            validation_types=[
                ValidationType(v) for v in data.get("validation_types", [])
            ],
            pipeline_steps=[
                PipelineStep(s) for s in data.get("pipeline_steps", [])
            ],
            schedule_period=SchedulePeriod.from_dict(
                data.get(
                    "schedule_period",
                    # Backwards-compatible: migrate old "testing_period" key
                    data.get("testing_period", {}),
                )
            ),
            input_directory=data.get("input_directory", ""),
            output_directory=data.get("output_directory", ""),
            log_level=data.get("log_level", "INFO"),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else None
            ),
            last_run=(
                datetime.fromisoformat(data["last_run"])
                if data.get("last_run")
                else None
            ),
            next_run=(
                datetime.fromisoformat(data["next_run"])
                if data.get("next_run")
                else None
            ),
        )


@dataclass
class StepResult:
    """Result of a single pipeline step execution.

    Attributes:
        step: Which pipeline step this result belongs to.
        status: Final status of the step.
        started_at: When the step began.
        completed_at: When the step finished (``None`` if still running).
        output_files: Paths of files produced by this step.
        stdout: Combined standard output captured from subprocesses.
        stderr: Combined standard error captured from subprocesses.
        error_message: Human-readable error summary on failure.
    """

    step: PipelineStep
    status: RunStatus
    started_at: datetime
    completed_at: datetime | None = None
    output_files: list[str] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    error_message: str = ""

    def to_dict(self) -> dict:
        """Serialise the step result to a JSON-compatible dictionary.

        Returns:
            Dictionary suitable for ``json.dumps`` and QSettings storage.
        """
        return {
            "step": self.step.value,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "output_files": self.output_files,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict) -> StepResult:
        """Deserialise a step result from a plain dictionary.

        Args:
            data: Dictionary as produced by :meth:`to_dict`.

        Returns:
            Populated :class:`StepResult` instance.
        """
        return cls(
            step=PipelineStep(data["step"]),
            status=RunStatus(data["status"]),
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
            output_files=data.get("output_files", []),
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            error_message=data.get("error_message", ""),
        )


@dataclass
class RunRecord:
    """Complete record of a single pipeline execution.

    Attributes:
        run_id: UUID string uniquely identifying this run.
        schedule_id: ID of the parent schedule.
        schedule_name: Display name of the parent schedule (snapshot at run time).
        started_at: When the run began.
        completed_at: When the run finished (``None`` if still running).
        status: Overall run status.
        step_results: Per-step result objects in execution order.
        output_files: Aggregated list of all output files produced.
        error_message: Human-readable error summary on failure.
    """

    run_id: str
    schedule_id: str
    schedule_name: str
    started_at: datetime
    completed_at: datetime | None = None
    status: RunStatus = RunStatus.PENDING
    step_results: list[StepResult] = field(default_factory=list)
    output_files: list[str] = field(default_factory=list)
    error_message: str = ""

    def to_dict(self) -> dict:
        """Serialise the run record to a JSON-compatible dictionary.

        Returns:
            Dictionary suitable for ``json.dumps`` and QSettings storage.
        """
        return {
            "run_id": self.run_id,
            "schedule_id": self.schedule_id,
            "schedule_name": self.schedule_name,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "status": self.status.value,
            "step_results": [sr.to_dict() for sr in self.step_results],
            "output_files": self.output_files,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict) -> RunRecord:
        """Deserialise a run record from a plain dictionary.

        Args:
            data: Dictionary as produced by :meth:`to_dict`.

        Returns:
            Populated :class:`RunRecord` instance.

        Raises:
            KeyError: If required fields are missing.
        """
        return cls(
            run_id=data["run_id"],
            schedule_id=data["schedule_id"],
            schedule_name=data["schedule_name"],
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
            status=RunStatus(data.get("status", "pending")),
            step_results=[
                StepResult.from_dict(sr) for sr in data.get("step_results", [])
            ],
            output_files=data.get("output_files", []),
            error_message=data.get("error_message", ""),
        )


@dataclass
class PipelinePreset:
    """A named, pre-configured set of validation types and pipeline steps.

    .. deprecated::
        Use the API pipeline concept instead (``gui.api.pipeline``).
        Kept for backwards compatibility with existing QSettings data.

    Attributes:
        key: Machine-readable identifier for the preset.
        display_name: Human-readable name shown in the UI.
        description: Brief explanation of what the preset does.
        validation_types: Which validation scripts the preset enables.
        pipeline_steps: Which pipeline steps the preset includes.
    """

    key: str
    display_name: str
    description: str
    validation_types: list[ValidationType]
    pipeline_steps: list[PipelineStep]


# Built-in presets removed in v2.0 — use API pipelines instead.
PIPELINE_PRESETS: list[PipelinePreset] = []
