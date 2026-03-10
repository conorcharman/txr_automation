"""
Unit tests for FCA FIRDS XML parser (firds.parser).

Tests cover:
- FULINS (full file) record parsing
- DLTINS delta record types: NewRcrd, ModfdRcrd, TermntdRcrd, CancRcrd
- Namespace handling (with and without XML namespace)
- Graceful handling of records missing ISIN or MIC
- Date normalisation
"""

import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from firds.parser import (
    FirdsXmlParser,
    InstrumentRecord,
    _extract_namespace,
    _local_name,
    _normalise_date,
    _normalise_date_optional,
)


# ---------------------------------------------------------------------------
# XML fixture helpers
# ---------------------------------------------------------------------------

_NS = "urn:iso:std:iso:20022:tech:xsd:auth.017.001.01"
_DELTA_NS = "urn:iso:std:iso:20022:tech:xsd:auth.036.001.03"


def _make_fulins_xml(isin: str, mic: str, cfi: str = "ESXXXX",
                     admission: str = "2020-01-15",
                     termination: str = "",
                     rca: str = "GB") -> str:
    """Return a minimal FULINS XML string for one RefData record."""
    term_elem = f"<{_NS_PFX}TermntnDt>{termination}</{_NS_PFX}TermntnDt>" if termination else ""
    return textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <Document xmlns="{_NS}">
          <FinInstrmRptgRefDataRpt>
            <RefData>
              <FinInstrmGnlAttrbts>
                <Id>{isin}</Id>
                <FullNm>Test Instrument</FullNm>
                <ShrtNm>TESTINST</ShrtNm>
                <ClssfctnTp>{cfi}</ClssfctnTp>
              </FinInstrmGnlAttrbts>
              <TradgVnRltdAttrbts>
                <Id>{mic}</Id>
                <AdmssnApprvlDtByTheTradgVn>{admission}</AdmssnApprvlDtByTheTradgVn>
                {term_elem}
              </TradgVnRltdAttrbts>
              <TechRcrdId>
                <TechAttrbts>
                  <RlvntCmptntAuthrty>{rca}</RlvntCmptntAuthrty>
                </TechAttrbts>
              </TechRcrdId>
            </RefData>
          </FinInstrmRptgRefDataRpt>
        </Document>
    """)


_NS_PFX = ""  # used in helpers above – overridden below when namespace is present


def _make_delta_xml(record_tag: str, isin: str, mic: str,
                    admission: str = "2020-01-15",
                    termination: str = "") -> str:
    """Return a minimal DLTINS XML string for one delta record."""
    term_elem = f"<TermntnDt>{termination}</TermntnDt>" if termination else ""
    return textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <Document xmlns="{_DELTA_NS}">
          <FinInstrmRptgDltaRpt>
            <{record_tag}>
              <FinInstrmGnlAttrbts>
                <Id>{isin}</Id>
                <FullNm>Delta Instrument</FullNm>
                <ShrtNm>DELTINST</ShrtNm>
                <ClssfctnTp>ESXXXX</ClssfctnTp>
              </FinInstrmGnlAttrbts>
              <TradgVnRltdAttrbts>
                <Id>{mic}</Id>
                <AdmssnApprvlDtByTheTradgVn>{admission}</AdmssnApprvlDtByTheTradgVn>
                {term_elem}
              </TradgVnRltdAttrbts>
            </{record_tag}>
          </FinInstrmRptgDltaRpt>
        </Document>
    """)


@pytest.fixture()
def tmp_xml(tmp_path):
    """Factory fixture: returns a function that writes XML to a temp file."""

    def _write(content: str, filename: str = "test.xml") -> Path:
        p = tmp_path / filename
        p.write_text(content, encoding="utf-8")
        return p

    return _write


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_extract_namespace_present(self):
        tag = f"{{{_NS}}}Document"
        assert _extract_namespace(tag) == f"{{{_NS}}}"

    def test_extract_namespace_absent(self):
        assert _extract_namespace("Document") == ""

    def test_local_name_with_namespace(self):
        tag = f"{{{_NS}}}RefData"
        assert _local_name(tag) == "RefData"

    def test_local_name_without_namespace(self):
        assert _local_name("RefData") == "RefData"

    def test_normalise_date_full_timestamp(self):
        assert _normalise_date("2026-03-08T00:00:00Z") == "2026-03-08"

    def test_normalise_date_plain_date(self):
        assert _normalise_date("2026-03-08") == "2026-03-08"

    def test_normalise_date_empty(self):
        assert _normalise_date("") == ""

    def test_normalise_date_optional_returns_none_for_empty(self):
        assert _normalise_date_optional("") is None

    def test_normalise_date_optional_returns_value(self):
        assert _normalise_date_optional("2026-03-08") == "2026-03-08"


# ---------------------------------------------------------------------------
# FULINS full file parsing
# ---------------------------------------------------------------------------


class TestFullFileParsing:
    def test_parses_single_record(self, tmp_xml):
        xml = _make_fulins_xml("GB00B3RBWM25", "XLON")
        path = tmp_xml(xml)
        parser = FirdsXmlParser()
        records = list(parser.parse(path))
        assert len(records) == 1

    def test_record_type_is_full(self, tmp_xml):
        xml = _make_fulins_xml("GB00B3RBWM25", "XLON")
        path = tmp_xml(xml)
        records = list(FirdsXmlParser().parse(path))
        assert records[0].record_type == "FULL"

    def test_isin_and_mic_extracted(self, tmp_xml):
        xml = _make_fulins_xml("GB00B3RBWM25", "XLON")
        path = tmp_xml(xml)
        record = list(FirdsXmlParser().parse(path))[0]
        assert record.isin == "GB00B3RBWM25"
        assert record.mic == "XLON"

    def test_cfi_extracted(self, tmp_xml):
        xml = _make_fulins_xml("GB00B3RBWM25", "XLON", cfi="ESXXXX")
        path = tmp_xml(xml)
        record = list(FirdsXmlParser().parse(path))[0]
        assert record.cfi_code == "ESXXXX"

    def test_admission_date_extracted(self, tmp_xml):
        xml = _make_fulins_xml("GB00B3RBWM25", "XLON", admission="2021-06-01")
        path = tmp_xml(xml)
        record = list(FirdsXmlParser().parse(path))[0]
        assert record.admission_date == "2021-06-01"

    def test_termination_date_absent_is_none(self, tmp_xml):
        xml = _make_fulins_xml("GB00B3RBWM25", "XLON")
        path = tmp_xml(xml)
        record = list(FirdsXmlParser().parse(path))[0]
        assert record.termination_date is None

    def test_termination_date_present(self, tmp_xml):
        xml = _make_fulins_xml("GB00B3RBWM25", "XLON", termination="2025-12-31")
        path = tmp_xml(xml)
        record = list(FirdsXmlParser().parse(path))[0]
        assert record.termination_date == "2025-12-31"

    def test_rca_extracted(self, tmp_xml):
        xml = _make_fulins_xml("GB00B3RBWM25", "XLON", rca="GB")
        path = tmp_xml(xml)
        record = list(FirdsXmlParser().parse(path))[0]
        assert record.rca == "GB"

    def test_full_name_extracted(self, tmp_xml):
        xml = _make_fulins_xml("GB00B3RBWM25", "XLON")
        path = tmp_xml(xml)
        record = list(FirdsXmlParser().parse(path))[0]
        assert record.full_name == "Test Instrument"

    def test_multiple_records(self, tmp_xml):
        """Two RefData blocks in one file should yield two records."""
        xml = textwrap.dedent(f"""\
            <?xml version="1.0" encoding="UTF-8"?>
            <Document xmlns="{_NS}">
              <FinInstrmRptgRefDataRpt>
                <RefData>
                  <FinInstrmGnlAttrbts><Id>GB00B3RBWM25</Id><FullNm>A</FullNm><ShrtNm>A</ShrtNm><ClssfctnTp>ES</ClssfctnTp></FinInstrmGnlAttrbts>
                  <TradgVnRltdAttrbts><Id>XLON</Id><AdmssnApprvlDtByTheTradgVn>2020-01-01</AdmssnApprvlDtByTheTradgVn></TradgVnRltdAttrbts>
                  <TechRcrdId><TechAttrbts><RlvntCmptntAuthrty>GB</RlvntCmptntAuthrty></TechAttrbts></TechRcrdId>
                </RefData>
                <RefData>
                  <FinInstrmGnlAttrbts><Id>US0378331005</Id><FullNm>B</FullNm><ShrtNm>B</ShrtNm><ClssfctnTp>ES</ClssfctnTp></FinInstrmGnlAttrbts>
                  <TradgVnRltdAttrbts><Id>XNAS</Id><AdmssnApprvlDtByTheTradgVn>2019-05-01</AdmssnApprvlDtByTheTradgVn></TradgVnRltdAttrbts>
                  <TechRcrdId><TechAttrbts><RlvntCmptntAuthrty>US</RlvntCmptntAuthrty></TechAttrbts></TechRcrdId>
                </RefData>
              </FinInstrmRptgRefDataRpt>
            </Document>
        """)
        records = list(FirdsXmlParser().parse(tmp_xml(xml)))
        assert len(records) == 2
        assert records[0].isin == "GB00B3RBWM25"
        assert records[1].isin == "US0378331005"

    def test_record_missing_isin_skipped(self, tmp_xml):
        """Records without ISIN should be silently skipped."""
        xml = textwrap.dedent(f"""\
            <?xml version="1.0" encoding="UTF-8"?>
            <Document xmlns="{_NS}">
              <FinInstrmRptgRefDataRpt>
                <RefData>
                  <FinInstrmGnlAttrbts><FullNm>No ISIN</FullNm><ShrtNm>X</ShrtNm><ClssfctnTp>ES</ClssfctnTp></FinInstrmGnlAttrbts>
                  <TradgVnRltdAttrbts><Id>XLON</Id></TradgVnRltdAttrbts>
                </RefData>
              </FinInstrmRptgRefDataRpt>
            </Document>
        """)
        records = list(FirdsXmlParser().parse(tmp_xml(xml)))
        assert records == []


# ---------------------------------------------------------------------------
# DLTINS delta record types
# ---------------------------------------------------------------------------


class TestDeltaFileParsing:
    def test_new_record_type(self, tmp_xml):
        xml = _make_delta_xml("NewRcrd", "GB00B3RBWM25", "XLON")
        records = list(FirdsXmlParser().parse(tmp_xml(xml)))
        assert len(records) == 1
        assert records[0].record_type == "NEW"

    def test_modified_record_type(self, tmp_xml):
        xml = _make_delta_xml("ModfdRcrd", "GB00B3RBWM25", "XLON")
        records = list(FirdsXmlParser().parse(tmp_xml(xml)))
        assert records[0].record_type == "MOD"

    def test_terminated_record_type(self, tmp_xml):
        xml = _make_delta_xml("TermntdRcrd", "GB00B3RBWM25", "XLON", termination="2025-06-30")
        records = list(FirdsXmlParser().parse(tmp_xml(xml)))
        assert records[0].record_type == "TERM"
        assert records[0].termination_date == "2025-06-30"

    def test_cancelled_record_type(self, tmp_xml):
        xml = _make_delta_xml("CancRcrd", "GB00B3RBWM25", "XLON")
        records = list(FirdsXmlParser().parse(tmp_xml(xml)))
        assert records[0].record_type == "CANC"

    def test_delta_isin_and_mic(self, tmp_xml):
        xml = _make_delta_xml("NewRcrd", "FR0012345678", "XPAR")
        records = list(FirdsXmlParser().parse(tmp_xml(xml)))
        assert records[0].isin == "FR0012345678"
        assert records[0].mic == "XPAR"

    def test_file_not_found_raises(self):
        parser = FirdsXmlParser()
        with pytest.raises(FileNotFoundError):
            list(parser.parse(Path("/nonexistent/path.xml")))


# ---------------------------------------------------------------------------
# BAH-wrapped schema v2 (auth.017.001.02 inside head.003 BizData envelope)
# ---------------------------------------------------------------------------

_V2_NS = "urn:iso:std:iso:20022:tech:xsd:auth.017.001.02"
_BAH_NS = "urn:iso:std:iso:20022:tech:xsd:head.003.001.01"


def _make_fulins_v2_xml(
    isin: str,
    mic: str,
    admission: str = "2022-03-09",
    termination: str = "",
    rca: str = "NO",
) -> str:
    """Return a BAH-wrapped auth.017.001.02 FULINS XML with one RefData record."""
    term_elem = f"<TermntnDt>{termination}</TermntnDt>" if termination else ""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<BizData xmlns="{_BAH_NS}">'
        f'<Hdr><AppHdr xmlns="urn:iso:std:iso:20022:tech:xsd:head.001.001.01">'
        '<MsgDefIdr>auth.017.001.02</MsgDefIdr></AppHdr></Hdr>'
        f'<Pyld><Document xmlns="{_V2_NS}">'
        "<FinInstrmRptgRefDataRpt><RefData>"
        f"<FinInstrmGnlAttrbts><Id>{isin}</Id>"
        "<FullNm>Test V2</FullNm><ShrtNm>TST2</ShrtNm>"
        "<ClssfctnTp>FCACSX</ClssfctnTp></FinInstrmGnlAttrbts>"
        f"<TradgVnRltdAttrbts><Id>{mic}</Id>"
        f"<AdmssnApprvlDtByIssr>{admission}</AdmssnApprvlDtByIssr>"
        f"{term_elem}</TradgVnRltdAttrbts>"
        f"<TechAttrbts><RlvntCmptntAuthrty>{rca}</RlvntCmptntAuthrty></TechAttrbts>"
        "</RefData></FinInstrmRptgRefDataRpt>"
        "</Document></Pyld></BizData>"
    )


class TestBahWrappedSchemaV2:
    """Parser correctly handles BAH-wrapped auth.017.001.02 FULINS files."""

    def test_bah_wrapped_parses_isin_and_mic(self, tmp_xml):
        xml = _make_fulins_v2_xml("NO0012469701", "FISH")
        records = list(FirdsXmlParser().parse(tmp_xml(xml)))
        assert len(records) == 1
        assert records[0].isin == "NO0012469701"
        assert records[0].mic == "FISH"

    def test_bah_wrapped_admission_via_issuer_field(self, tmp_xml):
        xml = _make_fulins_v2_xml("NO0012469701", "FISH", admission="2022-03-09")
        records = list(FirdsXmlParser().parse(tmp_xml(xml)))
        assert records[0].admission_date == "2022-03-09"

    def test_bah_wrapped_termination_date(self, tmp_xml):
        xml = _make_fulins_v2_xml("NO0012469701", "FISH", termination="2026-11-13")
        records = list(FirdsXmlParser().parse(tmp_xml(xml)))
        assert records[0].termination_date == "2026-11-13"

    def test_bah_wrapped_rca_without_tech_rcrd_id_wrapper(self, tmp_xml):
        xml = _make_fulins_v2_xml("NO0012469701", "FISH", rca="NO")
        records = list(FirdsXmlParser().parse(tmp_xml(xml)))
        assert records[0].rca == "NO"

    def test_bah_wrapped_record_type_is_full(self, tmp_xml):
        xml = _make_fulins_v2_xml("NO0012469701", "FISH")
        records = list(FirdsXmlParser().parse(tmp_xml(xml)))
        assert records[0].record_type == "FULL"

    def test_bah_wrapped_cfi_code(self, tmp_xml):
        xml = _make_fulins_v2_xml("NO0012469701", "FISH")
        records = list(FirdsXmlParser().parse(tmp_xml(xml)))
        assert records[0].cfi_code == "FCACSX"

    def test_bah_wrapped_multiple_records(self, tmp_xml):
        rec = (
            "<RefData>"
            "<FinInstrmGnlAttrbts><Id>{isin}</Id><FullNm>X</FullNm>"
            "<ShrtNm>X</ShrtNm><ClssfctnTp>ESXXXX</ClssfctnTp></FinInstrmGnlAttrbts>"
            "<TradgVnRltdAttrbts><Id>{mic}</Id>"
            "<AdmssnApprvlDtByIssr>2021-01-01</AdmssnApprvlDtByIssr></TradgVnRltdAttrbts>"
            "<TechAttrbts><RlvntCmptntAuthrty>DE</RlvntCmptntAuthrty></TechAttrbts>"
            "</RefData>"
        )
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<BizData xmlns="{_BAH_NS}"><Hdr></Hdr><Pyld>'
            f'<Document xmlns="{_V2_NS}"><FinInstrmRptgRefDataRpt>'
            + rec.format(isin="DE000A0D9PT0", mic="XFRA")
            + rec.format(isin="DE000A1EWWW0", mic="XETR")
            + "</FinInstrmRptgRefDataRpt></Document></Pyld></BizData>"
        )
        records = list(FirdsXmlParser().parse(tmp_xml(xml)))
        assert len(records) == 2
        assert {r.isin for r in records} == {"DE000A0D9PT0", "DE000A1EWWW0"}
