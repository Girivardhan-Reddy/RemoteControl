# Database Module

The backend stores persistent state in PostgreSQL for production and SQLite for
development. SQLAlchemy models are the application source of truth, and Alembic
migrations are the production schema-change mechanism.

## Tables

- `users`: authenticated accounts, password hashes, roles, active flag
- `devices`: registered desktop agents, status, heartbeat, Socket.IO identity
- `sessions`: remote-control sessions between a user and a device
- `logs`: audit and operational events
- `revoked_tokens`: JWT denylist entries for logout and token revocation

## Local Commands

Run commands from `RemoteControl/backend`.

```powershell
python scripts/database_admin.py create
python scripts/database_admin.py health
python scripts/database_admin.py seed-admin --email owner@example.com --name Owner
```

The `drop` command refuses to run when `APP_ENV=production`.
Set `AUTO_CREATE_DEV_DB=false` when running migration tooling that should not
create development tables automatically.

## Production Migration Flow

```powershell
flask db upgrade
```

When changing models:

```powershell
flask db migrate -m "describe change"
flask db upgrade
```

## Security Notes

- Passwords are stored only as bcrypt hashes.
- JWT logout is backed by `revoked_tokens`.
- User-owned devices and sessions use cascading foreign keys.
- Check constraints enforce minimum shape at the database boundary.
- Operational queries use explicit indexes on ownership, status, heartbeat, and audit timestamps.
