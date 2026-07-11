$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
python build_tools_create_icon.py
python -m PyInstaller --noconfirm --clean RemoteControlAgent.spec
Write-Host "Executable created at dist\RemoteControlAgent.exe"
