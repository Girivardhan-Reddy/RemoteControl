# Security

- Only use the system for devices you own or are authorized to administer.
- Backend passwords are bcrypt-hashed.
- Access and refresh JWTs are signed and can be revoked.
- Refresh token rotation reduces replay risk.
- Devices must be registered by an authenticated user and paired before Socket.IO access.
- REST routes scope devices and sessions to the authenticated owner.
- File, power, screen, mouse, and keyboard actions are available only through an active authenticated session.
- Production must use HTTPS/WSS and strong secrets.
