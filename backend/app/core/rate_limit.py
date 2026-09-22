"""
Simple fixed-window rate limiter backed by Redis. Not perfectly precise
(no sliding window), but cheap, explainable, and enough to blunt naive
abuse of auth/join endpoints without adding a dependency like slowapi.
"""
import time

from fastapi import Request, HTTPException, status

from app.core.config import settings
from app.core.redis_client import redis_client


async def rate_limit(request: Request):
    if settings.ENV == "test":
        return
    client_ip = request.client.host if request.client else "unknown"
    window = int(time.time() // 60)
    key = f"ratelimit:{client_ip}:{window}"
    try:
        count = redis_client.incr(key)
        if count == 1:
            redis_client.expire(key, 65)
        if count > settings.RATE_LIMIT_PER_MINUTE:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests, slow down")
    except HTTPException:
        raise
    except Exception:
        # If Redis is unreachable, fail open rather than taking the API down.
        return
