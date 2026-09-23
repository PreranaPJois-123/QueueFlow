"""
Simple fixed-window rate limiter backed by Redis. Not perfectly precise
(no sliding window), but cheap, explainable, and enough to blunt naive
abuse of auth/join endpoints without adding a dependency like slowapi.
"""
import time

from fastapi import Request, HTTPException, status

from app.core.config import settings
from app.core.redis_client import redis_client


def rate_limit(request: Request):
    if settings.ENV == "test":
        return
    client_ip = request.client.host if request.client else "unknown"
    window = int(time.time() // 60)
    key = f"ratelimit:{client_ip}:{window}"
    try:
        with redis_client.pipeline(transaction=True) as pipeline:
            pipeline.incr(key)
            pipeline.expire(key, 65)
            count, _ = pipeline.execute()
        if count > settings.RATE_LIMIT_PER_MINUTE:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests, slow down")
    except HTTPException:
        raise
    except Exception:
        # If Redis is unreachable, fail open rather than taking the API down.
        return
