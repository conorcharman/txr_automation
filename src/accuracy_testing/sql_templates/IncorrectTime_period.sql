-- Period Extract: Incorrect Time Validation
-- Template variables: {START_DATE}, {END_DATE} (YYYY-MM-DD format)
-- Purpose: Extract all Incorrect Time transactions for a date range
-- Replaces: IncorrectTime.sql
-- Version: 1.0
--
-- Design note: The reference-list counterpart uses a target_keys CTE with a
-- VALUES block.  This period version replaces that CTE with date_filtered,
-- which selects child refs from CRSNET whose TXNREPESMA trade date falls
-- within the requested range.  All subsequent CTEs and the final SELECT are
-- identical to the original template.

WITH date_filtered AS (
    SELECT DISTINCT
        c.GRFIRM AS k_firm,
        c.GRYEAR AS k_year,
        c.GRACCL AS k_accl,
        c.GRCONT AS k_cont,
        c.GRSUFF AS k_suff
    FROM CRSNET c
    INNER JOIN GLDATA/TXNREPESMA t
        ON  c.GRFIRM || c.GRYEAR || c.GRACCL || c.GRCONT || c.GRSUFF = t.REPORTREF
    WHERE c.STATUS = 'A'
      AND DATE(t.TRDDATTIM) BETWEEN '{START_DATE}' AND '{END_DATE}'
),
target_parent AS (
    SELECT
        n.NTFIRM,
        n.NTYEAR,
        n.NTACCL,
        n.NTCONT,
        n.NTSUFF
    FROM CRSNET n
    INNER JOIN date_filtered k
        ON  n.GRFIRM = k.k_firm
        AND n.GRYEAR = k.k_year
        AND n.GRACCL = k.k_accl
        AND n.GRCONT = k.k_cont
        AND n.GRSUFF = k.k_suff
    WHERE n.STATUS = 'A'
),
children AS (
    SELECT
        c.GRFIRM,
        c.GRYEAR,
        c.GRACCL,
        c.GRCONT,
        c.GRSUFF,
        c.NTFIRM,
        c.NTYEAR,
        c.NTACCL,
        c.NTCONT,
        c.NTSUFF,
        c.GRFIRM||c.GRYEAR||c.GRACCL||c.GRCONT||c.GRSUFF AS child_ref,
        c.NTFIRM||c.NTYEAR||c.NTACCL||c.NTCONT||c.NTSUFF  AS parent_ref
    FROM CRSNET c
    INNER JOIN target_parent tp
        ON  c.NTFIRM = tp.NTFIRM
        AND c.NTYEAR = tp.NTYEAR
        AND c.NTACCL = tp.NTACCL
        AND c.NTCONT = tp.NTCONT
        AND c.NTSUFF = tp.NTSUFF
    WHERE c.STATUS = 'A'
)
SELECT
    c.child_ref,
    t2.TRDDATTIM  AS child_datetime,
    c.parent_ref,
    t3.TRDDATTIM  AS parent_datetime
FROM children c
LEFT JOIN GLDATA/TXNREPESMA t2
    ON c.child_ref = t2.REPORTREF
LEFT JOIN GLDATA/TXNREPESMA t3
    ON SUBSTR(c.parent_ref, 1, 12) = t3.REPORTREF
WHERE SUBSTR(c.child_ref, 1, 2) <> 'CA'
ORDER BY
    t2.TRDDATTIM ASC
