from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.exceptions import EmailAlreadyRegisteredError
from app.auth.models import AuthSession, User
from app.auth.schemas import RegisterRequest
from app.auth.security import hash_password, make_session_token


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
    return AuthResult(user=user, raw_token=raw_token)
