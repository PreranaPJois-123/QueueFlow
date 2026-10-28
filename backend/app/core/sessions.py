"""Server-side browser sessions carried in an HttpOnly cookie.

* ``qf_session`` (HttpOnly, SameSite) holds a random 256-bit token. The
  database stores only an HMAC of it (see ``token_digest``).
* ``qf_csrf`` (readable by the SPA) holds a random CSRF token. Every unsafe
  request carrying a session must echo it in ``X-CSRF-Token`` (double submit).
* Sessions have an absolute lifetime and an idle timeout, and are revoked on
  logout, "log out everywhere", password change and password reset.
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Request, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import new_token, token_digest
from app.models.models import User, UserSession

_TOUCH_INTERVAL = timedelta(minutes=1)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def create_session(db: Session, user: User, request: Optional[Request]) -> tuple[str, UserSession]:
    token = new_token()
    session = UserSession(
        user_id=user.id,
        token_hash=token_digest(token),
        expires_at=_now() + timedelta(hours=settings.SESSION_TTL_HOURS),
        user_agent=(request.headers.get("user-agent", "")[:255] if request else None),
        ip_address=(request.client.host if request and request.client else None),
    )
    db.add(session)
    db.flush()
    return token, session


def resolve_session(db: Session, raw_token: Optional[str]) -> Optional[UserSession]:
    if not raw_token or len(raw_token) > 128:
        return None
    session = db.query(UserSession).filter(UserSession.token_hash == token_digest(raw_token)).first()
    if session is None or session.revoked_at is not None:
        return None
    now = _now()
    if _utc(session.expires_at) <= now:
        return None
    if _utc(session.last_seen_at) + timedelta(minutes=settings.SESSION_IDLE_MINUTES) <= now:
        return None
    if now - _utc(session.last_seen_at) > _TOUCH_INTERVAL:
        session.last_seen_at = now
        db.commit()
    return session


def revoke_session(db: Session, session: UserSession) -> None:
    if session.revoked_at is None:
        session.revoked_at = _now()


def revoke_all(db: Session, user_id: str, except_session_id: Optional[str] = None) -> int:
    query = db.query(UserSession).filter(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
    if except_session_id:
        query = query.filter(UserSession.id != except_session_id)
    return query.update({UserSession.revoked_at: _now()}, synchronize_session=False)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def set_auth_cookies(response: Response, session_token: str, csrf_token: str) -> None:
    max_age = settings.SESSION_TTL_HOURS * 3600
    common = dict(max_age=max_age, path="/", secure=settings.cookie_secure, samesite=settings.COOKIE_SAMESITE.lower())
    response.set_cookie(settings.SESSION_COOKIE_NAME, session_token, httponly=True, **common)
    response.set_cookie(settings.CSRF_COOKIE_NAME, csrf_token, httponly=False, **common)


def clear_auth_cookies(response: Response) -> None:
    for name in (settings.SESSION_COOKIE_NAME, settings.CSRF_COOKIE_NAME):
        response.delete_cookie(name, path="/", secure=settings.cookie_secure,
                               samesite=settings.COOKIE_SAMESITE.lower())
