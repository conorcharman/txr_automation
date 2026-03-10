# FIRDS Reportability Guide

## Overview

The FIRDS reportability module automates the determination of whether a
financial instrument is subject to MiFIR transaction reporting on a given
trade date.

The FCA publishes instrument reference data via the Financial Instruments
Reference Data System (FIRDS).  These files are the authoritative source for
determining whether an instrument was admitted to trading on a regulated venue
at the time of a trade.

This guide covers:

- How the local cache works
- First-time setup
- Regular scheduled refresh
- Checking a single instrument
- Annotating an entire incident file with reportability results
- Python API integration

---

## How It Works

The FCA FIRDS API does not support per-instrument queries.  Instead, it
publishes bulk XML files that must be downloaded and ingested into a local
SQLite cache.  The cache stores admission dates, termination dates, and
cancellation flags per ISIN/venue pair.

Reportability is then determined by querying the cache:

- **Reportable** if `admission_date ≤ trade_date` AND
  (`termination_date` is absent OR `termination_date > trade_date`) AND
  the record is not cancelled.

File types:

| File type | Published | Purpose |
|-----------|-----------|---------|
| `FULINS` | Every Saturday by 09:00 UTC | Full instrument reference data |
| `DLTINS` | Monday–Friday by 09:00 UTC | Daily delta changes (admissions, terminations, cancellations) |
| `FULCAN` | Every Saturday by 09:00 UTC | Cancellation records |

---

## Setup

### 1. Install the package

```bash
conda activate txr_automation
pip install -e .
```

### 2. Create a local config file

```bash
cp config/templates/firds_config.yaml config/local/firds_config.yaml
```

Edit `config/local/firds_config.yaml` to set the database path:

```yaml
database:
  path: data/firds_cache.db
```

The default database path is `data/firds_cache.db` relative to the repo root.
You do not need the config file if you use the default paths.

---

## Regular Scheduled Refresh

For live trade checking, keep the cache current with a scheduled refresh.

### Weekly full refresh (Saturday)

Run this after the FCA FIRDS full files are published (typically by 10:00 UTC):

```bash
firds-refresh --type full
```

This truncates and rebuilds the instruments table from the latest FULINS and
FULCAN files.  It takes approximately 5–15 minutes depending on internet speed
and file sizes.

### Daily delta refresh (Monday–Friday)

Run this each morning to apply the previous day's changes:

```bash
firds-refresh --type delta
```

### Targeting a specific date

If a scheduled run was missed:

```bash
firds-refresh --type full --date 2026-03-07
firds-refresh --type delta --since 2026-03-08
```

All refresh commands are idempotent — files already in the sync log are
skipped automatically.

---

## Checking a Single Instrument

```bash
firds-check --isin GB00B3RBWM25 --mic XLON --date 2026-03-10
```

Without a specific venue (checks across all venues):

```bash
firds-check --isin GB00B3RBWM25 --date 2026-03-10
```

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Reportable |
| `1` | Error (database not found, invalid input) |
| `2` | Not reportable |

---

## Batch Check (Generic Trade CSV)

Prepare a CSV with columns `isin`, `trade_date`, and optionally `mic`:

```csv
isin,trade_date,mic
GB00B3RBWM25,2026-03-10,XLON
DE000CM7VX13,2026-03-10,XFRA
```

Then run:

```bash
firds-check --input trades.csv --output results.csv
```

The output CSV contains all original columns plus three appended columns:

| Column | Values | Description |
|--------|--------|-------------|
| `is_reportable` | `Y` / `N` | Whether the instrument is reportable |
| `reportability_reason` | See below | Explanation of the result |
| `matched_mics` | Pipe-delimited MIC list | Venues where the instrument is active (Y results only) |

### Reason codes

| Code | Meaning |
|------|---------|
| `ACTIVE` | Admitted and not terminated or cancelled at the trade date |
| `NOT_IN_FIRDS` | ISIN (or ISIN + MIC combination) not found in the cache |
| `ADMISSION_AFTER_TRADE` | Instrument was not yet admitted at the trade date |
| `TERMINATED_BEFORE_TRADE` | Instrument was terminated on or before the trade date |
| `CANCELLED` | Record has been cancelled |

---

## Historic Backfill from an Incident File

For reviewing a historic incident file, the cache must contain FIRDS data
covering the period of the trades.  The `firds-backfill` command handles this
automatically:

1. Reads the incident CSV and extracts all trade dates.
2. Identifies the FULINS baseline needed (the Saturday on or before the
   earliest trade date).
3. Downloads the FULINS file for that date and all DLTINS delta files through
   the latest trade date — skipping any files already in the cache.
4. Annotates each trade record with a reportability result and writes the
   output CSV.

### Input formats

The command accepts two input formats, auto-detected from column headers.

**FCA incident file** (Consolidated Errors/Queries Data):

| CSV column | Used for |
|------------|----------|
| `Instrument identification code` | ISIN |
| `Venue` | MIC (trading venue) |
| `Trading date time_Date` | Trade date |

Blank rows (rows with no ISIN or trade date) are skipped automatically.

**Generic trade CSV**:

Requires columns `isin` and `trade_date` (and optionally `mic`).

### Usage

```bash
firds-backfill --input incidents.csv --output results.csv
```

With a specific database location:

```bash
firds-backfill --input incidents.csv --output results.csv --db /data/firds_cache.db
```

Force generic format (if auto-detection is incorrect):

```bash
firds-backfill --input trades.csv --format generic --output results.csv
```

Skip the FIRDS download if the cache is already known to cover the period:

```bash
firds-backfill --input incidents.csv --output results.csv --skip-refresh
```

### Output

All original columns from the input file are preserved in the output.  Three
additional columns are appended:

| Column | Values | Description |
|--------|--------|-------------|
| `is_reportable` | `Y` / `N` | Whether the instrument is reportable at the trade date |
| `reportability_reason` | See reason codes above | Explanation of the result |
| `matched_mics` | Pipe-delimited | Active venues for the instrument at the trade date |

### Example: incident file covering Q3 2025

For an incident file covering trades from 2025-07-01 to 2025-09-30, the
backfill would:

1. Load FULINS published on **2025-06-28** (the Saturday before 2025-07-01)
2. Load DLTINS for each day **2025-06-29 → 2025-09-30**

The cache then reflects the instrument reference data state for any date in
that range, enabling accurate point-in-time reportability checks.

```bash
firds-backfill \
    --input "incidents_Q3_2025.csv" \
    --output "incidents_Q3_2025_reportability.csv"
```

Console output:

```text
[1/3] Reading trade records from 'incidents_Q3_2025.csv' …
  4,823 trade records loaded.
  Date range:    2025-07-01  →  2025-09-30
  Unique ISINs:  312

[2/3] Refreshing FIRDS cache …
  Loading FULINS baseline for 2025-06-28 …
  FULINS: 3 file(s) processed, 0 skipped, 2,847,391 records.
  Loading DLTINS from 2025-06-29 to 2025-09-30 …
  DLTINS: 66 file(s) processed, 0 skipped, 184,203 records.

[3/3] Checking reportability …

  Results written to: incidents_Q3_2025_reportability.csv
  Reportable:      4,501
  Not reportable:    322
  Total:           4,823
```

---

## Python API

Use the module directly in your own scripts.

### Single instrument check

```python
from firds import FirdsReportabilityChecker
from datetime import date

checker = FirdsReportabilityChecker(db_path="data/firds_cache.db")
result = checker.is_reportable("GB00B3RBWM25", date(2026, 3, 10), mic="XLON")

print(result.is_reportable)   # True
print(result.reason)          # "ACTIVE"
print(result.matched_mics)    # ["XLON"]
```

### Bulk check

```python
from firds import FirdsReportabilityChecker
from datetime import date

checker = FirdsReportabilityChecker(db_path="data/firds_cache.db")

checks = [
    {"isin": "GB00B3RBWM25", "trade_date": date(2026, 3, 10), "mic": "XLON"},
    {"isin": "DE000CM7VX13", "trade_date": date(2026, 3, 10), "mic": "XFRA"},
    {"isin": "FR0000131104", "trade_date": date(2026, 3, 10)},
]

results = checker.bulk_check(checks)
for r in results:
    print(r.isin, "→", "Y" if r.is_reportable else "N", r.reason)
```

### Programmatic backfill

```python
from datetime import date
from firds import FirdsCacheManager, FirdsApiClient
from firds.refresher import FirdsRefresher, _most_recent_saturday

cache = FirdsCacheManager("data/firds_cache.db")
cache.initialise_db()

refresher = FirdsRefresher(cache=cache, api_client=FirdsApiClient())
refresher.run_full_refresh(target_date=_most_recent_saturday(date(2025, 7, 1)))
refresher.run_delta_refresh(since_date=date(2025, 6, 29), to_date=date(2025, 9, 30))
```

---

## Database Location

The default database is created at `data/firds_cache.db` relative to the repo
root.  All CLI tools accept `--db PATH` to override this.

The database is a single SQLite file using WAL mode.  It can be safely read
by multiple concurrent readers and written by one writer at a time.

---

## Troubleshooting

### "FIRDS cache database not found"

The cache has not been built yet.  Run a full refresh first:

```bash
firds-refresh --type full
```

### "No FULINS files found for date"

The FCA may not have published files for the requested date yet, or the date
was not a Saturday.  Check `https://api.data.fca.org.uk/fca_data_firds_files`
for available files, or run without `--date` to use the most recent Saturday.

### "NOT_IN_FIRDS" for an instrument you expect to be reportable

- The cache may not yet contain data for the trade date.  Run a backfill for
  the relevant period.
- The ISIN may be an OTC instrument not admitted to a trading venue (not in
  FIRDS by design).
- The MIC you specified may not be the venue on which the instrument is
  admitted — try omitting `--mic` to check all venues.

### Large initial download

The FULINS full files are typically 2–4 GB compressed.  On a slow connection
this may take 30+ minutes.  The download is resumable by re-running the
command; already-processed files are skipped.
