"""Regression tests for Kaizen validation hardening in IDValidationProcessor."""

from __future__ import annotations

from src.accuracy_testing.processor import ClientRecord, IDValidationProcessor


def _record(**overrides) -> ClientRecord:
    base = dict(
        row_index=1,
        transaction_ref="TXN001",
        account_id="ACC1",
        person_code="P1",
        account_type="IND",
        id_value="GB1234567890",
        id_type="NIDN",
        first_name="John",
        surname="Smith",
        date_of_birth="1990-01-01",
        gender="M",
        primary_nationality="GB",
        secondary_nationality="",
        original_row=[],
    )
    base.update(overrides)
    return ClientRecord(**base)


def test_template_lookup_normalizes_transaction_reference() -> None:
    processor = IDValidationProcessor(client_type="buyer", verbose=False)
    processor.template_data = {
        "TXN001": {"id": "GBCORRECT", "type": "NIDN"},
    }

    record = _record(
        transaction_ref=" txn001 ",
        correction_output="GBCORRECT:NIDN",
        correction_fields="ID:IDT",
    )

    processor._perform_template_validation(record)

    assert record.kaizen_error == "GBCORRECT:NIDN"
    assert record.match == "TRUE"
    assert record.error == "N"


def test_template_value_sentinels_are_treated_as_blank() -> None:
    processor = IDValidationProcessor(client_type="buyer", verbose=False)
    processor.template_data = {
        "TXN001": {"id": "N/A", "type": "NIDN"},
    }

    record = _record(correction_output=":NIDN", correction_fields="ID:IDT")

    processor._perform_template_validation(record)

    assert record.kaizen_error == ":NIDN"
    assert record.match == "TRUE"
    assert record.error == "N"


def test_process_batch_exception_sets_non_blank_error() -> None:
    processor = IDValidationProcessor(client_type="buyer", verbose=False)

    def _boom(_record: ClientRecord) -> ClientRecord:
        raise RuntimeError("forced failure")

    processor.process_record = _boom  # type: ignore[method-assign]

    out = processor.process_batch([_record()])

    assert len(out) == 1
    assert out[0].error == "Y"
    assert out[0].validation_error.startswith("Processing error:")
