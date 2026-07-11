# Authentication Module

The authentication module provides account creation, login, refresh rotation,
logout, profile management, password changes, and audit records.

## Endpoints

All routes are under `/api/v1/auth`.

- `POST /register`: create a user and issue tokens
- `POST /login`: authenticate and issue tokens
- `POST /refresh`: rotate a refresh token and issue a new token pair
- `POST /logout`: revoke the presented token
- `GET /me`: return the current user profile
- `PATCH /me`: update the current user name
- `POST /change-password`: verify the current password, set a new password, and revoke the current token

## Token Behavior

- Access and refresh tokens include user id, email, and role claims.
- Refresh uses rotation: the presented refresh token is revoked after the new pair is issued.
- Logout stores the presented token id in `revoked_tokens`.
- Expired, revoked, missing, and invalid JWTs return JSON errors.

## Password Rules

Passwords must contain at least 10 characters, uppercase and lowercase letters,
and a number. Passwords are stored only as bcrypt hashes.

## Audit

Authentication activity is recorded in two places:

- `login_attempts`: structured success/failure records with email, IP address, user agent, and reason
- `logs`: security events such as registration, login, failed login, logout, profile update, and password changes
