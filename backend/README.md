# Remote Control Backend

Production-ready Flask backend for the Remote Control System.

## Features

- User registration, login, JWT access tokens, and refresh tokens
- Refresh token rotation, logout revocation, and password changes
- Password hashing with bcrypt
- Device registration, heartbeat, and online status
- Device pairing code verification
- Authenticated Socket.IO channels for desktop agents and controllers
- Remote session lifecycle management
- SQLAlchemy models for users, devices, sessions, and audit logs
- JSON error handling, input validation, rate limiting, CORS, and rotating logs
- SQLite for development and PostgreSQL for production

## Local Development

```powershell
cd RemoteControl/backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:APP_ENV = "development"
python app.py
```

The API will run at `http://127.0.0.1:5000`.

## Environment Variables

- `APP_ENV`: `development`, `testing`, or `production`
- `SECRET_KEY`: Flask secret key
- `JWT_SECRET_KEY`: JWT signing secret
- `DATABASE_URL`: PostgreSQL URL in production; defaults to local SQLite
- `CORS_ORIGINS`: comma-separated allowed REST origins
- `SOCKETIO_CORS_ORIGINS`: comma-separated allowed Socket.IO origins
- `JWT_ACCESS_MINUTES`: access token lifetime in minutes
- `JWT_REFRESH_DAYS`: refresh token lifetime in days
- `LOG_LEVEL`: logging level

## API

All REST routes are prefixed with `/api/v1`.

- `GET /health`
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`
- `PATCH /auth/me`
- `POST /auth/change-password`
- `GET /devices`
- `POST /devices`
- `GET /devices/<device_id>`
- `POST /devices/<device_id>/heartbeat`
- `POST /devices/<device_id>/pair`
- `POST /connect/sessions`
- `DELETE /connect/sessions/<session_id>`

## Socket.IO Events

- Agent emits `agent_connect` with `token` and `device_id`
- Agent emits `agent_heartbeat`
- Agent emits `agent_frame`
- Agent emits `agent_event`
- Controller emits `controller_join` with `token` and `session_id`
- Controller emits `remote_command`

## Render Deployment

Create the service from `render.yaml`, then set `CORS_ORIGINS` and
`SOCKETIO_CORS_ORIGINS` to the HTTPS origins used by your Android/web clients.
