import redis

from app.core.config import settings

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=3, socket_timeout=3)
