from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import rate_limit as limiter
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.logging_config import logger
from app.core.security import (
    burn_verification_time, hash_password, needs_rehash, new_token, token_digest, verify_password,
)
from app.core.sessions import (
    clear_auth_cookies, create_session, new_csrf_token, resolve_session, revoke_all, revoke_session,
    set_auth_cookies,
)
from app.models.models import PasswordResetToken, User, UserRole
from app.schemas.schemas import (
    PasswordChange, PasswordResetConfirm, PasswordResetRequest, ProfileUpdate, SessionOut, UserLogin, UserOut,
    UserRegister,
)
from app.services import audit
from app.services.mailer import send_email

router = APIRouter(prefix="/api/auth", tags=["auth"])
LIMITED = [Depends(limiter.auth_rate_limit)]

RESET_ACCEPTED = {"detail": "If an account exists for that email, a reset link has been sent."}


def _start_session(db: Session, user: User, request: Request, response: Response) -> SessionOut:
    token, _ = create_session(db, user, request)
    csrf = new_csrf_token()
    db.commit()
    set_auth_cookies(response, token, csrf)
    return SessionOut(user=UserOut.model_validate(user), csrf_token=csrf)


@router.post("/register", response_model=SessionOut, status_code=status.HTTP_201_CREATED, dependencies=LIMITED)
def register(payload: UserRegister, request: Request, response: Response, db: Session = Depends(get_db)):
    if payload.role not in (None, UserRole.CUSTOMER):
        audit.record(db, "auth.register_escalation_blocked", request=request, email=payload.email.lower())
        db.commit()
        raise HTTPException(403, "Staff and admin accounts must be provisioned by an administrator")
    email = payload.email.lower()
    if db.query(User.id).filter(User.email == email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists. Try signing in.")
    user = User(email=email, hashed_password=hash_password(payload.password), full_name=payload.full_name,
                role=UserRole.CUSTOMER)
    db.add(user)
    try:
        db.flush()
    except IntegrityError:  # concurrent registration; the unique index is authoritative
        db.rollback()
        raise HTTPException(409, "An account with this email already exists. Try signing in.")
    audit.record(db, "auth.register", actor_id=user.id, entity_type="user", entity_id=user.id, request=request)
    return _start_session(db, user, request, response)


@router.post("/login", response_model=SessionOut, dependencies=LIMITED)
def login(payload: UserLogin, request: Request, response: Response, db: Session = Depends(get_db)):
    email = payload.email.lower()
    failure_key = f"loginfail:{email}"
    if settings.rate_limit_enabled and limiter.get_count(failure_key) >= settings.LOGIN_MAX_FAILURES:
        raise HTTPException(429, "Too many failed sign-in attempts. Wait 15 minutes or reset your password.")
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        burn_verification_time(payload.password)
    if user is None or not verify_password(payload.password, user.hashed_password) or not user.is_active:
        limiter.incr(failure_key, settings.LOGIN_FAILURE_WINDOW_SECONDS)
        audit.record(db, "auth.login_failed", actor_id=user.id if user else None, request=request, email=email)
        db.commit()
        # Same message for unknown email, wrong password and disabled account.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    limiter.reset(failure_key)
    if needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(payload.password)
    # Any session cookie presented at login is discarded: a fresh session is
    # always issued, which prevents session fixation.
    old = resolve_session(db, request.cookies.get(settings.SESSION_COOKIE_NAME))
    if old is not None:
        revoke_session(db, old)
    audit.record(db, "auth.login", actor_id=user.id, entity_type="user", entity_id=user.id, request=request)
    return _start_session(db, user, request, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    session = resolve_session(db, request.cookies.get(settings.SESSION_COOKIE_NAME))
    if session is not None:
        revoke_session(db, session)
        audit.record(db, "auth.logout", actor_id=session.user_id, request=request)
        db.commit()
    clear_auth_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(request: Request, response: Response, db: Session = Depends(get_db),
               current_user: User = Depends(get_current_user)):
    revoke_all(db, current_user.id)
    audit.record(db, "auth.logout_all", actor_id=current_user.id, request=request)
    db.commit()
    clear_auth_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/session", response_model=SessionOut)
def current_session(request: Request, response: Response, current_user: User = Depends(get_current_user)):
    """Current user plus the CSRF token (for deployments where the SPA cannot read the cookie)."""
    csrf = request.cookies.get(settings.CSRF_COOKIE_NAME)
    if not csrf:
        csrf = new_csrf_token()
        response.set_cookie(settings.CSRF_COOKIE_NAME, csrf, httponly=False, path="/", secure=settings.cookie_secure,
                            samesite=settings.COOKIE_SAMESITE.lower(), max_age=settings.SESSION_TTL_HOURS * 3600)
    return SessionOut(user=UserOut.model_validate(current_user), csrf_token=csrf)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserOut)
def update_profile(payload: ProfileUpdate, db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    for field in ("full_name", "pref_sound_enabled", "pref_browser_enabled"):
        value = getattr(payload, field)
        if value is not None:
            setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT, dependencies=LIMITED)
def change_password(payload: PasswordChange, request: Request, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(400, "Current password is incorrect")
    if payload.new_password == payload.current_password:
        raise HTTPException(400, "Choose a password different from your current one")
    current_user.hashed_password = hash_password(payload.new_password)
    current_user.password_changed_at = datetime.now(timezone.utc)
    revoke_all(db, current_user.id, except_session_id=request.state.session.id)
    audit.record(db, "auth.password_changed", actor_id=current_user.id, request=request)
    db.commit()


@router.get("/capabilities")
def capabilities():
    return {"password_reset_email": settings.smtp_configured}


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED, dependencies=LIMITED)
def request_password_reset(payload: PasswordResetRequest, request: Request, db: Session = Depends(get_db)):
    limiter.check("reset", payload.email.lower(), 3, window=900)
    user = db.query(User).filter(User.email == payload.email.lower(), User.is_active.is_(True)).first()
    if user is not None:
        token = new_token()
        db.add(PasswordResetToken(user_id=user.id, token_hash=token_digest(token),
                                  expires_at=datetime.now(timezone.utc)
                                  + timedelta(minutes=settings.PASSWORD_RESET_TTL_MINUTES)))
        audit.record(db, "auth.password_reset_requested", actor_id=user.id, request=request)
        db.commit()
        link = f"{settings.PUBLIC_APP_URL.rstrip('/')}/reset-password?token={token}"
        sent = send_email(user.email, "Reset your QueueFlow password",
                          f"Use this link within {settings.PASSWORD_RESET_TTL_MINUTES} minutes to choose a new "
                          f"password:\n\n{link}\n\nIf you did not request this, you can ignore this email.")
        if not sent:
            if settings.ENV == "development":
                logger.warning(f"[development only] SMTP not configured; password reset link: {link}")
            else:
                logger.warning("Password reset requested but email delivery is not configured or failed")
    # Identical response whether or not the account exists.
    return RESET_ACCEPTED


@router.post("/password-reset/confirm", dependencies=LIMITED)
def confirm_password_reset(payload: PasswordResetConfirm, request: Request, response: Response,
                           db: Session = Depends(get_db)):
    record = (db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == token_digest(payload.token))
              .with_for_update().first())
    now = datetime.now(timezone.utc)
    if record is None or record.used_at is not None or record.expires_at.replace(tzinfo=record.expires_at.tzinfo
                                                                                 or timezone.utc) <= now:
        raise HTTPException(400, "This reset link is invalid or has expired. Request a new one.")
    user = db.get(User, record.user_id)
    user.hashed_password = hash_password(payload.new_password)
    user.password_changed_at = now
    record.used_at = now
    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id,
                                        PasswordResetToken.used_at.is_(None)).update({"used_at": now})
    revoke_all(db, user.id)
    limiter.reset(f"loginfail:{user.email}")
    audit.record(db, "auth.password_reset_completed", actor_id=user.id, request=request)
    db.commit()
    clear_auth_cookies(response)
    return {"detail": "Password updated. Please sign in with your new password."}
