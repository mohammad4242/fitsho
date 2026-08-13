from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.auth.cookies import (
    clear_session_cookie,
    require_trusted_origin,
    set_session_cookie,
)
from app.auth.dependencies import get_current_user
from app.auth.exceptions import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
)
from app.auth.models import User
from app.auth.providers import EmailProvider, SmsProvider
from app.auth.schemas import (
    ForgotPasswordRequest,
    GenericMessageResponse,
    LoginRequest,
    PhoneOtpSentResponse,
    PhoneSendOtpRequest,
    PhoneVerifyOtpRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UserResponse,
)
from app.auth.service import (
    login_user,
    logout_session,
    register_user,
    request_password_reset,
    reset_password,
    send_phone_otp,
    verify_phone_otp,
)
from app.config import Settings, get_settings
from app.database.session import get_db

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

DatabaseSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
CurrentUser = Annotated[User, Depends(get_current_user)]

FORGOT_PASSWORD_MESSAGE = "If the account exists, a reset link has been sent."
PHONE_OTP_MESSAGE = "If the number can receive messages, an OTP has been sent."


def get_email_provider(request: Request) -> EmailProvider:
    return request.app.state.email_provider  # type: ignore[no-any-return]


EmailDelivery = Annotated[EmailProvider, Depends(get_email_provider)]


def get_sms_provider(request: Request) -> SmsProvider:
    return request.app.state.sms_provider  # type: ignore[no-any-return]


SmsDelivery = Annotated[SmsProvider, Depends(get_sms_provider)]


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
def register(
    payload: RegisterRequest,
    response: Response,
    db: DatabaseSession,
    settings: AppSettings,
) -> UserResponse:
    try:
        result = register_user(db, payload, settings.session_ttl_seconds)
    except EmailAlreadyRegisteredError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        ) from None
    set_session_cookie(response, result.raw_token, settings)
    return UserResponse.model_validate(result.user)


@router.post(
    "/login",
    response_model=UserResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def login(
    payload: LoginRequest,
    response: Response,
    db: DatabaseSession,
    settings: AppSettings,
) -> UserResponse:
    try:
        result = login_user(db, payload, settings.session_ttl_seconds)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from None
    set_session_cookie(response, result.raw_token, settings)
    return UserResponse.model_validate(result.user)


@router.post(
    "/forgot-password",
    response_model=GenericMessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_trusted_origin)],
)
def forgot_password(
    payload: ForgotPasswordRequest,
    db: DatabaseSession,
    settings: AppSettings,
    email_provider: EmailDelivery,
) -> GenericMessageResponse:
    request_password_reset(
        db,
        str(payload.email),
        settings.password_reset_ttl_seconds,
        settings.frontend_origin,
        email_provider,
    )
    return GenericMessageResponse(message=FORGOT_PASSWORD_MESSAGE)


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_trusted_origin)],
)
def reset_password_endpoint(
    payload: ResetPasswordRequest,
    db: DatabaseSession,
) -> None:
    if not reset_password(db, payload.token, payload.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )


@router.post(
    "/phone/send-otp",
    response_model=PhoneOtpSentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_trusted_origin)],
)
def phone_send_otp(
    payload: PhoneSendOtpRequest,
    db: DatabaseSession,
    settings: AppSettings,
    sms_provider: SmsDelivery,
) -> PhoneOtpSentResponse:
    result = send_phone_otp(
        db,
        payload.phone_number,
        settings.phone_otp_ttl_seconds,
        settings.phone_otp_resend_cooldown_seconds,
        settings.phone_otp_max_attempts,
        settings.phone_otp_hmac_secret.get_secret_value(),
        sms_provider,
    )
    return PhoneOtpSentResponse(
        message=PHONE_OTP_MESSAGE,
        retry_after_seconds=result.retry_after_seconds,
    )


@router.post(
    "/phone/verify-otp",
    response_model=UserResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def phone_verify_otp(
    payload: PhoneVerifyOtpRequest,
    response: Response,
    db: DatabaseSession,
    settings: AppSettings,
) -> UserResponse:
    result = verify_phone_otp(
        db,
        payload.phone_number,
        payload.code,
        settings.phone_otp_hmac_secret.get_secret_value(),
        settings.session_ttl_seconds,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired OTP",
        )
    set_session_cookie(response, result.raw_token, settings)
    return UserResponse.model_validate(result.user)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_trusted_origin)],
)
def logout(
    request: Request,
    response: Response,
    db: DatabaseSession,
    settings: AppSettings,
) -> None:
    logout_session(db, request.cookies.get(settings.session_cookie_name))
    clear_session_cookie(response, settings)


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)
