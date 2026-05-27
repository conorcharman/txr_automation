-- Period Extract: Incorrect Net Amount Validation
-- Template variables: {START_DATE}, {END_DATE} (YYYY-MM-DD format)
-- Purpose: Extract all Incorrect Net Amount transactions for a date range
-- Replaces: InconsistentNetAmount.sql
-- Version: 1.0

SELECT
    t1.REPORTREF,
    t1.NETAMT,
    t2.CLICSD,
    t2.INTRST,
    t2.ASSET,
    t3.INSTCLASS
FROM
    GLDATA/TXNREPESMA t1
JOIN GLDATA/CONTCT t2 ON t2.FRMCOD || t2.YEAR || t2.ACCLTR || t2.CONTNO || '1' = t1.REPORTREF
LEFT JOIN GLDATA/SECFIG t3 ON t3.SEDOL = t2.ASSET
WHERE
    DATE(t1.TRDDATTIM) BETWEEN '{START_DATE}' AND '{END_DATE}'
