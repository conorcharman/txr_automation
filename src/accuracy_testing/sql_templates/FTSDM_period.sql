-- Period Extract: Fund Trade Seller Decision Maker Validation
-- Template variables: {START_DATE}, {END_DATE} (YYYY-MM-DD format)
-- Purpose: Extract all Fund Trade Seller DM transactions for a date range
-- Replaces: FTSDM.sql
-- Version: 1.0

SELECT
    t1.REPORTREF,
    t2.CLINO,
    CASE
        WHEN t3.INDIDCODE <> '' THEN t3.INDIDCODE
        ELSE t4.ENTIDCODE
    END AS Seller_ID_Code,
    CASE
        WHEN t1.SELDECIND <> '' THEN t1.SELDECIND
        ELSE t1.SELDECENT
    END AS Seller_DM_Code,
    t2.CLNTTY,
    t2.TSATYP,
    CASE
		WHEN t2.BRNCH3 <> ''
		THEN t2.BRNCH3
		ELSE t2.PARTNR
	END AS BGETTER
FROM
    GLDATA/TXNREPESMA t1
    JOIN GLDATA/CONTCT t7 ON 
        t7.FRMCOD
        || t7.YEAR
        || t7.ACCLTR
        || t7.CONTNO
        || '1' = t1.REPORTREF 
    JOIN GLDATA/CLIENT t2 ON t7.CLINUM = t2.CLINO
    LEFT JOIN GLDATA/ESMAPTYIND t3 ON t1.REPORTREF = t3.REPORTREF
		AND t3.PARTY = 'SELLER'
    LEFT JOIN GLDATA/ESMAPTYENT t4 ON t1.REPORTREF = t4.REPORTREF
		AND t4.PARTY = 'SELLER'
WHERE
    DATE(t1.TRDDATTIM) BETWEEN '{START_DATE}' AND '{END_DATE}'
