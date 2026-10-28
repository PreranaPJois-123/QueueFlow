from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.sessions import resolve_session
from app.models.models import User, UserRole

_UNAUTHENTICATED = HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in to continue")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    session = resolve_session(db, request.cookies.get(settings.SESSION_COOKIE_NAME))
    if session is None:
        raise _UNAUTHENTICATED
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise _UNAUTHENTICATED
    request.state.session = session
    return user


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    try:
        return get_current_user(request, db)
    except HTTPException:
        return None


def require_roles(*roles: UserRole):
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission to perform this action")
        return current_user
    return dependency


require_staff = require_roles(UserRole.STAFF, UserRole.ADMIN)
require_admin = require_roles(UserRole.ADMIN)
