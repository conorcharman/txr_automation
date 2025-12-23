Option Explicit

' ============================================================================
' SELLER ID VALIDATION v5.5 - TEMPLATE LOOKUP ENHANCEMENTS
' ============================================================================
' Upgrades in v5.4:
' - Enhanced lookup function for specific quarters
' Upgrades in v5.5:
' - Updated PerformTemplateLookup to use columns 33 and 34 for ID and ID Type lookup
' - Added financial year input prompt to dynamically determine FY value in file paths
' Upgrades in v5.3:
' - Enhanced PerformTemplateLookup to return both column 22 and 23 concatenated with ':'
' - Modified Formula 3 to compare full correction (column 21) with lookup result (column 26)
' - Fixed template lookup logic for better accuracy
' 
' Previous upgrades in v5.2:
' - Integrated column 25, 26, 27 formula functionality into macro
' - Added incident code lookup with dynamic template selection
' - Enhanced post-processing with formula calculations
' 
' Fixed issues from v5.0:
' - Restored joint account aggregation logic
' - Fixed GetAllowedIDTypes subscript error
' - Restored proper TestIDAgainstAllPatterns functionality
' - Restored original validation logic flow
' - Enhanced error handling and logging
' ============================================================================

' ============================================================================
' CONFIGURATION MODULE
' ============================================================================

' Column mapping constants
Private Const COL_TRANSACTION_REF As Long = 1
Private Const COL_PERSON_CODE As Long = 6
Private Const COL_ACCOUNT_TYPE As Long = 7
Private Const COL_ID_VALUE As Long = 8
Private Const COL_ID_TYPE As Long = 9
Private Const COL_FNAME As Long = 10
Private Const COL_SNAME As Long = 11
Private Const COL_DOB As Long = 12
Private Const COL_GENDER As Long = 13
Private Const COL_PRIMARY_NAT As Long = 14
Private Const COL_SECONDARY_NAT As Long = 15
Private Const COL_OUTPUT As Long = 21
Private Const COL_FIELDS As Long = 22
Private Const COL_TRACKER As Long = 23
Private Const COL_ACTIONS As Long = 24
Private Const COL_FORMULA1 As Long = 25  ' Column AA formula result
Private Const COL_FORMULA2 As Long = 26  ' VLOOKUP formula result
Private Const COL_FORMULA3 As Long = 27  ' Comparison formula result

' Date formatting constants
Private Const DATE_FORMAT_SHORT As String = "dd/mm/yyyy"
Private Const DATE_REPLACE_CHAR As String = "."
Private Const DATE_TARGET_CHAR As String = "/"

' Tracker file paths
Private Const TRACKER_MAIN_PATH As String = "\\srv01.uk.ajbell.com\common\Transaction Reporting\Kaizen Reporting\Accuracy Testing\Client data remediation\Query Tracker\Transaction Reporting - Sharepoint Client Data Remediation DL_31072025.xlsx"
Private Const TRACKER_ITALIAN_PATH As String = "\\srv01.uk.ajbell.com\common\Transaction Reporting\Kaizen Reporting\Accuracy Testing\Client data remediation\Query Tracker\Transaction Reporting - Italian Fiscal Code Validation.xlsx"

' Template lookup base path (will be constructed dynamically)
Private Const TEMPLATE_BASE_PATH_ROOT As String = "F:\Transaction Reporting\Kaizen Reporting\Accuracy Testing\"

' Global variables
Private g_FinancialYear As String
Private g_IncidentCode As String
Private g_Quarter As String

' ============================================================================
' DATA STRUCTURES
' ============================================================================

' Client record structure for better data organization
Type ClientRecord
    RowIndex As Long
    TransactionRef As String
    PersonCode As String
    AccountType As String
    OriginalID As String
    OriginalIDType As String
    FirstName As String
    Surname As String
    DateOfBirth As Date
    Gender As String
    PrimaryNationality As String
    SecondaryNationality As String
    PriorityCountryCode As String
    
    ' Processing results
    FinalID As String
    FinalIDType As String
    ValidationStatus As String
    Actions As String
    TrackerStatus As String
    CorrectionFields As String
    CorrectionOutput As String
    
    ' Formula calculation results
    Formula1Result As String    ' Column AA formula result
    Formula2Result As String    ' VLOOKUP result
    Formula3Result As String    ' Comparison result
End Type

' Validation context structure
Type ValidationContext
    CountryDict As Object
    EEADict As Object
    FormatDict As Object
    RegexEngine As Object
    MainTracker As Object
    ItalianTracker As Object
    TemplateWorkbook As Object
End Type

' ============================================================================
' MAIN ENTRY POINT
' ============================================================================

Sub SellerIDValidation5_5()
    Dim startTime As Double: startTime = Timer
    
    On Error GoTo ErrorHandler
    
    ' Get financial year from user
    g_FinancialYear = GetFinancialYearFromUser()
    If g_FinancialYear = "" Then
        MsgBox "Validation cancelled - no financial year provided.", vbInformation, "Validation Cancelled"
        Exit Sub
    End If
    
    ' Get quarter from user
    g_Quarter = GetQuarterFromUser()
    If g_Quarter = "" Then
        MsgBox "Validation cancelled - no quarter provided.", vbInformation, "Validation Cancelled"
        Exit Sub
    End If
    
    ' Get incident code from user
    g_IncidentCode = GetIncidentCodeFromUser()
    If g_IncidentCode = "" Then
        MsgBox "Validation cancelled - no incident code provided.", vbInformation, "Validation Cancelled"
        Exit Sub
    End If
    
    ' Validate that the target worksheet exists
    If Not WorksheetExists("Client Data - " & g_IncidentCode) Then
        MsgBox "Worksheet 'Client Data - " & g_IncidentCode & "' not found in this workbook." & vbNewLine & vbNewLine & _
               "Please ensure the correct worksheet exists and try again.", vbExclamation, "Worksheet Not Found"
        Exit Sub
    End If
    
    ' Initialize application settings
    Call OptimizePerformance(True)
    
    ' Initialize validation context
    Dim context As ValidationContext
    If Not InitializeValidationContext(context) Then Exit Sub
    
    ' Preprocess data formatting
    Call PreprocessDataFormatting
    
    ' Load and validate data
    Dim clientRecords() As ClientRecord
    If Not LoadClientData(clientRecords, context) Then GoTo CleanupAndExit
    
    ' Process all client records
    Call ProcessClientRecords(clientRecords, context)
    
    ' Write results back to worksheet
    Call WriteResults(clientRecords)
    
    ' Calculate and write formula results
    Call CalculateFormulaResults(clientRecords, context)
    
    ' Check for joint accounts and handle aggregation (after processing)
    Call HandleJointAccountAggregation
    
    ' Show completion message
    Call ShowCompletionMessage(UBound(clientRecords) - LBound(clientRecords) + 1, Timer - startTime)
    
CleanupAndExit:
    Call CleanupResources(context)
    Call OptimizePerformance(False)
    Exit Sub
    
ErrorHandler:
    Call HandleError(Err.Number, Err.Description, "SellerIDValidation5_5")
    GoTo CleanupAndExit
End Sub

' ============================================================================
' JOINT ACCOUNT HANDLING
' ============================================================================

Private Sub HandleJointAccountAggregation()
    On Error GoTo ErrorHandler
    
    Dim ws As Worksheet
    Set ws = GetClientDataWorksheet()
    If ws Is Nothing Then
        MsgBox "Unable to access Client Data worksheet for incident code " & g_IncidentCode, vbExclamation, "Worksheet Error"
        Exit Sub
    End If
    
    Dim lastRow As Long
    lastRow = ws.Cells(ws.Rows.Count, "A").End(xlUp).Row
    If lastRow < 2 Then Exit Sub
    
    ' Check if we need to aggregate JNT accounts
    Dim jntFound As Boolean
    jntFound = False
    
    ' More efficient JNT detection using range search
    On Error Resume Next
    jntFound = Not IsError(Application.Match("JNT", ws.Range(ws.Cells(2, COL_ACCOUNT_TYPE), ws.Cells(lastRow, COL_ACCOUNT_TYPE)), 0))
    On Error GoTo ErrorHandler
    
    If jntFound Then
        Dim aggregateChoice As VbMsgBoxResult
        aggregateChoice = MsgBox("JNT (Joint) accounts detected." & vbNewLine & vbNewLine & _
                          "Would you like to aggregate joint account rows?" & vbNewLine & _
                          "(This will combine matching JNT account rows by Transaction Reference)", _
                          vbYesNo + vbQuestion, "Aggregate Joint Accounts?")
        
        If aggregateChoice = vbYes Then
            Call AggregateJNTAccounts
        End If
    End If
    
    Exit Sub
    
ErrorHandler:
    Call HandleError(Err.Number, Err.Description, "HandleJointAccountAggregation")
End Sub

Private Sub AggregateJNTAccounts()
    ' Aggregates Joint Account (JNT) rows with matching Transaction Reference
    
    On Error GoTo ErrorHandler
    
    Dim ws As Worksheet
    Set ws = GetClientDataWorksheet()
    If ws Is Nothing Then
        MsgBox "Unable to access Client Data worksheet for incident code " & g_IncidentCode, vbExclamation, "Worksheet Error"
        Exit Sub
    End If
    
    Application.ScreenUpdating = False
    Application.Calculation = xlCalculationManual
    
    Dim lastRow As Long, i As Long, j As Long
    Dim currentTxnRef As String, compareTxnRef As String
    Dim currentAccountType As String, compareAccountType As String
    Dim deleteRows As Collection
    Set deleteRows = New Collection
    Dim processedPairs As Long
    
    lastRow = ws.Cells(ws.Rows.Count, "A").End(xlUp).Row
    
    MsgBox "Starting JNT account aggregation for " & (lastRow - 1) & " records...", vbInformation, "Aggregation Starting"
    
    i = 2
    Do While i <= lastRow
        currentTxnRef = Trim(CStr(ws.Cells(i, 1).Value))
        currentAccountType = Trim(CStr(ws.Cells(i, 7).Value))
        
        If UCase(currentAccountType) = "JNT" Then
            ' Look for the next JNT row with the same transaction reference
            For j = i + 1 To lastRow
                compareTxnRef = Trim(CStr(ws.Cells(j, 1).Value))
                compareAccountType = Trim(CStr(ws.Cells(j, 7).Value))
                
                If UCase(compareAccountType) = "JNT" And compareTxnRef = currentTxnRef Then
                    Call AggregateJNTPair(ws, i, j)
                    processedPairs = processedPairs + 1
                    
                    ' Add row to deletion list
                    On Error Resume Next
                    deleteRows.Add j
                    If Err.Number <> 0 Then
                        Err.Clear
                    End If
                    On Error GoTo ErrorHandler
                    
                    Exit For ' Only aggregate one match per row
                End If
            Next j
        End If
        
        i = i + 1
        
        ' Progress indicator
        If i Mod 50 = 0 Then
            Application.StatusBar = "Aggregating JNT accounts... Row " & i & " of " & lastRow
        End If
    Loop
    
    ' Delete aggregated rows in reverse order to maintain row numbers
    If deleteRows.Count > 0 Then
        Dim deleteArray() As Long
        ReDim deleteArray(1 To deleteRows.Count)
        
        ' Copy collection to array for sorting
        For i = 1 To deleteRows.Count
            deleteArray(i) = deleteRows(i)
        Next i
        
        ' Simple bubble sort in descending order
        Dim temp As Long, swapped As Boolean
        Do
            swapped = False
            For i = 1 To UBound(deleteArray) - 1
                If deleteArray(i) < deleteArray(i + 1) Then
                    temp = deleteArray(i)
                    deleteArray(i) = deleteArray(i + 1)
                    deleteArray(i + 1) = temp
                    swapped = True
                End If
            Next i
        Loop While swapped
        
        ' Delete rows in descending order
        For i = 1 To UBound(deleteArray)
            On Error Resume Next
            ws.Rows(deleteArray(i)).Delete
            If Err.Number <> 0 Then
                Err.Clear
            End If
            On Error GoTo ErrorHandler
        Next i
        
        MsgBox "JNT aggregation completed successfully!" & vbNewLine & _
               "Processed " & processedPairs & " joint account pairs." & vbNewLine & _
               "Deleted " & UBound(deleteArray) & " duplicate rows.", vbInformation, "Aggregation Complete"
    End If
    
    Application.StatusBar = False
    Application.ScreenUpdating = True
    Application.Calculation = xlCalculationAutomatic
    
    Exit Sub
    
ErrorHandler:
    Application.StatusBar = False
    Application.ScreenUpdating = True
    Application.Calculation = xlCalculationAutomatic
    Call HandleError(Err.Number, Err.Description, "AggregateJNTAccounts")
End Sub

Private Sub AggregateJNTPair(ws As Worksheet, row1 As Long, row2 As Long)
    ' Aggregates two JNT rows into the first row
    ' Parameters:
    '   ws - worksheet reference
    '   row1 - first row (will contain aggregated data)
    '   row2 - second row (will be marked for deletion)
    
    On Error Resume Next
    
    ' Validate inputs
    If row1 <= 0 Or row2 <= 0 Or row1 = row2 Then
        Exit Sub
    End If
    
    ' Check if rows exist
    If row1 > ws.Rows.Count Or row2 > ws.Rows.Count Then
        Exit Sub
    End If
    
    ' FIRST: Capture the original correction outputs before modifying anything
    Dim originalCorr1 As String, originalCorr2 As String
    Dim originalFields1 As String, originalFields2 As String
    Dim originalID1 As String, originalID2 As String
    Dim originalIDType1 As String, originalIDType2 As String
    
    originalCorr1 = Trim(CStr(ws.Cells(row1, COL_OUTPUT).Value))
    originalCorr2 = Trim(CStr(ws.Cells(row2, COL_OUTPUT).Value))
    originalFields1 = Trim(CStr(ws.Cells(row1, COL_FIELDS).Value))
    originalFields2 = Trim(CStr(ws.Cells(row2, COL_FIELDS).Value))
    
    ' Capture original ID values for proper correction format
    originalID1 = Trim(CStr(ws.Cells(row1, COL_ID_VALUE).Value))
    originalID2 = Trim(CStr(ws.Cells(row2, COL_ID_VALUE).Value))
    originalIDType1 = Trim(CStr(ws.Cells(row1, COL_ID_TYPE).Value))
    originalIDType2 = Trim(CStr(ws.Cells(row2, COL_ID_TYPE).Value))
    
    ' SECOND: Aggregate the regular data fields with pipe delimiter
    ws.Cells(row1, COL_PERSON_CODE).Value = CombineWithPipe(ws.Cells(row1, COL_PERSON_CODE).Value, ws.Cells(row2, COL_PERSON_CODE).Value)
    ws.Cells(row1, COL_ID_VALUE).Value = CombineWithPipe(ws.Cells(row1, COL_ID_VALUE).Value, ws.Cells(row2, COL_ID_VALUE).Value)
    ws.Cells(row1, COL_ID_TYPE).Value = CombineWithPipe(ws.Cells(row1, COL_ID_TYPE).Value, ws.Cells(row2, COL_ID_TYPE).Value)
    ws.Cells(row1, COL_FNAME).Value = CombineWithPipe(ws.Cells(row1, COL_FNAME).Value, ws.Cells(row2, COL_FNAME).Value)
    ws.Cells(row1, COL_SNAME).Value = CombineWithPipe(ws.Cells(row1, COL_SNAME).Value, ws.Cells(row2, COL_SNAME).Value)
    ws.Cells(row1, COL_DOB).Value = CombineWithPipe(ws.Cells(row1, COL_DOB).Value, ws.Cells(row2, COL_DOB).Value)
    
    ' FIX: Properly combine gender values without overwriting
    Dim gender1 As String, gender2 As String
    gender1 = Trim(CStr(ws.Cells(row1, COL_GENDER).Value))
    gender2 = Trim(CStr(ws.Cells(row2, COL_GENDER).Value))
    ws.Cells(row1, COL_GENDER).Value = CombineWithPipe(gender1, gender2)
    
    ws.Cells(row1, COL_PRIMARY_NAT).Value = CombineWithPipe(ws.Cells(row1, COL_PRIMARY_NAT).Value, ws.Cells(row2, COL_PRIMARY_NAT).Value)
    ws.Cells(row1, COL_SECONDARY_NAT).Value = CombineWithPipe(ws.Cells(row1, COL_SECONDARY_NAT).Value, ws.Cells(row2, COL_SECONDARY_NAT).Value)
    
    ' THIRD: Build proper correction outputs in the correct format
    Dim finalOutput As String, finalFields As String
    
    ' Parse and rebuild corrections to ensure proper format
    If originalCorr1 <> "" And originalCorr2 <> "" Then
        ' Both rows have corrections - combine them properly
        Dim corr1ID As String, corr1Type As String
        Dim corr2ID As String, corr2Type As String
        
        ' Parse first correction
        If InStr(originalCorr1, ":") > 0 Then
            corr1ID = Split(originalCorr1, ":")(0)
            corr1Type = Split(originalCorr1, ":")(1)
        Else
            corr1ID = originalID1
            corr1Type = originalIDType1
        End If
        
        ' Parse second correction
        If InStr(originalCorr2, ":") > 0 Then
            corr2ID = Split(originalCorr2, ":")(0)
            corr2Type = Split(originalCorr2, ":")(1)
        Else
            corr2ID = originalID2
            corr2Type = originalIDType2
        End If
        
        ' Build proper combined format: ID1:Type1|ID2:Type2
        finalOutput = corr1ID & ":" & corr1Type & "|" & corr2ID & ":" & corr2Type
        finalFields = "ID:IDT|ID:IDT"
        
    ElseIf originalCorr1 <> "" Then
        ' Only first row has correction
        If InStr(originalCorr1, ":") > 0 Then
            finalOutput = originalCorr1 & "|" & originalID2 & ":" & originalIDType2
        Else
            finalOutput = originalID1 & ":" & originalIDType1 & "|" & originalID2 & ":" & originalIDType2
        End If
        finalFields = "ID:IDT|ID:IDT"
        
    ElseIf originalCorr2 <> "" Then
        ' Only second row has correction
        If InStr(originalCorr2, ":") > 0 Then
            finalOutput = originalID1 & ":" & originalIDType1 & "|" & originalCorr2
        Else
            finalOutput = originalID1 & ":" & originalIDType1 & "|" & originalID2 & ":" & originalIDType2
        End If
        finalFields = "ID:IDT|ID:IDT"
        
    Else
        ' Neither row has corrections - leave empty
        finalOutput = ""
        finalFields = ""
    End If
    
    ' Set the final correction values
    ws.Cells(row1, COL_OUTPUT).Value = finalOutput
    ws.Cells(row1, COL_FIELDS).Value = finalFields
    
    ' FOURTH: Combine tracker and actions
    ws.Cells(row1, COL_TRACKER).Value = CombineWithPipe(ws.Cells(row1, COL_TRACKER).Value, ws.Cells(row2, COL_TRACKER).Value)
    ws.Cells(row1, COL_ACTIONS).Value = CombineWithPipe(ws.Cells(row1, COL_ACTIONS).Value, ws.Cells(row2, COL_ACTIONS).Value)
    
    If Err.Number <> 0 Then
        Err.Clear
    End If
End Sub

Private Function CombineWithPipe(value1 As Variant, value2 As Variant) As String
    ' Combines two values with a pipe delimiter
    ' Handles dates properly and skips delimiter if either value is blank
    
    Dim str1 As String, str2 As String
    
    ' Handle different data types properly
    If IsDate(value1) Then
        str1 = Format(CDate(value1), "dd/mm/yyyy")
    ElseIf IsNull(value1) Or IsEmpty(value1) Then
        str1 = ""
    Else
        str1 = Trim(CStr(value1))
    End If
    
    If IsDate(value2) Then
        str2 = Format(CDate(value2), "dd/mm/yyyy")
    ElseIf IsNull(value2) Or IsEmpty(value2) Then
        str2 = ""
    Else
        str2 = Trim(CStr(value2))
    End If
    
    ' Combine with pipe delimiter
    If str1 = "" And str2 = "" Then
        CombineWithPipe = ""
    ElseIf str1 = "" Then
        CombineWithPipe = str2
    ElseIf str2 = "" Then
        CombineWithPipe = str1
    Else
        CombineWithPipe = str1 & "|" & str2
    End If
End Function

' ============================================================================
' INITIALIZATION FUNCTIONS
' ============================================================================

Private Function InitializeValidationContext(ByRef context As ValidationContext) As Boolean
    On Error GoTo ErrorHandler
    
    ' Initialize dictionaries
    Set context.CountryDict = CreateObject("Scripting.Dictionary")
    Set context.EEADict = CreateObject("Scripting.Dictionary")
    Set context.FormatDict = CreateObject("Scripting.Dictionary")
    Set context.RegexEngine = CreateObject("VBScript.RegExp")
    
    ' Load reference data
    If Not LoadCountryMappings(context) Then GoTo ErrorExit
    If Not LoadIDFormats(context) Then GoTo ErrorExit
    If Not LoadTrackerWorkbooks(context) Then GoTo ErrorExit
    If Not LoadTemplateWorkbook(context) Then GoTo ErrorExit
    
    InitializeValidationContext = True
    Exit Function
    
ErrorHandler:
    Call HandleError(Err.Number, Err.Description, "InitializeValidationContext")
ErrorExit:
    InitializeValidationContext = False
End Function

Private Function LoadCountryMappings(ByRef context As ValidationContext) As Boolean
    On Error GoTo ErrorHandler
    
    Dim countryWs As Worksheet
    Set countryWs = GetWorksheet("Country Codes")
    If countryWs Is Nothing Then GoTo ErrorExit
    
    Dim lastRow As Long
    lastRow = countryWs.Cells(countryWs.Rows.Count, "A").End(xlUp).Row
    If lastRow < 2 Then GoTo ErrorExit
    
    Dim i As Long
    For i = 2 To lastRow
        Dim countryName As String, iso2Code As String, iso3Code As String, eeaStatus As String
        countryName = Trim(CStr(countryWs.Cells(i, 1).Value))
        iso2Code = Trim(UCase(CStr(countryWs.Cells(i, 2).Value)))
        iso3Code = Trim(UCase(CStr(countryWs.Cells(i, 3).Value)))
        eeaStatus = Trim(UCase(CStr(countryWs.Cells(i, 4).Value)))
        
        If IsValidCountryEntry(countryName, iso2Code, iso3Code, eeaStatus) Then
            context.CountryDict(iso3Code) = iso2Code
            context.CountryDict(iso2Code) = iso2Code
            context.EEADict(iso2Code) = (eeaStatus = "Y")
        End If
    Next i
    
    LoadCountryMappings = (context.CountryDict.Count > 0)
    Exit Function
    
ErrorHandler:
    Call HandleError(Err.Number, Err.Description, "LoadCountryMappings")
ErrorExit:
    LoadCountryMappings = False
End Function

Private Function LoadIDFormats(ByRef context As ValidationContext) As Boolean
    On Error GoTo ErrorHandler
    
    Dim formatWs As Worksheet
    Set formatWs = GetWorksheet("ID Formats")
    If formatWs Is Nothing Then GoTo ErrorExit
    
    Dim lastRow As Long
    lastRow = formatWs.Cells(formatWs.Rows.Count, "A").End(xlUp).Row
    If lastRow < 2 Then GoTo ErrorExit
    
    context.FormatDict.RemoveAll
    
    Dim i As Long, formatCount As Long
    For i = 2 To lastRow
        Dim countryCode As String, idType As String, regexPattern As String
        countryCode = Trim(UCase(CStr(formatWs.Cells(i, 1).Value)))
        idType = Trim(UCase(CStr(formatWs.Cells(i, 2).Value)))
        regexPattern = Trim(CStr(formatWs.Cells(i, 3).Value))
        
        If countryCode <> "" And idType <> "" And regexPattern <> "" Then
            Dim key As String
            key = BuildFormatKey(countryCode, idType, context.FormatDict)
            context.FormatDict(key) = regexPattern
            formatCount = formatCount + 1
        End If
    Next i
    
    LoadIDFormats = (formatCount > 0)
    Exit Function
    
ErrorHandler:
    Call HandleError(Err.Number, Err.Description, "LoadIDFormats")
ErrorExit:
    LoadIDFormats = False
End Function

Private Function LoadTrackerWorkbooks(ByRef context As ValidationContext) As Boolean
    On Error GoTo ErrorHandler
    
    ' Load main tracker (non-critical)
    On Error Resume Next
    Dim wb1 As Workbook
    Set wb1 = Workbooks.Open(TRACKER_MAIN_PATH, False, True)
    If Not wb1 Is Nothing Then
        Set context.MainTracker = wb1.Sheets("Client Data - Outstanding")
    End If
    
    ' Load Italian tracker (non-critical)
    Dim wb2 As Workbook
    Set wb2 = Workbooks.Open(TRACKER_ITALIAN_PATH, False, True)
    If Not wb2 Is Nothing Then
        Set context.ItalianTracker = wb2.Sheets("IT Fiscal Codes Reviewed")
    End If
    On Error GoTo ErrorHandler
    
    LoadTrackerWorkbooks = True ' Always return true as trackers are optional
    Exit Function
    
ErrorHandler:
    Call HandleError(Err.Number, Err.Description, "LoadTrackerWorkbooks")
    LoadTrackerWorkbooks = False
End Function

Private Function GetFinancialYearFromUser() As String
    ' Get financial year from user input with validation
    On Error GoTo ErrorHandler
    
    Dim userInput As String
    Dim validInput As Boolean
    validInput = False
    
    Do While Not validInput
        userInput = InputBox("Please enter the financial year for testing:" & vbNewLine & vbNewLine & _
                           "Examples: FY25, FY26, FY27" & vbNewLine & vbNewLine & _
                           "This will determine which financial year folder to use for template lookup.", _
                           "Financial Year Input", "FY25")
        
        ' Check if user cancelled
        If userInput = "" Then
            GetFinancialYearFromUser = ""
            Exit Function
        End If
        
        ' Validate format (basic validation)
        userInput = Trim(UCase(userInput))
        If Len(userInput) >= 4 And Left(userInput, 2) = "FY" And IsNumeric(Mid(userInput, 3)) Then
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
        userInput = InputBox("Please enter the quarter for testing:" & vbNewLine & vbNewLine & _
                           "Examples: Q1, Q2, Q3, Q4" & vbNewLine & vbNewLine & _
                           "This will determine which quarter folder to use for template lookup.", _
                           "Quarter Input", "Q3")
        
        ' Check if user cancelled
        If userInput = "" Then
            GetQuarterFromUser = ""
            Exit Function
        End If
        
        ' Validate format (basic validation)
        userInput = Trim(UCase(userInput))
        If userInput = "Q1" Or userInput = "Q2" Or userInput = "Q3" Or userInput = "Q4" Then
            validInput = True
            GetQuarterFromUser = userInput
        Else
            MsgBox "Invalid quarter format. Please enter Q1, Q2, Q3, or Q4.", vbExclamation, "Invalid Format"
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
        userInput = InputBox("Please enter the incident code for template lookup:" & vbNewLine & vbNewLine & _
                           "Examples: 16_19, 16_21, 16_23" & vbNewLine & vbNewLine & _
                           "This will determine which template file to use for VLOOKUP operations.", _
                           "Incident Code Input", "16_19")
        
        ' Check if user cancelled
        If userInput = "" Then
            GetIncidentCodeFromUser = ""
            Exit Function
        End If
        
        ' Validate format (basic validation)
        userInput = Trim(userInput)
        If Len(userInput) >= 4 And InStr(userInput, "_") > 0 Then
            ' Check if template file exists
            Dim templatePath As String
            templatePath = BuildTemplatePath(userInput)
            
            If Dir(Replace(templatePath, "[", "")) <> "" Then
                validInput = True
                GetIncidentCodeFromUser = userInput
            Else
                MsgBox "Template file not found: " & templatePath & vbNewLine & vbNewLine & _
                       "Please check the incident code and try again.", vbExclamation, "File Not Found"
            End If
        Else
            MsgBox "Invalid incident code format. Please use format like '16_19'.", vbExclamation, "Invalid Format"
        End If
    Loop
    
    Exit Function
    
ErrorHandler:
    Call HandleError(Err.Number, Err.Description, "GetIncidentCodeFromUser")
    GetIncidentCodeFromUser = ""
End Function

Private Function LoadTemplateWorkbook(ByRef context As ValidationContext) As Boolean
    On Error GoTo ErrorHandler
    
    ' Build template file path using dynamic quarter
    Dim templatePath As String
    templatePath = BuildTemplatePath(g_IncidentCode)
    
    ' Load template workbook (non-critical)
    On Error Resume Next
    Dim templateWb As Workbook
    Set templateWb = Workbooks.Open(templatePath, False, True)
    If Not templateWb Is Nothing Then
        Set context.TemplateWorkbook = templateWb.Sheets("Template")
    End If
    On Error GoTo ErrorHandler
    
    LoadTemplateWorkbook = True ' Always return true as template is optional
    Exit Function
    
ErrorHandler:
    Call HandleError(Err.Number, Err.Description, "LoadTemplateWorkbook")
    LoadTemplateWorkbook = False
End Function

' ============================================================================
' DATA LOADING AND PREPROCESSING
' ============================================================================

Private Sub PreprocessDataFormatting()
    On Error GoTo ErrorHandler
    
    Dim ws As Worksheet
    Set ws = GetClientDataWorksheet()
    If ws Is Nothing Then
        MsgBox "Unable to access Client Data worksheet for incident code " & g_IncidentCode, vbExclamation, "Worksheet Error"
        Exit Sub
    End If
    
    ' Format date columns
    ws.Columns(COL_DOB).NumberFormat = DATE_FORMAT_SHORT
    ws.Columns(20).NumberFormat = DATE_FORMAT_SHORT
    
    ' Replace dots with slashes in date columns
    Dim lastRow As Long
    lastRow = ws.Cells(ws.Rows.Count, "A").End(xlUp).Row
    
    Dim cellRange As Range
    Set cellRange = ws.Range(ws.Cells(1, COL_DOB), ws.Cells(lastRow, COL_DOB))
    cellRange.Replace What:=DATE_REPLACE_CHAR, Replacement:=DATE_TARGET_CHAR, LookAt:=xlPart
    
    Set cellRange = ws.Range(ws.Cells(1, 20), ws.Cells(lastRow, 20))
    cellRange.Replace What:=DATE_REPLACE_CHAR, Replacement:=DATE_TARGET_CHAR, LookAt:=xlPart
    
    Exit Sub
    
ErrorHandler:
    Call HandleError(Err.Number, Err.Description, "PreprocessDataFormatting")
End Sub

Private Function LoadClientData(ByRef clientRecords() As ClientRecord, ByRef context As ValidationContext) As Boolean
    On Error GoTo ErrorHandler
    
    Dim ws As Worksheet
    Set ws = GetClientDataWorksheet()
    If ws Is Nothing Then
        MsgBox "Unable to access Client Data worksheet for incident code " & g_IncidentCode, vbExclamation, "Worksheet Error"
        GoTo ErrorExit
    End If
    
    Dim lastRow As Long
    lastRow = ws.Cells(ws.Rows.Count, "A").End(xlUp).Row
    If lastRow < 2 Then GoTo ErrorExit
    
    ReDim clientRecords(1 To lastRow - 1) As ClientRecord
    
    Dim i As Long, recordIndex As Long
    For i = 2 To lastRow
        recordIndex = i - 1
        
        With clientRecords(recordIndex)
            .RowIndex = i
            .TransactionRef = Trim(CStr(ws.Cells(i, COL_TRANSACTION_REF).Value))
            .PersonCode = Trim(CStr(ws.Cells(i, COL_PERSON_CODE).Value))
            .AccountType = Trim(CStr(ws.Cells(i, COL_ACCOUNT_TYPE).Value))
            .OriginalID = Trim(CStr(ws.Cells(i, COL_ID_VALUE).Value))
            .OriginalIDType = Trim(CStr(ws.Cells(i, COL_ID_TYPE).Value))
            .FirstName = Trim(CStr(ws.Cells(i, COL_FNAME).Value))
            .Surname = Trim(CStr(ws.Cells(i, COL_SNAME).Value))
            .Gender = Trim(CStr(ws.Cells(i, COL_GENDER).Value))
            
            ' Enhanced date handling
            .DateOfBirth = ParseDateSafely(ws.Cells(i, COL_DOB).Value)
            
            ' Load and process nationalities
            Dim primaryNat As String, secondaryNat As String
            primaryNat = Trim(CStr(ws.Cells(i, COL_PRIMARY_NAT).Value))
            secondaryNat = Trim(CStr(ws.Cells(i, COL_SECONDARY_NAT).Value))
            
            Dim priorityResult() As String
            priorityResult = DeterminePriorityNationalities(primaryNat, secondaryNat, context)
            .PriorityCountryCode = priorityResult(0)
            .PrimaryNationality = priorityResult(1)
            .SecondaryNationality = priorityResult(2)
            
            ' Initialize processing results
            .FinalID = .OriginalID
            .FinalIDType = .OriginalIDType
            .ValidationStatus = "Unknown"
            .Actions = ""
            .TrackerStatus = "Not On tracker"
            .CorrectionFields = ""
            .CorrectionOutput = ""
            
            ' Initialize formula results
            .Formula1Result = ""
            .Formula2Result = ""
            .Formula3Result = ""
        End With
        
        ' Update nationality columns with Alpha-2 codes
        ws.Cells(i, COL_PRIMARY_NAT).Value = clientRecords(recordIndex).PrimaryNationality
        ws.Cells(i, COL_SECONDARY_NAT).Value = clientRecords(recordIndex).SecondaryNationality
    Next i
    
    LoadClientData = True
    Exit Function
    
ErrorHandler:
    Call HandleError(Err.Number, Err.Description, "LoadClientData")
ErrorExit:
    LoadClientData = False
End Function

' ============================================================================
' CORE PROCESSING ENGINE - RESTORED v4.5 LOGIC
' ============================================================================

Private Sub ProcessClientRecords(ByRef clientRecords() As ClientRecord, ByRef context As ValidationContext)
    On Error GoTo ErrorHandler
    
    Dim i As Long
    For i = LBound(clientRecords) To UBound(clientRecords)
        If i Mod 50 = 0 Then
            Application.StatusBar = "Processing record " & i & " of " & UBound(clientRecords)
        End If
        
        Call ProcessSingleClient(clientRecords(i), context)
    Next i
    
    Application.StatusBar = False
    Exit Sub
    
ErrorHandler:
    Application.StatusBar = False
    Call HandleError(Err.Number, Err.Description, "ProcessClientRecords")
End Sub

Private Sub ProcessSingleClient(ByRef client As ClientRecord, ByRef context As ValidationContext)
    On Error GoTo ErrorHandler
    
    ' Skip if no valid country code
    If client.PriorityCountryCode = "" Then
        client.ValidationStatus = "Invalid Country"
        client.Actions = "Skip - Invalid Nationality"
        Exit Sub
    End If
    
    ' Initialize validation variables (restored from v4.5)
    Dim originalTypeValid As Boolean, correctTypeFound As String
    Dim correctTypeLogicValid As Boolean, concatGenerated As Boolean
    originalTypeValid = False
    correctTypeFound = ""
    correctTypeLogicValid = False
    concatGenerated = False
    
    ' Step 1: Validate original ID and type (v4.5 logic)
    If client.OriginalIDType <> "" Then
        If TestIDAgainstAllPatterns(client.OriginalID, client.PriorityCountryCode, client.OriginalIDType, context.FormatDict, context.RegexEngine) Then
            ' Test logic validity
            Dim idForLogic As String
            If Len(client.OriginalID) > 2 And Left(UCase(client.OriginalID), 2) = UCase(client.PriorityCountryCode) Then
                idForLogic = Mid(client.OriginalID, 3)
            Else
                idForLogic = client.OriginalID
            End If
            
            Dim logicValid As Boolean
            logicValid = ValidateIDLogic(idForLogic, client.OriginalIDType, client.PriorityCountryCode, Format(client.DateOfBirth, "yyyymmdd"), client.Gender)
            
            If logicValid Then
                ' Original type is completely valid
                originalTypeValid = True
                client.FinalIDType = client.OriginalIDType
            Else
                ' Original type has valid format but logic issues
                client.Actions = "Valid format - Logic query"
            End If
        End If
    End If
    
    ' Step 2: If original type is not completely valid, test against other allowed types (v4.5 logic)
    ' Skip alternative type testing for Rest of World countries (no formats defined)
    If Not originalTypeValid And client.OriginalID <> "" And HasCountryFormats(client.PriorityCountryCode, context.FormatDict) Then
        Dim allowedTypes As Variant
        allowedTypes = Array("NIDN", "PASSPORT", "CONCAT", "CCPT", "PASS", "DLIC")
        
        Dim testType As Variant
        For Each testType In allowedTypes
            If CStr(testType) <> client.OriginalIDType Then
                If TestIDAgainstAllPatterns(client.OriginalID, client.PriorityCountryCode, CStr(testType), context.FormatDict, context.RegexEngine) Then
                    Dim idForLogicAlt As String
                    If Len(client.OriginalID) > 2 And Left(UCase(client.OriginalID), 2) = UCase(client.PriorityCountryCode) Then
                        idForLogicAlt = Mid(client.OriginalID, 3)
                    Else
                        idForLogicAlt = client.OriginalID
                    End If
                    
                    Dim altLogicValid As Boolean
                    altLogicValid = ValidateIDLogic(idForLogicAlt, CStr(testType), client.PriorityCountryCode, Format(client.DateOfBirth, "yyyymmdd"), client.Gender)
                    
                    If correctTypeFound = "" Then
                        correctTypeFound = CStr(testType)
                        correctTypeLogicValid = altLogicValid
                    End If
                    
                    If altLogicValid Then
                        correctTypeFound = CStr(testType)
                        correctTypeLogicValid = True
                        Exit For
                    End If
                End If
            End If
        Next testType
    End If
    
    ' Step 3: Handle validation results based on what we found (v4.5 logic)
    If originalTypeValid Then
        ' Original ID and type are completely valid
        If client.PriorityCountryCode = "IT" And client.FinalIDType = "NIDN" Then
            client.Actions = "Pass - Check Tracker"
        Else
            client.Actions = "Pass"
        End If
        client.ValidationStatus = "Valid"
    ElseIf correctTypeFound <> "" Then
        ' Found alternative valid type
        client.FinalIDType = correctTypeFound
        client.CorrectionFields = "ID:IDT"
        client.CorrectionOutput = client.FinalID & ":" & client.FinalIDType
        
        If correctTypeLogicValid Then
            client.ValidationStatus = "Valid"
            If client.PriorityCountryCode = "IT" And correctTypeFound = "NIDN" Then
                client.Actions = "Pass - Check Tracker"
            Else
                client.Actions = "Valid format - ID Type updated"
            End If
        Else
            client.ValidationStatus = "Logic Issue"
            client.Actions = "Valid format - Logic query - ID Type updated"
        End If
    Else
        ' No valid format found - try CONCAT generation
        If TryGenerateCONCAT(client, context) Then
            concatGenerated = True
        Else
            ' Fall back to person code ID
            Call GenerateFallbackID(client)
        End If
    End If
    
    ' Step 4: Apply Italian tracker logic
    If client.PriorityCountryCode = "IT" Then
        Call ApplyItalianTrackerLogic(client, context)
    End If
    
    ' Step 5: Apply Kaizen Error Lookup Validation (NEW)
    If originalTypeValid Then
        Call ApplyKaizenErrorLookupValidation(client, context)
    End If
    
    Exit Sub
    
ErrorHandler:
    Call HandleError(Err.Number, Err.Description, "ProcessSingleClient")
End Sub

' ============================================================================
' VALIDATION FUNCTIONS - RESTORED v4.5 LOGIC
' ============================================================================

Private Function TestIDAgainstAllPatterns(testID As String, countryCode As String, idType As String, dict As Object, regex As Object) As Boolean
    ' This function tests an ID against all available patterns for a given country:idType combination
    ' It also handles stripping the ISO-2 country code prefix if present
    ' Restored from v4.5 with the fixed logic
    
    On Error Resume Next
    Dim baseKey     As String
    Dim patternIndex As Long
    Dim currentKey  As String
    Dim regexPattern As String
    Dim idToTest    As String
    Dim originalID  As String
    
    originalID = Trim(UCase(testID))
    baseKey = Trim(UCase(countryCode)) & ":" & Trim(UCase(idType))
    patternIndex = 1
    
    ' Test both the original ID and the ID with country code prefix removed
    Dim testVersions As Variant
    
    ' If ID starts with the country code, create version without it
    If Len(originalID) > 2 And Left(originalID, 2) = Trim(UCase(countryCode)) Then
        testVersions = Array(originalID, Mid(originalID, 3))        ' Original and without country prefix
    Else
        testVersions = Array(originalID)        ' Just original
    End If
    
    ' Test against all available patterns for this country:idType combination
    Do While dict.exists(baseKey & ":" & patternIndex)
        currentKey = baseKey & ":" & patternIndex
        regexPattern = dict(currentKey)
        
        ' Force clean any malformed patterns - check if pattern is wrapped in extra brackets
        If Left(regexPattern, 1) = "[" And Right(regexPattern, 1) = "]" And _
           Len(regexPattern) > 2 And InStr(2, regexPattern, "[") > 0 Then
            regexPattern = Mid(regexPattern, 2, Len(regexPattern) - 2)
        End If
        
        If regexPattern <> "" Then
            regex.Pattern = regexPattern
            regex.IgnoreCase = True
            regex.Global = False
            
            ' Test both versions of the ID (with and without country prefix)
            Dim testVersion As Variant
            For Each testVersion In testVersions
                idToTest = CStr(testVersion)
                
                Dim testResult As Boolean
                testResult = regex.Test(idToTest)
                
                If idToTest <> "" And testResult Then
                    TestIDAgainstAllPatterns = True
                    Exit Function
                End If
            Next testVersion
        End If
        
        patternIndex = patternIndex + 1
    Loop
    
    TestIDAgainstAllPatterns = False
    On Error GoTo 0
End Function

' ============================================================================
' CORRECTION GENERATION
' ============================================================================

Private Function TryGenerateCONCAT(ByRef client As ClientRecord, ByRef context As ValidationContext) As Boolean
    On Error GoTo ErrorHandler
    
    ' Check eligibility
    If Not IsCONCATEligible(client, context) Then
        TryGenerateCONCAT = False
        Exit Function
    End If
    
    ' Generate CONCAT ID
    Dim concatID As String
    concatID = BuildCONCATID(client)
    
    ' Test generated CONCAT
    If TestIDAgainstAllPatterns(concatID, client.PriorityCountryCode, "CONCAT", context.FormatDict, context.RegexEngine) Then
        client.FinalID = concatID
        client.FinalIDType = "CONCAT"
        client.ValidationStatus = "Corrected"
        client.Actions = "Fail - Replaced With CONCAT"
        client.CorrectionFields = "ID:IDT"
        client.CorrectionOutput = concatID & ":" & "CONCAT"
        TryGenerateCONCAT = True
    Else
        TryGenerateCONCAT = False
    End If
    
    Exit Function
    
ErrorHandler:
    Call HandleError(Err.Number, Err.Description, "TryGenerateCONCAT")
    TryGenerateCONCAT = False
End Function

Private Function IsCONCATEligible(ByRef client As ClientRecord, ByRef context As ValidationContext) As Boolean
    IsCONCATEligible = (client.DateOfBirth <> 0 And _
                       client.FirstName <> "" And _
                       client.Surname <> "" And _
                       context.FormatDict.exists(client.PriorityCountryCode & ":CONCAT:1"))
End Function

Private Function BuildCONCATID(ByRef client As ClientRecord) As String
    Dim dateStr As String
    dateStr = Format(client.DateOfBirth, "yyyymmdd")
    
    Dim cleanFirstName As String, cleanSurname As String
    cleanFirstName = CleanNameForCONCAT(client.FirstName, False)
    cleanSurname = CleanNameForCONCAT(client.Surname, True)
    
    BuildCONCATID = client.PriorityCountryCode & dateStr & cleanFirstName & cleanSurname
End Function

Private Function HasCountryFormats(countryCode As String, formatDict As Object) As Boolean
    ' Check if a country has ANY ID format patterns defined
    ' Used to distinguish between countries with defined formats vs rest of world
    ' Returns True if country has at least one format defined, False otherwise
    
    Dim idTypes As Variant
    idTypes = Array("NIDN", "CONCAT", "CCPT", "TIN")
    
    Dim idType As Variant
    For Each idType In idTypes
        If formatDict.exists(countryCode & ":" & CStr(idType) & ":1") Then
            HasCountryFormats = True
            Exit Function
        End If
    Next idType
    
    HasCountryFormats = False
End Function

Private Sub GenerateFallbackID(ByRef client As ClientRecord)
    client.FinalID = client.PriorityCountryCode & client.PersonCode
    client.FinalIDType = "NIDN"
    client.ValidationStatus = "Corrected"
    client.Actions = "Fail - Replaced With fallback"
    client.CorrectionFields = "ID:IDT"
    client.CorrectionOutput = client.FinalID & ":" & client.FinalIDType
End Sub

' ============================================================================
' ITALIAN TRACKER LOGIC
' ============================================================================

Private Sub ApplyItalianTrackerLogic(ByRef client As ClientRecord, ByRef context As ValidationContext)
    On Error GoTo ErrorHandler
    
    ' Get tracker status
    client.TrackerStatus = GetTrackerStatus(client, context)
    
    ' Apply specific logic based on tracker status and current actions
    If client.Actions = "Pass - Check Tracker" Then
        If client.TrackerStatus = "Not Started" Or client.TrackerStatus = "Not On tracker" Or _
           client.TrackerStatus = "In Progress" Or client.TrackerStatus = "Awaiting Response" Then
            ' Generate fallback correction as requested
            Call GenerateFallbackID(client)
            client.Actions = "Pass - Check Tracker - Replaced With fallback"
        ElseIf client.TrackerStatus = "Complete" Then
            client.Actions = "Pass - Check Tracker - Complete"
            ' Keep original values
            client.CorrectionFields = ""
            client.CorrectionOutput = ""
        End If
    End If
    
    Exit Sub
    
ErrorHandler:
    Call HandleError(Err.Number, Err.Description, "ApplyItalianTrackerLogic")
End Sub

Private Function GetTrackerStatus(ByRef client As ClientRecord, ByRef context As ValidationContext) As String
    On Error GoTo ErrorHandler
    
    GetTrackerStatus = "Not On tracker"
    
    ' Check Italian tracker first
    If Not context.ItalianTracker Is Nothing Then
        On Error Resume Next
        Dim result As Variant
        result = Application.VLookup(client.PersonCode, context.ItalianTracker.Range("C:G"), 5, False)
        If Not IsError(result) And Not IsEmpty(result) And Trim(CStr(result)) <> "" Then
            GetTrackerStatus = Trim(CStr(result))
            Exit Function
        End If
        On Error GoTo ErrorHandler
    End If
    
    ' Check main tracker
    If Not context.MainTracker Is Nothing Then
        On Error Resume Next
        result = Application.VLookup(client.PersonCode, context.MainTracker.Range("J:N"), 5, False)
        If Not IsError(result) And Not IsEmpty(result) And Trim(CStr(result)) <> "" Then
            GetTrackerStatus = Trim(CStr(result))   
        End If
        On Error GoTo ErrorHandler
    End If
    
    Exit Function
    
ErrorHandler:
    GetTrackerStatus = "Not On tracker"
End Function

' ============================================================================
' KAIZEN ERROR LOOKUP VALIDATION
' ============================================================================

Private Sub ApplyKaizenErrorLookupValidation(ByRef client As ClientRecord, ByRef context As ValidationContext)
    ' New Step 5: Validate passed records against Kaizen error lookup
    ' Only applies to records that have originalTypeValid = True AND no correction already generated
    On Error GoTo ErrorHandler
    
    ' Skip if record already has a correction from original testing logic
    If client.CorrectionOutput <> "" Then
        Exit Sub
    End If
    
    ' Get the expected ID:IDType from template lookup
    Dim expectedLookupResult As String
    expectedLookupResult = PerformTemplateLookup(client.TransactionRef, context.TemplateWorkbook)
    
    ' Skip if no lookup result available
    If expectedLookupResult = "" Then
        Exit Sub
    End If
    
    ' Parse the expected result (format: "ExpectedID:ExpectedIDType")
    Dim expectedParts() As String
    Dim expectedID As String, expectedIDType As String
    
    If InStr(expectedLookupResult, ":") > 0 Then
        expectedParts = Split(expectedLookupResult, ":")
        expectedID = Trim(expectedParts(0))
        If UBound(expectedParts) >= 1 Then
            expectedIDType = Trim(expectedParts(1))
        Else
            expectedIDType = ""
        End If
    Else
        ' Handle case where lookup result doesn't contain colon
        expectedID = Trim(expectedLookupResult)
        expectedIDType = ""
    End If
    
    ' Compare actual vs expected
    Dim actualID As String, actualIDType As String
    actualID = client.OriginalID
    actualIDType = client.OriginalIDType
    
    ' Check if either component doesn't match
    Dim idMatches As Boolean, typeMatches As Boolean
    idMatches = (actualID = expectedID)
    typeMatches = (actualIDType = expectedIDType)
    
    ' If either doesn't match, convert to error state with correction
    If Not idMatches Or Not typeMatches Then
        ' Set correction output to original values (they passed validation but don't match template)
        client.CorrectionOutput = actualID & ":" & actualIDType
        client.CorrectionFields = "ID:IDT"
        client.ValidationStatus = "Template Mismatch"
        ' Note: Actions column remains unchanged (still shows "Pass")
    End If
    
    Exit Sub
    
ErrorHandler:
    Call HandleError(Err.Number, Err.Description, "ApplyKaizenErrorLookupValidation")
End Sub

' ============================================================================
' OUTPUT FUNCTIONS
' ============================================================================

Private Sub WriteResults(ByRef clientRecords() As ClientRecord)
    On Error GoTo ErrorHandler
    
    Dim ws As Worksheet
    Set ws = GetClientDataWorksheet()
    If ws Is Nothing Then
        MsgBox "Unable to access Client Data worksheet for incident code " & g_IncidentCode, vbExclamation, "Worksheet Error"
        Exit Sub
    End If
    
    Dim i As Long
    For i = LBound(clientRecords) To UBound(clientRecords)
        With clientRecords(i)
            ws.Cells(.RowIndex, COL_OUTPUT).Value = .CorrectionOutput
            ws.Cells(.RowIndex, COL_FIELDS).Value = .CorrectionFields
            ws.Cells(.RowIndex, COL_TRACKER).Value = .TrackerStatus
            ws.Cells(.RowIndex, COL_ACTIONS).Value = .Actions
        End With
    Next i
    
    Exit Sub
    
ErrorHandler:
    Call HandleError(Err.Number, Err.Description, "WriteResults")
End Sub

Private Sub CalculateFormulaResults(ByRef clientRecords() As ClientRecord, ByRef context As ValidationContext)
    ' Calculate and populate the three formula columns (25, 26, 27)
    On Error GoTo ErrorHandler
    
    Dim ws As Worksheet
    Set ws = GetClientDataWorksheet()
    If ws Is Nothing Then
        MsgBox "Unable to access Client Data worksheet for incident code " & g_IncidentCode, vbExclamation, "Worksheet Error"
        Exit Sub
    End If
    
    Dim i As Long
    For i = LBound(clientRecords) To UBound(clientRecords)
        With clientRecords(i)
            ' Formula 2: VLOOKUP against template (calculate this first)
            .Formula2Result = PerformTemplateLookup(.TransactionRef, context.TemplateWorkbook)
            
            ' Formula 3: Comparison logic (compare correction output with template lookup result)
            .Formula3Result = CalculateFormula3(.CorrectionOutput, .Formula2Result)
            
            ' Formula 1: =IF(AA2=TRUE,"N",IF(AA2=FALSE,"Y","N"))
            ' Column AA is column 27 (Formula3Result), so check if match is TRUE/FALSE
            If .Formula3Result = "TRUE" Then
                .Formula1Result = "N"  ' No error - match found
            ElseIf .Formula3Result = "FALSE" Then
                .Formula1Result = "Y"  ' Error - no match
            Else
                .Formula1Result = "N"  ' Default to no error for empty/unknown values
            End If
            
            ' Write results to worksheet
            ws.Cells(.RowIndex, COL_FORMULA1).Value = .Formula1Result
            ws.Cells(.RowIndex, COL_FORMULA2).Value = .Formula2Result
            ws.Cells(.RowIndex, COL_FORMULA3).Value = .Formula3Result
        End With
        
        If i Mod 50 = 0 Then
            Application.StatusBar = "Calculating formulas... Record " & i & " of " & UBound(clientRecords)
        End If
    Next i
    
    Application.StatusBar = False
    Exit Sub
    
ErrorHandler:
    Application.StatusBar = False
    Call HandleError(Err.Number, Err.Description, "CalculateFormulaResults")
End Sub

Private Function CalculateFormula3(correctionOutput As String, templateLookupResult As String) As String
    ' Compare the full correction in column 21 with the lookup result in column 26
    
    On Error GoTo ErrorHandler
    
    If correctionOutput <> "" Then
        ' Compare the full correction with the template lookup result
        If correctionOutput = templateLookupResult Then
            CalculateFormula3 = "TRUE"
        Else
            CalculateFormula3 = "FALSE"
        End If
    Else
        CalculateFormula3 = ""
    End If
    
    Exit Function
    
ErrorHandler:
    CalculateFormula3 = ""
End Function

Private Function PerformTemplateLookup(transactionRef As String, templateSheet As Object) As String
    ' Enhanced VLOOKUP for both columns 33 and 34, with support for concatenated joint account data
    On Error GoTo ErrorHandler
    
    PerformTemplateLookup = ""
    
    If templateSheet Is Nothing Or transactionRef = "" Then
        Exit Function
    End If
    
    ' Perform VLOOKUP equivalent for column 33 and 34
    On Error Resume Next
    Dim result33 As Variant
    Dim result34 As Variant
    
    result33 = Application.VLookup(transactionRef, templateSheet.Range("A:AH"), 33, False)
    result34 = Application.VLookup(transactionRef, templateSheet.Range("A:AH"), 34, False)
    
    Dim col33Value As String, col34Value As String
    
    ' Get column 33 value (ID)
    If Not IsError(result33) And Not IsEmpty(result33) Then
        col33Value = CStr(result33)
    Else
        col33Value = ""
    End If
    
    ' Get column 34 value (ID Type)  
    If Not IsError(result34) And Not IsEmpty(result34) Then
        col34Value = CStr(result34)
    Else
        col34Value = ""
    End If
    
    ' Handle concatenated data properly for joint accounts
    If InStr(col33Value, "|") > 0 And InStr(col34Value, "|") > 0 Then
        ' Both columns contain pipe-separated data (joint accounts)
        PerformTemplateLookup = FormatJointAccountLookup(col33Value, col34Value)
    ElseIf col33Value <> "" And col34Value <> "" Then
        ' Single account format
        PerformTemplateLookup = col33Value & ":" & col34Value
    ElseIf col33Value <> "" Then
        PerformTemplateLookup = col33Value & ":"
    ElseIf col34Value <> "" Then
        PerformTemplateLookup = ":" & col34Value
    End If
    
    On Error GoTo ErrorHandler
    Exit Function
    
ErrorHandler:
    PerformTemplateLookup = ""
End Function

Private Function FormatJointAccountLookup(idValues As String, idTypes As String) As String
    ' Formats joint account lookup results in correct ID1:IDTYPE1|ID2:IDTYPE2 format
    On Error GoTo ErrorHandler
    
    FormatJointAccountLookup = ""
    
    ' Split the pipe-separated values
    Dim idParts() As String, typeParts() As String
    idParts = Split(idValues, "|")
    typeParts = Split(idTypes, "|")
    
    ' Ensure we have matching pairs
    If UBound(idParts) <> UBound(typeParts) Then
        ' Mismatch in array sizes - return empty to avoid errors
        Exit Function
    End If
    
    ' Build the properly formatted result
    Dim result As String, i As Long
    For i = 0 To UBound(idParts)
        Dim currentID As String, currentType As String
        currentID = Trim(idParts(i))
        currentType = Trim(typeParts(i))
        
        If currentID <> "" And currentType <> "" Then
            If result <> "" Then
                result = result & "|"
            End If
            result = result & currentID & ":" & currentType
        End If
    Next i
    
    FormatJointAccountLookup = result
    Exit Function
    
ErrorHandler:
    FormatJointAccountLookup = ""
End Function

' ============================================================================
' UTILITY FUNCTIONS
' ============================================================================

Private Function DeterminePriorityNationalities(primaryNat As String, secondaryNat As String, ByRef context As ValidationContext) As String()
    Dim result(0 To 2) As String
    
    ' Convert to ISO-2 format
    Dim primary_ISO2 As String, secondary_ISO2 As String
    primary_ISO2 = ConvertToISO2(primaryNat, context.CountryDict)
    secondary_ISO2 = ConvertToISO2(secondaryNat, context.CountryDict)
    
    ' Apply EEA priority logic
    Dim primaryIsEEA As Boolean, secondaryIsEEA As Boolean
    primaryIsEEA = IsEEACountry(primary_ISO2, context.EEADict)
    secondaryIsEEA = IsEEACountry(secondary_ISO2, context.EEADict)
    
    If primaryIsEEA And Not secondaryIsEEA Then
        result(0) = primary_ISO2: result(1) = primary_ISO2: result(2) = secondary_ISO2
    ElseIf secondaryIsEEA And Not primaryIsEEA Then
        result(0) = secondary_ISO2: result(1) = secondary_ISO2: result(2) = primary_ISO2
    ElseIf primary_ISO2 <> "" And secondary_ISO2 <> "" Then
        If primary_ISO2 <= secondary_ISO2 Then
            result(0) = primary_ISO2: result(1) = primary_ISO2: result(2) = secondary_ISO2
        Else
            result(0) = secondary_ISO2: result(1) = secondary_ISO2: result(2) = primary_ISO2
        End If
    ElseIf primary_ISO2 <> "" Then
        result(0) = primary_ISO2: result(1) = primary_ISO2: result(2) = ""
    ElseIf secondary_ISO2 <> "" Then
        result(0) = secondary_ISO2: result(1) = secondary_ISO2: result(2) = ""
    Else
        result(0) = "": result(1) = "": result(2) = ""
    End If
    
    DeterminePriorityNationalities = result
End Function

Private Function ConvertToISO2(nationality As String, countryDict As Object) As String
    Dim cleanNat As String
    cleanNat = Trim(UCase(nationality))
    
    If cleanNat = "" Then
        ConvertToISO2 = ""
    ElseIf Len(cleanNat) = 2 And countryDict.exists(cleanNat) Then
        ConvertToISO2 = cleanNat
    ElseIf Len(cleanNat) = 3 And countryDict.exists(cleanNat) Then
        ConvertToISO2 = countryDict(cleanNat)
    Else
        ConvertToISO2 = ""
    End If
End Function

Private Function IsEEACountry(countryCode As String, eeaDict As Object) As Boolean
    If countryCode <> "" And eeaDict.exists(countryCode) Then
        IsEEACountry = eeaDict(countryCode)
    Else
        IsEEACountry = False
    End If
End Function

Private Function ParseDateSafely(cellValue As Variant) As Date
    On Error GoTo ErrorHandler
    
    If IsEmpty(cellValue) Or Trim(CStr(cellValue)) = "" Then
        ParseDateSafely = 0
    ElseIf IsDate(cellValue) Then
        ParseDateSafely = CDate(cellValue)
    ElseIf IsDate(CStr(cellValue)) Then
        ParseDateSafely = CDate(CStr(cellValue))
    Else
        ParseDateSafely = 0
    End If
    
    Exit Function
    
ErrorHandler:
    ParseDateSafely = 0
End Function

Private Function CleanNameForCONCAT(nameValue As String, isSurname As Boolean) As String
    If Trim(nameValue) = "" Then
        CleanNameForCONCAT = "#####"
        Exit Function
    End If
    
    Dim cleanedName As String
    cleanedName = UCase(Trim(nameValue))
    
    ' FIRST: Handle comma delimiters - extract first part before comma
    If InStr(cleanedName, ",") > 0 Then
        cleanedName = Trim(Split(cleanedName, ",")(0))
    End If
    
    If isSurname Then
        cleanedName = RemoveNamePrefixes(cleanedName)
    Else
        ' For first names, take first word only (after comma handling)
        Dim nameParts As Variant
        nameParts = Split(cleanedName & " ", " ")
        If UBound(nameParts) >= 0 Then
            cleanedName = nameParts(0)
        End If
    End If
    
    ' Clean special characters
    cleanedName = Replace(cleanedName, "-", "")
    cleanedName = Replace(cleanedName, "'", "")
    cleanedName = Replace(cleanedName, ".", "")
    cleanedName = Replace(cleanedName, " ", "")
    
    If cleanedName = "" Then cleanedName = "#####"
    
    CleanNameForCONCAT = Left(cleanedName & "#####", 5)
End Function

Private Function RemoveNamePrefixes(surname As String) As String
    Dim prefixes As Variant
    prefixes = Array("VON DER", "VAN DER", "VAN DE", "DE LA", "VON", "VAN", "DE", "DI", "DA", "MC", "MAC", "O")
    
    Dim cleanSurname As String
    cleanSurname = Trim(UCase(surname))
    
    Dim i As Long
    For i = 0 To UBound(prefixes)
        Dim prefix As String
        prefix = Trim(UCase(CStr(prefixes(i)))) & " "
        If Left(cleanSurname, Len(prefix)) = prefix Then
            ' Remove the prefix and return the cleaned surname
            RemoveNamePrefixes = Trim(Mid(cleanSurname, Len(prefix) + 1))
            Exit Function
        End If
    Next i
    
    ' If no prefix found, return original surname (cleaned)
    RemoveNamePrefixes = cleanSurname
End Function

' ============================================================================
' HELPER FUNCTIONS
' ============================================================================

Private Function GetWorksheet(sheetName As String) As Worksheet
    On Error GoTo ErrorHandler
    Set GetWorksheet = ThisWorkbook.Sheets(sheetName)
    Exit Function
ErrorHandler:
    Set GetWorksheet = Nothing
End Function

Private Function WorksheetExists(sheetName As String) As Boolean
    On Error GoTo ErrorHandler
    Dim ws As Worksheet
    Set ws = ThisWorkbook.Sheets(sheetName)
    WorksheetExists = True
    Exit Function
ErrorHandler:
    WorksheetExists = False
End Function

Private Function GetClientDataWorksheet() As Worksheet
    ' Returns the Client Data worksheet based on the incident code
    On Error GoTo ErrorHandler
    Dim worksheetName As String
    worksheetName = "Client Data - " & g_IncidentCode
    Set GetClientDataWorksheet = ThisWorkbook.Sheets(worksheetName)
    Exit Function
ErrorHandler:
    Set GetClientDataWorksheet = Nothing
End Function

Private Function IsValidCountryEntry(countryName As String, iso2Code As String, iso3Code As String, eeaStatus As String) As Boolean
    IsValidCountryEntry = (countryName <> "" And Len(iso2Code) = 2 And Len(iso3Code) = 3 And (eeaStatus = "Y" Or eeaStatus = "N"))
End Function

Private Function BuildFormatKey(countryCode As String, idType As String, formatDict As Object) As String
    Dim baseKey As String
    baseKey = countryCode & ":" & idType
    
    Dim patternIndex As Long
    patternIndex = 1
    Do While formatDict.exists(baseKey & ":" & patternIndex)
        patternIndex = patternIndex + 1
    Loop
    
    BuildFormatKey = baseKey & ":" & patternIndex
End Function

Private Function BuildTemplatePath(incidentCode As String) As String
    ' Build dynamic template file path based on financial year, quarter and incident code
    Dim basePath As String
    Dim fileName As String
    
    basePath = TEMPLATE_BASE_PATH_ROOT & g_FinancialYear & "\" & g_Quarter & "\Incident Code Analysis\"
    fileName = g_FinancialYear & " " & g_Quarter & " - " & incidentCode & ".xlsx"
    
    BuildTemplatePath = basePath & fileName
End Function

' ============================================================================
' SYSTEM FUNCTIONS
' ============================================================================

Private Sub OptimizePerformance(enableOptimization As Boolean)
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

Private Sub CleanupResources(ByRef context As ValidationContext)
    On Error Resume Next
    
    If Not context.MainTracker Is Nothing Then
        context.MainTracker.Parent.Close False
    End If
    
    If Not context.ItalianTracker Is Nothing Then
        context.ItalianTracker.Parent.Close False
    End If
    
    If Not context.TemplateWorkbook Is Nothing Then
        context.TemplateWorkbook.Parent.Close False
    End If
    
    Set context.CountryDict = Nothing
    Set context.EEADict = Nothing
    Set context.FormatDict = Nothing
    Set context.RegexEngine = Nothing
    Set context.MainTracker = Nothing
    Set context.ItalianTracker = Nothing
    Set context.TemplateWorkbook = Nothing
End Sub

Private Sub HandleError(errorNumber As Long, errorDescription As String, functionName As String)
    Dim errorMsg As String
    errorMsg = "Error in " & functionName & ": " & errorNumber & " - " & errorDescription
    MsgBox errorMsg, vbCritical, "Processing Error"
End Sub

Private Sub ShowCompletionMessage(recordCount As Long, processingTime As Double)
    Dim msg As String
    msg = "Validation completed successfully!" & vbNewLine & vbNewLine
    msg = msg & "Records processed: " & recordCount & vbNewLine
    msg = msg & "Processing time: " & Format(processingTime, "0.0") & " seconds"
    MsgBox msg, vbInformation, "Validation Complete"
End Sub

' ============================================================================
' VALIDATION LOGIC FUNCTIONS (Simplified placeholders)
' ============================================================================

Private Function ValidateIDLogic(idValue As String, idType As String, countryCode As String, dob As String, gender As String) As Boolean
    ' Simplified logic validation - implement specific validation rules as needed
    ' This is a placeholder that returns True for now
    ValidateIDLogic = True
End Function
