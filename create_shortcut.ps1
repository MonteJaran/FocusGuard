# Creates (or updates) the FocusGuard desktop shortcut.
$dir      = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonw  = (Get-Command pythonw -ErrorAction SilentlyContinue)?.Source
$desktop  = [Environment]::GetFolderPath("Desktop")
$lnk      = Join-Path $desktop "FocusGuard.lnk"
$ico      = Join-Path $dir "FocusGuard.ico"

if (-not $pythonw) {
    Write-Host "  [SKIP] pythonw not found — shortcut not created." -ForegroundColor DarkGray
    exit 0
}

$wsh              = New-Object -ComObject WScript.Shell
$sc               = $wsh.CreateShortcut($lnk)
$sc.TargetPath    = $pythonw
$sc.Arguments     = "`"$dir\main.py`""
$sc.WorkingDirectory = $dir
$sc.Description   = "FocusGuard — App Usage Monitor"
if (Test-Path $ico) { $sc.IconLocation = $ico }
$sc.Save()

Write-Host "  [OK] Shortcut created on Desktop." -ForegroundColor Green
