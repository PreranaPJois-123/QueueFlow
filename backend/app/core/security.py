from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

# We call the `bcrypt` library directly rather than going through passlib's
# CryptContext: passlib 1.7.4 (last released 2020) probes bcrypt's internal
# `__about__` module to detect the backend, which bcrypt >=4.1 no longer
# ships — that raises at hash time. Calling bcrypt directly avoids the
# unmaintained compatibility shim entirely.
_BCRYPT_MAX_BYTES = 72  # bcrypt silently ignores bytes beyond this; we validate instead


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > _BCRYPT_MAX_BYTES:
        raise ValueError(f"Password must be at most {_BCRYPT_MAX_BYTES} bytes")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM], options={"require_exp": True, "require_sub": True})
    except JWTError:
        return None
