$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$venvConfig = Join-Path $PSScriptRoot ".venv\pyvenv.cfg"
$pythonCandidates = @()

if ((Test-Path -LiteralPath $venvPython) -and (Test-Path -LiteralPath $venvConfig)) {
    $homeLine = Get-Content -LiteralPath $venvConfig | Where-Object { $_ -like "home =*" } | Select-Object -First 1
    $venvHome = if ($homeLine) { ($homeLine -replace "^home\s*=\s*", "").Trim() } else { $null }
    $venvBaseExists = $false
    if ($venvHome) {
        try {
            $venvBaseExists = Test-Path -LiteralPath (Join-Path $venvHome "python.exe")
        } catch {
            $venvBaseExists = $false
        }
    }
    if ($venvBaseExists) {
        $pythonCandidates += $venvPython
    }
}

$pythonCandidates += @("python", "py")

$python = $null
foreach ($candidate in $pythonCandidates) {
    try {
        if ($candidate.EndsWith(".exe") -and -not (Test-Path -LiteralPath $candidate)) {
            continue
        }
        $versionOutput = & $candidate --version 2>&1
        if ($LASTEXITCODE -eq 0 -and ($versionOutput -join "`n") -notmatch "No Python") {
            $python = $candidate
            break
        }
    } catch {
        continue
    }
}

if (-not $python) {
    throw "Python was not found. Install Python 3.10+ and run: python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
}

& $python build_tools_create_icon.py
& $python -m PyInstaller --noconfirm --clean RemoteControlAgent.spec
Write-Host "Build complete: dist\RemoteControlAgent.exe"
