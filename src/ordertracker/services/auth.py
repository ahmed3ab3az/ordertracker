"""Authentication: password hashing, login throttling, session tokens."""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..constants import (
    BCRYPT_ROUNDS,
    LOGIN_LOCKOUT_MINUTES,
    MAX_LOGIN_ATTEMPTS,
    SESSION_TIMEOUT_MINUTES,
    AuditAction,
    EntityType,
    UserRole,
)
from ..db.models import User
from .audit import write_audit


class AuthError(Exception):
    pass


class AccountLocked(AuthError):
    def __init__(self, locked_until: datetime) -> None:
        super().__init__(f"Account locked until {locked_until.isoformat()}")
        self.locked_until = locked_until


class InvalidCredentials(AuthError):
    pass


class AccountInactive(AuthError):
    pass


# ---------------------------------------------------------------------------
# Password handling
# ---------------------------------------------------------------------------
def hash_password(plain: str) -> str:
    if not plain:
        raise ValueError("Password cannot be empty.")
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------
@dataclass
class SessionInfo:
    """In-memory representation of a logged-in user's session."""

    user_id: uuid.UUID
    username: str
    role: UserRole
    token: str
    issued_at: datetime
    last_activity_at: datetime

    def touch(self) -> None:
        self.last_activity_at = _utcnow()

    def expired(self) -> bool:
        return _utcnow() - self.last_activity_at >= timedelta(minutes=SESSION_TIMEOUT_MINUTES)


# ---------------------------------------------------------------------------
# Login flow
# ---------------------------------------------------------------------------
def authenticate(session: Session, username: str, password: str) -> SessionInfo:
    user = session.execute(
        select(User).where(User.username == username)
    ).scalar_one_or_none()

    if user is None:
        # Audit the failed attempt without leaking the username.
        write_audit(
            session,
            user_id=None,
            entity_type=EntityType.USER,
            entity_id="-",
            action=AuditAction.LOGIN_FAILED,
            new={"attempted_username": username},
        )
        session.commit()
        raise InvalidCredentials("Invalid username or password.")

    now = _utcnow()
    if user.locked_until and user.locked_until > now:
        raise AccountLocked(user.locked_until)

    if not user.active:
        raise AccountInactive("Account is inactive.")

    if not verify_password(password, user.password_hash):
        user.failed_attempts += 1
        if user.failed_attempts >= MAX_LOGIN_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=LOGIN_LOCKOUT_MINUTES)
            user.failed_attempts = 0
        write_audit(
            session,
            user_id=user.user_id,
            entity_type=EntityType.USER,
            entity_id=user.user_id,
            action=AuditAction.LOGIN_FAILED,
            new={"failed_attempts": user.failed_attempts},
        )
        session.commit()
        raise InvalidCredentials("Invalid username or password.")

    # Success: reset throttling, stamp last login.
    user.failed_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    write_audit(
        session,
        user_id=user.user_id,
        entity_type=EntityType.USER,
        entity_id=user.user_id,
        action=AuditAction.LOGIN,
    )
    session.commit()

    return SessionInfo(
        user_id=user.user_id,
        username=user.username,
        role=user.role,
        token=secrets.token_urlsafe(32),
        issued_at=now,
        last_activity_at=now,
    )


def change_password(session: Session, *, user_id: uuid.UUID, new_password: str) -> None:
    user = session.get(User, user_id)
    if user is None:
        raise InvalidCredentials("User not found.")
    user.password_hash = hash_password(new_password)
    write_audit(
        session,
        user_id=user.user_id,
        entity_type=EntityType.USER,
        entity_id=user.user_id,
        action=AuditAction.UPDATE,
        new={"password_changed": True},
    )
    session.commit()


def require_admin(s: SessionInfo) -> None:
    if s.role is not UserRole.ADMIN:
        raise PermissionError("Admin role required.")
