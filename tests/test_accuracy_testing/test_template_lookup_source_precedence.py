"""
Tests for template lookup source precedence.

These tests verify Kaizen lookup reads from the consolidated-data section
(after INCIDENT_CODE) when pre-INCIDENT validation ID/type columns are blank.
"""

import csv
from pathlib import Path

from src.accuracy_testing.processor import ClientRecord, IDValidationProcessor


def _write_template(path: Path, header: list[str], rows: list[list[str]]) -> None:
    """Write a minimal template CSV for lookup tests."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def _build_record(transaction_ref: str, correction_output: str) -> ClientRecord:
    """Create a minimal client record suitable for template validation."""
    return ClientRecord(
        row_index=2,
        transaction_ref=transaction_ref,
        account_id="ACC001",
        person_code="P001",
        account_type="IND",
        id_value="",
        id_type="",
        first_name="",
        surname="",
        date_of_birth="",
        gender="",
        primary_nationality="",
        secondary_nationality="",
        correction_output=correction_output,
    )


def test_seller_lookup_falls_back_to_consolidated_columns(tmp_path: Path) -> None:
    """Use consolidated seller columns when left-side seller columns are blank."""
    template_path = tmp_path / "seller_template.csv"
    header = [
        "Transaction Reference",
        "Seller ID Code",
        "Type of Seller ID Code",
        "INCIDENT_CODE",
        "Seller identification code",
        "Type of seller identification code",
    ]
    rows = [["TXN001", "", "", "16_21", "GBAA123456A", "NIDN"]]
    _write_template(template_path, header, rows)

    processor = IDValidationProcessor(client_type="seller", template_path=str(template_path))
    record = _build_record("TXN001", "GBAA123456A:NIDN")

    processor._perform_template_validation(record)

    assert record.kaizen_error == "GBAA123456A:NIDN"
    assert record.match == "TRUE"
    assert record.error == "N"


def test_buyer_lookup_falls_back_to_consolidated_columns(tmp_path: Path) -> None:
    """Use consolidated buyer columns when left-side buyer columns are blank."""
    template_path = tmp_path / "buyer_template.csv"
    header = [
        "Transaction Reference",
        "Buyer ID Code",
        "Type of Buyer ID Code",
        "INCIDENT_CODE",
        "Buyer identification code",
        "Type of buyer identification code",
    ]
    rows = [["TXN002", "", "", "7_66", "FRZZ987654B", "CCPT"]]
    _write_template(template_path, header, rows)

    processor = IDValidationProcessor(client_type="buyer", template_path=str(template_path))
    record = _build_record("TXN002", "FRZZ987654B:CCPT")

    processor._perform_template_validation(record)

    assert record.kaizen_error == "FRZZ987654B:CCPT"
    assert record.match == "TRUE"
    assert record.error == "N"


def test_primary_columns_override_fallback_when_populated(tmp_path: Path) -> None:
    """Prefer pre-INCIDENT ID/type values when they are present."""
    template_path = tmp_path / "seller_primary_wins.csv"
    header = [
        "Transaction Reference",
        "Seller ID Code",
        "Type of Seller ID Code",
        "INCIDENT_CODE",
        "Seller identification code",
        "Type of seller identification code",
    ]
    rows = [[
        "TXN003",
        "GBPRIMARY999A",
        "NIDN",
        "16_21",
        "GBFALLBACK111A",
        "CCPT",
    ]]
    _write_template(template_path, header, rows)

    processor = IDValidationProcessor(client_type="seller", template_path=str(template_path))
    record = _build_record("TXN003", "GBPRIMARY999A:NIDN")

    processor._perform_template_validation(record)

    assert record.kaizen_error == "GBPRIMARY999A:NIDN"
    assert record.match == "TRUE"
    assert record.error == "N"


def test_legacy_columns_still_work_without_consolidated_section(tmp_path: Path) -> None:
    """Keep legacy behaviour when consolidated columns are absent."""
    template_path = tmp_path / "legacy_template.csv"
    header = [
        "Transaction Reference",
        "Seller ID Code",
        "Type of Seller ID Code",
    ]
    rows = [["TXN004", "GBLEGACY222A", "NIDN"]]
    _write_template(template_path, header, rows)

    processor = IDValidationProcessor(client_type="seller", template_path=str(template_path))
    record = _build_record("TXN004", "GBLEGACY222A:NIDN")

    processor._perform_template_validation(record)

    assert record.kaizen_error == "GBLEGACY222A:NIDN"
    assert record.match == "TRUE"
    assert record.error == "N"


def test_correction_field_id_uses_id_only_for_comparison(tmp_path: Path) -> None:
    """When Correction Field is ID, compare correction ID to template ID."""
    template_path = tmp_path / "id_only_template.csv"
    header = [
        "Transaction Reference",
        "Seller ID Code",
        "Type of Seller ID Code",
    ]
    rows = [["TXN005", "GBIDONLY123A", "NIDN"]]
    _write_template(template_path, header, rows)

    processor = IDValidationProcessor(client_type="seller", template_path=str(template_path))
    record = _build_record("TXN005", "GBIDONLY123A:CCPT")
    record.correction_fields = "ID"

    processor._perform_template_validation(record)

    assert record.kaizen_error == "GBIDONLY123A"
    assert record.match == "TRUE"
    assert record.error == "N"


def test_correction_field_idt_uses_type_only_for_comparison(tmp_path: Path) -> None:
    """When Correction Field is IDT, compare correction type to template type."""
    template_path = tmp_path / "type_only_template.csv"
    header = [
        "Transaction Reference",
        "Buyer ID Code",
        "Type of Buyer ID Code",
    ]
    rows = [["TXN006", "GBTYPEONLY321B", "CCPT"]]
    _write_template(template_path, header, rows)

    processor = IDValidationProcessor(client_type="buyer", template_path=str(template_path))
    record = _build_record("TXN006", "DIFFERENTID:CCPT")
    record.correction_fields = "IDT"

    processor._perform_template_validation(record)

    assert record.kaizen_error == "CCPT"
    assert record.match == "TRUE"
    assert record.error == "N"
