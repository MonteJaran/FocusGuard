# Build FocusGuard: PyInstaller folder build, then an Inno Setup installer.
#
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -Sign
#
# Windows PowerShell 5.1 compatible -- see the note in create_shortcut.ps1
# about PowerShell 7-only syntax.

[CmdletBinding()]
param(
    # Sign the executable and installer. Needs a certificate; see BUILD.md.
    [switch]$Sign,
    [string]$CertThumbprint = $env:FOCUSGUARD_CERT_THUMBPRINT,
    [string]$TimestampUrl = 'http://timestamp.digicert.com',
    [switch]$SkipInstaller
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Step($message) { Write-Host "==> $message" -ForegroundColor Cyan }
function Ok($message)   { Write-Host "    $message" -ForegroundColor Green }

# ── Version, read from the one place that defines it ─────────────────────────
Step 'Reading version'
$Version = (python -c "import sys; sys.path.insert(0, '.'); from core.version import __version__; print(__version__)").Trim()
if (-not $Version) { throw 'Could not read version from core/version.py' }
Ok "FocusGuard $Version"

# ── Checks before spending time on a build ───────────────────────────────────
Step 'Checking the tree is releasable'
python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Tests failed -- not building a release from a red tree.' }
Ok 'Tests pass'

python -m ruff check .
if ($LASTEXITCODE -ne 0) { throw 'Lint failed.' }
Ok 'Lint clean'

# ── Clean ────────────────────────────────────────────────────────────────────
Step 'Cleaning previous output'
foreach ($dir in @('build', 'dist')) {
    if (Test-Path $dir) { Remove-Item $dir -Recurse -Force }
}
Ok 'Clean'

# ── Version resource ─────────────────────────────────────────────────────────
Step 'Generating the Windows version resource'
python packaging\make_version_info.py
Ok 'version_info.txt written'

# ── PyInstaller ──────────────────────────────────────────────────────────────
Step 'Building the executable'
python -m PyInstaller packaging\focusguard.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }

$ExePath = Join-Path $Root 'dist\FocusGuard\FocusGuard.exe'
if (-not (Test-Path $ExePath)) { throw "Expected $ExePath, which is missing." }
Ok "Built $ExePath"

# ── Smoke test ───────────────────────────────────────────────────────────────
# A frozen build that fails on a missing hidden import does so at launch, and
# a GUI app fails silently. Catch it here rather than in someone's download.
Step 'Smoke-testing the frozen build'
$proc = Start-Process -FilePath $ExePath -PassThru
Start-Sleep -Seconds 8
if ($proc.HasExited) {
    throw "The built app exited immediately (code $($proc.ExitCode)). Check for a missing hidden import."
}
Stop-Process -Id $proc.Id -Force
Ok 'Launches and stays running'

# ── Signing ──────────────────────────────────────────────────────────────────
# Sign BEFORE packaging, so the installer contains signed binaries, then sign
# the installer itself afterwards.
function Invoke-Sign($path) {
    if (-not $CertThumbprint) {
        throw 'No certificate thumbprint. Set FOCUSGUARD_CERT_THUMBPRINT or pass -CertThumbprint.'
    }
    & signtool.exe sign /sha1 $CertThumbprint /fd SHA256 `
        /tr $TimestampUrl /td SHA256 /d 'FocusGuard' $path
    if ($LASTEXITCODE -ne 0) { throw "Signing failed for $path" }
    Ok "Signed $path"
}

if ($Sign) {
    Step 'Signing the executable'
    Invoke-Sign $ExePath
} else {
    Write-Host '    [SKIP] Unsigned build. SmartScreen will warn users.' -ForegroundColor Yellow
}

# ── Installer ────────────────────────────────────────────────────────────────
if ($SkipInstaller) {
    Ok 'Skipping installer'
} else {
    Step 'Building the installer'
    $iscc = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if ($null -eq $iscc) {
        $candidates = @(
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
            "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
        )
        foreach ($candidate in $candidates) {
            if (Test-Path $candidate) { $iscc = $candidate; break }
        }
    } else {
        $iscc = $iscc.Source
    }

    if (-not $iscc) {
        Write-Host '    [SKIP] Inno Setup not found. Install it from https://jrsoftware.org/isdl.php' -ForegroundColor Yellow
    } else {
        & $iscc "/DAppVersion=$Version" 'packaging\installer.iss'
        if ($LASTEXITCODE -ne 0) { throw 'Inno Setup failed.' }

        $SetupPath = Join-Path $Root "dist\installer\FocusGuard-$Version-setup.exe"
        Ok "Built $SetupPath"

        if ($Sign) {
            Step 'Signing the installer'
            Invoke-Sign $SetupPath
        }
    }
}

Write-Host ''
Write-Host "FocusGuard $Version built." -ForegroundColor Green
if (-not $Sign) {
    Write-Host 'Unsigned. Read BUILD.md before distributing this to anyone.' -ForegroundColor Yellow
}
