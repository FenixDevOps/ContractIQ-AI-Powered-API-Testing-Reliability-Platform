"""Account registration, authentication, and recovery endpoints."""

import logging
import secrets
import hmac
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    AUTH_ALLOW_REGISTRATION,
    AUTH_COOKIE_SAMESITE,
    AUTH_COOKIE_SECURE,
    AUTH_REQUIRE_EMAIL_VERIFICATION,
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS,
    FRONTEND_BASE_URL,
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from app.database.connection import get_db
from app.database.models import (
    AuthSession,
    EmailVerificationToken,
    PasswordResetToken,
    User,
)
from app.schemas.auth import (
    AuthResponse,
    EmailVerificationConfirm,
    EmailVerificationRequest,
    LoginRequest,
    MessageOut,
    PasswordChange,
    PasswordResetConfirm,
    PasswordResetRequest,
    ProfileUpdate,
    RegisterRequest,
    UserOut,
)
from app.services.authentication import (
    AuthenticationError,
    authenticate_access_token,
    create_access_token,
    create_auth_session,
    enforce_rate_limits,
    get_current_user,
    hash_opaque_token,
    hash_password,
    password_needs_rehash,
    refresh_access_session,
    utc_now,
    verify_csrf_token,
    verify_password,
)
from app.services.email_delivery import (
    EmailDeliveryError,
    email_delivery_configured,
    send_security_email,
)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
logger = logging.getLogger(__name__)
REFRESH_COOKIE = "contractiq_refresh"
CSRF_COOKIE = "contractiq_csrf"
CSRF_HEADER = "X-CSRF-Token"
RESET_MESSAGE = "If an account matches that email, password reset instructions will be sent."
VERIFICATION_MESSAGE = "If an account needs verification, instructions will be sent."


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _rate_limit(db: Session, request: Request, action: str, email: str, *, max_email: int = 5) -> None:
    try:
        enforce_rate_limits(
            db,
            action=action,
            identities=[
                (f"ip:{_client_ip(request)}", 20),
                (f"email:{email}", max_email),
            ],
            window=timedelta(minutes=15),
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            str(exc),
            headers={"Retry-After": "900"},
        ) from exc


def _set_auth_cookies(response: Response, refresh_token: str, csrf_token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite=AUTH_COOKIE_SAMESITE,
        path="/api/v1/auth",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=False,
        secure=AUTH_COOKIE_SECURE,
        samesite=AUTH_COOKIE_SAMESITE,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth", samesite=AUTH_COOKIE_SAMESITE)
    response.delete_cookie(CSRF_COOKIE, path="/", samesite=AUTH_COOKIE_SAMESITE)


def _auth_response(db: Session, user: User, response: Response) -> AuthResponse:
    auth_session, refresh_token, csrf_token = create_auth_session(db, user)
    db.commit()
    _set_auth_cookies(response, refresh_token, csrf_token)
    return AuthResponse(
        access_token=create_access_token(user, str(auth_session.id)),
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user),
    )


def _send_email_verification(db: Session, user: User) -> None:
    token = secrets.token_urlsafe(32)
    db.query(EmailVerificationToken).filter(
        EmailVerificationToken.user_id == user.id,
        EmailVerificationToken.used_at.is_(None),
    ).delete(synchronize_session=False)
    token_record = EmailVerificationToken(
        user_id=user.id,
        token_hash=hash_opaque_token(token),
        expires_at=utc_now() + timedelta(hours=EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS),
    )
    db.add(token_record)
    db.flush()
    verification_url = f"{FRONTEND_BASE_URL}/#verify_token={token}"
    send_security_email(
        user.email,
        "Verify your ContractIQ email",
        f"Use this one-time link to verify your email address. It expires in "
        f"{EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS} hours:\n\n{verification_url}\n\n"
        "If you did not create this account, you can ignore this email.",
    )


def get_current_user_from_token(token: str, db: Session) -> User:
    try:
        return authenticate_access_token(token, db)
    except AuthenticationError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired access token.") from exc


@router.post("/register", response_model=AuthResponse | MessageOut, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    if not AUTH_ALLOW_REGISTRATION:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account registration is disabled.")

    email = str(payload.email).strip().lower()
    _rate_limit(db, request, "register", email, max_email=10)
    if db.query(User.id).filter(User.email == email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with that email already exists.")
    if AUTH_REQUIRE_EMAIL_VERIFICATION and not email_delivery_configured():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Email verification delivery is not configured. Contact the workspace administrator.",
        )

    user = User(
        full_name=payload.full_name,
        email=email,
        hashed_password=hash_password(payload.password),
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    db.flush()
    try:
        if AUTH_REQUIRE_EMAIL_VERIFICATION:
            _send_email_verification(db, user)
            db.commit()
            return MessageOut(message="Check your email for a verification link before signing in.")
        return _auth_response(db, user, response)
    except EmailDeliveryError as exc:
        db.rollback()
        logger.error("Email verification delivery failed.")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Email verification could not be delivered. Try again later.",
        ) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with that email already exists.") from exc


@router.post("/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    email = str(payload.email).strip().lower()
    _rate_limit(db, request, "login", email)
    user = db.query(User).filter(User.email == email).first()
    valid_password = verify_password(
        payload.password,
        user.hashed_password if user else _DUMMY_PASSWORD_HASH,
    )
    if not user or not user.is_active or not valid_password:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Email or password is incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if AUTH_REQUIRE_EMAIL_VERIFICATION and not user.is_verified:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Verify your email address before signing in. You can request a new verification email.",
        )
    if password_needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(payload.password)
    return _auth_response(db, user, response)


@router.post("/refresh", response_model=AuthResponse)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    csrf_cookie = request.cookies.get(CSRF_COOKIE)
    csrf_header = request.headers.get(CSRF_HEADER)
    if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF token is invalid.")
    try:
        user, auth_session, new_refresh, new_csrf = refresh_access_session(
            db,
            request.cookies.get(REFRESH_COOKIE),
            csrf_header,
        )
        db.commit()
    except AuthenticationError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Refresh session is invalid or expired.",
        ) from exc
    _set_auth_cookies(response, new_refresh, new_csrf)
    return AuthResponse(
        access_token=create_access_token(user, str(auth_session.id)),
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> Response:
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    csrf_cookie = request.cookies.get(CSRF_COOKIE)
    csrf_header = request.headers.get(CSRF_HEADER)
    if refresh_token:
        auth_session = db.query(AuthSession).filter(
            AuthSession.refresh_token_hash == hash_opaque_token(refresh_token),
        ).first()
        if auth_session and (
            not csrf_cookie
            or not csrf_header
            or not hmac.compare_digest(csrf_cookie, csrf_header)
            or not verify_csrf_token(auth_session, csrf_header)
        ):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF token is invalid.")
        if auth_session:
            auth_session.revoked_at = utc_now()
            db.commit()
    _clear_auth_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserOut)
def read_profile(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
def update_profile(
    payload: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    user.full_name = payload.full_name
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/change-password", response_model=MessageOut)
def change_password(
    payload: PasswordChange,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageOut:
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect.")
    if payload.current_password == payload.new_password:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choose a new password.")
    user.hashed_password = hash_password(payload.new_password)
    db.query(AuthSession).filter(AuthSession.user_id == user.id).update(
        {AuthSession.revoked_at: utc_now()},
        synchronize_session=False,
    )
    db.commit()
    _clear_auth_cookies(response)
    return MessageOut(message="Password changed. Sign in again on your devices.")


@router.post("/email-verification/request", response_model=MessageOut, status_code=status.HTTP_202_ACCEPTED)
def request_email_verification(
    payload: EmailVerificationRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> MessageOut:
    if not email_delivery_configured():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Email verification delivery is not configured. Contact the workspace administrator.",
        )
    email = str(payload.email).strip().lower()
    _rate_limit(db, request, "email-verification", email)
    user = db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
    if user and not user.is_verified:
        try:
            _send_email_verification(db, user)
            db.commit()
        except EmailDeliveryError:
            db.rollback()
            logger.error("Email verification delivery failed.")
    return MessageOut(message=VERIFICATION_MESSAGE)


@router.post("/email-verification/confirm", response_model=MessageOut)
def confirm_email_verification(
    payload: EmailVerificationConfirm,
    db: Session = Depends(get_db),
) -> MessageOut:
    token_record = db.query(EmailVerificationToken).filter(
        EmailVerificationToken.token_hash == hash_opaque_token(payload.token),
        EmailVerificationToken.used_at.is_(None),
        EmailVerificationToken.expires_at > utc_now(),
    ).with_for_update().first()
    if not token_record:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email verification link is invalid or expired.")
    user = db.get(User, token_record.user_id)
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email verification link is invalid or expired.")
    user.is_verified = True
    token_record.used_at = utc_now()
    db.commit()
    return MessageOut(message="Email verified. You can now sign in.")


@router.post("/password-reset/request", response_model=MessageOut, status_code=status.HTTP_202_ACCEPTED)
def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> MessageOut:
    if not email_delivery_configured():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Password reset delivery is not configured. Contact the workspace administrator.",
        )
    email = str(payload.email).strip().lower()
    _rate_limit(db, request, "password-reset", email)
    user = db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
    if user:
        token = secrets.token_urlsafe(32)
        token_record = PasswordResetToken(
            user_id=user.id,
            token_hash=hash_opaque_token(token),
            expires_at=utc_now() + timedelta(minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
        )
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        ).delete(synchronize_session=False)
        db.add(token_record)
        db.commit()
        reset_url = f"{FRONTEND_BASE_URL}/#reset_token={token}"
        try:
            send_security_email(
                email,
                "Reset your ContractIQ password",
                f"Use this one-time link to reset your password. It expires in "
                f"{PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes:\n\n{reset_url}\n\n"
                "If you did not request this, you can ignore this email.",
            )
        except EmailDeliveryError:
            db.delete(token_record)
            db.commit()
            logger.error("Password reset email delivery failed.")
    return MessageOut(message=RESET_MESSAGE)


@router.post("/password-reset/confirm", response_model=MessageOut)
def confirm_password_reset(
    payload: PasswordResetConfirm,
    db: Session = Depends(get_db),
) -> MessageOut:
    token_record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == hash_opaque_token(payload.token),
        PasswordResetToken.used_at.is_(None),
        PasswordResetToken.expires_at > utc_now(),
    ).with_for_update().first()
    if not token_record:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Password reset link is invalid or expired.")
    user = db.get(User, token_record.user_id)
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Password reset link is invalid or expired.")
    user.hashed_password = hash_password(payload.new_password)
    token_record.used_at = utc_now()
    db.query(AuthSession).filter(AuthSession.user_id == user.id).update(
        {AuthSession.revoked_at: utc_now()},
        synchronize_session=False,
    )
    db.commit()
    return MessageOut(message="Password updated. You can now sign in.")


_DUMMY_PASSWORD_HASH = hash_password("ContractIQ-invalid-login-dummy-secret")
