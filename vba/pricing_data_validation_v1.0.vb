Sub PricingDataValidation()
    '
    ' Pricing Data Validation Macro v1.0
    ' Purpose: Validate pricing of trades using net amount, consideration amount and interest amount
    ' Author: Generated from technical specifications
    ' Date: September 30, 2025
    '
    
    Dim ws As Worksheet
    Dim lastRow As Long
    Dim currentRow As Long
    
    ' Column indexes (1-based for VBA, matching Excel columns)
    Const COL_TRANSACTION_REF As Integer = 1    ' A: Transaction Reference
    Const COL_ERROR As Integer = 2              ' B: Error (Y/N)
    Const COL_CORRECTION As Integer = 3         ' C: Correction
    Const COL_CORRECTION_FIELD As Integer = 4   ' D: Correction Field
    Const COL_COMMENTS As Integer = 5           ' E: Comments
    Const COL_NET_AMOUNT As Integer = 6         ' F: Net Amount
    Const COL_CONSIDERATION As Integer = 7      ' G: Consideration
    Const COL_INTEREST As Integer = 8           ' H: Interest
    Const COL_TOTAL As Integer = 9              ' I: Total
    Const COL_EXPECTED_INTEREST As Integer = 10 ' J: Expected Interest
    Const COL_NET_DIFFERENCE As Integer = 11    ' K: Net Difference
    
    ' Set the active worksheet
    Set ws = ActiveSheet
    
    ' Find the last row with data (check column F - Net Amount)
    lastRow = ws.Cells(ws.Rows.Count, COL_NET_AMOUNT).End(xlUp).Row
    
    ' Start from row 2 to skip headers
    For currentRow = 2 To lastRow
        
        ' Check if we have the required input data
        If IsNumeric(ws.Cells(currentRow, COL_NET_AMOUNT).Value) And _
           IsNumeric(ws.Cells(currentRow, COL_CONSIDERATION).Value) And _
           IsNumeric(ws.Cells(currentRow, COL_INTEREST).Value) Then
            
            ' Get input values
            Dim netAmount As Double
            Dim consideration As Double
            Dim interest As Double
            
            netAmount = ws.Cells(currentRow, COL_NET_AMOUNT).Value
            consideration = ws.Cells(currentRow, COL_CONSIDERATION).Value
            interest = ws.Cells(currentRow, COL_INTEREST).Value
            
            ' Calculate output values according to specification
            
            ' Total = Consideration + Interest
            Dim total As Double
            total = consideration + interest
            ws.Cells(currentRow, COL_TOTAL).Value = total
            
            ' Expected Interest = Consideration - Net Amount
            Dim expectedInterest As Double
            expectedInterest = consideration - netAmount
            ws.Cells(currentRow, COL_EXPECTED_INTEREST).Value = expectedInterest
            
            ' Net Difference = Total - Net Amount
            Dim netDifference As Double
            netDifference = total - netAmount
            ws.Cells(currentRow, COL_NET_DIFFERENCE).Value = netDifference
            
            ' Error Logic: if Net Difference != 0 then "TBC" else "N"
            ' Note: Using small tolerance for floating point comparison
            If Abs(netDifference) > 0.01 Then
                ws.Cells(currentRow, COL_ERROR).Value = "TBC"
            Else
                ws.Cells(currentRow, COL_ERROR).Value = "N"
            End If
            
        End If
        
    Next currentRow
    
    ' Format the calculated columns to 2 decimal places
    ws.Range(ws.Cells(2, COL_TOTAL), ws.Cells(lastRow, COL_TOTAL)).NumberFormat = "0.00"
    ws.Range(ws.Cells(2, COL_EXPECTED_INTEREST), ws.Cells(lastRow, COL_EXPECTED_INTEREST)).NumberFormat = "0.00"
    ws.Range(ws.Cells(2, COL_NET_DIFFERENCE), ws.Cells(lastRow, COL_NET_DIFFERENCE)).NumberFormat = "0.00"
    
    ' Display completion message
    MsgBox "Pricing data validation completed successfully!" & vbCrLf & _
           "Processed " & (lastRow - 1) & " rows of data.", vbInformation, "Validation Complete"
    
End Sub

Sub ClearCalculatedFields()
    '
    ' Clear Calculated Fields
    ' Purpose: Clear the calculated output columns to allow re-running validation
    '
    
    Dim ws As Worksheet
    Dim lastRow As Long
    
    ' Column indexes for output fields
    Const COL_ERROR As Integer = 2
    Const COL_TOTAL As Integer = 9
    Const COL_EXPECTED_INTEREST As Integer = 10
    Const COL_NET_DIFFERENCE As Integer = 11
    
    Set ws = ActiveSheet
    
    ' Find the last row with data
    lastRow = ws.Cells(ws.Rows.Count, 6).End(xlUp).Row ' Check Net Amount column
    
    ' Clear the output columns (start from row 2 to preserve headers)
    If lastRow > 1 Then
        ws.Range(ws.Cells(2, COL_ERROR), ws.Cells(lastRow, COL_ERROR)).ClearContents
        ws.Range(ws.Cells(2, COL_TOTAL), ws.Cells(lastRow, COL_TOTAL)).ClearContents
        ws.Range(ws.Cells(2, COL_EXPECTED_INTEREST), ws.Cells(lastRow, COL_EXPECTED_INTEREST)).ClearContents
        ws.Range(ws.Cells(2, COL_NET_DIFFERENCE), ws.Cells(lastRow, COL_NET_DIFFERENCE)).ClearContents
        
        MsgBox "Calculated fields cleared successfully!", vbInformation, "Fields Cleared"
    End If
    
End Sub
