'' launch_gui.vbs
'' Silently activates the txr_automation conda environment and launches the GUI.
'' No terminal window is shown.

Dim shell
Set shell = CreateObject("WScript.Shell")

Dim projectDir
projectDir = "C:\Users\ccharm\Documents\GitHub\txr_automation"

Dim cmd
cmd = "cmd /c """ & _
      "C:\Users\ccharm\AppData\Local\anaconda3\condabin\conda.bat" & _
      " run -n txr_automation --no-capture-output " & _
      "pythonw -m gui"""

shell.CurrentDirectory = projectDir
shell.Run cmd, 0, False

Set shell = Nothing
