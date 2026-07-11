@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if exist "%PYTHON_EXE%" (
    if exist "%~dp0.venv\pyvenv.cfg" (
        for /f "tokens=1,* delims==" %%A in ('findstr /B /C:"home =" "%~dp0.venv\pyvenv.cfg"') do set "VENV_HOME=%%B"
        for /f "tokens=* delims= " %%H in ("%VENV_HOME%") do set "VENV_HOME=%%H"
        if exist "%VENV_HOME%\python.exe" goto build
    )
)

where python >nul 2>nul
if %errorlevel%==0 (
    python --version >nul 2>nul
    if errorlevel 1 goto check_py
    set "PYTHON_EXE=python"
    goto build
)

:check_py
where py >nul 2>nul
if %errorlevel%==0 (
    py --version >nul 2>nul
    if errorlevel 1 goto missing_python
    set "PYTHON_EXE=py"
    goto build
)

:missing_python
echo Python was not found. Install Python 3.10+ and run:
echo python -m venv .venv
echo .\.venv\Scripts\python.exe -m pip install -r requirements.txt
exit /b 1

:build
"%PYTHON_EXE%" build_tools_create_icon.py
if errorlevel 1 exit /b 1
"%PYTHON_EXE%" -m PyInstaller --noconfirm --clean RemoteControlAgent.spec
if errorlevel 1 exit /b 1
echo Executable created at dist\RemoteControlAgent.exe
endlocal
