"""Device registration metadata.

Revision ID: 0003_device_registration
Revises: 0002_authentication_audit
Create Date: 2026-07-11
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_device_registration"
down_revision = "0002_authentication_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add pairing state and device metadata columns."""
    op.add_column("devices", sa.Column("is_paired", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("devices", sa.Column("os_version", sa.String(length=120), nullable=True))
    op.add_column("devices", sa.Column("capabilities", sa.JSON(), nullable=True))
    op.alter_column("devices", "is_paired", server_default=None)


def downgrade() -> None:
    """Remove pairing state and device metadata columns."""
    op.drop_column("devices", "capabilities")
    op.drop_column("devices", "os_version")
    op.drop_column("devices", "is_paired")
