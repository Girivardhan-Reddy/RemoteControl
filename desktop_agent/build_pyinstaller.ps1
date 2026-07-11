$ErrorActionPreference = "Stop"
python -m PyInstaller --noconfirm --clean --name RemoteControlAgent --onefile --windowed app.py
Write-Host "Build complete: dist\RemoteControlAgent.exe"
