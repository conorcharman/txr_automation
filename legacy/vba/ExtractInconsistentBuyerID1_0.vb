Sub ExtractInconsistentBuyerID1_0()
    Dim ws As Worksheet
    Dim outputPath As String
    Dim sqlTemplate As String
    Dim sqlBody As String
    Dim lRow As Long
    Dim transactionRef As String
    Dim currentExtract As String
    Dim previousExtract As String
    Dim extractNumber As Long
    Dim transactionCount As Long

    Set ws = ThisWorkbook.Sheets("Extract Generator")
    outputPath = ws.Range("B1").Value

    If Right(outputPath, 1) <> "\" Then
        outputPath = "F:\Transaction Reporting\Kaizen Reporting\Accuracy Testing\Automated Accuracy Testing\Inconsistent Identification Code - Buyer - 7_66\Extracts\sql\"
    End If

    ' --- Assign Extract Numbers (was in AssignExtractNumbers sub) ---
    lRow = 2
    Do While ws.Cells(lRow, 1).Value <> ""
        ws.Cells(lRow, 2).Value = ""
        lRow = lRow + 1
    Loop

    lRow = 2
    extractNumber = 1
    transactionCount = 0

    Do While ws.Cells(lRow, 1).Value <> ""
        transactionRef = Trim(ws.Cells(lRow, 1).Value)

        If transactionRef <> "" Then
            If transactionCount = 900 Then
                extractNumber = extractNumber + 1
                transactionCount = 0
            End If
            
            transactionCount = transactionCount + 1
            ws.Cells(lRow, 2).Value = extractNumber
        End If

        lRow = lRow + 1
    Loop

    Dim sqlPart1 As String, sqlPart2 As String, sqlPart3 As String, sqlPart4 As String

    sqlPart1 = "WITH LinkCodes AS (" & vbCrLf
    sqlPart1 = sqlPart1 & "  SELECT " & vbCrLf
    sqlPart1 = sqlPart1 & "    t4.CLINUM, " & vbCrLf
    sqlPart1 = sqlPart1 & "    MAX(" & vbCrLf
    sqlPart1 = sqlPart1 & "      CASE WHEN t4.RLNKTP = 'BEN' THEN t4.ROTCOD END" & vbCrLf
    sqlPart1 = sqlPart1 & "    ) AS BEN_LINK, " & vbCrLf
    sqlPart1 = sqlPart1 & "    MAX(" & vbCrLf
    sqlPart1 = sqlPart1 & "      CASE WHEN t4.RLNKTP = 'OWN' THEN t4.ROTCOD END" & vbCrLf
    sqlPart1 = sqlPart1 & "    ) AS OWN_LINK" & vbCrLf
    sqlPart1 = sqlPart1 & "  FROM " & vbCrLf
    sqlPart1 = sqlPart1 & "    GLDATA / ROTCLI t4 " & vbCrLf
    sqlPart1 = sqlPart1 & "  GROUP BY " & vbCrLf
    sqlPart1 = sqlPart1 & "    t4.CLINUM" & vbCrLf
    sqlPart1 = sqlPart1 & ")" & vbCrLf

    sqlPart2 = "  SELECT " & vbCrLf
    sqlPart2 = sqlPart2 & "    t1.REPORTREF, " & vbCrLf
    sqlPart2 = sqlPart2 & "    t2.CLINUM, " & vbCrLf
    sqlPart2 = sqlPart2 & "    lc.BEN_LINK, " & vbCrLf
    sqlPart2 = sqlPart2 & "    lc.OWN_LINK, " & vbCrLf
    sqlPart2 = sqlPart2 & "    t5.UECODE, " & vbCrLf
    sqlPart2 = sqlPart2 & "    t6b.UETYPE," & vbCrLf
    sqlPart2 = sqlPart2 & "    CASE WHEN t5.INDIDCODE <> '' THEN t5.INDIDCODE ELSE t6.UENINO END AS BUYER_ID_CODE, " & vbCrLf
    sqlPart2 = sqlPart2 & "    CASE WHEN t5.INDIDCODE = '' " & vbCrLf
    sqlPart2 = sqlPart2 & "    OR t5.INDIDCODE IS NULL THEN 'NINO' ELSE t5.PTYSCHCODE END AS BUYER_ID_TYPE, " & vbCrLf
    sqlPart2 = sqlPart2 & "    t5.PTYFORE, " & vbCrLf
    sqlPart2 = sqlPart2 & "    t5.PTYSURN, " & vbCrLf
    sqlPart2 = sqlPart2 & "    CASE WHEN t5.PTYDOB IS NULL " & vbCrLf
    sqlPart2 = sqlPart2 & "    OR t5.PTYDOB <= DATE('1941-01-01') THEN NULL ELSE t5.PTYDOB END AS PTYDOB, " & vbCrLf
    sqlPart2 = sqlPart2 & "    CASE " & vbCrLf
    sqlPart2 = sqlPart2 & "    WHEN UPPER(" & vbCrLf
    sqlPart2 = sqlPart2 & "      SUBSTR(" & vbCrLf
    sqlPart2 = sqlPart2 & "        t3.CLNAME, " & vbCrLf
    sqlPart2 = sqlPart2 & "        1, " & vbCrLf
    sqlPart2 = sqlPart2 & "        LOCATE(' ', t3.CLNAME) -1" & vbCrLf
    sqlPart2 = sqlPart2 & "      )" & vbCrLf
    sqlPart2 = sqlPart2 & "    ) IN ('MR', 'MASTER') THEN 'M' WHEN UPPER(" & vbCrLf
    sqlPart2 = sqlPart2 & "      SUBSTR(" & vbCrLf
    sqlPart2 = sqlPart2 & "        t3.CLNAME, " & vbCrLf
    sqlPart2 = sqlPart2 & "        1, " & vbCrLf
    sqlPart2 = sqlPart2 & "        LOCATE(' ', t3.CLNAME) -1" & vbCrLf
    sqlPart2 = sqlPart2 & "      )" & vbCrLf
    sqlPart2 = sqlPart2 & "    ) IN ('MRS', 'MISS', 'MS') THEN 'F' WHEN UPPER(" & vbCrLf
    sqlPart2 = sqlPart2 & "      SUBSTR(" & vbCrLf
    sqlPart2 = sqlPart2 & "        t3.CLNAME, " & vbCrLf
    sqlPart2 = sqlPart2 & "        1, " & vbCrLf
    sqlPart2 = sqlPart2 & "        LOCATE(' ', t3.CLNAME) -1" & vbCrLf
    sqlPart2 = sqlPart2 & "      )" & vbCrLf
    sqlPart2 = sqlPart2 & "    ) IN ('DR', 'PROF') THEN 'N/A' ELSE 'N/A' END AS CLIENT_GENDER, " & vbCrLf
    sqlPart2 = sqlPart2 & "    t6.UENAT, " & vbCrLf
    sqlPart2 = sqlPart2 & "    t7.NATION, " & vbCrLf
    sqlPart2 = sqlPart2 & "    t1.TRDDATTIM" & vbCrLf

    sqlPart3 = "  FROM " & vbCrLf
    sqlPart3 = sqlPart3 & "    GLDATA / TXNREPESMA t1 " & vbCrLf
    sqlPart3 = sqlPart3 & "    JOIN GLDATA / CONTCT t2 ON t2.FRMCOD || t2.YEAR || t2.ACCLTR || t2.CONTNO || '1' = t1.REPORTREF " & vbCrLf
    sqlPart3 = sqlPart3 & "    AND BUYSEL = 'B'" & vbCrLf
    sqlPart3 = sqlPart3 & "    JOIN GLDATA / CLIENT t3 ON t2.CLINUM = t3.CLINO " & vbCrLf
    sqlPart3 = sqlPart3 & "    JOIN GLDATA / ESMAPTYIND t5 ON t1.REPORTREF = t5.REPORTREF" & vbCrLf
    sqlPart3 = sqlPart3 & "    LEFT JOIN GLDATA / PERSON t6 ON t5.UECODE = t6.UECODE " & vbCrLf
    sqlPart3 = sqlPart3 & "    LEFT JOIN GLDATA / PERSON t6b	ON SUBSTR(t2.CLINUM, 1, LENGTH(t2.CLINUM) - 1) = t6b.UECODE" & vbCrLf
    sqlPart3 = sqlPart3 & "    LEFT JOIN GLDATA / PERSONNAT t7 ON t3.UECODE = t7.UECODE " & vbCrLf
    sqlPart3 = sqlPart3 & "    LEFT JOIN GLDATA / ESMAPTYIND t5b ON t1.BUYDECIND = t5b.PTYSCHCODE " & vbCrLf
    sqlPart3 = sqlPart3 & "    LEFT JOIN LinkCodes lc ON t2.CLINUM = lc.CLINUM " & vbCrLf

    sqlPart4 = "  WHERE " & vbCrLf
    sqlPart4 = sqlPart4 & "    t1.REPORTREF IN (" & vbCrLf
    sqlPart4 = sqlPart4 & "      --<<TRANSACTION REFERENCES>>" & vbCrLf
    sqlPart4 = sqlPart4 & "      )"

    sqlTemplate = sqlPart1 & sqlPart2 & sqlPart3 & sqlPart4

    ' Process the Excel data and create SQL files
    lRow = 2
    previousExtract = ""
    sqlBody = ""

    Do While ws.Cells(lRow, 1).Value <> "" Or ws.Cells(lRow, 2).Value <> ""
        transactionRef = Trim(ws.Cells(lRow, 1).Value)
        currentExtract = Trim(ws.Cells(lRow, 2).Value)

        If transactionRef = "" Or currentExtract = "" Then
            lRow = lRow + 1
            GoTo ContinueLoop
        End If

        If currentExtract <> previousExtract And previousExtract <> "" Then
            If Right(sqlBody, 2) = "," & vbCrLf Then
                sqlBody = Left(sqlBody, Len(sqlBody) - 2)
            End If
            WriteSQLToFile outputPath, previousExtract, sqlTemplate, sqlBody
            sqlBody = ""
        End If

        If sqlBody = "" Then
            sqlBody = "'" & transactionRef & "'"
        Else
            sqlBody = sqlBody & "," & vbCrLf & "'" & transactionRef & "'"
        End If

        previousExtract = currentExtract

ContinueLoop:
        lRow = lRow + 1
    Loop

    If sqlBody <> "" Then
        If Right(sqlBody, 2) = "," & vbCrLf Then
            sqlBody = Left(sqlBody, Len(sqlBody) - 2)
        End If
        WriteSQLToFile outputPath, previousExtract, sqlTemplate, sqlBody
    End If

    MsgBox "Extract numbers assigned and SQL text files created successfully.", vbInformation
End Sub

Private Sub WriteSQLToFile(strFilePath As String, fileName As String, template As String, refs As String)
    Dim fullPath As String
    Dim iFileNum As Integer
    Dim finalSQL As String

    finalSQL = Replace(template, "--<<TRANSACTION REFERENCES>>", refs)
    fullPath = strFilePath & "Extract" & fileName & ".sql"

    iFileNum = FreeFile
    Open fullPath For Output As iFileNum
    Print #iFileNum, finalSQL;
    Close iFileNum
End Sub
