"""Create the first administrator account.

Run from RemoteControl/backend:
    python create_admin.py
"""

from __future__ import annotations

import getpass

from app import create_app
from extensions import bcrypt, db
from models import User, UserRole
from utils.validators import validate_email, validate_password, validate_safe_name


def prompt_non_empty(label: str) -> str:
    """Prompt until a non-empty value is supplied."""
    while True:
        value = input(f"{label}: ").strip()
        if value:
            return value
        print(f"{label} is required.")


def main() -> int:
    """Create or promote an admin account."""
    app = create_app()
    with app.app_context():
        name = validate_safe_name(prompt_non_empty("Name"), "name")
        email = validate_email(prompt_non_empty("Email"))
        while True:
            password = getpass.getpass("Password: ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                print("Passwords do not match.")
                continue
            validate_password(password)
            break

        user = User.query.filter_by(email=email).first()
        created = user is None
        if user is None:
            user = User(email=email, name=name)
            db.session.add(user)

        user.name = name
        user.role = UserRole.ADMIN
        user.is_active = True
        user.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
        db.session.commit()
        action = "Created" if created else "Updated"
        print(f"{action} admin account: {user.email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
