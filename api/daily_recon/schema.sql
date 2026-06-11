-- Daily Reconciliation Schema
-- =========================
-- PostgreSQL DDL for the daily_recon domain
-- EAV model: normalized rows/cells for scalability + traceability
-- Run this via SQLAlchemy ORM (api/main.py lifespan create_all)
-- Or manually: psql -U user -d dbname -f daily_recon_schema.sql

-- ─────────────────────────────────────────────────────────────────────────
-- Extraction Run Metadata
-- ─────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS daily_recon_run (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID,
    source_query TEXT NOT NULL,
    row_count INTEGER NOT NULL DEFAULT 0,
    error_row_count INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE daily_recon_run IS 'Batch extraction run metadata';
COMMENT ON COLUMN daily_recon_run.job_id IS 'Link to Celery job in jobs table';
COMMENT ON COLUMN daily_recon_run.status IS 'pending|running|validated|exported|failed';

-- ─────────────────────────────────────────────────────────────────────────
-- Per-Source-Record Row
-- ─────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS daily_recon_row (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES daily_recon_run(id) ON DELETE CASCADE,
    row_index INTEGER NOT NULL,
    trade_ref VARCHAR(100),
    has_error BOOLEAN NOT NULL DEFAULT FALSE,
    approved BOOLEAN NOT NULL DEFAULT FALSE,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, row_index)
);

COMMENT ON TABLE daily_recon_row IS 'One row per extracted source record';
COMMENT ON COLUMN daily_recon_row.row_index IS 'Ordinal position within run (0-based)';
COMMENT ON COLUMN daily_recon_row.has_error IS 'Aggregate: true if any cell is errored';
COMMENT ON COLUMN daily_recon_row.approved IS 'User approval flag for export eligibility';

-- ─────────────────────────────────────────────────────────────────────────
-- EAV Cell Model: One Row per (SourceRow × Column)
-- ─────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS daily_recon_cell (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    row_id UUID NOT NULL REFERENCES daily_recon_row(id) ON DELETE CASCADE,
    column_name VARCHAR(64) NOT NULL,
    original_value TEXT,
    suggested_fix TEXT,
    corrected_value TEXT,
    is_errored BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (row_id, column_name)
);

COMMENT ON TABLE daily_recon_cell IS 'EAV model: one row per (source_row × column)';
COMMENT ON COLUMN daily_recon_cell.original_value IS 'Raw source text (preserved as-is for audit)';
COMMENT ON COLUMN daily_recon_cell.suggested_fix IS 'Auto-suggested correction (nullable)';
COMMENT ON COLUMN daily_recon_cell.corrected_value IS 'User-applied manual correction (nullable)';
COMMENT ON COLUMN daily_recon_cell.is_errored IS 'Per-cell error flag set by validation';

-- ─────────────────────────────────────────────────────────────────────────
-- Validation Issue Traceability
-- ─────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS daily_recon_cell_issue (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cell_id BIGINT NOT NULL REFERENCES daily_recon_cell(id) ON DELETE CASCADE,
    rule_id VARCHAR(100) NOT NULL,
    message TEXT NOT NULL,
    suggested_fix TEXT
);

COMMENT ON TABLE daily_recon_cell_issue IS 'Per-rule failure traceability (0..n per cell)';
COMMENT ON COLUMN daily_recon_cell_issue.rule_id IS 'Which validation rule failed (e.g. id_not_empty)';

-- ─────────────────────────────────────────────────────────────────────────
-- Indexes for Common Queries
-- ─────────────────────────────────────────────────────────────────────────

-- Run lookups
CREATE INDEX idx_recon_run_status
    ON daily_recon_run(status);

CREATE INDEX idx_recon_run_created_at
    ON daily_recon_run(created_at DESC);

-- Row filters
CREATE INDEX idx_recon_row_run
    ON daily_recon_row(run_id);

CREATE INDEX idx_recon_row_run_has_error
    ON daily_recon_row(run_id, has_error)
    WHERE has_error = TRUE;

CREATE INDEX idx_recon_row_run_approved
    ON daily_recon_row(run_id, approved)
    WHERE approved = TRUE;

CREATE INDEX idx_recon_row_trade_ref
    ON daily_recon_row(trade_ref);

-- Cell lookups
CREATE INDEX idx_recon_cell_row
    ON daily_recon_cell(row_id);

CREATE INDEX idx_recon_cell_row_errored
    ON daily_recon_cell(row_id, is_errored)
    WHERE is_errored = TRUE;

CREATE INDEX idx_recon_cell_column_name
    ON daily_recon_cell(column_name);

-- Issue lookups
CREATE INDEX idx_recon_cell_issue_cell
    ON daily_recon_cell_issue(cell_id);

CREATE INDEX idx_recon_cell_issue_rule_id
    ON daily_recon_cell_issue(rule_id);

-- ─────────────────────────────────────────────────────────────────────────
-- Optional: Partitioning by run_id (for 1M+ rows per run)
-- ─────────────────────────────────────────────────────────────────────────
-- After initial deployment, if needed:
-- ALTER TABLE daily_recon_cell
--   PARTITION BY HASH (run_id)
--   PARTITIONS 16;
-- This distributes cell storage across 16 partitions for better cache locality.

-- ─────────────────────────────────────────────────────────────────────────
-- Schema Verification View (optional)
-- ─────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW daily_recon_summary AS
SELECT
    r.id,
    r.status,
    COUNT(DISTINCT dr.id) AS row_count,
    COUNT(DISTINCT CASE WHEN dr.has_error THEN dr.id END) AS error_row_count,
    COUNT(DISTINCT CASE WHEN dr.approved THEN dr.id END) AS approved_row_count,
    COUNT(DISTINCT dc.id) AS cell_count,
    COUNT(DISTINCT CASE WHEN dc.is_errored THEN dc.id END) AS error_cell_count,
    r.created_at,
    r.updated_at
FROM daily_recon_run r
LEFT JOIN daily_recon_row dr ON dr.run_id = r.id
LEFT JOIN daily_recon_cell dc ON dc.row_id = dr.id
GROUP BY r.id, r.status, r.created_at, r.updated_at;

COMMENT ON VIEW daily_recon_summary IS 'Quick summary of run statistics';

