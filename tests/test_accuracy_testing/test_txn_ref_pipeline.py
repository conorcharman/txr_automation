"""
Tests for TransactionRefPipelineExecutor — the manually-triggered
accuracy testing pipeline orchestrator.

All external dependencies (SQLExtractGenerator, DTFRunner, subprocess)
are mocked so no files are written or processes launched.
"""
from __future__ import annotations

import csv
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.accuracy_testing.core.txn_ref_pipeline import (
    PipelineStepName,
    StepStatus,
    TransactionRefPipelineConfig,
    TransactionRefPipelineExecutor,
    get_sql_template_path,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def refs_csv(tmp_path: Path) -> Path:
    """Create a minimal transaction-references CSV."""
    csv_path = tmp_path / "refs.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Transaction reference number"])
        writer.writerow(["44625CMGKHP1"])
        writer.writerow(["44625CMGKHP2"])
        writer.writerow(["44625CMGKHP3"])
    return csv_path


@pytest.fixture()
def config(refs_csv: Path, tmp_path: Path) -> TransactionRefPipelineConfig:
    """Return a minimal pipeline config."""
    return TransactionRefPipelineConfig(
        input_csv=refs_csv,
        validation_type="buyer",
        sql_template_path=Path("src/accuracy_testing/sql_templates/BuyerID.sql"),
        output_dir=tmp_path / "output",
        batch_size=900,
        auto_execute_dtf=False,
        dry_run=False,
        script_module_path="accuracy_testing.scripts.buyer_id_validation",
    )


_GENERATOR_CLS = "src.accuracy_testing.sql_extract_generator.SQLExtractGenerator"
_DTF_EXECUTE = "src.accuracy_testing.core.dtf_runner.DTFRunner.execute_dtf"
_DTF_WAIT = "src.accuracy_testing.core.dtf_runner.DTFRunner.wait_for_output"
_SUBPROCESS_RUN = "src.accuracy_testing.core.txn_ref_pipeline.subprocess.run"


def _mock_generate_extracts(**kwargs):
    """Return a mock SQLExtractGenerator whose generate_extracts returns files."""
    mock_gen = MagicMock()
    mock_gen.generate_extracts.return_value = {
        "sql_files": [Path("out/sql/buyer.sql")],
        "dtf_files": [Path("out/dtf/buyer.dtf")],
    }
    mock_cls = MagicMock(return_value=mock_gen)
    return mock_cls


# ---------------------------------------------------------------------------
# Tests: template mapping
# ---------------------------------------------------------------------------

class TestGetSqlTemplatePath:
    def test_buyer_returns_path(self) -> None:
        p = get_sql_template_path("buyer")
        assert p is not None
        assert p.name == "BuyerID.sql"

    def test_seller_returns_path(self) -> None:
        p = get_sql_template_path("seller")
        assert p is not None
        assert p.name == "SellerID.sql"

    def test_unknown_returns_none(self) -> None:
        assert get_sql_template_path("unknown_type") is None

    def test_all_nine_types_mapped(self) -> None:
        from src.accuracy_testing.core.txn_ref_pipeline import VALIDATION_SQL_TEMPLATE

        assert len(VALIDATION_SQL_TEMPLATE) == 9


# ---------------------------------------------------------------------------
# Tests: GENERATE step
# ---------------------------------------------------------------------------

class TestGenerateStep:
    def test_generate_reads_refs_and_produces_files(
        self, config: TransactionRefPipelineConfig
    ) -> None:
        with patch(_GENERATOR_CLS, _mock_generate_extracts()):
            executor = TransactionRefPipelineExecutor()
            result = executor.execute(config)

        gen_step = result.step_results[0]
        assert gen_step.step == PipelineStepName.GENERATE
        assert gen_step.status == StepStatus.SUCCESS
        assert len(gen_step.output_files) >= 1

    def test_generate_empty_csv_fails(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "empty.csv"
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow(["Transaction reference number"])

        cfg = TransactionRefPipelineConfig(
            input_csv=csv_path,
            validation_type="buyer",
            sql_template_path=Path("x.sql"),
            output_dir=tmp_path,
        )
        executor = TransactionRefPipelineExecutor()
        result = executor.execute(cfg)
        assert result.status == StepStatus.FAILED
        assert result.step_results[0].step == PipelineStepName.GENERATE

    def test_dry_run_skips_generation(
        self, config: TransactionRefPipelineConfig
    ) -> None:
        config.dry_run = True
        executor = TransactionRefPipelineExecutor()
        result = executor.execute(config)
        # All steps should succeed (dry run).
        assert result.status == StepStatus.SUCCESS
        gen_step = result.step_results[0]
        assert gen_step.status == StepStatus.SUCCESS
        assert "Dry run" in gen_step.message


# ---------------------------------------------------------------------------
# Tests: EXECUTE_DTF step
# ---------------------------------------------------------------------------

class TestExecuteDtfStep:
    def test_manual_mode_returns_waiting(
        self, config: TransactionRefPipelineConfig
    ) -> None:
        """With auto_execute_dtf=False, pipeline should pause (WAITING)."""
        config.auto_execute_dtf = False
        with patch(_GENERATOR_CLS, _mock_generate_extracts()):
            executor = TransactionRefPipelineExecutor()
            result = executor.execute(config)

        assert result.status == StepStatus.WAITING
        dtf_step = result.step_results[1]
        assert dtf_step.step == PipelineStepName.EXECUTE_DTF
        assert dtf_step.status == StepStatus.WAITING

    def test_auto_mode_success(
        self, config: TransactionRefPipelineConfig
    ) -> None:
        config.auto_execute_dtf = True
        with patch(_GENERATOR_CLS, _mock_generate_extracts()), \
             patch(_DTF_EXECUTE, return_value=True), \
             patch(_DTF_WAIT, return_value=True), \
             patch(
                 "src.accuracy_testing.core.txn_ref_pipeline."
                 "TransactionRefPipelineExecutor._infer_csv_from_dtf",
                 return_value=Path("out/dtf/csv/buyer.csv"),
             ), \
             patch(_SUBPROCESS_RUN, return_value=MagicMock(returncode=0, stdout="", stderr="")):
            executor = TransactionRefPipelineExecutor()
            result = executor.execute(config)

        dtf_step = result.step_results[1]
        assert dtf_step.status == StepStatus.SUCCESS

    def test_auto_mode_failure_halts(
        self, config: TransactionRefPipelineConfig
    ) -> None:
        config.auto_execute_dtf = True
        with patch(_GENERATOR_CLS, _mock_generate_extracts()), \
             patch(_DTF_EXECUTE, return_value=False):
            executor = TransactionRefPipelineExecutor()
            result = executor.execute(config)

        assert result.status == StepStatus.FAILED
        dtf_step = result.step_results[1]
        assert dtf_step.status == StepStatus.FAILED


# ---------------------------------------------------------------------------
# Tests: COLLATE step
# ---------------------------------------------------------------------------

class TestCollateStep:
    def test_single_batch_skips_collation(
        self, config: TransactionRefPipelineConfig
    ) -> None:
        config.auto_execute_dtf = True
        with patch(_GENERATOR_CLS, _mock_generate_extracts()), \
             patch(_DTF_EXECUTE, return_value=True), \
             patch(_DTF_WAIT, return_value=True), \
             patch(
                 "src.accuracy_testing.core.txn_ref_pipeline."
                 "TransactionRefPipelineExecutor._infer_csv_from_dtf",
                 return_value=Path("out/dtf/csv/buyer.csv"),
             ), \
             patch(_SUBPROCESS_RUN, return_value=MagicMock(returncode=0, stdout="", stderr="")):
            executor = TransactionRefPipelineExecutor()
            result = executor.execute(config)

        collate_step = next(
            s for s in result.step_results if s.step == PipelineStepName.COLLATE
        )
        assert collate_step.status == StepStatus.SKIPPED


# ---------------------------------------------------------------------------
# Tests: VALIDATE step
# ---------------------------------------------------------------------------

class TestValidateStep:
    def test_validate_runs_subprocess(
        self, config: TransactionRefPipelineConfig
    ) -> None:
        config.auto_execute_dtf = True
        mock_proc = MagicMock(returncode=0, stdout="OK\n", stderr="")
        with patch(_GENERATOR_CLS, _mock_generate_extracts()), \
             patch(_DTF_EXECUTE, return_value=True), \
             patch(_DTF_WAIT, return_value=True), \
             patch(
                 "src.accuracy_testing.core.txn_ref_pipeline."
                 "TransactionRefPipelineExecutor._infer_csv_from_dtf",
                 return_value=Path("out/dtf/csv/buyer.csv"),
             ), \
             patch(_SUBPROCESS_RUN, return_value=mock_proc) as mock_run:
            executor = TransactionRefPipelineExecutor()
            result = executor.execute(config)

        validate_step = next(
            s for s in result.step_results if s.step == PipelineStepName.VALIDATE
        )
        assert validate_step.status == StepStatus.SUCCESS
        # Verify subprocess was called with the validation module.
        assert mock_run.called

    def test_validate_skipped_when_no_module(
        self, config: TransactionRefPipelineConfig
    ) -> None:
        config.auto_execute_dtf = True
        config.script_module_path = ""
        with patch(_GENERATOR_CLS, _mock_generate_extracts()), \
             patch(_DTF_EXECUTE, return_value=True), \
             patch(_DTF_WAIT, return_value=True), \
             patch(
                 "src.accuracy_testing.core.txn_ref_pipeline."
                 "TransactionRefPipelineExecutor._infer_csv_from_dtf",
                 return_value=Path("out/dtf/csv/buyer.csv"),
             ), \
             patch(_SUBPROCESS_RUN, return_value=MagicMock(returncode=0, stdout="", stderr="")):
            executor = TransactionRefPipelineExecutor()
            result = executor.execute(config)

        validate_step = next(
            s for s in result.step_results if s.step == PipelineStepName.VALIDATE
        )
        assert validate_step.status == StepStatus.SKIPPED


# ---------------------------------------------------------------------------
# Tests: PUSH step
# ---------------------------------------------------------------------------

class TestPushStep:
    def test_push_skipped_when_no_target(
        self, config: TransactionRefPipelineConfig
    ) -> None:
        config.auto_execute_dtf = True
        config.push_target_file = ""
        with patch(_GENERATOR_CLS, _mock_generate_extracts()), \
             patch(_DTF_EXECUTE, return_value=True), \
             patch(_DTF_WAIT, return_value=True), \
             patch(
                 "src.accuracy_testing.core.txn_ref_pipeline."
                 "TransactionRefPipelineExecutor._infer_csv_from_dtf",
                 return_value=Path("out/dtf/csv/buyer.csv"),
             ), \
             patch(_SUBPROCESS_RUN, return_value=MagicMock(returncode=0, stdout="", stderr="")):
            executor = TransactionRefPipelineExecutor()
            result = executor.execute(config)

        push_step = next(
            s for s in result.step_results if s.step == PipelineStepName.PUSH
        )
        assert push_step.status == StepStatus.SKIPPED


# ---------------------------------------------------------------------------
# Tests: resume
# ---------------------------------------------------------------------------

class TestResume:
    def test_resume_continues_from_waiting(
        self, config: TransactionRefPipelineConfig
    ) -> None:
        config.auto_execute_dtf = False
        with patch(_GENERATOR_CLS, _mock_generate_extracts()):
            executor = TransactionRefPipelineExecutor()
            partial = executor.execute(config)

        assert partial.status == StepStatus.WAITING

        mock_proc = MagicMock(returncode=0, stdout="", stderr="")
        with patch(_SUBPROCESS_RUN, return_value=mock_proc):
            result = executor.resume(config, partial)

        assert result.status == StepStatus.SUCCESS
        # Should have COLLATE + VALIDATE + PUSH added (plus original GENERATE + EXECUTE_DTF).
        step_names = [s.step for s in result.step_results]
        assert PipelineStepName.COLLATE in step_names
        assert PipelineStepName.VALIDATE in step_names
        assert PipelineStepName.PUSH in step_names


# ---------------------------------------------------------------------------
# Tests: callbacks
# ---------------------------------------------------------------------------

class TestCallbacks:
    def test_on_progress_called(
        self, config: TransactionRefPipelineConfig
    ) -> None:
        calls: list[tuple] = []

        def recorder(step, status, msg):
            calls.append((step, status, msg))

        with patch(_GENERATOR_CLS, _mock_generate_extracts()):
            executor = TransactionRefPipelineExecutor(on_progress=recorder)
            executor.execute(config)

        # At minimum: GENERATE running + GENERATE done + EXECUTE_DTF running
        step_names = [c[0] for c in calls]
        assert PipelineStepName.GENERATE in step_names

    def test_on_output_called(
        self, config: TransactionRefPipelineConfig
    ) -> None:
        lines: list[str] = []

        with patch(_GENERATOR_CLS, _mock_generate_extracts()):
            executor = TransactionRefPipelineExecutor(on_output=lines.append)
            executor.execute(config)

        assert any("transaction references" in l.lower() for l in lines)
