"""Password, token, session, and authentication rate-limit helpers."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import case
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    AUTH_REQUIRE_EMAIL_VERIFICATION,
    REFRESH_TOKEN_EXPIRE_DAYS,
    SECRET_KEY,
)
from app.database.connection import get_db
from app.database.models import AuthRateLimitBucket, AuthSession, User

password_hasher = PasswordHasher()
bearer_scheme = HTTPBearer(auto_error=False)


class AuthenticationError(ValueError):
    """Raised when an access or refresh credential is invalid."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, encoded_password: str) -> bool:
    try:
        return password_hasher.verify(encoded_password, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(encoded_password: str) -> bool:
    return password_hasher.check_needs_rehash(encoded_password)


def hash_opaque_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_rate_limit_key(value: str) -> str:
    return hmac.new(SECRET_KEY.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def create_auth_session(db: Session, user: User) -> tuple[AuthSession, str, str]:
    refresh_token = new_refresh_token()
    csrf_token = new_csrf_token()
    now = utc_now()
    session = AuthSession(
        user_id=user.id,
        refresh_token_hash=hash_opaque_token(refresh_token),
        csrf_token_hash=hash_opaque_token(csrf_token),
        expires_at=now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        last_used_at=now,
    )
    db.add(session)
    db.flush()
    return session, refresh_token, csrf_token


def create_access_token(user: User, session_id: str) -> str:
    issued_at = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user.id),
            "sid": session_id,
            "type": "access",
            "iat": issued_at,
            "exp": issued_at + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
            "jti": secrets.token_urlsafe(16),
        },
        SECRET_KEY,
        algorithm="HS256",
    )


def authenticate_access_token(token: str, db: Session) -> User:
    try:
        claims = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "sid", "type"]},
        )
        if claims.get("type") != "access":
            raise AuthenticationError("Invalid access token.")
        session_id = claims["sid"]
        user_id = claims["sub"]
    except (jwt.InvalidTokenError, KeyError, TypeError) as exc:
        raise AuthenticationError("Invalid or expired access token.") from exc

    try:
        session_uuid = UUID(session_id)
        user_uuid = UUID(user_id)
        auth_session = db.get(AuthSession, session_uuid)
        user = db.get(User, user_uuid)
    except (ValueError, TypeError) as exc:
        raise AuthenticationError("Invalid access token.") from exc
    if (
        auth_session is None
        or auth_session.user_id != user_uuid
        or auth_session.revoked_at is not None
        or auth_session.expires_at <= utc_now()
        or user is None
        or not user.is_active
        or (AUTH_REQUIRE_EMAIL_VERIFICATION and not user.is_verified)
    ):
        raise AuthenticationError("Invalid or expired access token.")
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Authentication is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return authenticate_access_token(credentials.credentials, db)
    except AuthenticationError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def verify_csrf_token(session: AuthSession, csrf_token: str | None) -> bool:
    return bool(
        csrf_token
        and hmac.compare_digest(
            session.csrf_token_hash,
            hash_opaque_token(csrf_token),
        )
    )


def refresh_access_session(
    db: Session,
    refresh_token: str | None,
    csrf_token: str | None,
) -> tuple[User, AuthSession, str, str]:
    if not refresh_token:
        raise AuthenticationError("A valid refresh session is required.")
    auth_session = db.query(AuthSession).filter(
        AuthSession.refresh_token_hash == hash_opaque_token(refresh_token),
    ).with_for_update().first()
    if (
        auth_session is None
        or auth_session.revoked_at is not None
        or auth_session.expires_at <= utc_now()
        or not verify_csrf_token(auth_session, csrf_token)
    ):
        raise AuthenticationError("A valid refresh session is required.")

    user = db.get(User, auth_session.user_id)
    if user is None or not user.is_active or (
        AUTH_REQUIRE_EMAIL_VERIFICATION and not user.is_verified
    ):
        auth_session.revoked_at = utc_now()
        db.commit()
        raise AuthenticationError("A valid refresh session is required.")

    new_refresh = new_refresh_token()
    new_csrf = new_csrf_token()
    now = utc_now()
    auth_session.refresh_token_hash = hash_opaque_token(new_refresh)
    auth_session.csrf_token_hash = hash_opaque_token(new_csrf)
    auth_session.expires_at = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    auth_session.last_used_at = now
    db.flush()
    return user, auth_session, new_refresh, new_csrf


def _rate_limit_insert(db: Session, key_hash: str, now: datetime, window: timedelta) -> None:
    cutoff = now - window
    expired = AuthRateLimitBucket.window_started_at <= cutoff
    values = {"key_hash": key_hash, "window_started_at": now, "attempts": 1}
    update_values = {
        "window_started_at": case(
            (expired, now),
            else_=AuthRateLimitBucket.window_started_at,
        ),
        "attempts": case(
            (expired, 1),
            else_=AuthRateLimitBucket.attempts + 1,
        ),
    }
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        statement = postgresql_insert(AuthRateLimitBucket).values(**values).on_conflict_do_update(
            index_elements=[AuthRateLimitBucket.key_hash],
            set_=update_values,
        )
    elif dialect == "sqlite":
        statement = sqlite_insert(AuthRateLimitBucket).values(**values).on_conflict_do_update(
            index_elements=[AuthRateLimitBucket.key_hash],
            set_=update_values,
        )
    else:
        raise RuntimeError("Authentication rate limits require PostgreSQL or SQLite.")
    db.execute(statement)


def enforce_rate_limits(
    db: Session,
    *,
    action: str,
    identities: list[tuple[str, int]],
    window: timedelta,
) -> None:
    now = utc_now()
    db.query(AuthRateLimitBucket).filter(
        AuthRateLimitBucket.window_started_at < now - timedelta(days=1)
    ).delete(synchronize_session=False)
    exceeded = False
    for identity, limit in identities:
        key_hash = hash_rate_limit_key(f"{action}:{identity}")
        _rate_limit_insert(db, key_hash, now, window)
        bucket = db.query(AuthRateLimitBucket).filter(
            AuthRateLimitBucket.key_hash == key_hash
        ).populate_existing().first()
        exceeded = exceeded or bool(bucket and bucket.attempts > limit)
    db.commit()
    if exceeded:
        raise AuthenticationError("Too many attempts. Please wait before trying again.")
