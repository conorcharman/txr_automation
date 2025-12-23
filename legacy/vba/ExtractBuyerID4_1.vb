Sub ExtractBuyerID4_1()
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
        outputPath = "H:\Transaction Reporting\Automated Accuracy Testing\Buyer Identification Code - 7_35, 7_37, 7_39\Extracts\SQL\"
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
    sqlPart1 = sqlPart1 & "                SELECT " & vbCrLf
    sqlPart1 = sqlPart1 & "                                 t4.CLINUM," & vbCrLf
    sqlPart1 = sqlPart1 & "                                MAX(CASE WHEN t4.RLNKTP = 'BEN' THEN t4.ROTCOD END) AS BEN_LINK," & vbCrLf
    sqlPart1 = sqlPart1 & "                                MAX(CASE WHEN t4.RLNKTP = 'OWN' THEN t4.ROTCOD END) AS OWN_LINK," & vbCrLf
    sqlPart1 = sqlPart1 & "                                MAX(CASE WHEN t4.RLNKTP = 'TPA' THEN t4.ROTCOD END) AS TPA_LINK" & vbCrLf
    sqlPart1 = sqlPart1 & "                FROM " & vbCrLf
    sqlPart1 = sqlPart1 & "                                 GLDATA/ROTCLI t4" & vbCrLf
    sqlPart1 = sqlPart1 & "                GROUP BY " & vbCrLf
    sqlPart1 = sqlPart1 & "                                 t4.CLINUM" & vbCrLf
    sqlPart1 = sqlPart1 & "                )" & vbCrLf

    sqlPart2 = "                SELECT" & vbCrLf
    sqlPart2 = sqlPart2 & "                t1.REPORTREF," & vbCrLf
    sqlPart2 = sqlPart2 & "                t2.CLINUM," & vbCrLf
    sqlPart2 = sqlPart2 & "                lc.BEN_LINK," & vbCrLf
    sqlPart2 = sqlPart2 & "                lc.OWN_LINK," & vbCrLf
    sqlPart2 = sqlPart2 & "                lc.TPA_LINK," & vbCrLf
    sqlPart2 = sqlPart2 & "                t5.UECODE," & vbCrLf
	sqlPart2 = sqlPart2 & "                t6b.UETYPE," & vbCrLf
    sqlPart2 = sqlPart2 & "                CASE" & vbCrLf
    sqlPart2 = sqlPart2 & "                                WHEN t5.INDIDCODE <> '' THEN t5.INDIDCODE" & vbCrLf
    sqlPart2 = sqlPart2 & "                                ELSE t6.UENINO" & vbCrLf
    sqlPart2 = sqlPart2 & "                END AS BUYER_ID_CODE," & vbCrLf
    sqlPart2 = sqlPart2 & "                CASE" & vbCrLf
    sqlPart2 = sqlPart2 & "                                WHEN t5.INDIDCODE = '' OR t5.INDIDCODE IS NULL THEN 'NINO'" & vbCrLf
    sqlPart2 = sqlPart2 & "                                ELSE t5.PTYSCHCODE" & vbCrLf
    sqlPart2 = sqlPart2 & "                END AS BUYER_ID_TYPE," & vbCrLf
    sqlPart2 = sqlPart2 & "                t5.PTYFORE," & vbCrLf
    sqlPart2 = sqlPart2 & "                t5.PTYSURN," & vbCrLf
    sqlPart2 = sqlPart2 & "CASE " & vbCrLf
    sqlPart2 = sqlPart2 & "    WHEN t5.PTYDOB IS NULL OR t5.PTYDOB <= DATE('1941-01-01') THEN NULL" & vbCrLf
    sqlPart2 = sqlPart2 & "    ELSE t5.PTYDOB" & vbCrLf
    sqlPart2 = sqlPart2 & "END AS PTYDOB," & vbCrLf
    sqlPart2 = sqlPart2 & "                CASE" & vbCrLf
    sqlPart2 = sqlPart2 & "                                WHEN UPPER(SUBSTR(t3.CLNAME, 1, LOCATE(' ', t3.CLNAME) - 1)) IN ('MR', 'MASTER') THEN 'M'" & vbCrLf
    sqlPart2 = sqlPart2 & "                                WHEN UPPER(SUBSTR(t3.CLNAME, 1, LOCATE(' ', t3.CLNAME) - 1)) IN ('MRS', 'MISS', 'MS') THEN 'F'" & vbCrLf
    sqlPart2 = sqlPart2 & "                                WHEN UPPER(SUBSTR(t3.CLNAME, 1, LOCATE(' ', t3.CLNAME) - 1)) IN ('DR', 'PROF') THEN 'N/A'" & vbCrLf
    sqlPart2 = sqlPart2 & "                                ELSE 'N/A'" & vbCrLf
    sqlPart2 = sqlPart2 & "                END AS CLIENT_GENDER," & vbCrLf
    sqlPart2 = sqlPart2 & "                t6.UENAT," & vbCrLf
    sqlPart2 = sqlPart2 & "                t7.NATION," & vbCrLf
    sqlPart2 = sqlPart2 & "                t1.BUYDECIND," & vbCrLf
    sqlPart2 = sqlPart2 & "                CASE" & vbCrLf
    sqlPart2 = sqlPart2 & "                                WHEN t1.BUYDECIND <> '' THEN t5.PTYSCHCODE" & vbCrLf
    sqlPart2 = sqlPart2 & "                END AS BUYDEC_ID_TYPE," & vbCrLf
    sqlPart2 = sqlPart2 & "                t1.BUYDECFORE," & vbCrLf
    sqlPart2 = sqlPart2 & "                t1.BUYDECSURN," & vbCrLf
    sqlPart2 = sqlPart2 & "CASE " & vbCrLf
    sqlPart2 = sqlPart2 & "    WHEN t1.BUYDECDOB IS NULL OR t1.BUYDECDOB <= DATE('1941-01-01') THEN NULL" & vbCrLf
    sqlPart2 = sqlPart2 & "    ELSE t1.BUYDECDOB" & vbCrLf
    sqlPart2 = sqlPart2 & "END AS BUYDECDOB" & vbCrLf

    sqlPart3 = "                FROM" & vbCrLf
    sqlPart3 = sqlPart3 & "                GLDATA/TXNREPESMA t1" & vbCrLf
    sqlPart3 = sqlPart3 & "                JOIN GLDATA/CONTCT t2 ON" & vbCrLf
    sqlPart3 = sqlPart3 & "                                t2.FRMCOD || t2.YEAR || t2.ACCLTR || t2.CONTNO || '1' = t1.REPORTREF" & vbCrLf
    sqlPart3 = sqlPart3 & "                                AND BUYSEL = 'B'" & vbCrLf
    sqlPart3 = sqlPart3 & "                JOIN GLDATA/CLIENT t3 ON t2.CLINUM = t3.CLINO" & vbCrLf
    sqlPart3 = sqlPart3 & "                JOIN GLDATA/ESMAPTYIND t5 ON t1.REPORTREF = t5.REPORTREF" & vbCrLf
    sqlPart3 = sqlPart3 & "                LEFT JOIN GLDATA/PERSON t6 ON t5.UECODE = t6.UECODE" & vbCrLf
	sqlPart3 = sqlPart3 & "				   LEFT JOIN GLDATA / PERSON t6b ON SUBSTR(t2.CLINUM, 1, LENGTH(t2.CLINUM) - 1) = t6b.UECODE" & vbCrLf
    sqlPart3 = sqlPart3 & "                LEFT JOIN GLDATA/PERSONNAT t7 ON t3.UECODE = t7.UECODE" & vbCrLf
    sqlPart3 = sqlPart3 & "                LEFT JOIN GLDATA/ESMAPTYIND t5b ON t1.BUYDECIND = t5b.PTYSCHCODE" & vbCrLf
    sqlPart3 = sqlPart3 & "                LEFT JOIN LinkCodes lc ON t2.CLINUM = lc.CLINUM" & vbCrLf

    sqlPart4 = "                WHERE" & vbCrLf
    sqlPart4 = sqlPart4 & "                t1.REPORTREF IN (" & vbCrLf
    sqlPart4 = sqlPart4 & "--<<TRANSACTION REFERENCES>>" & vbCrLf
    sqlPart4 = sqlPart4 & "                )"

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
