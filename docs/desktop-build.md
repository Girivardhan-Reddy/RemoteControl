# Desktop Agent Build

## Install

```powershell
cd desktop_agent
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Register and Pair

```powershell
python app.py --server-url https://your-service.onrender.com --login
```

The agent prints a pairing code. Confirm it from an authenticated controller.

## PyInstaller

```powershell
.\build_pyinstaller.ps1
```

The executable is written to `desktop_agent/dist/RemoteControlAgent.exe`.

## Windows Auto Start

The `startup` command registers the current user Run key. It is reversible from
the agent command channel or by removing the Run entry.
