"""Authentication audit schema.

Revision ID: 0002_authentication_audit
Revises: 0001_initial_schema
Create Date: 2026-07-11
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_authentication_audit"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

login_attempt_result = sa.Enum("SUCCESS", "FAILURE", name="loginattemptresult")


def upgrade() -> None:
    """Create authentication audit tables."""
    bind = op.get_bind()
    login_attempt_result.create(bind, checkfirst=True)
    op.create_table(
        "login_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("result", login_attempt_result, nullable=False),
        sa.Column("reason", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_login_attempts_user_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_login_attempts"),
    )
    op.create_index("ix_login_attempts_email", "login_attempts", ["email"])
    op.create_index("ix_login_attempts_email_created", "login_attempts", ["email", "created_at"])
    op.create_index("ix_login_attempts_ip_address", "login_attempts", ["ip_address"])
    op.create_index("ix_login_attempts_ip_created", "login_attempts", ["ip_address", "created_at"])
    op.create_index("ix_login_attempts_result_created", "login_attempts", ["result", "created_at"])
    op.create_index("ix_login_attempts_user_id", "login_attempts", ["user_id"])


def downgrade() -> None:
    """Drop authentication audit tables."""
    op.drop_index("ix_login_attempts_user_id", table_name="login_attempts")
    op.drop_index("ix_login_attempts_result_created", table_name="login_attempts")
    op.drop_index("ix_login_attempts_ip_created", table_name="login_attempts")
    op.drop_index("ix_login_attempts_ip_address", table_name="login_attempts")
    op.drop_index("ix_login_attempts_email_created", table_name="login_attempts")
    op.drop_index("ix_login_attempts_email", table_name="login_attempts")
    op.drop_table("login_attempts")
    bind = op.get_bind()
    login_attempt_result.drop(bind, checkfirst=True)
