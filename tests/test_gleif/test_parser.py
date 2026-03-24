"""Tests for GLEIF CSV parser (parser.py)."""

import io
import pytest
from pathlib import Path
from unittest.mock import patch

from gleif.parser import GleifCsvParser, GleifIsinMapParser, LeiRecord

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_GOLDEN_COPY_HEADER = (
    "LEI,Entity.LegalName,Entity.LegalJurisdiction,Entity.EntityStatus,"
    "Entity.LegalAddress.Country,Entity.EntityExpirationDate,"
    "Entity.EntityExpirationReason,Entity.SuccessorEntity.SuccessorLEI,"
    "Registration.RegistrationStatus,Registration.InitialRegistrationDate,"
    "Registration.LastUpdateDate,Registration.NextRenewalDate"
)

_GOLDEN_COPY_ROW_ISSUED = (
    "5493001KJTIIGC8Y1R12,Test Entity Ltd,GB,ACTIVE,GB,,"
    ",,"
    "ISSUED,2020-01-01T00:00:00Z,2025-01-01T00:00:00Z,2026-01-01T00:00:00Z"
)

_GOLDEN_COPY_ROW_LAPSED = (
    "213800WAVVOPS85N2205,Lapsed Corp,DE,INACTIVE,DE,2024-06-01T00:00:00Z,"
    "DISSOLVED,,"
    "LAPSED,2018-03-01T00:00:00Z,2024-01-01T00:00:00Z,2024-06-01T00:00:00Z"
)

_GOLDEN_COPY_CSV = "\n".join([
    _GOLDEN_COPY_HEADER,
    _GOLDEN_COPY_ROW_ISSUED,
    _GOLDEN_COPY_ROW_LAPSED,
])

_ISIN_MAP_CSV = "LEI,ISIN\n5493001KJTIIGC8Y1R12,GB00B3RBWM25\n5493001KJTIIGC8Y1R12,GB00ABC12345\n"


@pytest.fixture
def golden_copy_csv(tmp_path: Path) -> Path:
    """Write a minimal Golden Copy CSV to a temp file and return its path."""
    p = tmp_path / "golden_copy.csv"
    p.write_text(_GOLDEN_COPY_CSV, encoding="utf-8")
    return p


@pytest.fixture
def isin_map_csv(tmp_path: Path) -> Path:
    """Write a minimal ISIN mapping CSV to a temp file and return its path."""
    p = tmp_path / "isin_map.csv"
    p.write_text(_ISIN_MAP_CSV, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# GleifCsvParser tests
# ---------------------------------------------------------------------------


class TestGleifCsvParser:
    def test_parse_yields_correct_record_count(self, golden_copy_csv: Path) -> None:
        parser = GleifCsvParser()
        records = list(parser.parse(golden_copy_csv))
        assert len(records) == 2

    def test_parse_issued_record_fields(self, golden_copy_csv: Path) -> None:
        parser = GleifCsvParser()
        records = list(parser.parse(golden_copy_csv))
        issued = records[0]
        assert issued.lei == "5493001KJTIIGC8Y1R12"
        assert issued.legal_name == "Test Entity Ltd"
        assert issued.registration_status == "ISSUED"
        assert issued.entity_status == "ACTIVE"
        assert issued.legal_address_country == "GB"
        assert issued.legal_jurisdiction == "GB"
        assert issued.next_renewal_date == "2026-01-01T00:00:00Z"
        assert issued.entity_expiration_date is None

    def test_parse_lapsed_record_fields(self, golden_copy_csv: Path) -> None:
        parser = GleifCsvParser()
        records = list(parser.parse(golden_copy_csv))
        lapsed = records[1]
        assert lapsed.lei == "213800WAVVOPS85N2205"
        assert lapsed.registration_status == "LAPSED"
        assert lapsed.entity_status == "INACTIVE"
        assert lapsed.entity_expiration_date == "2024-06-01T00:00:00Z"
        assert lapsed.entity_expiration_reason == "DISSOLVED"

    def test_parse_skips_rows_without_lei(self, tmp_path: Path) -> None:
        csv_content = _GOLDEN_COPY_HEADER + "\n,Missing LEI Corp,GB,ACTIVE,GB,,,, ISSUED,2020-01-01,2025-01-01,2026-01-01\n"
        p = tmp_path / "bad.csv"
        p.write_text(csv_content, encoding="utf-8")
        records = list(GleifCsvParser().parse(p))
        assert records == []

    def test_parse_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            list(GleifCsvParser().parse(tmp_path / "nonexistent.csv"))

    def test_parse_missing_required_column_raises(self, tmp_path: Path) -> None:
        bad_csv = "LEI,Entity.LegalName\n5493001KJTIIGC8Y1R12,Some Corp\n"
        p = tmp_path / "bad.csv"
        p.write_text(bad_csv, encoding="utf-8")
        with pytest.raises(ValueError, match="missing required columns"):
            list(GleifCsvParser().parse(p))

    def test_parse_collects_other_names(self, tmp_path: Path) -> None:
        header = _GOLDEN_COPY_HEADER + ",Entity.OtherEntityNames.0.OtherEntityName.name,Entity.OtherEntityNames.1.OtherEntityName.name"
        row = _GOLDEN_COPY_ROW_ISSUED + ",Alt Name One,Alt Name Two"
        p = tmp_path / "with_other_names.csv"
        p.write_text(header + "\n" + row, encoding="utf-8")
        records = list(GleifCsvParser().parse(p))
        assert records[0].other_names == "Alt Name One; Alt Name Two"


# ---------------------------------------------------------------------------
# GleifIsinMapParser tests
# ---------------------------------------------------------------------------


class TestGleifIsinMapParser:
    def test_parse_yields_correct_pairs(self, isin_map_csv: Path) -> None:
        pairs = list(GleifIsinMapParser().parse(isin_map_csv))
        assert len(pairs) == 2
        assert ("5493001KJTIIGC8Y1R12", "GB00B3RBWM25") in pairs
        assert ("5493001KJTIIGC8Y1R12", "GB00ABC12345") in pairs

    def test_parse_skips_empty_rows(self, tmp_path: Path) -> None:
        csv_content = "LEI,ISIN\n5493001KJTIIGC8Y1R12,GB00B3RBWM25\n,\n"
        p = tmp_path / "isin.csv"
        p.write_text(csv_content, encoding="utf-8")
        pairs = list(GleifIsinMapParser().parse(p))
        assert len(pairs) == 1

    def test_parse_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            list(GleifIsinMapParser().parse(tmp_path / "nope.csv"))

    def test_parse_missing_column_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.csv"
        p.write_text("LEI,Code\n5493001KJTIIGC8Y1R12,XYZ\n", encoding="utf-8")
        with pytest.raises(ValueError, match="missing required column"):
            list(GleifIsinMapParser().parse(p))
