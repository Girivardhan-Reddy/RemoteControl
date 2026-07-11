# Database Migrations

This folder contains Alembic migrations managed through Flask-Migrate.

Common commands from `RemoteControl/backend`:

```powershell
flask db upgrade
flask db migrate -m "describe schema change"
flask db downgrade
python scripts/database_admin.py health
python scripts/database_admin.py seed-admin --email owner@example.com --name Owner
```

Use migrations for production PostgreSQL. The application may create tables
automatically only in development mode.
