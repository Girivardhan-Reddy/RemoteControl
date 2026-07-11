"""Database administration CLI for development and deployment.

Usage:
    python scripts/database_admin.py health
    python scripts/database_admin.py create
    python scripts/database_admin.py seed-admin --email owner@example.com --name Owner
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys

CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app import create_app  # noqa: E402
from database import check_database_health, create_database_schema, drop_database_schema  # noqa: E402
from extensions import bcrypt, db  # noqa: E402
from models import User, UserRole  # noqa: E402
from utils.validators import validate_email, validate_password, validate_safe_name  # noqa: E402


def _seed_admin(args: argparse.Namespace) -> int:
    """Create or update an administrator account."""
    app = create_app()
    password = args.password or getpass.getpass("Admin password: ")
    email = validate_email(args.email)
    name = validate_safe_name(args.name, "name")
    validate_password(password)

    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(email=email, name=name, role=UserRole.ADMIN)
            db.session.add(user)
        user.name = name
        user.role = UserRole.ADMIN
        user.is_active = True
        user.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
        db.session.commit()
        print(json.dumps({"admin_user": user.to_dict()}, indent=2))
    return 0


def _health(_: argparse.Namespace) -> int:
    """Print database health as JSON."""
    app = create_app()
    status = check_database_health(app)
    print(json.dumps(status.to_dict(), indent=2))
    return 0 if status.connected else 1


def _create(_: argparse.Namespace) -> int:
    """Create all configured database tables."""
    app = create_app()
    create_database_schema(app)
    print(json.dumps({"schema": "created"}, indent=2))
    return 0


def _drop(_: argparse.Namespace) -> int:
    """Drop all non-production database tables."""
    app = create_app()
    drop_database_schema(app)
    print(json.dumps({"schema": "dropped"}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the command parser."""
    parser = argparse.ArgumentParser(description="Remote Control database administration")
    subparsers = parser.add_subparsers(dest="command", required=True)

    health_parser = subparsers.add_parser("health", help="Check database connectivity")
    health_parser.set_defaults(handler=_health)

    create_parser = subparsers.add_parser("create", help="Create database schema")
    create_parser.set_defaults(handler=_create)

    drop_parser = subparsers.add_parser("drop", help="Drop database schema outside production")
    drop_parser.set_defaults(handler=_drop)

    seed_parser = subparsers.add_parser("seed-admin", help="Create or update an admin user")
    seed_parser.add_argument("--email", required=True, help="Admin email address")
    seed_parser.add_argument("--name", required=True, help="Admin display name")
    seed_parser.add_argument("--password", help="Admin password; omitted prompts securely")
    seed_parser.set_defaults(handler=_seed_admin)
    return parser


def main() -> int:
    """Run the CLI."""
    parser = build_parser()
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
