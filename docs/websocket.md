# WebSocket Module

Socket.IO carries real-time control traffic between Android controllers and
desktop agents. REST APIs create sessions; WebSocket events attach each side and
relay frames, commands, and responses.

## Events

- `agent_connect`: desktop agent authenticates with JWT and paired `device_id`
- `agent_heartbeat`: keeps device presence fresh
- `controller_join`: Android client joins an active session
- `remote_command`: controller-to-agent command relay
- `agent_frame`: screen frame relay
- `agent_event`: command response and status relay

## Authentication

Socket events decode the JWT, reject revoked tokens, require owned devices, and
refuse unpaired agent connections.
