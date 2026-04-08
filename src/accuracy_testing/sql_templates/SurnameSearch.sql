SELECT 
  t1.REPORTREF                                            AS "Report Ref",
  t5.PTYFORE                                              AS "Buyer Forename",
  t5.PTYSURN                                              AS "Buyer Surname",
  t1.BUYDECFORE                                           AS "Buyer DM Forename",
  t1.BUYDECSURN                                           AS "Buyer DM Surname"
FROM 
  GLDATA / TXNREPESMA t1 
  JOIN GLDATA / CONTCT t2 ON t2.FRMCOD || t2.YEAR || t2.ACCLTR || t2.CONTNO || '1' = t1.REPORTREF 
	AND BUYSEL = 'B'
  JOIN GLDATA / ESMAPTYIND t5 ON t1.REPORTREF = t5.REPORTREF
  LEFT JOIN GLDATA / ESMAPTYIND t5b ON t1.BUYDECIND = t5b.PTYSCHCODE 
WHERE
  t1.TRDDATTIM > '2018-01-01'
  AND (
    t5.PTYSURN LIKE '%,RE,%'
    OR t1.BUYDECSURN LIKE '%,RE,%'
    OR t5b.PTYSURN LIKE '%,RE,%'
  ) 

