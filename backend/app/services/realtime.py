"""Realtime fan-out over Redis pub/sub, with local delivery as a fallback.

Producers (sync service code, any thread) call ``enqueue(db, channel, event)``.
Events are published only after the surrounding transaction commits, so a
rolled-back booking never produces a notification. Each backend instance
subscribes to ``qf:*`` and forwards messages to its own WebSockets, so events
reach users connected to any instance.

Channels: ``user:<id>`` (private to that user) and ``queue:<id>`` (public
walk-in queue boards that contain no personal data).
"""
import asyncio
import json
from collections import defaultdict
from typing import Any

from fastapi import WebSocket
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging_config import logger
from app.core.redis_client import redis_client

PREFIX = "qf:"


class LocalHub:
    def __init__(self) -> None:
        self.sockets: dict[str, set[WebSocket]] = defaultdict(set)
        self.loop: asyncio.AbstractEventLoop | None = None

    def add(self, channel: str, ws: WebSocket) -> None:
        self.sockets[channel].add(ws)

    def remove(self, channel: str, ws: WebSocket) -> None:
        conns = self.sockets.get(channel)
        if conns is not None:
            conns.discard(ws)
            if not conns:
                self.sockets.pop(channel, None)

    def count(self, channel: str) -> int:
        return len(self.sockets.get(channel, ()))

    async def deliver(self, channel: str, payload: dict[str, Any]) -> None:
        message = json.dumps(payload, default=str)
        for ws in tuple(self.sockets.get(channel, ())):
            try:
                await ws.send_text(message)
            except Exception:
                self.remove(channel, ws)

    def deliver_threadsafe(self, channel: str, payload: dict[str, Any]) -> None:
        loop = self.loop
        if loop is None or loop.is_closed():
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            loop.create_task(self.deliver(channel, payload))
        else:
            asyncio.run_coroutine_threadsafe(self.deliver(channel, payload), loop)


hub = LocalHub()


def publish(channel: str, payload: dict[str, Any]) -> None:
    if settings.REALTIME_BACKEND == "redis":
        try:
            redis_client.publish(PREFIX + channel, json.dumps(payload, default=str))
            return
        except Exception:
            logger.warning("Redis publish failed; delivering to this instance only")
    hub.deliver_threadsafe(channel, payload)


def enqueue(db: Session, channel: str, payload: dict[str, Any]) -> None:
    db.info.setdefault("realtime_events", []).append((channel, payload))


@event.listens_for(Session, "after_commit")
def _flush_events(session: Session) -> None:
    events = session.info.pop("realtime_events", None)
    for channel, payload in events or ():
        try:
            publish(channel, payload)
        except Exception:
            logger.exception("Realtime publish failed")


@event.listens_for(Session, "after_rollback")
def _drop_events(session: Session) -> None:
    session.info.pop("realtime_events", None)


async def subscriber_loop() -> None:
    """Forward Redis messages to local sockets; reconnect with backoff."""
    import redis.asyncio as aioredis

    delay = 1.0
    while True:
        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=3)
        try:
            pubsub = client.pubsub()
            await pubsub.psubscribe(PREFIX + "*")
            delay = 1.0
            async for message in pubsub.listen():
                if message.get("type") != "pmessage":
                    continue
                channel = message["channel"][len(PREFIX):]
                if channel in hub.sockets:
                    try:
                        await hub.deliver(channel, json.loads(message["data"]))
                    except ValueError:
                        continue
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning(f"Realtime subscriber disconnected; retrying in {delay:.0f}s")
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)
        finally:
            try:
                await client.aclose()
            except Exception:
                pass
