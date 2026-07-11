"""Input validation helpers."""

from __future__ import annotations

import re
from typing import Any

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SAFE_NAME_RE = re.compile(r"^[\w .\-()]{1,120}$", re.UNICODE)


class ValidationError(ValueError):
    """Raised when client input fails validation."""


def require_json(data: Any) -> dict:
    """Require a JSON object body."""
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object.")
    return data


def require_string(data: dict, field: str, *, min_len: int = 1, max_len: int = 255) -> str:
    """Validate and return a stripped string field."""
    value = data.get(field)
    if not isinstance(value, str):
        raise ValidationError(f"{field} is required.")
    value = value.strip()
    if len(value) < min_len or len(value) > max_len:
        raise ValidationError(f"{field} must be between {min_len} and {max_len} characters.")
    return value


def optional_string(data: dict, field: str, *, max_len: int = 255) -> str | None:
    """Validate an optional string field."""
    value = data.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string.")
    value = value.strip()
    if len(value) > max_len:
        raise ValidationError(f"{field} must be {max_len} characters or fewer.")
    return value


def validate_email(email: str) -> str:
    """Validate an email address."""
    normalized = email.strip().lower()
    if not EMAIL_RE.match(normalized):
        raise ValidationError("A valid email address is required.")
    return normalized


def validate_password(password: str) -> str:
    """Validate password strength."""
    if len(password) < 10:
        raise ValidationError("Password must be at least 10 characters.")
    if not re.search(r"[A-Z]", password):
        raise ValidationError("Password must include an uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise ValidationError("Password must include a lowercase letter.")
    if not re.search(r"\d", password):
        raise ValidationError("Password must include a number.")
    return password


def validate_safe_name(value: str, field: str) -> str:
    """Validate a display name or device name."""
    if not SAFE_NAME_RE.match(value):
        raise ValidationError(f"{field} contains unsupported characters.")
    return value
