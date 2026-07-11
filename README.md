# Remote Control System

Remote Control System is a full-stack remote desktop platform for computers you
own or are authorized to manage.

## Modules

- `backend`: Flask REST and Socket.IO backend
- `desktop_agent`: Windows-oriented Python desktop agent
- `android`: Java Android controller application
- `docs`: deployment, API, build, and architecture documentation

## Quick Start

Backend:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/database_admin.py create
python app.py
```

Desktop agent:

```powershell
cd desktop_agent
pip install -r requirements.txt
python app.py --server-url http://127.0.0.1:5000 --login
```

Android:

Open `android` in Android Studio, set the server URL in Settings, then build and
run the app.

## Security Model

The backend requires JWT authentication, password hashing, refresh rotation,
token revocation, device pairing, owner-scoped device access, and authenticated
Socket.IO events. The desktop agent is intended for authorized machines and
provides visible local logging and an optional tray indicator.

## Production Setup

Use [docs/end-to-end-deployment.md](docs/end-to-end-deployment.md) for the
Render + Supabase + Desktop Agent + Android flow.

Useful references:

- [API](docs/api.md)
- [Testing](docs/testing-guide.md)
- [Security](docs/security.md)
- [Desktop build](docs/desktop-build.md)
- [Desktop GUI](docs/desktop-gui.md)
- [Android build](docs/android-build.md)
