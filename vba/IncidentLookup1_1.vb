Option Explicit

' ============================================================================
' TRANSACTION LOOKUP MACRO
' ============================================================================
' This macro takes transaction references from column 1 of the current workbook
' and looks them up in the Buyer ID Validation.xlsm workbook, returning data
' from specified columns based on user-defined conditions.
' ============================================================================

' Configuration constants
Private Const TARGET_WORKBOOK_PATH As String = "F:\Transaction Reporting\Kaizen Reporting\Accuracy Testing\Automated Accuracy Testing\Identification Code - Buyer - 7_35, 7_37, 7_39\Buyer ID Validation.xlsm"
Private Const COL_TRANSACTION_REF As Long = 1

' Target columns to return (in order)
Private Const RETURN_COLS As String = "2,6,25,21,22,23,24"
Private Const CONDITIONAL_COLS As String = "2,6,25"  ' Columns to return when W2 C25 = "N"

' ============================================================================
' MAIN ENTRY POINT
' ============================================================================

Sub IncidentLookup1_1()
    ' Main function to perform transaction reference lookups
    
    Dim startTime As Double
    startTime = Timer
    
    On Error GoTo ErrorHandler
    
    ' Get incident code from user
    Dim incidentCode As String
    incidentCode = GetIncidentCodeFromUser()
    If incidentCode = "" Then
        MsgBox "Lookup cancelled - no incident code provided.", vbInformation, "Lookup Cancelled"
        Exit Sub
    End If
    
    ' Initialize application settings for performance
    Call OptimizePerformance(True)
    
    ' Check if target workbook is already open and open it if needed
    Dim targetWorkbook As Workbook
    Dim wasAlreadyOpen As Boolean
    Set targetWorkbook = OpenTargetWorkbook(wasAlreadyOpen)
    If targetWorkbook Is Nothing Then GoTo CleanupAndExit
    
    ' Get target worksheet based on incident code
    Dim targetWorksheet As Worksheet
    Set targetWorksheet = GetTargetWorksheet(targetWorkbook, incidentCode)
    If targetWorksheet Is Nothing Then GoTo CleanupAndExit
    
    ' Get source data from current workbook
    Dim sourceWorksheet As Worksheet
    Set sourceWorksheet = ThisWorkbook.Sheets(1)
    
    ' Perform the lookup operations
    Call ProcessTransactionLookups(sourceWorksheet, targetWorksheet)
    
    ' Show completion message
    Call ShowCompletionMessage(Timer - startTime)
    
CleanupAndExit:
    ' Close target workbook only if it wasn't already open
    If Not targetWorkbook Is Nothing And Not wasAlreadyOpen Then
        targetWorkbook.Close False
    End If
    
    Call OptimizePerformance(False)
    Exit Sub
    
ErrorHandler:
    Call HandleError(Err.Number, Err.Description, "PerformTransactionLookup")
    GoTo CleanupAndExit
End Sub

' ============================================================================
' USER INPUT FUNCTION (Based on your existing function)
' ============================================================================

Private Function GetIncidentCodeFromUser() As String
    ' Get incident code from user input with validation
    On Error GoTo ErrorHandler
    
    Dim userInput As String
    Dim validInput As Boolean
    validInput = False
    
    Do While Not validInput
        userInput = InputBox("Please enter the incident code for transaction lookup:" & vbNewLine & vbNewLine & _
                           "Examples: 7_35, 7_37, 7_39" & vbNewLine & vbNewLine & _
                           "This will determine which worksheet to lookup data from.", _
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

Private Function OpenTargetWorkbook(ByRef wasAlreadyOpen As Boolean) As Workbook
    ' Opens the target workbook for lookup operations or returns existing instance
    On Error GoTo ErrorHandler
    
    ' Check if workbook is already open
    Dim wb As Workbook
    Dim workbookName As String
    workbookName = "Buyer ID Validation.xlsm"
    
    wasAlreadyOpen = False
    Set OpenTargetWorkbook = Nothing
    
    ' Check if workbook is already open
    On Error Resume Next
    Set wb = Workbooks(workbookName)
    On Error GoTo ErrorHandler
    
    If Not wb Is Nothing Then
        ' Workbook is already open
        wasAlreadyOpen = True
        Set OpenTargetWorkbook = wb
        Exit Function
    End If
    
    ' Check if file exists
    If Dir(TARGET_WORKBOOK_PATH) = "" Then
        MsgBox "Target workbook not found: " & TARGET_WORKBOOK_PATH, vbCritical, "File Not Found"
        Set OpenTargetWorkbook = Nothing
        Exit Function
    End If
    
    ' Try to open the workbook
    wasAlreadyOpen = False
    Set OpenTargetWorkbook = Workbooks.Open(TARGET_WORKBOOK_PATH, False, True)
    Exit Function
    
ErrorHandler:
    MsgBox "Error opening target workbook: " & Err.Description, vbCritical, "Error Opening File"
    Set OpenTargetWorkbook = Nothing
End Function

Private Function GetTargetWorksheet(targetWb As Workbook, incidentCode As String) As Worksheet
    ' Gets the appropriate worksheet based on incident code
    On Error GoTo ErrorHandler
    
    Dim worksheetName As String
    worksheetName = "Client Data - " & incidentCode
    
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

' ============================================================================
' LOOKUP PROCESSING
' ============================================================================

Private Sub ProcessTransactionLookups(sourceWs As Worksheet, targetWs As Worksheet)
    ' Processes all transaction reference lookups
    On Error GoTo ErrorHandler
    
    ' Get the last row of source data
    Dim lastRow As Long
    lastRow = sourceWs.Cells(sourceWs.Rows.Count, COL_TRANSACTION_REF).End(xlUp).Row
    
    If lastRow < 2 Then
        MsgBox "No data found in source worksheet.", vbInformation, "No Data"
        Exit Sub
    End If
    
    ' Clear existing lookup results (columns 3 onwards)
    Call ClearExistingResults(sourceWs, lastRow)
    
    ' Parse the column arrays
    Dim returnColumns As Variant
    Dim conditionalColumns As Variant
    returnColumns = Split(RETURN_COLS, ",")
    conditionalColumns = Split(CONDITIONAL_COLS, ",")
    
    ' Process each row
    Dim i As Long
    For i = 2 To lastRow
        Dim transactionRef As String
        transactionRef = Trim(CStr(sourceWs.Cells(i, COL_TRANSACTION_REF).Value))
        
        If transactionRef <> "" Then
            Call ProcessSingleLookup(sourceWs, targetWs, i, transactionRef, returnColumns, conditionalColumns)
        End If
        
        ' Update progress
        If i Mod 50 = 0 Then
            Application.StatusBar = "Processing transaction " & (i - 1) & " of " & (lastRow - 1)
        End If
    Next i
    
    Application.StatusBar = False
    Exit Sub
    
ErrorHandler:
    Application.StatusBar = False
    Call HandleError(Err.Number, Err.Description, "ProcessTransactionLookups")
End Sub

Private Sub ProcessSingleLookup(sourceWs As Worksheet, targetWs As Worksheet, rowIndex As Long, transactionRef As String, returnColumns As Variant, conditionalColumns As Variant)
    ' Processes a single transaction reference lookup
    On Error GoTo ErrorHandler
    
    ' Find the transaction reference in the target worksheet
    Dim targetRow As Long
    targetRow = FindTransactionRow(targetWs, transactionRef)
    
    If targetRow = 0 Then
        ' Transaction not found - mark as "Not on spreadsheet"
        sourceWs.Cells(rowIndex, 3).Value = "Not on spreadsheet"
        Exit Sub
    End If
    
    ' Check column 25 value to determine which columns to return
    Dim col25Value As String
    col25Value = Trim(UCase(CStr(targetWs.Cells(targetRow, 25).Value)))
    
    Dim columnsToUse As Variant
    If col25Value = "N" Then
        ' Return only conditional columns (2, 6, 25)
        columnsToUse = conditionalColumns
    Else
        ' Return all columns (2, 6, 25, 21, 22, 23, 24)
        columnsToUse = returnColumns
    End If
    
    ' Copy the data from target worksheet to source worksheet
    Dim j As Long
    For j = 0 To UBound(columnsToUse)
        Dim sourceCol As Long
        Dim targetCol As Long
        
        sourceCol = j + 3 ' Start from column 3 in source
        targetCol = CLng(Trim(columnsToUse(j)))
        
        ' Copy the value
        sourceWs.Cells(rowIndex, sourceCol).Value = targetWs.Cells(targetRow, targetCol).Value
    Next j
    
    Exit Sub
    
ErrorHandler:
    Call HandleError(Err.Number, Err.Description, "ProcessSingleLookup")
End Sub

Private Function FindTransactionRow(targetWs As Worksheet, transactionRef As String) As Long
    ' Finds the row containing the specified transaction reference
    On Error GoTo ErrorHandler
    
    Dim lastRow As Long
    lastRow = targetWs.Cells(targetWs.Rows.Count, 1).End(xlUp).Row
    
    ' Use Application.Match for better performance
    On Error Resume Next
    Dim matchResult As Variant
    matchResult = Application.Match(transactionRef, targetWs.Range(targetWs.Cells(1, 1), targetWs.Cells(lastRow, 1)), 0)
    
    If IsError(matchResult) Then
        FindTransactionRow = 0
    Else
        FindTransactionRow = CLng(matchResult)
    End If
    
    On Error GoTo ErrorHandler
    Exit Function
    
ErrorHandler:
    FindTransactionRow = 0
End Function

Private Sub ClearExistingResults(sourceWs As Worksheet, lastRow As Long)
    ' Clears existing lookup results from column 3 onwards
    On Error Resume Next
    
    Dim clearRange As Range
    Set clearRange = sourceWs.Range(sourceWs.Cells(2, 3), sourceWs.Cells(lastRow, 10))
    clearRange.ClearContents
    
    On Error GoTo 0
End Sub

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

Private Sub ShowCompletionMessage(processingTime As Double)
    ' Shows completion message with processing time
    Dim msg As String
    msg = "Transaction lookup completed successfully!" & vbNewLine & vbNewLine
    msg = msg & "Processing time: " & Format(processingTime, "0.0") & " seconds"
    MsgBox msg, vbInformation, "Lookup Complete"
End Sub
