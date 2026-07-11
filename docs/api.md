# API Documentation

Base path: `/api/v1`.

## Authentication

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`
- `PATCH /auth/me`
- `POST /auth/change-password`

## Devices

- `GET /devices`
- `POST /devices`
- `GET /devices/<device_id>`
- `PATCH /devices/<device_id>`
- `DELETE /devices/<device_id>`
- `POST /devices/<device_id>/heartbeat`
- `POST /devices/<device_id>/pair`
- `POST /devices/<device_id>/pairing-code`

## Connections

- `POST /connect/sessions`
- `DELETE /connect/sessions/<session_id>`

## Socket.IO

- `agent_connect`
- `agent_heartbeat`
- `controller_join`
- `remote_command`
- `agent_frame`
- `agent_event`

All REST endpoints except registration and login require `Authorization: Bearer
<access_token>`. Socket events include the token in their JSON payload.
