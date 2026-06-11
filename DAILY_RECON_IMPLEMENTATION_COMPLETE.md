# Daily Reconciliation — SQL Integration Implementation Summary

**Status:** ✅ **COMPLETE & READY FOR TESTING**

---

## What Was Implemented

### Files Created (5 new files)

1. **`api/daily_recon/source_query.py`**
   - Stores the canonical OPENQUERY SQL
   - Helper function to read ODBC connection from environment
   - Connection string read from `DAILY_RECON_SOURCE_ODBC` env var

2. **`api/services/daily_recon_source.py`**
   - `extract_rows()` function connects to SQL Server via pyodbc
   - Maps 50 columns from FIGARO_CL to canonical names
   - Returns list of dicts keyed by column name

3. **`api/tasks/daily_recon_tasks.py`**
   - Celery task: `run_daily_recon(job_id, run_id, query=None)`
   - 3-phase pipeline:
     1. Extract rows from SQL Server
     2. Validate (20+ rules, column-major)
     3. Persist to PostgreSQL (rows/cells/issues)
   - Redis pub/sub progress (matches reconciliation_tasks pattern)

4. **`web/src/pages/DailyReconciliation.tsx` (updated)**
   - "Run Query Now" button that triggers the Celery task
   - Button disabled during execution (shows "Running..." status)
   - Auto-opens run detail on success for viewing results

5. **`DAILY_RECON_SQL_INTEGRATION.md`**
   - Quick start guide
   - Troubleshooting references
   - Performance notes

### Files Modified (4 files)

| File | Change |
|------|--------|
| `api/tasks/celery_app.py` | Add `daily_recon_tasks` to `include` list (task registration) |
| `api/routers/daily_recon.py` | Wire trigger endpoint with job/task dispatch |
| `api/schemas/daily_recon.py` | Make `source_query` optional (defaults to stored query) |
| `api/requirements.txt` | Add `pyodbc>=5.1.0` |
| `api/daily_recon/validation/engine.py` | Fix dataclass field default bug |
| `web/src/types/index.ts` | Make `DailyReconTriggerRequest.sourceQuery` optional |

---

## Setup Instructions

### 1. Add Environment Variable

**Add to `.env` (project root):**

```dotenv
# SQL Server ODBC connection (hosts FIGARO_CL linked server)
DAILY_RECON_SOURCE_ODBC=DRIVER={ODBC Driver 17 for SQL Server};SERVER=your-server;DATABASE=your-db;UID=user;PWD=password
```

Or for Trusted Connection (Windows auth):
```dotenv
DAILY_RECON_SOURCE_ODBC=DRIVER={ODBC Driver 17 for SQL Server};SERVER=your-server;DATABASE=your-db;Trusted_Connection=yes
```

### 2. Install ODBC Driver

**Windows:** Download [ODBC Driver 17](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)

**Linux:**
```bash
sudo apt install unixodbc-dev msodbcsql17
```

**macOS:**
```bash
brew install unixodbc msodbcsql17
```

### 3. Install Dependencies

```bash
conda activate txr_automation
pip install -r api/requirements.txt
```

### 4. Start Services

**Terminal 1 — FastAPI:**
```bash
uvicorn api.main:app --reload
```

**Terminal 2 — Celery Worker:**
```bash
celery -A api.tasks.celery_app worker --loglevel=info
```

**Terminal 3 — Redis (if not service):**
```bash
redis-server
```

**Terminal 4 — Frontend:**
```bash
cd web && npm run dev
```

### 5. Test

1. Open http://localhost:5173/daily-recon
2. Click **"Run Query Now"** button
3. Watch extraction/validation/persistence (live progress via Redis)
4. Review errors, corrections, approve rows
5. Export as CSV (future phase)

---

## Data Flow (Manual Trigger)

```
User clicks "Run Query Now"
    ↓ (disabled while running)
POST /api/daily-recon/runs {}
    ↓
Backend:
  1. Create Job (status:pending)
  2. Create ReconRun (status:pending)
  3. Dispatch run_daily_recon.delay(job_id, run_id, query)
    ↓ (return immediately, task runs in background)
Frontend polls GET /api/daily-recon/runs/{id}
    ↓ (every 5 seconds)
Celery Worker processes task:
  1. Update status → running, publish progress 5%
  2. Connect to SQL Server, execute OPENQUERY
  3. Map columns, validate (20+ rules), publish progress 50%
  4. Persist rows/cells/issues, publish progress 100%
  5. Update run status → validated
  6. Update job status → success
    ↓
UI opens run detail automatically
  - Shows row count, error count, stats
  - Expandable rows with cell errors
  - Click cell to inspect (original, issues, suggested, corrected)
  - Accept suggestion or manual correction
  - Approve/unapprove rows
  - Export approved as CSV
```

---

## Key Features

✅ **Manual trigger only** — No automatic scheduling  
✅ **No auth required** — POC confidence test  
✅ **Live progress** — Redis pub/sub updates to UI  
✅ **Column-major validation** — Efficient batch processing  
✅ **Per-rule traceability** — Know exactly which rule failed  
✅ **Non-destructive corrections** — Never auto-applies fixes  
✅ **Task isolation** — Celery worker handles long-running extraction  

---

## Query Customization

Default query runs 2-month window (past 2 months) on WAIT status.

To override for single run:

```bash
curl -X POST http://localhost:8000/api/daily-recon/runs \
  -H "Content-Type: application/json" \
  -d '{
    "sourceQuery": "SELECT * FROM openquery(FIGARO_CL, \"SELECT ... LIMIT 10\")"
  }'
```

To permanently change, edit `api/daily_recon/source_query.py::DAILY_RECON_QUERY`.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "DAILY_RECON_SOURCE_ODBC is not set" | Add to `.env`, restart worker |
| "ODBC Driver not found" | Install driver (see Setup), restart |
| "Connection refused" | Verify connection string, test with `isql` |
| "Celery task not running" | Check Redis: `redis-cli ping` → should return PONG |
| "Button disabled forever" | Check Celery worker logs for errors |

---

## Next Phase

Once POC is stable:

1. **Scheduled runs** — Add Celery Beat entry to autorun daily
2. **CSV export** — Implement export endpoint (framework ready)
3. **Batch operations** — Multi-select rows for bulk approve
4. **Revalidation** — Re-run validation after corrections
5. **Rule customization** — Add/remove rules per business needs

---

## Files Ready to Use

```
✅ api/daily_recon/source_query.py
✅ api/services/daily_recon_source.py
✅ api/tasks/daily_recon_tasks.py
✅ api/routers/daily_recon.py (updated)
✅ api/tasks/celery_app.py (updated)
✅ api/schemas/daily_recon.py (updated)
✅ api/daily_recon/validation/engine.py (fixed)
✅ api/requirements.txt (updated)
✅ web/src/pages/DailyReconciliation.tsx (updated)
✅ web/src/types/index.ts (updated)
✅ DAILY_RECON_SQL_INTEGRATION.md (quick start)
```

---

## Key Implementation Details

- **Stored Query:** `FIGARO_CL` linked server OPENQUERY (server-side execution)
- **Column Mapping:** 50 canonical columns from `COLUMNS` registry
- **Validation:** 20+ rules (ID format, country, numeric, date, indicator)
- **Persistence:** EAV model (row → cells → issues) for scalability
- **UI:**row expansion, cell modal inspection, suggestions/corrections, approval
- **Export:** (future) corrected > original precedence, approved rows only

---

**All pieces are in place. Ready for manual POC testing.**

