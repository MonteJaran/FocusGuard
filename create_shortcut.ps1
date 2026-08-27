# Creates (or updates) the FocusGuard desktop shortcut.
#
# Must stay compatible with Windows PowerShell 5.1, which is what ships with
# Windows 10 and 11 and what `powershell` always resolves to. PowerShell 7-only
# syntax (the ?. null-conditional operator, ?? coalescing, ternaries) is a parse
# error there, and a parse error means no shortcut for every user on a stock
# install. Test any change with: powershell -NoProfile -File create_shortcut.ps1

$ErrorActionPreference = 'Stop'

try {
    $dir = Split-Path -Parent $MyInvocation.MyCommand.Path

    $pythonwCmd = Get-Command pythonw -ErrorAction SilentlyContinue
    if ($null -eq $pythonwCmd) {
        Write-Host "  [SKIP] pythonw not found - shortcut not created." -ForegroundColor DarkGray
        exit 0
    }
    $pythonw = $pythonwCmd.Source

    $desktop = [Environment]::GetFolderPath("Desktop")
    if ([string]::IsNullOrEmpty($desktop)) {
        Write-Host "  [SKIP] Desktop folder not found - shortcut not created." -ForegroundColor DarkGray
        exit 0
    }

    $lnk = Join-Path $desktop "FocusGuard.lnk"
    $ico = Join-Path $dir "FocusGuard.ico"

    $wsh = New-Object -ComObject WScript.Shell
    $sc  = $wsh.CreateShortcut($lnk)
    $sc.TargetPath       = $pythonw
    $sc.Arguments        = '"' + (Join-Path $dir 'main.py') + '"'
    $sc.WorkingDirectory = $dir
    $sc.Description      = "FocusGuard - App Usage Monitor"
    if (Test-Path $ico) { $sc.IconLocation = $ico }
    $sc.Save()

    Write-Host "  [OK] Shortcut created on Desktop." -ForegroundColor Green
}
catch {
    # A missing shortcut must never stop the app from launching.
    Write-Host ("  [SKIP] Could not create shortcut: " + $_.Exception.Message) -ForegroundColor DarkGray
    exit 0
}
