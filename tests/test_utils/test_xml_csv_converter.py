#!/usr/bin/env python3
"""Tests for XML to CSV converter auth.016 transaction flattening behaviour."""

import csv
from pathlib import Path

from utils.xml_csv_converter import XMLToCSVConverter


def _write_sample_auth016_xml(xml_path: Path) -> None:
    """Write a minimal auth.016-like XML with two outer Tx records."""
    xml_content = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<h3:BizData xmlns:h3=\"urn:iso:std:iso:20022:tech:xsd:head.003.001.01\"
    xmlns:a=\"urn:iso:std:iso:20022:tech:xsd:auth.016.199.01\">
    <h3:Pyld>
        <a:Document>
            <a:FinInstrmRptgTxRpt>
                <a:Tx>
                    <a:New>
                        <a:TxId>TX-1</a:TxId>
                        <a:Tx>
                            <a:TradDt>2022-08-08T12:48:00.6901234Z</a:TradDt>
                            <a:TradgCpcty>MTCH</a:TradgCpcty>
                            <a:Qty>
                                <a:Unit>10</a:Unit>
                            </a:Qty>
                            <a:DerivNtnlChng>DECR</a:DerivNtnlChng>
                            <a:Pric>
                                <a:Pric>
                                    <a:MntryVal>
                                        <a:Amt Ccy=\"GBP\">999.99999999</a:Amt>
                                        <a:Sgn>true</a:Sgn>
                                    </a:MntryVal>
                                </a:Pric>
                            </a:Pric>
                            <a:TradVn>GB02</a:TradVn>
                            <a:CtryOfBrnch>DK</a:CtryOfBrnch>
                        </a:Tx>
                        <a:AddtlAttrbts>
                            <a:WvrInd>NETW</a:WvrInd>
                            <a:WvrInd>NTLS</a:WvrInd>
                            <a:SctiesFincgTxInd>false</a:SctiesFincgTxInd>
                        </a:AddtlAttrbts>
                    </a:New>
                </a:Tx>
                <a:Tx>
                    <a:New>
                        <a:TxId>TX-2</a:TxId>
                        <a:Tx>
                            <a:TradDt>2022-08-08T12:48:00.6900000Z</a:TradDt>
                            <a:TradgCpcty>MTCH</a:TradgCpcty>
                            <a:Qty>
                                <a:Unit>20</a:Unit>
                            </a:Qty>
                            <a:TradVn>GB02</a:TradVn>
                            <a:CtryOfBrnch>DK</a:CtryOfBrnch>
                        </a:Tx>
                        <a:AddtlAttrbts>
                            <a:OTCPstTradInd>CLSE</a:OTCPstTradInd>
                            <a:OTCPstTradInd>PORT</a:OTCPstTradInd>
                            <a:SctiesFincgTxInd>false</a:SctiesFincgTxInd>
                        </a:AddtlAttrbts>
                    </a:New>
                </a:Tx>
            </a:FinInstrmRptgTxRpt>
        </a:Document>
    </h3:Pyld>
</h3:BizData>
"""
    xml_path.write_text(xml_content, encoding="utf-8")


def _write_sample_auth016_with_mic_identity(xml_path: Path) -> None:
    """Write auth.016-like XML where buyer/seller account owner IDs use MIC."""
    xml_content = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<h3:BizData xmlns:h3=\"urn:iso:std:iso:20022:tech:xsd:head.003.001.01\"
    xmlns:a=\"urn:iso:std:iso:20022:tech:xsd:auth.016.199.01\">
    <h3:Pyld>
        <a:Document>
            <a:FinInstrmRptgTxRpt>
                <a:Tx>
                    <a:New>
                        <a:TxId>TX-MIC</a:TxId>
                        <a:Buyr>
                            <a:AcctOwnr>
                                <a:Id>
                                    <a:MIC>GB01</a:MIC>
                                </a:Id>
                            </a:AcctOwnr>
                        </a:Buyr>
                        <a:Sellr>
                            <a:AcctOwnr>
                                <a:Id>
                                    <a:MIC>GB02</a:MIC>
                                </a:Id>
                            </a:AcctOwnr>
                        </a:Sellr>
                        <a:Tx>
                            <a:TradDt>2022-08-08T12:48:00.690Z</a:TradDt>
                            <a:TradgCpcty>MTCH</a:TradgCpcty>
                            <a:Qty>
                                <a:Unit>1</a:Unit>
                            </a:Qty>
                            <a:TradVn>GB02</a:TradVn>
                            <a:CtryOfBrnch>DK</a:CtryOfBrnch>
                        </a:Tx>
                    </a:New>
                </a:Tx>
            </a:FinInstrmRptgTxRpt>
        </a:Document>
    </h3:Pyld>
</h3:BizData>
"""
    xml_path.write_text(xml_content, encoding="utf-8")


def test_auth016_single_tx_per_record(tmp_path: Path) -> None:
    """Each outer Tx should produce exactly one CSV row."""
    xml_path = tmp_path / "sample.xml"
    csv_path = tmp_path / "sample.csv"
    _write_sample_auth016_xml(xml_path)

    converter = XMLToCSVConverter()
    result = converter.convert_file(xml_path, csv_path)

    assert result.success
    assert result.record_count == 2

    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == 2


def test_auth016_expected_mappings_and_no_shadow_columns(tmp_path: Path) -> None:
    """Ensure nested Tx fields map to New_Tx_* and no duplicate shadow columns exist."""
    xml_path = tmp_path / "sample.xml"
    csv_path = tmp_path / "sample.csv"
    _write_sample_auth016_xml(xml_path)

    converter = XMLToCSVConverter()
    result = converter.convert_file(xml_path, csv_path)

    assert result.success

    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        headers = reader.fieldnames or []

    assert "TradDt" not in headers
    assert "CtryOfBrnch" not in headers

    assert rows[0]["New_Tx_DerivNtnlChng"] == "DECR"
    assert rows[0]["New_AddtlAttrbts_WvrInd"] == "NETW|NTLS"
    assert rows[1]["New_AddtlAttrbts_OTCPstTradInd"] == "CLSE|PORT"


def test_datetime_normalisation_in_output(tmp_path: Path) -> None:
    """UTC datetimes with >3 fractional digits should be truncated to milliseconds."""
    xml_path = tmp_path / "sample.xml"
    csv_path = tmp_path / "sample.csv"
    _write_sample_auth016_xml(xml_path)

    converter = XMLToCSVConverter()
    result = converter.convert_file(xml_path, csv_path)

    assert result.success

    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    assert rows[0]["New_Tx_TradDt"] == "2022-08-08T12:48:00.690Z"
    assert rows[1]["New_Tx_TradDt"] == "2022-08-08T12:48:00.690Z"


def test_normalise_datetime_helper() -> None:
    """Helper should only alter UTC values with over-precision fractions."""
    assert (
        XMLToCSVConverter._normalise_datetime("2022-08-08T12:48:00.6901234Z")
        == "2022-08-08T12:48:00.690Z"
    )
    assert (
        XMLToCSVConverter._normalise_datetime("2022-08-08T12:48:00.690Z")
        == "2022-08-08T12:48:00.690Z"
    )
    assert XMLToCSVConverter._normalise_datetime("not-a-datetime") == "not-a-datetime"


def test_auth016_mic_identity_mapping(tmp_path: Path) -> None:
    """Buyer/seller MIC identity choice should map to *_Id_MIC columns."""
    xml_path = tmp_path / "sample_mic.xml"
    csv_path = tmp_path / "sample_mic.csv"
    _write_sample_auth016_with_mic_identity(xml_path)

    converter = XMLToCSVConverter()
    result = converter.convert_file(xml_path, csv_path)

    assert result.success

    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == 1
    assert rows[0]["New_Buyr_AcctOwnr_Id_MIC"] == "GB01"
    assert rows[0]["New_Sellr_AcctOwnr_Id_MIC"] == "GB02"
