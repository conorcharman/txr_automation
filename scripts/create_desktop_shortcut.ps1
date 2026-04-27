# create_desktop_shortcut.ps1
# Creates a Desktop shortcut that launches the TXR Automation GUI
# without showing a terminal window.
#
# Usage: Run once from any PowerShell prompt:
#   .\scripts\create_desktop_shortcut.ps1

$ProjectDir  = "C:\Users\ccharm\Documents\GitHub\txr_automation"
$LauncherVbs = Join-Path $ProjectDir "scripts\launch_gui.vbs"
$IconPath    = Join-Path $ProjectDir "src\gui\assets\icon.ico"
$ShortcutDst = Join-Path ([Environment]::GetFolderPath("Desktop")) "TXR Automation.lnk"

$WshShell  = New-Object -ComObject WScript.Shell
$Shortcut  = $WshShell.CreateShortcut($ShortcutDst)

$Shortcut.TargetPath       = "wscript.exe"
$Shortcut.Arguments        = "`"$LauncherVbs`""
$Shortcut.WorkingDirectory = $ProjectDir
$Shortcut.Description      = "TXR Automation GUI"

# Use the project icon if it exists, otherwise fall back to wscript icon
if (Test-Path $IconPath) {
    $Shortcut.IconLocation = $IconPath
}

$Shortcut.Save()

Write-Host "Shortcut created: $ShortcutDst"
