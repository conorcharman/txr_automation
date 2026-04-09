SELECT
    t1.TXNREF                                            AS "Transaction Reference",
    t1.ACCOUNT_ID                                        AS "Account ID",
    ''                                                   AS "Field2",
    ''                                                   AS "Field3",
    ''                                                   AS "Field4",
    t2.PERSON_CODE                                       AS "Person Code",
    t2.ACCOUNT_TYPE                                      AS "Account Type",
    t2.BUYER_ID_CODE                                     AS "Buyer ID Code",
    t2.BUYER_ID_TYPE                                     AS "Type of Buyer ID Code",
    t2.FIRST_NAME                                        AS "First Name",
    t2.SURNAME                                           AS "Surname",
    t2.DATE_OF_BIRTH                                     AS "Date of Birth",
    t2.GENDER                                            AS "Gender",
    t2.PRIMARY_NATIONALITY                               AS "Primary Nationality",
    t2.SECONDARY_NATIONALITY                             AS "Secondary Nationality"
FROM TRADE_REPORTING_DB.TRANSACTION_TABLE t1
JOIN TRADE_REPORTING_DB.BUYER_PARTY_TABLE t2
    ON t1.TXNREF = t2.TXNREF
WHERE t1.TXNREF IN (
--<<TRANSACTION REFERENCES>>
)
ORDER BY t1.TXNREF ASC
