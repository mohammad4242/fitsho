from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.exceptions import EmailAlreadyRegisteredError, InvalidCredentialsError
from app.auth.models import AuthSession, User
from app.auth.schemas import LoginRequest, RegisterRequest
from app.auth.security import (
    DUMMY_PASSWORD_HASH,
    hash_password,
    hash_session_token,
    make_session_token,
    verify_password,
)


@dataclass(frozen=True)
class AuthResult:
    user: User
    raw_token: str


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def register_user(
    db: Session,
    payload: RegisterRequest,
    ttl_seconds: int,
) -> AuthResult:
    raw_token, token_hash = make_session_token()
    user = User(
        email=normalize_email(str(payload.email)),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.flush()
        db.add(
            AuthSession(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
            )
        )
        db.commit()
        db.refresh(user)
    except IntegrityError as error:
        db.rollback()
        raise EmailAlreadyRegisteredError from error
    except SQLAlchemyError:
        db.rollback()
        raise
    return AuthResult(user=user, raw_token=raw_token)


def login_user(
    db: Session,
    payload: LoginRequest,
    ttl_seconds: int,
) -> AuthResult:
    email = normalize_email(str(payload.email))
    user = db.scalar(select(User).where(User.email == email))
    stored_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    password_is_valid = verify_password(payload.password, stored_hash)
    if user is None or not password_is_valid:
        raise InvalidCredentialsError

    raw_token, token_hash = make_session_token()
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
        )
    )
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    return AuthResult(user=user, raw_token=raw_token)


def user_for_session(db: Session, raw_token: str) -> User | None:
    auth_session = db.scalar(
        select(AuthSession).where(AuthSession.token_hash == hash_session_token(raw_token))
    )
    if auth_session is None:
        return None
    if auth_session.expires_at <= datetime.now(UTC):
        db.delete(auth_session)
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            raise
        return None
    return db.get(User, auth_session.user_id)


def logout_session(db: Session, raw_token: str | None) -> None:
    if raw_token is None:
        return
    auth_session = db.scalar(
        select(AuthSession).where(AuthSession.token_hash == hash_session_token(raw_token))
    )
    if auth_session is None:
        return
    db.delete(auth_session)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
