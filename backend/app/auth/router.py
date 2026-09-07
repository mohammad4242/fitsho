from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from google.auth.exceptions import GoogleAuthError
from sqlalchemy.orm import Session

from app.auth.cookies import (
    clear_session_cookie,
    require_trusted_origin,
    set_session_cookie,
)
from app.auth.dependencies import get_current_mobile_session, get_current_user
from app.auth.exceptions import (
    AuthRateLimitError,
    EmailAlreadyRegisteredError,
    GoogleAccountConflictError,
    InvalidCredentialsError,
)
from app.auth.models import User
from app.auth.providers import EmailProvider, GoogleIdentityProvider, SmsProvider
from app.auth.schemas import (
    EmailVerificationRequest,
    ForgotPasswordRequest,
    GenericMessageResponse,
    GoogleAuthRequest,
    LoginRequest,
    MobileAuthResponse,
    MobileGoogleLoginRequest,
    MobilePasswordLoginRequest,
    MobilePhoneSendOtpRequest,
    MobilePhoneVerifyOtpRequest,
    MobileRefreshRequest,
    PhoneOtpSentResponse,
    PhoneSendOtpRequest,
    PhoneVerifyOtpRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UserResponse,
)
from app.auth.service import (
    MobileAccessContext,
    MobileAuthResult,
    authenticate_google,
    authenticate_mobile_google,
    authenticate_mobile_phone_otp,
    authenticate_password_user,
    consume_auth_rate_limit,
    issue_mobile_tokens,
    login_user,
    logout_session,
    normalize_email,
    refresh_mobile_tokens,
    register_user,
    request_email_verification,
    request_password_reset,
    reset_password,
    revoke_all_mobile_token_families,
    revoke_mobile_token_family,
    send_phone_otp,
    verify_email,
    verify_phone_otp,
)
from app.config import Settings, get_settings
from app.database.session import get_db

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

DatabaseSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentMobileSession = Annotated[MobileAccessContext, Depends(get_current_mobile_session)]

FORGOT_PASSWORD_MESSAGE = "If the account exists, a reset link has been sent."
PHONE_OTP_MESSAGE = "If the number can receive messages, an OTP has been sent."
EMAIL_VERIFICATION_MESSAGE = "If verification is available, an email has been sent."
AUTH_RATE_LIMIT_MESSAGE = "Too many authentication requests"


def get_email_provider(request: Request) -> EmailProvider:
    return request.app.state.email_provider  # type: ignore[no-any-return]


EmailDelivery = Annotated[EmailProvider, Depends(get_email_provider)]


def get_sms_provider(request: Request) -> SmsProvider:
    return request.app.state.sms_provider  # type: ignore[no-any-return]


SmsDelivery = Annotated[SmsProvider, Depends(get_sms_provider)]


def get_google_identity_provider(request: Request) -> GoogleIdentityProvider:
    return request.app.state.google_identity_provider  # type: ignore[no-any-return]


GoogleIdentityDelivery = Annotated[
    GoogleIdentityProvider,
    Depends(get_google_identity_provider),
]


def _client_actor(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"


def _consume_limit(
    db: Session,
    settings: Settings,
    *,
    actor: str,
    operation: str,
    limit: int,
) -> None:
    try:
        consume_auth_rate_limit(
            db,
            actor=actor,
            operation=operation,
            limit=limit,
            window_seconds=settings.auth_rate_limit_window_seconds,
            hmac_secret=settings.phone_otp_hmac_secret.get_secret_value(),
        )
    except AuthRateLimitError as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=AUTH_RATE_LIMIT_MESSAGE,
            headers={"Retry-After": str(error.retry_after_seconds)},
        ) from None


def _mobile_auth_response(result: MobileAuthResult) -> MobileAuthResponse:
    return MobileAuthResponse(
        access_token=result.raw_access_token,
        refresh_token=result.raw_refresh_token,
        expires_in=result.access_expires_in,
        refresh_expires_in=result.refresh_expires_in,
        user=UserResponse.model_validate(result.user),
    )


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
    email_provider: EmailDelivery,
) -> UserResponse:
    try:
        result = register_user(
            db,
            payload,
            settings.session_ttl_seconds,
            settings.email_verification_ttl_seconds,
            settings.frontend_origin,
            email_provider,
        )
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
    "/mobile/password",
    response_model=MobileAuthResponse,
)
def mobile_password_login(
    payload: MobilePasswordLoginRequest,
    db: DatabaseSession,
    settings: AppSettings,
) -> MobileAuthResponse:
    try:
        user = authenticate_password_user(
            db,
            LoginRequest(email=payload.email, password=payload.password),
        )
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    return _mobile_auth_response(
        issue_mobile_tokens(
            db,
            user,
            device_id=payload.device_id,
            platform=payload.platform,
            app_version=payload.app_version,
            device_name=payload.device_name,
            access_ttl_seconds=settings.mobile_access_token_ttl_seconds,
            refresh_ttl_seconds=settings.mobile_refresh_token_ttl_seconds,
        )
    )


@router.post(
    "/google",
    response_model=UserResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def google_auth(
    payload: GoogleAuthRequest,
    request: Request,
    response: Response,
    db: DatabaseSession,
    settings: AppSettings,
    provider: GoogleIdentityDelivery,
) -> UserResponse:
    _consume_limit(
        db,
        settings,
        actor=f"ip:{_client_actor(request)}",
        operation="google",
        limit=settings.auth_google_ip_limit,
    )
    try:
        identity = provider.verify(payload.credential)
    except (GoogleAuthError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google authentication failed",
        ) from None
    try:
        result = authenticate_google(db, identity, settings.session_ttl_seconds)
    except GoogleAccountConflictError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to use this Google account",
        ) from None
    set_session_cookie(response, result.raw_token, settings)
    return UserResponse.model_validate(result.user)


@router.post(
    "/mobile/google",
    response_model=MobileAuthResponse,
)
def mobile_google_auth(
    payload: MobileGoogleLoginRequest,
    db: DatabaseSession,
    settings: AppSettings,
    provider: GoogleIdentityDelivery,
) -> MobileAuthResponse:
    try:
        identity = provider.verify(payload.credential)
    except (GoogleAuthError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    try:
        result = authenticate_mobile_google(
            db,
            identity,
            device_id=payload.device_id,
            platform=payload.platform,
            app_version=payload.app_version,
            device_name=payload.device_name,
            access_ttl_seconds=settings.mobile_access_token_ttl_seconds,
            refresh_ttl_seconds=settings.mobile_refresh_token_ttl_seconds,
        )
    except GoogleAccountConflictError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to use this Google account",
        ) from None
    return _mobile_auth_response(result)


@router.post(
    "/mobile/phone/send-otp",
    response_model=PhoneOtpSentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def mobile_phone_send_otp(
    payload: MobilePhoneSendOtpRequest,
    request: Request,
    db: DatabaseSession,
    settings: AppSettings,
    sms_provider: SmsDelivery,
) -> PhoneOtpSentResponse:
    _consume_limit(
        db,
        settings,
        actor=f"ip:{_client_actor(request)}",
        operation="mobile-phone-otp-ip",
        limit=settings.auth_phone_otp_ip_limit,
    )
    _consume_limit(
        db,
        settings,
        actor=f"phone:{payload.phone_number}",
        operation="mobile-phone-otp-phone",
        limit=settings.auth_phone_otp_identifier_limit,
    )
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
    "/mobile/phone/verify-otp",
    response_model=MobileAuthResponse,
)
def mobile_phone_verify_otp(
    payload: MobilePhoneVerifyOtpRequest,
    db: DatabaseSession,
    settings: AppSettings,
) -> MobileAuthResponse:
    result = authenticate_mobile_phone_otp(
        db,
        payload.phone_number,
        payload.code,
        settings.phone_otp_hmac_secret.get_secret_value(),
        device_id=payload.device_id,
        platform=payload.platform,
        app_version=payload.app_version,
        device_name=payload.device_name,
        access_ttl_seconds=settings.mobile_access_token_ttl_seconds,
        refresh_ttl_seconds=settings.mobile_refresh_token_ttl_seconds,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired OTP",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _mobile_auth_response(result)


@router.post(
    "/mobile/refresh",
    response_model=MobileAuthResponse,
)
def mobile_refresh(
    payload: MobileRefreshRequest,
    db: DatabaseSession,
    settings: AppSettings,
) -> MobileAuthResponse:
    result = refresh_mobile_tokens(
        db,
        payload.refresh_token,
        access_ttl_seconds=settings.mobile_access_token_ttl_seconds,
        refresh_ttl_seconds=settings.mobile_refresh_token_ttl_seconds,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _mobile_auth_response(result)


@router.post(
    "/mobile/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
def mobile_logout(
    session: CurrentMobileSession,
    db: DatabaseSession,
) -> None:
    revoke_mobile_token_family(db, session.family, reason="logout")


@router.post(
    "/mobile/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
)
def mobile_logout_all(
    session: CurrentMobileSession,
    db: DatabaseSession,
) -> None:
    revoke_all_mobile_token_families(db, session.user.id, reason="logout_all")


@router.post(
    "/forgot-password",
    response_model=GenericMessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_trusted_origin)],
)
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: DatabaseSession,
    settings: AppSettings,
    email_provider: EmailDelivery,
) -> GenericMessageResponse:
    _consume_limit(
        db,
        settings,
        actor=f"ip:{_client_actor(request)}",
        operation="forgot-password-ip",
        limit=settings.auth_forgot_password_ip_limit,
    )
    _consume_limit(
        db,
        settings,
        actor=f"email:{normalize_email(str(payload.email))}",
        operation="forgot-password-email",
        limit=settings.auth_forgot_password_identifier_limit,
    )
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
    "/email/send-verification",
    response_model=GenericMessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_trusted_origin)],
)
def email_send_verification(
    request: Request,
    user: CurrentUser,
    db: DatabaseSession,
    settings: AppSettings,
    email_provider: EmailDelivery,
) -> GenericMessageResponse:
    _consume_limit(
        db,
        settings,
        actor=f"ip:{_client_actor(request)}",
        operation="email-verification-ip",
        limit=settings.auth_email_verification_ip_limit,
    )
    _consume_limit(
        db,
        settings,
        actor=f"user:{user.id}",
        operation="email-verification-user",
        limit=settings.auth_email_verification_user_limit,
    )
    request_email_verification(
        db,
        user,
        settings.email_verification_ttl_seconds,
        settings.frontend_origin,
        email_provider,
    )
    return GenericMessageResponse(message=EMAIL_VERIFICATION_MESSAGE)


@router.post(
    "/email/verify",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_trusted_origin)],
)
def email_verify(
    payload: EmailVerificationRequest,
    db: DatabaseSession,
    email_provider: EmailDelivery,
) -> None:
    if not verify_email(db, payload.token, email_provider):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )


@router.post(
    "/phone/send-otp",
    response_model=PhoneOtpSentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_trusted_origin)],
)
def phone_send_otp(
    payload: PhoneSendOtpRequest,
    request: Request,
    db: DatabaseSession,
    settings: AppSettings,
    sms_provider: SmsDelivery,
) -> PhoneOtpSentResponse:
    _consume_limit(
        db,
        settings,
        actor=f"ip:{_client_actor(request)}",
        operation="phone-otp-ip",
        limit=settings.auth_phone_otp_ip_limit,
    )
    _consume_limit(
        db,
        settings,
        actor=f"phone:{payload.phone_number}",
        operation="phone-otp-phone",
        limit=settings.auth_phone_otp_identifier_limit,
    )
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
