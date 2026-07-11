# Step-by-Step Testing Guide

## 1. Verify Render Environment

In Render, confirm:

```text
APP_ENV=production
FLASK_ENV=production
DATABASE_URL=postgresql://...supabase.../postgres?sslmode=require
SECRET_KEY=<set>
JWT_SECRET_KEY=<set>
CORS_ORIGINS=https://remotecontrol-ef6d.onrender.com
SOCKETIO_CORS_ORIGINS=https://remotecontrol-ef6d.onrender.com
```

Open:

```text
https://remotecontrol-ef6d.onrender.com/api/v1/health
https://remotecontrol-ef6d.onrender.com/api/v1/health/database
```

The database health response must show:

```json
{
  "connected": true,
  "dialect": "postgresql"
}
```

## 2. Repair or Migrate Supabase

If Render logs mention existing enum types or tables, run
`backend/sql/supabase_schema_repair.sql` in the Supabase SQL editor.

Then run:

```powershell
cd E:\remote\RemoteControl\backend
$env:APP_ENV="production"
$env:FLASK_ENV="production"
$env:FLASK_APP="app.py"
$env:DATABASE_URL="<supabase-url>"
$env:SECRET_KEY="<secret>"
$env:JWT_SECRET_KEY="<jwt-secret>"
flask db stamp 0003_device_registration
flask db upgrade
```

## 3. Create First User

If `users` is empty, login must fail. Create the first account:

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

## 4. Test Auth API

```powershell
$base="https://remotecontrol-ef6d.onrender.com/api/v1"
$body=@{email="you@example.com";password="YourPassword123"} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$base/auth/login" -Body $body -ContentType "application/json"
```

## 5. Test Desktop Agent

```powershell
cd E:\remote\RemoteControl\desktop_agent
python app.py --server-url https://remotecontrol-ef6d.onrender.com --login
```

Expected:

- Login succeeds
- Device registers
- Pairing code prints
- Agent continues running and writes `logs.txt`

## 6. Test Android

1. Open Android project.
2. Set server URL to `https://remotecontrol-ef6d.onrender.com`.
3. Login.
4. Pair device with the desktop agent code.
5. Connect to the device.

## 7. Logs

Backend logs:

```text
RemoteControl/backend/logs/logs.txt
```

Desktop agent logs:

```text
%USERPROFILE%\.remote_control_agent\logs\logs.txt
```
