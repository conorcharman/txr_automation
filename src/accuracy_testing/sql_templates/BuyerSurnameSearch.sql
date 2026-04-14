SELECT 
  t1.REPORTREF                                            AS "Report Ref",
  t3.PTYFORE                                              AS "Buyer Forename",
  t3.PTYSURN                                              AS "Buyer Surname",
  t1.BUYDECFORE                                           AS "Buyer DM Forename",
  t1.BUYDECSURN                                           AS "Buyer DM Surname",
  t1.TRDDATTIM                                            AS "Trade Date Time",
  t4.REPORTABLE                                           AS "Reportable"
  
FROM 
  GLDATA / TXNREPESMA t1 
  JOIN GLDATA / ESMAPTYIND t3 ON t1.REPORTREF = t3.REPORTREF
  LEFT JOIN GLDATA / TXNRPTRD t4 on t1.REPORTREF = t4.TRADEREF

WHERE
  t1.TRDDATTIM > '2018-01-01'
  AND EXISTS (
    SELECT 1 FROM GLDATA / CONTCT t2
    WHERE t2.FRMCOD || t2.YEAR || t2.ACCLTR || t2.CONTNO || '1' = t1.REPORTREF
      AND t2.BUYSEL = 'B'
  )
  AND (
    t3.PTYSURN LIKE '%,RE,%'
    OR t1.BUYDECSURN LIKE '%,RE,%'
    OR EXISTS (
      SELECT 1 FROM GLDATA / ESMAPTYIND t3b
      WHERE t1.BUYDECIND = t3b.PTYSCHCODE
        AND t3b.PTYSURN LIKE '%,RE,%'
    )
  ) 

