@echo off
setlocal
cd /d "%~dp0"
python build_tools_create_icon.py
if errorlevel 1 exit /b 1
python -m PyInstaller --noconfirm --clean RemoteControlAgent.spec
if errorlevel 1 exit /b 1
echo Executable created at dist\RemoteControlAgent.exe
endlocal
