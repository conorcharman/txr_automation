"""Tests for FCA argv construction in ScriptRunnerService."""

from types import SimpleNamespace

import pytest

from api.schemas.fca import FcaCheckRequest
from api.services.script_runner import script_runner_service


def test_build_fca_argv_includes_config_with_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """FCA batch argv should include --config and carry credentials in snapshot."""
    monkeypatch.setattr(
        "api.services.script_runner.get_settings",
        lambda: SimpleNamespace(
            fca_api_email="user@example.com",
            fca_api_key="top-secret",
            data_dir="data",
        ),
    )

    req = FcaCheckRequest(
        mode="batch",
        input_file="C:/tmp/fca_input.csv",
        output_file="C:/tmp/fca_output.csv",
        permission="Accepting Deposits",
        log_level="INFO",
    )

    module_path, argv, snapshot = script_runner_service.build_fca_argv(req)

    assert module_path == "src.fca.scripts.check_firm"
    assert "--config" in argv
    assert "--input" in argv
    assert "--output" in argv
    assert snapshot["fca"]["api_email"] == "user@example.com"
    assert snapshot["fca"]["api_key"] == "top-secret"
    assert snapshot["batch"]["input_file"].replace("\\", "/").endswith("/tmp/fca_input.csv")
    assert snapshot["batch"]["output_file"].replace("\\", "/").endswith("/tmp/fca_output.csv")


def test_build_fca_argv_succeeds_when_credentials_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing credentials must NOT raise — job must be created so failure appears in Job History.

    Previously this raised HTTPException(400) before the job row was inserted, causing the job
    to silently not appear in Job History. Credential validation is now deferred to the script
    layer (fca-check calls _load_credentials and exits with a clear message that Celery captures).
    """
    monkeypatch.setattr(
        "api.services.script_runner.get_settings",
        lambda: SimpleNamespace(fca_api_email="", fca_api_key="", data_dir="data"),
    )

    req = FcaCheckRequest(mode="batch", input_file="in.csv", output_file="out.csv")

    # Must not raise — a valid (module_path, argv, snapshot) tuple is returned so that
    # the router can create the job row before dispatching to Celery.
    module_path, argv, snapshot = script_runner_service.build_fca_argv(req)

    assert module_path == "src.fca.scripts.check_firm"
    assert "--config" in argv
    assert snapshot["fca"]["api_email"] == ""
    assert snapshot["fca"]["api_key"] == ""
