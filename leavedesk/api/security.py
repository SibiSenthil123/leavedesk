"""Passwords and tokens. Nothing here knows about HTTP."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from leavedesk.api.config import Settings

# Argon2id: slow on purpose, salted automatically. Never store or log plain passwords.
_password_hash = PasswordHash.recommended()


class InvalidTokenError(Exception):
    """The token is missing, expired, tampered with or malformed."""


def hash_password(plain: str) -> str:
    return _password_hash.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _password_hash.verify(plain, hashed)


def create_access_token(user_id: UUID, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(
        claims, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str, settings: Settings) -> UUID:
    """Return the user id inside a valid token, or raise InvalidTokenError."""
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            # A fixed list stops the "alg: none" trick.
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp"]},
        )
        return UUID(claims["sub"])
    except (jwt.PyJWTError, ValueError) as exc:
        raise InvalidTokenError(str(exc)) from exc
