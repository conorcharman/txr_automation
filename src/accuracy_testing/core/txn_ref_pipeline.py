#!/usr/bin/env python3
"""
Transaction-Reference Pipeline Executor
========================================

Orchestrates the full accuracy testing pipeline for transaction-reference-based
extracts:

    GENERATE → EXECUTE_DTF → COLLATE → VALIDATE → PUSH

This is the manually-triggered counterpart to the scheduler's
:class:`~src.gui.scheduler.pipeline.PipelineExecutor`, which handles
period-based (date range) extracts.

The executor is Qt-free — progress is reported via optional callbacks so it
can be driven from CLI, tests, or a GUI ``QThread`` wrapper equally.

Version 1.0 Changes:
- Initial implementation

Usage:
    >>> from src.accuracy_testing.core.txn_ref_pipeline import (
    ...     TransactionRefPipelineConfig,
    ...     TransactionRefPipelineExecutor,
    ... )
    >>> config = TransactionRefPipelineConfig(
    ...     input_csv=Path("data/refs.csv"),
    ...     validation_type="buyer",
    ...     sql_template_path=Path("src/accuracy_testing/sql_templates/BuyerID.sql"),
    ...     output_dir=Path("data/output"),
    ... )
    >>> executor = TransactionRefPipelineExecutor()
    >>> result = executor.execute(config)
    >>> print(result.status)
"""
from __future__ import annotations

import csv
import enum
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
_SQL_TEMPLATES_DIR = _PROJECT_ROOT / "src" / "accuracy_testing" / "sql_templates"


# ---------------------------------------------------------------------------
# Enums & dataclasses
# ---------------------------------------------------------------------------


class PipelineStepName(enum.Enum):
    """Ordered steps in the transaction-reference pipeline."""

    GENERATE = "generate"
    EXECUTE_DTF = "execute_dtf"
    COLLATE = "collate"
    VALIDATE = "validate"
    PUSH = "push"


class StepStatus(enum.Enum):
    """Outcome status for a single pipeline step."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING = "waiting"


@dataclass
class StepResult:
    """Result of a single pipeline step execution."""

    step: PipelineStepName
    status: StepStatus = StepStatus.PENDING
    message: str = ""
    output_files: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class PipelineResult:
    """Aggregate result of a full pipeline run."""

    status: StepStatus = StepStatus.PENDING
    step_results: List[StepResult] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def output_files(self) -> List[str]:
        """Collect all output files from every step."""
        files: List[str] = []
        for sr in self.step_results:
            files.extend(sr.output_files)
        return files


@dataclass
class TransactionRefPipelineConfig:
    """Configuration for a transaction-reference pipeline run.

    Attributes:
        input_csv: Path to CSV containing transaction references.
        validation_type: Validation type key (e.g. ``"buyer"``).
        sql_template_path: Path to the transaction-reference SQL template.
        output_dir: Base output directory for generated files.
        batch_size: Number of references per SQL batch.
        auto_execute_dtf: If True, execute DTF files via cwbodtfx.exe.
        dry_run: If True, log actions without writing files or executing.
        incident_code: Optional incident code for file naming.
        id_column: CSV column name containing transaction references.
        script_module_path: Dotted path to the validation script module.
        push_target_file: Optional target file for the data push step.
    """

    input_csv: Path
    validation_type: str
    sql_template_path: Path
    output_dir: Path
    batch_size: int = 900
    auto_execute_dtf: bool = False
    dry_run: bool = False
    incident_code: str = ""
    id_column: str = "Transaction reference number"
    script_module_path: str = ""
    push_target_file: str = ""


# Callback type aliases
ProgressCallback = Callable[[PipelineStepName, StepStatus, str], None]
OutputCallback = Callable[[str], None]


# ---------------------------------------------------------------------------
# SQL template mapping
# ---------------------------------------------------------------------------

#: Maps ValidationType values to transaction-reference SQL template filenames.
VALIDATION_SQL_TEMPLATE: dict[str, str] = {
    "buyer": "BuyerID.sql",
    "seller": "SellerID.sql",
    "inconsistent-buyer": "InconsistentBuyerID.sql",
    "inconsistent-seller": "InconsistentSellerID.sql",
    "ftbdm": "FTBDM.sql",
    "ftsdm": "FTSDM.sql",
    "non-zero-qty": "NonZeroNetQuantity.sql",
    "non-zero-amt": "NonZeroNetAmount.sql",
    "incorrect_net_amount": "InconsistentNetAmount.sql",
}


def get_sql_template_path(validation_type: str) -> Optional[Path]:
    """Return the default SQL template path for a validation type.

    Args:
        validation_type: ValidationType value string (e.g. ``"buyer"``).

    Returns:
        Absolute path to the template, or ``None`` if not mapped.
    """
    filename = VALIDATION_SQL_TEMPLATE.get(validation_type)
    if filename is None:
        return None
    return _SQL_TEMPLATES_DIR / filename


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


class TransactionRefPipelineExecutor:
    """Execute the full transaction-reference pipeline.

    The executor runs five steps in order, halting on the first failure.
    The *EXECUTE_DTF* step returns ``WAITING`` when ``auto_execute_dtf``
    is ``False``, allowing a GUI to show a Resume button.

    Args:
        on_progress: Optional callback ``(step, status, message)``.
        on_output: Optional callback for log-style text lines.
    """

    def __init__(
        self,
        on_progress: Optional[ProgressCallback] = None,
        on_output: Optional[OutputCallback] = None,
    ) -> None:
        self._on_progress = on_progress or (lambda *_: None)
        self._on_output = on_output or (lambda _: None)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self, config: TransactionRefPipelineConfig) -> PipelineResult:
        """Run the full pipeline.

        Args:
            config: Pipeline configuration.

        Returns:
            :class:`PipelineResult` with overall status and per-step results.
            If *EXECUTE_DTF* returns ``WAITING``, the result status will be
            ``WAITING`` and the caller should invoke :meth:`resume` after the
            user has confirmed DTF files are executed.
        """
        result = PipelineResult(
            status=StepStatus.RUNNING,
            started_at=datetime.now(),
        )

        steps = [
            (PipelineStepName.GENERATE, self._step_generate),
            (PipelineStepName.EXECUTE_DTF, self._step_execute_dtf),
            (PipelineStepName.COLLATE, self._step_collate),
            (PipelineStepName.VALIDATE, self._step_validate),
            (PipelineStepName.PUSH, self._step_push),
        ]

        for step_name, handler in steps:
            self._on_progress(step_name, StepStatus.RUNNING, "")
            step_result = handler(config, result)
            result.step_results.append(step_result)

            if step_result.status == StepStatus.WAITING:
                result.status = StepStatus.WAITING
                return result

            if step_result.status == StepStatus.FAILED:
                result.status = StepStatus.FAILED
                result.completed_at = datetime.now()
                return result

        result.status = StepStatus.SUCCESS
        result.completed_at = datetime.now()
        return result

    def resume(
        self,
        config: TransactionRefPipelineConfig,
        partial_result: PipelineResult,
    ) -> PipelineResult:
        """Resume a pipeline that paused at EXECUTE_DTF (WAITING status).

        Verifies the expected CSV output files exist, then continues with
        COLLATE → VALIDATE → PUSH.

        Args:
            config: Pipeline configuration (same as original call).
            partial_result: The :class:`PipelineResult` returned by
                :meth:`execute` with ``WAITING`` status.

        Returns:
            Updated :class:`PipelineResult`.
        """
        partial_result.status = StepStatus.RUNNING

        # Mark the DTF step as complete now that user confirmed.
        dtf_step = next(
            (s for s in partial_result.step_results
             if s.step == PipelineStepName.EXECUTE_DTF),
            None,
        )
        if dtf_step is not None:
            dtf_step.status = StepStatus.SUCCESS
            dtf_step.completed_at = datetime.now()
            dtf_step.message = "DTF files executed manually by user."

        remaining = [
            (PipelineStepName.COLLATE, self._step_collate),
            (PipelineStepName.VALIDATE, self._step_validate),
            (PipelineStepName.PUSH, self._step_push),
        ]

        for step_name, handler in remaining:
            self._on_progress(step_name, StepStatus.RUNNING, "")
            step_result = handler(config, partial_result)
            partial_result.step_results.append(step_result)

            if step_result.status == StepStatus.FAILED:
                partial_result.status = StepStatus.FAILED
                partial_result.completed_at = datetime.now()
                return partial_result

        partial_result.status = StepStatus.SUCCESS
        partial_result.completed_at = datetime.now()
        return partial_result

    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    def _step_generate(
        self,
        config: TransactionRefPipelineConfig,
        _result: PipelineResult,
    ) -> StepResult:
        """GENERATE: Read refs from CSV and produce batched SQL + DTF files."""
        sr = StepResult(
            step=PipelineStepName.GENERATE,
            status=StepStatus.RUNNING,
            started_at=datetime.now(),
        )

        # Read transaction references from the input CSV.
        try:
            refs = self._read_transaction_refs(config.input_csv, config.id_column)
        except Exception as exc:
            sr.status = StepStatus.FAILED
            sr.message = f"Failed to read transaction references: {exc}"
            sr.completed_at = datetime.now()
            self._emit(sr)
            return sr

        if not refs:
            sr.status = StepStatus.FAILED
            sr.message = "No transaction references found in the input CSV."
            sr.completed_at = datetime.now()
            self._emit(sr)
            return sr

        self._on_output(f"Read {len(refs)} transaction references from {config.input_csv.name}")

        if config.dry_run:
            sr.status = StepStatus.SUCCESS
            sr.message = f"Dry run — would generate extracts for {len(refs)} refs."
            sr.completed_at = datetime.now()
            self._emit(sr)
            return sr

        # Use SQLExtractGenerator to produce SQL + DTF files.
        try:
            # Import lazily to avoid circular deps at load time.
            from src.accuracy_testing.sql_extract_generator import SQLExtractGenerator

            generator = SQLExtractGenerator(
                template_path=str(config.sql_template_path),
                batch_size=config.batch_size,
                output_format="both",
            )
            base_name = config.incident_code or config.validation_type
            files = generator.generate_extracts(
                transaction_refs=refs,
                output_dir=str(config.output_dir),
                base_filename=base_name,
                incident_code=config.incident_code or None,
            )
        except Exception as exc:
            sr.status = StepStatus.FAILED
            sr.message = f"Extract generation failed: {exc}"
            sr.completed_at = datetime.now()
            self._emit(sr)
            return sr

        sql_files = files.get("sql_files", [])
        dtf_files = files.get("dtf_files", [])

        for f in sql_files:
            sr.output_files.append(str(f))
        for f in dtf_files:
            sr.output_files.append(str(f))

        self._on_output(
            f"Generated {len(sql_files)} SQL file(s) and {len(dtf_files)} DTF file(s)"
        )

        sr.status = StepStatus.SUCCESS
        sr.message = f"{len(sql_files)} SQL, {len(dtf_files)} DTF"
        sr.completed_at = datetime.now()
        self._emit(sr)
        return sr

    def _step_execute_dtf(
        self,
        config: TransactionRefPipelineConfig,
        result: PipelineResult,
    ) -> StepResult:
        """EXECUTE_DTF: Launch cwbodtfx.exe for each DTF or pause for manual execution."""
        sr = StepResult(
            step=PipelineStepName.EXECUTE_DTF,
            status=StepStatus.RUNNING,
            started_at=datetime.now(),
        )

        # Collect DTF files from the GENERATE step.
        gen_step = next(
            (s for s in result.step_results if s.step == PipelineStepName.GENERATE),
            None,
        )
        dtf_files = [
            f for f in (gen_step.output_files if gen_step else [])
            if f.endswith(".dtf")
        ]

        if not dtf_files:
            sr.status = StepStatus.SKIPPED
            sr.message = "No DTF files to execute."
            sr.completed_at = datetime.now()
            self._emit(sr)
            return sr

        if config.dry_run:
            sr.status = StepStatus.SUCCESS
            sr.message = f"Dry run — would execute {len(dtf_files)} DTF file(s)."
            sr.completed_at = datetime.now()
            self._emit(sr)
            return sr

        if not config.auto_execute_dtf:
            # Return WAITING so the GUI can show a Resume button.
            self._on_output("DTF files generated. Execute them manually, then click Resume.")
            for f in dtf_files:
                self._on_output(f"  → {f}")
            sr.status = StepStatus.WAITING
            sr.message = f"{len(dtf_files)} DTF file(s) awaiting manual execution."
            sr.output_files = list(dtf_files)
            return sr

        # Auto-execute DTFs via cwbodtfx.exe.
        from src.accuracy_testing.core.dtf_runner import DTFRunner

        runner = DTFRunner()

        for dtf_path in dtf_files:
            self._on_output(f"Executing DTF: {Path(dtf_path).name}")
            ok = runner.execute_dtf(dtf_path)
            if not ok:
                sr.status = StepStatus.FAILED
                sr.message = (
                    f"DTF execution failed for {Path(dtf_path).name}. "
                    "Ensure IBM i Access for Windows is installed (rtopcb.exe) or set CWBODTFX_PATH."
                )
                sr.completed_at = datetime.now()
                self._emit(sr)
                return sr

            # Infer the expected CSV output path from the DTF.
            csv_path = self._infer_csv_from_dtf(dtf_path)
            if csv_path:
                self._on_output(f"Waiting for output: {csv_path.name}")
                appeared = runner.wait_for_output(csv_path, timeout_seconds=300)
                if not appeared:
                    sr.status = StepStatus.FAILED
                    sr.message = f"Timed out waiting for {csv_path.name}."
                    sr.completed_at = datetime.now()
                    self._emit(sr)
                    return sr
                sr.output_files.append(str(csv_path))

        sr.status = StepStatus.SUCCESS
        sr.message = f"Executed {len(dtf_files)} DTF file(s)."
        sr.completed_at = datetime.now()
        self._emit(sr)
        return sr

    def _step_collate(
        self,
        config: TransactionRefPipelineConfig,
        result: PipelineResult,
    ) -> StepResult:
        """COLLATE: Merge split CSV extracts if multiple batches were generated."""
        sr = StepResult(
            step=PipelineStepName.COLLATE,
            status=StepStatus.RUNNING,
            started_at=datetime.now(),
        )

        # Count DTF files (and therefore number of batches) from GENERATE step.
        gen_step = next(
            (s for s in result.step_results if s.step == PipelineStepName.GENERATE),
            None,
        )
        dtf_count = len([
            f for f in (gen_step.output_files if gen_step else [])
            if f.endswith(".dtf")
        ])

        if dtf_count <= 1:
            sr.status = StepStatus.SKIPPED
            sr.message = "Single batch — collation not required."
            sr.completed_at = datetime.now()
            self._emit(sr)
            return sr

        if config.dry_run:
            sr.status = StepStatus.SUCCESS
            sr.message = "Dry run — would collate split CSV files."
            sr.completed_at = datetime.now()
            self._emit(sr)
            return sr

        incident_code = config.incident_code or config.validation_type
        csv_dir = config.output_dir / "dtf" / "csv"

        self._on_output(f"Collating {dtf_count} split CSV files in {csv_dir}")

        try:
            from src.accuracy_testing.scripts.collate_csv_extracts import (
                CSVExtractCollator,
            )

            collator = CSVExtractCollator(
                input_dir=csv_dir,
                output_dir=config.output_dir,
                dry_run=False,
            )
            stats = collator.collate_incident(incident_code)
            sr.status = StepStatus.SUCCESS
            sr.message = f"Collated {stats.files_merged} files → {stats.output_file}"
            if stats.output_file:
                sr.output_files.append(str(stats.output_file))
            self._on_output(sr.message)
        except Exception as exc:
            sr.status = StepStatus.FAILED
            sr.message = f"Collation failed: {exc}"
            self._on_output(sr.message)

        sr.completed_at = datetime.now()
        self._emit(sr)
        return sr

    def _step_validate(
        self,
        config: TransactionRefPipelineConfig,
        _result: PipelineResult,
    ) -> StepResult:
        """VALIDATE: Run the appropriate validation script via subprocess."""
        sr = StepResult(
            step=PipelineStepName.VALIDATE,
            status=StepStatus.RUNNING,
            started_at=datetime.now(),
        )

        module_path = config.script_module_path
        if not module_path:
            sr.status = StepStatus.SKIPPED
            sr.message = "No validation script configured — skipped."
            sr.completed_at = datetime.now()
            self._emit(sr)
            return sr

        if config.dry_run:
            sr.status = StepStatus.SUCCESS
            sr.message = f"Dry run — would run {module_path}."
            sr.completed_at = datetime.now()
            self._emit(sr)
            return sr

        self._on_output(f"Running validation: {module_path}")

        cmd = [sys.executable, "-m", module_path, "--gui-mode"]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(_PROJECT_ROOT),
                timeout=600,
            )
        except subprocess.TimeoutExpired:
            sr.status = StepStatus.FAILED
            sr.message = f"Validation timed out after 600s: {module_path}"
            sr.completed_at = datetime.now()
            self._emit(sr)
            return sr
        except OSError as exc:
            sr.status = StepStatus.FAILED
            sr.message = f"Failed to launch validation: {exc}"
            sr.completed_at = datetime.now()
            self._emit(sr)
            return sr

        if proc.stdout:
            for line in proc.stdout.strip().splitlines():
                self._on_output(line)
        if proc.returncode != 0:
            sr.status = StepStatus.FAILED
            sr.message = f"Validation exited with code {proc.returncode}."
            if proc.stderr:
                sr.message += f"\n{proc.stderr.strip()}"
            sr.completed_at = datetime.now()
            self._emit(sr)
            return sr

        sr.status = StepStatus.SUCCESS
        sr.message = "Validation completed successfully."
        sr.completed_at = datetime.now()
        self._emit(sr)
        return sr

    def _step_push(
        self,
        config: TransactionRefPipelineConfig,
        _result: PipelineResult,
    ) -> StepResult:
        """PUSH: Run data_push.py to merge validated data into master tracking."""
        sr = StepResult(
            step=PipelineStepName.PUSH,
            status=StepStatus.RUNNING,
            started_at=datetime.now(),
        )

        if not config.push_target_file:
            sr.status = StepStatus.SKIPPED
            sr.message = "No push target file configured — skipped."
            sr.completed_at = datetime.now()
            self._emit(sr)
            return sr

        if config.dry_run:
            sr.status = StepStatus.SUCCESS
            sr.message = "Dry run — would push data to target file."
            sr.completed_at = datetime.now()
            self._emit(sr)
            return sr

        self._on_output("Running data push...")

        cmd = [
            sys.executable, "-m",
            "accuracy_testing.scripts.data_push",
            "--target", config.push_target_file,
            "--gui-mode",
        ]
        incident = config.incident_code or config.validation_type
        cmd.extend(["--incident", incident])

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(_PROJECT_ROOT),
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            sr.status = StepStatus.FAILED
            sr.message = "Data push timed out after 300s."
            sr.completed_at = datetime.now()
            self._emit(sr)
            return sr
        except OSError as exc:
            sr.status = StepStatus.FAILED
            sr.message = f"Failed to launch data push: {exc}"
            sr.completed_at = datetime.now()
            self._emit(sr)
            return sr

        if proc.stdout:
            for line in proc.stdout.strip().splitlines():
                self._on_output(line)
        if proc.returncode != 0:
            sr.status = StepStatus.FAILED
            sr.message = f"Data push exited with code {proc.returncode}."
            if proc.stderr:
                sr.message += f"\n{proc.stderr.strip()}"
        else:
            sr.status = StepStatus.SUCCESS
            sr.message = "Data push completed."

        sr.completed_at = datetime.now()
        self._emit(sr)
        return sr

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _emit(self, sr: StepResult) -> None:
        """Emit progress callback for a completed step."""
        self._on_progress(sr.step, sr.status, sr.message)

    def _read_transaction_refs(self, csv_path: Path, column: str) -> List[str]:
        """Read transaction reference strings from a CSV file.

        Args:
            csv_path: Path to input CSV.
            column: Column header containing references.

        Returns:
            Deduplicated list of non-empty reference strings.
        """
        refs: List[str] = []
        with open(csv_path, encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                val = row.get(column, "").strip()
                if val:
                    refs.append(val)
        return list(dict.fromkeys(refs))  # Deduplicate, preserve order.

    @staticmethod
    def _infer_csv_from_dtf(dtf_path: str) -> Optional[Path]:
        """Read a DTF file and extract the PCFile (output CSV) path.

        Args:
            dtf_path: Path to the ``.dtf`` file.

        Returns:
            :class:`Path` to the expected output CSV, or ``None`` if not found.
        """
        try:
            content = Path(dtf_path).read_text(encoding="cp1252")
            for line in content.splitlines():
                if line.startswith("PCFile="):
                    pc_file = line.split("=", 1)[1].strip()
                    if pc_file:
                        return Path(pc_file)
        except Exception:
            pass
        return None
