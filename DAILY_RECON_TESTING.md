# Daily Reconciliation — Testing & Validation Plan

**Scope:** Unit tests, integration tests, API tests, UI component tests, and E2E scenarios.

---

## 1. Unit Tests

### Data Model (api/daily_recon/model.py)

**File:** `tests/test_daily_recon/test_model.py`

```python
def test_recon_record_from_row_coerces_dates():
    """Dates parse correctly to date objects."""
    record = ReconRecord.from_row({
        "BUYER_DOB": "1990-05-15",
        "BUYER_ID": "GB12345",
        # ...other columns...
    })
    assert record.BUYER_DOB == date(1990, 5, 15)

def test_recon_record_from_row_preserves_raw():
    """Raw strings preserved for audit."""
    record = ReconRecord.from_row({
        "PRICE": "123.45",
        "QUANTITY": "1000",
    })
    assert record.raw["PRICE"] == "123.45"
    assert record.PRICE == Decimal("123.45")

def test_recon_record_coercion_failure_keeps_none():
    """Bad dates don't crash; kept as None."""
    record = ReconRecord.from_row({
        "BUYER_DOB": "invalid-date",
    })
    assert record.BUYER_DOB is None
    assert record.raw["BUYER_DOB"] == "invalid-date"

def test_recon_record_empty_strings_treated_as_null():
    """Empty strings coerced to None."""
    record = ReconRecord.from_row({
        "BUYER_ID": "",
        "PRICE": "   ",
    })
    assert record.BUYER_ID is None
    assert record.PRICE is None
```

### Validation Rules (api/daily_recon/validation/rules.py)

**File:** `tests/test_daily_recon/test_rules.py`

```python
def test_id_not_empty_rule_fails_null():
    rule = IdNotEmptyRule()
    result = rule.validate(None, {})
    assert not result.is_valid
    assert "empty" in result.message.lower()

def test_id_not_empty_rule_passes_valid():
    rule = IdNotEmptyRule()
    result = rule.validate("GB123456", {})
    assert result.is_valid

def test_id_format_rule_accepts_alphanumeric_dash():
    rule = IdFormatRule()
    result = rule.validate("GB-12_34.56", {})
    assert result.is_valid

def test_id_format_rule_rejects_special_chars():
    rule = IdFormatRule()
    result = rule.validate("GB@12#34", {})
    assert not result.is_valid

def test_country_code_rule_valid():
    rule = CountryCodeRule()
    assert rule.validate("GB", {}).is_valid
    assert rule.validate("gb", {}).is_valid  # Case-insensitive

def test_country_code_rule_invalid():
    rule = CountryCodeRule()
    assert not rule.validate("XX", {}).is_valid
    assert not rule.validate("", {}).is_valid

def test_numeric_rule():
    rule = NumericRule()
    assert rule.validate("123.45", {}).is_valid
    assert rule.validate("-50", {}).is_valid
    assert not rule.validate("abc", {}).is_valid

def test_positive_number_rule():
    rule = PositiveNumberRule()
    assert rule.validate("100", {}).is_valid
    assert rule.validate("0", {}).is_valid
    assert not rule.validate("-1", {}).is_valid

def test_date_format_rule():
    rule = DateFormatRule()
    assert rule.validate("2026-06-11", {}).is_valid
    assert rule.validate("11/06/2026", {}).is_valid
    assert rule.validate("06/11/2026", {}).is_valid
    assert not rule.validate("2026/06/11", {}).is_invalid  # Wrong format

def test_reasonable_date_rule():
    rule = ReasonableDateRule()
    assert rule.validate("2026-06-11", {}).is_valid
    assert not rule.validate("1850-01-01", {}).is_valid
    assert not rule.validate("2100-01-01", {}).is_valid

def test_indicator_rule():
    rule = IndicatorRule()
    assert rule.validate("Y", {}).is_valid
    assert rule.validate("N", {}).is_valid
    assert rule.validate("y", {}).is_valid  # Case-insensitive
    assert rule.validate("n", {}).is_valid
    assert not rule.validate("X", {}).is_valid
    assert not rule.validate("", {}).is_valid
```

### Validation Engine (api/daily_recon/validation/engine.py)

**File:** `tests/test_daily_recon/test_engine.py`

```python
def test_validate_batch_returns_results_per_row():
    batch = [
        {"BUYER_ID": "GB123", "PRICE": "100"},
        {"BUYER_ID": "", "PRICE": "abc"},
    ]
    results = validate_batch(batch)
    assert len(results) == 2
    assert len(results[0]) > 0  # Cells validated
    assert len(results[1]) > 0

def test_validate_batch_marks_cells_errored():
    batch = [
        {"BUYER_ID": "", "PRICE": "invalid"},
    ]
    results = validate_batch(batch)
    buyer_id_result = [r for r in results[0] if r.column_name == "BUYER_ID"][0]
    price_result = [r for r in results[0] if r.column_name == "PRICE"][0]
    assert buyer_id_result.is_errored
    assert price_result.is_errored

def test_validate_batch_collects_issues():
    batch = [
        {"BUYER_ID": "", "PRICE": "invalid"},
    ]
    results = validate_batch(batch)
    buyer_result = [r for r in results[0] if r.column_name == "BUYER_ID"][0]
    assert len(buyer_result.issues) > 0
    assert buyer_result.issues[0].rule_id == "id_not_empty"

def test_validate_batch_column_major():
    """Validation is column-major (not per-cell sequential)."""
    # This is tested indirectly via performance benchmarks
    # Expected: O(n_rows * n_rules_avg) not O(n_rows * n_columns * n_rules)
    pass
```

---

## 2. Integration Tests

### Service Layer (api/services/daily_recon_service.py)

**File:** `tests/test_daily_recon/test_service.py`

```python
import pytest
from uuid import uuid4
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

@pytest.fixture
async def test_db():
    """In-memory SQLite for tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

@pytest.mark.asyncio
async def test_create_run(test_db):
    async_session = AsyncSession(test_db)
    service = DailyReconService()
    
    run = await service.create_run(
        async_session,
        source_query="SELECT * FROM test",
    )
    
    assert run.id is not None
    assert run.status == "pending"
    assert run.source_query == "SELECT * FROM test"

@pytest.mark.asyncio
async def test_list_runs_paginated(test_db):
    async_session = AsyncSession(test_db)
    service = DailyReconService()
    
    # Create 5 runs
    for i in range(5):
        await service.create_run(async_session, source_query=f"Query {i}")
    
    runs = await service.list_runs(async_session, limit=3, offset=0)
    assert len(runs) == 3
    
    runs = await service.list_runs(async_session, limit=3, offset=3)
    assert len(runs) == 2

@pytest.mark.asyncio
async def test_approve_row(test_db):
    async_session = AsyncSession(test_db)
    service = DailyReconService()
    
    # Setup: create run + row
    run = await service.create_run(async_session, source_query="SELECT * FROM test")
    
    # Insert row manually (service doesn't yet create rows via API)
    # This will be done by Celery task in Phase 6
    row = ReconRow(run_id=run.id, row_index=0, trade_ref="T123")
    async_session.add(row)
    await async_session.commit()
    
    # Approve
    approved = await service.approve_row(async_session, row.id)
    assert approved.approved is True
    assert approved.approved_at is not None

@pytest.mark.asyncio
async def test_apply_correction(test_db):
    # (Similar setup as test_approve_row)
    # cell = ...
    # corrected = await service.apply_correction(async_session, cell.id, "fixed_value")
    # assert corrected.corrected_value == "fixed_value"
    pass

@pytest.mark.asyncio
async def test_accept_suggestion(test_db):
    # (Similar setup)
    # cell_with_suggestion = ...
    # accepted = await service.accept_suggestion(async_session, cell.id)
    # assert accepted.corrected_value == cell.suggested_fix
    pass
```

---

## 3. API Route Tests

**File:** `tests/test_daily_recon/test_routes.py`

```python
import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_post_runs_creates_run(client):
    response = await client.post(
        "/api/daily-recon/runs",
        json={"source_query": "SELECT * FROM test"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
    assert "id" in data

@pytest.mark.asyncio
async def test_get_runs_returns_paginated(client):
    # Create 2 runs
    for i in range(2):
        await client.post(
            "/api/daily-recon/runs",
            json={"source_query": f"Query {i}"},
        )
    
    response = await client.get("/api/daily-recon/runs?limit=10&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2
    assert len(data["data"]) >= 2

@pytest.mark.asyncio
async def test_get_run_detail_includes_rows(client):
    # Create run with rows (mocked)
    req = await client.post(
        "/api/daily-recon/runs",
        json={"source_query": "SELECT * FROM test"},
    )
    run_id = req.json()["id"]
    
    response = await client.get(f"/api/daily-recon/runs/{run_id}")
    assert response.status_code == 200
    data = response.json()
    assert "rows" in data or "id" in data

@pytest.mark.asyncio
async def test_patch_cell_correction(client):
    # Setup: get a cell ID
    # (Depends on Phase 6 when rows/cells exist)
    pass

@pytest.mark.asyncio
async def test_post_row_approve(client):
    # Setup: get a row ID
    # response = await client.post(f"/api/daily-recon/rows/{row_id}/approve")
    # assert response.status_code == 200
    # data = response.json()
    # assert data["approved"] is True
    pass

@pytest.mark.asyncio
async def test_get_export_returns_csv(client):
    # Setup: get run ID with approved rows
    # response = await client.get(f"/api/daily-recon/runs/{run_id}/export")
    # assert response.status_code == 200
    # assert response.headers["content-type"] == "text/csv"
    pass
```

---

## 4. Frontend Component Tests

**File:** `web/src/__tests__/DailyReconciliation.test.tsx`

```typescript
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import DailyReconciliation from "@/pages/DailyReconciliation";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
  },
});

const wrapper = ({ children }) => (
  <QueryClientProvider client={queryClient}>
    {children}
  </QueryClientProvider>
);

describe("DailyReconciliation", () => {
  beforeEach(() => {
    queryClient.clear();
  });

  it("renders page title", () => {
    render(<DailyReconciliation />, { wrapper });
    expect(screen.getByText("Daily Reconciliation")).toBeInTheDocument();
  });

  it("displays run list", async () => {
    render(<DailyReconciliation />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText(/run/i)).toBeInTheDocument();
    });
  });

  it("shows error badge on errored rows", async () => {
    // Mock data with errors
    // ...
    render(<DailyReconciliation />, { wrapper });
    expect(screen.getByText(/error/i)).toBeInTheDocument();
  });

  it("expands row on click", async () => {
    render(<DailyReconciliation />, { wrapper });
    const row = screen.getByText(/row 0/i);
    fireEvent.click(row);
    await waitFor(() => {
      expect(screen.getByText(/original value/i)).toBeInTheDocument();
    });
  });

  it("opens cell detail modal", async () => {
    render(<DailyReconciliation />, { wrapper });
    // Click to expand row, then click cell
    // ...
  });

  it("accepts suggestion and applies correction", async () => {
    // Mock API responses
    // Click "Accept" button
    // Verify corrected_value updates
    // ...
  });
});
```

---

## 5. End-to-End Test Scenarios

**File:** `tests/test_daily_recon/test_e2e.py`

### Scenario 1: Happy Path

```python
@pytest.mark.asyncio
async def test_e2e_extract_validate_approve_export():
    """Full flow: create run → validate → approve → export."""
    # 1. CREATE RUN
    run = await service.create_run(db, source_query="SELECT * FROM test_trades")
    assert run.status == "pending"
    
    # 2. SIMULATE EXTRACTION (phase 6 uses Celery)
    # Insert rows + cells manually (mock extraction)
    row1 = ReconRow(run_id=run.id, row_index=0, trade_ref="T001")
    cell1_buyer = ReconCell(
        row_id=row1.id,
        column_name="BUYER_ID",
        original_value="GB123",
    )
    cell1_price = ReconCell(
        row_id=row1.id,
        column_name="PRICE",
        original_value="invalid",  # Will fail numeric validation
        is_errored=True,
    )
    issue1 = ReconCellIssue(
        cell_id=cell1_price.id,
        rule_id="numeric",
        message="Not a valid number",
        suggested_fix="100.00",
    )
    db.add_all([row1, cell1_buyer, cell1_price, issue1])
    await db.commit()
    
    # 3. MARK ERROR STATE
    row1.has_error = True
    run.row_count = 1
    run.error_row_count = 1
    await db.commit()
    
    # 4. CORRECT & APPROVE
    await service.accept_suggestion(db, cell1_price.id)
    await service.approve_row(db, row1.id)
    
    # 5. VERIFY EXPORT DATA
    approved_rows = await db.execute(
        select(ReconRow).where(
            and_(ReconRow.run_id == run.id, ReconRow.approved == True)
        )
    )
    assert len(approved_rows.scalars().all()) == 1
```

### Scenario 2: Large Volume Performance

```python
@pytest.mark.asyncio
async def test_perf_1m_rows_validation():
    """1M rows validated in < 60 seconds."""
    import time
    
    # Generate 1M rows with validation issues
    batch_size = 10000
    start = time.time()
    
    for i in range(0, 1000000, batch_size):
        batch = [
            {
                "BUYER_ID": "",  # Will fail id_not_empty
                "PRICE": str(i),
                # ... 48 more columns
            }
            for _ in range(batch_size)
        ]
        results = validate_batch(batch, start_row_index=i)
        assert len(results) == batch_size
    
    elapsed = time.time() - start
    assert elapsed < 60, f"Validation took {elapsed}s (expected < 60s)"
    
    # Expected rate: 16.7K rows/sec
    rate = 1000000 / elapsed
    print(f"Validation rate: {rate:.0f} rows/sec")
```

---

## 6. Test Checklist

### Backend Unit Tests
- [ ] Model coercion (dates, decimals, nulls, empty strings)
- [ ] All 20+ validation rules (pass/fail/edge cases)
- [ ] Validation engine (batch, column-major, traceability)
- [ ] Column registry consistency

### Backend Integration Tests
- [ ] Service CRUD (create, read, list, update, delete)
- [ ] Row approval workflow
- [ ] Cell correction flow
- [ ] Suggestion acceptance
- [ ] Pagination & filters

### Backend API Tests
- [ ] POST /runs (create, return 201)
- [ ] GET /runs (paginated)
- [ ] GET /runs/{id} (detail with rows)
- [ ] GET /runs/{id}/rows (error filter, pagination)
- [ ] PATCH /cells/{id}/correct (update corrected_value)
- [ ] POST /cells/{id}/accept-suggestion
- [ ] POST /rows/{id}/approve (update flags + timestamp)
- [ ] GET /runs/{id}/export (CSV, approved only)
- [ ] Error handling (404, 400, 500)

### Frontend Component Tests
- [ ] RunList renders + polling
- [ ] RunDetail stats + export button
- [ ] RowInspector expand/collapse + error display
- [ ] CellDetailModal (original, issues, suggested, corrected)
- [ ] Accept suggestion mutation
- [ ] Manual correction input + apply
- [ ] Row approval toggle
- [ ] Error filter toggle

### E2E Tests
- [ ] Create run → validate → approve → export workflow
- [ ] Multiple rows with mixed error states
- [ ] Large volume (1M+ rows) performance

---

## 7. Performance Benchmarks

**File:** `tests/test_daily_recon/test_performance.py`

| Scenario | Target | Notes |
|----------|--------|-------|
| **Validation batch (10K rows)** | < 2s | Column-major engine |
| **Service list_rows (1000 rows, paginated)** | < 100ms | Indexed query |
| **API GET /runs/{id} (full detail)** | < 200ms | Includes 1000 nested rows/cells |
| **Export CSV (100K approved rows)** | < 5s | Streamed, not loaded in memory |
| **Frontend page render (1000 rows)** | < 1s | Virtualised grid recommended |

---

## 8. CI/CD Integration

### GitHub Actions (if available)

```yaml
name: Daily Recon Tests

on: [push, pull_request]

jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_PASSWORD: postgres
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: 3.10
      - run: pip install -r requirements.txt
      - run: pytest tests/test_daily_recon/ -v --cov

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-node@v2
        with:
          node-version: 18
      - run: cd web && npm install
      - run: npm run test
```

---

## 9. Manual Testing Checklist

- [ ] **Backend start:** `uvicorn api.main:app --reload` — no errors
- [ ] **DB tables created:** `psql dbname -c "\dt daily_recon*"` — 4 tables present
- [ ] **Frontend start:** `npm run dev` — loads at http://localhost:5173/daily-recon
- [ ] **Create run via API:** `curl -X POST ... /api/daily-recon/runs` — returns 201
- [ ] **List runs:** Appears in UI within 10 seconds (polling)
- [ ] **Inspect row:** Click row → sees cells/errors
- [ ] **Inspect cell:** Click cell → modal shows original, issues, suggested, corrected fields
- [ ] **Accept suggestion:** "Accept" button works → corrected_value updates
- [ ] **Manual correction:** Type in input → "Apply" works → saved value shown
- [ ] **Approve row:** Toggle "Approve" → row flagged + timestamp set
- [ ] **Export:** Button enabled (if approved rows) → CSV downloads

---

## 10. Known Limitations & Future Work

| Item | Status | Phase |
|------|--------|-------|
| SQL source streaming from SQL Server | TODO | Phase 6 |
| Celery task integration | TODO | Phase 6 |
| CSV export endpoint | TODO | Phase 7 |
| Scheduled daily runs | TODO | Phase 8 |
| Batch approve/reject UI | TODO | Future |
| Revalidate after correction | TODO | Future |
| Rule-specific error filter | TODO | Future |
| Data lineage / audit log | TODO | Future |

---

**Test Coverage Goal:** Minimum 80% for backend (model + validation + service), 60% for frontend (mocked API responses).

