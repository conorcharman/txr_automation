Sub extract_buyer_id()
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
        outputPath = "F:\Transaction Reporting\Kaizen Reporting\Accuracy Testing\Automated Accuracy Testing\Incorrect Net Amount - 35_3\Extracts\SQL\"
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

    ' SQL Template from SCR_pricing_data_v1.0.sql
    sqlTemplate = "SELECT" & vbCrLf
    sqlTemplate = sqlTemplate & "    t1.REPORTREF," & vbCrLf
    sqlTemplate = sqlTemplate & "    t1.NETAMT," & vbCrLf
    sqlTemplate = sqlTemplate & "    t2.CLICSD," & vbCrLf
    sqlTemplate = sqlTemplate & "    t2.INTRST" & vbCrLf
    sqlTemplate = sqlTemplate & "FROM" & vbCrLf
    sqlTemplate = sqlTemplate & "    GLDATA/TXNREPESMA t1" & vbCrLf
    sqlTemplate = sqlTemplate & "JOIN GLDATA/CONTCT t2 ON t2.FRMCOD || t2.YEAR || t2.ACCLTR || t2.CONTNO || '1' = t1.REPORTREF" & vbCrLf
    sqlTemplate = sqlTemplate & "WHERE" & vbCrLf
    sqlTemplate = sqlTemplate & "    t1.REPORTREF IN (" & vbCrLf
    sqlTemplate = sqlTemplate & "--<<TRANSACTION REFERENCES>>" & vbCrLf
    sqlTemplate = sqlTemplate & "    )"

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
