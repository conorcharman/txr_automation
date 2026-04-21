WITH target_keys (k_firm, k_year, k_accl, k_cont, k_suff) AS (
    VALUES
{VALUES}
),
target_parent AS (
    SELECT
        n.NTFIRM,
        n.NTYEAR,
        n.NTACCL,
        n.NTCONT,
        n.NTSUFF
    FROM CRSNET n
    INNER JOIN target_keys k
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
    c_stk.F11    AS child_f11,
    c.parent_ref,
    p_stk.F11    AS parent_f11,
    t1.TRDDATTIM AS trade_date_time
FROM children c
LEFT JOIN GLDATA/CONTCT c_ct
    ON  c_ct.FRMCOD = c.GRFIRM
    AND c_ct.YEAR   = c.GRYEAR
    AND c_ct.ACCLTR = c.GRACCL
    AND c_ct.CONTNO = c.GRCONT
LEFT JOIN GLDATA/STOCK c_stk
    ON c_stk.SEDOL = c_ct.ASSET
LEFT JOIN GLDATA/CONTCT p_ct
    ON  p_ct.FRMCOD = c.NTFIRM
    AND p_ct.YEAR   = c.NTYEAR
    AND p_ct.ACCLTR = c.NTACCL
    AND p_ct.CONTNO = c.NTCONT
LEFT JOIN GLDATA/STOCK p_stk
    ON p_stk.SEDOL = p_ct.ASSET
LEFT JOIN GLDATA/TXNREPESMA t1
    ON c.child_ref = t1.REPORTREF
WHERE SUBSTR(c.child_ref, 1, 2) <> 'CA'
ORDER BY
    t1.TRDDATTIM ASC
