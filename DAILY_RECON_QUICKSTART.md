# Daily Reconciliation — Quick Start Guide

## Prerequisites

- **Backend:** Python 3.10+, PostgreSQL 12+, Redis (for Celery)
- **Frontend:** Node.js 18+, npm/yarn
- **SQL Source:** SQL Server (or adapt aioodbc to your DB)
- **Environment:** txr_automation conda environment activated

---

## 1. Configuration Setup

### Step 1a: Add Environment Variable

Add to your `.env` or `config/local/environment.yml`:

```yaml
# SQL Server connection for daily recon extraction
DAILY_RECON_SOURCE_URL: "mssql+aioodbc://sa:your_password@localhost:1433/your_database?driver=ODBC+Driver+17+for+SQL+Server"
```

### Step 1b: Update api/config.py

**NOTE:** This file is access-restricted. Contact admin or manually add:

```python
from pydantic import Field

class Settings(BaseSettings):
    # ...existing settings...
    
    daily_recon_source_url: str = Field(
        default="mssql+aioodbc://sa:password@localhost:1433/dbname",
        description="SQL Server connection for daily recon report extraction"
    )
```

### Step 1c: Install SQL Server ODBC Driver (if Linux/Unix)

```bash
# Ubuntu/Debian
sudo apt install -y unixodbc-dev
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
sudo apt install -y msodbcsql17

# macOS
brew install msodbcsql17 unixodbc

# Windows: Download from Microsoft or via msodbcsql17-msi
```

### Step 1d: Verify Connection

```bash
conda activate txr_automation
python -c "
import aioodbc
import asyncio

async def test():
    conn_str = 'mssql+aioodbc://sa:password@localhost:1433/dbname?driver=ODBC+Driver+17+for+SQL+Server'
    async with aioodbc.connect(conn_str) as conn:
        async with conn.cursor() as cur:
            await cur.execute('SELECT 1')
            print(await cur.fetchone())

asyncio.run(test())
"
```

---

## 2. Database Setup

### Automatic (Recommended)

PostgreSQL tables are auto-created via SQLAlchemy in `api/main.py` lifespan:

```bash
uvicorn api.main:app --reload
# Check logs: "Database tables created / verified."
```

### Manual (if needed)

```bash
psql -U postgres -d txr_automation -f api/daily_recon/schema.sql
```

---

## 3. Backend Startup

```bash
# Terminal 1: Activate environment
conda activate txr_automation
cd /path/to/txr_automation

# Start FastAPI development server
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Check: http://localhost:8000/docs (FastAPI Swagger UI)
```

### Verify Backend Health

```bash
curl http://localhost:8000/api/health
# Should respond with {"status": "ok", ...}
```

---

## 4. Frontend Startup

```bash
# Terminal 2: In another window
cd /path/to/txr_automation/web
npm install  # (if node_modules not present)
npm run dev

# Check: http://localhost:5173/
```

---

## 5. Navigate to Daily Reconciliation

1. Open browser → http://localhost:5173/
2. Click **"Daily Reconciliation"** in sidebar (BarChart3 icon)
3. Click **"New Run"** (TODO: will be implemented in Phase 6 when Celery task is wired)

---

## 6. First Run: Manual Testing with API

### 6a. Create a Test Run

```bash
curl -X POST http://localhost:8000/api/daily-recon/runs \
  -H "Content-Type: application/json" \
  -d '{
    "source_query": "SELECT * FROM your_reconciliation_report LIMIT 100",
    "job_id": null
  }'

# Note the returned `id` (run_id)
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "job_id": null,
  "source_query": "SELECT * FROM ...",
  "row_count": 0,
  "error_row_count": 0,
  "status": "pending",
  "created_at": "2026-06-11T12:30:00Z",
  "updated_at": "2026-06-11T12:30:00Z"
}
```

### 6b. List Runs

```bash
curl http://localhost:8000/api/daily-recon/runs
```

### 6c: Get Run Detail

```bash
curl http://localhost:8000/api/daily-recon/runs/{run_id}
```

---

## 7. UI Walkthrough

### View: Run List
- Shows all historical runs
- Badges: status (pending, running, validated, failed)
- Error count displayed per run
- Click run to open detail

### View: Run Detail
- **Stats panel:** Total rows, error rows, approved count
- **Row list:** Expandable per row
  - Collapse/expand via chevron
  - Shows trade_ref + error count
  - Approve/Unapprove toggle
- **Error filter toggle:** View all rows or errors only

### View: Row Inspector (Expanded)
- List of errored cells (only if has_error=true)
- Click cell to open detail modal
- Shows original value, issues, suggested fix, corrected value

### Modal: Cell Detail
- **Column name** header with error/success icon
- **Original Value:** Raw source text (read-only)
- **Validation Issues:** List per rule
  - Rule ID, message
  - Suggested fix (if available)
- **Suggested Fix:** Inline "Accept" button (copies to corrected_value)
- **Manual Correction:** Text input + Apply button
- **Corrected Value:** Display after apply (read-only, green badge)

### Export
- Button on Run Detail (enabled only if approved rows exist)
- Downloads CSV with:
  - Headers: canonical column names (REPSTS, TRADEREF, ..., SECFININD)
  - Rows: approved rows only
  - Columns: corrected_value (if present) → original_value

---

## 8. Validation Rules Reference

**Registered rules** (api/daily_recon/validation/rules.py):

| Column(s) | Rules |
|-----------|-------|
| BUYER_ID, SELLER_ID, EXENTITYID | id_not_empty, id_format |
| BUYER_BRANCH_COUNTRY, SELLER_BRANCH_COUNTRY | country_code_valid |
| QUANTITY, PRICE, NETAMT, DERIV_NOTIONAL | numeric, positive_number |
| BUYER_DOB, SELLER_DOB, BUYDECDOB, SELLDEC_DOB | date_format, reasonable_date |
| FRMDIRIND, TRANSIND, SHRTSELIND, etc. | indicator_valid (Y/N) |

**Add custom rule:**
```python
# In api/daily_recon/validation/rules.py

class MyCustomRule:
    rule_id = "my_custom"
    
    def validate(self, value: str | None, record: dict) -> RuleResult:
        if not condition(value):
            return RuleResult(
                is_valid=False,
                message="My error message",
                suggested_fix="suggested value"
            )
        return RuleResult(is_valid=True)

# Register
rule_registry.register("COLUMN_NAME")(MyCustomRule())
```

No other code changes needed — validation engine picks it up automatically.

---

## 9. Troubleshooting

### Issue: "Cannot connect to SQL Server"

**Solution:**
1. Verify connection string in environment
2. Check ODBC driver installed: `odbcinst -j`
3. Test with `isql` (unixODBC utility): `isql -v DSN_NAME user password`
4. Verify firewall allows TCP 1433 (SQL Server default port)

### Issue: "PostgreSQL connection failed"

**Solution:**
1. Ensure PostgreSQL is running: `pg_isready -h localhost`
2. Verify DATABASE_URL in env: `postgresql://user:pass@localhost:5432/dbname`
3. Check user has CREATE TABLE permission: `psql -U postgres -c "CREATE TABLE test (id INT)"`

### Issue: "Frontend can't reach backend"

**Solution:**
1. Backend running on port 8000: `lsof -i :8000`
2. Frontend proxy configured: check `vite.config.ts` (should have `/api` proxy to `:8000`)
3. CORS enabled: check `api/main.py` CORSMiddleware

### Issue: "Celery task not running"

**Solution (Phase 6):**
1. Ensure Redis running: `redis-cli ping` (should return PONG)
2. Check Celery worker: `celery -A api.tasks.celery_app worker --loglevel=info`
3. Verify task registered: `celery -A api.tasks.celery_app inspect registered_tasks`

---

## 10. Example: End-to-End Flow

**Scenario:** Validate 5000 trade reports, approve clean rows, export.

```bash
# 1. Create run with SQL query
RUN_ID=$(curl -X POST http://localhost:8000/api/daily-recon/runs \
  -H "Content-Type: application/json" \
  -d '{
    "source_query": "SELECT * FROM trades WHERE trade_date >= CAST(GETDATE()-7 AS DATE)",
    "job_id": null
  }' | jq -r '.id')

echo "Run created: $RUN_ID"

# 2. Poll until validated (once Celery task is implemented)
for i in {1..30}; do
  STATUS=$(curl http://localhost:8000/api/daily-recon/runs/$RUN_ID | jq -r '.status')
  echo "Status: $STATUS"
  if [ "$STATUS" = "validated" ]; then break; fi
  sleep 2
done

# 3. Get run summary
curl http://localhost:8000/api/daily-recon/runs/$RUN_ID | jq '{
  row_count, error_row_count, status
}'

# 4. List errored rows
curl "http://localhost:8000/api/daily-recon/runs/$RUN_ID/rows?limit=50&offset=0&errored_only=true" \
  | jq '.data[] | {id, row_index, has_error}'

# 5. Approve some rows manually (via UI or API)
# curl -X POST http://localhost:8000/api/daily-recon/rows/{row_id}/approve

# 6. Export approved rows
curl http://localhost:8000/api/daily-recon/runs/$RUN_ID/export \
  --output daily_recon_export.csv

head daily_recon_export.csv
```

---

## 11. Next Steps (Phase 6–7)

- [ ] **SQL Source Connector:** Implement streaming extraction from SQL Server
- [ ] **Celery Task:** Wire extraction + validation + persistence pipeline
- [ ] **CSV Export:** Implement endpoint + frontend download
- [ ] **Scheduled Runs:** Add scheduling UI (reuse [`Scheduler.tsx`](../web/src/pages/Scheduler.tsx) pattern)
- [ ] **Batch Operations:** Multi-select rows for bulk approve/reject
- [ ] **Performance Tuning:** Test with 1M+ rows; verify index effectiveness

---

## 📞 Support

- **Documentation:** See [DAILY_RECON_IMPLEMENTATION.md](../DAILY_RECON_IMPLEMENTATION.md)
- **Architecture:** See [plan in copilot instructions](../.github/copilot-instructions.md)
- **Backend Errors:** Check `logs/` directory and review async stack traces
- **Frontend Errors:** Browser DevTools Console + check Vite terminal output

