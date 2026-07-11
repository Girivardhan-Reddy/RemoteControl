$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath "dist\RemoteControlAgent.exe")) {
    .\build.ps1
}
$iscc = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
if (-not $iscc) {
    $default = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if (Test-Path -LiteralPath $default) {
        $iscc = Get-Item -LiteralPath $default
    }
}
if (-not $iscc) {
    throw "Inno Setup 6 is required to build RemoteControlSetup.exe."
}
& $iscc.Source "installer.iss"
Write-Host "Installer created in desktop_agent\Output\RemoteControlSetup.exe"
