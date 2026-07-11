# Deployment

## Backend on Render

1. Create the Render service from `backend/render.yaml`.
2. Set `CORS_ORIGINS` and `SOCKETIO_CORS_ORIGINS` to trusted client origins.
3. Render generates `SECRET_KEY` and `JWT_SECRET_KEY`.
4. Run the migration command after deployment:

```powershell
flask db upgrade
```

The Procfile command is:

```text
gunicorn -w 1 --threads 100 --bind 0.0.0.0:$PORT app:app
```

The backend uses Flask-SocketIO in `threading` mode with `simple-websocket`.
Do not use Eventlet for this project on Render; Eventlet monkey patching can
break SQLAlchemy/Supabase connection locks.

## Required Environment Variables

- `APP_ENV=production`
- `FLASK_ENV=production`
- `DATABASE_URL`
- `SECRET_KEY`
- `JWT_SECRET_KEY`
- `CORS_ORIGINS`
- `SOCKETIO_CORS_ORIGINS`

## HTTPS and WSS

Render terminates HTTPS. Android and desktop clients should use the HTTPS Render
URL; Socket.IO will use secure WebSocket transport through the same origin.
