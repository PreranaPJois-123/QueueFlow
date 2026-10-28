"""Password hashing (Argon2id) and opaque-token helpers.

Legacy bcrypt hashes from earlier releases still verify and are transparently
upgraded to Argon2id on the next successful login.
"""
import hashlib
import hmac
import secrets

import bcrypt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import settings

# OWASP-recommended Argon2id baseline (m=19 MiB, t=2, p=1) is the floor; these
# argon2-cffi defaults (m=64 MiB, t=3, p=4) are stronger and fast enough here.
_hasher = PasswordHasher()
MAX_PASSWORD_CHARS = 128


def hash_password(password: str) -> str:
    if len(password) > MAX_PASSWORD_CHARS:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_CHARS} characters")
    return _hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if hashed_password.startswith("$argon2"):
        try:
            return _hasher.verify(hashed_password, plain_password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False
    if hashed_password.startswith("$2"):
        try:
            return bcrypt.checkpw(plain_password.encode("utf-8")[:72], hashed_password.encode("utf-8"))
        except ValueError:
            return False
    return False


def needs_rehash(hashed_password: str) -> bool:
    if not hashed_password.startswith("$argon2"):
        return True
    try:
        return _hasher.check_needs_rehash(hashed_password)
    except InvalidHashError:
        return True


# A dummy hash so failed lookups take comparable time to real verifications.
_DUMMY_HASH = _hasher.hash("timing-equalisation-only")


def burn_verification_time(password: str) -> None:
    verify_password(password, _DUMMY_HASH)


def new_token() -> str:
    """256-bit URL-safe random token."""
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> str:
    """Keyed digest stored in the database instead of the raw token, so a
    database leak alone cannot be replayed as live sessions or reset links."""
    return hmac.new(settings.JWT_SECRET_KEY.encode(), token.encode(), hashlib.sha256).hexdigest()
