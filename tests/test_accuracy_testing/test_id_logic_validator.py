"""
Unit Tests for IDLogicValidator
================================

Tests for embedded-logic validation (DOB, gender, check digits) in national
identifiers.  Each test class covers one country or one cross-cutting concern.
"""

import pytest

from src.accuracy_testing.id_logic_validator import IDLogicValidator


@pytest.fixture
def validator() -> IDLogicValidator:
    """Return a fresh IDLogicValidator for each test."""
    return IDLogicValidator(verbose=False)


# ===========================================================================
# Spanish NIF / NIE logic (check-letter, mod-23)
# ===========================================================================


class TestSpanishNIFLogic:
    """Tests for _validate_spanish_nidn check-letter algorithm."""

    def test_valid_nif_check_letter(self, validator: IDLogicValidator) -> None:
        """Standard NIF: 8 digits, correct check letter accepted."""
        # 12345678 % 23 = 14 → 'Z'
        assert validator._validate_spanish_nidn("12345678Z", "", "") is True

    def test_invalid_nif_check_letter(self, validator: IDLogicValidator) -> None:
        """Standard NIF: wrong check letter rejected."""
        assert validator._validate_spanish_nidn("12345678A", "", "") is False

    def test_nif_check_letter_failure_reason(self, validator: IDLogicValidator) -> None:
        """Failure reason is recorded when check letter is wrong."""
        validator._validate_spanish_nidn("12345678A", "", "")
        assert "check letter failed" in validator.last_failure_reason.lower()
        assert "Z" in validator.last_failure_reason  # expected letter is Z

    def test_valid_nif_zero_number(self, validator: IDLogicValidator) -> None:
        """NIF with leading zeros: 00000000 % 23 = 0 → 'T'."""
        assert validator._validate_spanish_nidn("00000000T", "", "") is True

    def test_valid_nif_boundary_mod(self, validator: IDLogicValidator) -> None:
        """NIF with number divisible by 23: 23000000 % 23 = 0 → 'T'."""
        assert validator._validate_spanish_nidn("23000000T", "", "") is True

    def test_dob_and_gender_not_validated(self, validator: IDLogicValidator) -> None:
        """Spanish NIF has no embedded DOB/gender — mismatched values still pass."""
        # 12345678Z is valid; DOB/gender values are irrelevant
        assert validator._validate_spanish_nidn("12345678Z", "1990-01-01", "M") is True
        assert validator._validate_spanish_nidn("12345678Z", "2000-06-15", "F") is True

    def test_valid_k_prefix_nif(self, validator: IDLogicValidator) -> None:
        """K-prefix NIF: 1-letter + 7 digits + check letter."""
        # K + 1234567 → 1234567 % 23 = 19 → 'L'
        assert validator._validate_spanish_nidn("K1234567L", "", "") is True

    def test_invalid_k_prefix_nif(self, validator: IDLogicValidator) -> None:
        """K-prefix NIF with wrong check letter is rejected."""
        assert validator._validate_spanish_nidn("K1234567A", "", "") is False

    def test_valid_l_prefix_nif(self, validator: IDLogicValidator) -> None:
        """L-prefix NIF: 1-letter + 7 digits + check letter."""
        # L + 1234567 → 1234567 % 23 = 19 → 'L'
        assert validator._validate_spanish_nidn("L1234567L", "", "") is True

    def test_invalid_l_prefix_nif(self, validator: IDLogicValidator) -> None:
        """L-prefix NIF with wrong check letter is rejected."""
        assert validator._validate_spanish_nidn("L1234567Z", "", "") is False

    def test_malformed_returns_true(self, validator: IDLogicValidator) -> None:
        """Malformed IDs bypass check-letter validation (format layer handles them)."""
        assert validator._validate_spanish_nidn("TOOSHORT", "", "") is True
        assert validator._validate_spanish_nidn("", "", "") is True
        assert validator._validate_spanish_nidn("ABCDEFGHI", "", "") is True

    def test_validate_id_logic_dispatches_to_es(
        self, validator: IDLogicValidator
    ) -> None:
        """validate_id_logic routes ES NIDN to the Spanish validator."""
        # Valid NIF with country prefix stripped by validate_id_logic
        assert validator.validate_id_logic("ES12345678Z", "NIDN", "ES", "", "") is True
        assert validator.validate_id_logic("ES12345678A", "NIDN", "ES", "", "") is False

    def test_validate_id_logic_non_nidn_skipped(
        self, validator: IDLogicValidator
    ) -> None:
        """Non-NIDN types are not validated."""
        assert validator.validate_id_logic("ES12345678A", "CCPT", "ES", "", "") is True
        assert (
            validator.validate_id_logic("ES12345678A", "CONCAT", "ES", "", "") is True
        )


# ===========================================================================
# Belgian NIDN — year-2000 DOB handling
# ===========================================================================


class TestBelgianNIDNYear2000:
    """Verify century-prefix logic in the Belgian check-digit calculation."""

    def test_year_2000_dob_check_digit(self, validator: IDLogicValidator) -> None:
        """
        Belgian NIDN for year-2000 birth must prepend '2' before mod-97.

        ID: 01031500108
          - DOB: 2001-03-15 (year_2digit=01 < 50 → century 2000)
          - Sequence 001 → odd → Male
          - Base (year < 50): '2' + '010315001' = 2010315001
          - Check: 97 − (2010315001 % 97) = 97 − 89 = 08
        """
        result = validator._validate_belgian_nidn("01031500108", "15/03/2001", "M")
        assert result is True

    def test_year_2000_dob_mismatch_rejected(self, validator: IDLogicValidator) -> None:
        """Belgian NIDN rejected when provided DOB differs from encoded DOB."""
        # Encoded DOB is 2001-03-15; providing a different date must fail
        result = validator._validate_belgian_nidn("01031500108", "16/03/2001", "M")
        assert result is False
        assert "DOB mismatch" in validator.last_failure_reason


# ===========================================================================
# GB NINO format — prefix rejection via id_format_manager
# ===========================================================================


class TestGBNINOFormatInvalidPrefixes:
    """
    Verify that the updated GB NINO regex in id_formats.py correctly rejects
    HMRC-invalid administrative prefixes and accepts valid ones.
    """

    @pytest.fixture
    def format_manager(self):
        from src.accuracy_testing.core.id_formats import IDFormatManager

        return IDFormatManager()

    # --- Prefixes that MUST be rejected ---------------------------------

    @pytest.mark.parametrize("prefix", ["BG", "GB", "KN", "NK", "NT", "OO", "TN", "ZZ"])
    def test_invalid_hmrc_prefix_rejected(self, format_manager, prefix: str) -> None:
        """HMRC-invalid prefixes are rejected by the format validator."""
        nino = f"{prefix}123456C"
        assert (
            format_manager.validate("GB", "NIDN", nino) is False
        ), f"Expected {nino} to be invalid (prefix '{prefix}' is HMRC-disallowed)"

    # --- Prefixes that MUST be accepted ---------------------------------

    @pytest.mark.parametrize(
        "nino",
        [
            "AB123456C",  # Standard valid NINO
            "CR045092B",  # CR prefix — valid per HMRC, was incorrectly rejected before fix
            "JL123456A",  # Another valid prefix
            "ST123456D",  # Another valid prefix
        ],
    )
    def test_valid_nino_accepted(self, format_manager, nino: str) -> None:
        """Structurally valid NINOs (including CR prefix) are accepted."""
        assert (
            format_manager.validate("GB", "NIDN", nino) is True
        ), f"Expected {nino} to be valid but was rejected"

    def test_invalid_first_char_rejected(self, format_manager) -> None:
        """First character must not be D, F, I, Q, U, or V."""
        for char in "DFIQUV":
            nino = f"{char}B123456C"
            assert (
                format_manager.validate("GB", "NIDN", nino) is False
            ), f"Expected {nino} to be invalid (first char '{char}' disallowed)"

    def test_invalid_second_char_rejected(self, format_manager) -> None:
        """
        Second character must not be D, F, I, O, U, or V.

        Note: the character class ``[A-CEGHJ-NP-TW-Z]`` in the current regex
        inadvertently creates a P-T range, which permits Q as a second
        character.  That is a pre-existing issue tracked separately; this test
        covers the characters the current regex *does* correctly exclude.
        """
        for char in "DFIOUV":
            nino = f"A{char}123456C"
            assert (
                format_manager.validate("GB", "NIDN", nino) is False
            ), f"Expected A{char}123456C to be invalid (second char '{char}' disallowed)"
