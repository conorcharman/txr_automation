"""Router tests for api/routers/drr.py — DRR compliance endpoints."""

import uuid

import pytest
from httpx import AsyncClient

# ISO 17442 mod-97 verified valid LEI (ISDA)
VALID_LEI = "529900T8BM49AURSDO55"
INVALID_LEI = "529900T8BM49AURSDO99"  # valid format, bad check digits

VALID_PAYLOAD = {
    "transactionRef": "TXN-API-001",
    "buyerId": VALID_LEI,
    "buyerIdType": "LEI",
    "sellerId": VALID_LEI,
    "sellerIdType": "LEI",
    "tradingDateTime": "2024-01-15T09:30:00",
    "quantity": 1000.0,
    "netAmount": 10500.0,
    "venue": "XLON",
    "isin": "GB0001234567",
    "investmentDecisionMaker": "ALGO",
}


@pytest.mark.anyio
async def test_list_rules_returns_200(client: AsyncClient) -> None:
    response = await client.get("/api/drr/rules")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_list_rules_returns_catalogue_entries(client: AsyncClient) -> None:
    response = await client.get("/api/drr/rules")
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    first = data[0]
    assert "ruleName" in first
    assert "fieldNumber" in first
    assert "fieldName" in first
    assert "regulation" in first
    assert "provision" in first


@pytest.mark.anyio
async def test_list_rules_sorted_by_field_number(client: AsyncClient) -> None:
    response = await client.get("/api/drr/rules")
    field_numbers = [r["fieldNumber"] for r in response.json()]
    assert field_numbers == sorted(field_numbers, key=lambda x: x.zfill(3))


@pytest.mark.anyio
async def test_compliance_check_valid_payload_returns_200(client: AsyncClient) -> None:
    response = await client.post("/api/drr/compliance-check", json=VALID_PAYLOAD)
    assert response.status_code == 200


@pytest.mark.anyio
async def test_compliance_check_response_shape(client: AsyncClient) -> None:
    response = await client.post("/api/drr/compliance-check", json=VALID_PAYLOAD)
    data = response.json()
    assert data["transactionRef"] == "TXN-API-001"
    assert "submissionId" in data
    assert "overallStatus" in data
    assert "checkedAt" in data
    assert isinstance(data["results"], list)
    assert data["totalRules"] > 0
    assert isinstance(data["passed"], int)
    assert isinstance(data["failed"], int)
    assert isinstance(data["warnings"], int)


@pytest.mark.anyio
async def test_compliance_check_results_carry_regulatory_references(client: AsyncClient) -> None:
    response = await client.post("/api/drr/compliance-check", json=VALID_PAYLOAD)
    result = response.json()["results"][0]
    assert result["fieldNumber"]
    assert result["fieldName"]
    assert result["regulation"]
    assert result["provision"]
    assert result["status"] in ("pass", "fail", "warning", "not_checked")


@pytest.mark.anyio
async def test_compliance_check_all_pass_on_valid_payload(client: AsyncClient) -> None:
    response = await client.post("/api/drr/compliance-check", json=VALID_PAYLOAD)
    data = response.json()
    assert data["overallStatus"] == "pass"
    assert data["failed"] == 0


@pytest.mark.anyio
async def test_compliance_check_invalid_buyer_lei_fails_rule(client: AsyncClient) -> None:
    payload = {**VALID_PAYLOAD, "buyerId": INVALID_LEI}
    response = await client.post("/api/drr/compliance-check", json=payload)
    assert response.status_code == 200
    data = response.json()
    buyer_result = next(r for r in data["results"] if r["ruleName"] == "BuyerSeller_Buyer")
    assert buyer_result["status"] == "fail"
    assert data["overallStatus"] == "fail"


@pytest.mark.anyio
async def test_compliance_check_missing_transaction_ref_returns_422(client: AsyncClient) -> None:
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "transactionRef"}
    response = await client.post("/api/drr/compliance-check", json=payload)
    assert response.status_code == 422


@pytest.mark.anyio
async def test_compliance_check_persists_to_submissions(client: AsyncClient) -> None:
    post = await client.post("/api/drr/compliance-check", json=VALID_PAYLOAD)
    submission_id = post.json()["submissionId"]

    history = await client.get("/api/drr/submissions")
    assert history.status_code == 200
    ids = [s["submissionId"] for s in history.json()]
    assert submission_id in ids


@pytest.mark.anyio
async def test_list_submissions_empty_initially(client: AsyncClient) -> None:
    response = await client.get("/api/drr/submissions")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.anyio
async def test_list_submissions_returns_summaries(client: AsyncClient) -> None:
    await client.post("/api/drr/compliance-check", json=VALID_PAYLOAD)
    response = await client.get("/api/drr/submissions")
    data = response.json()
    assert len(data) == 1
    summary = data[0]
    assert "submissionId" in summary
    assert "transactionRef" in summary
    assert "checkedAt" in summary
    assert "overallStatus" in summary
    assert "passed" in summary
    assert "failed" in summary
    assert "warnings" in summary


@pytest.mark.anyio
async def test_list_submissions_ordered_newest_first(client: AsyncClient) -> None:
    await client.post("/api/drr/compliance-check", json={**VALID_PAYLOAD, "transactionRef": "TXN-FIRST"})
    await client.post("/api/drr/compliance-check", json={**VALID_PAYLOAD, "transactionRef": "TXN-SECOND"})
    response = await client.get("/api/drr/submissions")
    data = response.json()
    assert data[0]["transactionRef"] == "TXN-SECOND"


@pytest.mark.anyio
async def test_get_submission_by_id_returns_200(client: AsyncClient) -> None:
    post = await client.post("/api/drr/compliance-check", json=VALID_PAYLOAD)
    submission_id = post.json()["submissionId"]
    response = await client.get(f"/api/drr/submissions/{submission_id}")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_get_submission_by_id_returns_full_results(client: AsyncClient) -> None:
    post = await client.post("/api/drr/compliance-check", json=VALID_PAYLOAD)
    submission_id = post.json()["submissionId"]
    response = await client.get(f"/api/drr/submissions/{submission_id}")
    data = response.json()
    assert data["submissionId"] == submission_id
    assert data["transactionRef"] == "TXN-API-001"
    assert isinstance(data["results"], list)
    assert len(data["results"]) > 0


@pytest.mark.anyio
async def test_get_submission_unknown_id_returns_404(client: AsyncClient) -> None:
    response = await client.get(f"/api/drr/submissions/{uuid.uuid4()}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# CDM report endpoint
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_cdm_report_returns_200(client: AsyncClient) -> None:
    response = await client.post("/api/drr/cdm-report", json=VALID_PAYLOAD)
    assert response.status_code == 200


@pytest.mark.anyio
async def test_cdm_report_response_shape(client: AsyncClient) -> None:
    response = await client.post("/api/drr/cdm-report", json=VALID_PAYLOAD)
    data = response.json()
    assert data["transactionRef"] == "TXN-API-001"
    assert "cdmJson" in data
    assert "enrichment" in data
    assert "complianceStatus" in data
    assert isinstance(data["passed"], int)
    assert isinstance(data["failed"], int)
    assert isinstance(data["warnings"], int)


@pytest.mark.anyio
async def test_cdm_report_json_has_expected_keys(client: AsyncClient) -> None:
    response = await client.post("/api/drr/cdm-report", json=VALID_PAYLOAD)
    cdm = response.json()["cdmJson"]
    assert cdm["$type"] == "TransactionReportInstruction"
    assert cdm["reportingRegime"] == "ESMA MiFIR RTS_22"
    assert cdm["transactionReference"] == "TXN-API-001"
    assert "originatingWorkflowStep" in cdm
    assert "reportingSide" in cdm


@pytest.mark.anyio
async def test_cdm_report_trade_contains_parties(client: AsyncClient) -> None:
    response = await client.post("/api/drr/cdm-report", json=VALID_PAYLOAD)
    instruction = response.json()["cdmJson"]["originatingWorkflowStep"]["proposedEvent"]["instruction"]
    trade = instruction[0]["before"]["trade"]
    roles = [p["partyRole"] for p in trade["party"]]
    assert "BUYER" in roles
    assert "SELLER" in roles


@pytest.mark.anyio
async def test_cdm_report_enrichment_keys_present(client: AsyncClient) -> None:
    response = await client.post("/api/drr/cdm-report", json=VALID_PAYLOAD)
    enrichment = response.json()["enrichment"]
    assert "buyer" in enrichment
    assert "seller" in enrichment
    assert "instrument" in enrichment


@pytest.mark.anyio
async def test_cdm_report_not_persisted_to_submissions(client: AsyncClient) -> None:
    await client.post("/api/drr/cdm-report", json=VALID_PAYLOAD)
    history = await client.get("/api/drr/submissions")
    assert history.json() == []


@pytest.mark.anyio
async def test_cdm_report_missing_transaction_ref_returns_422(client: AsyncClient) -> None:
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "transactionRef"}
    response = await client.post("/api/drr/cdm-report", json=payload)
    assert response.status_code == 422


@pytest.mark.anyio
async def test_cdm_report_compliance_status_pass_on_valid_payload(client: AsyncClient) -> None:
    response = await client.post("/api/drr/cdm-report", json=VALID_PAYLOAD)
    assert response.json()["complianceStatus"] == "pass"
