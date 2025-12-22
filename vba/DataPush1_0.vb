Option Explicit

' ============================================================================
' DATA PUSH MACRO
' ============================================================================
' This macro takes data from the current workbook and pushes it to the
' Seller ID Validation.xlsx workbook, updating specific columns based on
' transaction reference matches. This reverses the lookup process to avoid
' needing macro-enabled target files.
' ============================================================================

' Configuration constants
Private Const TARGET_WORKBOOK_BASE_FOLDER As String = "F:\Transaction Reporting\Kaizen Reporting\Accuracy Testing\"  ' Base folder path for target workbooks
Private Const COL_TRANSACTION_REF As Long = 1

' Source columns to push (data from source workbook columns - same as original lookup columns)
Private Const SOURCE_DATA_COLS As String = "2,6,25,21,22,23,24"  ' Columns containing data to push
' Target columns to update (starting from column 3 onwards, one after the other)
Private Const TARGET_UPDATE_COLS As String = "3,4,5,6,7,8,9"  ' Columns to update in target

' ============================================================================
' MAIN ENTRY POINT
' ============================================================================

Sub DataPush1_0()
    ' Main function to push data from source to target workbook
    
    Dim startTime As Double
    startTime = Timer
    
    On Error GoTo ErrorHandler
    
    ' Get financial year from user
    Dim financialYear As String
    financialYear = GetFinancialYearFromUser()
    If financialYear = "" Then
        MsgBox "Data push cancelled - no financial year provided.", vbInformation, "Push Cancelled"
        Exit Sub
    End If
    
    ' Get quarter from user
    Dim quarterNum As String
    quarterNum = GetQuarterFromUser()
    If quarterNum = "" Then
        MsgBox "Data push cancelled - no quarter provided.", vbInformation, "Push Cancelled"
        Exit Sub
    End If
    
    ' Combine financial year and quarter
    Dim quarter As String
    quarter = financialYear & " " & quarterNum
    
    ' Get incident code from user
    Dim incidentCode As String
    incidentCode = GetIncidentCodeFromUser()
    If incidentCode = "" Then
        MsgBox "Data push cancelled - no incident code provided.", vbInformation, "Push Cancelled"
        Exit Sub
    End If
    
    ' Confirm the operation with user
    Dim confirmMsg As String
    confirmMsg = "This will push data from the current workbook to the target workbook." & vbNewLine & vbNewLine
    confirmMsg = confirmMsg & "Target: " & quarter & " - " & incidentCode & ".xlsx" & vbNewLine
    confirmMsg = confirmMsg & "Worksheet: Template" & vbNewLine & vbNewLine
    confirmMsg = confirmMsg & "Do you want to continue?"
    
    If MsgBox(confirmMsg, vbYesNo + vbQuestion, "Confirm Data Push") <> vbYes Then
        MsgBox "Data push cancelled by user.", vbInformation, "Push Cancelled"
        Exit Sub
    End If
    
    ' Initialize application settings for performance
    Call OptimizePerformance(True)
    
    ' Check if target workbook is already open and open it if needed
    Dim targetWorkbook As Workbook
    Dim wasAlreadyOpen As Boolean
    Set targetWorkbook = OpenTargetWorkbook(wasAlreadyOpen, financialYear, quarterNum, incidentCode)
    If targetWorkbook Is Nothing Then GoTo CleanupAndExit
    
    ' Get target worksheet based on incident code
    Dim targetWorksheet As Worksheet
    Set targetWorksheet = GetTargetWorksheet(targetWorkbook, incidentCode)
    If targetWorksheet Is Nothing Then GoTo CleanupAndExit
    
    ' Get source data from current workbook
    Dim sourceWorksheet As Worksheet
    Set sourceWorksheet = GetSourceWorksheet(ThisWorkbook, incidentCode)
    If sourceWorksheet Is Nothing Then GoTo CleanupAndExit
    
    ' Perform the data push operations
    Dim updateCount As Long
    updateCount = ProcessDataPush(sourceWorksheet, targetWorksheet)
    
    ' Save the target workbook
    If updateCount > 0 Then
        targetWorkbook.Save
        Call ShowCompletionMessage(Timer - startTime, updateCount)
    Else
        MsgBox "No matching records found to update.", vbInformation, "No Updates"
    End If
    
CleanupAndExit:
    ' Close target workbook only if it wasn't already open
    If Not targetWorkbook Is Nothing And Not wasAlreadyOpen Then
        targetWorkbook.Close True  ' Save changes
    End If
    
    Call OptimizePerformance(False)
    Exit Sub
    
ErrorHandler:
    Call HandleError(Err.Number, Err.Description, "DataPush1_0")
    GoTo CleanupAndExit
End Sub

' ============================================================================
' USER INPUT FUNCTIONS
' ============================================================================

Private Function GetFinancialYearFromUser() As String
    ' Get financial year from user input with validation
    On Error GoTo ErrorHandler
    
    Dim userInput As String
    Dim validInput As Boolean
    validInput = False
    
    Do While Not validInput
        userInput = InputBox("Please enter the financial year for data push:" & vbNewLine & vbNewLine & _
                           "Examples: FY25, FY26, FY27" & vbNewLine & vbNewLine & _
                           "This will determine which folder to target.", _
                           "Financial Year Input", "FY25")
        
        ' Check if user cancelled
        If userInput = "" Then
            GetFinancialYearFromUser = ""
            Exit Function
        End If
        
        ' Validate format (basic validation)
        userInput = Trim(UCase(userInput))
        If Len(userInput) = 4 And Left(userInput, 2) = "FY" And IsNumeric(Right(userInput, 2)) Then
            validInput = True
            GetFinancialYearFromUser = userInput
        Else
            MsgBox "Invalid financial year format. Please use format like 'FY25'.", vbExclamation, "Invalid Format"
        End If
    Loop
    
    Exit Function
    
ErrorHandler:
    Call HandleError(Err.Number, Err.Description, "GetFinancialYearFromUser")
    GetFinancialYearFromUser = ""
End Function

Private Function GetQuarterFromUser() As String
    ' Get quarter from user input with validation
    On Error GoTo ErrorHandler
    
    Dim userInput As String
    Dim validInput As Boolean
    validInput = False
    
    Do While Not validInput
        userInput = InputBox("Please enter the quarter for data push:" & vbNewLine & vbNewLine & _
                           "Examples: Q1, Q2, Q3, Q4" & vbNewLine & vbNewLine & _
                           "This will determine which folder and workbook to target.", _
                           "Quarter Input", "Q3")
        
        ' Check if user cancelled
        If userInput = "" Then
            GetQuarterFromUser = ""
            Exit Function
        End If
        
        ' Validate format (basic validation)
        userInput = Trim(UCase(userInput))
        If Len(userInput) = 2 And Left(userInput, 1) = "Q" And IsNumeric(Right(userInput, 1)) Then
            Dim quarterNum As Integer
            quarterNum = Val(Right(userInput, 1))
            If quarterNum >= 1 And quarterNum <= 4 Then
                validInput = True
                GetQuarterFromUser = userInput
            Else
                MsgBox "Invalid quarter number. Please use Q1, Q2, Q3, or Q4.", vbExclamation, "Invalid Format"
            End If
        Else
            MsgBox "Invalid quarter format. Please use format like 'Q3'.", vbExclamation, "Invalid Format"
        End If
    Loop
    
    Exit Function
    
ErrorHandler:
    Call HandleError(Err.Number, Err.Description, "GetQuarterFromUser")
    GetQuarterFromUser = ""
End Function

Private Function GetIncidentCodeFromUser() As String
    ' Get incident code from user input with validation
    On Error GoTo ErrorHandler
    
    Dim userInput As String
    Dim validInput As Boolean
    validInput = False
    
    Do While Not validInput
        userInput = InputBox("Please enter the incident code for data push:" & vbNewLine & vbNewLine & _
                           "Examples: 7_35, 7_37, 7_39" & vbNewLine & vbNewLine & _
                           "This will determine which worksheet to update in the target workbook.", _
                           "Incident Code Input", "7_37")
        
        ' Check if user cancelled
        If userInput = "" Then
            GetIncidentCodeFromUser = ""
            Exit Function
        End If
        
        ' Validate format (basic validation)
        userInput = Trim(userInput)
        If Len(userInput) >= 4 And InStr(userInput, "_") > 0 Then
            ' For now, assume the format is valid
            ' Additional validation could be added here
            validInput = True
            GetIncidentCodeFromUser = userInput
        Else
            MsgBox "Invalid incident code format. Please use format like '7_37'.", vbExclamation, "Invalid Format"
        End If
    Loop
    
    Exit Function
    
ErrorHandler:
    Call HandleError(Err.Number, Err.Description, "GetIncidentCodeFromUser")
    GetIncidentCodeFromUser = ""
End Function

' ============================================================================
' WORKBOOK AND WORKSHEET MANAGEMENT
' ============================================================================

Private Function OpenTargetWorkbook(ByRef wasAlreadyOpen As Boolean, financialYear As String, quarterNum As String, incidentCode As String) As Workbook
    ' Opens the target workbook for data push operations or returns existing instance
    On Error GoTo ErrorHandler
    
    ' Construct workbook name and path
    Dim workbookName As String
    Dim targetWorkbookPath As String
    
    workbookName = financialYear & " " & quarterNum & " - " & incidentCode & ".xlsx"
    targetWorkbookPath = TARGET_WORKBOOK_BASE_FOLDER & financialYear & "\" & quarterNum & "\Incident Code Analysis\" & workbookName
    
    ' Debug output
    Debug.Print "=== WORKBOOK OPEN DEBUG ==="
    Debug.Print "Workbook name: " & workbookName
    Debug.Print "Full path: " & targetWorkbookPath
    Debug.Print "Base folder: " & TARGET_WORKBOOK_BASE_FOLDER
    
    wasAlreadyOpen = False
    Set OpenTargetWorkbook = Nothing
    
    ' Check if workbook is already open
    Dim wb As Workbook
    Set wb = Nothing
    
    On Error Resume Next
    Set wb = Workbooks(workbookName)
    On Error GoTo ErrorHandler
    
    If Not wb Is Nothing Then
        ' Workbook is already open
        Debug.Print "Workbook already open: " & wb.FullName
        wasAlreadyOpen = True
        Set OpenTargetWorkbook = wb
        Debug.Print "=== END WORKBOOK DEBUG ==="
        Exit Function
    End If
    
    Debug.Print "Workbook not currently open, checking file existence..."
    
    ' Check if file exists at the constructed path
    If Dir(targetWorkbookPath) = "" Then
        Debug.Print "File NOT found at path: " & targetWorkbookPath
        MsgBox "Target workbook not found: " & targetWorkbookPath, vbCritical, "File Not Found"
        Set OpenTargetWorkbook = Nothing
        Debug.Print "=== END WORKBOOK DEBUG ==="
        Exit Function
    End If
    
    Debug.Print "File found, attempting to open..."
    
    ' Try to open the workbook
    wasAlreadyOpen = False
    Set OpenTargetWorkbook = Workbooks.Open(targetWorkbookPath, False, False)  ' Open for writing
    
    If Not OpenTargetWorkbook Is Nothing Then
        Debug.Print "Successfully opened: " & OpenTargetWorkbook.FullName
    Else
        Debug.Print "Failed to open workbook (returned Nothing)"
    End If
    
    Debug.Print "=== END WORKBOOK DEBUG ==="
    Exit Function
    
ErrorHandler:
    Debug.Print "Error in OpenTargetWorkbook: " & Err.Number & " - " & Err.Description
    Debug.Print "Attempted path: " & targetWorkbookPath
    Debug.Print "=== END WORKBOOK DEBUG ==="
    MsgBox "Error opening target workbook: " & Err.Description & vbNewLine & vbNewLine & _
           "Attempted path: " & targetWorkbookPath, vbCritical, "Error Opening File"
    Set OpenTargetWorkbook = Nothing
End Function

Private Function GetTargetWorksheet(targetWb As Workbook, incidentCode As String) As Worksheet
    ' Gets the appropriate worksheet based on incident code
    On Error GoTo ErrorHandler
    
    Dim worksheetName As String
    worksheetName = "Template"
    
    ' Check if worksheet exists
    Dim ws As Worksheet
    Set ws = Nothing
    
    On Error Resume Next
    Set ws = targetWb.Sheets(worksheetName)
    On Error GoTo ErrorHandler
    
    If ws Is Nothing Then
        MsgBox "Worksheet '" & worksheetName & "' not found in target workbook.", vbCritical, "Worksheet Not Found"
        Set GetTargetWorksheet = Nothing
    Else
        Set GetTargetWorksheet = ws
    End If
    
    Exit Function
    
ErrorHandler:
    MsgBox "Error accessing worksheet: " & Err.Description, vbCritical, "Worksheet Error"
    Set GetTargetWorksheet = Nothing
End Function

Private Function GetSourceWorksheet(sourceWb As Workbook, incidentCode As String) As Worksheet
    ' Gets the appropriate source worksheet based on incident code format "Client Data - [incident_code]"
    On Error GoTo ErrorHandler
    
    Dim worksheetName As String
    worksheetName = "Client Data - " & incidentCode
    
    ' Check if worksheet exists
    Dim ws As Worksheet
    Set ws = Nothing
    
    On Error Resume Next
    Set ws = sourceWb.Sheets(worksheetName)
    On Error GoTo ErrorHandler
    
    If ws Is Nothing Then
        MsgBox "Source worksheet '" & worksheetName & "' not found in current workbook." & vbNewLine & vbNewLine & _
               "Please ensure the worksheet exists with the correct name format: 'Client Data - " & incidentCode & "'", _
               vbCritical, "Source Worksheet Not Found"
        Set GetSourceWorksheet = Nothing
    Else
        Set GetSourceWorksheet = ws
    End If
    
    Exit Function
    
ErrorHandler:
    MsgBox "Error accessing source worksheet: " & Err.Description, vbCritical, "Source Worksheet Error"
    Set GetSourceWorksheet = Nothing
End Function

' ============================================================================
' DATA PUSH PROCESSING
' ============================================================================

Private Function ProcessDataPush(sourceWs As Worksheet, targetWs As Worksheet) As Long
    ' Processes all data push operations from source to target
    On Error GoTo ErrorHandler
    
    ' Get the last row of source data
    Dim lastRow As Long
    lastRow = sourceWs.Cells(sourceWs.Rows.Count, COL_TRANSACTION_REF).End(xlUp).Row
    
    If lastRow < 2 Then
        MsgBox "No data found in source worksheet.", vbInformation, "No Data"
        ProcessDataPush = 0
        Exit Function
    End If
    
    ' Parse the column arrays
    Dim sourceColumns As Variant
    Dim targetColumns As Variant
    sourceColumns = Split(SOURCE_DATA_COLS, ",")
    targetColumns = Split(TARGET_UPDATE_COLS, ",")
    
    ' Validate column arrays match
    If UBound(sourceColumns) <> UBound(targetColumns) Then
        MsgBox "Source and target column configurations don't match.", vbCritical, "Configuration Error"
        ProcessDataPush = 0
        Exit Function
    End If
    
    ' Process each row in source data
    Dim updateCount As Long
    updateCount = 0
    
    Dim i As Long
    For i = 2 To lastRow
        Dim transactionRef As String
        transactionRef = Trim(CStr(sourceWs.Cells(i, COL_TRANSACTION_REF).Value))
        
        If transactionRef <> "" Then
            If ProcessSingleDataPush(sourceWs, targetWs, i, transactionRef, sourceColumns, targetColumns) Then
                updateCount = updateCount + 1
            End If
        End If
        
        ' Update progress
        If i Mod 50 = 0 Then
            Application.StatusBar = "Processing record " & (i - 1) & " of " & (lastRow - 1) & " (Updated: " & updateCount & ")"
        End If
    Next i
    
    Application.StatusBar = False
    ProcessDataPush = updateCount
    Exit Function
    
ErrorHandler:
    Application.StatusBar = False
    Call HandleError(Err.Number, Err.Description, "ProcessDataPush")
    ProcessDataPush = 0
End Function

Private Function ProcessSingleDataPush(sourceWs As Worksheet, targetWs As Worksheet, sourceRowIndex As Long, transactionRef As String, sourceColumns As Variant, targetColumns As Variant) As Boolean
    ' Processes a single data push operation
    On Error GoTo ErrorHandler
    
    ProcessSingleDataPush = False
    
    ' Find the transaction reference in the target worksheet
    Dim targetRow As Long
    targetRow = FindTransactionRow(targetWs, transactionRef)
    
    If targetRow = 0 Then
        ' Transaction not found in target - log this if needed
        ' Could optionally add a log sheet or output for unmatched records
        Exit Function
    End If
    
    ' Check column 25 value to determine what to push
    Dim column25Value As String
    column25Value = Trim(UCase(CStr(sourceWs.Cells(sourceRowIndex, 25).Value)))
    
    If column25Value = "Y" Then
        ' Column 25 contains "Y" - push all configured data columns
        
        ' Check if source row has data to push (at least one non-empty cell in data columns)
        Dim hasData As Boolean
        hasData = False
        
        Dim j As Long
        For j = 0 To UBound(sourceColumns)
            Dim sourceCol As Long
            sourceCol = CLng(Trim(sourceColumns(j)))
            
            If sourceWs.Cells(sourceRowIndex, sourceCol).Value <> "" Then
                hasData = True
                Exit For
            End If
        Next j
        
        If Not hasData Then
            ' No data to push
            Exit Function
        End If
        
        ' Push the data from source worksheet to target worksheet
        For j = 0 To UBound(sourceColumns)
            Dim sourceColNum As Long
            Dim targetColNum As Long
            
            sourceColNum = CLng(Trim(sourceColumns(j)))
            targetColNum = CLng(Trim(targetColumns(j)))
            
            ' Copy the value from source to target
            Dim sourceValue As Variant
            sourceValue = sourceWs.Cells(sourceRowIndex, sourceColNum).Value
            
            ' Only update if source has a value (avoid overwriting with blanks unless intentional)
            If sourceValue <> "" Then
                targetWs.Cells(targetRow, targetColNum).Value = sourceValue
            End If
        Next j
        
    ElseIf column25Value = "N" Then
        ' Column 25 contains "N" - only push "N" to column 5 (target)
        targetWs.Cells(targetRow, 5).Value = "N"
        
    Else
        ' Column 25 doesn't contain "Y" or "N", so skip this row
        Exit Function
    End If
    
    ProcessSingleDataPush = True
    Exit Function
    
ErrorHandler:
    Call HandleError(Err.Number, Err.Description, "ProcessSingleDataPush")
    ProcessSingleDataPush = False
End Function

Private Function FindTransactionRow(targetWs As Worksheet, transactionRef As String) As Long
    ' Finds the row containing the specified transaction reference in target worksheet
    On Error GoTo ErrorHandler
    
    Dim lastRow As Long
    lastRow = targetWs.Cells(targetWs.Rows.Count, 1).End(xlUp).Row
    
    ' Enhanced Debug: Show detailed information
    Debug.Print "=== SEARCH DEBUG ==="
    Debug.Print "Looking for: '" & transactionRef & "' (Length: " & Len(transactionRef) & ")"
    Debug.Print "Target workbook: " & targetWs.Parent.Name
    Debug.Print "Target workbook path: " & targetWs.Parent.FullName
    Debug.Print "Target sheet: " & targetWs.Name
    Debug.Print "Search range: A1:A" & lastRow & " (Total rows: " & lastRow & ")"
    
    ' Show more sample data for better comparison
    Debug.Print "Target column A sample values (first 10 rows):"
    Dim i As Long
    For i = 1 To Application.Min(10, lastRow)
        Dim cellValue As String
        cellValue = CStr(targetWs.Cells(i, 1).Value)
        Debug.Print "Row " & i & ": '" & cellValue & "' (Length: " & Len(cellValue) & ", Type: " & TypeName(targetWs.Cells(i, 1).Value) & ")"
    Next i
    
    ' Use Application.Match for better performance
    On Error Resume Next
    Dim matchResult As Variant
    matchResult = Application.Match(transactionRef, targetWs.Range(targetWs.Cells(1, 1), targetWs.Cells(lastRow, 1)), 0)
    
    If IsError(matchResult) Then
        Debug.Print "No exact match found."
        
        ' Try to find partial matches or similar values
        Debug.Print "Checking for partial matches..."
        For i = 1 To Application.Min(lastRow, 20)
            Dim targetValue As String
            targetValue = Trim(CStr(targetWs.Cells(i, 1).Value))
            If InStr(1, targetValue, transactionRef, vbTextCompare) > 0 Or InStr(1, transactionRef, targetValue, vbTextCompare) > 0 Then
                Debug.Print "Potential partial match at row " & i & ": '" & targetValue & "'"
            End If
        Next i
        
        FindTransactionRow = 0
    Else
        Debug.Print "*** EXACT MATCH FOUND at row: " & CLng(matchResult) & " ***"
        FindTransactionRow = CLng(matchResult)
    End If
    
    Debug.Print "=== END SEARCH DEBUG ==="
    
    On Error GoTo ErrorHandler
    Exit Function
    
ErrorHandler:
    Debug.Print "Error in FindTransactionRow: " & Err.Description
    FindTransactionRow = 0
End Function

' ============================================================================
' UTILITY FUNCTIONS
' ============================================================================

Private Sub OptimizePerformance(enableOptimization As Boolean)
    ' Optimizes Excel performance during processing
    If enableOptimization Then
        Application.ScreenUpdating = False
        Application.Calculation = xlCalculationManual
        Application.EnableEvents = False
    Else
        Application.ScreenUpdating = True
        Application.Calculation = xlCalculationAutomatic
        Application.EnableEvents = True
        Application.StatusBar = False
    End If
End Sub

Private Sub HandleError(errorNumber As Long, errorDescription As String, functionName As String)
    ' Centralized error handling
    Dim errorMsg As String
    errorMsg = "Error in " & functionName & ": " & errorNumber & " - " & errorDescription
    MsgBox errorMsg, vbCritical, "Processing Error"
End Sub

Private Sub ShowCompletionMessage(processingTime As Double, updateCount As Long)
    ' Shows completion message with processing time and update count
    Dim msg As String
    msg = "Data push completed successfully!" & vbNewLine & vbNewLine
    msg = msg & "Records updated: " & updateCount & vbNewLine
    msg = msg & "Processing time: " & Format(processingTime, "0.0") & " seconds" & vbNewLine & vbNewLine
    msg = msg & "Target workbook has been saved."
    MsgBox msg, vbInformation, "Push Complete"
End Sub
