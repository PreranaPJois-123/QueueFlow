"""Fixed-window rate limiting backed by Redis, with an in-process fallback.

If Redis is unreachable the limiter keeps working per process instead of
failing open, so brute-force protection survives a cache outage.
"""
import threading
import time

from fastapi import HTTPException, Request, status

from app.core.config import settings
from app.core.redis_client import redis_client

_local: dict[str, tuple[int, float]] = {}
_local_lock = threading.Lock()


def _local_incr(key: str, window: int) -> int:
    now = time.time()
    with _local_lock:
        count, expires = _local.get(key, (0, now + window))
        if expires <= now:
            count, expires = 0, now + window
        count += 1
        _local[key] = (count, expires)
        if len(_local) > 50_000:  # bound memory under attack
            for k in [k for k, (_, e) in _local.items() if e <= now]:
                _local.pop(k, None)
        return count


def incr(key: str, window: int) -> int:
    try:
        with redis_client.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, window, nx=True)
            count, _ = pipe.execute()
        return int(count)
    except Exception:
        return _local_incr(key, window)


def get_count(key: str) -> int:
    try:
        value = redis_client.get(key)
        return int(value or 0)
    except Exception:
        with _local_lock:
            count, expires = _local.get(key, (0, 0))
            return count if expires > time.time() else 0


def reset(key: str) -> None:
    try:
        redis_client.delete(key)
    except Exception:
        pass
    with _local_lock:
        _local.pop(key, None)


def check(bucket: str, identity: str, limit: int, window: int = 60) -> None:
    if not settings.rate_limit_enabled:
        return
    key = f"rl:{bucket}:{identity}:{int(time.time() // window)}"
    if incr(key, window + 5) > limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests. Please wait a moment and try again.",
                            headers={"Retry-After": str(window)})


def client_ip(request: Request) -> str:
    # Uvicorn runs with --proxy-headers behind the nginx edge, which overwrites
    # X-Forwarded-For, so request.client is the real client address.
    return request.client.host if request.client else "unknown"


def rate_limit(request: Request):
    """General per-IP limit for write-heavy routes."""
    check("general", client_ip(request), settings.RATE_LIMIT_PER_MINUTE)


def auth_rate_limit(request: Request):
    check("auth", client_ip(request), settings.AUTH_RATE_LIMIT_PER_MINUTE)
