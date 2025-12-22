Sub ValidateDecisionMaker3_0()
    ' Enhanced error handling and performance improvements
    On Error GoTo ErrorHandler
    
    Dim wsClient As Worksheet, wsLEI As Worksheet, wsFormats As Worksheet
    Dim lastRow As Long, i As Long
    Dim accountID As String, accountType As String, serviceLevel As String
    Dim buyerCode As String, buyerDMCode As String, branchCode As String
    Dim product As String, isError As String, correction As String, correctionField As String
    Dim decisionMakerLEI As String
    Dim buyerCodeType As String, buyerDMCodeType As String
    Dim isSIPP As Boolean, branchExists As Boolean
    
    ' Constants for column positions (easier to maintain)
    Const COL_ACCOUNT_ID = 2
    Const COL_SELLER_CODE = 3
    Const COL_SELLER_CODE_TYPE = 4
    Const COL_SELLER_DM_CODE = 5
    Const COL_SELLER_DM_CODE_TYPE = 6
    Const COL_PRODUCT = 7
    Const COL_ACCOUNT_TYPE = 8
    Const COL_SERVICE_LEVEL = 9
    Const COL_BRANCH_CODE = 10
    Const COL_ERROR = 11
    Const COL_CORRECTION = 12
    Const COL_CORRECTION_FIELD = 13
    
    ' Validate worksheets exist
    Set wsClient = GetWorksheet("Client Data")
    Set wsLEI = GetWorksheet("LEI Data")
    Set wsFormats = GetWorksheet("ID and LEI Formats")
    If wsClient Is Nothing Or wsLEI Is Nothing Or wsFormats Is Nothing Then Exit Sub
    
    ' Find last row with data validation
    lastRow = wsClient.Cells(wsClient.Rows.Count, 1).End(xlUp).Row
    If lastRow < 2 Then
        MsgBox "No data found to validate."
        Exit Sub
    End If
    
    ' Initialize headers
    Call InitializeHeaders(wsClient)
    
    ' Turn off screen updating for better performance
    Application.ScreenUpdating = False
    
    ' Process each row
    For i = 2 To lastRow
        ' Clear previous values and get current row data
        Call ClearRowResults(isError, correction, correctionField, product, buyerCodeType, buyerDMCodeType)
        Call GetRowData(wsClient, i, accountID, buyerCode, buyerDMCode, accountType, serviceLevel, branchCode)
        
        ' NEW: Validate ID formats first (before product determination)
        buyerCodeType = ValidateIDFormat(wsFormats, buyerCode)
        buyerDMCodeType = ValidateIDFormat(wsFormats, buyerDMCode)
        
        ' Output ID types to columns 4 and 6
        wsClient.Cells(i, COL_SELLER_CODE_TYPE).Value = buyerCodeType
        wsClient.Cells(i, COL_SELLER_DM_CODE_TYPE).Value = buyerDMCodeType
        
        ' Determine product
        product = DetermineProduct(accountID)
        wsClient.Cells(i, COL_PRODUCT).Value = product
        
        ' Check if SIPP
        isSIPP = (UCase(Trim(accountType)) = "SIPP")
        
        ' Apply validation logic - preserving original business logic structure
        If UCase(accountType) = "CUSTODY SOLUTIONS" Then
            ' Custody Solutions account validation
            If UCase(serviceLevel) = "D" Then
                ' Discretionary Custody Solutions
                Call ValidateDiscretionaryAccount(wsLEI, buyerCode, buyerDMCode, branchCode, _
                                                isError, correction, correctionField)
            Else
                ' Non-discretionary Custody Solutions - no error
                isError = "N"
            End If
        ElseIf isSIPP Then
            ' SIPP account - no error
            isError = "N"
        Else
            ' Other account types (AJB, AJBIC, DODL, etc.)
            If UCase(serviceLevel) = "D" Then
                ' Discretionary other accounts
                Call ValidateDiscretionaryAccount(wsLEI, buyerCode, buyerDMCode, branchCode, _
                                                isError, correction, correctionField)
            Else
                ' Non-discretionary other accounts - no error
                isError = "N"
            End If
        End If
        
        ' Output results
        wsClient.Cells(i, COL_ERROR).Value = isError
        wsClient.Cells(i, COL_CORRECTION).Value = correction
        wsClient.Cells(i, COL_CORRECTION_FIELD).Value = correctionField
    Next i
    
    Application.ScreenUpdating = True
    MsgBox "Transaction validation completed for " & (lastRow - 1) & " records."
    Exit Sub
    
ErrorHandler:
    Application.ScreenUpdating = True
    MsgBox "Error occurred: " & Err.Description & " (Error " & Err.Number & ")"
End Sub

' NEW FUNCTION: Validates ID format against patterns in the formats sheet
Function ValidateIDFormat(wsFormats As Worksheet, idCode As String) As String
    ' This function checks if an ID matches any of the regex patterns
    ' Returns the ID type if match found, empty string if no match
    
    Dim regex As Object
    Dim lastRowFormats As Long, j As Long
    Dim currentPattern As String, currentIDType As String
    
    ValidateIDFormat = "" ' Default to empty if no match
    
    ' Skip validation if ID is empty
    If Trim(idCode) = "" Then Exit Function
    
    ' Create regex object for pattern matching
    Set regex = CreateObject("VBScript.RegExp")
    regex.Global = False ' We only need to know if it matches, not find all matches
    regex.IgnoreCase = False ' Case sensitive matching
    
    ' Find last row in formats sheet
    lastRowFormats = wsFormats.Cells(wsFormats.Rows.Count, 1).End(xlUp).Row
    If lastRowFormats < 2 Then Exit Function ' No data to check against
    
    ' Check LEI format first (most common)
    regex.Pattern = "^[A-Z0-9]{18}\d{2}$"
    If regex.Test(Trim(idCode)) Then
        ValidateIDFormat = "LEI"
        Exit Function
    End If
    
    ' Check other patterns in order they appear in the table
    For j = 2 To lastRowFormats
        currentIDType = Trim(CStr(wsFormats.Cells(j, 2).Value)) ' Column B has ID type
        currentPattern = Trim(CStr(wsFormats.Cells(j, 3).Value)) ' Column C has regex pattern
        
        ' Skip empty rows
        If currentPattern <> "" And currentIDType <> "" Then
            regex.Pattern = currentPattern
            
            ' Test if the ID matches this pattern
            If regex.Test(Trim(idCode)) Then
                ValidateIDFormat = currentIDType
                Exit Function ' Found a match, stop looking
            End If
        End If
    Next j
    
    ' If we reach here, no pattern matched, so return empty string
End Function

' Helper functions (modified to include new parameters)
Function GetWorksheet(sheetName As String) As Worksheet
    On Error Resume Next
    Set GetWorksheet = ThisWorkbook.Worksheets(sheetName)
    If GetWorksheet Is Nothing Then
        MsgBox "Worksheet '" & sheetName & "' not found."
    End If
    On Error GoTo 0
End Function

Sub InitializeHeaders(ws As Worksheet)
    ' Initialize headers including the new ID type columns
    If ws.Cells(1, 11).Value = "" Then
        ws.Cells(1, 11).Value = "Error"
        ws.Cells(1, 12).Value = "Correction"
        ws.Cells(1, 13).Value = "Correction Field"
    End If
    ' Add headers for ID type columns if they don't exist
    If ws.Cells(1, 4).Value = "" Then
        ws.Cells(1, 4).Value = "Type of buyer identification code"
    End If
    If ws.Cells(1, 6).Value = "" Then
        ws.Cells(1, 6).Value = "Type of buyer decision maker code"
    End If
End Sub

Sub ClearRowResults(ByRef isError As String, ByRef correction As String, _
                   ByRef correctionField As String, ByRef product As String, _
                   ByRef buyerCodeType As String, ByRef buyerDMCodeType As String)
    isError = "N"
    correction = ""
    correctionField = ""
    product = ""
    buyerCodeType = ""
    buyerDMCodeType = ""
End Sub

Sub GetRowData(ws As Worksheet, rowNum As Long, ByRef accountID As String, _
               ByRef buyerCode As String, ByRef buyerDMCode As String, _
               ByRef accountType As String, ByRef serviceLevel As String, _
               ByRef branchCode As String)
    accountID = Trim(CStr(ws.Cells(rowNum, 2).Value))
    buyerCode = Trim(CStr(ws.Cells(rowNum, 3).Value))
    buyerDMCode = Trim(CStr(ws.Cells(rowNum, 5).Value))
    accountType = Trim(CStr(ws.Cells(rowNum, 8).Value))
    serviceLevel = Trim(CStr(ws.Cells(rowNum, 9).Value))
    branchCode = Trim(CStr(ws.Cells(rowNum, 10).Value))
End Sub

Function DetermineProduct(accountID As String) As String
    If Len(accountID) > 0 Then
        Select Case UCase(Left(accountID, 1))
            Case "A": DetermineProduct = "AJB"
            Case "B": DetermineProduct = "AJBIC"
            Case "X": DetermineProduct = "DODL"
            Case Else: DetermineProduct = "Custody Solutions"
        End Select
    Else
        DetermineProduct = "Custody Solutions"
    End If
End Function

Sub ValidateDiscretionaryAccount(wsLEI As Worksheet, buyerCode As String, _
                                buyerDMCode As String, branchCode As String, _
                                ByRef isError As String, ByRef correction As String, _
                                ByRef correctionField As String)
    Dim decisionMakerLEI As String
    Dim branchExists As Boolean
    
    If buyerDMCode = "" Then
        ' No DM populated - need correction
        decisionMakerLEI = FindDecisionMakerLEI(wsLEI, branchCode, branchExists)
        If branchExists Then
            If decisionMakerLEI <> "" Then
                correction = decisionMakerLEI & ":L"
                correctionField = "Seller decision maker code:Type of buyer decision maker code"
                isError = "Y"
            Else
                isError = "Y" ' LEI found but empty
            End If
        Else
            isError = "TBC - Investigate branch code"
        End If
    ElseIf buyerCode = buyerDMCode Then
        ' Same values - potential error, try to find correct DM
        decisionMakerLEI = FindDecisionMakerLEI(wsLEI, branchCode, branchExists)
        If branchExists Then
            If decisionMakerLEI <> "" And decisionMakerLEI <> buyerDMCode Then
                correction = decisionMakerLEI & ":L"
                correctionField = "Seller decision maker code:Type of buyer decision maker code"
                isError = "Y"
            Else
                isError = "TBC - Investigate LEI"
            End If
        Else
            isError = "TBC - Investigate branch code"
        End If
    Else
        ' Different values - no error
        isError = "N"
    End If
End Sub

Function FindDecisionMakerLEI(wsLEI As Worksheet, branchCode As String, _
                             ByRef branchExists As Boolean) As String
    Dim lastRowLEI As Long, j As Long
    
    branchExists = False
    FindDecisionMakerLEI = ""
    
    ' Validate worksheet and find last row
    If wsLEI Is Nothing Then Exit Function
    lastRowLEI = wsLEI.Cells(wsLEI.Rows.Count, 1).End(xlUp).Row
    If lastRowLEI < 2 Then Exit Function
    
    ' Search for matching branch code
    For j = 2 To lastRowLEI
        If Trim(CStr(wsLEI.Cells(j, 1).Value)) = branchCode Then
            branchExists = True
            FindDecisionMakerLEI = Trim(CStr(wsLEI.Cells(j, 2).Value))
            Exit For
        End If
    Next j
End Function
