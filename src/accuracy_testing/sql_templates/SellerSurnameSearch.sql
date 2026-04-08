SELECT 
  t1.REPORTREF                                            AS "Report Ref",
  t5.PTYFORE                                              AS "Seller Forename",
  t5.PTYSURN                                              AS "Seller Surname",
  t1.SELDECFORE                                           AS "Seller DM Forename",
  t1.SELDECSURN                                           AS "Seller DM Surname",
  t1.TRDDATTIM                                            AS "Trade Date Time"
  
FROM 
  GLDATA / TXNREPESMA t1 
  JOIN GLDATA / CONTCT t2 ON t2.FRMCOD || t2.YEAR || t2.ACCLTR || t2.CONTNO || '1' = t1.REPORTREF 
	AND BUYSEL = 'S'
  JOIN GLDATA / ESMAPTYIND t5 ON t1.REPORTREF = t5.REPORTREF
  LEFT JOIN GLDATA / ESMAPTYIND t5b ON t1.SELDECIND = t5b.PTYSCHCODE 
WHERE
  t1.TRDDATTIM > '2018-01-01'
  AND (
    t5.PTYSURN LIKE '%,RE,%'
    OR t1.SELDECSURN LIKE '%,RE,%'
    OR t5b.PTYSURN LIKE '%,RE,%'
  ) 

