import hmac
import logging
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast
from urllib.parse import quote
from uuid import uuid4

from sqlalchemy import Table, delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.exceptions import (
    AuthRateLimitError,
    EmailAlreadyRegisteredError,
    GoogleAccountConflictError,
    InvalidCredentialsError,
)
from app.auth.models import (
    AuthOperationRateLimit,
    AuthSession,
    EmailVerificationToken,
    PasswordResetToken,
    PhoneOtpChallenge,
    User,
)
from app.auth.providers import EmailProvider, GoogleIdentity, SmsProvider
from app.auth.schemas import LoginRequest, RegisterRequest
from app.auth.security import (
    DUMMY_PASSWORD_HASH,
    hash_email_verification_token,
    hash_otp_code,
    hash_password,
    hash_password_reset_token,
    hash_rate_limit_actor,
    hash_session_token,
    make_email_verification_token,
    make_otp_code,
    make_password_reset_token,
    make_session_token,
    normalize_iranian_phone,
    verify_password,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthResult:
    user: User
    raw_token: str


@dataclass(frozen=True)
class OtpSendResult:
    retry_after_seconds: int


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def _new_session(user: User, ttl_seconds: int, now: datetime) -> tuple[AuthSession, str]:
    raw_token, token_hash = make_session_token()
    return (
        AuthSession(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=now + timedelta(seconds=ttl_seconds),
        ),
        raw_token,
    )


def _verification_url(frontend_origin: str, raw_token: str) -> str:
    return f"{frontend_origin.rstrip('/')}/verify-email?token={quote(raw_token)}"


def _deliver_email_verification(
    provider: EmailProvider,
    recipient: str,
    verification_url: str,
) -> None:
    try:
        provider.send_email_verification(recipient, verification_url)
    except Exception:
        logger.warning("Authentication email verification delivery failed")


def register_user(
    db: Session,
    payload: RegisterRequest,
    ttl_seconds: int,
    email_verification_ttl_seconds: int,
    frontend_origin: str,
    provider: EmailProvider,
) -> AuthResult:
    now = datetime.now(UTC)
    verification_raw_token, verification_hash = make_email_verification_token()
    recipient = normalize_email(str(payload.email))
    user = User(
        email=recipient,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.flush()
        auth_session, raw_token = _new_session(user, ttl_seconds, now)
        db.add(auth_session)
        db.add(
            EmailVerificationToken(
                user_id=user.id,
                token_hash=verification_hash,
                expires_at=now + timedelta(seconds=email_verification_ttl_seconds),
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
    _deliver_email_verification(
        provider,
        recipient,
        _verification_url(frontend_origin, verification_raw_token),
    )
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

    auth_session, raw_token = _new_session(user, ttl_seconds, datetime.now(UTC))
    db.add(auth_session)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    return AuthResult(user=user, raw_token=raw_token)


def authenticate_google(
    db: Session,
    identity: GoogleIdentity,
    session_ttl_seconds: int,
) -> AuthResult:
    now = datetime.now(UTC)
    normalized_google_email = (
        normalize_email(identity.email) if identity.email is not None else None
    )
    try:
        user = db.scalar(select(User).where(User.google_sub == identity.sub).with_for_update())
        if user is None:
            email_user = (
                db.scalar(
                    select(User).where(User.email == normalized_google_email).with_for_update()
                )
                if normalized_google_email is not None
                else None
            )
            if identity.email_verified and normalized_google_email is not None:
                if email_user is not None:
                    if email_user.google_sub not in {None, identity.sub}:
                        raise GoogleAccountConflictError
                    user = email_user
                    user.google_sub = identity.sub
                    user.email_verified_at = user.email_verified_at or now
                else:
                    user = User(
                        email=normalized_google_email,
                        google_sub=identity.sub,
                        email_verified_at=now,
                    )
                    db.add(user)
                    db.flush()
            else:
                if email_user is not None:
                    raise GoogleAccountConflictError
                user = User(google_sub=identity.sub)
                db.add(user)
                db.flush()
        elif (
            identity.email_verified
            and normalized_google_email is not None
            and user.email == normalized_google_email
            and user.email_verified_at is None
        ):
            user.email_verified_at = now

        auth_session, raw_token = _new_session(user, session_ttl_seconds, now)
        db.add(auth_session)
        db.commit()
        db.refresh(user)
    except GoogleAccountConflictError:
        db.rollback()
        raise
    except IntegrityError as error:
        db.rollback()
        raise GoogleAccountConflictError from error
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
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None or user.email is None:
        return
    raw_token, token_hash = make_password_reset_token()
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
        logger.warning("Authentication password reset delivery failed")


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


def request_email_verification(
    db: Session,
    user: User,
    ttl_seconds: int,
    frontend_origin: str,
    provider: EmailProvider,
) -> None:
    if user.email is None or user.email_verified_at is not None:
        return
    now = datetime.now(UTC)
    raw_token, token_hash = make_email_verification_token()
    db.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    db.add(
        EmailVerificationToken(
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
    _deliver_email_verification(
        provider,
        user.email,
        _verification_url(frontend_origin, raw_token),
    )


def verify_email(db: Session, raw_token: str, provider: EmailProvider) -> bool:
    now = datetime.now(UTC)
    token = db.scalar(
        select(EmailVerificationToken)
        .where(EmailVerificationToken.token_hash == hash_email_verification_token(raw_token))
        .with_for_update()
    )
    if token is None or token.used_at is not None or token.expires_at <= now:
        return False
    user = db.get(User, token.user_id)
    if user is None or user.email is None:
        return False
    user.email_verified_at = user.email_verified_at or now
    db.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    try:
        provider.send_welcome_email(user.email)
    except Exception:
        logger.warning("Authentication welcome email delivery failed")
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
        logger.warning("Authentication SMS OTP delivery failed")
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
    auth_session, raw_token = _new_session(user, session_ttl_seconds, now)
    db.add(auth_session)
    try:
        db.commit()
        db.refresh(user)
    except SQLAlchemyError:
        db.rollback()
        raise
    return AuthResult(user=user, raw_token=raw_token)


def consume_auth_rate_limit(
    db: Session,
    *,
    actor: str,
    operation: str,
    limit: int,
    window_seconds: int,
    hmac_secret: str,
    now: datetime | None = None,
) -> None:
    current = now or datetime.now(UTC)
    epoch = int(current.timestamp())
    window_epoch = epoch - (epoch % window_seconds)
    window_start = datetime.fromtimestamp(window_epoch, UTC)
    table = cast(Table, AuthOperationRateLimit.__table__)
    statement = (
        insert(table)
        .values(
            id=uuid4(),
            actor_hash=hash_rate_limit_actor(actor, hmac_secret),
            operation=operation,
            window_started_at=window_start,
            request_count=1,
        )
        .on_conflict_do_update(
            constraint="uq_auth_operation_rate_window",
            set_={
                "request_count": table.c.request_count + 1,
                "updated_at": current,
            },
        )
        .returning(table.c.request_count)
    )
    count = int(db.execute(statement).scalar_one())
    db.commit()
    if count > limit:
        raise AuthRateLimitError(window_epoch + window_seconds - epoch)
