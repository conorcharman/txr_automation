#!/usr/bin/env python3
"""
Test CONCAT Generation
=======================

Tests for CONCAT ID generation with focus on multi-part surname handling.

Version 1.0 Changes:
- Initial test suite for surname handling in CONCAT generation
- Tests for multi-part surnames (hyphenated, spaces)
- Tests for surname prefixes
- Tests for edge cases

Usage:
    pytest tests/test_accuracy_testing/test_concat_generation.py -v
"""

from datetime import datetime

import pytest

from src.accuracy_testing.processor import ClientRecord, IDValidationProcessor


class TestConcatSurnameHandling:
    """Test suite for surname handling in CONCAT generation"""

    @pytest.fixture
    def processor(self):
        """Create a test processor instance"""
        processor = IDValidationProcessor(
            client_type="buyer", logger=None, verbose=True
        )
        return processor

    def test_multi_part_surname_with_hyphen(self, processor):
        """Test that multi-part surnames with hyphens include ALL parts"""
        # Test case: ROIG-MEYN should become ROIGMEYN -> ROIGM (not ROIG#)
        result = processor._clean_name_for_concat("ROIG-MEYN", is_surname=True)
        assert result == "ROIGM", f"Expected 'ROIGM' for 'ROIG-MEYN', got '{result}'"

    def test_multi_part_surname_with_space(self, processor):
        """Test that multi-part surnames with spaces include ALL parts"""
        # Test case: GARCIA LOPEZ should become GARCIALOPEZ -> GARCI
        result = processor._clean_name_for_concat("GARCIA LOPEZ", is_surname=True)
        assert result == "GARCI", f"Expected 'GARCI' for 'GARCIA LOPEZ', got '{result}'"

    def test_multi_part_surname_with_apostrophe(self, processor):
        """Test that surnames with apostrophes include ALL parts"""
        # Test case: O'BRIEN should become OBRIEN -> OBRIE
        result = processor._clean_name_for_concat("O'BRIEN", is_surname=True)
        assert result == "OBRIE", f"Expected 'OBRIE' for \"O'BRIEN\", got '{result}'"

    def test_multi_part_surname_with_multiple_hyphens(self, processor):
        """Test surnames with multiple hyphens"""
        # Test case: SMITH-JONES-BROWN should become SMITHJONESBROWN -> SMITH
        result = processor._clean_name_for_concat("SMITH-JONES-BROWN", is_surname=True)
        assert (
            result == "SMITH"
        ), f"Expected 'SMITH' for 'SMITH-JONES-BROWN', got '{result}'"

    def test_surname_with_prefix_von(self, processor):
        """Test that VON prefix is removed but rest of surname kept"""
        # Test case: VON SMITH -> SMITH -> SMITH
        result = processor._clean_name_for_concat("VON SMITH", is_surname=True)
        assert result == "SMITH", f"Expected 'SMITH' for 'VON SMITH', got '{result}'"

    def test_surname_with_prefix_van_der(self, processor):
        """Test that compound prefix VAN DER is removed"""
        # Test case: VAN DER BERG -> BERG -> BERG#
        result = processor._clean_name_for_concat("VAN DER BERG", is_surname=True)
        assert result == "BERG#", f"Expected 'BERG#' for 'VAN DER BERG', got '{result}'"

    def test_surname_with_prefix_de_and_hyphen(self, processor):
        """Test prefix removal with multi-part surname"""
        # Test case: DE ROIG-MEYN -> ROIG-MEYN -> ROIGMEYN -> ROIGM
        result = processor._clean_name_for_concat("DE ROIG-MEYN", is_surname=True)
        assert result == "ROIGM", f"Expected 'ROIGM' for 'DE ROIG-MEYN', got '{result}'"

    def test_surname_with_prefix_mc(self, processor):
        """Test that MC prefix is removed"""
        # Test case: MC DONALD -> DONALD -> DONAL
        result = processor._clean_name_for_concat("MC DONALD", is_surname=True)
        assert result == "DONAL", f"Expected 'DONAL' for 'MC DONALD', got '{result}'"

    def test_first_name_single_word(self, processor):
        """Test first name with single word"""
        # Test case: ROGER -> ROGER
        result = processor._clean_name_for_concat("ROGER", is_surname=False)
        assert result == "ROGER", f"Expected 'ROGER' for 'ROGER', got '{result}'"

    def test_first_name_multiple_words(self, processor):
        """Test that first name takes ONLY first word"""
        # Test case: JEAN PAUL -> JEAN -> JEAN#
        result = processor._clean_name_for_concat("JEAN PAUL", is_surname=False)
        assert result == "JEAN#", f"Expected 'JEAN#' for 'JEAN PAUL', got '{result}'"

    def test_first_name_with_hyphen(self, processor):
        """Test that first name with hyphen keeps both parts (hyphen removed)"""
        # Test case: JEAN-PAUL -> JEANPAUL -> JEANP
        result = processor._clean_name_for_concat("JEAN-PAUL", is_surname=False)
        assert result == "JEANP", f"Expected 'JEANP' for 'JEAN-PAUL', got '{result}'"

    def test_short_surname(self, processor):
        """Test short surname gets padded with #"""
        # Test case: LEE -> LEE##
        result = processor._clean_name_for_concat("LEE", is_surname=True)
        assert result == "LEE##", f"Expected 'LEE##' for 'LEE', got '{result}'"

    def test_long_surname(self, processor):
        """Test long surname gets truncated to 5 chars"""
        # Test case: WILLIAMSON -> WILLI
        result = processor._clean_name_for_concat("WILLIAMSON", is_surname=True)
        assert result == "WILLI", f"Expected 'WILLI' for 'WILLIAMSON', got '{result}'"

    def test_surname_with_comma_suffix(self, processor):
        """Comma followed by a suffix (non-prefix word) keeps both parts joined"""
        # SMITH, JR → parts ["SMITH","JR"] → no prefix words filtered → "SMITHJR" → "SMITH"
        result = processor._clean_name_for_concat("SMITH, JR", is_surname=True)
        assert result == "SMITH", f"Expected 'SMITH' for 'SMITH, JR', got '{result}'"

    def test_surname_with_comma_embedded_prefix(self, processor):
        """Comma-separated surname with embedded prefix word keeps non-prefix parts"""
        # MAHN,DE,AZETU → parts ["MAHN","DE","AZETU"] → "DE" filtered → "MAHNAZETU" → "MAHNA"
        result = processor._clean_name_for_concat("MAHN,DE,AZETU", is_surname=True)
        assert (
            result == "MAHNA"
        ), f"Expected 'MAHNA' for 'MAHN,DE,AZETU', got '{result}'"

    def test_empty_name(self, processor):
        """Test empty name returns all hashes"""
        result = processor._clean_name_for_concat("", is_surname=True)
        assert result == "#####", f"Expected '#####' for empty string, got '{result}'"

    def test_whitespace_only_name(self, processor):
        """Test whitespace-only name returns all hashes"""
        result = processor._clean_name_for_concat("   ", is_surname=True)
        assert result == "#####", f"Expected '#####' for whitespace, got '{result}'"


class TestConcatPrefixRemoval:
    """Test suite for surname prefix removal"""

    @pytest.fixture
    def processor(self):
        """Create a test processor instance"""
        processor = IDValidationProcessor(
            client_type="buyer", logger=None, verbose=True
        )
        return processor

    def test_prefix_von_der(self, processor):
        """Test VON DER prefix removal"""
        result = processor._remove_name_prefixes("VON DER SMITH")
        assert result == "SMITH", f"Expected 'SMITH', got '{result}'"

    def test_prefix_van_der(self, processor):
        """Test VAN DER prefix removal"""
        result = processor._remove_name_prefixes("VAN DER BERG")
        assert result == "BERG", f"Expected 'BERG', got '{result}'"

    def test_prefix_van_de(self, processor):
        """Test VAN DE prefix removal"""
        result = processor._remove_name_prefixes("VAN DE VELDE")
        assert result == "VELDE", f"Expected 'VELDE', got '{result}'"

    def test_prefix_de_la(self, processor):
        """Test DE LA prefix removal"""
        result = processor._remove_name_prefixes("DE LA CRUZ")
        assert result == "CRUZ", f"Expected 'CRUZ', got '{result}'"

    def test_prefix_von(self, processor):
        """Test VON prefix removal"""
        result = processor._remove_name_prefixes("VON BRAUN")
        assert result == "BRAUN", f"Expected 'BRAUN', got '{result}'"

    def test_prefix_van(self, processor):
        """Test VAN prefix removal"""
        result = processor._remove_name_prefixes("VAN GOGH")
        assert result == "GOGH", f"Expected 'GOGH', got '{result}'"

    def test_prefix_de(self, processor):
        """Test DE prefix removal"""
        result = processor._remove_name_prefixes("DE GAULLE")
        assert result == "GAULLE", f"Expected 'GAULLE', got '{result}'"

    def test_prefix_de_with_multipart(self, processor):
        """Test DE prefix removal with multi-part remainder"""
        result = processor._remove_name_prefixes("DE ROIG-MEYN")
        assert result == "ROIG-MEYN", f"Expected 'ROIG-MEYN', got '{result}'"

    def test_prefix_mc(self, processor):
        """Test MC prefix removal"""
        result = processor._remove_name_prefixes("MC GREGOR")
        assert result == "GREGOR", f"Expected 'GREGOR', got '{result}'"

    def test_prefix_mac(self, processor):
        """Test MAC prefix removal"""
        result = processor._remove_name_prefixes("MAC DONALD")
        assert result == "DONALD", f"Expected 'DONALD', got '{result}'"

    def test_prefix_o(self, processor):
        """Test O prefix removal"""
        result = processor._remove_name_prefixes("O BRIEN")
        assert result == "BRIEN", f"Expected 'BRIEN', got '{result}'"

    def test_no_prefix(self, processor):
        """Test surname without prefix remains unchanged"""
        result = processor._remove_name_prefixes("SMITH")
        assert result == "SMITH", f"Expected 'SMITH', got '{result}'"

    def test_no_prefix_multipart(self, processor):
        """Test multi-part surname without prefix remains unchanged"""
        result = processor._remove_name_prefixes("ROIG-MEYN")
        assert result == "ROIG-MEYN", f"Expected 'ROIG-MEYN', got '{result}'"

    def test_prefix_case_insensitive(self, processor):
        """Test prefix removal is case insensitive"""
        result = processor._remove_name_prefixes("von smith")
        assert result == "SMITH", f"Expected 'SMITH', got '{result}'"


class TestFullConcatGeneration:
    """Integration tests for full CONCAT ID generation"""

    @pytest.fixture
    def processor(self):
        """Create a test processor instance"""
        processor = IDValidationProcessor(
            client_type="buyer", logger=None, verbose=True
        )
        return processor

    def test_concat_with_multipart_surname(self, processor):
        """Test full CONCAT generation with multi-part surname"""
        record = ClientRecord(
            row_index=0,
            transaction_ref="TEST001",
            account_id="ACC001",
            person_code="PER001",
            account_type="P",
            id_value="",
            id_type="",
            first_name="ROGER",
            surname="ROIG-MEYN",
            date_of_birth="2011-03-01",
            gender="",
            primary_nationality="GB",
        )

        concat_id = processor._generate_concat(record, "GB")

        # Expected: GB + 20110301 + ROGER + ROIGM
        expected = "GB20110301ROGERROIGM"
        assert concat_id == expected, f"Expected '{expected}', got '{concat_id}'"

    def test_concat_with_prefix_and_multipart(self, processor):
        """Test CONCAT with prefix removal and multi-part surname"""
        record = ClientRecord(
            row_index=0,
            transaction_ref="TEST002",
            account_id="ACC002",
            person_code="PER002",
            account_type="P",
            id_value="",
            id_type="",
            first_name="HANS",
            surname="VON ROIG-MEYN",
            date_of_birth="1990-05-15",
            gender="",
            primary_nationality="DE",
        )

        concat_id = processor._generate_concat(record, "DE")

        # Expected: DE + 19900515 + HANS# + ROIGM
        # VON prefix removed, then ROIG-MEYN -> ROIGMEYN -> ROIGM
        expected = "DE19900515HANS#ROIGM"
        assert concat_id == expected, f"Expected '{expected}', got '{concat_id}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
