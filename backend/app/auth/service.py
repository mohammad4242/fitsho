import hmac
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.exceptions import EmailAlreadyRegisteredError, InvalidCredentialsError
from app.auth.models import AuthSession, PasswordResetToken, PhoneOtpChallenge, User
from app.auth.providers import EmailProvider, SmsProvider
from app.auth.schemas import LoginRequest, RegisterRequest
from app.auth.security import (
    DUMMY_PASSWORD_HASH,
    hash_otp_code,
    hash_password,
    hash_password_reset_token,
    hash_session_token,
    make_otp_code,
    make_password_reset_token,
    make_session_token,
    normalize_iranian_phone,
    verify_password,
)


@dataclass(frozen=True)
class AuthResult:
    user: User
    raw_token: str


@dataclass(frozen=True)
class OtpSendResult:
    retry_after_seconds: int


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
    stored_hash = (
        user.password_hash
        if user is not None and user.password_hash is not None
        else DUMMY_PASSWORD_HASH
    )
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


def request_password_reset(
    db: Session,
    email: str,
    ttl_seconds: int,
    frontend_origin: str,
    provider: EmailProvider,
) -> None:
    raw_token, token_hash = make_password_reset_token()
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None or user.email is None:
        return

    now = datetime.now(UTC)
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
    )
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    reset_url = f"{frontend_origin.rstrip('/')}/reset-password?token={quote(raw_token)}"
    try:
        provider.send_password_reset(user.email, reset_url)
    except Exception:
        # Delivery failures must not turn this endpoint into an account-enumeration oracle.
        return


def reset_password(db: Session, raw_token: str, new_password: str) -> bool:
    now = datetime.now(UTC)
    token = db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == hash_password_reset_token(raw_token))
        .with_for_update()
    )
    if token is None or token.used_at is not None or token.expires_at <= now:
        return False
    user = db.get(User, token.user_id)
    if user is None or user.email is None:
        return False

    user.password_hash = hash_password(new_password)
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    return True


def send_phone_otp(
    db: Session,
    raw_phone_number: str,
    ttl_seconds: int,
    cooldown_seconds: int,
    max_attempts: int,
    hmac_secret: str,
    provider: SmsProvider,
) -> OtpSendResult:
    phone_number = normalize_iranian_phone(raw_phone_number)
    now = datetime.now(UTC)
    latest = db.scalar(
        select(PhoneOtpChallenge)
        .where(
            PhoneOtpChallenge.phone_number == phone_number,
            PhoneOtpChallenge.consumed_at.is_(None),
        )
        .order_by(PhoneOtpChallenge.created_at.desc(), PhoneOtpChallenge.id.desc())
        .limit(1)
        .with_for_update()
    )
    if (
        latest is not None
        and latest.consumed_at is None
        and latest.expires_at > now
        and latest.resend_available_at > now
    ):
        remaining = max(1, math.ceil((latest.resend_available_at - now).total_seconds()))
        return OtpSendResult(retry_after_seconds=remaining)

    db.execute(
        update(PhoneOtpChallenge)
        .where(
            PhoneOtpChallenge.phone_number == phone_number,
            PhoneOtpChallenge.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )
    code = make_otp_code()
    db.add(
        PhoneOtpChallenge(
            phone_number=phone_number,
            code_hash=hash_otp_code(phone_number, code, hmac_secret),
            expires_at=now + timedelta(seconds=ttl_seconds),
            resend_available_at=now + timedelta(seconds=cooldown_seconds),
            attempts_remaining=max_attempts,
        )
    )
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    try:
        provider.send_login_otp(phone_number, code)
    except Exception:
        # Delivery failures must not expose whether this number belongs to an account.
        pass
    return OtpSendResult(retry_after_seconds=cooldown_seconds)


def verify_phone_otp(
    db: Session,
    raw_phone_number: str,
    code: str,
    hmac_secret: str,
    session_ttl_seconds: int,
) -> AuthResult | None:
    phone_number = normalize_iranian_phone(raw_phone_number)
    now = datetime.now(UTC)
    challenge = db.scalar(
        select(PhoneOtpChallenge)
        .where(
            PhoneOtpChallenge.phone_number == phone_number,
            PhoneOtpChallenge.consumed_at.is_(None),
        )
        .order_by(PhoneOtpChallenge.created_at.desc(), PhoneOtpChallenge.id.desc())
        .limit(1)
        .with_for_update()
    )
    if challenge is None:
        return None
    if challenge.expires_at <= now or challenge.attempts_remaining <= 0:
        challenge.consumed_at = now
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            raise
        return None

    submitted_hash = hash_otp_code(phone_number, code, hmac_secret)
    if not hmac.compare_digest(challenge.code_hash, submitted_hash):
        challenge.attempts_remaining -= 1
        if challenge.attempts_remaining == 0:
            challenge.consumed_at = now
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            raise
        return None

    challenge.consumed_at = now
    user = db.scalar(select(User).where(User.phone_number == phone_number))
    if user is None:
        user = User(phone_number=phone_number)
        db.add(user)
        db.flush()
    raw_token, token_hash = make_session_token()
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=now + timedelta(seconds=session_ttl_seconds),
        )
    )
    try:
        db.commit()
        db.refresh(user)
    except SQLAlchemyError:
        db.rollback()
        raise
    return AuthResult(user=user, raw_token=raw_token)
