# End-to-End Deployment Guide

Backend URL: `https://remotecontrol-ef6d.onrender.com`

## Render Environment Variables

Set these on the Render backend service:

```text
APP_ENV=production
FLASK_ENV=production
DATABASE_URL=<Supabase pooled PostgreSQL URL with ?sslmode=require>
SECRET_KEY=<long random secret>
JWT_SECRET_KEY=<different long random secret>
CORS_ORIGINS=https://remotecontrol-ef6d.onrender.com
SOCKETIO_CORS_ORIGINS=https://remotecontrol-ef6d.onrender.com
AUTO_CREATE_MISSING_TABLES=false
```

Set the Render start command to:

```text
gunicorn -w 1 --threads 100 --bind 0.0.0.0:$PORT app:app
```

If the Render root directory is the repository root, use:

```text
cd backend && gunicorn -w 1 --threads 100 --bind 0.0.0.0:$PORT app:app
```

`DATABASE_URL` must start with `postgresql://`. `postgres://` is normalized, but
using `postgresql://` avoids ambiguity.

## Supabase Setup

Use the Supabase connection pooler URL for Render. Append `?sslmode=require` if
it is not already present.

When the database is empty, the app can create tables on first startup. For a
partially-created database, run:

```sql
-- Supabase SQL editor
-- paste backend/sql/supabase_schema_repair.sql
```

Then redeploy Render.

## Migration Commands

From `RemoteControl/backend`:

```powershell
$env:APP_ENV="production"
$env:FLASK_ENV="production"
$env:FLASK_APP="app.py"
$env:DATABASE_URL="<supabase-url>"
$env:SECRET_KEY="<secret>"
$env:JWT_SECRET_KEY="<jwt-secret>"
flask db upgrade
```

If tables already exist and the schema repair SQL was used:

```powershell
flask db stamp 0003_device_registration
flask db upgrade
```

## Create First Admin

```powershell
cd E:\remote\RemoteControl\backend
$env:APP_ENV="production"
$env:FLASK_ENV="production"
$env:FLASK_APP="app.py"
$env:DATABASE_URL="<supabase-url>"
$env:SECRET_KEY="<secret>"
$env:JWT_SECRET_KEY="<jwt-secret>"
python create_admin.py
```

The script asks for name, email, and password, then stores a bcrypt hash.

## Local Development

```powershell
cd E:\remote\RemoteControl\backend
$env:APP_ENV="development"
Remove-Item Env:\DATABASE_URL -ErrorAction SilentlyContinue
python scripts\database_admin.py create
python app.py
```

Local development uses SQLite at `backend/remote_control_dev.sqlite3`.

## Desktop Agent

```powershell
cd E:\remote\RemoteControl\desktop_agent
python app.py --server-url https://remotecontrol-ef6d.onrender.com --login
```

Login with the admin/user account. The agent registers the computer and prints a
pairing code.

## Android Test

1. Open `RemoteControl/android` in Android Studio.
2. Set server URL to `https://remotecontrol-ef6d.onrender.com`.
3. Login with the same account.
4. Pair the listed device using the desktop agent pairing code.
5. Tap Connect.

## Expected Flow

```text
Desktop Agent login -> Backend /auth/login -> Supabase users
Desktop Agent device registration -> Backend /devices -> Supabase devices
Android login -> Backend /auth/login -> Supabase users
Android pair/connect -> Backend /devices/<id>/pair and /connect/sessions
Socket.IO -> agent_connect/controller_join -> live session
```
