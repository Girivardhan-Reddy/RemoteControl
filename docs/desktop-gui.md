# Desktop Agent GUI

The graphical agent is launched from:

```powershell
cd E:\remote\RemoteControl\desktop_agent
python main.py
```

The terminal agent entrypoint `app.py` remains available.

## Features

- Dark PySide6 dashboard
- Login and registration pages
- First-run setup wizard
- Device status and pairing code display
- System monitor with live CPU/RAM charts
- Remote desktop local preview and streaming controls
- Split file manager with local copy, rename, delete, and folder creation
- Settings for backend URL, startup, auto-login, FPS, JPEG quality, reconnect, heartbeat
- Logs viewer with search, export, and clear
- System tray with Open, Reconnect, Settings, and Quit
- Update download with SHA-256 verification

## Build Executable

```powershell
cd E:\remote\RemoteControl\desktop_agent
pip install -r requirements.txt
.\build.ps1
```

Output:

```text
desktop_agent\dist\RemoteControlAgent.exe
```

## Build Installer

Install Inno Setup 6, then run:

```powershell
.\build_installer.ps1
```

Output:

```text
desktop_agent\Output\RemoteControlSetup.exe
```

The installer installs to:

```text
C:\Program Files\Remote Control Agent
```

It creates desktop and Start Menu shortcuts and registers per-user startup.
